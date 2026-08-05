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
