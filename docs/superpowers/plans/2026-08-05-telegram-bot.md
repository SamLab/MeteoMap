# Telegram-бот MeteoMap (PHP-вебхук) — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Один PHP-файл `bot.php`, работающий вебхуком на shared-хостинге Hostland, который по команде `/погода`/`/weather` (или любому тексту) отвечает сводкой погоды из задеплоенного `index.html`.

**Architecture:** Telegram присылает update на `bot.php`. Скрипт скачивает `index.html` с GitHub Pages (`https://samlab.github.io/MeteoMap/index.html`), вырезает JSON из тега `<script id="data" type="application/json">`, декодирует в массив и пересчитывает на PHP те же формулы, что JS на сайте (max/min сегодня, ближайший дождь/гроза/град, источники). Ответ отправляется прямым вызовом `sendMessage` через Bot API (`file_get_contents` + stream context, без cURL-зависимости).

**Tech Stack:** PHP 8.1+ (совместим с shared-хостингом), Bot API (getUpdates/setWebhook/sendMessage), стандартная библиотека. Без Composer, без внешних зависимостей.

## Global Constraints

- Один файл `bot.php` — весь функционал (парсинг, расчёт, Telegram), пригоден для FTP-заливки.
- Совместимость с PHP 8.1+; не использовать PHP 8.2+/8.3+-only синтаксис без необходимости.
- Числовые форматы совпадают с сайтом: `fmt` — 1 знак (`Math.round(v*10)/10`, без хвостовых нулей), `num` — целое, `temp` — `+23°` для положительных.
- Карта погодных кодов `wcode` идентична сайту (иконки-эмодзи).
- Давление в payload уже в мм рт. ст. (конвертация в `meteo.py`), PHP не пересчитывает.
- Время в payload — московское, строки `YYYY-MM-DDTHH:00`; сравнение лексикографическое.
- `curIdx` = первый индекс, где `D.time[i] >= curHour` (текущий час по `Europe/Moscow`).
- Тесты запускаются локально: `php tests/test_bot.php` (PHP установить через winget, Task 1).
- `BOT_TOKEN` — пустая строка в репозитории; пользователь заполняет перед FTP-заливкой.

---

### Task 1: Установить PHP локально для тестов

**Files:**
- (система, без изменений в репозитории)

**Interfaces:**
- Produces: команда `php` доступна в PowerShell.

- [ ] **Step 1: Установить PHP через winget**

Run (в PowerShell):
```powershell
winget install --id PHP.PHP.8.3 -e --accept-source-agreements --accept-package-agreements
```

- [ ] **Step 2: Проверить установку**

Run: `php -v`
Expected: `PHP 8.3.32 (cli) ...` (или 8.3.x)

- [ ] **Step 3: Если `php` не найден — добавить в PATH вручную**

Найти путь установки:
```powershell
Get-ChildItem "$env:LOCALAPPDATA\Programs" -Directory -Filter "*PHP*" -ErrorAction SilentlyContinue | Select-Object FullName
```
Добавить папку с `php.exe` в PATH текущей сессии (повторять в каждом новом терминале) или через «Переменные среды» (навсегда):
```powershell
$env:Path += ";C:\полный\путь\к\php"
```
Проверить: `php -v`.

- [ ] **Step 4: Проверить наличие нужных расширений**

Run: `php -m | Select-String "json"`
Expected: `json` присутствует (входит в ядро PHP 8).

---

### Task 2: Каркас bot.php — константы, форматтеры, WCODE

**Files:**
- Create: `bot.php`
- Create: `tests/test_bot.php`

**Interfaces:**
- Consumes: ничего (чистые функции).
- Produces:
  - `const SITE_URL = 'https://samlab.github.io/MeteoMap/index.html'`
  - `const BOT_TOKEN = ''`
  - `fmt($v): string` — 1 знак, без хвостовых нулей; `—` для null.
  - `num($v): string` — целое; `—` для null.
  - `temp($v): string` — `+23°`; `—` для null.
  - `wcode($c): array` — `[текст, иконка]`; для неизвестного кода `['—','']`.
  - `rumb_short($deg): string` — `С/СВ/В/ЮВ/Ю/ЮЗ/З/СЗ`; `—` для null.
  - `DOW_SHORT` — `['Вс','Пн','Вт','Ср','Чт','Пт','Сб']`.
  - `day_short($iso): string` — `Чт 6`.
  - `tstr($iso): string` — `Чт 6 в 14:00`.

- [ ] **Step 1: Написать падающий тест** (`tests/test_bot.php`)

