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
