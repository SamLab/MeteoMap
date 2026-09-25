# Range of Model Counts on Rain Rows Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show the per-hour model-count range (min-max, e.g. `по 2-13 моделям`) on all rain rows instead of only the minimum, collapsing to a single value when min==max.

**Architecture:** Client-side JS only. Replace `rainMinModels` with `rainModelRange(a,b)` returning `{mn,mx}`; track a max alongside `mCnt`/`peakModels` in the hour-loop of the hourly header and both widgets; format via shared helpers `rcLbl(mn,mx)` (full rows) and `rcCnt(mn,mx)` (widgets). Cosmetic change — triggers, thresholds, intervals unchanged.

**Tech Stack:** Vanilla JS in `template.html`, `meteo.html`, `meteow.html`; pytest (`tests/test_radar.py`).

## Global Constraints

- No changes to thresholds/triggers: consensus rows still show the suffix only when min >= 2; model-based rows (`по 1 модели`) when min >= 1.
- Collapse ranges when min == max: `по 2 моделям` (not `по 2-2 моделям`); widget `2м` (not `2-2м`).
- Russian declension: `1 модели` (only exact value 1), otherwise `N моделям` / `N-K моделям`; widget suffix `м` (Cyrillic).
- `meteow.html` stores Cyrillic as `\u` escapes (e.g. `model` is `'\u043C'`); `meteo.html` uses literal Cyrillic. Help text lines 213, 216, 268 updated to mention the range.
- Full test suite command: `$env:PYTHONIOENCODING="utf-8"; .\.venv\Scripts\python.exe -m pytest tests/ -m "not integration" -q` — all must pass.

---

### Task 1: Add `rainModelRange` and `rcLbl` helpers, rewire wr1/wr2 in template.html

**Files:**
- Modify: `F:\Meteo\template.html:842-855` (replace `rainMinModels` definition)
- Modify: `F:\Meteo\template.html:902` (wr1)
- Modify: `F:\Meteo\template.html:917` (wr2)
- Test: `F:\Meteo\tests\test_radar.py`

**Interfaces:**
- Consumes: existing `codes`, `D.models`, `RAIN_CODES` (all in scope in template.html).
- Produces: `rainModelRange(a,b) -> {mn,mx}` and `rcLbl(mn,mx) -> string`, used by Tasks 2-3.

- [ ] **Step 1: Write the failing test**

In `tests/test_radar.py`, update the two assertions that reference the old `rainMinModels`-based strings, and add checks for the new helpers:

```python
def test_warnings_nearest_row_uses_two_model_threshold_and_first_dry_boundary():
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
        tpl = f.read()
    assert "if(sourceCountAt(k,list,precipMin)<2)break;sE=k;" in tpl
    assert "sourceList(s,list,precipMin)" not in tpl
    assert "const R=rainModelRange(s,sE);const sLabel=R.mn>=1?'по '+rcLbl(R.mn,R.mx):''" in tpl
    assert "endLabel(ts[Math.min(sE+1,ts.length-1)]," in tpl
    assert "function rainModelRange(a,b){" in tpl
    assert "function rcLbl(mn,mx){" in tpl
    assert "return {mn,mx};" in tpl
```

And in `test_rain_model_count_uses_min_per_hour` (currently the assertion is on `const n=rainMinModels(c0,c1);rows.push('<div class="wr2">'+cLbl+wv+(n>=2?' · по '+n+' моделям':'')+'</div>');}`), replace that assertion with:

```python
    assert "const R=rainModelRange(c0,c1);rows.push('<div class=\"wr2\">'+cLbl+wv+(R.mn>=2?' · по '+rcLbl(R.mn,R.mx):'')+'</div>');}" in tpl
```

- [ ] **Step 2: Run test to verify it fails**

Run: `$env:PYTHONIOENCODING="utf-8"; .\.venv\Scripts\python.exe -m pytest tests/test_radar.py::test_warnings_nearest_row_uses_two_model_threshold_and_first_dry_boundary tests/test_radar.py::test_rain_model_count_uses_min_per_hour -q`
Expected: FAIL (old `rainMinModels` strings still in template.html).

- [ ] **Step 3: Replace `rainMinModels` with `rainModelRange` + add `rcLbl`**

Replace the `rainMinModels` function body (template.html:842-855):

