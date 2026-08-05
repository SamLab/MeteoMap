<?php

date_default_timezone_set('Europe/Moscow');
@ini_set('memory_limit', '128M');

define('SITE_URL', 'https://samlab.github.io/MeteoMap/index.html');
define('BOT_TOKEN', '');

$GLOBALS['DOW_SHORT'] = array('Вс', 'Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб');
$GLOBALS['COMPASS'] = array('С', 'СВ', 'В', 'ЮВ', 'Ю', 'ЮЗ', 'З', 'СЗ');

function fmt($v) {
    if ($v === null || $v === '') return '—';
    $s = number_format((float)$v, 1, '.', '');
    $s = rtrim($s, '0');
    $s = rtrim($s, '.');
    return $s === '' ? '0' : $s;
}

function num($v) {
    if ($v === null || $v === '') return '—';
    return (string)round((float)$v);
}

function temp($v) {
    if ($v === null || $v === '') return '—';
    $r = (int)round((float)$v);
    return ($r > 0 ? '+' : '') . $r . '°';
}

$GLOBALS['WCODE'] = array(
    0 => array('Ясно', '☀️'), 1 => array('В основном ясно', '🌤️'), 2 => array('Переменная облачность', '⛅'), 3 => array('Пасмурно', '☁️'),
    45 => array('Туман', '🌫️'), 48 => array('Изморозь', '🌫️'),
    51 => array('Небольшая морось', '🌦️'), 53 => array('Морось', '🌦️'), 55 => array('Сильная морось', '🌧️'),
    56 => array('Ледяная морось', '🌧️'), 57 => array('Ледяная морось', '🌧️'),
    61 => array('Небольшой дождь', '🌦️'), 63 => array('Дождь', '🌧️'), 65 => array('Сильный дождь', '🌧️'),
    66 => array('Ледяной дождь', '🌧️'), 67 => array('Ледяной дождь', '🌧️'),
    71 => array('Небольшой снег', '🌨️'), 73 => array('Снег', '❄️'), 75 => array('Сильный снег', '❄️'), 77 => array('Снежные зерна', '❄️'),
    80 => array('Небольшой ливень', '🌧️'), 81 => array('Ливень', '🌧️'), 82 => array('Сильный ливень', '⛈️'),
    85 => array('Снегопад', '🌨️'), 86 => array('Снегопад', '🌨️'),
    95 => array('Гроза', '⚡'), 96 => array('Гроза с градом', '⚡'), 99 => array('Гроза с градом', '⚡'),
);

function wcode($c) {
    return isset($GLOBALS['WCODE'][$c]) ? $GLOBALS['WCODE'][$c] : array('—', '');
}

function rumb_short($deg) {
    if ($deg === null || $deg === '') return '—';
    return $GLOBALS['COMPASS'][((int)round((float)$deg / 45)) % 8];
}

function day_short($iso) {
    $ts = strtotime((string)$iso);
    if ($ts === false) return '—';
    return $GLOBALS['DOW_SHORT'][(int)date('w', $ts)] . ' ' . date('j', $ts);
}

function tstr($iso) {
    $ts = strtotime((string)$iso);
    if ($ts === false) return '—';
    return $GLOBALS['DOW_SHORT'][(int)date('w', $ts)] . ' ' . date('j', $ts) . ' в ' . date('H:i', $ts);
}

function http_request($url, $json = null) {
    if (function_exists('curl_init')) {
        $attempts = array(true, false);
        $last = 'curl unavailable';
        foreach ($attempts as $verify) {
            $ch = curl_init($url);
            curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
            curl_setopt($ch, CURLOPT_TIMEOUT, 12);
            curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, $verify);
            curl_setopt($ch, CURLOPT_SSL_VERIFYHOST, $verify ? 2 : 0);
            if ($json !== null) {
                curl_setopt($ch, CURLOPT_POST, true);
                curl_setopt($ch, CURLOPT_HTTPHEADER, array('Content-Type: application/json'));
                curl_setopt($ch, CURLOPT_POSTFIELDS, $json);
            }
            $body = curl_exec($ch);
            $err = curl_error($ch);
            $code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
            curl_close($ch);
            if ($body !== false) return $body;
            $last = "curl error (verify=" . ($verify ? 'on' : 'off') . "): {$err} (http {$code})";
        }
        return $last;
    }
    if (ini_get('allow_url_fopen')) {
        $opts = array('timeout' => 12, 'ignore_errors' => true);
        if ($json !== null) {
            $opts['method'] = 'POST';
            $opts['header'] = "Content-Type: application/json\r\n";
            $opts['content'] = $json;
        }
        $ctx = stream_context_create(array('http' => $opts));
        $body = @file_get_contents($url, false, $ctx);
        if ($body !== false) return $body;
        return 'file_get_contents failed';
    }
    return 'no curl and allow_url_fopen disabled';
}

