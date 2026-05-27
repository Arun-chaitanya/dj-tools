# Rekordbox playlist CRUD

The `extract_playlists.py` / `set_playlist.py` / `sync_set_to_rekordbox.py` scripts wrap pyrekordbox's high-level playlist API. This file documents the underlying schema and the conventions our scripts rely on.

## Tables involved

- **`DjmdPlaylist`** — one row per playlist (or folder, or smart playlist).
  Key columns:
  - `ID` (string-serialized int) — playlist identity. New playlists get a fresh int from pyrekordbox.
  - `Name` (str)
  - `ParentID` (str) — `"root"` for top-level, else another `DjmdPlaylist.ID`
  - `Seq` (int) — display order among siblings in the same parent
  - `Attribute` (int) — `0` = playlist, `1` = folder, `4` = smart playlist (see `PlaylistType` enum in `pyrekordbox.db6.tables`)
  - `UUID` (uuid4 string)
  - `SmartList` (str) — XML for smart-playlist rules; null for normal playlists

- **`DjmdSongPlaylist`** — one row per (playlist, track) membership.
  Key columns:
  - `ID` (UUID string — note: *not* an int, unlike `DjmdCue.ID`)
  - `PlaylistID` — foreign key to `DjmdPlaylist.ID`
  - `ContentID` — foreign key to `DjmdContent.ID` (the track)
  - `TrackNo` (int) — 1-based position within the playlist
  - `UUID`

The same `ContentID` can appear in many playlists (one membership row per playlist).

## pyrekordbox high-level API (what our scripts use)

```python
db.create_playlist(name, parent=None, seq=None) -> DjmdPlaylist
db.delete_playlist(playlist)                    # cascades to membership rows
db.rename_playlist(playlist, name)
db.move_playlist(playlist, parent=None, seq=None)

db.add_to_playlist(playlist, content, track_no=None) -> DjmdSongPlaylist
db.remove_from_playlist(playlist, song)
db.move_song_in_playlist(playlist, song, new_track_no)

db.get_playlist(**kwargs)          # filtered query on DjmdPlaylist
db.get_playlist_songs(**kwargs)    # filtered query on DjmdSongPlaylist
```

The `playlist` arg accepts a `DjmdPlaylist` instance, an `ID` int, or an ID string. Same for `content` (track) and `song` (membership row). Our scripts pass strings.

After every mutation **`db.commit()`** is required; pyrekordbox does not auto-commit.

## Conventions our scripts rely on

- **Playlist identity**: name (case-sensitive). `sync_set_to_rekordbox.py` finds an existing playlist by name; ambiguity (two playlists with the same name) is a hard error.
- **TrackNo monotonicity**: `move_song_in_playlist` handles renumbering siblings when a track moves. We don't manage TrackNo manually.
- **Sequence → TrackNo**: `set.json`'s `sequence` is freeform (gaps and arbitrary values allowed); the sync pass sorts by sequence asc and assigns TrackNo `1..N`.
- **`sequence: null` is filtered out** of the sync. Lets you incrementally build a set without prematurely pushing half-placed tracks.

## Order of ops in `sync_set_to_rekordbox.py`

1. Resolve the diff: compare `set.json`'s placed tracks (sequence != null) against the rekordbox playlist's current membership.
2. **Removes** first — frees up TrackNo slots and prevents collisions when later moves need to occupy those positions.
3. **Reorders** — `move_song_in_playlist` handles shuffling other rows.
4. **Adds** last — appended at the explicit TrackNo from the desired list.
5. `db.commit()`. On any failure, `db.rollback()` and report the backup path.

## Safety

Same wrapper pattern as the cue writers — see `rekordbox-extraction.md` → "Safety wrapper". All write scripts:
- Refuse if `pgrep rekordbox` finds the app running. Override with `--force` (dangerous) or `--auto-close-rekordbox` (uses the shared `_rekordbox_lifecycle.py` graceful-quit helper).
- Back up `master.db` to `master.db.bak-<timestamp>` before any write.
- Run all mutations inside one SQLAlchemy session and call `commit()` once at the end. Any exception triggers `rollback()`.

## What we deliberately don't do (yet)

- **No folder creation / re-parenting.** All synced playlists land at root. Add when the user needs nested organization.
- **No smart-playlist support.** `SmartList` XML is left alone.
- **No `--delete-orphans` mode in sync** — if you delete `sets/<slug>/set.json`, the rekordbox playlist stays put. Add the flag when needed; deleting playlists is a one-way op so the default is conservative.
- **No image/cover support** (`ImagePath` column is left null on create).
- **No Cloud sync awareness.** If the user has rekordbox Cloud enabled, our local writes may be overwritten on Cloud's next sync cycle. Pre-flight: confirm before pushing on a Cloud-synced setup.
