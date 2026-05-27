#!/usr/bin/env python3
"""List rekordbox playlists (and optionally their track membership).

Read-only. Safe to run while rekordbox is open (pyrekordbox just warns).

USAGE
    extract_playlists.py                       # all playlists, summary only
    extract_playlists.py --with-tracks         # include track_ids per playlist
    extract_playlists.py --name "Telugu 9XM"   # one playlist by exact name
    extract_playlists.py --id 2931769606       # one playlist by ID

Output: JSON to stdout, errors to stderr, non-zero exit on failure.
Schema:
  {
    "exported_at": "...",
    "total_playlists": N,
    "playlists": [
      {
        "id": "2931769606",
        "name": "Telugu 9XM",
        "parent_id": "root",
        "seq": 8,
        "attribute": 0,                 // 0 = playlist, 1 = folder, 4 = smart
        "track_count": 16,
        "tracks": [                     // only when --with-tracks
          {"track_no": 1, "track_id": "68643951", "title": "...", "artists": "..."},
          ...
        ]
      }
    ]
  }
"""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import io
import json
import sys


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--with-tracks", action="store_true",
                   help="Include full track membership (track_no, track_id, title)")
    p.add_argument("--name", default=None, help="Filter to one playlist by exact name")
    p.add_argument("--id", default=None, help="Filter to one playlist by ID")
    args = p.parse_args()

    with contextlib.redirect_stdout(io.StringIO()):
        from pyrekordbox import Rekordbox6Database
        db = Rekordbox6Database()
        all_pls = list(db.get_playlist())

    if args.id:
        pls = [pl for pl in all_pls if str(pl.ID) == str(args.id)]
    elif args.name:
        pls = [pl for pl in all_pls if pl.Name == args.name]
    else:
        pls = all_pls

    out_pls = []
    for pl in pls:
        with contextlib.redirect_stdout(io.StringIO()):
            songs = sorted(
                [s for s in pl.Songs],
                key=lambda s: (s.TrackNo if s.TrackNo is not None else 1_000_000),
            )

        row = {
            "id": str(pl.ID),
            "name": pl.Name,
            "parent_id": str(pl.ParentID) if pl.ParentID is not None else None,
            "seq": pl.Seq,
            "attribute": pl.Attribute,
            "track_count": len(songs),
            "uuid": pl.UUID,
        }

        if args.with_tracks:
            tracks = []
            for s in songs:
                with contextlib.redirect_stdout(io.StringIO()):
                    content = s.Content
                tracks.append({
                    "track_no": s.TrackNo,
                    "track_id": str(s.ContentID),
                    "membership_id": str(s.ID),
                    "title": getattr(content, "Title", None) if content else None,
                    "artists": getattr(content, "ArtistName", None) if content else None,
                })
            row["tracks"] = tracks

        out_pls.append(row)

    out = {
        "exported_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "total_playlists": len(out_pls),
        "playlists": out_pls,
    }
    json.dump(out, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
