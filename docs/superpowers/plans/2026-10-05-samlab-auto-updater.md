# SamLab.ws Version Updater — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a bot that polls kaldata.com's software RSS feed every 6 hours, detects new Final versions of programs already in `soft/*.ini`, and rewrites the version plus download URLs in place.

**Architecture:** Python 3 stdlib only, no third-party dependencies (shared hosting may have none). The bot lives outside the web root and edits `.ini` files in place. Pipeline: fetch RSS → match to `.ini` → compare versions → substitute version into existing URLs → write atomically. Anything that cannot be updated safely goes to a review queue instead of being written.

**Tech Stack:** Python 3.6+, `xml.etree.ElementTree`, `urllib.request`, `re`, `pathlib`, `json`, `configparser` (not used — INI written by hand), `pytest` for local dev only.

**Local test interpreter:** `F:\Meteo\.venv\Scripts\python.exe`. The system
`python` on this machine has no `pytest`, so every `python -m pytest` command below
means that interpreter. Run it from the bot directory so the modules import.

## Global Constraints

- **Encoding:** all `.ini` files are **windows-1251**. Read and write bytes through `cp1251`, never UTF-8. Verified: decoding `aimp.ini` as UTF-8 yields 69 replacement chars, as cp1251 yields 0.
- **Line endings:** preserve `\r\n` exactly as found. Do not normalize.
- **Do not touch** sections named `[linkN]` / `[link1]` (no underscore) — these are intentionally hidden reserves, excluded by the site's `full.tpl` which matches only `~^link_~`. Only `[link_N]` with underscore is rendered and only `[link_N]` is rewritten.
- **Do not touch** `[warez_best]`, `.short`, `.long`, or any screenshot files.
- **Section naming:** any new link section written must be `link_N` with underscore, otherwise the site template will not render it.
- **Version rollback is forbidden:** if kaldata's version ≤ our version, skip. Never downgrade.
- **Match threshold:** both the normalized title and the candidate slug must be ≥ 5 characters for a containment match. Shorter is rejected to avoid false positives (`aimp` must not match `aimpfoo`).
- **Marker before a version does not bind:** only a marker in the window after a version and before the next one classifies it. This keeps `BetaClock (AlfaClock2) 1.0.17.517`, `FinalBurner 2.24.0.195` and `Final Uninstaller 2.69` (real stable releases whose names start with a marker word) updatable. The cost is that a marker glued to the front of a name is not recognised: `Dev-C++ 4.9.9.8` classifies as Final and `normalize()` reduces it to `"c"`, which the `MIN_MATCH_LEN` floor then refuses. No catalog entry is affected.
- **Ambiguity is refusal:** if two candidate slugs tie for longest, treat as no match and log it.
- **Dry-run is the default:** without an explicit `--apply` flag, no `.ini` file is modified.
- **Safety net:** every modified `.ini` gets a `.ini.bak` copy, then is written to a temp file and atomically renamed.
- **Banned content:** skip titles whose word starts with `Crack`, `Keygen` or `REPACK` (case-insensitive), so `Crack`, `Cracked`, `Cracking`, `Keygen`, `Keygens`, `REPACK` and `Repacked` are all filtered.
- **Two-version titles:** skip titles containing `/` between two versions (e.g. `Advanced Renamer 4.27 / 3.95 Final`).
- **Final track only:** Dev/Beta/Alpha/RC/Portable tracks are parsed and modeled but never updated from kaldata. A version belongs to the last channel marker that follows it and starts before the next version; a version with no marker in that window is Final.
- **Empty HTTP response:** kaldata sometimes returns 0 bytes. Treat empty body as failure, not as an empty feed.

## File Structure

Development happens at `F:\-SAM-\WWW\samlab.ws_bot\`, mirroring the server path
`/home/<user>/samlab.ws_bot/`. It sits next to the site root `samlab.ws\`, never
inside it, so nothing the bot writes can be served over HTTP.

```
F:\-SAM-\WWW\samlab.ws_bot\
  version.py         parse/compare versions, detect channel, extract Final track
  match.py           normalize titles, find our .ini by slug or name
  iniwrite.py        read cp1251, rewrite name= and link= in [link_N] only, atomic write
  kaldata.py         fetch RSS, parse items, fetch article page for review queue
  run.py             CLI entry point, orchestration, reporting
  config.json        soft_dir, feed_url, review_path, state_path
  aliases.json       manual slug overrides
  state.json         seen guids (created at runtime)
  needs-review.txt   manual-work queue (created at runtime)
  tests\
    test_version.py
    test_match.py
    test_iniwrite.py
    test_kaldata.py
    test_run.py
  fixtures\          real .ini samples captured from soft/ (created in Task 1)
```

Module dependency order is strictly one-directional: `version` ← `match` ← `iniwrite` ← `kaldata` ← `run`.

---

### Task 1: Project scaffold and fixtures

**Files:**
- Create: `F:\-SAM-\WWW\samlab.ws_bot\config.json`
- Create: `F:\-SAM-\WWW\samlab.ws_bot\aliases.json`
- Create: `F:\-SAM-\WWW\samlab.ws_bot\tests\test_smoke.py`
- Create: `F:\-SAM-\WWW\samlab.ws_bot\fixtures\reaper.ini` (captured from live `soft/`)
- Create: `F:\-SAM-\WWW\samlab.ws_bot\fixtures\vivaldi.ini` (captured from live `soft/`)

**Interfaces:**
- Consumes: nothing.
- Produces: `config.json` with keys `soft_dir`, `feed_url`, `review_path`, `state_path`. `fixtures/` directory holding two real `.ini` files for later tests.

- [ ] **Step 1: Create the project directory and config**

```powershell
New-Item -ItemType Directory -Force -Path "F:\-SAM-\WWW\samlab.ws_bot" | Out-Null
New-Item -ItemType Directory -Force -Path "F:\-SAM-\WWW\samlab.ws_bot\tests" | Out-Null
New-Item -ItemType Directory -Force -Path "F:\-SAM-\WWW\samlab.ws_bot\fixtures" | Out-Null
```

- [ ] **Step 2: Write `config.json`**

```json
{
  "soft_dir": "F:/-SAM-/WWW/samlab.ws/soft",
  "feed_url": "https://www.kaldata.com/%D1%81%D0%BE%D1%84%D1%82%D1%83%D0%B5%D1%80/feed",
  "review_path": "F:/-SAM-/WWW/samlab.ws_bot/needs-review.txt",
  "state_path": "F:/-SAM-/WWW/samlab.ws_bot/state.json",
  "review_link_pattern": "\\.(exe|msi|zip|7z|rar|dmg|tgz|deb)$"
}
```

On the server, `soft_dir` becomes the absolute path to the site's `soft/` directory and `review_path`/`state_path` become paths next to the bot.

Write this file as plain UTF-8 **without a BOM**. Windows PowerShell 5.1's
`Set-Content -Encoding UTF8` adds one; the readers tolerate it anyway
(`encoding="utf-8-sig"`), but a BOM-free file is the cleaner default.

- [ ] **Step 3: Write `aliases.json`**

Empty object to start — entries are added as the review queue reveals real mismatches.

```json
{}
```

- [ ] **Step 4: Capture two real `.ini` files as fixtures**

These are byte-for-byte copies so tests exercise genuine formatting, including the `\r\n` line endings and cp1251 bytes.

```powershell
Copy-Item "F:\-SAM-\WWW\samlab.ws\soft\reaper.ini"   "F:\-SAM-\WWW\samlab.ws_bot\fixtures\reaper.ini"
Copy-Item "F:\-SAM-\WWW\samlab.ws\soft\vivaldi.ini"  "F:\-SAM-\WWW\samlab.ws_bot\fixtures\vivaldi.ini"
```

- [ ] **Step 5: Verify fixtures decode as cp1251 and contain CRLF**

Run:
```powershell
python -c "b=open(r'F:\-SAM-\WWW\samlab.ws_bot\fixtures\reaper.ini','rb').read(); print('crlf',b.count(b'\r\n')); print('bad-utf8', b.decode('utf-8',errors='replace').count('\ufffd')); print('bad-cp1251', b.decode('cp1251',errors='replace').count('\ufffd'))"
```
Expected: `crlf` greater than 0, `bad-utf8` greater than 0 (proving it is not UTF-8), `bad-cp1251` exactly 0.

- [ ] **Step 6: Write the smoke test**

`F:\-SAM-\WWW\samlab.ws_bot\tests\test_smoke.py`

```python
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent


def test_config_has_required_keys():
    config = json.loads((ROOT / "config.json").read_text(encoding="utf-8-sig"))
    for key in ("soft_dir", "feed_url", "review_path", "state_path"):
        assert key in config, key


def test_aliases_is_an_object():
    aliases = json.loads((ROOT / "aliases.json").read_text(encoding="utf-8-sig"))
    assert isinstance(aliases, dict)


def test_fixtures_are_cp1251_with_crlf():
    for name in ("reaper.ini", "vivaldi.ini"):
        raw = (ROOT / "fixtures" / name).read_bytes()
        assert b"\r\n" in raw, name
        assert raw.decode("cp1251")
        assert "\ufffd" not in raw.decode("cp1251", errors="replace"), name
```

- [ ] **Step 7: Run the test**

Run: `cd F:\-SAM-\WWW\samlab.ws_bot; python -m pytest tests/test_smoke.py -v`
Expected: 3 passed.

- [ ] **Step 8: Initialize version control**

```powershell
cd F:\-SAM-\WWW\samlab.ws_bot
git init
git add config.json aliases.json tests fixtures .gitignore
git commit -m "chore: scaffold bot project with cp1251 ini fixtures"
```

`.gitignore` contents:
```
__pycache__/
*.pyc
state.json
needs-review.txt
cron.log
*.bak
soft-backup-*/
```

---

### Task 2: Version parsing and comparison

**Files:**
- Create: `F:\-SAM-\WWW\samlab.ws_bot\version.py`
- Create: `F:\-SAM-\WWW\samlab.ws_bot\tests\test_version.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `VERSION_RE` — compiled regex matching a dotted version cluster.
  - `CHANNEL_RE` — compiled regex matching a channel marker word with optional attached digits (`"RC2"`, `"Beta 3"`, `"beta3"`).
  - `classify_channel(word) -> str` returns `"final"` or `"beta"` for one marker word; anything outside `NON_FINAL_MARKERS` is Final.
  - `version_tracks(text) -> list[tuple[str, str]]` returns `(version, channel)` for every version cluster. A version owns the window from its end to the next version's start and takes the **last** channel marker in that window; an empty window means Final.
  - `split_channel(text) -> (str, str)` returns `(text_without_markers, channel)` where channel is the channel of the first version cluster, or the first marker's channel for a title with no version. Channel is only ever `"final"` or `"beta"`.
  - `find_versions(text) -> list[tuple[int, int]]` returns `(start, end)` offsets of each version cluster, in order of appearance.
  - `version_tuple(vstr) -> tuple[int, ...]` converts `"8.2.4133.83"` to `(8, 2, 4133, 83)`; raises `ValueError` on anything that is not a version cluster.
  - `is_newer(new, old) -> bool` returns True only when `new > old` numerically, and False when either side is unparsable.
  - `has_slash_versions(text) -> bool`
  - `has_banned_words(text) -> bool`
  - `final_track_version(ini_name) -> str or None` extracts the Final-track version from our own `name=` value.

- **Version ↔ channel pairing (binding for Tasks 2, 3, 6):** a version belongs to the **last** channel marker that follows it and starts before the next version; a version with no marker in that window is Final. This is what makes `"Vivaldi 8.3.4175.3 Dev + 8.2.4133.83 Final"` and the space-separated `"Foo 1.0 Dev 8.2 Final"` resolve the same way, and it keeps `"3.9.21 Stable Beta"` out because the trailing `Beta` overrides the earlier `Stable`. Never bind a version to a marker that precedes it, and never let a Final marker win over a later non-Final one.

- [ ] **Step 1: Write the failing tests**

`F:\-SAM-\WWW\samlab.ws_bot\tests\test_version.py`

