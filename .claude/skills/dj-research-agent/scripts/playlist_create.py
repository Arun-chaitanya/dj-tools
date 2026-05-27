#!/usr/bin/env python3
"""Create a new empty playlist.

Usage:
    playlist_create.py --slug telugu-9xm-30min-v2 --name "Telugu 9XM — 30 min set (v2)" \
        [--description "..."] [--lane "Telugu 9XM"] [--target-duration-min 30]

Refuses to overwrite an existing playlist. Slug must be kebab-case ASCII.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _playlist_io as plio  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--slug", required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--description", default=None)
    p.add_argument("--lane", default=None)
    p.add_argument("--target-duration-min", type=int, default=None)
    args = p.parse_args()

    try:
        plio.validate_slug(args.slug)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    path = plio.playlist_path(args.slug)
    if os.path.exists(path):
        print(f"error: playlist already exists at {path}", file=sys.stderr)
        return 2

    meta = {
        "slug": args.slug,
        "name": args.name,
        "created": dt.date.today().isoformat(),
    }
    if args.description is not None:
        meta["description"] = args.description
    if args.lane is not None:
        meta["lane"] = args.lane
    if args.target_duration_min is not None:
        meta["target_duration_min"] = args.target_duration_min

    data = {"playlist": meta, "tracks": []}
    plio.write_playlist(args.slug, data)

    json.dump({"ok": True, "slug": args.slug, "path": path, "playlist": meta},
              sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