function parse_payload($html) {
    $needle = '<script id="data" type="application/json">';
    $start = strpos($html, $needle);
    if ($start === false) return null;
    $start += strlen($needle);
    $end = strpos($html, '</script>', $start);
    if ($end === false) return null;
    $json = substr($html, $start, $end - $start);
    $data = json_decode($json, true);
    return is_array($data) ? $data : null;
}

function fetch_payload($url) {
    $body = http_request($url);
    if (!is_string($body)) return null;
    return parse_payload($body);
}

function cur_idx($data, $now = null) {
    if ($now === null) {
        $dt = new DateTime('now', new DateTimeZone('Europe/Moscow'));
        $now = $dt->format('Y-m-d\TH:00');
    }
    $times = isset($data['time']) ? $data['time'] : array();
    foreach ($times as $i => $t) {
        if (strcmp((string)$t, (string)$now) >= 0) return $i;
    }
    return 0;
}

function source_list($data, $i, $list) {
    $out = array();
    $codes = isset($data['model_codes']) ? $data['model_codes'] : array();
    foreach ($codes as $c) {
        $v = isset($data['models'][$c]['weather_code'][$i]) ? $data['models'][$c]['weather_code'][$i] : null;
        if (in_array($v, $list, true)) $out[] = $c;
    }
    return $out;
}

function source_count($data, $i, $list) {
    return count(source_list($data, $i, $list));
}

function source_names($data, $i, $list) {
    $res = array();
    foreach (source_list($data, $i, $list) as $c) {
        $res[] = isset($data['model_names'][$c]) ? $data['model_names'][$c] : $c;
    }
    return $res;
}

function find_nearest_source($data, $from, $list) {
    $n = isset($data['time']) ? count($data['time']) : 0;
    for ($i = $from; $i < $n; $i++) {
        if (source_count($data, $i, $list) > 0) return $i;
    }
    return -1;
}

function find_rain_by_consensus($data, $from) {
    $codes = array(51,53,55,56,57,61,63,65,66,67,80,81,82);
    $times = isset($data['time']) ? $data['time'] : array();
    foreach ($times as $i => $t) {
        if ($i < $from) continue;
        $v = isset($data['weighted']['weather_code'][$i]) ? $data['weighted']['weather_code'][$i] : null;
        if (in_array($v, $codes, true)) return $i;
    }
    return -1;
}

function rain_hour_today($data, $start) {
    $codes = array(51,53,55,56,57,61,63,65,66,67,80,81,82);
    $today = isset($data['time'][$start]) ? substr((string)$data['time'][$start], 0, 10) : '';
    $times = isset($data['time']) ? $data['time'] : array();
    foreach ($times as $i => $t) {
        if ($i < $start) continue;
        if (substr((string)$t, 0, 10) !== $today) break;
        $v = isset($data['weighted']['weather_code'][$i]) ? $data['weighted']['weather_code'][$i] : null;
        if (in_array($v, $codes, true)) return $i;
    }
    return -1;
}

function today_minmax($data, $start) {
    $tiMax = -1; $tiMin = -1;
    $today = isset($data['time'][$start]) ? substr((string)$data['time'][$start], 0, 10) : '';
    $times = isset($data['time']) ? $data['time'] : array();
    foreach ($times as $i => $t) {
        if ($i < $start) continue;
        if (substr((string)$t, 0, 10) !== $today) break;
        $v = isset($data['weighted']['temperature_2m'][$i]) ? $data['weighted']['temperature_2m'][$i] : null;
        if ($v === null || $v === '') continue;
        if ($tiMax < 0 || $v > $data['weighted']['temperature_2m'][$tiMax]) $tiMax = $i;
        if ($tiMin < 0 || $v < $data['weighted']['temperature_2m'][$tiMin]) $tiMin = $i;
    }
    return array($tiMax, $tiMin);
}

