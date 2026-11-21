# Design: раздельный деплой Pages, чтобы уйти от гонки артефакта

Дата: 2026-11-21

## Проблема

В ноябре участились падения `Deploy MeteoMap to Pages`. Из 10 последующих за
20–21.11 падений 9 были на последнем шаге:

```
Fetching artifact metadata for "github-pages" in this workflow run
Found 0 artifact(s)
Error: No artifacts named "github-pages" were found for this workflow run.
```

При этом шаг `actions/upload-pages-artifact` в том же прогоне завершался
успешно, а артефакт `github-pages` позже присутствовал в API с тем же
ID. Таймкоды: загрузка финализирована в `10:16:51Z`, деплой начался в ту же
секунду. Это известная гонка `actions/deploy-pages#451`: при загрузке и
деплое в одном job lookup иногда не видит только что зафиксированный
артефакт. Повторный запуск шага не помогает — он добавляет второй артефакт
с тем же именем и ломается уже на «Multiple artifacts named github-pages».

Отдельно 20.11 был один случай другого плана: Open-Meteo отдавал 429 и read timeouts
по всем моделям, `meteo.py` прервался на `no model data available`. К текущим
падениям это отношения не имеет — тесты и генерация в них проходили.

## Почему не время запуска

Основной триггер — внешний `workflow_dispatch` каждые 15 минут (это зафиксировано
в `test_header_refresh_caption_is_fifteen_minutes`); cron `0 * * * *`
в `deploy.yml` — только подстраховка. Сдвиг cron не уменьшит частоту запусков
и не повлияет на гонку между шагами внутри job.

## Решение

- `deploy.yml` разделён на два job: `build` (всё до `upload-pages-artifact`)
  и `deploy` (`needs: build`, environment `github-pages`).
- Перед `actions/deploy-pages@v4` добавлена пауза `sleep 5`: даже при быстром
  старте второго job API успевает увидеть артефакт.
- Права и `concurrency: pages / cancel-in-progress: true` остались прежними.

## Тесты

- `test_pages_upload_and_deploy_are_in_separate_jobs` проверяет, что загрузка
  и публикация разнесены по job, второй зависит от первого и содержит паузу.
- Остальные тесты workflow и весь набор — без изменений.