```python
import version


class TestSplitChannel:
    def test_final_marker(self):
        text, channel = version.split_channel("REAPER 7.82 Final")
        assert channel == "final"
        assert "Final" not in text

    def test_stable_marker(self):
        _, channel = version.split_channel("Microsoft Edge 154.0.4258.53 Stable")
        assert channel == "final"

    def test_beta_marker(self):
        text, channel = version.split_channel("Mozilla Firefox 158.0 Beta 3")
        assert channel == "beta"
        assert "Beta" not in text

    def test_no_marker_is_final(self):
        _, channel = version.split_channel("Google Chrome 154.0.8037.98")
        assert channel == "final"

    def test_dev_marker(self):
        _, channel = version.split_channel("Vivaldi 8.3.4175.3 Dev")
        assert channel == "beta"

    def test_attached_number_marker(self):
        # real catalog titles: "RC2", "RC34", "Beta3" - no space before the number
        assert version.split_channel("RAMDisk 4.4.0 RC34")[1] == "beta"
        assert version.split_channel("DUTraffic 1.5.36 RC2")[1] == "beta"
        assert version.split_channel("Foo 1.0 Beta3")[1] == "beta"
        assert version.split_channel("Foo 1.0 Alpha2")[1] == "beta"
        assert version.split_channel("Foo 1.0 Dev2")[1] == "beta"

    def test_attached_number_final_marker(self):
        # "final" is also the no-marker default, so pin the marker as consumed
        text, channel = version.split_channel("Shark007 Codecs 20.9.4 Final2")
        assert channel == "final"
        assert "Final2" not in text

    def test_portable_is_not_updatable(self):
        # a portable build lives at a different URL, so its name must not be
        # rewritten to the plain Final version
        assert version.split_channel("Foo 1.0 Portable")[1] == "beta"

    def test_marker_only_title(self):
        assert version.split_channel("Foo Beta")[1] == "beta"

    def test_two_tracks_report_first(self):
        # "Vivaldi 8.3.4175.3 Dev + 8.2.4133.83 Final" - reporting the Final
        # side would let the bot write a Dev-track version into the file
        assert version.split_channel("Vivaldi 8.3.4175.3 Dev + 8.2.4133.83 Final")[1] == "beta"

    def test_trailing_non_final_marker_wins(self):
        # real catalog title: "Stable" must not rescue the "Beta" that follows
        assert version.split_channel("Drivers BackUp Solution 3.9.21 Stable Beta")[1] == "beta"

    def test_marker_word_prefix_is_not_a_marker(self):
        # "Device" starts with "dev" but is not a channel marker
        text, channel = version.split_channel("Unknown Device Identifier 9.01")
        assert channel == "final"
        assert "Device" in text


class TestVersionTracks:
    def test_marker_binds_to_version_in_front(self):
        tracks = version.version_tracks("Foo 1.0 Dev + 8.2 Final")
        assert tracks == [("1.0", "beta"), ("8.2", "final")]

    def test_no_marker_is_final(self):
        assert version.version_tracks("REAPER 7.82") == [("7.82", "final")]

    def test_second_version_without_marker(self):
        assert version.version_tracks("Foo 2.0 Beta + 3.0") == [("2.0", "beta"), ("3.0", "final")]

    def test_marker_after_own_version_only(self):
        # "Dev" must not leak across a version boundary into the next track
        assert version.version_tracks("Foo 1.0 Dev + 8.2") == [("1.0", "beta"), ("8.2", "final")]

    def test_last_marker_in_window_wins(self):
        assert version.version_tracks("Foo 3.9.21 Stable Beta") == [("3.9.21", "beta")]

    def test_trailing_marker_after_final_does_not_reclassify(self):
        # real title: a "Beta" that follows the last version belongs to it
        assert version.version_tracks("Drivers BackUp Solution 3.9.21 Stable Beta") == [
            ("3.9.21", "beta")
        ]


class TestClassifyChannel:
    def test_final_markers(self):
        for word in ("final", "stable", "release", "Final", "STABLE"):
            assert version.classify_channel(word) == "final"

    def test_non_final_markers(self):
        # classify_channel only ever sees a bare marker word: CHANNEL_RE keeps
        # the trailing digits out of group(1)
        for word in ("beta", "alpha", "dev", "nightly", "rc", "portable", "RC"):
            assert version.classify_channel(word) == "beta"


class TestFindVersions:
    def test_simple(self):
        offsets = version.find_versions("REAPER 7.82")
        assert [version.version_tuple("REAPER 7.82"[a:b]) for a, b in offsets] == [(7, 82)]

    def test_four_part(self):
        offsets = version.find_versions("Google Chrome 154.0.8037.98")
        assert [version.version_tuple("Google Chrome 154.0.8037.98"[a:b]) for a, b in offsets] == [(154, 0, 8037, 98)]

    def test_no_separator_number_is_ignored(self):
        # "V282" and "Photoshop" style tokens must not be treated as versions
        offsets = version.find_versions("FanControl V282")
        assert offsets == []

    def test_multiple_versions(self):
        text = "Vivaldi 8.3.4175.3 Dev + 8.2.4133.83 Final"
        found = [version.version_tuple(text[a:b]) for a, b in version.find_versions(text)]
        assert found == [(8, 3, 4175, 3), (8, 2, 4133, 83)]


class TestVersionTuple:
    def test_two_parts(self):
        assert version.version_tuple("7.82") == (7, 82)

    def test_four_parts(self):
        assert version.version_tuple("8.2.4133.83") == (8, 2, 4133, 83)

    def test_dash_and_underscore_separators(self):
        assert version.version_tuple("8-2-4133-83") == (8, 2, 4133, 83)
        assert version.version_tuple("8_2_4133_83") == (8, 2, 4133, 83)


class TestIsNewer:
    def test_newer_patch(self):
        assert version.is_newer("7.83", "7.82") is True

    def test_not_newer_double_digit(self):
        # the classic bug: naive string compare says "9.9" > "10.0"
        assert version.is_newer("10.0", "9.9") is True
        assert version.is_newer("9.9", "10.0") is False

    def test_equal_is_not_newer(self):
        assert version.is_newer("7.82", "7.82") is False

    def test_rollback_rejected(self):
        assert version.is_newer("7.81", "7.82") is False

    def test_shorter_prefix_is_not_newer(self):
        assert version.is_newer("8.2", "8.2.4133.83") is False
        assert version.is_newer("8.2.4133.83", "8.2") is True

    def test_unparsable_never_counts_as_upgrade(self):
        # a malformed kaldata title must not be able to abort a batch run
        assert version.is_newer("abc", "1.0") is False
        assert version.is_newer("1.0", "abc") is False
        assert version.is_newer("", "1.0") is False
        assert version.is_newer("1.0", "8.2.") is False


class TestGuards:
    def test_slash_two_versions(self):
        assert version.has_slash_versions("Advanced Renamer 4.27 / 3.95 Final") is True

    def test_slash_not_a_separator(self):
        assert version.has_slash_versions("a/b tool 1.0") is False

    def test_banned_crack(self):
        assert version.has_banned_words("Foo 1.0 Crack") is True

    def test_banned_repack(self):
        assert version.has_banned_words("Foo 1.0 REPACK") is True

    def test_banned_keygen(self):
        assert version.has_banned_words("Foo 1.0 Keygen") is True

    def test_clean_title(self):
        assert version.has_banned_words("REAPER 7.82 Final") is False

    def test_banned_inflections(self):
        assert version.has_banned_words("Foo 1.0 Cracked") is True
        assert version.has_banned_words("Foo 1.0 Cracking") is True
        assert version.has_banned_words("Foo 1.0 Repacked") is True
        assert version.has_banned_words("Foo 1.0 Keygens") is True
        assert version.has_banned_words("Crack_foo 1.0") is True

    def test_slash_with_v_prefix(self):
        assert version.has_slash_versions("Foo v1.0 / v2.0") is True


class TestFinalTrack:
    def test_plain_name(self):
        assert version.final_track_version("REAPER 7.82") == "7.82"

    def test_dual_track_takes_final(self):
        name = "Vivaldi 8.3.4175.3 Dev + 8.2.4133.83 Final"
        assert version.final_track_version(name) == "8.2.4133.83"

    def test_dev_only_returns_none(self):
        # nothing on the Final track -> bot must not touch it
        assert version.final_track_version("Sumatra PDF 3.7.22641 Dev") is None

    def test_final_on_the_left(self):
        # the side order is not a guarantee: the Final track may sit first
        assert version.final_track_version("Foo 1.0 Final + 2.0 Dev") == "1.0"

    def test_multi_segment_takes_first_track(self):
        # the first track is the primary one, not the last segment: rsplit("+")
        # would answer "5.23" here and defeat the rollback guard
        name = "Realtek LAN Driver 11.23 W11 + 10.68 W10 + 8.69 W8.x + 7.62 W7 + 5.23 XP"
        assert version.final_track_version(name) == "11.23"

    def test_multi_segment_never_returns_a_later_track(self):
        # pinned so nobody reintroduces a "newest track wins" heuristic: an
        # earlier Final track wins even when a later track has a bigger number
        assert version.final_track_version("Foo 1.0 Final + 9.9") == "1.0"

    def test_right_side_without_version(self):
        # the "Rus" translation tag must not hide the Final version
        assert version.final_track_version("Becky Internet Mail 2.83.03 + Rus") == "2.83.03"

    def test_plus_in_product_name(self):
        assert version.final_track_version("Notepad++ 8.9.8.1") == "8.9.8.1"

    def test_beta_name_containing_plus(self):
        assert version.final_track_version("Notepad++ 8.9.8.1 Beta") is None
        assert version.final_track_version("MemTest86+ 8.10 Beta") is None

    def test_space_separated_two_tracks(self):
        assert version.final_track_version("Foo 1.0 Dev 8.2 Final") == "8.2"

    def test_release_candidate_is_not_final(self):
        assert version.final_track_version("DUTraffic 1.5.36 RC2") is None
        assert version.final_track_version("VideoMach 6.00 RC1") is None
        assert version.final_track_version("Avira AntiVirus 2014 v14.0.0.383 RC2") is None

    def test_stable_then_beta_is_not_final(self):
        # real dbs.ini name; a "Stable" before the "Beta" must not rescue it
        assert version.final_track_version("Drivers BackUp Solution 3.9.21 Stable Beta") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd F:\-SAM-\WWW\samlab.ws_bot; python -m pytest tests/test_version.py -v`
Expected: collection error, `ModuleNotFoundError: No module named 'version'`.

- [ ] **Step 3: Implement `version.py`**

```python
"""Version parsing and comparison for the samlab.ws updater.

Pure functions only: no I/O, no network, no filesystem. Every behaviour in this
module is exercised by tests/test_version.py.
"""

import re

# A version cluster is digits separated by dots/dashes/underscores, and must
# contain at least one separator. That excludes bare numbers such as "V282"
# and stray years inside program names.
VERSION_RE = re.compile(r"\d+(?:[.\-_]\d+)+")

# Marker words that classify the release channel. The digits are consumed but
# kept out of group(1), so "RC2", "RC34", "Beta 3" and "beta3" all classify the
# same way as the bare word. The trailing guard rejects a marker that is only a
# prefix of a longer word, which keeps "Device" and "StableFish" intact; it also
# still binds after a hyphen, as in "1.0.0.115-RC1".
CHANNEL_RE = re.compile(
    r"(?<!\w)(final|stable|release|beta|alpha|dev|nightly|rc|portable)\s*\d*(?!\w)",
    re.IGNORECASE,
)

# "portable" sits here on purpose: a portable build is published at a different
# URL, so rewriting its name to the plain Final version would point the file at
# the wrong download. Such entries go to the review queue instead.
NON_FINAL_MARKERS = {"beta", "alpha", "dev", "nightly", "rc", "portable"}

BANNED_RE = re.compile(r"\b(crack|keygen|repack)\w*", re.IGNORECASE)

# Matches "12 / 34" and "v1.0 / v2.0" but not "and/or": require a digit on both
# sides of the slash.
SLASH_VERSIONS_RE = re.compile(r"\d\s*/\s*v?\d")


def classify_channel(word):
    """Map one marker word to ``"final"`` or ``"beta"``.

    Only ``NON_FINAL_MARKERS`` is enumerated; every other marker word counts as
    Final, because that keeps the two marker sets from having to stay in sync as
    words are added and because a version with no marker at all is a plain
    stable release.
    """
    return "beta" if word.lower() in NON_FINAL_MARKERS else "final"


def find_versions(text):
    """Return ``[(start, end), ...]`` offsets of every version cluster."""
    return [m.span() for m in VERSION_RE.finditer(text)]


def version_tracks(text):
    """Return ``[(version, channel), ...]``, one entry per version cluster.

    A version owns the window that runs from its end to the start of the next
    version, and it takes the LAST marker in that window. Both real title shapes
    resolve the same way::

        "Foo 1.0 Dev + 8.2 Final"  ->  [("1.0", "beta"), ("8.2", "final")]
        "Foo 1.0 Dev 8.2 Final"    ->  [("1.0", "beta"), ("8.2", "final")]

    Taking the last marker is what keeps the real
    ``"Drivers BackUp Solution 3.9.21 Stable Beta"`` out: the trailing ``Beta``
    belongs to that version, so the earlier ``Stable`` cannot rescue it. A
    version with an empty window is Final, so plain titles need no ceremony and a
    multi-track name answers with its first Final track rather than with
    whichever side happens to come last.
    """
    spans = find_versions(text)
    markers = [(m.start(), m.group(1)) for m in CHANNEL_RE.finditer(text)]
    tracks = []
    for index, (start, end) in enumerate(spans):
        limit = spans[index + 1][0] if index + 1 < len(spans) else len(text)
        channel = "final"
        for marker_start, word in markers:
            if end <= marker_start < limit:
                channel = classify_channel(word)
        tracks.append((text[start:end], channel))
    return tracks


def split_channel(text):
    """Strip channel marker words and report the channel of the first track.

    Returns ``(text_without_markers, channel)`` where channel is ``"final"`` or
    ``"beta"``. For a title carrying several tracks the first one decides, so
    ``"Vivaldi 8.3.4175.3 Dev + 8.2.4133.83 Final"`` is reported as beta and the
    entry is left alone.
    """
    tracks = version_tracks(text)
    if tracks:
        channel = tracks[0][1]
    else:
        marker = CHANNEL_RE.search(text)
        channel = classify_channel(marker.group(1)) if marker else "final"
    return CHANNEL_RE.sub(" ", text), channel


def version_tuple(vstr):
    """Convert a version string to a tuple of ints for numeric comparison.

    ``"8.2.4133.83"`` -> ``(8, 2, 4133, 83)``. Separators may be dots,
    dashes or underscores. Raises ``ValueError`` on anything that is not a
    version cluster, so feed it ``find_versions`` output.
    """
    return tuple(int(part) for part in re.split(r"[.\-_]+", vstr.strip()))


def is_newer(new, old):
    """True only when ``new`` is strictly newer than ``old``.

    Rollback and equality both return False, and unparsable input returns False
    as well, so a malformed title can never look like an upgrade. Tuple
    comparison makes ``"10.0"`` newer than ``"9.9"``, which a string comparison
    gets wrong, and makes a shorter tuple never newer than a longer one that
    shares its prefix.
    """
    try:
        return version_tuple(new) > version_tuple(old)
    except ValueError:
        return False


def has_slash_versions(text):
    """True for titles like "Advanced Renamer 4.27 / 3.95 Final"."""
    return SLASH_VERSIONS_RE.search(text) is not None


def has_banned_words(text):
    """True when the title advertises cracks/keygens/repacks.

    Inflected forms carry the same warning, so the pattern takes a word
    prefix: "Cracked", "Cracking", "Repacked" and "Keygens" all count.
    """
    return BANNED_RE.search(text) is not None


def final_track_version(ini_name):
    """Extract the Final-track version from our own ``name=`` value.

    Our files sometimes carry several tracks at once, e.g.
    ``"Vivaldi 8.3.4175.3 Dev + 8.2.4133.83 Final"``. Only the Final side may
    ever be updated, so each version takes the last channel marker before the
    next version (see ``version_tracks``) and the first Final one is returned,
    whichever side of a ``+`` it happens to sit on. Returns ``None`` when no
    track is Final, which is the signal for the caller to skip the entry
    entirely.
    """
    for vstr, channel in version_tracks(ini_name):
        if channel == "final":
            return vstr
    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd F:\-SAM-\WWW\samlab.ws_bot; python -m pytest tests/test_version.py -v`
Expected: all passed.