```php
<?php
require __DIR__ . '/../bot.php';

$fail = 0;
function eq($name, $actual, $expected) {
    global $fail;
    if ($actual === $expected) { echo "PASS $name\n"; }
    else { $fail++; echo "FAIL $name\n  got: " . var_export($actual, true) . "\n  exp: " . var_export($expected, true) . "\n"; }
}

eq('fmt null', fmt(null), '—');
eq('fmt 0.1', fmt(0.1), '0.1');
eq('fmt 17.0', fmt(17.0), '17');
eq('fmt 1.25', fmt(1.25), '1.3');
eq('num 17.7', num(17.7), '18');
eq('num null', num(null), '—');
eq('temp +23', temp(23), '+23°');
eq('temp -4', temp(-4), '-4°');
eq('temp null', temp(null), '—');
eq('wcode 95', wcode(95), ['Гроза', '⚡']);
eq('wcode 999', wcode(999), ['—', '']);
eq('rumb 225', rumb_short(225), 'ЮЗ');
eq('rumb null', rumb_short(null), '—');
eq('day_short', day_short('2026-08-06T14:00'), 'Чт 6');
eq('tstr', tstr('2026-08-06T14:00'), 'Чт 6 в 14:00');

if ($fail) { fwrite(STDERR, "$fail failures\n"); exit(1); }
echo "OK\n";
```

- [ ] **Step 2: Запустить тест и убедиться, что падает**

Run: `php tests/test_bot.php`
Expected: `PHP Fatal error: Uncaught Error: Call to undefined function fmt()` (или подобное).

- [ ] **Step 3: Реализовать каркас** (`bot.php`)

```php
<?php
declare(strict_types=1);

date_default_timezone_set('Europe/Moscow');

const SITE_URL = 'https://samlab.github.io/MeteoMap/index.html';
const BOT_TOKEN = '';

const DOW_SHORT = ['Вс', 'Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб'];
const COMPASS = ['С', 'СВ', 'В', 'ЮВ', 'Ю', 'ЮЗ', 'З', 'СЗ'];

function fmt($v): string {
    if ($v === null || $v === '') return '—';
    $s = number_format((float)$v, 1, '.', '');
    $s = rtrim($s, '0');
    $s = rtrim($s, '.');
    return $s === '' ? '0' : $s;
}

function num($v): string {
    if ($v === null || $v === '') return '—';
    return (string)round((float)$v);
}

function temp($v): string {
    if ($v === null || $v === '') return '—';
    $r = (int)round((float)$v);
    return ($r > 0 ? '+' : '') . $r . '°';
}

const WCODE = [
    0 => ['Ясно', '☀️'], 1 => ['В основном ясно', '🌤️'], 2 => ['Переменная облачность', '⛅'], 3 => ['Пасмурно', '☁️'],
    45 => ['Туман', '🌫️'], 48 => ['Изморозь', '🌫️'],
    51 => ['Небольшая морось', '🌦️'], 53 => ['Морось', '🌦️'], 55 => ['Сильная морось', '🌧️'],
    56 => ['Ледяная морось', '🌧️'], 57 => ['Ледяная морось', '🌧️'],
    61 => ['Небольшой дождь', '🌦️'], 63 => ['Дождь', '🌧️'], 65 => ['Сильный дождь', '🌧️'],
    66 => ['Ледяной дождь', '🌧️'], 67 => ['Ледяной дождь', '🌧️'],
    71 => ['Небольшой снег', '🌨️'], 73 => ['Снег', '❄️'], 75 => ['Сильный снег', '❄️'], 77 => ['Снежные зерна', '❄️'],
    80 => ['Небольшой ливень', '🌧️'], 81 => ['Ливень', '🌧️'], 82 => ['Сильный ливень', '⛈️'],
    85 => ['Снегопад', '🌨️'], 86 => ['Снегопад', '🌨️'],
    95 => ['Гроза', '⚡'], 96 => ['Гроза с градом', '⚡'], 99 => ['Гроза с градом', '⚡'],
];

function wcode($c): array {
    return WCODE[$c] ?? ['—', ''];
}

function rumb_short($deg): string {
    if ($deg === null || $deg === '') return '—';
    return COMPASS[((int)round((float)$deg / 45)) % 8];
}

function day_short($iso): string {
    $ts = strtotime((string)$iso);
    if ($ts === false) return '—';
    return DOW_SHORT[(int)date('w', $ts)] . ' ' . date('j', $ts);
}

function tstr($iso): string {
    $ts = strtotime((string)$iso);
    if ($ts === false) return '—';
    return DOW_SHORT[(int)date('w', $ts)] . ' ' . date('j', $ts) . ' в ' . date('H:i', $ts);
}
```

- [ ] **Step 4: Запустить тест**

Run: `php tests/test_bot.php`
Expected: все строки `PASS`, в конце `OK`.

- [ ] **Step 5: Проверить синтаксис**

Run: `php -l bot.php`
Expected: `No syntax errors detected in bot.php`.

