# Radar: белые точки у населённых пунктов как на rainradar

**Дата:** 2026-08-13
**Статус:** approved

## Проблема

На rainradar.ru у подписей населённых пунктов есть маленькие белые точки,
отмечающие сам населённый пункт. У нас такие точки отсутствуют.

## Исследование

Точки не являются отдельным слоем и не находятся в растровых тайлах
(`/tiles?z=` на z8/z9/z10 вокруг Москвы: white=0, bright=0) и не в
`labels?z=` JSON (там только `[osm_id, name, x, y, class]`). В DOM живого
rainradar точек-элементов нет, но у `.label` есть `::before`-псевдоэлемент —
это и есть белая точка.

Точные правила из `bundle.css?v1740936296` (дословно):

```css
.label::before{
  content:" ";
  position:absolute; left:-3px; bottom:-3px;
  border:1px solid rgb(0,0,0); border-radius:50%;
  width:6px; height:6px; background-color:rgb(238,238,238);
}
.label.l1::before,.label.l2::before{left:-2px;bottom:-2px;width:4px;height:4px}
.label.l3::before,.label.l4::before{left:-1px;bottom:-1px;width:2px;height:2px}
```

- Точка позиционируется относительно `.label`, у которого
  `position:absolute;width:0;height:0` (высота/ширина 0, т.к. span absolute
  вне потока). Координата точки = якорь подписи (`left`/`bottom` из labels
  JSON), точка по центру якоря.
- Стили span: `position:absolute;left:-9px;bottom:5px;white-space:nowrap;
  color:#fff;font-weight:500;text-shadow:...` — текст сдвинут вправо-вверх от
  точки (computed: spanTop=-24.5px для l0, -23px l1, -21.5px l2, -20px l3;
  spanLeft -9px, кроме l3/l4 = -7px).
- font-size: l0 13px, l1 12px (computed, правило отдельно), l2 11px,
  l3/l4 10px.
- Точка имеет чёрную обводку `border:1px solid #000`, круг
  `border-radius:50%`, заливка `#eee` (`rgb(238,238,238)`, почти белая).

## Решение

В `radar_template.html` (CSS, строки 37–42) изменить стили `.label` на
точную копию rainradar: добавить `::before`-точку по классам (l0 6px,
l1/l2 4px, l3/l4 2px) и сделать span absolute-позиционирование
(`left:-9px;bottom:5px`, для l3/l4 `left:-7px`), чтобы текст лежал там же,
где на rainradar, а точка совпадала с якорем населённого пункта.

Способ реализации — CSS-only, без изменений JS LabelsLayer: JS уже ставит
`d.style.left`/`d.style.bottom` из labels JSON и класс `lN` на `.label`.

Конечный CSS-блок:

```css
.label{position:absolute;pointer-events:none}
.label::before{content:" ";position:absolute;left:-3px;bottom:-3px;border:1px solid #000;border-radius:50%;width:6px;height:6px;background-color:#eee}
.label>span{position:absolute;left:-9px;bottom:5px;white-space:nowrap;color:#fff;font-weight:500;text-shadow:-1px 0 1px rgba(0,0,0,.7),1px 0 1px rgba(0,0,0,.7),0 1px 1px rgba(0,0,0,.7),0 -1px 1px rgba(0,0,0,.7)}
.label.l0>span{font-size:13px}
.label.l1>span{font-size:12px}
.label.l2>span{font-size:11px}
.label.l3>span,.label.l4>span{font-size:10px}
.label.l1::before,.label.l2::before{left:-2px;bottom:-2px;width:4px;height:4px}
.label.l3::before,.label.l4::before{left:-1px;bottom:-1px;width:2px;height:2px}
.label.l3 span,.label.l4 span{left:-7px}
```

Примечания:
- `.label{white-space:nowrap;line-height:1}` убираем — nowrap переезжает на
  span (как у rainradar), line-height у нас не был критичен, на rainradar
  span line-height вычисляется (19.5px для l0 = 1.5×13). Оставляем дефолтный
  наследуемый line-height (браузерный ~1.2) — как на rainradar, где явного
  line-height в rules нет. Проверено: computed top с нашим span
  left/bottom даст текст выше точки как на rainradar.
- `pointer-events:none` оставляем (у нас он был, у rainradar может
  отличаться, но это UX-улучшение, не влияет на вид).
- `.label` становится `width:0;height:0` автоматически (span absolute).

### Что не меняем

- JS LabelsLayer, fetch labels, якоря `left/bottom` — не трогаем.
- Подложка `/tiles?z=` (zIndex 998), осадки, молнии, фон `#acacac` — нет.
- `bot.php` — не трогаем.

### Изменения в `tests/test_radar.py`

В `test_radar_has_labels_layer` добавить проверки:
- `.label::before{content:" ";` в tpl и radar;
- размеры точек по классам: `width:6px;height:6px` (базовое),
  `width:4px;height:4px`, `width:2px;height:2px` в tpl и radar;
- обводка/круг/заливка: `border:1px solid #000`, `border-radius:50%`,
  `background-color:#eee`;
- позиционирование span: `position:absolute;left:-9px;bottom:5px`,
  `left:-7px` (для l3/l4) в tpl и radar;
- класс l4: `.label.l4>span` присутствует.

## Критерии приёмки

1. `python -m pytest tests/test_radar.py -q` — 11 passed (обновлённый набор).
2. Полный `python -m pytest -q` — только 2 известных failed Open-Meteo.
3. Headless-проверка: у `.label` в DOM есть `::before`-точка, computed
   размер/фон совпадают с rainradar (6/4/2px, `#eee`, `border-radius:50%`),
   точка по центру якоря подписи; текст подписи сдвинут вправо-вверх.
4. Деплой через GitHub Actions, live-проверка.
