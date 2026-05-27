#!/usr/bin/env python3
"""Extract cued tracks live from the rekordbox master.db.

Reads ~/Library/Pioneer/rekordbox/master.db via pyrekordbox (handles SQLCipher
key derivation), filters tracks with >= --min-hot-cues hot cues, and writes a
JSON object to stdout matching extract_cued_from_xml.py's shape.

Rekordbox can be open while we read; pyrekordbox warns but works.

Usage:
    .venv/bin/python extract_cued_from_db.py [--min-hot-cues 2] [--genre-folder Telugu]
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from collections import defaultdict


REKORDBOX_COLOR_TABLE = {
    # rekordbox stores cue colors as a single int. Mapping from the int to its
    # display hex is from rekordbox's color palette. -1 means "no color set".
    -1: None,
    0: "#ff007f",  # pink
    1: "#ff6f00",  # orange
    2: "#ffcc00",  # yellow
    3: "#7dc13d",  # green
    4: "#45acdb",  # blue (default 1)
    5: "#aa72ff",  # purple
    6: "#ff376f",  # red
}


def color_to_hex(color_int) -> str | None:
    if color_int is None:
        return None
    return REKORDBOX_COLOR_TABLE.get(int(color_int))


def library_genre_folder(path: str, library_root: str) -> str | None:
    if not path or not library_root:
        return None
    try:
        rel = os.path.relpath(path, library_root)
    except ValueError:
        return None
    if rel.startswith(".."):
        return None
    parts = rel.split(os.sep)
    return parts[0] if len(parts) > 1 else None


def cue_dict(cue) -> dict:
    out = {
        "start_sec": (cue.InMsec / 1000.0) if cue.InMsec is not None and cue.InMsec >= 0 else None,
        "name": cue.Comment or "",
        "kind": int(cue.Kind) if cue.Kind is not None else None,
        "color": color_to_hex(cue.Color),
    }
    if cue.OutMsec is not None and cue.OutMsec > 0:
        out["end_sec"] = cue.OutMsec / 1000.0
    return out


def extract(min_hot_cues: int, genre_folder: str | None, library_root: str) -> dict:
    from pyrekordbox import Rekordbox6Database

    # pyrekordbox emits spurious '{}' lines to stdout during queries; capture
    # and discard them so our JSON output stays clean.
    import contextlib
    import io
    stdout_sink = io.StringIO()

    with contextlib.redirect_stdout(stdout_sink):
        db = Rekordbox6Database()

        cues_by_track = defaultdict(lambda: {"hot": [], "mem": []})
        for cue in db.get_cue():
            d = cue_dict(cue)
            if cue.is_hot_cue:
                cues_by_track[cue.ContentID]["hot"].append(d)
            elif cue.is_memory_cue:
                cues_by_track[cue.ContentID]["mem"].append(d)

        contents = list(db.get_content())

    out_tracks = []
    for c in contents:
        buckets = cues_by_track.get(c.ID, {"hot": [], "mem": []})
        hot = buckets["hot"]
        if len(hot) < min_hot_cues:
            continue

        path = c.FolderPath or ""
        sub_folder = library_genre_folder(path, library_root)
        if genre_folder and sub_folder != genre_folder:
            continue

        hot_sorted = sorted(hot, key=lambda d: (d.get("start_sec") is None, d.get("start_sec") or 0))
        # Assign a 0-based num matching the start-time order so output is
        # stable and useful even though the DB doesn't carry a "hot cue slot".
        for i, d in enumerate(hot_sorted):
            d["num"] = i

        loops = [d for d in hot_sorted if "end_sec" in d] + \
                [d for d in buckets["mem"] if "end_sec" in d]
        memory_cues = [d for d in buckets["mem"] if "end_sec" not in d]
        hot_cues = [d for d in hot_sorted if "end_sec" not in d]

        bpm = (c.BPM / 100.0) if c.BPM else None

        out_tracks.append({
            "track_id": str(c.ID),
            "title": c.Title or "",
            "artists": c.ArtistName or "",
            "album": c.AlbumName or "",
            "genre": c.GenreName or "",
            "bpm": bpm,
            "key": c.KeyName or "",
            "duration_sec": int(c.Length) if c.Length else None,
            "file_path": path,
            "library_genre_folder": sub_folder,
            "rating": int(c.Rating) if c.Rating else None,
            "play_count": int(c.DJPlayCount) if c.DJPlayCount else None,
            "date_added": c.StockDate,
            "hot_cues": hot_cues,
            "memory_cues": memory_cues,
            "loops": loops,
        })

    out_tracks.sort(key=lambda t: (t["library_genre_folder"] or "~", t["title"].lower()))

    return {
        "source": "db",
        "source_path": str(db.db_path) if hasattr(db, "db_path") else "~/Library/Pioneer/rekordbox/master.db",
        "exported_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "filter": {
            "min_hot_cues": min_hot_cues,
            "genre_folder": genre_folder,
        },
        "library_root": library_root,
        "total_tracks": len(out_tracks),
        "tracks": out_tracks,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--min-hot-cues", type=int, default=2,
                        help="Minimum hot cues required (default: 2)")
    parser.add_argument("--genre-folder", default=None,
                        help='Filter by library sub-folder name (e.g. "Telugu", "Bollywood")')
    parser.add_argument(
        "--library-root",
        default=os.path.expanduser("~/Desktop/DJ-Music"),
        help="Library root for genre-folder derivation (default: ~/Desktop/DJ-Music)",
    )
    args = parser.parse_args()

    try:
        result = extract(args.min_hot_cues, args.genre_folder, args.library_root)
    except ImportError:
        print("error: pyrekordbox not installed. Install with:", file=sys.stderr)
        print("  .claude/skills/dj-research-agent/.venv/bin/pip install pyrekordbox", file=sys.stderr)
        return 2

    json.dump(result, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