- [ ] **Step 6: Commit**

```bash
git add bot.php tests/test_bot.php
git commit -m "feat(bot): bot.php skeleton with formatters and wcode map"
```

---

### Task 3: Парсинг index.html и curIdx

**Files:**
- Modify: `bot.php`
- Modify: `tests/test_bot.php`

**Interfaces:**
- Consumes: `fmt`, `num`, `temp` (Task 2).
- Produces:
  - `parse_payload($html): ?array` — вырезает JSON из `<script id="data" type="application/json">...</script>`, `json_decode(..., true)`; null при ошибке.
  - `fetch_payload($url): ?array` — `file_get_contents` с stream context (timeout 20, ignore_errors), затем `parse_payload`.
  - `cur_idx($data, $now = null): int` — первый `i`, где `$data['time'][$i] >= $now`; `$now` по умолчанию — текущий час по `Europe/Moscow` (`Y-m-d\TH:00`); если не найден — `0`.

- [ ] **Step 1: Написать падающий тест** (добавить в `tests/test_bot.php`)

```php
$html = "<html><body><script id=\"data\" type=\"application/json\">{\"time\":[\"2026-08-05T10:00\"],\"a\":1}</script></body></html>";
$p = parse_payload($html);
eq('parse_payload ok', is_array($p) && $p['a'] === 1, true);
eq('parse_payload bad', parse_payload('<html></html>'), null);

$fixture = fixture();
eq('cur_idx exact', cur_idx($fixture, '2026-08-05T10:00'), 10);
eq('cur_idx empty-data', cur_idx(['time' => []], '2026-08-05T10:00'), 0);

if ($fail) { fwrite(STDERR, "$fail failures\n"); exit(1); }
echo "OK\n";
```

И добавить функцию `fixture()` в начало `tests/test_bot.php`:

```php
function fixture(): array {
    $time = []; $temp = []; $wc = []; $pr = []; $pp = [];
    for ($d = 0; $d < 2; $d++) {
        for ($h = 0; $h < 24; $h++) {
            $time[] = ($d ? '2026-08-06' : '2026-08-05') . sprintf('T%02d:00', $h);
            $temp[] = 20; $wc[] = 0; $pr[] = 0; $pp[] = 0;
        }
    }
    $temp[15] = 24; $temp[23] = 17; $temp[39] = 25;
    $wc[14] = 63; $pr[14] = 0.1; $pp[14] = 17;
    $wc[34] = 95; $pr[34] = 1.1; $pp[34] = 11;
    $wc[38] = 96; $pr[38] = 1.3; $pp[38] = 46;
    $n = count($time);
    $models = [
        'ukmo' => ['weather_code' => array_fill(0, $n, 0)],
        'dwd'  => ['weather_code' => array_fill(0, $n, 0)],
    ];
    $models['ukmo']['weather_code'][14] = 61;
    $models['dwd']['weather_code'][14] = 61;
    $models['ukmo']['weather_code'][34] = 95;
    $models['dwd']['weather_code'][38] = 96;
    return [
        'model_codes' => ['ukmo', 'dwd'],
        'model_names' => ['ukmo' => 'UKMO Global', 'dwd' => 'DWD ICON'],
        'time' => $time,
        'weighted' => [
            'temperature_2m' => $temp,
            'apparent_temperature' => $temp,
            'precipitation' => $pr,
            'precipitation_probability' => $pp,
            'weather_code' => $wc,
            'wind_speed_10m' => array_fill(0, $n, 3),
            'wind_direction_10m' => array_fill(0, $n, 225),
            'pressure_msl' => array_fill(0, $n, 756),
            'relative_humidity_2m' => array_fill(0, $n, 62),
        ],
        'models' => $models,
    ];
}
```

- [ ] **Step 2: Запустить тест — падает**

Run: `php tests/test_bot.php`
Expected: `FAIL parse_payload ok` и `FAIL cur_idx ...` (функции не определены).

- [ ] **Step 3: Реализовать** (добавить в `bot.php` после `tstr`)

```php
function parse_payload($html): ?array {
    if (!preg_match('/<script id="data" type="application\/json">(.*?)<\/script>/s', (string)$html, $m)) {
        return null;
    }
    $data = json_decode($m[1], true);
    return is_array($data) ? $data : null;
}

function fetch_payload($url): ?array {
    $ctx = stream_context_create(['http' => ['timeout' => 20, 'ignore_errors' => true]]);
    $body = @file_get_contents((string)$url, false, $ctx);
    if ($body === false) return null;
    return parse_payload($body);
}

function cur_idx($data, $now = null): int {
    if ($now === null) {
        $now = (new DateTime('now', new DateTimeZone('Europe/Moscow')))->format('Y-m-d\TH:00');
    }
    foreach (($data['time'] ?? []) as $i => $t) {
        if (strcmp((string)$t, (string)$now) >= 0) return $i;
    }
    return 0;
}
```

