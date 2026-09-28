import os
import subprocess

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKFLOWS = os.path.join(ROOT, ".github", "workflows")
COLLECT_STEP = "Commit station history"


def read_workflow(name):
    """Текст workflow из репозитория.

    Переводы строк нормализованы: .gitattributes в репозитории нет, поэтому
    core.autocrlf машины, на которой гоняют тесты, не должен решать, что
    записано в .github/workflows.
    """
    with open(os.path.join(WORKFLOWS, name), encoding="utf-8") as f:
        return f.read().replace("\r\n", "\n")


def step_run(yml, step_name):
    """Тело `run:` указанного шага.

    Проверяется сам скрипт шага, а не его пересказ в тесте: у снимков станций
    важна не отдельная строка, а порядок команд внутри блока.
    """
    lines = yml.splitlines()
    idx = next((i for i, ln in enumerate(lines)
                if ln.strip() == "- name: " + step_name), None)
    assert idx is not None, "в workflow нет шага %r" % step_name
    step_indent = len(lines[idx]) - len(lines[idx].lstrip())
    end = len(lines)
    for i in range(idx + 1, len(lines)):
        stripped = lines[i]
        if stripped.strip() and len(stripped) - len(stripped.lstrip()) <= step_indent:
            end = i
            break
    body = lines[idx + 1:end]
    run = next((i for i, ln in enumerate(body) if ln.strip() == "run: |"), None)
    assert run is not None, "у шага %r нет run: |" % step_name
    script = body[run + 1:]
    pad = min((len(ln) - len(ln.lstrip()) for ln in script if ln.strip()),
              default=0)
    return "\n".join(ln[pad:] for ln in script)


def run_scripts(yml):
    """Все блоки `run:` workflow, склеенные в один текст.

    Команды, а не комментарии: инвариант «воркфлоу не трогает снимок» должен
    ловить git add / git diff / cp, а не упоминание файла в пояснении.
    """
    lines = yml.splitlines()
    out = []
    for i, ln in enumerate(lines):
        if ln.strip().startswith("run: ") and not ln.strip().endswith("|"):
            out.append(ln.strip()[len("run: "):])
            continue
        if ln.strip() != "run: |":
            continue
        pad = len(ln) - len(ln.lstrip()) + 2
        body = []
        for nxt in lines[i + 1:]:
            if nxt.strip() and len(nxt) - len(nxt.lstrip()) < pad:
                break
            body.append(nxt[pad:])
        out.append("\n".join(body))
    return "\n".join(out)


def _git(*args):
    return subprocess.run(["git"] + list(args), cwd=ROOT,
                          capture_output=True, text=True)


def _ignored(path):
    return _git("check-ignore", "-q", "--no-index", path).returncode == 0


def test_sensors_workflow_commits_history_so_it_survives_between_runs():
    # data/ в .gitignore, и каждый запуск CI начинается с чистого checkout —
    # единственное долговременное хранилище накопленной истории это коммит
    # раз в 15 минут. Без него meteo.py на следующей сборке читает пустую
    # историю, и столбик «Датчик» в таблице «Часы» теряет данные.
    yml = read_workflow("sensors.yml")
    script = step_run(yml, COLLECT_STEP)
    assert "git add sensors_history.json" in script
    assert "git push" in script


def test_sensors_commit_checks_the_staged_file_not_the_untracked_one():
    # sensors_history.json до первого прогона в репозитории нет: чистый checkout
    # не приносит его, файл появляется только когда коллектор его запишет.
    # git diff невидит для неотслеживаемых файлов, поэтому решение «нечего
    # коммитить» по unstaged-diff на самом первом прогоне всегда было бы
    # положительным — и история не закоммитилась бы никогда. Значит, файл
    # сначала индексируется, а решение принимается по staged-diff.
    script = step_run(read_workflow("sensors.yml"), COLLECT_STEP)
    assert "git diff --cached --quiet -- sensors_history.json" in script
    assert script.index("git add sensors_history.json") < \
        script.index("git diff --cached --quiet -- sensors_history.json")
    assert "git diff --quiet -- sensors_history.json" not in script


def test_sensors_workflow_does_not_commit_the_snapshot_nobody_reads():
    # sensors.json писался collect_sensors.py как диагностический снимок, но
    # после переезда измерений в столбик «Датчик» его не читает ни одна
    # страница: ни template.html, ни nowcast_template.html, ни meteo.py, ни
    # собранные index.html/nowcast.html. Коммит раз в 15 минут файла с нулём
    # потребителей — это ~96 коммитов в сутки впустую; в историю попадает
    # только sensors_history.json.
    yml = read_workflow("sensors.yml")
    assert "sensors_history.json" in yml
    assert "sensors.json" not in run_scripts(yml), (
        "sensors.yml снова коммитит снимок sensors.json, который не читает ни "
        "одна страница. Долговременное хранилище — sensors_history.json, "
        "снимок остаётся локальным диагностическим файлом."
    )


def test_deploy_does_not_publish_the_snapshot_nobody_reads():
    # Инверсия потерянного с Task 6 теста (test_deploy_copies_snapshot_into_site).
    # deploy.yml копирует в _site/ явный список файлов, и снимок был в нём
    # только ради слоя станций на карте. Слоя больше нет, «Датчик» живёт в
    # таблице «Часы» и в данные попадает через meteo.py, поэтому публиковать
    # снимок нечего: читателей у него ноль, а наружу уехали бы сырые
    # показания станций.
    yml = read_workflow("deploy.yml")
    assert "sensors.json" not in yml, (
        "deploy.yml снова публикует sensors.json в _site/. Файл не читает ни "
        "одна страница сайта — слой станций убран с карты Task 6, измерения "
        "живут в столбике «Датчик» таблицы «Часы». Публиковать нечего."
    )


def test_deploy_does_not_publish_station_history():
    # sensors_history.json — серверный вход meteo.py, а не ассет страницы.
    # Наружу он не публикуется никогда.
    assert "sensors_history.json" not in read_workflow("deploy.yml")


def test_station_snapshot_is_untracked_and_ignored_narrowly():
    if not os.path.isdir(os.path.join(ROOT, ".git")):
        pytest.skip("проверка трекинга имеет смысл только внутри git-репозитория")
    # Снимок остаётся на диске (collect_sensors.py пишет его при каждом прогоне),
    # но в индекс не попадает: коммитить его нечего, читателей нет.
    assert _git("ls-files", "--", "sensors.json").stdout.strip() == "", \
        "sensors.json всё ещё отслеживается git — его коммитят 96 раз в сутки"
    assert _ignored("sensors.json"), "sensors.json не в .gitignore"

    # Правило узкое: ни история (её коммитить обязательно), ни одноимённый
    # файл Task 8 под него не попадают.
    assert not _ignored("sensors_history.json"), \
        "правило для sensors.json накрыло sensors_history.json — историю " \
        "нечем будет коммитить, и она обнулится на каждом CI-запуске"
    assert not _ignored("sensors_yar.json"), \
        "правило для sensors.json слишком широкое — накрывает sensors_yar.json"