- [ ] **Step 5: Commit**

```powershell
cd F:\-SAM-\WWW\samlab.ws_bot
git add version.py tests/test_version.py
git commit -m "feat: version parsing, channel detection and numeric comparison"
```

---

### Task 3: Matching kaldata titles to our .ini files

**Files:**
- Create: `F:\-SAM-\WWW\samlab.ws_bot\match.py`
- Create: `F:\-SAM-\WWW\samlab.ws_bot\tests\test_match.py`

**Interfaces:**
- Consumes: `version` (Task 2).
- Produces:
  - `normalize(text) -> str` lowercases, strips trailing channel markers, strips version clusters, removes the trailing `- SamLab.ws ...` decoration, and removes every non-alphanumeric character.
  - `slug_from_link(url) -> str` extracts the slug from a kaldata article URL (`reaper-51261` → `reaper`); strips any fragment or query string first and matches the extension case-insensitively.
  - `find_match(title, url, slugs, aliases, slug_names) -> str or None` returns the matching slug or `None`. `slugs` is a set of our `.ini` basenames; `aliases` is the dict from `aliases.json` keyed by normalized title; `slug_names` maps each slug to the `normalize()`d `name=` value of its file and is what lets `find_match` refuse an ambiguous title instead of guessing. Values must already be normalized; `run.py` calls `match.normalize` once per file rather than per article.

  **Expected refusal rate, stated up front so nobody mistakes it for a bug.** Against the live kaldata feed the URL step matches roughly 1 item in 5, because 25 of 50 slugs are hyphenated while none of our 920 slugs contain a hyphen. Hyphen-insensitive comparison does not recover them (`mozilla-thunderbird` is still not `thunderbird`), so the majority of in-catalog articles reach step 3 and are refused. That is the designed behaviour, not a regression: the alternative was a 62-in-920 wrong-file rate. `aliases.json` is the mechanism for closing the gap, and Task 7 exists to seed it from real feed data.

- [ ] **Step 1: Write the failing tests**

`F:\-SAM-\WWW\samlab.ws_bot\tests\test_match.py`

```python
import match
import version


SLUGS = {
    "reaper", "vivaldi", "firefox", "thunderbird", "googlechrome",
    "fruityloops", "antimalwarem", "foobar", "aimp", "potplayer",
}

# slug -> the raw name= value of that file. find_match needs this to tell a
# unique name from one that two of our files share, and to notice a title that
# names one file while the URL names another. Real names rarely equal their
# slug, so neither does this.
NAMES = {
    slug: match.normalize(name)
    for slug, name in {
        "reaper": "REAPER 7 host",
        "vivaldi": "Vivaldi Browser 5.6",
        "firefox": "Firefox Quantum",
        "thunderbird": "Mozilla Thunderbird 157",
        "googlechrome": "Google Chrome 120",
        "fruityloops": "FL Studio 26",
        "antimalwarem": "Malwarebytes Anti-Malware",
        "foobar": "Foobar 2000",
        "aimp": "AIMP 5.60",
        "potplayer": "PotPlayer 1.6",
    }.items()
}


class TestNormalize:
    def test_strips_version_and_markers(self):
        assert match.normalize("Mozilla Thunderbird 157.0.1 Final") == "mozillathunderbird"

    def test_strips_spaces_and_punctuation(self):
        assert match.normalize("Advanced Renamer 4.27") == "advancedrenamer"

    def test_parentheses_removed(self):
        assert match.normalize("DriverMax 18.0.309") == "drivermax"

    def test_marker_word_starting_a_product_name_survives(self):
        # real catalog entry: "Final" here is part of the name, and dropping it
        # leaves "uninstaller", which no slug can match
        assert match.normalize("Final Uninstaller 2.69") == "finaluninstaller"

    def test_marker_word_prefix_is_not_split(self):
        # real catalog entry: "Device" must not lose its leading letters
        assert match.normalize("Unknown Device Identifier 9.01") == "unknowndeviceidentifier"

    def test_numbered_trailing_marker_stripped(self):
        assert match.normalize("Sumatra PDF 3.7.22641 Dev") == "sumatrapdf"

    def test_marker_before_other_words_is_kept(self):
        # "Beta 1 Rus" is not trailing, so nothing is stripped; leaving the words
        # in place is the safe direction, and the channel gate rejects the
        # article before matching ever sees it
        assert match.normalize("WinRAR 7.30 Beta 1 Rus") == "winrarbeta1rus"

    def test_samlab_suffix_stripped(self):
        # 26 real names carry our own "- SamLab.ws Рекомендует!" decoration.
        # Leaving it in would leave "7zipsamlabws", which equals no slug;
        # the decoration is ours, so stripping it is strictly safe.
        assert match.normalize("7-Zip 26.03 - SamLab.ws Рекомендует!") == "7zip"
        # once the decoration is gone the channel marker is trailing again, so
        # it is stripped too and the name matches our slug exactly
        assert match.normalize("PotPlayer 1.6.53146 Alpha - SamLab.ws сборка!") == (
            "potplayer"
        )

    def test_samlab_suffix_is_stripped_only_at_the_end(self):
        # a product name that merely starts with "SamLab" keeps it
        assert match.normalize("SamLab Tools 2.0") == "samlabtools"

    def test_cyrillic_only_title_normalizes_to_empty(self):
        # nothing survives, which is safe: an empty key can never equal a slug
        assert match.normalize("Новогодние подарки и персонализированные украшения") == ""

    def test_bare_version_normalizes_to_empty(self):
        assert match.normalize("5.1.2600.5515") == ""


class TestSlugFromLink:
    def test_simple(self):
        url = "https://www.kaldata.com/x/reaper-51261.html"
        assert match.slug_from_link(url) == "reaper"

    def test_dash_variant(self):
        url = "https://www.kaldata.com/x/reg-organizer-43546.html"
        assert match.slug_from_link(url) == "reg-organizer"

    def test_underscore_variant(self):
        # kaldata spells the id separator with an underscore, and a slug may
        # itself contain underscores, so the two must not be confused
        url = "https://www.kaldata.com/x/reg-organizer_43546.html"
        assert match.slug_from_link(url) == "reg-organizer"
        url = "https://www.kaldata.com/x/reg_organizer-43546.html"
        assert match.slug_from_link(url) == "reg_organizer"

    def test_no_article_id(self):
        # a slug that legitimately ends in a digit keeps it: the "-<digits>"
        # tail is only stripped when a separator precedes it
        assert match.slug_from_link("https://www.kaldata.com/x/win10tools.html") == "win10tools"

    def test_trailing_slash(self):
        url = "https://www.kaldata.com/x/vivaldi-103265.html/"
        assert match.slug_from_link(url) == "vivaldi"

    def test_uppercase_url(self):
        # kaldata is inconsistent about case; the comparison is against
        # lowercase slugs, so the whole path is lowered
        url = "https://www.kaldata.com/x/REAPER-51261.HTML"
        assert match.slug_from_link(url) == "reaper"

    def test_fragment_and_query_are_stripped(self):
        # the feed's <comments> URLs all carry "#respond"; a leaked fragment
        # would turn every URL into a refusal
        url = "https://www.kaldata.com/x/reaper-51261.html#respond"
        assert match.slug_from_link(url) == "reaper"
        url = "https://www.kaldata.com/x/reaper-51261.html?page=2"
        assert match.slug_from_link(url) == "reaper"

    def test_slug_ending_in_digits_is_preserved(self):
        # "-<digits>" is only stripped when a separator precedes it, so
        # "foobar2" survives intact
        url = "https://www.kaldata.com/x/foobar2.html"
        assert match.slug_from_link(url) == "foobar2"

    def test_htm_extension(self):
        assert match.slug_from_link("https://www.kaldata.com/x/reaper-51261.htm") == "reaper"


class TestFindMatch:
    def test_exact_slug_wins(self):
        got = match.find_match(
            "REAPER 7.82 Final", "https://k/x/reaper-51261.html", SLUGS, {}, NAMES,
        )
        assert got == "reaper"

    def test_exact_name_match(self):
        got = match.find_match(
            "Thunderbird 157.0.1 Final", "https://k/x/xx-1.html", SLUGS, {}, NAMES,
        )
        assert got == "thunderbird"

    def test_real_feed_title_is_not_a_name_match(self):
        # the live kaldata title for Thunderbird; it normalizes to
        # "mozillathunderbird", which is not our slug, so the URL step has to
        # carry it. This is the documented refusal rate, not a defect.
        got = match.find_match(
            "Mozilla Thunderbird 157.0.1 Final", "https://k/x/xx-1.html", SLUGS, {}, NAMES,
        )
        assert got is None

    def test_hyphenated_url_slug_is_refused(self):
        # 25 of 50 live slugs are hyphenated and none of our 920 slugs are, so
        # this is a refusal. Refusing is correct: "thunderbird" cannot be
        # inferred from "mozilla-thunderbird" without guessing.
        got = match.find_match(
            "Mozilla Thunderbird 157.0.1 Final", "https://k/x/mozilla-thunderbird-1.html",
            SLUGS, {}, NAMES,
        )
        assert got is None

    def test_superstring_name_does_not_match_a_short_slug(self):
        # real catalog pair: containment would match "avira" here and rewrite
        # the System Speedup file with Avira's version
        slugs = {"avira", "aviraspeedup"}
        names = {"avira": "aviraantivirus", "aviraspeedup": "avirasystemspeedup"}
        got = match.find_match(
            "Avira System Speedup 7.5.0.552", "https://k/x/xx-1.html", slugs, {}, names,
        )
        assert got is None

    def test_brand_extension_does_not_match(self):
        # real catalog case: "qBittorrent" must not be matched by a bare
        # "BitTorrent" title, which is a different program
        slugs = {"bittorrent", "qbittorrent"}
        names = {"bittorrent": "bittorrent", "qbittorrent": "qbittorrent"}
        assert match.find_match(
            "qBittorrent 4.6.7.0", "https://k/x/xx-1.html", slugs, {}, names,
        ) == "qbittorrent"
        assert match.find_match(
            "BitTorrent 7.11.0.47255", "https://k/x/xx-1.html", slugs, {}, names,
        ) == "bittorrent"

    def test_generic_suffix_does_not_match(self):
        # real catalog case: "Shark007 Codecs" must not land on "codec"
        slugs = {"codec", "win8codecs"}
        names = {"codec": "codecs", "win8codecs": "shark007codecs"}
        got = match.find_match(
            "Shark007 Codecs 20.9.4", "https://k/x/xx-1.html", slugs, {}, names,
        )
        assert got is None

    def test_shared_name_is_refused(self):
        # real catalog case: mp3tags.ini is name="Mp3tag 3.36.1" (the free
        # build) and mp3tag.ini is name=mp3Tag Pro 12.1. An article titled
        # "Mp3tag 3.36.1" normalizes to "mp3tag", which IS a slug, but it is
        # not the file that owns the name. Refusing is the only safe answer;
        # guessing writes the Pro file with the free build's version.
        slugs = {"mp3tag", "mp3tags"}
        names = {"mp3tag": "mp3tagpro", "mp3tags": "mp3tag"}
        got = match.find_match(
            "Mp3tag 3.36.1", "https://k/x/xx-1.html", slugs, {}, names,
        )
        assert got is None

    def test_shared_name_resolved_by_alias(self):
        # the alias is how a human says which of the two files is meant
        slugs = {"mp3tag", "mp3tags"}
        names = {"mp3tag": "mp3tagpro", "mp3tags": "mp3tag"}
        aliases = {match.normalize("Mp3tag 3.36.1"): "mp3tags"}
        got = match.find_match(
            "Mp3tag 3.36.1", "https://k/x/xx-1.html", slugs, aliases, names,
        )
        assert got == "mp3tags"

    def test_shared_name_refused_even_when_url_agrees(self):
        # the URL slug must not override an ambiguous name either: "mp3tag" in
        # the URL says nothing about which of the two .ini files is meant
        slugs = {"mp3tag", "mp3tags"}
        names = {"mp3tag": "mp3tagpro", "mp3tags": "mp3tag"}
        got = match.find_match(
            "Mp3tag 3.36.1", "https://k/x/mp3tag-1.html", slugs, {}, names,
        )
        assert got is None

    def test_blank_alias_key_is_refused(self):
        # normalize() returns "" for a bare version and for an all-Cyrillic
        # title, both of which occur in the catalog. A "" key in a
        # hand-edited aliases.json would otherwise redirect every such title.
        aliases = {"": "samdrivers"}
        assert match.find_match(
            "5.1.2600.5515", "https://k/x/xx-1.html", SLUGS, aliases, NAMES,
        ) is None
        assert match.find_match(
            "Новогодние подарки", "https://k/x/xx-1.html", SLUGS, aliases, NAMES,
        ) is None
        # and the same is refused through the URL step
        assert match.find_match(
            "5.1.2600.5515", "https://k/x/reaper-1.html", SLUGS, {"": "samdrivers"}, NAMES,
        ) is None

    def test_empty_title_returns_none(self):
        assert match.find_match("", "", SLUGS, {}, NAMES) is None

    def test_stale_alias_is_not_replaced_by_a_name_match(self):
        # an alias is a human decision; if its slug is gone, the entry needs
        # review rather than a guess
        aliases = {match.normalize("Firefox 158.0 Beta 3"): "gone"}
        got = match.find_match(
            "Firefox 158.0 Beta 3", "https://k/x/xx-1.html", SLUGS, aliases, NAMES,
        )
        assert got is None

    def test_stale_alias_does_not_block_a_valid_url_slug(self):
        # the alias points at a file that no longer exists, but the URL is
        # independent evidence and is still honoured
        aliases = {match.normalize("Firefox 158.0 Beta 3"): "gone"}
        got = match.find_match(
            "Firefox 158.0 Beta 3", "https://k/x/reaper-51261.html", SLUGS, aliases, NAMES,
        )
        assert got == "reaper"

    def test_alias_override(self):
        aliases = {match.normalize("FL Studio 26.1.7.5653 Final"): "fruityloops"}
        got = match.find_match(
            "FL Studio 26.1.7.5653 Final", "https://k/x/fl-studio-1.html",
            SLUGS, aliases, NAMES,
        )
        assert got == "fruityloops"

    def test_alias_beats_a_valid_url_slug(self):
        # discriminating test for precedence: the URL slug here IS one of our
        # slugs, so swapping the two steps would return "vivaldi"
        aliases = {match.normalize("Firefox 158.0 Beta 3"): "firefox"}
        got = match.find_match(
            "Firefox 158.0 Beta 3", "https://k/x/vivaldi-103265.html", SLUGS, aliases, NAMES,
        )
        assert got == "firefox"

    def test_alias_outside_the_slug_set_is_refused(self):
        # the alias names a real file, but that file is not in the catalog we
        # were handed; the entry cannot be honoured
        aliases = {match.normalize("Firefox 158.0 Beta 3"): "fruityloops"}
        got = match.find_match(
            "Firefox 158.0 Beta 3", "https://k/x/xx-1.html", {"reaper", "vivaldi"},
            aliases, {"reaper": "reaper", "vivaldi": "vivaldi"},
        )
        assert got is None

    def test_no_match_returns_none(self):
        got = match.find_match(
            "RustDesk 1.5.0", "https://k/x/rustdesk-1.html", SLUGS, {}, NAMES,
        )
        assert got is None

    def test_short_title_still_matches_exactly(self):
        # a short normalized name equal to a real slug is a correct match;
        # there is no length floor to invent a reason to refuse it
        got = match.find_match(
            "AIMP 5.60 Final", "https://k/x/xx-1.html", SLUGS, {}, NAMES,
        )
        assert got == "aimp"

    def test_short_url_slug_still_wins(self):
        # an exact slug taken from the URL needs no length floor either
        got = match.find_match(
            "Foo 1.0", "https://k/x/aimp-1.html", SLUGS, {}, NAMES,
        )
        assert got == "aimp"

    def test_url_slug_beats_name_equality(self):
        # both are exact; the URL is the stronger evidence
        got = match.find_match(
            "Firefox 158.0 Beta 3", "https://k/x/vivaldi-1.html", SLUGS, {}, NAMES,
        )
        assert got == "vivaldi"

    def test_non_final_channel_normalizes_onto_the_plain_slug(self):
        # documents the coupling with version.split_channel: a Beta title
        # normalizes to the same key as the Final one, so matching is only safe
        # because the caller refuses non-final channels first
        assert match.normalize("Mozilla Thunderbird 115.0 Beta 4") == "mozillathunderbird"
        assert version.split_channel("Mozilla Thunderbird 115.0 Beta 4")[1] == "beta"
        got = match.find_match(
            "Mozilla Thunderbird 115.0 Beta 4", "https://k/x/thunderbird-1.html",
            SLUGS, {}, NAMES,
        )
        assert got == "thunderbird"
        assert version.split_channel("Mozilla Thunderbird 115.0 Beta 4")[1] != "final"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd F:\-SAM-\WWW\samlab.ws_bot; python -m pytest tests/test_match.py -v`