```js
function rainModelRange(a,b){
  let mn=Infinity,mx=-Infinity;
  for(let j=a;j<=b;j++){
    let n=0;
    for(const c of codes){
      const v=D.models[c]?D.models[c].weather_code?.[j]:undefined;
      const pr=D.models[c]?D.models[c].precipitation?.[j]:undefined;
      const pp=D.models[c]?D.models[c].precipitation_probability?.[j]:undefined;
      if(v!=null?RAIN_CODES.includes(v):(pr!=null&&pr>=0.1||(pp!=null&&pp>33)))n++;
    }
    if(n<mn)mn=n;
    if(n>mx)mx=n;
  }
  return {mn,mx};
}
function rcLbl(mn,mx){
  if(mn<1)return '';
  if(mn===mx)return mn===1?'1 модели':mn+' моделям';
  return mn+'-'+mx+' моделям';
}
```

- [ ] **Step 4: Rewire wr1 (line 902)**

Replace:
```js
const nAll=rainMinModels(s,sE);const sLabel=nAll>=1?'по '+(nAll===1?'1 модели':nAll+' моделям'):'';rows.push('<div class="wr1">'+sLbl+wetSpan(s,sE)+(sLabel?' · '+sLabel:'')+'</div>');}
```
With:
```js
const R=rainModelRange(s,sE);const sLabel=R.mn>=1?'по '+rcLbl(R.mn,R.mx):'';rows.push('<div class="wr1">'+sLbl+wetSpan(s,sE)+(sLabel?' · '+sLabel:'')+'</div>');}
```

- [ ] **Step 5: Rewire wr2 (line 917)**

Replace:
```js
const n=rainMinModels(c0,c1);rows.push('<div class="wr2">'+cLbl+wv+(n>=2?' · по '+n+' моделям':'')+'</div>');}
```
With:
```js
const R=rainModelRange(c0,c1);rows.push('<div class="wr2">'+cLbl+wv+(R.mn>=2?' · по '+rcLbl(R.mn,R.mx):'')+'</div>');}
```

- [ ] **Step 6: Run test to verify it passes**

Run: `$env:PYTHONIOENCODING="utf-8"; .\.venv\Scripts\python.exe -m pytest tests/test_radar.py::test_warnings_nearest_row_uses_two_model_threshold_and_first_dry_boundary tests/test_radar.py::test_rain_model_count_uses_min_per_hour -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add template.html tests/test_radar.py
git commit -m "feat(rain): add rainModelRange+rcLbl, wr1/wr2 show min-max model count"
```

---

### Task 2: Hourly header («По часам») shows min-max range

**Files:**
- Modify: `F:\Meteo\template.html:499-511` (track max in hour loop)
- Modify: `F:\Meteo\template.html:528` (`mcLbl`)
- Test: `F:\Meteo\tests\test_radar.py`

**Interfaces:**
- Consumes: `rcLbl` from Task 1, `inWin`, `codes`, `D.models`, `rainCodes`.
- Produces: nothing new; `mcLbl` in scope for line 529 (unchanged consumer).

- [ ] **Step 1: Write the failing test**

In `test_hourstitle_rain_type_uses_window_start_code` (currently asserts `const mcLbl='по '+(mCnt===1?'1 модели':mCnt+' моделям');` on line 187), replace that assertion with:

```python
    assert "const mcLbl='по '+rcLbl(mCnt,mX);" in tpl
    assert "if(n>mX)mX=n;" in tpl
```

Do the same in `test_hourstitle_rain_interval` (the identical assertion on line ~239).

- [ ] **Step 2: Run test to verify it fails**

Run: `$env:PYTHONIOENCODING="utf-8"; .\.venv\Scripts\python.exe -m pytest tests/test_radar.py::test_hourstitle_rain_type_uses_window_start_code tests/test_radar.py::test_hourstitle_rain_interval -q`
Expected: FAIL (`const mcLbl='по '+rcLbl(mCnt,mX);` absent).

- [ ] **Step 3: Track max in the hour loop**

