#!/usr/bin/env python3
"""Extract cued tracks from a rekordbox XML export.

Reads a rekordbox.xml (File → Export Collection in XML format), filters tracks
that have at least --min-hot-cues hot cues set, and writes a JSON object to
stdout describing each track + its cues.

Output shape matches extract_cued_from_db.py so downstream tools don't need to
care which source produced it.

Usage:
    python3 extract_cued_from_xml.py --xml rekordbox-export.xml [--min-hot-cues 2] [--genre-folder Telugu]
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import urllib.parse
import xml.etree.ElementTree as ET


def file_url_to_path(loc: str) -> str:
    """Convert rekordbox 'file://localhost/...' URL to a plain absolute path."""
    if not loc:
        return ""
    prefix = "file://localhost"
    if loc.startswith(prefix):
        loc = loc[len(prefix):]
    elif loc.startswith("file://"):
        loc = loc[len("file://"):]
    return urllib.parse.unquote(loc)


def library_genre_folder(path: str, library_root: str) -> str | None:
    """If path lives under library_root, return the immediate sub-folder name."""
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


def rgb_to_hex(r: str | None, g: str | None, b: str | None) -> str | None:
    if not (r and g and b):
        return None
    try:
        return "#{:02x}{:02x}{:02x}".format(int(r), int(g), int(b))
    except ValueError:
        return None


def cue_dict(c: ET.Element) -> dict:
    out = {
        "num": int(c.get("Num", "-1")),
        "start_sec": float(c.get("Start", "0")) if c.get("Start") else None,
        "name": c.get("Name", "") or "",
        "type": int(c.get("Type", "0")) if c.get("Type") else 0,
        "color": rgb_to_hex(c.get("Red"), c.get("Green"), c.get("Blue")),
    }
    end = c.get("End")
    if end:
        out["end_sec"] = float(end)
    return out


def extract(xml_path: str, min_hot_cues: int, genre_folder: str | None, library_root: str) -> dict:
    tree = ET.parse(xml_path)
    out_tracks = []
    for t in tree.iter("TRACK"):
        cues = t.findall("POSITION_MARK")
        hot = [c for c in cues if c.get("Num") and c.get("Num") != "-1"]
        if len(hot) < min_hot_cues:
            continue

        path = file_url_to_path(t.get("Location", ""))
        sub_folder = library_genre_folder(path, library_root)
        if genre_folder and sub_folder != genre_folder:
            continue

        hot_cues = sorted(
            [cue_dict(c) for c in hot if int(c.get("Type", "0")) == 0],
            key=lambda c: c["num"],
        )
        memory_cues = [
            cue_dict(c) for c in cues
            if c.get("Num") == "-1" and int(c.get("Type", "0")) == 0
        ]
        loops = [cue_dict(c) for c in cues if int(c.get("Type", "0")) == 4]

        bpm = t.get("AverageBpm")
        try:
            bpm_val = float(bpm) if bpm else None
        except ValueError:
            bpm_val = None

        try:
            duration = int(t.get("TotalTime") or 0) or None
        except ValueError:
            duration = None

        out_tracks.append({
            "track_id": t.get("TrackID"),
            "title": t.get("Name") or "",
            "artists": t.get("Artist") or "",
            "album": t.get("Album") or "",
            "genre": t.get("Genre") or "",
            "bpm": bpm_val,
            "key": t.get("Tonality") or "",
            "duration_sec": duration,
            "file_path": path,
            "library_genre_folder": sub_folder,
            "rating": int(t.get("Rating") or 0) or None,
            "play_count": int(t.get("PlayCount") or 0) or None,
            "date_added": t.get("DateAdded") or None,
            "hot_cues": hot_cues,
            "memory_cues": memory_cues,
            "loops": loops,
        })

    out_tracks.sort(key=lambda t: (t["library_genre_folder"] or "~", t["title"].lower()))

    return {
        "source": "xml",
        "source_path": xml_path,
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
    parser.add_argument("--xml", required=True, help="Path to rekordbox-export.xml")
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

    if not os.path.isfile(args.xml):
        print(f"error: xml file not found: {args.xml}", file=sys.stderr)
        return 1

    result = extract(args.xml, args.min_hot_cues, args.genre_folder, args.library_root)
    json.dump(result, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
