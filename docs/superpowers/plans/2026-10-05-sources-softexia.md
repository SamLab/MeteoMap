# Second Feed Source (softexia.com) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add softexia.com as a second RSS source beside kaldata, so the bot sees ~71 feed entries instead of 50, without changing a single kaldata decision.

**Architecture:** One shared source layer (`sources.py`) owns the registry, fetching and the state key; each source module (`kaldata.py`, `softexia.py`) carries a four-key PROFILE describing how its titles are read (prepare / pick / multi / channel). `run.py` polls every configured source in turn, counts per source, claims slugs across sources, and bounds the whole run by a time budget. Spec: `F:\Meteo\docs\superpowers\specs\2026-10-05-sources-softexia-design.md`.

**Tech Stack:** Python 3 stdlib only (re, time, json, urllib, xml.etree). `pytest` for local dev only.

**Local test interpreter:** `F:\Meteo\.venv\Scripts\python.exe`. The system `python` on this machine has no `pytest`. Run every command below **from the bot directory** `F:\-SAM-\WWW\samlab.ws_bot` — `python -m pytest` puts the CWD on `sys.path`, which is how `import version` resolves.

**Repos:** bot code lives in `F:\-SAM-\WWW\samlab.ws_bot` (commits in English conventional style: `feat:`, `fix:`, `docs:`). The spec lives in the `F:\Meteo` docs repo (commits in Russian).

## Global Constraints

