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
