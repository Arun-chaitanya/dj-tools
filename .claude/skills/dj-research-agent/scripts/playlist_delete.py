#!/usr/bin/env python3
"""Delete a playlist folder. Requires --yes to actually delete.

Usage:
    playlist_delete.py --slug telugu-9xm-30min-v1            # dry-run (lists what would be removed)
    playlist_delete.py --slug telugu-9xm-30min-v1 --yes      # actually delete
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _playlist_io as plio  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--slug", required=True)
    p.add_argument("--yes", action="store_true",
                   help="Actually delete (default: dry-run that lists what would be removed)")
    args = p.parse_args()

    folder = os.path.join(plio.playlists_dir(), args.slug)
    if not os.path.isdir(folder):
        print(f"error: no playlist folder at {folder}", file=sys.stderr)
        return 1

    files = sorted(os.listdir(folder))
    out = {
        "slug": args.slug,
        "folder": folder,
        "files": files,
        "dry_run": not args.yes,
    }
    if args.yes:
        shutil.rmtree(folder)
        out["deleted"] = True
    json.dump(out, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