- **No third-party dependencies.** stdlib only.
- **kaldata behavior must stay byte-identical** except Task 1's four new channel words (a deliberate bug fix: a Snapshot build must not enter the Final track). Every existing kaldata test must keep passing untouched.
- **Feed links never reach a `.ini`.** Links from either feed are shown in `needs-review.txt` only; the bot substitutes versions into our own URLs, never rewrites them to a source's URL. (Existing behavior — do not weaken it.)
- **No downgrade, no beta channel, banned words (`crack|keygen|repack`), two-version titles refused on kaldata** — all inherited, unchanged.
- **State key = `"<source>:<link>"`**, never `guid` (softexia's guid points at a foreign domain, `dev1.tech`).
- **Dry-run is the default.** The only live run in this plan (Task 8) is a dry-run; never pass `--apply`.
- **`.ini` files are cp1251, only `[link_N]` is rewritten** — untouched by this plan.
- **No `tail`/`head` on this machine.** Use PowerShell `Get-Content <file> -Tail N`.
- **Test commands:**
  - full suite: `& "F:\Meteo\.venv\Scripts\python.exe" -m pytest -q`
  - strict: `& "F:\Meteo\.venv\Scripts\python.exe" -m pytest -q -W error`
  - single file: `& "F:\Meteo\.venv\Scripts\python.exe" -m pytest tests/test_version.py -v`
- **`config.json` must keep `feed_url`**: `tests/test_smoke.py` asserts it, and it is the fallback when `sources` is absent.
- Never commit `state.json`, `needs-review.txt`, `*.bak` (already in `.gitignore`).

## File Structure

```
F:\-SAM-\WWW\samlab.ws_bot\
  version.py           + 4 words in CHANNEL_RE and NON_FINAL_MARKERS, + first_version()
  match.py             + 4 words in TRAILING_MARKERS_RE
  softexia.py          NEW — prepare_title, pick_version, PROFILE
  sources.py           NEW — PROFILES, load_sources, make_entry, fetch_entries
  kaldata.py           + PROFILE, + deadline-aware fetch()/fetch_feed()
  run.py               multi-source loop, per-source counters, duplicate-source,
                       time budget, queue dedup, profile-aware plan_entry
  config.json          + "sources": [...], + "budget_seconds"
  RUNBOOK.md           two-source docs
  tests\
    test_softexia.py       NEW
    test_sources.py        NEW
    test_real_catalog.py   NEW (skips when the real catalog is absent)
    test_run.py            multi-source / budget / duplicate / dedup tests
    test_version.py        new-marker and first_version tests
    test_match.py          softexia-shaped URL tests
    test_kaldata.py        deadline tests
```

Module dependency order (one-directional, no cycles):
`version` ← `match` ← {`kaldata`, `softexia`} ← `sources` ← `run`; `iniwrite` ← `run`.

Profiles are plain dicts, the shared contract every source implements:

```python
{
    "prepare": callable(title) -> title,   # cut the advertising tail, or identity
    "pick":    callable(title) -> version or None,
    "multi":   "skip" | "max-final",       # what "1.0 / 2.0" means for this feed
    "channel": "first" | "any",            # which track decides the release channel
}
```

---

### Task 1: Channel markers — snapshot / unstable / prerelease / insiders

**Files:**
- Modify: `F:\-SAM-\WWW\samlab.ws_bot\version.py` (CHANNEL_RE ~line 19, NON_FINAL_MARKERS ~line 27)
- Modify: `F:\-SAM-\WWW\samlab.ws_bot\match.py` (TRAILING_MARKERS_RE ~line 20)
- Test: `tests\test_version.py`, `tests\test_match.py`
- Create: `tests\test_real_catalog.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `version.classify_channel("snapshot") == "beta"`; `version.version_tracks(...)` marks the four words as beta channels; `version.split_channel(...)` strips them; `match.normalize("Vivaldi 8.3.4175.3 Snapshot") == "vivaldi"`; `match.slug_from_link` unchanged (new tests only pin softexia-shaped URLs).
- Note on the spec's phrase «гибрид `foo-bar-2` не срезается»: measured behavior is `slug_from_link(".../foo-bar-2") == "foo-bar"` — the `-<digits>` id goes, the slug's own hyphens stay; a digit run glued to a letter (`foo-bar2`) is kept. The tests below pin the measured behavior; behavior is unchanged by this plan.

- [ ] **Step 1: Write the failing tests**

Append to `tests\test_version.py`:

```python
class TestNewChannelWords:
    """The four words softexia needs: a Snapshot build must never look Final."""

    def test_classify(self):
        for word in ("snapshot", "unstable", "prerelease", "insiders",
                     "Snapshot", "UNSTABLE"):
            assert version.classify_channel(word) == "beta"

    def test_split_channel_reports_beta_and_strips_the_word(self):
        for word in ("Snapshot", "Unstable", "Prerelease", "Insiders"):
            text, channel = version.split_channel("Foo 1.0 " + word)
            assert channel == "beta"
            assert word not in text

    def test_vivaldi_snapshot_track_is_not_final(self):
        title = "Vivaldi 8.2.4133.83 Upd 8/ 8.3.4175.3 Snapshot"
        assert version.version_tracks(title) == [
            ("8.2.4133.83", "final"),
            ("8.3.4175.3", "beta"),
        ]
        assert version.final_track_version(title) == "8.2.4133.83"

    def test_greenshot_unstable_track_is_not_final(self):
        title = "Greenshot 1.4.289 Unstable/ 1.3.315 Stable"
        assert version.version_tracks(title) == [
            ("1.4.289", "beta"),
            ("1.3.315", "final"),
        ]
        assert version.final_track_version(title) == "1.3.315"
```

Append to `tests\test_match.py` (inside `TestNormalize` or as a new class — new class at file end):

```python
class TestNormalizeNewMarkers:
    def test_trailing_new_marker_is_stripped(self):
        # without the marker in TRAILING_MARKERS_RE the key keeps the suffix
        # and stops equaling any slug: "vivaldisnapshot"
        assert match.normalize("Vivaldi 8.3.4175.3 Snapshot") == "vivaldi"
        assert match.normalize("Greenshot 1.4.289 Unstable") == "greenshot"
        assert match.normalize("Foo 1.0 Prerelease") == "foo"
        assert match.normalize("Foo 1.0 Insiders") == "foo"


class TestSlugFromLinkWithoutId:
    """softexia links are clean paths with no numeric article id."""

    def test_plain_path_keeps_its_slug(self):
        url = "https://www.softexia.com/multimedia/audio-editing/reaper"
        assert match.slug_from_link(url) == "reaper"

    def test_hyphenated_slug_is_kept(self):
        url = "https://www.softexia.com/internet/browsers/microsoft-edge"
        assert match.slug_from_link(url) == "microsoft-edge"

    def test_trailing_id_is_still_stripped(self):
        # kaldata's "-<digits>" rule is unchanged; the id goes, the hyphens stay
        assert match.slug_from_link("https://x/foo-bar-2") == "foo-bar"

    def test_digit_run_without_a_separator_is_kept(self):
        assert match.slug_from_link("https://x/foo-bar2") == "foo-bar2"
        assert match.slug_from_link("https://x/foobar2.html") == "foobar2"
```

Create `tests\test_real_catalog.py`:

```python
"""Regression against the real catalog: the new marker words must change nothing.

The four words added for softexia (snapshot/unstable/prerelease/insiders) are
only safe because none of our 920 real names contains them. This proves that
claim on every machine that has the catalog; elsewhere it skips.
"""
import pathlib
import re

import pytest

import iniwrite

REAL_SOFT_DIR = pathlib.Path(r"F:\-SAM-\WWW\samlab.ws\soft")

NEW_MARKER_RE = re.compile(
    r"(?<!\w)(snapshot|unstable|prerelease|insiders)\s*\d*(?!\w)", re.IGNORECASE
)

pytestmark = pytest.mark.skipif(
    not REAL_SOFT_DIR.is_dir(), reason="the real catalog is not on this machine"
)


def _catalog_names():
    names = []
    for path in sorted(REAL_SOFT_DIR.glob("*.ini")):
        try:
            text = iniwrite.read_ini(str(path))
            names.append((path.stem, iniwrite.current_name(text)))
        except (OSError, UnicodeDecodeError):
            # the bot tolerates an unreadable file by giving it no name
            # (build_slug_names), so the regression check tolerates it too
            names.append((path.stem, ""))
    return names


def test_the_catalog_was_really_read():
    assert len(_catalog_names()) >= 900


def test_no_real_name_contains_a_new_marker_word():
    hits = []
    for stem, name in _catalog_names():
        if NEW_MARKER_RE.search(stem) or NEW_MARKER_RE.search(name):
            hits.append((stem, name))
    assert hits == []
```

- [ ] **Step 2: Run the tests to verify they fail**

```powershell
& "F:\Meteo\.venv\Scripts\python.exe" -m pytest tests/test_version.py tests/test_match.py tests/test_real_catalog.py -v
```

Expected: exactly the 5 new channel/normalize tests fail (`test_classify` gives `"final"` today; `version_tracks` reports both Vivaldi/Greenshot tracks as `final`; `normalize` leaves `snapshot` in the key). The catalog-guard and `slug_from_link` tests already pass — they pin existing behavior.

- [ ] **Step 3: Add the four words in all three places**

`version.py` — CHANNEL_RE (the comment above it stays):

```python
CHANNEL_RE = re.compile(
    r"(?<!\w)(final|stable|release|beta|alpha|dev|nightly|rc|portable"
    r"|snapshot|unstable|prerelease|insiders)\s*\d*(?!\w)",
    re.IGNORECASE,
)
```

`version.py` — NON_FINAL_MARKERS (keep the "portable sits here on purpose" comment, append the new rationale):

```python
# "portable" sits here on purpose: a portable build is published at a different
# URL, so rewriting its name to the plain Final version would point the file at
# the wrong download. Such entries go to the review queue instead.
# The last four words are softexia's snapshot builds: without them a
# "Vivaldi ... Snapshot" would be offered to the Final track.
NON_FINAL_MARKERS = {
    "beta", "alpha", "dev", "nightly", "rc", "portable",
    "snapshot", "unstable", "prerelease", "insiders",
}
```

`match.py` — TRAILING_MARKERS_RE:

```python
TRAILING_MARKERS_RE = re.compile(
    r"\s+(?:final|stable|release|beta|alpha|dev|nightly|rc|portable"
    r"|snapshot|unstable|prerelease|insiders)\s*\d*$",
    re.IGNORECASE,
)
```

- [ ] **Step 4: Run the full suite**

```powershell
& "F:\Meteo\.venv\Scripts\python.exe" -m pytest -q
```

Expected: all pass (174 old + 11 new = 185).

- [ ] **Step 5: Commit**

```powershell
git -C "F:\-SAM-\WWW\samlab.ws_bot" add version.py match.py tests/test_version.py tests/test_match.py tests/test_real_catalog.py
git -C "F:\-SAM-\WWW\samlab.ws_bot" commit -m "feat: classify snapshot, unstable, prerelease and insiders as beta channels"
```

---

### Task 2: `softexia.py` — trim the title, pick the biggest Final build

**Files:**
- Create: `F:\-SAM-\WWW\samlab.ws_bot\softexia.py`
- Create: `F:\-SAM-\WWW\samlab.ws_bot\tests\test_softexia.py`

**Interfaces:**
- Consumes: `version.version_tracks(text) -> [(version, channel)]`, `version.version_tuple(v) -> tuple[int]`.
- Produces:
  - `softexia.prepare_title(title: str) -> str`
  - `softexia.pick_version(title: str) -> str | None`
  - `softexia.PROFILE == {"prepare": prepare_title, "pick": pick_version, "multi": "max-final", "channel": "any"}`

- [ ] **Step 1: Write the failing tests**

Create `tests\test_softexia.py`:

```python
import softexia
import version


class TestPrepareTitle:
    def test_cuts_the_advertising_tail(self):
        got = softexia.prepare_title(
            "REAPER 7.82 \u2013 Digital Audio Workstation by Cockos"
        )
        assert got == "REAPER 7.82"

    def test_cuts_at_the_first_separator_only(self):
        got = softexia.prepare_title(
            "O&O Defrag 32.0 Build 26130 Pro \u2013 80% OFF"
        )
        assert got == "O&O Defrag 32.0 Build 26130 Pro"

    def test_plain_title_is_untouched(self):
        title = "Adobe Acrobat Reader 2026.002.21931"
        assert softexia.prepare_title(title) == title

    def test_hyphenated_product_names_survive(self):
        # the separator needs a space on BOTH sides, so names keep their hyphens
        for title in ("X-Pack 1.0", "Multi-Tool 2.0", "e-Sword 1.0"):
            assert softexia.prepare_title(title) == title

    def test_ascii_dash_with_spaces_is_cut_too(self):
        assert softexia.prepare_title("Foo 1.0 - Sale 50% OFF") == "Foo 1.0"

    def test_the_cut_leaves_no_version_behind_for_a_sale(self):
        got = softexia.prepare_title(
            "O&O Software Prime Sale \u2013 up to 85% OFF"
        )
        assert got == "O&O Software Prime Sale"
        assert version.find_versions(got) == []


class TestPickVersion:
    """The six live titles from the spec, one assertion each."""

    def test_larger_revision_wins(self):
        assert softexia.pick_version(
            "XYplorer 28.40.0300 x64/ 27.20.1600"
        ) == "28.40.0300"

    def test_bigger_major_wins(self):
        assert softexia.pick_version(
            "LibreOffice 26.8.1 / LibreOffice 26.2.6"
        ) == "26.8.1"

    def test_numeric_not_string_comparison(self):
        # "4.27.0" is longer than "3.95.4"; the compare must still pick 4.27.0
        assert softexia.pick_version(
            "Advanced Renamer 4.27.0 / 3.95.4"
        ) == "4.27.0"

    def test_snapshot_track_is_ignored(self):
        assert softexia.pick_version(
            "Vivaldi 8.2.4133.83 Upd 8/ 8.3.4175.3 Snapshot"
        ) == "8.2.4133.83"

    def test_unstable_track_is_ignored(self):
        assert softexia.pick_version(
            "Greenshot 1.4.289 Unstable/ 1.3.315 Stable"
        ) == "1.3.315"

    def test_beta_track_is_ignored(self):
        assert softexia.pick_version(
            "paint.NET 5.2 (5.200.9772.9330) Beta/ 5.1.12"
        ) == "5.2"

    def test_no_final_track_returns_none(self):
        assert softexia.pick_version("Foo 1.0 Snapshot") is None

    def test_no_version_returns_none(self):
        assert softexia.pick_version("O&O Software Prime Sale") is None

    def test_plain_title_returns_its_version(self):
        assert softexia.pick_version(
            "Adobe Acrobat Reader 2026.002.21931"
        ) == "2026.002.21931"


def test_profile_keys():
    assert set(softexia.PROFILE) == {"prepare", "pick", "multi", "channel"}
    assert softexia.PROFILE["multi"] == "max-final"
    assert softexia.PROFILE["channel"] == "any"
```

- [ ] **Step 2: Run the tests to verify they fail**

```powershell
& "F:\Meteo\.venv\Scripts\python.exe" -m pytest tests/test_softexia.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'softexia'`.

- [ ] **Step 3: Write `softexia.py`**

```python
"""Title preparation and version choice for the softexia feed.

softexia titles come in three shapes: clean, with an advertising tail
("REAPER 7.82 \u2013 Digital Audio Workstation by Cockos"), and with two
editions of one program ("XYplorer 28.40.0300 x64/ 27.20.1600"). The tail is
cut here, the biggest Final-track version wins there; the network, the RSS
parsing and the matching are shared through sources.py.
"""

import re

import version

# The advertising tail is separated by a spaced dash: en dash (U+2013, what the
# live feed uses), em dash (U+2014) or a plain hyphen. BOTH spaces are required,
# otherwise "X-Pack", "Multi-Tool" and "e-Sword" would be cut in half. The cut
# is at the FIRST separator, which is enough: seven of 21 live titles carry a
# tail and each carries one separator.
SEPARATOR_RE = re.compile(r"\s+[\u2013\u2014-]\s+")


def prepare_title(title):
    """Everything before the first spaced dash, or the title unchanged."""
    return SEPARATOR_RE.split(title, maxsplit=1)[0]


def pick_version(title):
    """The biggest Final-track version, or None.

    The opposite of kaldata's first-version rule: a softexia title may carry
    two editions ("Advanced Renamer 4.27.0 / 3.95.4") and the bigger one is
    the current release. Non-Final tracks are excluded by version_tracks,
    which is what keeps "Vivaldi 8.2.4133.83 Upd 8/ 8.3.4175.3 Snapshot" at
    8.2.4133.83. The comparison must be component-wise (version_tuple):
    "4.27.0" is longer than "3.95.4", yet (28, 40, 300) is smaller than
    (27, 20, 1600).
    """
    finals = [
        v for v, channel in version.version_tracks(title) if channel == "final"
    ]
    if not finals:
        return None
    return max(finals, key=version.version_tuple)


PROFILE = {
    "prepare": prepare_title,
    "pick": pick_version,
    "multi": "max-final",
    "channel": "any",
}
```

- [ ] **Step 4: Run the tests to verify they pass**

```powershell
& "F:\Meteo\.venv\Scripts\python.exe" -m pytest tests/test_softexia.py -v
```

Expected: all pass. (The Vivaldi/Greenshot picks depend on Task 1's markers — if this task is run out of order those two fail.)

- [ ] **Step 5: Run the full suite and commit**

```powershell
& "F:\Meteo\.venv\Scripts\python.exe" -m pytest -q
git -C "F:\-SAM-\WWW\samlab.ws_bot" add softexia.py tests/test_softexia.py
git -C "F:\-SAM-\WWW\samlab.ws_bot" commit -m "feat: add the softexia title profile"
```

Expected: all pass.

---

### Task 3: `version.first_version` + `kaldata.PROFILE` + profile-aware `plan_entry`

**Files:**
- Modify: `F:\-SAM-\WWW\samlab.ws_bot\version.py` (new function after `find_versions`)
- Modify: `F:\-SAM-\WWW\samlab.ws_bot\kaldata.py` (import version, add PROFILE)
- Modify: `F:\-SAM-\WWW\samlab.ws_bot\run.py` (`plan_entry`)
- Test: `tests\test_version.py`, `tests\test_run.py`

**Interfaces:**
- Consumes: Task 2's `softexia.PROFILE`.
- Produces:
  - `version.first_version(title) -> str | None` — first version cluster.
  - `kaldata.PROFILE == {"prepare": prepare_title, "pick": version.first_version, "multi": "skip", "channel": "first"}`.
  - `run.plan_entry(entry, slugs, aliases, soft_dir, slug_names=None, profile=None)` — with `profile=None` it behaves exactly as today (kaldata rules).

- [ ] **Step 1: Write the failing tests**

Append to `tests\test_version.py`:

```python
class TestFirstVersion:
    def test_first_cluster_wins(self):
        assert version.first_version("REAPER 7.82 Final") == "7.82"

    def test_multi_track_takes_the_first(self):
        # kaldata leads with its primary track; softexia picks the biggest
        # Final one instead (softexia.pick_version)
        title = "Vivaldi 8.3.4175.3 Dev + 8.2.4133.83 Final"
        assert version.first_version(title) == "8.3.4175.3"

    def test_none_without_a_version(self):
        assert version.first_version("Sale up to 85% OFF") is None
```

In `tests\test_run.py`: add `import softexia` next to the existing `import kaldata`, then append:

```python
class TestPlanEntryProfiles:
    """The profile swaps prepare/pick/gates; the default stays kaldata."""

    def test_default_profile_is_the_kaldata_one(self, soft_dir):
        got = bot.plan_entry(
            _entry("Foo 4.27 / 3.95 Final", "https://k/x/1.html", "1"),
            {"reaper"}, {}, soft_dir,
        )
        assert got["reason"] == "two-versions"

    def test_kaldata_refuses_a_beta_first_track(self, soft_dir):
        got = bot.plan_entry(
            _entry("Foo 9.9 Snapshot", "https://k/x/1.html", "1"),
            {"reaper"}, {}, soft_dir, profile=kaldata.PROFILE,
        )
        assert got["action"] == "skip"
        assert got["reason"] == "not-final-channel"

    def test_softexia_profile_takes_the_bigger_of_two_versions(self, soft_dir):
        got = bot.plan_entry(
            _entry("REAPER 7.83 / 7.82 Final",
                   "https://www.softexia.com/multimedia/audio-editing/reaper", "1"),
            {"reaper"}, {}, soft_dir, profile=softexia.PROFILE,
        )
        assert got["action"] == "update"
        assert got["new_version"] == "7.83"
        assert got["slug"] == "reaper"

    def test_softexia_cuts_the_tail_before_matching(self, soft_dir):
        got = bot.plan_entry(
            _entry("REAPER 7.83 \u2013 Digital Audio Workstation by Cockos",
                   "https://www.softexia.com/multimedia/audio-editing/reaper", "1"),
            {"reaper"}, {}, soft_dir, profile=softexia.PROFILE,
        )
        assert got["action"] == "update"
        assert got["title"] == "REAPER 7.83"
        assert got["slug"] == "reaper"

    def test_softexia_rejects_an_all_beta_title(self, soft_dir):
        got = bot.plan_entry(
            _entry("Foo 1.0 Snapshot", "https://www.softexia.com/x/foo", "1"),
            {"reaper"}, {}, soft_dir, profile=softexia.PROFILE,
        )
        assert got["action"] == "skip"
        assert got["reason"] == "not-final-channel"

    def test_softexia_sale_title_has_no_version(self, soft_dir):
        got = bot.plan_entry(
            _entry("O&O Software Prime Sale \u2013 up to 85% OFF",
                   "https://www.softexia.com/x/oo-sale", "1"),
            {"reaper"}, {}, soft_dir, profile=softexia.PROFILE,
        )
        assert got["action"] == "skip"
        assert got["reason"] == "no-version"
```

- [ ] **Step 2: Run the tests to verify they fail**

```powershell
& "F:\Meteo\.venv\Scripts\python.exe" -m pytest tests/test_version.py::TestFirstVersion tests/test_run.py::TestPlanEntryProfiles -v
```

Expected: `TestFirstVersion` fails (`first_version` undefined); `test_default_profile_is_the_kaldata_one` passes already; the four `profile=` tests fail with `TypeError: plan_entry() got an unexpected keyword argument 'profile'`.

- [ ] **Step 3: Implement the three pieces**

`version.py` — new function after `find_versions`:

```python
def first_version(title):
    """The first version cluster of the title, or None.

    kaldata leads with the track it considers primary, so the first cluster is
    the one to compare against. softexia needs the biggest Final track instead
    (see softexia.pick_version); one root, two rules, and which rule applies is
    the source profile's business.
    """
    offsets = find_versions(title)
    if not offsets:
        return None
    return title[offsets[0][0]:offsets[0][1]]
```

`kaldata.py` — add `import version` to the import block, then after the imports/constants block:

```python
# How this feed's titles are read; sources.py publishes it as PROFILES.
# kaldata leads with its primary version, treats a title carrying two
# slash-separated versions as a repack to refuse, and lets the FIRST track
# decide the release channel. Nothing about kaldata's behaviour changes —
# this dict is the existing rules, named.
def prepare_title(title):
    """kaldata titles are used as they come; the key exists so that every
    profile has the same four keys."""
    return title


PROFILE = {
    "prepare": prepare_title,
    "pick": version.first_version,
    "multi": "skip",
    "channel": "first",
}
```

`run.py` — replace `plan_entry` (docstring included):

```python
def plan_entry(entry, slugs, aliases, soft_dir, slug_names=None, profile=None):
    """Decide what to do with one feed article.

    Reads the matched ``.ini`` to learn its current Final-track version, but
    never writes anything.

    ``profile`` is the source's four-key dict: ``prepare`` trims the raw title,
    ``pick`` extracts the candidate version, ``multi`` decides what two
    slash-separated versions mean ("skip" for kaldata, "max-final" for
    softexia) and ``channel`` decides how a non-Final track rejects the entry
    ("first": the leading track decides, "any": reject only when no track is
    Final). It defaults to kaldata's profile, so callers written before
    profiles existed behave exactly as before.

    ``slug_names`` maps each slug to the ``name=`` of its file so ``find_match``
    can refuse a title two of our files share; it defaults to an empty map,
    which only disables that check and is meant for callers that already hold
    it.
    """
    if profile is None:
        profile = kaldata.PROFILE
    title = profile["prepare"](entry.get("title", ""))
    link = entry.get("link", "")
    result = {"action": "skip", "reason": "", "slug": None,
              "old_version": None, "new_version": None, "title": title}

    if version.has_banned_words(title):
        result["reason"] = "banned"
        return result

    if profile["multi"] == "skip" and version.has_slash_versions(title):
        result["reason"] = "two-versions"
        return result

    if profile["channel"] == "first":
        _clean, channel = version.split_channel(title)
        if channel != "final":
            result["reason"] = "not-final-channel"
            return result
    else:  # "any": reject only when NO track is Final; an empty title with no
        # versions at all falls through to pick_version and reports no-version
        tracks = version.version_tracks(title)
        if tracks and all(ch != "final" for _v, ch in tracks):
            result["reason"] = "not-final-channel"
            return result

    new_version = profile["pick"](title)
    if not new_version:
        result["reason"] = "no-version"
        return result
    result["new_version"] = new_version

    slug = match.find_match(title, link, slugs, aliases, slug_names or {})
    if slug is None:
        result["reason"] = "no-match"
        return result
    result["slug"] = slug

    ini_path = os.path.join(soft_dir, slug + ".ini")
    text = iniwrite.read_ini(ini_path)
    current = version.final_track_version(iniwrite.current_name(text))

    if current is None:
        result["action"] = "queue"
        result["reason"] = "no-final-track"
        return result
    result["old_version"] = current

    if not version.is_newer(new_version, current):
        result["reason"] = "not-newer"
        return result

    result["action"] = "update"
    return result
```

Note: for the kaldata profile the decision order and every value are identical to the old code — banned → two-versions → first-track channel → first version cluster → match → compare.

- [ ] **Step 4: Run the full suite**

```powershell
& "F:\Meteo\.venv\Scripts\python.exe" -m pytest -q
```

Expected: all pass (existing `TestPlanEntry` tests untouched and green).

- [ ] **Step 5: Commit**

```powershell
git -C "F:\-SAM-\WWW\samlab.ws_bot" add version.py kaldata.py run.py tests/test_version.py tests/test_run.py
git -C "F:\-SAM-\WWW\samlab.ws_bot" commit -m "feat: give plan_entry a per-source title profile"
```

---

### Task 4: `sources.py` — the source registry

**Files:**
- Create: `F:\-SAM-\WWW\samlab.ws_bot\sources.py`
- Create: `F:\-SAM-\WWW\samlab.ws_bot\tests\test_sources.py`

**Interfaces:**
- Consumes: `kaldata.PROFILE`, `softexia.PROFILE`, `kaldata.fetch_feed(feed_url, timeout=30)`.
- Produces:
  - `sources.PROFILES: dict[str, profile]` — `{"kaldata": kaldata.PROFILE, "softexia": softexia.PROFILE}`
  - `sources.load_sources(config) -> [{"name": str, "url": str, "profile": dict}]`
  - `sources.make_entry(item, source_name) -> {"title": str, "link": str, "key": str}` with `key = "<source>:<link>"`
  - `sources.fetch_entries(source, timeout=30) -> [entry]`

- [ ] **Step 1: Write the failing tests**

Create `tests\test_sources.py`:

```python
import pytest

import sources


class TestLoadSources:
    def test_falls_back_to_feed_url(self):
        cfg = {"feed_url": "https://k/feed"}
        got = sources.load_sources(cfg)
        assert [s["name"] for s in got] == ["kaldata"]
        assert got[0]["url"] == "https://k/feed"
        assert got[0]["profile"] is sources.PROFILES["kaldata"]

    def test_reads_the_sources_list_in_order(self):
        cfg = {
            "feed_url": "https://k/feed",
            "sources": [
                {"name": "kaldata", "url": "https://k/feed", "profile": "kaldata"},
                {"name": "softexia", "url": "https://www.softexia.com/feed",
                 "profile": "softexia"},
            ],
        }
        got = sources.load_sources(cfg)
        assert [s["name"] for s in got] == ["kaldata", "softexia"]
        assert got[1]["profile"] is sources.PROFILES["softexia"]
        assert got[1]["url"] == "https://www.softexia.com/feed"

    def test_profile_defaults_to_the_source_name(self):
        cfg = {"sources": [{"name": "softexia", "url": "u"}]}
        got = sources.load_sources(cfg)
        assert got[0]["profile"] is sources.PROFILES["softexia"]

    def test_unknown_profile_raises(self):
        cfg = {"sources": [{"name": "x", "url": "u", "profile": "nope"}]}
        with pytest.raises(ValueError, match="nope"):
            sources.load_sources(cfg)

    def test_profiles_are_the_module_objects(self):
        import kaldata
        import softexia
        assert sources.PROFILES["kaldata"] is kaldata.PROFILE
        assert sources.PROFILES["softexia"] is softexia.PROFILE


class TestMakeEntry:
    ITEM = {
        "title": "REAPER 7.82 Final",
        "link": "https://www.softexia.com/multimedia/audio-editing/reaper",
        "guid": "https://dev1.tech/uncategorized/reaper",
        "pub_date": "Mon, 05 Oct 2026 05:39:46 +0000",
    }

    def test_key_is_source_and_link(self):
        entry = sources.make_entry(self.ITEM, "softexia")
        assert entry["key"] == (
            "softexia:https://www.softexia.com/multimedia/audio-editing/reaper"
        )

    def test_guid_is_dropped(self):
        # softexia's guid points at the author's previous blog; relying on a
        # foreign domain would re-key the whole feed if the blog moved
        entry = sources.make_entry(self.ITEM, "softexia")
        assert "guid" not in entry

    def test_same_program_from_two_sources_gets_two_keys(self):
        link = "https://example.org/reaper"
        item = {"title": "x", "link": link}
        first = sources.make_entry(item, "kaldata")
        second = sources.make_entry(item, "softexia")
        assert first["key"] != second["key"]


class TestFetchEntries:
    def test_builds_keyed_entries(self, monkeypatch):
        monkeypatch.setattr(
            sources.kaldata, "fetch_feed",
            lambda url, timeout=30: [
                {"title": "REAPER 7.82", "link": "https://x/reaper",
                 "guid": "g1", "pub_date": ""},
            ],
        )
        source = {"name": "softexia", "url": "https://www.softexia.com/feed",
                  "profile": sources.PROFILES["softexia"]}

        got = sources.fetch_entries(source, timeout=5)

        assert got == [{
            "title": "REAPER 7.82",
            "link": "https://x/reaper",
            "key": "softexia:https://x/reaper",
        }]
```

- [ ] **Step 2: Run the tests to verify they fail**

```powershell
& "F:\Meteo\.venv\Scripts\python.exe" -m pytest tests/test_sources.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'sources'`.

- [ ] **Step 3: Write `sources.py`**

```python
"""Registry of feed sources.

One source = one RSS feed plus the profile that says how to read its titles.
Everything the sources share - retries, RSS parsing, the state key - lives in
kaldata.py and here; a profile only ever supplies four things:

    prepare title -> title      cut the advertising tail, or identity
    pick     title -> version   first cluster, or the biggest Final track
    multi    "skip"|"max-final" what "1.0 / 2.0" means for this feed
    channel  "first"|"any"      which track decides the release channel

Adding a source is one function in its own module plus one entry in
config.json.
"""

import kaldata
import softexia

PROFILES = {
    "kaldata": kaldata.PROFILE,
    "softexia": softexia.PROFILE,
}


def load_sources(config):
    """The configured sources, in polling order.

    A config without a ``sources`` key falls back to ``feed_url`` as a single
    kaldata source, so a config written before the second source existed keeps
    working unchanged. An unknown profile name raises: a typo in config.json
    must not silently poll with the wrong rules.
    """
    raw = config.get("sources")
    if not raw:
        raw = [{
            "name": "kaldata",
            "url": config["feed_url"],
            "profile": "kaldata",
        }]
    result = []
    for item in raw:
        name = item["name"]
        profile_name = item.get("profile", name)
        if profile_name not in PROFILES:
            raise ValueError("unknown source profile: %r" % profile_name)
        result.append({
            "name": name,
            "url": item["url"],
            "profile": PROFILES[profile_name],
        })
    return result


def make_entry(item, source_name):
    """One RSS item in our entry shape.

    ``guid`` is deliberately dropped: softexia's guid points at a foreign
    domain (the author's previous blog), and the state key is the pair
    "source + link" - stable across both feeds and unique within each. The
    same program seen in both feeds therefore gets two keys and neither
    feed's entry consumes the other's.
    """
    link = item.get("link", "")
    return {
        "title": item.get("title", ""),
        "link": link,
        "key": "%s:%s" % (source_name, link),
    }


def fetch_entries(source, timeout=30):
    """Fetch one source's feed and return its entries."""
    items = kaldata.fetch_feed(source["url"], timeout=timeout)
    return [make_entry(item, source["name"]) for item in items]
```

- [ ] **Step 4: Run the tests to verify they pass**

```powershell
& "F:\Meteo\.venv\Scripts\python.exe" -m pytest tests/test_sources.py -v
```

Expected: all pass.

- [ ] **Step 5: Run the full suite and commit**

```powershell
& "F:\Meteo\.venv\Scripts\python.exe" -m pytest -q
git -C "F:\-SAM-\WWW\samlab.ws_bot" add sources.py tests/test_sources.py
git -C "F:\-SAM-\WWW\samlab.ws_bot" commit -m "feat: add the feed source registry"
```

Expected: all pass.

---

### Task 5: Run-wide time budget in the fetch layer

**Files:**
- Modify: `F:\-SAM-\WWW\samlab.ws_bot\kaldata.py` (`fetch`, `fetch_feed`)
- Modify: `F:\-SAM-\WWW\samlab.ws_bot\sources.py` (`fetch_entries` signature)
- Test: `tests\test_kaldata.py`
- Modify: `tests\test_run.py` (widen two mocks to the new signature)

**Interfaces:**
- Consumes: nothing new.
- Produces:
  - `kaldata.fetch(url, timeout=30, attempts=None, backoff=..., deadline=None)` — `deadline` is a `time.monotonic()` value bounding the whole call; `None` keeps today's behavior byte-for-byte.
  - `kaldata.fetch_feed(feed_url, timeout=30, deadline=None)`
  - `sources.fetch_entries(source, timeout=30, deadline=None)`

Why: 8 retries with rising backoff cost 42 s of pure sleeping plus up to 30 s per attempt; a dead URL holds a run for over two minutes, and two sources would double that. The budget is enforced from `run.py` (Task 7) but must bite inside the retry loop, or "the run takes at most N minutes" is unprovable.

- [ ] **Step 1: Write the failing tests**

Append to `tests\test_kaldata.py`:

```python
class TestDeadline:
    def test_past_deadline_never_starts(self, monkeypatch):
        calls = []
        monkeypatch.setattr(kaldata.time, "sleep",
                            lambda s: calls.append(("sleep", s)))
        monkeypatch.setattr(kaldata, "_open",
                            lambda url, timeout: calls.append(("open", timeout)))
        try:
            kaldata.fetch("https://example.org/", attempts=5, backoff=1.5,
                          deadline=kaldata.time.monotonic() - 1)
        except RuntimeError as exc:
            assert "time budget exhausted" in str(exc)
        else:
            raise AssertionError("expected a budget failure")
        assert calls == []

    def test_tight_deadline_stops_before_sleeping(self, monkeypatch):
        slept = []
        monkeypatch.setattr(kaldata.time, "sleep", slept.append)
        monkeypatch.setattr(
            kaldata, "_open",
            lambda url, timeout: (_ for _ in ()).throw(OSError("connection reset")),
        )
        try:
            kaldata.fetch("https://example.org/", attempts=8, backoff=1.5,
                          deadline=kaldata.time.monotonic() + 0.5)
        except RuntimeError as exc:
            assert "time budget exhausted" in str(exc)
        else:
            raise AssertionError("expected the deadline to stop the retries")
        assert slept == [], slept

    def test_far_deadline_behaves_like_no_deadline(self, monkeypatch):
        class GoodResponse:
            def read(self):
                return b"<rss>full body</rss>"

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        monkeypatch.setattr(kaldata, "_open", lambda url, timeout: GoodResponse())
        body = kaldata.fetch(
            "https://example.org/", attempts=3, backoff=0,
            deadline=kaldata.time.monotonic() + 60,
        )
        assert body == "<rss>full body</rss>"
```

- [ ] **Step 2: Run the tests to verify they fail**

```powershell
& "F:\Meteo\.venv\Scripts\python.exe" -m pytest tests/test_kaldata.py::TestDeadline -v
```

Expected: 3 failures — `TypeError: fetch() got an unexpected keyword argument 'deadline'`.

- [ ] **Step 3: Implement the deadline**

`kaldata.py` — replace `fetch`:

```python
def fetch(url, timeout=30, attempts=None, backoff=FETCH_BACKOFF_SECONDS,
          deadline=None):
    """Fetch a URL and return its body as text, retrying truncated responses.

    kaldata is served through Cloudflare with chunked transfer encoding and
    closes the connection mid-body often enough that a single attempt is not a
    reasonable design: five of six live feed reads raised ``IncompleteRead``.
    Retrying is safe because every failure here is a failure to obtain the
    *whole* body - a partial read is discarded, never returned, because half a
    feed parses into half a list of articles and would look like a quiet week.

    ``Accept-Encoding: identity`` removes the compression negotiation that
    makes the truncation visible in the first place.

    ``deadline`` (a ``time.monotonic()`` value) bounds the whole call: the
    backoff sleep is skipped when it would pass the deadline, the per-attempt
    timeout is clamped to the time left, and RuntimeError then says "time
    budget exhausted" instead of retrying past the budget. With ``deadline``
    omitted every attempt behaves exactly as before.

    Raises ``RuntimeError`` when every attempt fails, including when the body
    is genuinely empty.
    """
    attempts = attempts or FETCH_ATTEMPTS
    last_error = None
    done = 0
    budget_hit = False

    for attempt in range(attempts):
        if attempt:
            wait = backoff * attempt
            if deadline is not None and time.monotonic() + wait >= deadline:
                budget_hit = True
                break
            time.sleep(wait)
        if deadline is not None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                budget_hit = True
                break
            timeout = min(timeout, remaining)
        done += 1
        body, error = _once(url, timeout)
        if body is not None:
            return body
        last_error = error

    if budget_hit:
        raise RuntimeError(
            "time budget exhausted while fetching %s" % url
        )
    raise RuntimeError(
        "fetch failed after %d attempts: %s: %s"
        % (done, type(last_error).__name__, last_error)
    )
```

With `deadline=None` the two new branches never fire, `done == attempts`, and the final message is identical to today's.

`kaldata.py` — replace `fetch_feed`:

```python
def fetch_feed(feed_url, timeout=30, deadline=None):
    """Fetch and parse the software feed."""
    return parse_feed(fetch(feed_url, timeout, deadline=deadline))
```

`sources.py` — replace `fetch_entries`:

```python
def fetch_entries(source, timeout=30, deadline=None):
    """Fetch one source's feed and return its entries."""
    items = kaldata.fetch_feed(source["url"], timeout=timeout, deadline=deadline)
    return [make_entry(item, source["name"]) for item in items]
```

`tests\test_run.py` — widen the two mocks that stand in for `fetch_feed`
(`fetch_feed` is now called with a `deadline=` kwarg from Task 6 on; land the
widening with the signature change):

```python
def _feed(*items):
    return lambda url, timeout=30, deadline=None: list(items)
```

and in `test_feed_failure_is_reported`:

```python
        def boom(url, timeout=30, deadline=None):
            raise RuntimeError("empty response body")
```

- [ ] **Step 4: Run the full suite**

```powershell
& "F:\Meteo\.venv\Scripts\python.exe" -m pytest -q
```

Expected: all pass, including the untouched retry tests (`test_attempts_are_delayed_between_tries` etc. still see identical sleeps because they pass no deadline).

- [ ] **Step 5: Commit**

```powershell
git -C "F:\-SAM-\WWW\samlab.ws_bot" add kaldata.py sources.py tests/test_kaldata.py tests/test_run.py
git -C "F:\-SAM-\WWW\samlab.ws_bot" commit -m "feat: bound a fetch by a run-wide time budget"
```

---

### Task 6: `run.py` — poll every configured source, report per source

**Files:**
- Modify: `F:\-SAM-\WWW\samlab.ws_bot\run.py`
- Test: `tests\test_run.py`

**Interfaces:**
- Consumes: `sources.load_sources(config)`, `sources.fetch_entries(source, timeout=...)`, `run.plan_entry(..., profile=...)` (Task 3).
- Produces:
  - `run.run(config, aliases, apply, now=None)` where `config` may carry `sources: [{name, url, profile}]` (falls back to `feed_url`).
  - `summary` gains `"duplicates"` and `"by_source": {name: counters}`; the flat counters keep their meaning.
  - stdout: flat line first, then one `  <name>: ...` line per source.
  - state keys are `entry["key"]` = `source:link`.
- Existing test fixes in this task: the `plan_entry` spy in `TestSlugNames` gains a `profile` parameter; `_unmatched_block` now suggests the alias key of the **prepared** title.

- [ ] **Step 1: Write the failing tests**

In `tests\test_run.py`: add `import json` next to `import os`, and append these module-level helpers after `_feed`:

```python
def _two_sources(config):
    config["sources"] = [
        {"name": "kaldata", "url": "https://k/x/feed", "profile": "kaldata"},
        {"name": "softexia", "url": "https://www.softexia.com/feed",
         "profile": "softexia"},
    ]
    return config


def _fake_feeds(monkeypatch, feeds):
    monkeypatch.setattr(
        bot.kaldata, "fetch_feed",
        lambda url, timeout=30, deadline=None: list(feeds[url]),
    )
```

Append the new test class:

```python
class TestMultiSource:
    """The report must say which feed an outcome came from, and one dead
    feed must never cost the other feed's updates."""

    def test_counters_are_split_by_source(self, soft_dir, tmp_path, monkeypatch):
        config = _two_sources(_config(soft_dir, tmp_path))
        _fake_feeds(monkeypatch, {
            "https://k/x/feed": [
                _entry("REAPER 7.83 Final", "https://k/x/reaper-1.html", "g1"),
            ],
            "https://www.softexia.com/feed": [
                _entry("RustDesk 1.5.0", "https://www.softexia.com/x/rustdesk", "g2"),
            ],
        })

        summary = bot.run(config, {}, apply=False)

        assert summary["seen"] == 2
        assert summary["by_source"]["kaldata"]["would_update"] == 1
        assert summary["by_source"]["kaldata"]["unmatched"] == 0
        assert summary["by_source"]["softexia"]["would_update"] == 0
        assert summary["by_source"]["softexia"]["unmatched"] == 1
        assert summary["would_update"] == 1
        assert summary["unmatched"] == 1

    def test_one_feed_down_does_not_lose_the_other(self, soft_dir, tmp_path,
                                                   monkeypatch):
        config = _two_sources(_config(soft_dir, tmp_path))

        def fetch(url, timeout=30, deadline=None):
            if url.endswith("softexia.com/feed"):
                raise RuntimeError("empty response body")
            return [_entry("REAPER 7.83 Final", "https://k/x/reaper-1.html", "g1")]

        monkeypatch.setattr(bot.kaldata, "fetch_feed", fetch)

        summary = bot.run(config, {}, apply=False)

        assert summary["would_update"] == 1
        assert summary["errors"] == 1
        assert summary["by_source"]["softexia"]["errors"] == 1
        assert summary["by_source"]["kaldata"]["errors"] == 0
        with open(config["review_path"], encoding="utf-8") as fh:
            assert "FEED ERROR (softexia)" in fh.read()

    def test_state_keys_are_source_and_link_not_guid(self, soft_dir, tmp_path,
                                                     monkeypatch):
        # softexia's guid points at a foreign domain; the key must be the
        # source and the link instead, and each feed keeps its own copy
        config = _two_sources(_config(soft_dir, tmp_path))
        _fake_feeds(monkeypatch, {
            "https://k/x/feed": [
                _entry("REAPER 7.83 Final", "https://k/x/feed/reaper", "g1"),
            ],
            "https://www.softexia.com/feed": [
                _entry("REAPER 7.83 Final",
                       "https://www.softexia.com/feed/reaper", "g2"),
            ],
        })

        bot.run(config, {}, apply=True)

        state = bot.load_state(config["state_path"])
        assert state["seen_guids"] == [
            "kaldata:https://k/x/feed/reaper",
            "softexia:https://www.softexia.com/feed/reaper",
        ]

    def test_unmatched_suggestion_uses_the_prepared_title(self, soft_dir,
                                                          tmp_path, monkeypatch):
        config = _two_sources(_config(soft_dir, tmp_path))
        _fake_feeds(monkeypatch, {
            "https://k/x/feed": [],
            "https://www.softexia.com/feed": [
                _entry("RustDesk 1.5.0 \u2013 Remote Desktop",
                       "https://www.softexia.com/x/rustdesk", "g2"),
            ],
        })

        bot.run(config, {}, apply=False)

        with open(config["review_path"], encoding="utf-8") as fh:
            text = fh.read()
        assert "RustDesk 1.5.0" in text        # the cut title is reported
        assert "Remote Desktop" not in text     # the tail never leaks
        assert "'rustdesk': <slug>" in text     # the suggested key is usable

    def test_main_prints_a_per_source_line(self, soft_dir, tmp_path, monkeypatch,
                                           capsys):
        config = _two_sources(_config(soft_dir, tmp_path))
        cfg_path = tmp_path / "config.json"
        cfg_path.write_text(json.dumps(config), encoding="utf-8")
        _fake_feeds(monkeypatch, {
            "https://k/x/feed": [
                _entry("REAPER 7.83 Final", "https://k/x/reaper-1.html", "g1"),
            ],
            "https://www.softexia.com/feed": [],
        })

        code = bot.main([
            "--config", str(cfg_path),
            "--aliases", str(tmp_path / "aliases.json"),
        ])

        out = capsys.readouterr().out.splitlines()
        assert code == 0
        assert out[0].startswith("[DRY-RUN] seen=1 new=1")
        assert "duplicates=0" in out[0]
        assert "errors=0" in out[0]
        assert out[1].startswith("  kaldata: seen=1 new=1")
        assert out[2].startswith("  softexia: seen=0 new=0")
```

- [ ] **Step 2: Run the tests to verify they fail**

```powershell
& "F:\Meteo\.venv\Scripts\python.exe" -m pytest tests/test_run.py::TestMultiSource -v
```

Expected: all 5 fail — `by_source` missing, only `feed_url` polled (fallback path), flat line without `duplicates=`.

- [ ] **Step 3: Implement the loop**

In `run.py`:

1. Add `import sources` to the import block.
2. Add `duplicate-source` to `REASONS` (used from Task 7; the key must exist before the counters print it):

```python
REASONS = {
    "not-newer": "kaldata version is not newer than ours",
    "banned": "title advertises crack/keygen/repack",
    "two-versions": "title carries two versions separated by a slash",
    "no-version": "no parseable version in the title",
    "not-final-channel": "source is a beta/dev build; only the Final track is updated",
    "no-match": "no matching .ini in our catalog",
    "no-url-change": "the new version could not be put into our download URLs; nothing was written",
    "no-final-track": "our own name has no Final-track version to compare against",
    "duplicate-source": "the same slug was already handled by an earlier source in this run",
}
```

3. Add the counters factory after `ACTIONABLE_REASONS`:

```python
def _new_counters():
    """One source's share of the flat summary counters."""
    return {
        "seen": 0, "new_entries": 0, "updated": 0, "would_update": 0,
        "queued": 0, "skipped": 0, "errors": 0, "unmatched": 0,
        "duplicates": 0,
    }
```

4. Replace `run()` entirely:

```python
def run(config, aliases, apply, now=None):
    """Execute one polling cycle and return a summary dict.

    Every configured source is polled in turn and processed in its own
    ``try``: one feed being down is a line in the report and a non-zero
    counter, never a reason to lose the other feed's updates.

    With ``apply=False`` no ``.ini`` is opened for writing and the state file is
    left alone, so reviewing a dry-run never consumes the work.
    """
    soft_dir = config["soft_dir"]

    summary = _new_counters()
    summary["review_appended"] = 0
    summary["by_source"] = {}
    stamp = (now or datetime.datetime.now()).strftime("%Y-%m-%d %H:%M")
    review_lines = []

    source_list = sources.load_sources(config)

    state = load_state(config["state_path"])
    seen = set(state["seen_guids"])
    slug_set = set(list_slugs(soft_dir))
    slug_names = build_slug_names(soft_dir, slug_set)
    reported = set()

    for source in source_list:
        name = source["name"]
        counters = _new_counters()
        summary["by_source"][name] = counters

        try:
            entries = sources.fetch_entries(source, timeout=30)
        except Exception as exc:
            summary["errors"] += 1
            counters["errors"] += 1
            review_lines.append("%s FEED ERROR (%s): %s" % (stamp, name, exc))
            continue

        summary["seen"] += len(entries)
        counters["seen"] = len(entries)
        fresh = [entry for entry in entries if entry["key"] not in seen]
        summary["new_entries"] += len(fresh)
        counters["new_entries"] = len(fresh)

        # The review file is the durable record (a dry-run keeps no state), so
        # a title already written there must not be written again. softexia
        # titles are compared AFTER the advertising tail is cut, hence
        # prepare(): the file holds cut titles.
        reported |= _already_reported(
            config["review_path"],
            [source["profile"]["prepare"](entry["title"]) for entry in fresh],
        )

        for entry in fresh:
            try:
                decision = plan_entry(
                    entry, slug_set, aliases, soft_dir, slug_names,
                    profile=source["profile"],
                )
            except Exception as exc:
                summary["errors"] += 1
                counters["errors"] += 1
                review_lines.append(
                    "%s ERROR on %r: %s" % (stamp, entry.get("title"), exc)
                )
                seen.add(entry["key"])
                continue

            action = decision["action"]
            if action == "skip":
                summary["skipped"] += 1
                counters["skipped"] += 1
                # A title we cannot place is the one outcome that needs a
                # decision: either we do not carry the program, or our file is
                # named differently and an alias would fix it.
                if (decision["reason"] in ACTIONABLE_REASONS
                        and decision["title"] not in reported):
                    summary["unmatched"] += 1
                    counters["unmatched"] += 1
                    reported.add(decision["title"])
                    review_lines.extend(_unmatched_block(stamp, decision, entry))
            elif action == "queue":
                summary["queued"] += 1
                counters["queued"] += 1
                review_lines.extend(_review_block(stamp, decision, entry, config))
            else:
                path = os.path.join(soft_dir, decision["slug"] + ".ini")
                result = iniwrite.update_ini(
                    path, decision["old_version"], decision["new_version"],
                    write=apply,
                )
                if not result["changed"]:
                    # the version could not be put into the download URLs
                    summary["queued"] += 1
                    counters["queued"] += 1
                    decision["reason"] = "no-url-change"
                    review_lines.extend(
                        _review_block(stamp, decision, entry, config)
                    )
                elif apply:
                    summary["updated"] += 1
                    counters["updated"] += 1
                else:
                    summary["would_update"] += 1
                    counters["would_update"] += 1

            seen.add(entry["key"])

    summary["review_appended"] = append_review(config["review_path"], review_lines)
    if apply:
        state["seen_guids"] = sorted(seen)
        save_state(config["state_path"], state)
    return summary
```

5. Fix the alias suggestion in `_unmatched_block` to use the prepared title:

```python
    key = match.normalize(decision["title"])
```

(replace `key = match.normalize(entry.get("title", ""))` — `decision["title"]` is what `plan_entry` stored after `prepare()`, so a softexia advertising tail cannot pollute the suggested `aliases.json` key; for kaldata the two are identical.)

6. Fix the `TestSlugNames` spy in `tests\test_run.py` — `run()` now calls `plan_entry` with a keyword `profile`:

```python
        def spy(entry, slugs, aliases, soft_dir_arg, slug_names=None,
                profile=None):
            seen.update(slug_names or {})
            return real_plan(entry, slugs, aliases, soft_dir_arg, slug_names,
                             profile)
```

7. Replace the `main()` report block:

```python
    mode = "APPLY" if args.apply else "DRY-RUN"
    print(
        "[%s] seen=%d new=%d updated=%d would_update=%d queued=%d skipped=%d "
        "unmatched=%d duplicates=%d errors=%d"
        % (
            mode, summary["seen"], summary["new_entries"], summary["updated"],
            summary["would_update"], summary["queued"], summary["skipped"],
            summary["unmatched"], summary["duplicates"], summary["errors"],
        )
    )
    for name, counters in summary["by_source"].items():
        print(
            "  %s: seen=%d new=%d updated=%d would_update=%d queued=%d "
            "skipped=%d unmatched=%d duplicates=%d errors=%d"
            % (
                name, counters["seen"], counters["new_entries"],
                counters["updated"], counters["would_update"],
                counters["queued"], counters["skipped"],
                counters["unmatched"], counters["duplicates"],
                counters["errors"],
            )
        )
```

Also update the argparse description `"Update samlab.ws versions from kaldata"` → `"Update samlab.ws versions from the configured feeds"`.

- [ ] **Step 4: Run the full suite**

```powershell
& "F:\Meteo\.venv\Scripts\python.exe" -m pytest -q
```

Expected: all pass (existing single-source tests go through the `feed_url` fallback and keep their exact counters).

- [ ] **Step 5: Commit**

```powershell
git -C "F:\-SAM-\WWW\samlab.ws_bot" add run.py tests/test_run.py
git -C "F:\-SAM-\WWW\samlab.ws_bot" commit -m "feat: poll every configured source and report per-source counts"
```

---

### Task 7: Run policies — duplicate-source, time budget, queue dedup

**Files:**
- Modify: `F:\-SAM-\WWW\samlab.ws_bot\run.py`
- Test: `tests\test_run.py`

**Interfaces:**
- Consumes: Task 6 loop, Task 5 `fetch_entries(..., deadline=)`.
- Produces:
  - `summary["duplicates"]` counts entries dropped because an earlier source already claimed their slug with an `update`/`queue` action.
  - `config.get("budget_seconds", 300)` bounds the run; exhaustion writes `TIME BUDGET EXHAUSTED` lines and increments `errors`.
  - A `queue`/`no-url-change` block is written to `needs-review.txt` once, not once per dry-run.

Why duplicate-source claims only on `update`/`queue`: if kaldata merely says `not-newer` for reaper, softexia's bigger version must still apply — the slug is reserved only when the first source actually acted on it.

Why queue dedup: the spec states that re-examining the feed after the state-key migration «не удвоит очередь, потому что дедупликация dry-run опирается на `needs-review.txt`». The unmatched path already works that way; the queue path did not — every dry-run re-appended the same blocks and re-fetched the article page each time. This task makes the spec true.

- [ ] **Step 1a: Write the duplicate-source tests**

Append:

```python
class TestDuplicateSource:
    def _dup_feeds(self, monkeypatch):
        _fake_feeds(monkeypatch, {
            "https://k/x/feed": [
                _entry("REAPER 7.83 Final", "https://k/x/reaper-1.html", "g1"),
            ],
            "https://www.softexia.com/feed": [
                _entry("REAPER 7.84 Final",
                       "https://www.softexia.com/multimedia/audio-editing/reaper",
                       "g2"),
            ],
        })

    def test_second_source_skips_a_slug_the_first_handled(self, soft_dir, tmp_path,
                                                          monkeypatch):
        config = _two_sources(_config(soft_dir, tmp_path))
        self._dup_feeds(monkeypatch)

        summary = bot.run(config, {}, apply=False)

        assert summary["would_update"] == 1       # only kaldata's
        assert summary["duplicates"] == 1
        assert summary["skipped"] == 1
        assert summary["by_source"]["softexia"]["duplicates"] == 1

    def test_a_not_newer_first_source_does_not_block_the_second(
            self, soft_dir, tmp_path, monkeypatch):
        # kaldata only says "not newer"; it did not act, so it must not
        # reserve the slug against softexia's bigger version
        config = _two_sources(_config(soft_dir, tmp_path))
        _fake_feeds(monkeypatch, {
            "https://k/x/feed": [
                _entry("Foo 1.0 Final", "https://k/x/reaper-1.html", "g1"),
            ],
            "https://www.softexia.com/feed": [
                _entry("REAPER 7.84 Final",
                       "https://www.softexia.com/multimedia/audio-editing/reaper",
                       "g2"),
            ],
        })

        summary = bot.run(config, {}, apply=False)

        assert summary["duplicates"] == 0
        assert summary["would_update"] == 1
```

- [ ] **Step 2a: Run to verify failure, implement, verify pass**

```powershell
& "F:\Meteo\.venv\Scripts\python.exe" -m pytest tests/test_run.py::TestDuplicateSource -v
```

Expected: FAIL (`duplicates` never incremented; softexia would show `would_update` 1 instead).

Implementation in `run()` — add `claimed = set()` after `reported = set()`, and insert directly after `decision = plan_entry(...)` succeeds (before `action = decision["action"]` is read):

```python
            action = decision["action"]
            if action in ("update", "queue"):
                if decision["slug"] in claimed:
                    action = "skip"
                    decision["action"] = "skip"
                    decision["reason"] = "duplicate-source"
                    summary["duplicates"] += 1
                    counters["duplicates"] += 1
                else:
                    claimed.add(decision["slug"])
```

The rewritten action then falls through the normal `if action == "skip"` branch (counted as `skipped`, not actionable, nothing written), and the original `else` write-branch is untouched.

```powershell
& "F:\Meteo\.venv\Scripts\python.exe" -m pytest tests/test_run.py::TestDuplicateSource -v
```

Expected: both pass. Commit:

```powershell
git -C "F:\-SAM-\WWW\samlab.ws_bot" add run.py tests/test_run.py
git -C "F:\-SAM-\WWW\samlab.ws_bot" commit -m "feat: skip a slug an earlier source already handled"
```

- [ ] **Step 3b: Write the time-budget tests**

Append:

```python
class TestTimeBudget:
    def test_exhausted_budget_reports_and_stops(self, soft_dir, tmp_path,
                                                monkeypatch):
        calls = []

        def fetch(url, timeout=30, deadline=None):
            calls.append(url)
            return []

        monkeypatch.setattr(bot.kaldata, "fetch_feed", fetch)
        config = _two_sources(_config(soft_dir, tmp_path))
        config["budget_seconds"] = 0

        summary = bot.run(config, {}, apply=False)

        assert calls == []
        assert summary["errors"] == 2
        assert summary["by_source"]["kaldata"]["errors"] == 1
        assert summary["by_source"]["softexia"]["errors"] == 1
        with open(config["review_path"], encoding="utf-8") as fh:
            assert fh.read().count("TIME BUDGET EXHAUSTED") == 2

    def test_the_second_source_is_skipped_when_the_first_used_the_budget(
            self, soft_dir, tmp_path, monkeypatch):
        config = _two_sources(_config(soft_dir, tmp_path))
        config["budget_seconds"] = 10
        clock = {"now": 0.0}
        monkeypatch.setattr(bot.time, "monotonic", lambda: clock["now"])

        def fetch(url, timeout=30, deadline=None):
            clock["now"] += 100   # the first source ate the whole budget
            return []

        monkeypatch.setattr(bot.kaldata, "fetch_feed", fetch)

        summary = bot.run(config, {}, apply=False)

        assert summary["errors"] == 1
        assert summary["by_source"]["softexia"]["errors"] == 1
        with open(config["review_path"], encoding="utf-8") as fh:
            assert "TIME BUDGET EXHAUSTED: source softexia" in fh.read()
```

- [ ] **Step 4b: Run to verify failure, implement, verify pass**

```powershell
& "F:\Meteo\.venv\Scripts\python.exe" -m pytest tests/test_run.py::TestTimeBudget -v
```

Expected: both FAIL — no `budget_seconds` handling yet, fetch is always attempted.

Implementation in `run()`:

1. Add `import time` to the import block.
2. After `source_list = sources.load_sources(config)` add:

```python
    deadline = time.monotonic() + config.get("budget_seconds", 300)
```

3. Inside the source loop, before the fetch `try`, add:

```python
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            summary["errors"] += 1
            counters["errors"] += 1
            review_lines.append(
                "%s TIME BUDGET EXHAUSTED: source %s was not polled" % (stamp, name)
            )
            continue
```

4. Replace the fetch call:

```python
            entries = sources.fetch_entries(
                source, timeout=min(30, max(1, int(remaining))),
                deadline=deadline,
            )
```

```powershell
& "F:\Meteo\.venv\Scripts\python.exe" -m pytest tests/test_run.py::TestTimeBudget -v
```

Expected: both pass. Commit:

```powershell
git -C "F:\-SAM-\WWW\samlab.ws_bot" add run.py tests/test_run.py
git -C "F:\-SAM-\WWW\samlab.ws_bot" commit -m "feat: bound the whole run by a time budget"
```

- [ ] **Step 5c: Write the queue-dedup tests**

Append:

```python
class TestQueueReportedOnce:
    """The review file is the durable record: a dry-run keeps no state, so
    without the file every dry-run would append the same queue block again."""

    def _force_no_url_change(self, soft_dir):
        # reaper.ini advertises 7.82 but its URL carries no version, so the
        # update cannot be placed and the entry is queued
        with open(os.path.join(soft_dir, "reaper.ini"), "wb") as fh:
            fh.write(b"[info]\r\nname=Foo 7.82\r\n[link_5]\r\n"
                     b"link=https://vendor.example/app.exe\r\n")

    def test_no_url_change_block_is_written_once(self, soft_dir, tmp_path,
                                                 monkeypatch):
        monkeypatch.setattr(bot.kaldata, "fetch_feed", _feed(
            _entry("REAPER 7.83 Final", "https://k/x/reaper-1.html", "g1"),
        ))
        monkeypatch.setattr(bot.kaldata, "fetch_article_links",
                            lambda url, pattern=None, timeout=30:
                            ["https://vendor.example/reaper783.exe"])
        config = _config(soft_dir, tmp_path)
        self._force_no_url_change(soft_dir)

        first = bot.run(config, {}, apply=False)
        second = bot.run(config, {}, apply=False)

        assert first["queued"] == 1
        assert second["queued"] == 1   # still counted, just not re-printed
        with open(config["review_path"], encoding="utf-8") as fh:
            text = fh.read()
        assert text.count("reaper783.exe") == 1
        assert text.count("REAPER 7.83 Final") == 1

    def test_queue_action_block_is_written_once(self, soft_dir, tmp_path,
                                                monkeypatch):
        # aimp.ini only has a Beta track, so plan_entry queues the entry
        monkeypatch.setattr(bot.kaldata, "fetch_feed", _feed(
            _entry("AIMP 5.61 Final", "https://k/x/aimp-1.html", "g1"),
        ))
        monkeypatch.setattr(bot.kaldata, "fetch_article_links",
                            lambda url, pattern=None, timeout=30: [])
        config = _config(soft_dir, tmp_path)

        bot.run(config, {}, apply=False)
        bot.run(config, {}, apply=False)

        with open(config["review_path"], encoding="utf-8") as fh:
            assert fh.read().count("AIMP 5.61 Final") == 1
```

- [ ] **Step 6c: Run to verify failure, implement, verify pass**

```powershell
& "F:\Meteo\.venv\Scripts\python.exe" -m pytest tests/test_run.py::TestQueueReportedOnce -v
```

Expected: both FAIL — the second run appends a second block (counts become 2).

Implementation in `run()` — wrap both review-block writes with the same rule the unmatched path already follows:

`action == "queue"` branch becomes:

```python
            elif action == "queue":
                summary["queued"] += 1
                counters["queued"] += 1
                # the file is the durable record; a repeated dry-run must not
                # append the block (or re-fetch the article page) again
                if decision["title"] not in reported:
                    reported.add(decision["title"])
                    review_lines.extend(
                        _review_block(stamp, decision, entry, config)
                    )
```

the `no-url-change` branch becomes:

```python
                if not result["changed"]:
                    # the version could not be put into the download URLs
                    summary["queued"] += 1
                    counters["queued"] += 1
                    decision["reason"] = "no-url-change"
                    if decision["title"] not in reported:
                        reported.add(decision["title"])
                        review_lines.extend(
                            _review_block(stamp, decision, entry, config)
                        )
```

```powershell
& "F:\Meteo\.venv\Scripts\python.exe" -m pytest -q
```

Expected: full suite all pass. Commit:

```powershell
git -C "F:\-SAM-\WWW\samlab.ws_bot" add run.py tests/test_run.py
git -C "F:\-SAM-\WWW\samlab.ws_bot" commit -m "fix: report a queue entry once, not once per dry-run"
```

---

### Task 8: Config, docs, live verification

**Files:**
- Modify: `F:\-SAM-\WWW\samlab.ws_bot\config.json`
- Modify: `F:\-SAM-\WWW\samlab.ws_bot\RUNBOOK.md`
- Modify: `F:\Meteo\docs\superpowers\specs\2026-10-05-sources-softexia-design.md` (docs repo, Russian)

**Interfaces:**
- Consumes: everything from Tasks 1–7.
- Produces: a config that polls both feeds; a runbook that describes reality; a spec that no longer contradicts the code.

- [ ] **Step 1: Add the sources to `config.json`**

Replace the file:

```json
{
  "soft_dir": "F:/-SAM-/WWW/samlab.ws/soft",
  "feed_url": "https://www.kaldata.com/%D1%81%D0%BE%D1%84%D1%82%D1%83%D0%B5%D1%80/feed",
  "sources": [
    {
      "name": "kaldata",
      "url": "https://www.kaldata.com/%D1%81%D0%BE%D1%84%D1%82%D1%83%D0%B5%D1%80/feed",
      "profile": "kaldata"
    },
    {
      "name": "softexia",
      "url": "https://www.softexia.com/feed",
      "profile": "softexia"
    }
  ],
  "budget_seconds": 300,
  "review_path": "F:/-SAM-/WWW/samlab.ws_bot/needs-review.txt",
  "state_path": "F:/-SAM-/WWW/samlab.ws_bot/state.json",
  "review_link_pattern": "\\.(exe|msi|zip|7z|rar|dmg|tgz|deb)$"
}
```

`feed_url` stays (smoke test + fallback). `soft_dir`/`review_path`/`state_path` stay exactly as they are.

- [ ] **Step 2: Full strict suite**

```powershell
& "F:\Meteo\.venv\Scripts\python.exe" -m pytest -q -W error
```

Expected: all pass, zero warnings.

- [ ] **Step 3: Confirm no stale state**

```powershell
Test-Path "F:\-SAM-\WWW\samlab.ws_bot\state.json"
```

Expected: `False` (a dry-run never creates it; it is `.gitignore`d). If `True`, delete it — the state keys changed from bare guids to `source:link`, and the old keys would re-process everything anyway with no benefit. The server never ran `--apply`, so there is nothing to migrate there either.

- [ ] **Step 4: Live dry-run**

```powershell
& "F:\Meteo\.venv\Scripts\python.exe" run.py --config config.json
```

(run from `F:\-SAM-\WWW\samlab.ws_bot`; network-bound, can take up to a minute; kaldata retries — rerun once if `errors=1` from a transient feed failure.)

Expected:
- `seen=71 new=71` (50 kaldata + 21 softexia; no state file exists);
- three lines: flat `[DRY-RUN] ... duplicates=N errors=0`, then `  kaldata: ...` and `  softexia: ...`;
- softexia line shows ~21 seen with unmatched entries in the 10–15 range (12 hyphenated slugs never match — expected cost of coverage, fixed later by aliases);
- spec cross-check: softexia yields 18 titles with a version + 3 honest `no-version` skips; 4 two-version titles (XYplorer, LibreOffice, Advanced Renamer, Vivaldi) become normal outcomes instead of `two-versions`. Deviations are worth noting in the final report, not blocking.

Verify nothing was written:

```powershell
(Get-ChildItem "F:\-SAM-\WWW\samlab.ws\soft\*.bak" -ErrorAction SilentlyContinue | Measure-Object).Count
(Get-ChildItem "F:\-SAM-\WWW\samlab.ws\soft\*.tmp" -ErrorAction SilentlyContinue | Measure-Object).Count
Test-Path "F:\-SAM-\WWW\samlab.ws_bot\state.json"
```

Expected: `0`, `0`, `False`.

Inspect the review file (no `tail` on this machine — use `-Tail`):

```powershell
Get-Content "F:\-SAM-\WWW\samlab.ws_bot\needs-review.txt" -Tail 60
```

Expected: softexia blocks present (titles cut at the dash, e.g. `REAPER 7.82`, never the `– Digital Audio…` tail), source links under `suggestions (NOT written to the ini):`, usable alias keys like `'rustdesk': <slug>`, and no duplicated blocks from earlier dry-runs.

- [ ] **Step 5: Fix the spec's stale claims (docs repo)**

In `F:\Meteo\docs\superpowers\specs\2026-10-05-sources-softexia-design.md`:

1. In «Чего не делаем» replace:

   `- Не меняем \`plan_entry\`, \`find_match\`, \`is_ambiguous\`, \`iniwrite\`.`

   with:

   `- Не меняем логику \`find_match\`, \`is_ambiguous\`, \`iniwrite\`. \`plan_entry\` получает параметр \`profile\` (словарь prepare/pick/multi/channel); без профиля он работает как раньше, поведение kaldata не меняется.`

   (The plan needed profiles — the spec's original «не меняем plan_entry» became false the moment softexia needed a different pick rule.)

2. In the `match.py` test list replace:

   `- гибрид \`foo-bar-2\` не срезается, как и раньше.`

   with:

   `- хвост \`-<digits>\` срезается, дефисы slug остаются (\`foo-bar-2\` → \`foo-bar\`), слитные цифры сохраняются (\`foo-bar2\`).`

   (Measured: the tail IS stripped; what survives is the slug's own hyphens.)

```powershell
git -C "F:\Meteo" add docs/superpowers/specs/2026-10-05-sources-softexia-design.md
git -C "F:\Meteo" commit -m "Правка спеки: plan_entry получает параметр профиля, slug-хвост как в коде"
```

- [ ] **Step 6: Update `RUNBOOK.md`**

Replace the intro (lines 3–5):

```markdown
Polls the kaldata and softexia software feeds, bumps the Final-track version
in our own `soft/*.ini` files, and sends everything it cannot handle to
`needs-review.txt` instead of guessing.
```

Add to «What it will never do», after the downgrade bullet:

```markdown
- Use a download link from either feed. The `suggestions` lines in
  `needs-review.txt` are for a human to read; only our own URLs are ever
  written, because a source's link can point at an older build than its own
  title claims (measured: softexia's vivaldi `.x64.exe` is three patches
  behind).
```

Replace the «First run» output block (lines 26–30) with the flat line **plus the two source lines, using the real numbers from Step 4** (format, values pasted from the actual run):

```markdown
Output is a flat line plus one line per source:

```
<the three lines exactly as Step 4 printed them>
```
```

Add a new section «## Sources» after «Aliases»:

```markdown
## Sources

`config.json` lists the feeds in polling order:

```json
"sources": [
  {"name": "kaldata",  "url": "https://www.kaldata.com/.../feed", "profile": "kaldata"},
  {"name": "softexia", "url": "https://www.softexia.com/feed",    "profile": "softexia"}
],
"budget_seconds": 300
```

- A config without `sources` falls back to `feed_url` as a single kaldata
  source, so the old config keeps working.
- A `profile` is the four rules in `sources.py` / `softexia.py`:
  kaldata takes the FIRST version in the title and refuses two-version
  titles; softexia cuts the advertising tail at the first spaced dash and
  takes the BIGGEST Final-track version. An unknown profile name aborts the
  run with `ValueError`.
- kaldata goes first. When both feeds carry the same program, the entry that
  acts second (update or queue) is dropped with reason `duplicate-source`;
  the `duplicates` counter says how many. A first source that only reports
  "not newer" does NOT reserve the slug, so the other feed's bigger version
  still applies.
- `budget_seconds` bounds the whole run: every source gets what time is
  left, the retry loop inside `kaldata.fetch` honours the same deadline, and
  an exhausted budget is reported as `TIME BUDGET EXHAUSTED` instead of
  retrying for minutes.
- The state key is `source:link` — softexia's `<guid>` points at a foreign
  domain and cannot be trusted. Changing `sources` therefore makes an old
  `state.json` stale: delete it, expect one run with `new=` equal to the
  total feed size (71 today), then `new=0`.
```

In «Notes on the site», add a bullet after the kaldata one:

```markdown
- softexia's `/feed` answers but also truncates intermittently; `/rss` drops
  the connection. It shares kaldata's retry loop, which is why the run has a
  `budget_seconds` ceiling: two dead feeds must not hold cron for ten
  minutes.
```

- [ ] **Step 7: Final suite and commits**

```powershell
& "F:\Meteo\.venv\Scripts\python.exe" -m pytest -q -W error
git -C "F:\-SAM-\WWW\samlab.ws_bot" add config.json
git -C "F:\-SAM-\WWW\samlab.ws_bot" commit -m "feat: enable the softexia feed in the config"
git -C "F:\-SAM-\WWW\samlab.ws_bot" add RUNBOOK.md
git -C "F:\-SAM-\WWW\samlab.ws_bot" commit -m "docs: runbook for two sources, budgets and duplicate slugs"
```

Expected: all tests pass; both bot commits created; docs commit from Step 5 already created.

---

## Self-review notes (checked while writing)

- **Spec coverage:** markers in three places → Task 1; `softexia.py` trim/pick table → Task 2; «один корень, два профиля» + kaldata unchanged → Task 3; registry + fallback → Task 4; budget → Tasks 5+7; state key → Tasks 4+6; duplicates → Task 7; `by_source` → Task 6; source failure isolation → Task 6; links only to the report → untouched existing path (`_review_block`), re-verified by `test_queue_entry_appended`; aliases untouched; «не меняем plan_entry» → corrected in Task 8.
- **Type consistency:** `PROFILE` four-key shape identical in `kaldata.py`/`softexia.py`; `load_sources` output dict consumed by `fetch_entries` and `run`; `plan_entry(profile=)` used everywhere by name, never positionally, except the historical 5-positional spy which Task 6 re-signatures.
- **Out of order risks:** Task 2's Vivaldi/Greenshot pick tests need Task 1 (called out in Task 2 Step 4). Everything else is independent.