Expected: `ModuleNotFoundError: No module named 'match'`.

- [ ] **Step 3: Implement `match.py`**

```python
"""Map kaldata article titles onto our own soft/*.ini slugs."""

import re

import version

# Our own trailing decoration, on 26 real names: "7-Zip 26.03 - SamLab.ws
# Рекомендует!". Keeping it would leave "7zipsamlabws", which equals no slug.
SAMLAB_SUFFIX_RE = re.compile(r"\s*[-–—]?\s*samlab\.?ws\b.*$", re.IGNORECASE)

# A trailing "-<digits>" is a kaldata article id, not part of the slug.
# "reaper-51261" and "reaper_51261" both answer "reaper".
SLUG_TAIL_RE = re.compile(r"[-_]\d+$")

EXT_RE = re.compile(r"\.html?$", re.IGNORECASE)

# A channel marker sitting at the very end of a title, with an optional number:
# "Mozilla Thunderbird 157.0.1 Final", "Sumatra PDF 3.7.22641 Dev". Anchored at
# the end, so a marker word that merely starts a product name keeps it.
TRAILING_MARKERS_RE = re.compile(
    r"\s+(?:final|stable|release|beta|alpha|dev|nightly|rc|portable)\s*\d*$",
    re.IGNORECASE,
)


def normalize(text):
    """Reduce a title to a comparable bare name.

    Strips our own trailing decoration, version clusters, trailing channel
    markers, then removes every character that is not a letter or digit.
    ``"Mozilla Thunderbird 157.0.1 Final"`` becomes ``"mozillathunderbird"``.

    Channel markers are removed from the END of the string only, never from the
    middle. ``version.CHANNEL_RE`` cannot tell a marker word that belongs to a
    release from one that is part of a product name: in ``"WinRAR 7.30 Beta 1
    Rus"`` the ``Beta`` is a marker, while in ``"Final Uninstaller 2.69"`` — a
    real catalog entry — the ``Final`` is the product name, and removing it
    leaves ``"uninstaller"``, which no slug can match. Trailing removal captures
    the first case and cannot damage the second, because a product name does not
    end in a marker word followed by nothing.

    Working from the raw text also keeps ``"Device"`` intact: a marker regex
    loose enough to strip ``Beta 1 Rus`` would otherwise split ``Device`` down to
    ``ice``.

    Non-ASCII characters are deleted rather than transliterated, so a wholly
    Cyrillic title normalizes to ``""``. That is the safe direction: an empty key
    equals no slug, so the title is refused. The cost is that a Cyrillic title
    with one stray Latin token can still reach a slug, which is why ``find_match``
    also refuses a name shared by two of our files.
    """
    text = SAMLAB_SUFFIX_RE.sub("", text)
    text = version.VERSION_RE.sub(" ", text)
    text = TRAILING_MARKERS_RE.sub("", text)
    return re.sub(r"[^a-z0-9]", "", text.lower())


def slug_from_link(url):
    """``.../reaper-51261.html`` -> ``"reaper"``.

    kaldata appends a numeric post id to the slug; that id changes whenever an
    article is reposted, so it is stripped. Both the dash and the underscore
    spelling occur in real URLs, hence ``SLUG_TAIL_RE``. Only a ``-<digits>``
    tail with a separator is stripped, so a slug that legitimately ends in a
    digit (``foobar2``) survives.

    Fragments and query strings are removed first: the feed's ``<comments>``
    URLs all carry ``#respond``, which would otherwise leak into the slug and
    turn every such URL into a refusal. The extension is matched
    case-insensitively because kaldata is not consistent about ``.HTML``.
    """
    url = url.split("#", 1)[0].split("?", 1)[0]
    tail = url.rstrip("/").rsplit("/", 1)[-1].lower()
    tail = EXT_RE.sub("", tail)
    return SLUG_TAIL_RE.sub("", tail)


def is_ambiguous(key, slug, slug_names):
    """Does another one of our files carry the same normalized ``name=``?

    Exact title-to-slug equality is not by itself proof that the title belongs
    to ``slug``. In the real catalog ``mp3tags.ini`` is ``name="Mp3tag 3.36.1"``
    (the free build) while ``mp3tag.ini`` is ``name=mp3Tag Pro 12.1`` (paid).
    A kaldata article titled ``"Mp3tag 3.36.1"`` normalizes to ``mp3tag``, which
    is a real slug, so equality hands back the Pro file. Nothing in the title
    says which of the two is meant, and answering anyway writes one program's
    version into the other's ``.ini``.

    Seven pairs of real files share one normalized name, so this is a live
    case and not a theoretical one. An alias is how a human resolves it, which
    is why this is checked after the alias step and before the URL step: an
    explicit alias overrides the ambiguity, but a URL slug does not, because
    ``mp3tag`` in a URL is equally uninformative.

    ``slug_names`` maps a slug to that file's name already passed through
    ``normalize``, so this is a lookup rather than 920 regex substitutions per
    article.
    """
    return any(
        other != slug and name == key for other, name in slug_names.items()
    )


def find_match(title, url, slugs, aliases, slug_names):
    """Find our slug for a kaldata article, or ``None``.

    Resolution order, strongest evidence first:

    1. an explicit entry in ``aliases.json`` keyed by normalized title;
    2. the slug embedded in the article URL;
    3. exact equality between the normalized title and a slug.

    Step 3 demands exact equality, and ``aliases`` exists precisely because that
    is too strict to be the only name-based option. Substring containment looks
    reasonable and is not: measured against the real 920-file catalog it resolved
    610 names correctly and 62 to the WRONG file, because a short slug is a
    substring of a longer name far more often than it identifies the program.
    ``"Avira System Speedup 7.5.0.552"`` matched ``avira``, ``"Notepad4
    26.08.6282"`` matched ``notepad``, ``"BitTorrent 7.11.0.47255"`` matched
    ``qbittorrent``, ``"Shark007 Codecs 20.9.4"`` matched ``codec``. A wrong
    match writes the version from one program into another program's ``.ini``,
    which is the worst failure this bot has, and it is unrecoverable without the
    ``.bak`` review a human has to do by hand.

    An empty key is refused outright. ``normalize`` returns ``""`` for a bare
    version and for a wholly Cyrillic title, both of which occur in the catalog,
    so a single ``""`` entry in a hand-edited ``aliases.json`` would otherwise
    redirect every such title to one file.

    Refusing is expected to be common, not exceptional. On the live feed the URL
    step matches about 1 item in 5, because 25 of 50 kaldata slugs are hyphenated
    while none of our 920 slugs contain a hyphen, and hyphen-insensitive
    comparison does not recover them (``mozilla-thunderbird`` is still not
    ``thunderbird``). Exact equality costs real coverage; it buys the elimination
    of every wrong answer the name path can produce. Refusing a title costs one
    line in ``needs-review.txt``, where a human decides, and closing the gap is
    ``aliases.json``'s job.

    ``slug_names`` records the normalized ``name=`` of each of our files and is
    what lets an ambiguous title be refused rather than guessed; see
    ``is_ambiguous``.

    A stale alias blocks the name step but not the URL step: an alias is a human
    decision, so if its slug no longer exists the entry is surfaced for review,
    while a valid URL slug is independent evidence and is still honoured.

    Callers must apply ``version.split_channel`` first and drop non-final
    articles. ``normalize`` folds ``"Mozilla Thunderbird 115.0 Beta 4"`` onto the
    same key as the Final release, so a beta article would otherwise reach the
    final track's URL.
    """
    if not title or not url:
        return None

    key = normalize(title)
    if not key:
        return None

    aliased = aliases.get(key)
    stale_alias = key in aliases
    if aliased and aliased in slugs:
        return aliased

    slug = slug_from_link(url)
    if slug and slug in slugs:
        if not is_ambiguous(key, slug, slug_names):
            return slug
        return None

    if stale_alias:
        return None

    if key not in slugs:
        return None

    return None if is_ambiguous(key, key, slug_names) else key
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd F:\-SAM-\WWW\samlab.ws_bot; python -m pytest tests/test_match.py -v`
Expected: all passed.

- [ ] **Step 5: Run the full suite so far**

Run: `cd F:\-SAM-\WWW\samlab.ws_bot; python -m pytest -v`
Expected: smoke + version + match all pass.

- [ ] **Step 6: Commit**

```powershell
cd F:\-SAM-\WWW\samlab.ws_bot
git add match.py tests/test_match.py
git commit -m "feat: map kaldata titles to our ini slugs by alias, slug, then name"
```

---

### Task 4: Rewriting .ini files in cp1251

**Files:**
- Create: `F:\-SAM-\WWW\samlab.ws_bot\iniwrite.py`
- Create: `F:\-SAM-\WWW\samlab.ws_bot\tests\test_iniwrite.py`

**Interfaces:**
- Consumes: `version` (Task 2).
- Produces:
  - `read_ini(path) -> str` decodes bytes as cp1251.
  - `current_name(text) -> str` returns the `name=` value without surrounding quotes.
  - `parse_sections(text) -> list[tuple[int, int, str]]` returns `(start, end, section_name)` for every `[name]` header, with `""` for the preamble before the first header.
  - `rewrite_name(text, old_version, new_version) -> str` replaces the Final-track version inside the `name=` value only. Returns text unchanged when the old version is absent.
  - `rewrite_links(text, old_version, new_version) -> (str, int)` substitutes the version inside `link=` lines that belong to `[link_N]` sections. Returns `(new_text, replacements_made)`. Returns `(text, 0)` when nothing matched.
  - `version_forms(vstr) -> list[str]` returns the spellings a version may take inside a URL: dotted, compact (`782`), dashed (`7-82`), underscored (`7_82`).
  - `substitute_url(url, old_version, new_version) -> str or None` returns the rewritten URL, or `None` when no spelling occurs, when a spelling occurs more than once, or when two different spellings match.
  - `plan_rewrite(text, old_version, new_version) -> (str, int)` returns what the file would become plus the link count, without touching the filesystem.
  - `update_ini(path, old_version, new_version, write=True) -> dict` performs the write when `write=True`: backup, atomic replace. Returns `{"changed": bool, "links": int, "backup": str or None}` where `changed` means "was rewritten, or would be if `write` were true". Returns `changed=False` whenever `links == 0`, so a version we cannot put into the URLs is never written.

- [ ] **Step 1: Write the failing tests**

`F:\-SAM-\WWW\samlab.ws_bot\tests\test_iniwrite.py`

