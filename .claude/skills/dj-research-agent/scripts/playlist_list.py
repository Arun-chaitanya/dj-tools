#!/usr/bin/env python3
"""List all playable playlists in playlists/.

Stdout: JSON { "total": N, "playlists": [ {slug, name, created, track_count, lane, target_duration_min, description}, ... ] }
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _playlist_io as plio  # noqa: E402


def main() -> int:
    pls = plio.list_playlists()
    out = {"total": len(pls), "playlists": pls}
    json.dump(out, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