- [ ] **Step 4: Запустить тест — зелёный**

Run: `php tests/test_bot.php`
Expected: все `PASS`, в конце `OK`.

- [ ] **Step 5: Commit**

```bash
git add bot.php tests/test_bot.php
git commit -m "feat(bot): parse index.html payload and compute curIdx"
```

---

### Task 4: Поисковые функции (дождь/гроза/град, max/min)

**Files:**
- Modify: `bot.php`
- Modify: `tests/test_bot.php`

**Interfaces:**
- Consumes: `fmt`, `num`, `temp`, `tstr` (Task 2), `cur_idx` (Task 3).
- Produces:
  - `source_list($data, $i, $list): array` — коды моделей, у которых `weather_code[$i]` в `$list`.
  - `source_count($data, $i, $list): int`.
  - `source_names($data, $i, $list): array` — имена моделей через массив.
  - `find_nearest_source($data, $from, $list): int` — первый час `>= $from`, где `source_count > 0`; иначе `-1`.
  - `find_rain_by_consensus($data, $from): int` — первый час `>= $from`, где `weighted.weather_code` в списке дождя `[51,53,55,56,57,61,63,65,66,67,80,81,82]`; иначе `-1`.
  - `rain_hour_today($data, $start): int` — первый час сегодня (та же дата, что `$data['time'][$start]`), где `weighted.weather_code` в списке дождя; иначе `-1`.
  - `today_minmax($data, $start): array` — `[maxIdx, minIdx]` по `temperature_2m` за сегодня; `-1` если нет.
  - `wet_str($data, $i): string` — ` на 0.1мм с 17%` (осадки/вероятность из `weighted`).

- [ ] **Step 1: Написать падающий тест** (добавить в `tests/test_bot.php`)

```php
$f = fixture();
eq('source_list rain', source_list($f, 14, [51,53,55,56,57,61,63,65,66,67,80,81,82]), ['ukmo', 'dwd']);
eq('source_count rain', source_count($f, 14, [51,53,55,56,57,61,63,65,66,67,80,81,82]), 2);
eq('source_names storm', source_names($f, 34, [95,96,99]), ['UKMO Global']);
eq('find storm', find_nearest_source($f, 11, [95,96,99]), 34);
eq('find hail', find_nearest_source($f, 11, [96,99]), 38);
eq('find rain', find_rain_by_consensus($f, 11), 14);
eq('rain today', rain_hour_today($f, 11), 14);
eq('rain today none', rain_hour_today($f, 24), -1);
$mm = today_minmax($f, 11);
eq('max idx', $mm[0], 15);
eq('min idx', $mm[1], 23);
eq('wet_str', wet_str($f, 14), ' на 0.1мм с 17%');
eq('wet_str zero', wet_str($f, 11), '');

if ($fail) { fwrite(STDERR, "$fail failures\n"); exit(1); }
echo "OK\n";
```

- [ ] **Step 2: Запустить тест — падает**

Run: `php tests/test_bot.php`
Expected: `FAIL` на неопределённых функциях.

- [ ] **Step 3: Реализовать** (добавить в `bot.php`)

```php
function source_list($data, $i, $list): array {
    $out = [];
    foreach (($data['model_codes'] ?? []) as $c) {
        $v = $data['models'][$c]['weather_code'][$i] ?? null;
        if (in_array($v, $list, true)) $out[] = $c;
    }
    return $out;
}

function source_count($data, $i, $list): int {
    return count(source_list($data, $i, $list));
}

function source_names($data, $i, $list): array {
    $res = [];
    foreach (source_list($data, $i, $list) as $c) {
        $res[] = $data['model_names'][$c] ?? $c;
    }
    return $res;
}

function find_nearest_source($data, $from, $list): int {
    for ($i = $from; $i < count($data['time'] ?? []); $i++) {
        if (source_count($data, $i, $list) > 0) return $i;
    }
    return -1;
}

function find_rain_by_consensus($data, $from): int {
    $codes = [51,53,55,56,57,61,63,65,66,67,80,81,82];
    foreach (($data['time'] ?? []) as $i => $t) {
        if ($i < $from) continue;
        if (in_array($data['weighted']['weather_code'][$i] ?? null, $codes, true)) return $i;
    }
    return -1;
}

function rain_hour_today($data, $start): int {
    $codes = [51,53,55,56,57,61,63,65,66,67,80,81,82];
    $today = isset($data['time'][$start]) ? substr((string)$data['time'][$start], 0, 10) : '';
    foreach (($data['time'] ?? []) as $i => $t) {
        if ($i < $start) continue;
        if (substr((string)$t, 0, 10) !== $today) break;
        if (in_array($data['weighted']['weather_code'][$i] ?? null, $codes, true)) return $i;
    }
    return -1;
}

function today_minmax($data, $start): array {
    $tiMax = -1; $tiMin = -1;
    $today = isset($data['time'][$start]) ? substr((string)$data['time'][$start], 0, 10) : '';
    foreach (($data['time'] ?? []) as $i => $t) {
        if ($i < $start) continue;
        if (substr((string)$t, 0, 10) !== $today) break;
        $v = $data['weighted']['temperature_2m'][$i] ?? null;
        if ($v === null || $v === '') continue;
        if ($tiMax < 0 || $v > $data['weighted']['temperature_2m'][$tiMax]) $tiMax = $i;
        if ($tiMin < 0 || $v < $data['weighted']['temperature_2m'][$tiMin]) $tiMin = $i;
    }
    return [$tiMax, $tiMin];
}

function wet_str($data, $i): string {
    $pr = $data['weighted']['precipitation'][$i] ?? null;
    $pp = $data['weighted']['precipitation_probability'][$i] ?? null;
    $s = '';
    if ($pr !== null && $pr !== '') $s .= ' на ' . fmt($pr) . 'мм';
    if ($pp !== null && $pp !== '') $s .= ' с ' . num($pp) . '%';
    return $s;
}
```

