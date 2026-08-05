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

$html = "<html><body><script id=\"data\" type=\"application/json\">{\"time\":[\"2026-08-05T10:00\"],\"a\":1}</script></body></html>";
$p = parse_payload($html);
eq('parse_payload ok', is_array($p) && $p['a'] === 1, true);
eq('parse_payload bad', parse_payload('<html></html>'), null);

$fixture = fixture();
eq('cur_idx exact', cur_idx($fixture, '2026-08-05T10:00'), 10);
eq('cur_idx empty-data', cur_idx(['time' => []], '2026-08-05T10:00'), 0);

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
eq('wet_str zero', wet_str($f, 11), ' на 0мм с 0%');

$f = fixture();
eq('now', build_now($f, 11), "Сейчас: ☀️ Ср 5 — +20°, ощущается как +20°\nОсадки: 0мм · Ветер: 3 м/с ЮЗ · Давление: 756 мм рт. ст. · Влажность: 62%");
eq('hours dry', build_hours_line($f, 24), 'По часам — без дождя / макс. +25° в 15:00 / мин. +20° в 00:00');
eq('hours rain', build_hours_line($f, 11), 'По часам — дождь в 14:00 / макс. +24° в 15:00 / мин. +17° в 23:00');
eq('16 line', build_16_line($f, 11), 'На 16 дней — дождь Ср 5 в 14:00 на 0.1мм с 17% по 2 моделям / гроза Чт 6 в 10:00 на 1.1мм с 11% по UKMO Global / град Чт 6 в 14:00 на 1.3мм с 46% по DWD ICON');
eq('summary', build_summary($f, '2026-08-05T11:00'), "Сейчас: ☀️ Ср 5 — +20°, ощущается как +20°\nОсадки: 0мм · Ветер: 3 м/с ЮЗ · Давление: 756 мм рт. ст. · Влажность: 62%\nПо часам — дождь в 14:00 / макс. +24° в 15:00 / мин. +17° в 23:00\nНа 16 дней — дождь Ср 5 в 14:00 на 0.1мм с 17% по 2 моделям / гроза Чт 6 в 10:00 на 1.1мм с 11% по UKMO Global / град Чт 6 в 14:00 на 1.3мм с 46% по DWD ICON");

if ($fail) { fwrite(STDERR, "$fail failures\n"); exit(1); }
echo "OK\n";