```python
import pathlib
import shutil

import iniwrite

ROOT = pathlib.Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "fixtures"


def _load(name):
    return (FIXTURES / name).read_bytes().decode("cp1251")


def _section(text, index):
    start, end, _ = iniwrite.parse_sections(text)[index]
    return text[start:end]


class TestVersionForms:
    def test_dotted_included(self):
        assert "7.82" in iniwrite.version_forms("7.82")

    def test_compact(self):
        assert "782" in iniwrite.version_forms("7.82")

    def test_dashed(self):
        assert "7-82" in iniwrite.version_forms("7.82")

    def test_underscored(self):
        assert "7_82" in iniwrite.version_forms("7.82")

    def test_four_part_compact(self):
        assert "82413383" in iniwrite.version_forms("8.2.4133.83")

    def test_short_compact_excluded(self):
        # "0.3" -> compact "03" is too short to match safely
        assert "03" not in iniwrite.version_forms("0.3")


class TestSubstituteUrl:
    def test_compact_form_in_url(self):
        url = "https://www.reaper.fm/files/7.x/reaper782-install.exe"
        got = iniwrite.substitute_url(url, "7.82", "7.83")
        assert got == "https://www.reaper.fm/files/7.x/reaper783-install.exe"

    def test_dotted_form_in_url(self):
        url = "https://downloads.vivaldi.com/stable/Vivaldi.8.2.4133.83.exe"
        got = iniwrite.substitute_url(url, "8.2.4133.83", "8.2.4133.99")
        assert got == "https://downloads.vivaldi.com/stable/Vivaldi.8.2.4133.99.exe"

    def test_dashed_form_in_url(self):
        url = "https://example.org/files/app-8-2-4133-83-setup.exe"
        got = iniwrite.substitute_url(url, "8.2.4133.83", "8.2.4133.99")
        assert got == "https://example.org/files/app-8-2-4133-99-setup.exe"

    def test_url_without_version_returns_none(self):
        url = "https://www.google.com/chrome/browser/desktop/index.html"
        assert iniwrite.substitute_url(url, "154.0.8037.98", "155.0.0.0") is None

    def test_tracker_url_returns_none(self):
        url = "http://turbobit.net/0bu8u10x42j8/avira_setup.exe.html"
        assert iniwrite.substitute_url(url, "2.7.0.3165", "2.8.0.0") is None

    def test_ambiguous_repeat_returns_none(self):
        url = "https://example.org/7.82/7.82/setup.exe"
        assert iniwrite.substitute_url(url, "7.82", "7.83") is None

    def test_digit_boundary_respected(self):
        # "7821" must not match the compact spelling "782"
        url = "https://example.org/app7821.exe"
        assert iniwrite.substitute_url(url, "7.82", "7.83") is None

    def test_quoteless_and_quoted_urls(self):
        assert iniwrite.substitute_url("https://e.org/reaper782.exe", "7.82", "7.83").endswith("reaper783.exe")


class TestParseSections:
    def test_finds_link_sections(self):
        text = _load("reaper.ini")
        names = [name for _, _, name in iniwrite.parse_sections(text)]
        assert "info" in names
        assert "link_5" in names

    def test_underscore_and_plain_coexist(self):
        text = _load("reaper.ini")
        names = [name for _, _, name in iniwrite.parse_sections(text)]
        assert "link_8" in names
        assert "link7" in names  # reserve section, must stay untouched

    def test_section_index_layout(self):
        # reaper.ini section order, pinned so the rewrite tests can address a
        # section by index: [info] [link_5] [link7] [link_8] ...
        text = _load("reaper.ini")
        names = [name for _, _, name in iniwrite.parse_sections(text)]
        assert names[:4] == ["info", "link_5", "link7", "link_8"]

    def test_preamble_present(self):
        text = "junk\n[info]\nname=x\n"
        sections = iniwrite.parse_sections(text)
        assert sections[0][2] == ""


class TestRewriteName:
    def test_replaces_only_final_track(self):
        text = _load("vivaldi.ini")
        got = iniwrite.rewrite_name(text, "8.2.4133.83", "8.2.4133.99")
        assert "Vivaldi 8.3.4175.3 Dev + 8.2.4133.99 Final" in got
        assert "8.3.4175.3" in got  # Dev track untouched

    def test_unchanged_when_version_absent(self):
        text = _load("reaper.ini")
        got = iniwrite.rewrite_name(text, "9.9.9", "9.9.10")
        assert got == text

    def test_other_keys_untouched(self):
        text = _load("reaper.ini")
        got = iniwrite.rewrite_name(text, "7.82", "7.83")
        assert "type=audioedit" in got
        assert "licence=" in got


class TestRewriteLinks:
    def test_only_underscore_sections_change(self):
        text = _load("reaper.ini")
        got, count = iniwrite.rewrite_links(text, "7.82", "7.83")
        assert count == 2  # link_5 and link_8 only
        # link7 sits at index 2 and has no underscore: hidden reserve, identical
        assert _section(text, 2) == _section(got, 2)
        assert _section(text, 2).startswith("[link7]")
        # link_8 at index 3 does carry the version and must have been rewritten
        assert _section(text, 3) != _section(got, 3)
        assert "reaper783_x64-install.exe" in _section(got, 3)
        # the reserve URLs still point at the old build on purpose
        assert "landoleet.org/reaper782-install.exe" in got
        assert "landoleet.org/reaper782_x64-install.exe" in got

    def test_link_forum_untouched(self):
        text = _load("reaper.ini")
        got, _ = iniwrite.rewrite_links(text, "7.82", "7.83")
        assert "http://samforum.org/showthread.php?goto=newpost&t=5216" in got

    def test_zero_when_no_version_in_links(self):
        text = _load("googlechrome.ini")
        got, count = iniwrite.rewrite_links(text, "154.0.8037.98", "155.0.0.0")
        assert count == 0
        assert got == text

    def test_crlf_preserved(self):
        text = _load("reaper.ini")
        got, _ = iniwrite.rewrite_links(text, "7.82", "7.83")
        assert got.count("\r\n") == text.count("\r\n")


class TestUpdateIni:
    def test_end_to_end_writes_and_backs_up(self, tmp_path):
        src = FIXTURES / "reaper.ini"
        target = tmp_path / "reaper.ini"
        shutil.copyfile(str(src), str(target))

        before = target.read_bytes()
        result = iniwrite.update_ini(str(target), "7.82", "7.83")

        assert result["changed"] is True
        assert result["links"] > 0
        assert (tmp_path / "reaper.ini.bak").read_bytes() == before
        after = target.read_bytes().decode("cp1251")
        assert "REAPER 7.83" in after
        assert "\ufffd" not in after

    def test_no_change_leaves_file_untouched(self, tmp_path):
        src = FIXTURES / "reaper.ini"
        target = tmp_path / "reaper.ini"
        shutil.copyfile(str(src), str(target))
        before = target.read_bytes()

        result = iniwrite.update_ini(str(target), "1.2.3", "1.2.4")

        assert result["changed"] is False
        assert target.read_bytes() == before
        assert not (tmp_path / "reaper.ini.bak").exists()

    def test_no_url_change_blocks_the_write(self, tmp_path):
        # a version we cannot rewrite the download URLs for is left completely
        # alone: shipping the new name would advertise a build nobody downloads
        src = FIXTURES / "googlechrome.ini"
        target = tmp_path / "googlechrome.ini"
        shutil.copyfile(str(src), str(target))
        before = target.read_bytes()

        result = iniwrite.update_ini(str(target), "154.0.8037.98", "155.0.0.0")

        assert result["changed"] is False
        assert result["links"] == 0
        assert target.read_bytes() == before
        assert not (tmp_path / "googlechrome.ini.bak").exists()

    def test_write_false_reports_without_touching_the_file(self, tmp_path):
        src = FIXTURES / "reaper.ini"
        target = tmp_path / "reaper.ini"
        shutil.copyfile(str(src), str(target))
        before = target.read_bytes()

        result = iniwrite.update_ini(str(target), "7.82", "7.83", write=False)

        assert result["changed"] is True
        assert result["links"] == 2
        assert result["backup"] is None
        assert target.read_bytes() == before
        assert not (tmp_path / "reaper.ini.bak").exists()

    def test_idempotent(self, tmp_path):
        src = FIXTURES / "reaper.ini"
        target = tmp_path / "reaper.ini"
        shutil.copyfile(str(src), str(target))

        iniwrite.update_ini(str(target), "7.82", "7.83")
        once = target.read_bytes()
        second = iniwrite.update_ini(str(target), "7.83", "7.83")

        assert second["changed"] is False
        assert target.read_bytes() == once
```

- [ ] **Step 2: Copy the Chrome fixture needed by the tests**

`test_rewrite_links.test_zero_when_no_version_in_links` and
`test_no_url_change_blocks_the_write` need a file whose URLs carry no version at
all — `googlechrome.ini` is exactly that case. Its line endings are bare LF, unlike
the CRLF fixtures, which is why it is not covered by the smoke test's CRLF check.

```powershell
Copy-Item "F:\-SAM-\WWW\samlab.ws\soft\googlechrome.ini" "F:\-SAM-\WWW\samlab.ws_bot\fixtures\googlechrome.ini"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd F:\-SAM-\WWW\samlab.ws_bot; python -m pytest tests/test_iniwrite.py -v`
Expected: `ModuleNotFoundError: No module named 'iniwrite'`.

- [ ] **Step 4: Implement `iniwrite.py`**

```python
"""Read and rewrite the site's soft/*.ini files.

Two rules shape this module and must not be relaxed:

* files are windows-1251, so every read and write goes through cp1251;
* sections named ``[linkN]`` without an underscore are hidden reserves that
  the site template deliberately skips. Only ``[link_N]`` is rendered, so only
  ``[link_N]`` is rewritten.

Writes are atomic: the original is copied to ``<path>.bak``, the new content
lands in a temp file, and that temp file is renamed over the original. A
concurrent site request therefore sees either the old file or the new one,
never a half-written one.
"""

import os
import re
import shutil
import tempfile

import version

# Only underscore sections are rendered by templates/full.tpl.
LINK_SECTION_RE = re.compile(r"^link_\d+$")

SECTION_RE = re.compile(r"^\[([^\]\r\n]+)\][ \t]*\r?$", re.MULTILINE)

# Values stop at the CR/LF instead of running to the end of the line. With ".*"
# the CR of a CRLF file lands inside the match and rebuilding the line would
# silently drop it, turning CRLF into LF in every rewritten link.
NAME_RE = re.compile(r"^(name\s*=\s*)([^\r\n]*)", re.MULTILINE)
LINK_RE = re.compile(r"^(link\s*=\s*)([^\r\n]*)", re.MULTILINE)


def read_ini(path):
    """Read a .ini as cp1251 text."""
    with open(path, "rb") as fh:
        return fh.read().decode("cp1251")


def version_forms(vstr):
    """Spellings a version may take inside a download URL.

    ``7.82`` becomes ``["7.82", "782", "7-82", "7_82"]``. Compact forms shorter
    than 3 characters are dropped: they match too much by accident.
    """
    parts = re.split(r"[.\-_]+", vstr.strip())
    forms = [vstr.strip()]

    compact = "".join(parts)
    if len(compact) >= 3 and compact not in forms:
        forms.append(compact)

    for sep in ("-", "_"):
        joined = sep.join(parts)
        if joined not in forms:
            forms.append(joined)

    return forms


def substitute_url(url, old_version, new_version):
    """Swap ``old_version`` for ``new_version`` inside a single URL.

    Every spelling of the old version gets a counterpart in the same spelling
    for the new one, so a URL that reads ``reaper782-install.exe`` becomes
    ``reaper783-install.exe`` and a dotted URL stays dotted.

    Returns ``None`` — "cannot be done safely" — when no spelling of the old
    version occurs, when one spelling occurs more than once, or when two
    different spellings match. Guessing in any of those cases risks pointing at
    a file that does not exist.
    """
    old_parts = re.split(r"[.\-_]+", old_version.strip())
    new_parts = re.split(r"[.\-_]+", new_version.strip())
    if len(old_parts) != len(new_parts):
        return None

    compact_old = "".join(old_parts)
    pairs = [(".".join(old_parts), ".".join(new_parts))]
    if len(compact_old) >= 3:
        pairs.append((compact_old, "".join(new_parts)))
    for separator in ("-", "_"):
        pairs.append((separator.join(old_parts), separator.join(new_parts)))

    result = url
    hits = 0
    for old_form, new_form in pairs:
        if old_form == new_form:
            continue  # nothing to do for this spelling
        pattern = re.compile(r"(?<![0-9])" + re.escape(old_form) + r"(?![0-9])")
        found = pattern.findall(result)
        if not found:
            continue
        if len(found) > 1:
            return None  # same version twice in one URL: intent is unclear
        result = pattern.sub(lambda _match: new_form, result, count=1)
        hits += 1

    return result if hits == 1 else None


def parse_sections(text):
    """Return ``[(start, end, section_name), ...]`` covering the whole text.

    The first entry has an empty name and covers any preamble before the first
    ``[header]``. ``end`` of one section is the ``start`` of the next.
    """
    matches = list(SECTION_RE.finditer(text))
    if not matches:
        return [(0, len(text), "")]

    sections = []
    if matches[0].start() > 0:
        sections.append((0, matches[0].start(), ""))
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections.append((match.start(), end, match.group(1).strip()))
    return sections


def rewrite_name(text, old_version, new_version):
    """Replace the Final-track version inside the ``name=`` line only."""
    match = NAME_RE.search(text)
    if not match:
        return text

    value = match.group(2)
    quoted = value.strip().startswith('"')
    inner = value.strip().strip('"')

    current = version.final_track_version(inner)
    if current != old_version:
        return text

    new_inner = inner.replace(old_version, new_version, 1)
    if quoted:
        new_value = '"%s"' % new_inner
    else:
        new_value = new_inner

    return text[:match.start(2)] + new_value + text[match.end(2):]


def rewrite_links(text, old_version, new_version):
    """Substitute the version in ``link=`` lines inside ``[link_N]`` sections.

    Returns ``(new_text, replacements)``. Sections without the underscore are
    left byte-identical, as are ``[link_forum]`` and every other key.
    """
    sections = parse_sections(text)
    pieces = []
    cursor = 0
    total = 0

    for start, end, name in sections:
        if not LINK_SECTION_RE.match(name):
            continue

        chunk = text[start:end]

        def replace(match):
            nonlocal total
            url = match.group(2).strip().strip('"')
            new_url = substitute_url(url, old_version, new_version)
            if new_url is None:
                return match.group(0)
            total += 1
            if match.group(2).strip().startswith('"'):
                return '%s"%s"' % (match.group(1), new_url)
            return "%s%s" % (match.group(1), new_url)

        rewritten = LINK_RE.sub(replace, chunk)
        pieces.append(text[cursor:start])
        pieces.append(rewritten)
        cursor = end

    pieces.append(text[cursor:])
    return "".join(pieces), total


def current_name(text):
    """Return the current ``name=`` value without surrounding quotes."""
    match = NAME_RE.search(text)
    if not match:
        return ""
    return match.group(2).strip().strip('"')


def plan_rewrite(text, old_version, new_version):
    """Return ``(new_text, links)`` without touching the filesystem.

    The name is rewritten first so the links are substituted in the final
    layout, but the caller is responsible for discarding both when ``links`` is
    zero.
    """
    new_text = rewrite_name(text, old_version, new_version)
    new_text, links = rewrite_links(new_text, old_version, new_version)
    return new_text, links


def update_ini(path, old_version, new_version, write=True):
    """Rewrite a single .ini in place, with backup and atomic replace.

    ``write=False`` computes the result and reports it without modifying
    anything — that is how a dry-run learns what *would* change.

    ``changed`` means "the file was rewritten, or would have been if ``write``
    were true". A rewrite with ``links == 0`` is refused outright: bumping the
    name while the download URLs still serve the old build would make the page
    lie. Such an entry is queued for review instead.

    Returns ``{"changed": bool, "links": int, "backup": str or None}``.
    """
    text = read_ini(path)
    new_text, links = plan_rewrite(text, old_version, new_version)

    if links == 0 or new_text == text:
        return {"changed": False, "links": 0, "backup": None}

    if not write:
        return {"changed": True, "links": links, "backup": None}

    backup = path + ".bak"
    shutil.copy2(path, backup)

    directory = os.path.dirname(os.path.abspath(path))
    fd, tmp_path = tempfile.mkstemp(dir=directory, suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(new_text.encode("cp1251"))
        shutil.copystat(path, tmp_path)
        os.replace(tmp_path, path)
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise

    return {"changed": True, "links": links, "backup": backup}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd F:\-SAM-\WWW\samlab.ws_bot; python -m pytest tests/test_iniwrite.py -v`