- [ ] **Step 4: Запустить тест — зелёный**

Run: `php tests/test_bot.php`
Expected: все `PASS`, `OK`.

- [ ] **Step 5: Commit**

```bash
git add bot.php tests/test_bot.php
git commit -m "feat(bot): search functions for rain/storm/hail and daily minmax"
```

---

### Task 5: Сборка сводки (build_now / build_hours_line / build_16_line / build_summary)

**Files:**
- Modify: `bot.php`
- Modify: `tests/test_bot.php`

**Interfaces:**
- Consumes: все функции Task 2–4.
- Produces:
  - `build_now($data, $idx): string` — две строки, соединённые `\n`.
  - `build_hours_line($data, $start): string` — `По часам — ...`.
  - `build_16_line($data, $from): string` — `На 16 дней — ...`.
  - `build_summary($data, $now = null): string` — полное сообщение.

- [ ] **Step 1: Написать падающий тест** (добавить в `tests/test_bot.php`)

```php
$f = fixture();
eq('now', build_now($f, 11), "Сейчас: ☀️ Ср 5 — +20°, ощущается как +20°\nОсадки: 0мм · Ветер: 3 м/с ЮЗ · Давление: 756 мм рт. ст. · Влажность: 62%");
eq('hours dry', build_hours_line($f, 24), 'По часам — без дождя / макс. +25° в 15:00 / мин. +20° в 00:00');
eq('hours rain', build_hours_line($f, 11), 'По часам — дождь в 14:00 / макс. +24° в 15:00 / мин. +17° в 23:00');
eq('16 line', build_16_line($f, 11), 'На 16 дней — дождь Чт 6 в 14:00 на 0.1мм с 17% по 2 моделям / гроза Чт 6 в 10:00 на 1.1мм с 11% по UKMO Global / град Чт 6 в 14:00 на 1.3мм с 46% по DWD ICON');
eq('summary', build_summary($f, '2026-08-05T11:00'), "Сейчас: ☀️ Ср 5 — +20°, ощущается как +20°\nОсадки: 0мм · Ветер: 3 м/с ЮЗ · Давление: 756 мм рт. ст. · Влажность: 62%\nПо часам — дождь в 14:00 / макс. +24° в 15:00 / мин. +17° в 23:00\nНа 16 дней — дождь Чт 6 в 14:00 на 0.1мм с 17% по 2 моделям / гроза Чт 6 в 10:00 на 1.1мм с 11% по UKMO Global / град Чт 6 в 14:00 на 1.3мм с 46% по DWD ICON");

if ($fail) { fwrite(STDERR, "$fail failures\n"); exit(1); }
echo "OK\n";
```

Примечание: в фикстуре день 2 (2026-08-06) — четверг, поэтому `Чт 6`. Проверить `date('w')` для 2026-08-06 локально: должно быть четверг. Если машина/локаль даёт иное — исправить ожидания теста на фактический день недели, но не менять логику.

- [ ] **Step 2: Запустить тест — падает**

Run: `php tests/test_bot.php`
Expected: `FAIL` на `build_now` и т.д. (функции не определены).

- [ ] **Step 3: Реализовать** (добавить в `bot.php`)