Replace (template.html:499-511):
```js
    let mCnt=Infinity;
    for(let j=rainHour;j<=jLast;j++){
      if(!inWin(j))continue;
      let n=0;
      for(const c of codes){
        const v=D.models[c]?D.models[c].weather_code?.[j]:undefined;
        const pr=D.models[c]?D.models[c].precipitation?.[j]:undefined;
        const pp=D.models[c]?D.models[c].precipitation_probability?.[j]:undefined;
        if(v!=null?rainCodes.includes(v):(pr!=null&&pr>=0.1||(pp!=null&&pp>33)))n++;
      }
      if(n<mCnt)mCnt=n;
    }
    if(mCnt===Infinity)mCnt=0;
```
With:
```js
    let mCnt=Infinity,mX=-Infinity;
    for(let j=rainHour;j<=jLast;j++){
      if(!inWin(j))continue;
      let n=0;
      for(const c of codes){
        const v=D.models[c]?D.models[c].weather_code?.[j]:undefined;
        const pr=D.models[c]?D.models[c].precipitation?.[j]:undefined;
        const pp=D.models[c]?D.models[c].precipitation_probability?.[j]:undefined;
        if(v!=null?rainCodes.includes(v):(pr!=null&&pr>=0.1||(pp!=null&&pp>33)))n++;
      }
      if(n<mCnt)mCnt=n;
      if(n>mX)mX=n;
    }
    if(mCnt===Infinity)mCnt=0;
    if(mX===-Infinity)mX=0;
```

- [ ] **Step 4: Build `mcLbl` from range**

Replace (line 528):
```js
    const mcLbl='по '+(mCnt===1?'1 модели':mCnt+' моделям');
```
With:
```js
    const mcLbl='по '+rcLbl(mCnt,mX);
```

Line 529 (`parts.push(fromModels?...:txt+(mCnt>=2?' · '+mcLbl:''));`) stays unchanged.

- [ ] **Step 5: Run test to verify it passes**

Run: `$env:PYTHONIOENCODING="utf-8"; .\.venv\Scripts\python.exe -m pytest tests/test_radar.py::test_hourstitle_rain_type_uses_window_start_code tests/test_radar.py::test_hourstitle_rain_interval -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add template.html tests/test_radar.py
git commit -m "feat(rain): hourly header shows min-max model count range"
```

---

### Task 3: Widgets (meteo.html, meteow.html) show min-max range

**Files:**
- Modify: `F:\Meteo\meteo.html:231-236` (peakModels loop), `meteo.html:248-249` (cntStr/conCnt)
- Modify: `F:\Meteo\meteow.html:193-199` (peakModels loop), `meteow.html:210-213` (cntStr/conCnt)
- Test: `F:\Meteo\tests\test_radar.py`

**Interfaces:**
- Consumes: existing `rawData`, `RAIN`, `peakModels`.
- Produces: `rcCnt(mn,mx) -> string` (widget helper), `peakMax`.

- [ ] **Step 1: Write the failing test**

In `test_rain_model_count_uses_min_per_hour`, after the existing widget loop assertions (`assert "if(n<peakModels)peakModels=n;" in w, fname`, etc.), add:

```python
        assert "if(n>peakMax)peakMax=n;" in w, fname
        assert "function rcCnt(mn,mx){return mn===mx?mn+'м':mn+'-'+mx+'м';}" in w, fname
        assert "cntStr=peakModels>=1?(' '+rcCnt(peakModels,peakMax)):''" in w, fname
        assert "conCnt=peakModels>=2?(' '+rcCnt(peakModels,peakMax)):''" in w, fname
```

Note: `meteow.html` stores the Cyrillic suffix as `'\u043C'`; the assertion string `'м'` must match after the test reads the file. Since the test reads raw text, use the literal that appears in each file — for `meteow.html` assert `rcCnt(mn,mx){return mn===mx?mn+'\u043C':mn+'-'+mx+'\u043C';}` instead. Simplest: assert on the ASCII part only:

```python
        assert "if(n>peakMax)peakMax=n;" in w, fname
        assert "function rcCnt(mn,mx)" in w, fname
        assert "rcCnt(peakModels,peakMax)" in w, fname
        assert "mn===mx?mn+'" in w, fname
```

Add separately, after the loop:

```python
    with open(os.path.join(HERE, "meteo.html"), encoding="utf-8") as f:
        m = f.read()
    assert "function rcCnt(mn,mx){return mn===mx?mn+'м':mn+'-'+mx+'м';}" in m
```

- [ ] **Step 2: Run test to verify it fails**

