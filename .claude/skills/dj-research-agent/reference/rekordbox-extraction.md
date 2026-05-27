# Rekordbox cued-tracks extraction

Two scripts pull the user's already-cued tracks out of rekordbox so they can seed set-building. They produce the same JSON shape — downstream tooling shouldn't care which source produced it.

## When to use which

- **`extract_cued_from_db.py`** — read the live `master.db`. Always current. Default choice. Needs the bundled venv (`pyrekordbox`).
- **`extract_cued_from_xml.py`** — read a `rekordbox-export.xml` the user has exported (File → Export Collection in XML format). Stdlib only, no venv needed. Use when the venv is unavailable, or when the user wants to extract from a historical export. Will lag behind the DB until re-exported.

The DB script is the source of truth; the XML script is a fallback / archival reader.

## Running them

```bash
# DB (live):
.claude/skills/dj-research-agent/.venv/bin/python \
  .claude/skills/dj-research-agent/scripts/extract_cued_from_db.py \
  --min-hot-cues 2 \
  --genre-folder "Telugu 9XM" \
  > /tmp/cued.json

# XML (export-based):
python3 .claude/skills/dj-research-agent/scripts/extract_cued_from_xml.py \
  --xml rekordbox-export.xml \
  --min-hot-cues 2 \
  --genre-folder "Telugu 9XM" \
  > /tmp/cued.json
```