Expected: all passed. `test_section_index_layout` pins the reaper fixture's section
order; if a fixture is ever refreshed and that test fails, update the index used by
`test_only_underscore_sections_change` to the position of the no-underscore reserve
section rather than relaxing the assertion.

- [ ] **Step 6: Run the full suite**

Run: `cd F:\-SAM-\WWW\samlab.ws_bot; python -m pytest -v`
Expected: all pass.

- [ ] **Step 7: Commit**

```powershell
cd F:\-SAM-\WWW\samlab.ws_bot
git add iniwrite.py tests/test_iniwrite.py fixtures/googlechrome.ini
git commit -m "feat: rewrite ini versions and urls in cp1251 with backup and atomic replace"
```

---

### Task 5: kaldata feed and article fetching

**Files:**
- Create: `F:\-SAM-\WWW\samlab.ws_bot\kaldata.py`
- Create: `F:\-SAM-\WWW\samlab.ws_bot\tests\test_kaldata.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `USER_AGENT` — browser UA string; kaldata returns 403 without it.
  - `fetch(url, timeout=30, attempts=None, backoff=FETCH_BACKOFF_SECONDS) -> str` returns decoded body text. Retries a truncated or dropped connection up to 8 times with backoff, because Cloudflare serves the feed chunked and closes it mid-body on roughly five of six live reads. Raises `RuntimeError` when every attempt fails. An `HTTPError` (403, 404) is re-raised immediately rather than retried — it subclasses `OSError` and would otherwise look like a flaky socket.
  - `parse_feed(xml_text) -> list[dict]` returns entries with keys `title`, `link`, `guid`, `pub_date`.
  - `extract_file_links(html_text, pattern) -> list[str]` returns direct download URLs, order preserved, duplicates removed.
  - `fetch_feed(feed_url, timeout=30) -> list[dict]`
  - `fetch_article_links(url, pattern, timeout=30) -> list[str]`

- [ ] **Step 1: Write the failing tests**

`F:\-SAM-\WWW\samlab.ws_bot\tests\test_kaldata.py`

```python
import kaldata

FEED_XML = """<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0"><channel>
<item><title>REAPER 7.82 Final</title>
<link>https://www.kaldata.com/x/reaper-51261.html</link>
<guid isPermaLink="false">51261</guid>
<pubDate>Mon, 05 Oct 2026 05:39:46 +0000</pubDate></item>
<item><title>Vivaldi 8.2.4133.83 Final</title>
<link>https://www.kaldata.com/x/vivaldi-103265.html</link>
<guid isPermaLink="false">103265</guid>
<pubDate>Sun, 04 Oct 2026 20:50:00 +0000</pubDate></item>
</channel></rss>"""

ARTICLE_HTML = """
<p>REAPER 7.82</p>
<a href="https://dlcf.reaper.fm/7.x/reaper782-install.exe">x86</a>
<a href="https://dlcf.reaper.fm/7.x/reaper782_x64-install.exe">x64</a>
<a href="https://www.kaldata.com/tag/reaper">tag</a>
<a href="https://example.org/other.zip">zip</a>
"""


class TestParseFeed:
    def test_returns_two_items(self):
        items = kaldata.parse_feed(FEED_XML)
        assert len(items) == 2

    def test_item_fields(self):
        item = kaldata.parse_feed(FEED_XML)[0]
        assert item["title"] == "REAPER 7.82 Final"
        assert item["link"].endswith("reaper-51261.html")
        assert item["guid"] == "51261"
        assert "Oct 2026" in item["pub_date"]

    def test_cyrillic_preserved(self):
        xml = FEED_XML.replace("REAPER 7.82 Final", "REAPER 7.82 Окончательно")
        assert "Окончательно" in kaldata.parse_feed(xml)[0]["title"]

    def test_malformed_xml_raises(self):
        try:
            kaldata.parse_feed("<rss><channel>")
        except Exception as exc:
            assert exc is not None
        else:
            raise AssertionError("expected a parse failure")


class TestExtractFileLinks:
    def test_finds_downloads(self):
        got = kaldata.extract_file_links(ARTICLE_HTML)
        assert "https://dlcf.reaper.fm/7.x/reaper782-install.exe" in got
        assert "https://dlcf.reaper.fm/7.x/reaper782_x64-install.exe" in got

    def test_order_preserved(self):
        got = kaldata.extract_file_links(ARTICLE_HTML)
        assert got.index("https://dlcf.reaper.fm/7.x/reaper782-install.exe") < \
               got.index("https://dlcf.reaper.fm/7.x/reaper782_x64-install.exe")

    def test_deduplicated(self):
        got = kaldata.extract_file_links(ARTICLE_HTML + ARTICLE_HTML)
        assert len(got) == len(set(got))

    def test_non_download_links_ignored(self):
        got = kaldata.extract_file_links(ARTICLE_HTML)
        assert not any("tag" in u for u in got)

    def test_custom_pattern(self):
        html = '<a href="https://e.org/a.torrent">t</a>'
        assert kaldata.extract_file_links(html, r"\.(exe|torrent)$") == ["https://e.org/a.torrent"]


class TestFetchErrors:
    def test_empty_body_raises(self, monkeypatch):
        class FakeResponse:
            def read(self):
                return b""
            def __enter__(self):
                return self
            def __exit__(self, *a):
                return False

        monkeypatch.setattr(kaldata, "_open", lambda url, timeout: FakeResponse())
        try:
            kaldata.fetch("https://example.org/")
        except RuntimeError as exc:
            assert "empty" in str(exc).lower()
        else:
            raise AssertionError("expected RuntimeError for empty body")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd F:\-SAM-\WWW\samlab.ws_bot; python -m pytest tests/test_kaldata.py -v`
Expected: `ModuleNotFoundError: No module named 'kaldata'`.

- [ ] **Step 3: Implement `kaldata.py`**

```python
"""Talk to kaldata.com: the software RSS feed and individual articles.

Three behaviours of the site drive this module, all measured rather than
assumed:

* it answers 403 to requests without a browser User-Agent;
* it intermittently returns a zero-byte body, which must be treated as a
  failure rather than as "no news";
* behind Cloudflare it serves chunked transfer encoding and regularly closes the
  connection before the last chunk arrives. Six consecutive feed fetches gave
  five ``IncompleteRead`` failures and one clean read of the identical 115062
  bytes, so the truncation is the server's, not ours, and a single attempt
  fails most of the time.
"""

import http.client
import re
import time
import urllib.request
from xml.etree import ElementTree

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

DEFAULT_LINK_PATTERN = r"\.(exe|msi|zip|7z|rar|dmg|tgz|deb)$"

# One attempt succeeds roughly one time in six against the live feed, so this
# is sized to make a failure genuinely unlikely rather than merely less likely.
FETCH_ATTEMPTS = 8
FETCH_BACKOFF_SECONDS = 1.5

# Errors that mean "this attempt did not complete", as opposed to "this URL is
# broken". Retrying the first kind is useful; retrying the second only wastes
# time, so 404 and friends are deliberately absent.
TRANSIENT_ERRORS = (
    http.client.IncompleteRead,
    http.client.HTTPException,
    ConnectionError,
    TimeoutError,
    OSError,
)

# ``urllib.error.HTTPError`` is a subclass of ``OSError``, so it is caught by the
# tuple above and would be retried like a flaky socket. A 404 or a 403 is not
# flaky: it is the site answering, and retrying only delays the report. This is
# checked first for that reason.
from urllib.error import HTTPError, URLError  # noqa: E402


def _is_transient(exc):
    """Would retrying this error plausibly succeed?"""
    if isinstance(exc, (HTTPError, URLError)):
        return False
    return isinstance(exc, TRANSIENT_ERRORS)


def _open(url, timeout):
    """Open a URL with a browser User-Agent and return the response."""
    request = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept-Language": "ru,en;q=0.8",
        "Accept-Encoding": "identity",
        "Connection": "close",
    })
    return urllib.request.urlopen(request, timeout=timeout)


def _once(url, timeout):
    """One fetch attempt. Returns ``(body_text, error)``."""
    try:
        with _open(url, timeout) as response:
            raw = response.read()
    except Exception as exc:
        if _is_transient(exc):
            return None, exc
        raise
    if not raw:
        return None, RuntimeError("empty response body from %s" % url)
    return raw.decode("utf-8", errors="replace"), None


def fetch(url, timeout=30, attempts=None, backoff=FETCH_BACKOFF_SECONDS):
    """Fetch a URL and return its body as text, retrying truncated responses.

    kaldata is served through Cloudflare with chunked transfer encoding and
    closes the connection mid-body often enough that a single attempt is not a
    reasonable design: five of six live feed reads raised ``IncompleteRead``.
    Retrying is safe because every failure here is a failure to obtain the
    *whole* body — a partial read is discarded, never returned, because half a
    feed parses into half a list of articles and would look like a quiet week.

    ``Accept-Encoding: identity`` removes the compression negotiation that
    makes the truncation visible in the first place.

    Raises ``RuntimeError`` when every attempt fails, including when the body
    is genuinely empty.
    """
    attempts = attempts or FETCH_ATTEMPTS
    last_error = None

    for attempt in range(attempts):
        if attempt:
            time.sleep(backoff * attempt)
        body, error = _once(url, timeout)
        if body is not None:
            return body
        last_error = error

    raise RuntimeError(
        "fetch failed after %d attempts: %s: %s"
        % (attempts, type(last_error).__name__, last_error)
    )


def parse_feed(xml_text):
    """Parse an RSS 2.0 feed into a list of entry dicts."""
    root = ElementTree.fromstring(xml_text.encode("utf-8"))
    items = []
    for item in root.iter("item"):
        items.append({
            "title": (item.findtext("title") or "").strip(),
            "link": (item.findtext("link") or "").strip(),
            "guid": (item.findtext("guid") or "").strip(),
            "pub_date": (item.findtext("pubDate") or "").strip(),
        })
    return items


def extract_file_links(html_text, pattern=DEFAULT_LINK_PATTERN):
    """Return direct download URLs found in an article, in order, deduplicated."""
    found = re.findall(
        r'href="(https?://[^"\'<>\s]+)"',
        html_text,
        re.IGNORECASE,
    )
    matcher = re.compile(pattern, re.IGNORECASE)
    result = []
    seen = set()
    for url in found:
        if matcher.search(url) and url not in seen:
            seen.add(url)
            result.append(url)
    return result


def fetch_feed(feed_url, timeout=30):
    """Fetch and parse the software feed."""
    return parse_feed(fetch(feed_url, timeout))


def fetch_article_links(url, pattern=DEFAULT_LINK_PATTERN, timeout=30):
    """Fetch one article and return its direct download links.

    Used only for entries that land in the review queue, never for every item.
    """
    return extract_file_links(fetch(url, timeout), pattern)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd F:\-SAM-\WWW\samlab.ws_bot; python -m pytest tests/test_kaldata.py -v`
Expected: all passed.

- [ ] **Step 5: Verify the real feed end-to-end, once**

```powershell
cd F:\-SAM-\WWW\samlab.ws_bot
python -c "import kaldata,json; items=kaldata.fetch_feed('https://www.kaldata.com/%D1%81%D0%BE%D1%84%D1%82%D1%83%D0%B5%D1%80/feed'); print(len(items)); print(items[0]['title'], items[0]['guid'])"
```
Expected: `50` on the first line and a REAPER entry on the second. If the count differs, the feed window changed; that is fine, the bot must not depend on a fixed count.

- [ ] **Step 6: Commit**

```powershell
cd F:\-SAM-\WWW\samlab.ws_bot
git add kaldata.py tests/test_kaldata.py
git commit -m "feat: fetch kaldata rss feed and article download links"
```

---

### Task 6: Orchestration, state, and reporting

**Files:**
- Create: `F:\-SAM-\WWW\samlab.ws_bot\run.py`
- Create: `F:\-SAM-\WWW\samlab.ws_bot\tests\test_run.py`

**Interfaces:**
- Consumes: `version` (Task 2), `match` (Task 3), `iniwrite` (Task 4), `kaldata` (Task 5).
- Produces:
  - `load_config(path) -> dict`
  - `load_aliases(path) -> dict`
  - `list_slugs(soft_dir) -> list[str]`
  - `load_state(path) -> dict` returns `{"seen_guids": [...]}`; missing or unreadable file yields empty.
  - `save_state(path, state)` dedupes and writes atomically.
  - `plan_entry(entry, slugs, aliases, soft_dir) -> dict` returns a decision dict with keys `action` (`update`, `skip`, `queue`), `reason`, `slug`, `old_version`, `new_version`, `title`. It reads the matched `.ini` to learn the current Final-track version but performs no writes.
  - `append_review(path, lines) -> int` appends text to the review queue and returns the line count.
  - `build_slug_names(soft_dir, slugs) -> dict` maps each slug to its normalized `name=`, read once per cycle. An unreadable file yields `""` for its own entry rather than aborting the run.
  - `run(config, aliases, apply, now=None) -> dict` returns a summary with keys `seen`, `new_entries`, `updated`, `would_update`, `queued`, `skipped`, `errors`, `review_appended`, `unmatched`. State is persisted **only** when `apply` is true, so a dry-run never consumes the entries a later `--apply` run still needs.
  - `unmatched` counts titles that no `.ini` of ours claims. They are appended to `needs-review.txt` with the reason and the exact `aliases.json` key to add, and their article page is **not** downloaded: there is no file to put a link into. Dedup is against the review file rather than `state.json`, because a dry-run never persists state and would otherwise re-append every entry on every run.
  - `main(argv=None) -> int` CLI entry, returns process exit code.

- [ ] **Step 1: Write the failing tests**

`F:\-SAM-\WWW\samlab.ws_bot\tests\test_run.py`

```python
import os