```php
function build_now($data, $idx): string {
    $w = $data['weighted'];
    $wc = $w['weather_code'][$idx] ?? null;
    [, $icon] = wcode($wc);
    $day = day_short($data['time'][$idx] ?? '');
    $t = temp($w['temperature_2m'][$idx] ?? null);
    $feels = temp($w['apparent_temperature'][$idx] ?? null);
    $os = fmt($w['precipitation'][$idx] ?? null) . 'мм';
    $wind = num($w['wind_speed_10m'][$idx] ?? null) . ' м/с ' . rumb_short($w['wind_direction_10m'][$idx] ?? null);
    $pres = num($w['pressure_msl'][$idx] ?? null) . ' мм рт. ст.';
    $hum = num($w['relative_humidity_2m'][$idx] ?? null) . '%';
    return "Сейчас: {$icon} {$day} — {$t}, ощущается как {$feels}\n"
        . "Осадки: {$os} · Ветер: {$wind} · Давление: {$pres} · Влажность: {$hum}";
}

function build_hours_line($data, $start): string {
    $parts = [];
    $rh = rain_hour_today($data, $start);
    $parts[] = $rh >= 0 ? 'дождь в ' . substr((string)$data['time'][$rh], 11, 5) : 'без дождя';
    [$tiMax, $tiMin] = today_minmax($data, $start);
    $mn = [];
    if ($tiMax >= 0) $mn[] = 'макс. ' . temp($data['weighted']['temperature_2m'][$tiMax]) . ' в ' . substr((string)$data['time'][$tiMax], 11, 5);
    if ($tiMin >= 0) $mn[] = 'мин. ' . temp($data['weighted']['temperature_2m'][$tiMin]) . ' в ' . substr((string)$data['time'][$tiMin], 11, 5);
    if (count($mn)) $parts[] = implode(' / ', $mn);
    return 'По часам — ' . implode(' / ', $parts);
}

function build_16_line($data, $from): string {
    $codes = [51,53,55,56,57,61,63,65,66,67,80,81,82];
    $parts = [];
    $ri = find_rain_by_consensus($data, $from);
    if ($ri >= 0) {
        $n = source_count($data, $ri, $codes);
        $parts[] = 'дождь ' . tstr($data['time'][$ri]) . wet_str($data, $ri)
            . ' по ' . ($n === 1 ? '1 модели' : $n . ' моделям');
    }
    $ti = find_nearest_source($data, $from, [95, 96, 99]);
    if ($ti >= 0) {
        $parts[] = 'гроза ' . tstr($data['time'][$ti]) . wet_str($data, $ti)
            . ' по ' . implode(' и ', source_names($data, $ti, [95, 96, 99]));
    }
    $hi = find_nearest_source($data, $from, [96, 99]);
    if ($hi >= 0) {
        $parts[] = 'град ' . tstr($data['time'][$hi]) . wet_str($data, $hi)
            . ' по ' . implode(' и ', source_names($data, $hi, [96, 99]));
    }
    return 'На 16 дней — ' . implode(' / ', $parts);
}

function build_summary($data, $now = null): string {
    $idx = cur_idx($data, $now);
    return build_now($data, $idx) . "\n"
        . build_hours_line($data, $idx) . "\n"
        . build_16_line($data, $idx);
}
```

- [ ] **Step 4: Запустить тест — зелёный**

Run: `php tests/test_bot.php`
Expected: все `PASS`, `OK`.

- [ ] **Step 5: Commit**

```bash
git add bot.php tests/test_bot.php
git commit -m "feat(bot): build weather summary lines"
```

---

### Task 6: Telegram-интеграция (API, webhook setup, обработка update)

**Files:**
- Modify: `bot.php`
- Modify: `tests/test_bot.php`

**Interfaces:**
- Consumes: `build_summary` (Task 5).
- Produces:
  - `telegram_api($token, $method, $params): ?array` — POST на `https://api.telegram.org/bot{$token}/{$method}` через `file_get_contents` + stream context (Content-Type: application/json, timeout 15, ignore_errors); null при сетевой ошибке.
  - `send_message($token, $chatId, $text): bool`.
  - `set_webhook($token, $url): bool`.
  - `process_update($update, $data = null): array` — возвращает `['chat_id'=>.., 'text'=>..]` для ответа, либо `['ignore'=>true]`. Если `$data` передан — использует его (для тестов), иначе `fetch_payload(SITE_URL)`.
  - `main(): void` — веб-вход: `?setup` → регистрация вебхука; иначе чтение `php://input`, `process_update`, `send_message`.
  - В конце файла: `if (PHP_SAPI !== 'cli') { main(); }`.

- [ ] **Step 1: Написать падающий тест** (добавить в `tests/test_bot.php`)

