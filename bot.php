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