import pytest

import kaldata
import run as bot


def _ini(name_value):
    return (
        "[info]\r\nname=%s\r\n[link_5]\r\ntitle=x\r\n"
        "link=https://e.org/f-1.0.exe\r\n" % name_value
    )


@pytest.fixture
def soft_dir(tmp_path):
    """A tiny catalog where each file carries a deliberately different name."""
    d = tmp_path / "soft"
    d.mkdir()
    files = {
        # plain Final-track name, the normal case
        "reaper": _ini("Foo 1.0"),
        # only a Beta track: nothing to compare against, must be queued
        "aimp": _ini('"AIMP SamLab 5.60 Beta"'),
        "fruityloops": _ini("Foo 1.0"),
    }
    for slug, text in files.items():
        (d / (slug + ".ini")).write_bytes(text.encode("cp1251"))
    return str(d)


def _config(soft_dir, tmp_path):
    return {
        "soft_dir": soft_dir,
        "feed_url": "https://k/x/feed",
        "review_path": str(tmp_path / "review.txt"),
        "state_path": str(tmp_path / "state.json"),
    }


def _entry(title, link, guid):
    return {"title": title, "link": link, "guid": guid, "pub_date": ""}


def _feed(*items):
    return lambda url, timeout=30: list(items)


class TestPlanEntry:
    def test_newer_version_plans_update(self, soft_dir):
        got = bot.plan_entry(
            _entry("REAPER 7.83 Final", "https://k/x/reaper-1.html", "1"),
            {"reaper"}, {}, soft_dir,
        )
        assert got["action"] == "update"
        assert got["slug"] == "reaper"
        assert got["old_version"] == "1.0"
        assert got["new_version"] == "7.83"

    def test_same_version_skips(self, soft_dir):
        got = bot.plan_entry(
            _entry("Foo 1.0", "https://k/x/reaper-1.html", "1"), {"reaper"}, {}, soft_dir,
        )
        assert got["action"] == "skip"
        assert got["reason"] == "not-newer"

    def test_rollback_skips(self, soft_dir):
        got = bot.plan_entry(
            _entry("Foo 0.9", "https://k/x/reaper-1.html", "1"), {"reaper"}, {}, soft_dir,
        )
        assert got["action"] == "skip"
        assert got["reason"] == "not-newer"

    def test_banned_title_skips(self, soft_dir):
        got = bot.plan_entry(
            _entry("Foo 9.9 Crack", "https://k/x/1.html", "1"), {"foo"}, {}, soft_dir,
        )
        assert got["action"] == "skip"
        assert got["reason"] == "banned"

    def test_two_version_title_skips(self, soft_dir):
        got = bot.plan_entry(
            _entry("Foo 4.27 / 3.95 Final", "https://k/x/1.html", "1"), {"foo"}, {}, soft_dir,
        )
        assert got["action"] == "skip"
        assert got["reason"] == "two-versions"

    def test_beta_only_source_skips(self, soft_dir):
        got = bot.plan_entry(
            _entry("Foo 9.9 Beta 2", "https://k/x/1.html", "1"), {"foo"}, {}, soft_dir,
        )
        assert got["action"] == "skip"
        assert got["reason"] == "not-final-channel"

    def test_unparseable_version_skips(self, soft_dir):
        got = bot.plan_entry(
            _entry("FooBarBaz 1", "https://k/x/1.html", "1"), {"foo"}, {}, soft_dir,
        )
        assert got["action"] == "skip"
        assert got["reason"] == "no-version"

    def test_no_matching_ini_skips(self, soft_dir):
        got = bot.plan_entry(
            _entry("RustDesk 1.5.0", "https://k/x/rustdesk-1.html", "1"),
            {"reaper", "aimp"}, {}, soft_dir,
        )
        assert got["action"] == "skip"
        assert got["reason"] == "no-match"

    def test_our_file_without_final_track_queues(self, soft_dir):
        # the title parses fine, but our own file only has a Beta track
        got = bot.plan_entry(
            _entry("AIMP 5.61 Final", "https://k/x/aimp-1.html", "1"), {"aimp"}, {}, soft_dir,
        )
        assert got["action"] == "queue"
        assert got["reason"] == "no-final-track"


class TestState:
    def test_missing_file_is_empty(self, tmp_path):
        assert bot.load_state(str(tmp_path / "nope.json")) == {"seen_guids": []}

    def test_roundtrip(self, tmp_path):
        p = str(tmp_path / "state.json")
        bot.save_state(p, {"seen_guids": ["a", "b"]})
        assert bot.load_state(p) == {"seen_guids": ["a", "b"]}

    def test_duplicate_guid_written_once(self, tmp_path):
        p = str(tmp_path / "state.json")
        bot.save_state(p, {"seen_guids": ["a", "a", "b"]})
        assert bot.load_state(p)["seen_guids"] == ["a", "b"]


class TestRunDry:
    def test_dry_run_changes_nothing(self, soft_dir, tmp_path, monkeypatch):
        monkeypatch.setattr(bot.kaldata, "fetch_feed", _feed(
            _entry("REAPER 7.83 Final", "https://k/x/reaper-1.html", "g1"),
        ))
        path = os.path.join(soft_dir, "reaper.ini")
        before = open(path, "rb").read()

        summary = bot.run(_config(soft_dir, tmp_path), {}, apply=False)

        assert summary["updated"] == 0
        assert summary["would_update"] == 1
        assert open(path, "rb").read() == before
        assert not os.path.exists(path + ".bak")

    def test_dry_run_does_not_consume_the_state(self, soft_dir, tmp_path, monkeypatch):
        # a dry-run must leave the work for the eventual --apply run
        monkeypatch.setattr(bot.kaldata, "fetch_feed", _feed(
            _entry("REAPER 7.83 Final", "https://k/x/reaper-1.html", "g1"),
        ))
        config = _config(soft_dir, tmp_path)

        bot.run(config, {}, apply=False)
        assert not os.path.exists(config["state_path"])
        assert bot.run(config, {}, apply=True)["updated"] == 1

    def test_apply_writes(self, soft_dir, tmp_path, monkeypatch):
        monkeypatch.setattr(bot.kaldata, "fetch_feed", _feed(
            _entry("REAPER 7.83 Final", "https://k/x/reaper-1.html", "g1"),
        ))

        summary = bot.run(_config(soft_dir, tmp_path), {}, apply=True)

        assert summary["updated"] == 1
        path = os.path.join(soft_dir, "reaper.ini")
        text = open(path, "rb").read().decode("cp1251")
        assert "name=Foo 7.83" in text
        assert "f-7.83.exe" in text
        assert os.path.exists(path + ".bak")

    def test_seen_guid_not_reprocessed(self, soft_dir, tmp_path, monkeypatch):
        monkeypatch.setattr(bot.kaldata, "fetch_feed", _feed(
            _entry("REAPER 7.83 Final", "https://k/x/reaper-1.html", "g1"),
        ))
        config = _config(soft_dir, tmp_path)
        bot.run(config, {}, apply=True)
        second = bot.run(config, {}, apply=True)
        assert second["new_entries"] == 0

    def test_feed_failure_is_reported(self, soft_dir, tmp_path, monkeypatch):
        def boom(url, timeout=30):
            raise RuntimeError("empty response body")
        monkeypatch.setattr(bot.kaldata, "fetch_feed", boom)

        summary = bot.run(_config(soft_dir, tmp_path), {}, apply=False)

        assert summary["errors"] == 1
        assert summary["new_entries"] == 0


class TestReviewQueue:
    def test_queue_entry_appended(self, soft_dir, tmp_path, monkeypatch):
        # our reaper.ini version cannot be put into the URL, so it is queued
        monkeypatch.setattr(bot.kaldata, "fetch_feed", _feed(
            _entry("REAPER 7.83 Final", "https://k/x/reaper-1.html", "g1"),
        ))
        monkeypatch.setattr(bot.kaldata, "fetch_article_links",
                            lambda url, pattern=None, timeout=30:
                            ["https://vendor.example/reaper783.exe"])
        config = _config(soft_dir, tmp_path)
        review = tmp_path / "review.txt"
        review.write_text("PREVIOUS ENTRY\n", encoding="utf-8")

        # force the no-URL-change path: the fixture link carries 1.0, not 7.82
        with open(os.path.join(soft_dir, "reaper.ini"), "wb") as fh:
            fh.write(b"[info]\r\nname=Foo 7.82\r\n[link_5]\r\n"
                     b"link=https://vendor.example/app.exe\r\n")

        summary = bot.run(config, {}, apply=False)

        assert summary["would_update"] == 0
        assert summary["queued"] == 1
        text = review.read_text(encoding="utf-8")
        assert "PREVIOUS ENTRY" in text
        assert "reaper783.exe" in text
        assert "reaper" in text
        # the reason must be spelled out, not left blank
        assert "could not be put into our download URLs" in text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd F:\-SAM-\WWW\samlab.ws_bot; python -m pytest tests/test_run.py -v`
Expected: `ModuleNotFoundError: No module named 'run'`.

- [ ] **Step 3: Implement `run.py`**

```python
"""Bot entry point: poll kaldata, update our .ini files, queue the rest.

Dry-run is the default. Without ``--apply`` nothing is written to any .ini and
the run only produces a report, so the first cron schedule can be installed
with confidence.
"""

import argparse
import datetime
import json
import os
import sys
import tempfile

import iniwrite
import kaldata
import match
import version

REASONS = {
    "not-newer": "kaldata version is not newer than ours",
    "banned": "title advertises crack/keygen/repack",
    "two-versions": "title carries two versions separated by a slash",
    "no-version": "no parseable version in the title",
    "not-final-channel": "source is a beta/dev build; only the Final track is updated",
    "no-match": "no matching .ini in our catalog",
    "no-url-change": "the new version could not be put into our download URLs; nothing was written",
    "no-final-track": "our own name has no Final-track version to compare against",
}

# Reasons that are a normal outcome and need no human. Everything else in
# REASONS is a question for someone: we could not place the article, or we could
# not act on it safely.
ACTIONABLE_REASONS = ("no-match", "no-final-track", "no-url-change")


def load_config(path):
    # utf-8-sig so a file saved by Windows PowerShell, which writes a BOM by
    # default, still loads instead of dying on the first byte.
    with open(path, "r", encoding="utf-8-sig") as fh:
        return json.load(fh)


def load_aliases(path):
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8-sig") as fh:
        return json.load(fh)


def list_slugs(soft_dir):
    return sorted(
        name[:-4] for name in os.listdir(soft_dir) if name.endswith(".ini")
    )


def build_slug_names(soft_dir, slugs):
    """Map each slug to the normalized ``name=`` of its file.

    ``find_match`` needs this to notice a kaldata title that two of our files
    both answer to. Without it a title like "Foo 2.0 Final" would be rewritten
    into whichever file happened to sort first.
    """
    names = {}
    for slug in slugs:
        path = os.path.join(soft_dir, slug + ".ini")
        try:
            text = iniwrite.read_ini(path)
            names[slug] = match.normalize(iniwrite.current_name(text))
        except (OSError, UnicodeDecodeError):
            # An unreadable file must not stop the whole run; it simply cannot
            # contribute a name, which only makes the ambiguity check weaker for
            # that one slug.
            names[slug] = ""
    return names


def load_state(path):
    if not os.path.exists(path):
        return {"seen_guids": []}
    try:
        with open(path, "r", encoding="utf-8-sig") as fh:
            state = json.load(fh)
    except (ValueError, OSError):
        return {"seen_guids": []}
    state.setdefault("seen_guids", [])
    return state


