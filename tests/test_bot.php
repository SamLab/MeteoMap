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

if ($fail) { fwrite(STDERR, "$fail failures\n"); exit(1); }
echo "OK\n";