Run: `$env:PYTHONIOENCODING="utf-8"; .\.venv\Scripts\python.exe -m pytest tests/test_radar.py::test_rain_model_count_uses_min_per_hour -q`
Expected: FAIL.

- [ ] **Step 3: meteo.html — track peakMax and add rcCnt**

Replace (meteo.html:231-236):
```js
  var peakModels=Infinity;
  for(var j=rainHour;j<=jLast;j++){var n=0;
    for(var c in rawData){var m=rawData[c];if(!m)continue;var code=m.weather_code?Math.round(m.weather_code[j]):0;var pr=m.precipitation?m.precipitation[j]:null;var pp=m.precipitation_probability?m.precipitation_probability[j]:null;if(code?RAIN.indexOf(code)>=0:(pr!=null&&pr>=0.1||(pp!=null&&pp>33)))n++;}
    if(n<peakModels)peakModels=n;
  }
  if(peakModels===Infinity)peakModels=0;
```
With:
```js
  var peakModels=Infinity,peakMax=-Infinity;
  for(var j=rainHour;j<=jLast;j++){var n=0;
    for(var c in rawData){var m=rawData[c];if(!m)continue;var code=m.weather_code?Math.round(m.weather_code[j]):0;var pr=m.precipitation?m.precipitation[j]:null;var pp=m.precipitation_probability?m.precipitation_probability[j]:null;if(code?RAIN.indexOf(code)>=0:(pr!=null&&pr>=0.1||(pp!=null&&pp>33)))n++;}
    if(n<peakModels)peakModels=n;
    if(n>peakMax)peakMax=n;
  }
  if(peakModels===Infinity)peakModels=0;
  if(peakMax===-Infinity)peakMax=0;
```

Add `rcCnt` just before `function buildSummary(times, data, rawData, idx)` (meteo.html:202):
```js
function rcCnt(mn,mx){return mn===mx?mn+'м':mn+'-'+mx+'м';}
```

- [ ] **Step 4: meteo.html — use rcCnt in cntStr/conCnt**

Replace (meteo.html:248-249):
```js
  var cntStr=peakModels>=1?(' '+peakModels+'м'):'';
  var conCnt=peakModels>=2?(' '+peakModels+'м'):'';
```
With:
```js
  var cntStr=peakModels>=1?(' '+rcCnt(peakModels,peakMax)):'';
  var conCnt=peakModels>=2?(' '+rcCnt(peakModels,peakMax)):'';
```

- [ ] **Step 5: meteow.html — same, with \u escapes**

Replace (meteow.html:193-198):
```js
  var peakModels=Infinity;
  for(var j=rainHour;j<=jLast;j++){var n=0;
    for(var c in rawData){var m=rawData[c];if(!m)continue;var code=m.weather_code?Math.round(m.weather_code[j]):0;var pr=m.precipitation?m.precipitation[j]:null;var pp=m.precipitation_probability?m.precipitation_probability[j]:null;if(code?RAIN.indexOf(code)>=0:(pr!=null&&pr>=0.1||(pp!=null&&pp>33)))n++;}
    if(n<peakModels)peakModels=n;
  }
  if(peakModels===Infinity)peakModels=0;
```
With:
```js
  var peakModels=Infinity,peakMax=-Infinity;
  for(var j=rainHour;j<=jLast;j++){var n=0;
    for(var c in rawData){var m=rawData[c];if(!m)continue;var code=m.weather_code?Math.round(m.weather_code[j]):0;var pr=m.precipitation?m.precipitation[j]:null;var pp=m.precipitation_probability?m.precipitation_probability[j]:null;if(code?RAIN.indexOf(code)>=0:(pr!=null&&pr>=0.1||(pp!=null&&pp>33)))n++;}
    if(n<peakModels)peakModels=n;
    if(n>peakMax)peakMax=n;
  }
  if(peakModels===Infinity)peakModels=0;
  if(peakMax===-Infinity)peakMax=0;
```

Add `rcCnt` just before `function buildSummary(times, data, rawData, idx)` (meteow.html:202):
```js
function rcCnt(mn,mx){return mn===mx?mn+'\u043C':mn+'-'+mx+'\u043C';}
```