def save_state(path, state):
    seen = sorted(set(state.get("seen_guids", [])))
    state["seen_guids"] = seen
    directory = os.path.dirname(os.path.abspath(path))
    fd, tmp_path = tempfile.mkstemp(dir=directory, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(state, fh, ensure_ascii=False, indent=2)
        os.replace(tmp_path, path)
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


def plan_entry(entry, slugs, aliases, soft_dir, slug_names=None):
    """Decide what to do with one kaldata article.

    Reads the matched ``.ini`` to learn its current Final-track version, but
    never writes anything.

    ``slug_names`` maps each slug to the ``name=`` of its file so ``find_match``
    can refuse a title two of our files share; it defaults to an empty map,
    which only disables that check and is meant for callers that already hold
    it.
    """
    title = entry.get("title", "")
    link = entry.get("link", "")
    result = {"action": "skip", "reason": "", "slug": None,
              "old_version": None, "new_version": None, "title": title}

    if version.has_banned_words(title):
        result["reason"] = "banned"
        return result

    if version.has_slash_versions(title):
        result["reason"] = "two-versions"
        return result

    _clean, channel = version.split_channel(title)
    if channel != "final":
        result["reason"] = "not-final-channel"
        return result

    offsets = version.find_versions(title)
    if not offsets:
        result["reason"] = "no-version"
        return result

    new_version = title[offsets[0][0]:offsets[0][1]]
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


def _already_reported(path, titles):
    """Titles this file already mentions.

    A dry-run never persists ``state.json``, so every dry-run re-examines the
    whole feed and would otherwise append the same 50 entries every time. The
    file is the durable record, so it is what decides what is new.
    """
    if not titles or not os.path.exists(path):
        return set()
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            body = fh.read()
    except OSError:
        return set()
    return {title for title in titles if title and title in body}


def append_review(path, lines):
    if not lines:
        return 0
    with open(path, "a", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    return len(lines)


def run(config, aliases, apply, now=None):
    """Execute one polling cycle and return a summary dict.

    With ``apply=False`` no ``.ini`` is opened for writing and the state file is
    left alone, so reviewing a dry-run never consumes the work.
    """
    soft_dir = config["soft_dir"]

    summary = {
        "seen": 0, "new_entries": 0, "updated": 0, "would_update": 0,
        "queued": 0, "skipped": 0, "errors": 0, "review_appended": 0,
        "unmatched": 0,
    }
    stamp = (now or datetime.datetime.now()).strftime("%Y-%m-%d %H:%M")
    review_lines = []

    try:
        entries = kaldata.fetch_feed(config["feed_url"])
    except Exception as exc:
        summary["errors"] = 1
        summary["review_appended"] = append_review(config["review_path"], [
            "%s FEED ERROR: %s" % (stamp, exc),
        ])
        return summary

    summary["seen"] = len(entries)
    state = load_state(config["state_path"])
    seen = set(state["seen_guids"])

    fresh = [e for e in entries if (e.get("guid") or e.get("link")) not in seen]
    summary["new_entries"] = len(fresh)
    slug_set = set(list_slugs(soft_dir))
    # match.find_match needs our own names to detect a title that two of our
    # files share, which is how an ambiguous article gets refused instead of
    # resolved by guesswork
    slug_names = build_slug_names(soft_dir, slug_set)

    reported = _already_reported(
        config["review_path"], [e.get("title", "") for e in fresh]
    )

    for entry in fresh:
        guid = entry.get("guid") or entry.get("link")
        try:
            decision = plan_entry(entry, slug_set, aliases, soft_dir, slug_names)
        except Exception as exc:
            summary["errors"] += 1
            review_lines.append("%s ERROR on %r: %s" % (stamp, entry.get("title"), exc))
            continue

        action = decision["action"]
        if action == "skip":
            summary["skipped"] += 1
            # A title we cannot place is the one outcome that needs a decision:
            # either we do not carry the program, or our file is named
            # differently and an alias would fix it. Without this line the only
            # trace is a counter in stdout, and no alias ever gets written.
            if (decision["reason"] in ACTIONABLE_REASONS
                    and decision["title"] not in reported):
                summary["unmatched"] += 1
                reported.add(decision["title"])
                review_lines.extend(_unmatched_block(stamp, decision, entry))
        elif action == "queue":
            summary["queued"] += 1
            review_lines.extend(_review_block(stamp, decision, entry, config))
        else:
            path = os.path.join(soft_dir, decision["slug"] + ".ini")
            result = iniwrite.update_ini(
                path, decision["old_version"], decision["new_version"], write=apply
            )
            if not result["changed"]:
                # the version could not be put into the download URLs
                summary["queued"] += 1
                decision["reason"] = "no-url-change"
                review_lines.extend(_review_block(stamp, decision, entry, config))
            elif apply:
                summary["updated"] += 1
            else:
                summary["would_update"] += 1

        seen.add(guid)

    summary["review_appended"] = append_review(config["review_path"], review_lines)
    if apply:
        state["seen_guids"] = sorted(seen)
        save_state(config["state_path"], state)
    return summary


def _unmatched_block(stamp, decision, entry):
    """Review text for a title no .ini of ours claims.

    No article download is attempted: there is no file of ours to put a link
    into, so fetching the page would cost a request and produce a suggestion
    with nowhere to go.
    """
    lines = [
        "",
        "%s  %s" % (stamp, decision["title"]),
        "    our file : (none matched)",
        "    theirs   : %s" % (decision["new_version"] or "unknown"),
        "    reason   : %s" % REASONS.get(decision["reason"], decision["reason"]),
    ]
    key = match.normalize(entry.get("title", ""))
    if key:
        lines.append(
            "    if we do carry it under another name, add to aliases.json: %r: <slug>"
            % key
        )
    return lines


def _review_block(stamp, decision, entry, config):
    """Build the review-queue text for one entry that could not be auto-updated."""
    pattern = config.get("review_link_pattern", kaldata.DEFAULT_LINK_PATTERN)
    lines = [
        "",
        "%s  %s" % (stamp, decision["title"]),
        "    our file : soft/%s.ini" % decision["slug"],
    ]
    if decision["old_version"]:
        lines.append("    our ver  : %s" % decision["old_version"])
    lines.append("    theirs   : %s" % (decision["new_version"] or "unknown"))
    lines.append("    reason   : %s" % REASONS.get(decision["reason"], decision["reason"]))

    try:
        links = kaldata.fetch_article_links(entry["link"], pattern)
    except Exception as exc:
        lines.append("    article  : fetch failed (%s)" % exc)
        return lines

    if links:
        lines.append("    suggestions (NOT written to the ini):")
        for url in links[:6]:
            lines.append("      - %s" % url)
    else:
        lines.append("    suggestions: no direct download links found")
    return lines


def main(argv=None):
    parser = argparse.ArgumentParser(description="Update samlab.ws versions from kaldata")
    parser.add_argument("--apply", action="store_true",
                        help="actually write changes; without this the run is a dry-run")
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--aliases", default="aliases.json")
    args = parser.parse_args(argv)

    config = load_config(args.config)
    aliases = load_aliases(args.aliases)
    summary = run(config, aliases, args.apply)

    mode = "APPLY" if args.apply else "DRY-RUN"
    print(
        "[%s] seen=%d new=%d updated=%d would_update=%d queued=%d skipped=%d "
        "unmatched=%d errors=%d"
        % (
            mode, summary["seen"], summary["new_entries"], summary["updated"],
            summary["would_update"], summary["queued"], summary["skipped"],
            summary["unmatched"], summary["errors"],
        )
    )

    return 1 if summary["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd F:\-SAM-\WWW\samlab.ws_bot; python -m pytest tests/test_run.py -v`
Expected: all passed.

- [ ] **Step 5: Run the full suite**

Run: `cd F:\-SAM-\WWW\samlab.ws_bot; python -m pytest -v`
Expected: all pass.

- [ ] **Step 6: Commit**

```powershell
cd F:\-SAM-\WWW\samlab.ws_bot
git add run.py tests/test_run.py
git commit -m "feat: orchestrate polling, dry-run reporting and the review queue"
```

---

### Task 7: First live dry-run against the real catalog

**Files:**
- Modify: `F:\-SAM-\WWW\samlab.ws_bot\config.json` (no change expected — add a note field only if useful)
- Create: `F:\-SAM-\WWW\samlab.ws_bot\RUNBOOK.md`

**Interfaces:**
- Consumes: `run.main` (Task 6).
- Produces: `RUNBOOK.md` with deployment and cron instructions.

- [ ] **Step 1: Back up the real `soft/` directory before any live run**

```powershell
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
Copy-Item -Recurse "F:\-SAM-\WWW\samlab.ws\soft" "F:\-SAM-\WWW\samlab.ws_bot\soft-backup-$stamp"
```

- [ ] **Step 2: Run the bot in dry-run mode against the real catalog**

```powershell
cd F:\-SAM-\WWW\samlab.ws_bot
python run.py --config config.json
```
Expected: a single `[DRY-RUN] seen=50 new=50 ...` line. Confirm `would_update` and `queued` are plausible and `errors` is 0.

Measured on the first real run: `seen=50 new=50 updated=0 would_update=0 queued=0 skipped=50 unmatched=29 errors=0`. Zero updates is the expected result — every one of our 18 matching files was already at the kaldata version. The 29 `unmatched` entries are programs we do not carry.

- [ ] **Step 3: Inspect the review queue**

```powershell
Get-Content F:\-SAM-\WWW\samlab.ws_bot\needs-review.txt -TotalCount 60
```
Expected: human-readable blocks, one per un-updatable entry. Each unmatched block
also prints the exact `aliases.json` key to add, so no separate `normalize` call is
needed. Confirm no file in `soft/` was modified:

```powershell
(Get-ChildItem "F:\-SAM-\WWW\samlab.ws\soft\*.bak" | Measure-Object).Count
(Get-ChildItem "F:\-SAM-\WWW\samlab.ws\soft\*.tmp" | Measure-Object).Count
```
Expected: `0` and `0`.

Note that a dry-run never persists `state.json`, so a second dry-run re-examines the
whole feed. Dedup for `needs-review.txt` is therefore done against the file itself,
not against state: without it every dry-run would re-append all 50 entries.

- [ ] **Step 4: Add aliases for the first round of mismatches**

For each line in `needs-review.txt` whose reason is `no-match` but which clearly corresponds to a program we do carry (e.g. `FL Studio` → `fruityloops`), add an entry to `aliases.json`:

```json
{
  "flstudio": "fruityloops",
  "malwarebytesantimalware": "antimalwarem"
}
```

Keys must be produced by `match.normalize(title)`.

Six were added from the first run, each verified by reading the candidate `.ini`
and confirming its `name=` really is that program: `shark007codecs` → `win8codecs`,
`malwarebytesantimalware` → `antimalwarem`, `mozillathunderbird` → `thunderbird`,
`foobar2000` → `foobar`, `flstudio` → `fruityloops`,
`wysiwygwebbuilder` → `wysiwyg`. All six then resolved to `not-newer`, i.e. our
files already carry those versions.

Do not add an alias on the strength of a fuzzy name match. In the same run
`Virtual DJ Studio` scored closest to `virtualcd`, `Arc` matched `freearc`, and
`Advanced Renamer` matched `syscare` — none of which is the same program.

- [ ] **Step 5: Re-run the dry-run with the new aliases**

A dry-run never writes `state.json`, so every run re-examines the whole feed and
the new aliases take effect immediately.

```powershell
Remove-Item F:\-SAM-\WWW\samlab.ws_bot\state.json -ErrorAction SilentlyContinue
python run.py --config config.json
```

- [ ] **Step 6: Write `RUNBOOK.md`**

```markdown
# SamLab.ws version updater — runbook

## What it does

Polls the kaldata.com software RSS feed, finds articles for programs already in
`soft/*.ini`, and rewrites the version plus download URLs in place. Anything it
cannot update safely is written to `needs-review.txt` instead of being applied.

## Files

| file | purpose |
|---|---|
| `run.py` | entry point |
| `version.py` | version parsing, channel detection, numeric comparison |
| `match.py` | maps kaldata titles to our `.ini` slugs |
| `iniwrite.py` | cp1251 read/write, atomic replace, backup |
| `kaldata.py` | RSS and article fetching |
| `config.json` | paths |
| `aliases.json` | manual title → slug overrides |
| `state.json` | already-seen article guids; written only by `--apply` runs |
| `needs-review.txt` | queue of entries needing a human |
| `cron.log` | cron run history |

## Running

Dry run (default, writes nothing to any `.ini` and does not touch `state.json`):

    python3 run.py --config config.json

Apply for real:

    python3 run.py --config config.json --apply

## Cron

In the hosting panel, every 6 hours:

    0 */6 * * *  cd /home/USER/samlab.ws_bot && python3 run.py --config config.json >> cron.log 2>&1

Start with the dry-run form above. Only change it to `--apply` after reviewing
several dry-run reports.

## Safety

- Every modified `.ini` is backed up to `<name>.ini.bak` before writing.
- Writes are atomic: temp file plus rename.
- Only `[link_N]` sections are rewritten. `[linkN]` sections are hidden reserves
  and are left untouched by design.
- A version bump is refused unless it also lands in the download URLs, so the
  page never advertises a build the links do not serve.
- `.short`, `.long` and screenshots are never touched.
- Versions are never rolled back.
- A dry-run records nothing, so reviewing reports cannot swallow a pending update.

## Recovering

Restore one file:

    cp soft/reaper.ini.bak soft/reaper.ini

Restore everything:

    rsync -a soft-backup-YYYYMMDD-HHMMSS/ soft/

## Adding aliases

When `needs-review.txt` reports `no-match` for a program we do carry, add its
normalized title to `aliases.json`:

    python3 -c "import match; print(match.normalize('FL Studio 26.1.7.5653 Final'))"

Then map that key to our slug.
```

- [ ] **Step 7: Commit**

```powershell
cd F:\-SAM-\WWW\samlab.ws_bot
git add aliases.json RUNBOOK.md
git commit -m "docs: runbook for deploying and operating the updater"
```

---

### Task 8: Deploy to the server

**Files:**
- Create on server: `/home/<user>/samlab.ws_bot/` (all `.py`, `config.json`, `aliases.json`)

**Interfaces:**
- Consumes: everything from Tasks 1–7.
- Produces: a running cron job.

- [ ] **Step 1: Confirm the server's `soft/` absolute path**

Ask the hosting panel, or read it from an existing script. The site root is the
directory containing `index.php`, `config.php` and `templates/`.

- [ ] **Step 2: Upload the bot outside the web root**

Upload `.py` files, `config.json` and `aliases.json` to `/home/<user>/samlab.ws_bot/`.
Do not upload `tests/` or `fixtures/`. Confirm no bot file landed inside the web
root.

- [ ] **Step 3: Point `config.json` at the real paths**

```json
{
  "soft_dir": "/home/USER/www/samlab.ws/soft",
  "feed_url": "https://www.kaldata.com/%D1%81%D0%BE%D1%84%D1%82%D1%83%D0%B5%D1%80/feed",
  "review_path": "/home/USER/samlab.ws_bot/needs-review.txt",
  "state_path": "/home/USER/samlab.ws_bot/state.json",
  "review_link_pattern": "\\.(exe|msi|zip|7z|rar|dmg|tgz|deb)$"
}
```

- [ ] **Step 4: Verify write permissions**

```bash
touch /home/USER/www/samlab.ws/soft/.write-test && rm /home/USER/www/samlab.ws/soft/.write-test
```
Expected: no output, exit code 0.

- [ ] **Step 5: Verify Python and run one manual dry-run**

```bash
python3 --version
cd /home/USER/samlab.ws_bot && python3 run.py --config config.json
```
Expected: the `[DRY-RUN] ...` summary line with `errors=0`.

- [ ] **Step 6: Install the cron job in the hosting panel**

Schedule `0 */6 * * *`, command:

```
cd /home/USER/samlab.ws_bot && python3 run.py --config config.json >> cron.log 2>&1
```

Leave it in dry-run for the first few cycles. Switch to `--apply` only after
reading `needs-review.txt` and confirming the reports look right.

- [ ] **Step 7: Back up `soft/` on the server once, before switching to `--apply`**

```bash
tar czf /home/USER/samlab-soft-$(date +%Y%m%d).tar.gz -C /home/USER/www samlab.ws/soft
```