```php
$f = fixture();
$upd = ['message' => ['chat' => ['id' => 123], 'text' => '/погода']];
$r = process_update($upd, $f);
eq('process update text', $r['text'], build_summary($f, '2026-08-05T11:00'));
eq('process update chat', $r['chat_id'], 123);

$rStart = process_update(['message' => ['chat' => ['id' => 1], 'text' => '/start']], $f);
eq('process start', $rStart['text'], 'Привет! Отправьте /погода или /weather, чтобы получить сводку погоды по Ярославлю.');

$rIgnore = process_update([], $f);
eq('process ignore', $rIgnore, ['ignore' => true]);

if ($fail) { fwrite(STDERR, "$fail failures\n"); exit(1); }
echo "OK\n";
```

- [ ] **Step 2: Запустить тест — падает**

Run: `php tests/test_bot.php`
Expected: `FAIL` на `process_update` (функция не определена).

- [ ] **Step 3: Реализовать** (добавить в `bot.php` после `build_summary`)

```php
function telegram_api($token, $method, $params): ?array {
    $url = "https://api.telegram.org/bot{$token}/{$method}";
    $ctx = stream_context_create(['http' => [
        'method' => 'POST',
        'header' => "Content-Type: application/json\r\n",
        'content' => json_encode($params, JSON_UNESCAPED_UNICODE),
        'ignore_errors' => true,
        'timeout' => 15,
    ]]);
    $body = @file_get_contents($url, false, $ctx);
    if ($body === false) return null;
    $r = json_decode($body, true);
    return is_array($r) ? $r : null;
}

function send_message($token, $chatId, $text): bool {
    $r = telegram_api($token, 'sendMessage', ['chat_id' => $chatId, 'text' => $text]);
    return is_array($r) && !empty($r['ok']);
}

function set_webhook($token, $url): bool {
    $r = telegram_api($token, 'setWebhook', ['url' => $url]);
    return is_array($r) && !empty($r['ok']);
}

function process_update($update, $data = null): array {
    $msg = $update['message'] ?? null;
    if (!$msg) return ['ignore' => true];
    $chatId = $msg['chat']['id'] ?? null;
    if ($chatId === null) return ['ignore' => true];
    $text = trim((string)($msg['text'] ?? ''));
    if ($text === '') return ['ignore' => true];
    if (strpos($text, '/start') === 0) {
        return ['chat_id' => $chatId, 'text' => 'Привет! Отправьте /погода или /weather, чтобы получить сводку погоды по Ярославлю.'];
    }
    if ($data === null) $data = fetch_payload(SITE_URL);
    if (!$data) return ['chat_id' => $chatId, 'text' => 'Данные недоступны, попробуйте позже.'];
    return ['chat_id' => $chatId, 'text' => build_summary($data)];
}

function main(): void {
    $token = BOT_TOKEN;
    if (isset($_GET['setup'])) {
        if ($_GET['setup'] === BOT_TOKEN) {
            $host = $_SERVER['HTTP_HOST'] ?? '';
            $path = parse_url($_SERVER['REQUEST_URI'] ?? '', PHP_URL_PATH);
            $scheme = isset($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off' ? 'https' : 'http';
            $webhookUrl = $scheme . '://' . $host . $path;
            echo set_webhook($token, $webhookUrl) ? "webhook set: {$webhookUrl}\n" : "webhook failed\n";
        } else {
            echo "bad setup token\n";
        }
        return;
    }
    $raw = file_get_contents('php://input');
    $update = json_decode((string)$raw, true) ?: [];
    $res = process_update($update);
    if (isset($res['chat_id'], $res['text'])) {
        send_message($token, $res['chat_id'], $res['text']);
    }
}

if (PHP_SAPI !== 'cli') {
    main();
}
```

- [ ] **Step 4: Запустить тест — зелёный**

Run: `php tests/test_bot.php`
Expected: все `PASS`, `OK`.

- [ ] **Step 5: Смоук-тест веб-входа** (встроенный сервер PHP)

Run:
```powershell
Start-Process php -ArgumentList "-S","127.0.0.1:8090" -WorkingDirectory "F:\Meteo"
Start-Sleep 2
Invoke-RestMethod -Uri "http://127.0.0.1:8090/bot.php?setup=bad" -Method Post | Out-String
```
Expected: `bad setup token` (BOT_TOKEN пустой, «bad» не совпадает). Остановить сервер: `Stop-Process -Name php -ErrorAction SilentlyContinue`.

- [ ] **Step 6: Проверить синтаксис**

Run: `php -l bot.php`
Expected: `No syntax errors detected in bot.php`.

- [ ] **Step 7: Commit**

```bash
git add bot.php tests/test_bot.php
git commit -m "feat(bot): telegram API integration and webhook entry"
```

---

### Task 7: README-bot.md — инструкция по установке

**Files:**
- Create: `README-bot.md`

**Interfaces:**
- Consumes: ничего (документация).

- [ ] **Step 1: Создать README-bot.md**

