#!/usr/bin/env python3
"""Show one playlist with library-joined track metadata.

Usage:
    playlist_show.py --slug telugu-9xm-30min-v1

Stdout: JSON { "playlist": {...}, "tracks": [ {sequence, comment, track_id, library: {...|null}} ] }
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _playlist_io as plio  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--slug", required=True)
    args = p.parse_args()

    try:
        data = plio.load_playlist(args.slug)
    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    library = plio.load_library()
    tracks_in = sorted(data.get("tracks", []), key=lambda t: t.get("sequence", 0))
    tracks_out = []
    missing = 0
    for t in tracks_in:
        lib = plio.resolve_track(library, t["track_id"])
        if lib is None:
            missing += 1
        tracks_out.append({
            "sequence": t.get("sequence"),
            "comment": t.get("comment", ""),
            "track_id": t["track_id"],
            "library": lib,
        })

    out = {
        "playlist": {**(data.get("playlist") or {}), "slug": args.slug},
        "track_count": len(tracks_out),
        "missing_from_snapshot": missing,
        "library_exported_at": (library or {}).get("exported_at"),
        "tracks": tracks_out,
    }
    json.dump(out, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