function wet_str($data, $i) {
    $pr = isset($data['weighted']['precipitation'][$i]) ? $data['weighted']['precipitation'][$i] : null;
    $pp = isset($data['weighted']['precipitation_probability'][$i]) ? $data['weighted']['precipitation_probability'][$i] : null;
    $s = '';
    if ($pr !== null && $pr !== '') $s .= ' на ' . fmt($pr) . 'мм';
    if ($pp !== null && $pp !== '') $s .= ' с ' . num($pp) . '%';
    return $s;
}

function build_now($data, $idx) {
    $w = $data['weighted'];
    $wc = isset($w['weather_code'][$idx]) ? $w['weather_code'][$idx] : null;
    $pair = wcode($wc);
    $icon = $pair[1];
    $day = day_short(isset($data['time'][$idx]) ? $data['time'][$idx] : '');
    $t = temp(isset($w['temperature_2m'][$idx]) ? $w['temperature_2m'][$idx] : null);
    $feels = temp(isset($w['apparent_temperature'][$idx]) ? $w['apparent_temperature'][$idx] : null);
    $os = fmt(isset($w['precipitation'][$idx]) ? $w['precipitation'][$idx] : null) . 'мм';
    $wind = num(isset($w['wind_speed_10m'][$idx]) ? $w['wind_speed_10m'][$idx] : null) . ' м/с ' . rumb_short(isset($w['wind_direction_10m'][$idx]) ? $w['wind_direction_10m'][$idx] : null);
    $pres = num(isset($w['pressure_msl'][$idx]) ? $w['pressure_msl'][$idx] : null) . ' мм рт. ст.';
    $hum = num(isset($w['relative_humidity_2m'][$idx]) ? $w['relative_humidity_2m'][$idx] : null) . '%';
    return "Сейчас: {$icon} {$day} — {$t}, ощущается как {$feels}\n"
        . "Осадки: {$os} · Ветер: {$wind} · Давление: {$pres} · Влажность: {$hum}";
}

function build_hours_line($data, $start) {
    $parts = array();
    $rh = rain_hour_today($data, $start);
    $parts[] = $rh >= 0 ? 'дождь в ' . substr((string)$data['time'][$rh], 11, 5) : 'без дождя';
    $mm = today_minmax($data, $start);
    $tiMax = $mm[0]; $tiMin = $mm[1];
    $mn = array();
    if ($tiMax >= 0) $mn[] = 'макс. ' . temp($data['weighted']['temperature_2m'][$tiMax]) . ' в ' . substr((string)$data['time'][$tiMax], 11, 5);
    if ($tiMin >= 0) $mn[] = 'мин. ' . temp($data['weighted']['temperature_2m'][$tiMin]) . ' в ' . substr((string)$data['time'][$tiMin], 11, 5);
    if (count($mn)) $parts[] = implode(' / ', $mn);
    return 'По часам — ' . implode(' / ', $parts);
}

function build_16_line($data, $from) {
    $codes = array(51,53,55,56,57,61,63,65,66,67,80,81,82);
    $parts = array();
    $ri = find_rain_by_consensus($data, $from);
    if ($ri >= 0) {
        $n = source_count($data, $ri, $codes);
        $parts[] = 'дождь ' . tstr($data['time'][$ri]) . wet_str($data, $ri)
            . ' по ' . ($n === 1 ? '1 модели' : $n . ' моделям');
    }
    $ti = find_nearest_source($data, $from, array(95, 96, 99));
    if ($ti >= 0) {
        $parts[] = 'гроза ' . tstr($data['time'][$ti]) . wet_str($data, $ti)
            . ' по ' . implode(' и ', source_names($data, $ti, array(95, 96, 99)));
    }
    $hi = find_nearest_source($data, $from, array(96, 99));
    if ($hi >= 0) {
        $parts[] = 'град ' . tstr($data['time'][$hi]) . wet_str($data, $hi)
            . ' по ' . implode(' и ', source_names($data, $hi, array(96, 99)));
    }
    return 'На 16 дней — ' . implode(' / ', $parts);
}

function build_summary($data, $now = null) {
    $idx = cur_idx($data, $now);
    return build_now($data, $idx) . "\n"
        . build_hours_line($data, $idx) . "\n"
        . build_16_line($data, $idx);
}

function telegram_api($token, $method, $params) {
    $url = "https://api.telegram.org/bot{$token}/{$method}";
    $body = http_request($url, json_encode($params));
    $r = json_decode($body, true);
    return is_array($r) ? $r : $body;
}