Replace (meteow.html:210-211):
```js
  var cntStr=peakModels>=1?(' '+peakModels+'\u043C'):'';
  var conCnt=peakModels>=2?(' '+peakModels+'\u043C'):'';
```
With:
```js
  var cntStr=peakModels>=1?(' '+rcCnt(peakModels,peakMax)):'';
  var conCnt=peakModels>=2?(' '+rcCnt(peakModels,peakMax)):'';
```

- [ ] **Step 6: Run test to verify it passes**

Run: `$env:PYTHONIOENCODING="utf-8"; .\.venv\Scripts\python.exe -m pytest tests/test_radar.py::test_rain_model_count_uses_min_per_hour -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add meteo.html meteow.html tests/test_radar.py
git commit -m "feat(rain): widgets show min-max model count range"
```

---

### Task 4: Update help texts and run full suite

**Files:**
- Modify: `F:\Meteo\template.html:213`, `template.html:216`, `template.html:268`
- Test: full `tests/`

**Interfaces:**
- Consumes: nothing new.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_radar.py`:

```python
def test_help_texts_mention_model_range():
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
        tpl = f.read()
    assert "«по N-K моделям»" in tpl
    assert "N-K моделям" in tpl or "мин-макс" in tpl
```

- [ ] **Step 2: Run test to verify it fails**

Run: `$env:PYTHONIOENCODING="utf-8"; .\.venv\Scripts\python.exe -m pytest tests/test_radar.py::test_help_texts_mention_model_range -q`
Expected: FAIL.

- [ ] **Step 3: Update help text line 213 (warnings)**

Current text ends: `«по N моделям» — наименьшее число моделей с дождём в каком-то часу интервала (модель даёт дождь, если дождевой код, осадки ≥ 0.1 мм или вероятность &gt; 33%; при 0 не показывается). На подтверждённых (консенсусных) строках «по N моделям» показывается только при N ≥ 2 — консенсус не может исходить от одной модели.`

Replace `«по N моделям» — наименьшее число моделей` with `«по N-K моделям» — диапазон (минимум-максимум по часам) числа моделей` and the consensus clause with `На подтверждённых (консенсусных) строках диапазон «по N-K моделям» показывается только при N ≥ 2 — консенсус не может исходить от одной модели.`

- [ ] **Step 4: Update help text line 216 (По часам)**

Current: `…по ≥ 2 моделям («Подтвержденного дождя нет, но по N моделям вероятны Осадки …»).` — change `по N моделям` to `по N-K моделям` and add `(диапазон числа моделей по часам интервала)`.

- [ ] **Step 5: Update help text line 268 (widgets)**

Current: `«9м» — наименьшее число моделей с дождём в каком-то часу интервала (при 0 не показывается; на консенсус-строках — только при N ≥ 2, консенсус не может быть от одной модели).` — replace with `«2-13м» — диапазон числа моделей с дождём по часам интервала (при минимуме 0 не показывается; на консенсус-строках — только при минимуме ≥ 2, консенсус не может быть от одной модели).`

- [ ] **Step 6: Run test to verify it passes**

Run: `$env:PYTHONIOENCODING="utf-8"; .\.venv\Scripts\python.exe -m pytest tests/test_radar.py::test_help_texts_mention_model_range -q`
Expected: PASS.

- [ ] **Step 7: Run full suite**

Run: `$env:PYTHONIOENCODING="utf-8"; .\.venv\Scripts\python.exe -m pytest tests/ -m "not integration" -q`
Expected: all pass (232 + new tests).

- [ ] **Step 8: Commit**

```bash
git add template.html tests/test_radar.py
git commit -m "docs(help): describe min-max model count range"
```

---

## Self-Review

- **Spec coverage:** Task 1 covers wr1/wr2 + helpers; Task 2 covers hourly header; Task 3 covers both widgets incl. collapse (via `rcCnt`/`rcLbl`) and `Вероятны Осадки` (cntStr path); Task 4 covers help texts. Collapse-when-equal and `по 1 модели` declension handled inside `rcLbl`/`rcCnt`. Thresholds untouched (R.mn>=2 for consensus, R.mn>=1 for model-based). ✓
- **Placeholder scan:** No TBD/TODO; every step has concrete code. ✓
- **Type consistency:** `rainModelRange` returns `{mn,mx}` everywhere; `rcLbl(mn,mx)`, `rcCnt(mn,mx)` used consistently; `mX` (hourly header) and `peakMax` (widgets) distinct names. ✓