Both default `--library-root` to `~/Desktop/DJ-Music` (matches the repo's library layout). The `library_genre_folder` field on each track comes from the immediate sub-folder of the library root — that's what `--genre-folder` filters on.

Both write JSON to stdout, errors to stderr, non-zero exit on failure (per the repo's script contract).

## Output shape

```jsonc
{
  "source": "db" | "xml",
  "source_path": "...",
  "exported_at": "2026-05-27T...",
  "filter": { "min_hot_cues": 2, "genre_folder": "Telugu 9XM" },
  "library_root": "/Users/arunchaitanya/Desktop/DJ-Music",
  "total_tracks": 16,
  "tracks": [
    {
      "track_id": "...",
      "title": "Yenti Yenti Audio",
      "artists": "...",
      "album": "...",
      "genre": "...",                  // rekordbox Genre field (often the film name)
      "bpm": 75.0,
      "key": "D",                       // Camelot/Tonality letter
      "duration_sec": 195,
      "file_path": "/Users/.../DJ-Music/Telugu 9XM/...mp3",
      "library_genre_folder": "Telugu 9XM",
      "rating": null,
      "play_count": 1,
      "date_added": "2025-..",
      "hot_cues": [
        { "num": 0, "start_sec": 5.972, "name": "", "color": "#ff376f" }
      ],
      "memory_cues": [...],
      "loops": [...]
    }
  ]
}
```

## Why hot-cue count > 1 by default

A single hot cue often gets auto-set to the first downbeat by analysis. ≥ 2 means the user actually placed cues — typically intro / mix-in / drop / outro markers. Adjust with `--min-hot-cues` if needed.

## Notes on quirks

- **DB BPM is `bpm * 100` as an int.** The script divides by 100 before emitting.
- **XML cue Type vs DB Kind.** XML uses `Type=0` for cue / `Type=4` for loop, and `Num=-1` for memory. DB uses `Kind` (a label) plus `is_hot_cue` / `is_memory_cue` booleans, with `OutMsec > 0` flagging loops. Output normalizes both into separate `hot_cues` / `memory_cues` / `loops` arrays.
- **pyrekordbox prints `{}` to stdout** during queries. The DB script wraps DB calls in `contextlib.redirect_stdout` so the JSON output stays clean.
- **Rekordbox can stay open** while running the DB reader — pyrekordbox just warns. Don't try to *write* while it's open, but read is fine.
- **Stale XML exports**: if the XML count is lower than the DB count, the user just hasn't re-exported. Tell them to File → Export Collection in XML format.

## Setting up the venv (one-time)

```bash
python3.13 -m venv .claude/skills/dj-research-agent/.venv
.claude/skills/dj-research-agent/.venv/bin/pip install pyrekordbox
```

Python 3.14 on this machine has a broken pyexpat — use 3.13. The venv is gitignored.

---

# Writing cues into rekordbox

The `set_cue.py` and `bulk_cue_from_json.py` scripts use the same DB connection as the readers above to *write* hot cues. See SKILL.md → "Write hot cues into rekordbox" for usage. This section documents the rekordbox internals the writers rely on.

## Slot encoding

Hot cues A..H map to `DjmdCue.Kind` 1..8. Memory cues use `Kind` 0 (not exposed by these scripts yet). Loops use the same `DjmdCue` row but set `OutMsec > 0` (also not exposed yet).

## Color encoding

`DjmdCue.Color` is one int from the rekordbox palette. Mapping (we expose by name):

| name | int |
|---|---|
| pink | 0 |
| orange | 1 |
| yellow | 2 |
| green | 3 |
| blue | 4 |
| purple | 5 |
| red | 6 |
| none | -1 |

Free hex colors are not supported by rekordbox at the cue level — you pick from this palette.

## DjmdCue NOT NULL fields we set on insert

Most `DjmdCue` columns are declared NOT NULL but accept zero / empty-string in practice (we observed real rows with `None` for several of them). To stay safe we explicitly set:

- `ID` — random 10-digit string (rekordbox uses a similar opaque ID)
- `ContentID` — the track's `DjmdContent.ID`
- `ContentUUID` — the track's `DjmdContent.UUID` (rekordbox uses this to match cues across libraries)
- `UUID` — a fresh `uuid.uuid4()` for the cue itself
- `InMsec` — start time in milliseconds (int)
- `OutMsec` — `-1` for point cues, `> 0` for loops
- `InFrame`, `InMpegFrame`, `InMpegAbs`, `OutFrame`, `OutMpegFrame`, `OutMpegAbs` — `0` (per-format analysis offsets; rekordbox recomputes from `InMsec` when loading)
- `Kind` — slot (1..8 for hot cues A..H)
- `Color` — int from palette above
- `ActiveLoop` — `0`
- `Comment` — cue label (empty string if none)
- `BeatLoopSize` — `0`
- `CueMicrosec` — `0`
- `InPointSeekInfo`, `OutPointSeekInfo` — empty string

`created_at` / `updated_at` are populated by the model's default callable.

## Transaction semantics

`pyrekordbox` uses SQLAlchemy. Both writers:
1. Open the session (read-only ops first).
2. Resolve and validate the plan against the current state — fails fast on collisions / missing slots / unknown tracks.
3. Stage all inserts/updates/deletes.
4. Call `db.commit()`. On exception, `db.rollback()`.

The bulk writer commits the whole plan as one transaction — if any op validation fails, nothing is written. Once a `commit()` succeeds, the cues are immediately readable by the next rekordbox launch.

## Safety wrapper

Both writers refuse to commit if `pgrep rekordbox` finds the app running (exit code 2). `--force` overrides — only use it if you understand that running rekordbox can overwrite your changes on its next save cycle.

Before every commit, `master.db` is copied to `master.db.bak-<YYYYMMDD-HHMMSS>` in the same folder. To restore: quit rekordbox, `cp <backup> ~/Library/Pioneer/rekordbox/master.db`.

## What we deliberately don't do (yet)

- **No memory-cue writing.** Hot cues only — that's the immediate need.
- **No loop writing.** `OutMsec` is forced to `-1` (point cue). Add loop support when `analyze_structure` needs it.
- **No write to ANLZ binary files.** The `master.db` is the source of truth for the laptop; ANLZ matters only for USB export to CDJs. Address when relevant.
- **No multi-library / Cloud sync handling.** If the user uses rekordbox Cloud, writes only apply locally — Cloud sync may overwrite. Pre-flight: ask before enabling on a Cloud-synced setup.

---

# Reading the beat grid + phrase structure

`phrase_grid.py` extracts rekordbox's per-track analyzer output: beat positions (PQTZ tag, in the `.DAT` file) and phrase/section labels (PSSI tag, in the `.EXT` file). Read-only; safe while rekordbox is open. This is the rekordbox-side input that the future `analyze_structure` module fuses with YouTube heatmap data to produce cue plans.

## Where the ANLZ files live

`DjmdContent.AnalysisDataPath` is a PIONEER-relative path like `/PIONEER/USBANLZ/<aa>/<bbbbbbb-...uuid>/ANLZ0000.DAT`. Resolve it by prepending `~/Library/Pioneer/rekordbox/share`. The folder contains `ANLZ0000.DAT` (beat grid + cues + waveform v1), `ANLZ0000.EXT` (extended beats + song structure + waveform v2), and sometimes `ANLZ0000.2EX` / `ANLZ0000.3EX`.

## Running the script

```bash
.claude/skills/dj-research-agent/.venv/bin/python \
  .claude/skills/dj-research-agent/scripts/phrase_grid.py \
  --track-id 67810230 > /tmp/grid.json
```

## Output shape

```jsonc
{
  "track": {
    "track_id": "67810230",
    "title": "SVSC Movie - Mahesh Babu, Venkatesh, Samantha, Anjali",
    "analysis_data_path": "/PIONEER/USBANLZ/9bc/.../ANLZ0000.DAT",
    "bpm": 105.0,
    "duration_sec": 265,
    "file_path": "/Users/.../DJ-Music/Telugu/...mp3"
  },
  "mood": 3,                // 1=high, 2=mid, 3=low — sets the kind→label vocabulary
  "mood_label": "low",
  "total_beats": 464,
  "total_bars": 116,
  "has_phrases": true,      // false if PSSI is missing (track not analyzed for phrase)
  "phrases": [
    {
      "index": 1,            // 1-based PSSI entry index
      "label": "intro",      // human label from kind→label table for this mood
      "kind_int": 1,         // raw PSSI kind int
      "start_beat": 1,       // 1-based beat number where the phrase begins
      "start_sec": 0.38,
      "end_sec": 9.52        // = next phrase's start_sec; last phrase = duration_sec
    }
  ],
  "bars": [
    { "bar_index": 0, "start_ms": 377, "end_ms": 2662, "first_beat_index": 0 }
  ],
  "beats": [
    { "time_ms": 113, "beat_in_bar": 3, "tempo_bpm": 136.71 }
  ]
}
```

## Phrase kind→label mapping

Rekordbox picks a **mood** for each track during phrase analysis. The mood determines which vocabulary of phrase labels is used. The mood int is stored in PSSI; the label table below mirrors what rekordbox shows in Performance Mode → Phrase view. (Sourced from the [crate-digger](https://github.com/Deep-Symmetry/crate-digger) public reverse-engineering.)

| mood | label  | kind ints → label                                                                                                                                  |
|------|--------|-----------------------------------------------------------------------------------------------------------------------------------------------------|
| 1    | high   | 1=intro, 2=up, 3=down, 5=chorus, 6=outro, 7=up (and sub-flavors at higher ints)                                                                     |
| 2    | mid    | 1=intro, 2=verse-1, 3=verse-2, 4=chorus, 5=bridge, 6=outro                                                                                          |
| 3    | low    | 1=intro, 2=verse-1, 3=verse-2, 4=verse-3, 5=verse-4, 6=verse-5, 7=verse-6, 8=bridge, 9=chorus, 10=outro                                             |

Unknown kind ints render as `unknown-<int>` in `label` (with the raw int still in `kind_int`) so downstream tooling can decide whether to bail or treat it as a generic boundary.

## Prerequisites in rekordbox

Phrase analysis is **opt-in** in rekordbox. Without it, the `.EXT` file contains the extended beat grid (PQT2) and waveforms but no PSSI tag — the script then sets `has_phrases: false` and only emits beats + bars.

To enable: **Preferences → Analysis → Track Analysis Settings → check "Phrase"**, then right-click affected tracks → **Analyze Track**. The next time `phrase_grid.py` runs, PSSI will be present.

## Notes on quirks

- **PSSI is XOR-scrambled in rekordbox 6.6.5+ exports** ("license reasons"). `pyrekordbox.anlz.AnlzFile` auto-detects garbled tags by checking if the first decoded `mood` is outside the 1–3 range and unscrambles transparently — we get clean phrase data without any extra step.
- **PSSI is in the `.EXT` file, not `.DAT`.** `.DAT` has PQTZ (basic beat grid) only. PQT2 (extended grid, same beats with bar info) is in `.EXT` — we use PQTZ since both share the same time/beat fields.
- **Beat times are in ms from track start.** PQTZ stores them as Int32 ms. `tempo_bpm` is `tempo * 0.01` (BPM × 100 in the file).
- **First beat may not be at t=0.** Tracks with a few seconds of pre-beat audio (silence, fade-in) have `beats[0].time_ms > 0`. The `intro` phrase begins at this beat.
- **Bar boundaries** are derived from `beat_in_bar == 1` markers in PQTZ. We don't trust an external bar field — beat-in-bar is the only authoritative signal for downbeats.
- **Phrase end = next phrase start.** The PSSI structure stores phrase **starts** only. The script derives `end_sec` by looking at the next entry's `start_sec`; the last entry's end is `track.duration_sec`.

---

# Editing phrase analysis

`set_phrases.py` rewrites the PSSI tag in a track's `.EXT` file from a phrase plan. `lock_track.py` flips the lock bit so rekordbox preserves the edit on the next analyze pass. Both are write operations — they require rekordbox to be quit (or `--auto-close-rekordbox` to handle it).

## When to use this

rekordbox auto-detects phrases based on its analyzer's model of intro/verse/chorus/etc. It's right most of the time but not always — common failure modes on Indian-film catalog: chorus mislabelled as verse-N, drifted phrase boundaries (off by 4–8 beats), or odd mood selection for melodic tracks. Edit when the wrong boundary would lead to a bad mix-in / mix-out decision downstream.

## Phrase plan schema

```jsonc
{
  "track_id": "67810230",           // DjmdContent.ID — required
  "mood": 3,                         // 1=high, 2=mid, 3=low — required.
                                     // Changing mood switches the label vocabulary;
                                     // see the kind→label table above.
  "phrases": [                       // required, non-empty. Full replacement of
                                     // the existing PSSI entries — not a diff.
    { "start_beat": 1,   "label": "intro" },
    { "start_beat": 17,  "label": "verse-1" },
    { "start_beat": 101, "label": "bridge" },
    { "start_beat": 393, "label": "outro" }
  ]
}
```

- `start_beat` is a **1-based beat number** matching `phrase_grid.py`'s `start_beat`. Use beat numbers, not seconds — beats are the authoritative grid.
- `label` is reverse-mapped to the rekordbox `kind` int via the mood's label table. Invalid labels error out.
- Phrases are auto-sorted by `start_beat`; duplicates error out.
- No `start_sec` / `end_sec` — PSSI stores starts only.

## Running the writer

```bash
# Dry-run: validate + show diff:
.claude/skills/dj-research-agent/.venv/bin/python \
  .claude/skills/dj-research-agent/scripts/set_phrases.py \
  --plan /tmp/plan.json --dry-run

# Real write — closes + reopens rekordbox; locks the track in the same call:
.claude/skills/dj-research-agent/.venv/bin/python \
  .claude/skills/dj-research-agent/scripts/set_phrases.py \
  --plan /tmp/plan.json --auto-lock --auto-close-rekordbox
```

The writer backs up the `.EXT` file to `.EXT.bak-<YYYYMMDD-HHMMSS>` next to the original before writing. To restore: quit rekordbox, `cp <backup> <original>`.

## Lock flag (the protection layer)

`DjmdContent.Analysed` is a small int. Empirically across the entire library:

- **`105` = 0b01101001** — unlocked, fully analyzed
- **`233` = 0b11101001** — locked

The only difference is **bit 7 (0x80)**. `lock_track.py` toggles this bit. Other bits 0–6 seem to encode the analyze-state and stay constant — we don't touch them.

When the lock bit is **off**, rekordbox will re-detect cues / beat grid / phrases on its next analyze pass (manual reanalyze, or triggered by some setting changes) and **overwrite** our edits. When the bit is **on**, rekordbox preserves the data and skips reanalysis.

```bash
# Lock:
.claude/skills/dj-research-agent/.venv/bin/python \
  .claude/skills/dj-research-agent/scripts/lock_track.py \
  --track-id 67810230 --lock --auto-close-rekordbox

# Unlock:
.claude/skills/dj-research-agent/.venv/bin/python \
  .claude/skills/dj-research-agent/scripts/lock_track.py \
  --track-id 67810230 --unlock --auto-close-rekordbox
```

The lock flag is **also reachable from rekordbox's UI** (Track → Lock / 🔒 icon). The CLI and the UI write the same bit — interchangeable.

## Roundtrip safety

Before adding any real edit, the parse → build roundtrip was verified byte-identical for the SVSC test track (`AnlzFile.parse(bytes).build() == bytes`). pyrekordbox transparently handles the PSSI XOR re-scrambling on write. PSSI's `update_len` is a no-op in pyrekordbox, so the writer manually recomputes `len_entries` and the tag's `len_tag` when the entry count changes. Each PSSI entry is 24 bytes; tag = 32-byte header + `len_entries * 24` bytes.

## What we deliberately don't do (yet)

- **No multi-track plan format.** One plan = one track. Wrap with a `bulk_phrases.py` if/when the analyzer drives this in batch.
- **No insert/update/delete diff mode.** Full replacement only. Easier to dry-run-review.
- **No mood-auto-detect.** The plan must specify mood; the writer doesn't second-guess it. If you want to change mood, every phrase's `label` must still be valid under the new mood's table.
- **No write to PQTZ (beat grid) or other tags.** Phrases only. Beat grid edits would require also updating PQT2 + waveform tags to stay consistent — out of scope.