function send_message($token, $chatId, $text) {
    $r = telegram_api($token, 'sendMessage', array('chat_id' => $chatId, 'text' => $text));
    return is_array($r) && !empty($r['ok']);
}

function set_webhook($token, $url) {
    $r = telegram_api($token, 'setWebhook', array('url' => $url));
    return is_array($r) && !empty($r['ok']);
}

function process_update($update, $data = null) {
    $msg = isset($update['message']) ? $update['message'] : null;
    if (!$msg) return array('ignore' => true);
    $chatId = isset($msg['chat']['id']) ? $msg['chat']['id'] : null;
    if ($chatId === null) return array('ignore' => true);
    $text = trim((string)(isset($msg['text']) ? $msg['text'] : ''));
    if ($text === '') return array('ignore' => true);
    if (strpos($text, '/start') === 0) {
        return array('chat_id' => $chatId, 'text' => 'Привет! Отправьте /погода или /weather, чтобы получить сводку погоды по Ярославлю.');
    }
    if ($data === null) $data = fetch_payload(SITE_URL);
    if (!$data) return array('chat_id' => $chatId, 'text' => 'Данные недоступны, попробуйте позже.');
    return array('chat_id' => $chatId, 'text' => build_summary($data));
}

function main() {
    @set_time_limit(60);
    $token = BOT_TOKEN;
    if (isset($_GET['setup'])) {
        if ($_GET['setup'] === BOT_TOKEN) {
            $host = isset($_SERVER['HTTP_HOST']) ? $_SERVER['HTTP_HOST'] : '';
            $path = parse_url(isset($_SERVER['REQUEST_URI']) ? $_SERVER['REQUEST_URI'] : '', PHP_URL_PATH);
            $scheme = isset($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off' ? 'https' : 'http';
            $webhookUrl = $scheme . '://' . $host . $path;
            $res = telegram_api($token, 'setWebhook', array('url' => $webhookUrl));
            if (is_array($res) && !empty($res['ok'])) {
                echo "webhook set: {$webhookUrl}\n";
            } else {
                echo "webhook failed: " . (is_array($res) ? json_encode($res) : $res) . "\n";
            }
        } else {
            echo "bad setup token\n";
        }
        return;
    }
    if (isset($_GET['debug'])) {
        while (ob_get_level()) ob_end_flush();
        echo "php: " . PHP_VERSION . "\n"; flush();
        echo "curl: " . (function_exists('curl_init') ? 'yes' : 'no') . ", openssl: " . (extension_loaded('openssl') ? 'yes' : 'no') . ", allow_url_fopen: " . ini_get('allow_url_fopen') . ", memory_limit: " . ini_get('memory_limit') . "\n"; flush();
        $t0 = microtime(true);
        $body = http_request(SITE_URL);
        echo "site fetch: " . round(microtime(true) - $t0, 1) . "s, len=" . strlen($body) . "\n"; flush();
        $needle = '<script id="data" type="application/json">';
        $p = strpos($body, $needle);
        echo "needle found: " . ($p === false ? 'no' : 'yes') . "\n"; flush();
        if ($p !== false) {
            $start = $p + strlen($needle);
            $end = strpos($body, '</script>', $start);
            $json = substr($body, $start, ($end === false ? 0 : $end - $start));
            echo "json len: " . strlen($json) . "\n"; flush();
            $t1 = microtime(true);
            $d = json_decode($json, true);
            echo "json_decode: " . round(microtime(true) - $t1, 1) . "s, array=" . (is_array($d) ? 'yes' : 'no') . "\n"; flush();
            if (is_array($d)) {
                echo build_summary($d) . "\n"; flush();
            }
        }
        echo "--- telegram getMe ---\n"; flush();
        $t2 = microtime(true);
        $me = telegram_api($token, 'getMe', array());
        echo "getMe: " . round(microtime(true) - $t2, 1) . "s, " . (is_array($me) && !empty($me['ok']) ? 'ok' : (is_array($me) ? json_encode($me) : $me)) . "\n"; flush();
        return;
    }
    $raw = file_get_contents('php://input');
    $update = json_decode((string)$raw, true);
    if (!is_array($update)) $update = array();
    $res = process_update($update);
    if (isset($res['chat_id'], $res['text'])) {
        send_message($token, $res['chat_id'], $res['text']);
    }
}

if (PHP_SAPI !== 'cli') {
    main();
}