```markdown
# Telegram-бот MeteoMap

Бот отвечает сводкой погоды (Ярославль) по команде `/погода` или `/weather` (или по любому тексту) в личных чатах и группах.

## Установка

1. В Telegram: откройте @BotFather, создайте бота командой `/newbot`, получите токен вида `123456789:ABC...`.
2. Откройте `bot.php` и впишите токен в константу `BOT_TOKEN`.
3. Загрузите `bot.php` по FTP на свой сайт (Hostland), например в корень `https://ваш-сайт/`.
4. Откройте в браузере:
   `https://ваш-сайт/bot.php?setup=ВАШ_ТОКЕН`
   В ответ должно появиться `webhook set: https://ваш-сайт/bot.php`.
5. Напишите боту `/start` в Telegram — должен ответить приветствием, затем `/погода`.

## Как это работает

- Telegram сам присылает update на `bot.php` (вебхук) — долгий процесс не нужен.
- Бот скачивает `index.html` с GitHub Pages (`https://samlab.github.io/MeteoMap/index.html`), который обновляется каждый час, и выводит сводку.
- Данные те же, что на сайте: максимум/минимум по часам, ближайший дождь (по консенсусу), гроза и град (по источникам-моделям).

## Команды

- `/погода`, `/weather` — сводка погоды.
- `/start` — приветствие.
- Любой другой текст — тоже сводка.

## Разработка

Локальные тесты (нужен PHP): `php tests/test_bot.php`
```

- [ ] **Step 2: Проверить содержимое** — пути, токен и команды совпадают с реализацией.

- [ ] **Step 3: Commit**

```bash
git add README-bot.md
git commit -m "docs: bot setup instructions"
```

---

### Task 8: Сверка с реальными данными и финальная проверка

**Files:**
- Modify: `tests/test_bot.php` (только если смоук выявит расхождение)
- (Возможная правка `bot.php`)

**Interfaces:**
- Consumes: всё выше.

- [ ] **Step 1: Сгенерировать свежий index.html**

Run: `F:\Meteo\.venv\Scripts\python.exe F:\Meteo\meteo.py`
Expected: `[ok] index.html written; models=13 hours=384`

- [ ] **Step 2: Проверить, что bot.php парсит реальный файл**

Run (в PowerShell, `F:\Meteo`):
```powershell
$html = Get-Content index.html -Raw -Encoding UTF8
$php = @'
<?php
require __DIR__ . '/bot.php';
$html = file_get_contents('php://stdin');
$d = parse_payload($html);
echo $d ? 'parsed ok, hours=' . count($d['time']) . "\n" : "PARSE FAIL\n";
echo build_summary($d) . "\n";
'@
Set-Content -Path "$env:TEMP\bot_smoke.php" -Value $php -Encoding UTF8
$html | php "$env:TEMP\bot_smoke.php"
```
Expected: `parsed ok, hours=384` и три строки сводки, совпадающие по смыслу с заголовками на сайте (дождь/гроза/град, макс/мин). Внимание: PHP-скрипт и индекс сгенерированы в разное время суток — значения «время» могут отличаться от ранее проверенных проб, это нормально.

- [ ] **Step 3: Запустить полный набор тестов**

Run: `php tests/test_bot.php`
Expected: все `PASS`, `OK`.

- [ ] **Step 4: Запустить регрессию pytest (не трогаем Python-код, проверяем что ничего не сломано)**

Run: `F:\Meteo\.venv\Scripts\python.exe -m pytest tests -m "not integration" -q`
Expected: `58 passed, 2 deselected`.

- [ ] **Step 5: Commit**

```bash
git add bot.php tests/test_bot.php
git commit -m "test(bot): verify against live index.html payload"
```
(если правок не было — commit не нужен)

---

## Self-Review

**Покрытие спецификации:**
- Формат ответа (3–4 строки) — Task 5 (`build_now`, `build_hours_line`, `build_16_line`, `build_summary`).
- «Сейчас» с осадками/ветром/давлением/влажностью — `build_now` (Task 5).
- «По часам» с дождём/без дождя и макс/мин — `build_hours_line`.
- «На 16 дней» с дождём (консенсус, число моделей), грозой/градом (имена моделей) — `build_16_line`.
- Вебхук + setup через `?setup` — Task 6 (`set_webhook`, `main`).
- Команды `/погода`, `/weather`, любой текст, `/start` — `process_update` (Task 6).
- Работа в группах — Bot API отвечает на любой chat_id, ограничений нет.
- Безопасность: `BOT_TOKEN` пустой в репо, заполняется вручную; `?setup` проверяет совпадение токена — Task 6.
- README — Task 7.

**Плейсхолдеры:** нет; весь код приведён в задачах.

**Согласованность типов:** имена функций и сигнатуры согласованы между задачами (см. блоки Interfaces). `fixture()` определена в Task 3 и используется Tasks 4–6.
