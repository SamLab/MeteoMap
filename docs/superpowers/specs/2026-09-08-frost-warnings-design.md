# Design: Frost warnings replace thunderstorm column

Date: 2026-09-08

## Goal

Replace the thunderstorm column (⚡ / CAPE / hail) in the `Предупреждения`
(warnings) block with a frost column, showing the nearest day+hour where at
least one model drops to ≤0 °C, plus a "confirmed" (consensus) row.

## Data

- Per model hourly temperature: `D.models[c].temperature_2m[i]`.
- Consensus temperature: `D.weighted.temperature_2m[i]`.
- Search range: `from .. ts.length` (all future hours, across days), same as
  the existing `findSrc`/`findCon`.

## Column

- Icon: 🥶
- Two rows, built like the gust column (outside the reusable `col(...)`).

### Row 1 — models (class `wr1`)

- Interval: first hour where **≥1 model** has `temperature_2m <= 0`, extended
  continuously while **≥1 model** keeps `<= 0`.
- `по N моделям`: **max** number of models with `<= 0` in **any single hour**
  across the interval.
- Temperature shown: **minimum** temperature among all models across the
  interval.
- Text: `Пт 11 с 05ч до 08ч −2° · по 6 моделям`.

### Row 2 — confirmed (class `wr2`, bold)

- Interval based on **consensus** `D.weighted.temperature_2m <= 0`.
- No `по N моделям` — instead suffix `подтверждено`.
- Temperature: **minimum consensus** value across the interval.
- Text: `Пт 11 с 05ч до 06ч −3° · подтверждено`.

Both rows use the interval label format (with `до` when `end > start`, else
`в 05ч`).

## Empty state

If there is no model interval **and** no consensus interval, show:
`Заморозков в ближайшие дни не ожидается`.

## Removals

Remove all thunderstorm-only helpers no longer used: `S`, `findRisk`,
`modelRisk`, `maxCapeUnblocked`, `cinBlock`, `CIN_BLOCK`, `hasHail`, `hail`,
`capeRow`. Keep `tstr` (still used by gust row).

## Testing

- Rewrite `test_warnings_hail_in_thunderstorm_column` → frost assertions:
  `temperature_2m?.[i]`, `<=0`, `🥶`, `по N моделям`, `подтверждено`,
  and absence of `v===96||v===99`, `риск грозы`.
- Update `test_warnings_empty_messages`: `Гроз и града ...` →
  `Заморозков в ближайшие дни не ожидается`.
