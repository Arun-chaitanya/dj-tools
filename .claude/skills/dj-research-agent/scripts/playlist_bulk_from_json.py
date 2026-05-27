#!/usr/bin/env python3
"""Apply many playlist edits across many playlists from a JSON plan.

Two-phase like bulk_cue_from_json.py:
  1. resolve_plan — validates every op against current state. No writes.
  2. apply_plan   — performs writes. All-or-nothing per playlist (the whole
                    playlist file is rewritten at the end of its op list).
                    If any playlist's resolution fails, NOTHING is written.

USAGE
    playlist_bulk_from_json.py --plan plan.json [--dry-run]

PLAN FORMAT

    {
      "name": "Telugu 9XM 30-min set, build v1",      // freeform, optional
      "playlists": [
        {
          "slug": "telugu-9xm-30min-v1",
          "create": {                                 // optional — create if missing
            "name": "Telugu 9XM — 30 min set (v1)",
            "lane": "Telugu 9XM",
            "target_duration_min": 30,
            "description": "..."
          },
          "ops": [
            {"action": "add",          "track_id": "68643951",  "sequence": 1, "comment": "opener"},
            {"action": "add",          "track_id": "163512415", "comment": "build"},
            {"action": "set-comment",  "sequence": 1, "comment": "soft open"},
            {"action": "move",         "from": 2,     "to": 1},
            {"action": "remove",       "sequence": 3},
            {"action": "set-meta",     "name": "...", "lane": "..."}
          ]
        }
      ]
    }
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from copy import deepcopy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _playlist_io as plio  # noqa: E402


def _resolve_one(slug: str, spec: dict, library: dict | None) -> dict:
    """Build the final playlist dict by replaying ops on top of current state.

    Doesn't write anything. Raises ValueError on any error.
    """
    path = plio.playlist_path(slug)
    if os.path.isfile(path):
        data = deepcopy(plio.load_playlist(slug))
    elif "create" in spec:
        meta = {"slug": slug,
                "name": spec["create"].get("name", slug),
                "created": dt.date.today().isoformat()}
        for k in ("description", "lane", "target_duration_min"):
            if k in spec["create"]:
                meta[k] = spec["create"][k]
        data = {"playlist": meta, "tracks": []}
    else:
        raise ValueError(f"playlist {slug!r} does not exist and plan has no 'create' block")

    tracks = data.setdefault("tracks", [])

    for op in spec.get("ops", []):
        action = op.get("action")
        if action == "add":
            tid = str(op["track_id"])
            if library is not None:
                plio.assert_track_in_library(library, tid)
            seq = op.get("sequence")
            new_t = {"track_id": tid, "sequence": 0, "comment": op.get("comment", "")}
            if seq is None:
                new_t["sequence"] = len(tracks) + 1
                tracks.append(new_t)
            else:
                if seq < 1 or seq > len(tracks) + 1:
                    raise ValueError(f"{slug}: add sequence must be 1..{len(tracks) + 1}, got {seq}")
                for t in tracks:
                    if t["sequence"] >= seq:
                        t["sequence"] += 1
                new_t["sequence"] = seq
                tracks.append(new_t)

        elif action == "remove":
            seq = op.get("sequence")
            tid = op.get("track_id")
            if seq is None and tid is None:
                raise ValueError(f"{slug}: remove requires sequence or track_id")
            if seq is not None:
                vics = [t for t in tracks if t["sequence"] == seq]
                if not vics:
                    raise ValueError(f"{slug}: no track at sequence {seq}")
            else:
                vics = [t for t in tracks if t["track_id"] == str(tid)]
                if not vics:
                    raise ValueError(f"{slug}: no track with track_id {tid}")
                if len(vics) > 1:
                    raise ValueError(f"{slug}: track_id {tid} appears multiple times; use sequence")
            tracks.remove(vics[0])

        elif action == "move":
            f = op["from"]
            t = op["to"]
            n = len(tracks)
            if not (1 <= f <= n and 1 <= t <= n):
                raise ValueError(f"{slug}: move from/to must be 1..{n}, got {f}->{t}")
            if f != t:
                tracks.sort(key=lambda x: x["sequence"])
                mv = next(x for x in tracks if x["sequence"] == f)
                tracks.remove(mv)
                tracks.insert(t - 1, mv)

        elif action == "set-comment":
            seq = op["sequence"]
            ms = [t for t in tracks if t["sequence"] == seq]
            if not ms:
                raise ValueError(f"{slug}: no track at sequence {seq}")
            ms[0]["comment"] = op["comment"]

        elif action == "set-meta":
            meta = data.setdefault("playlist", {})
            for k in ("name", "description", "lane", "target_duration_min"):
                if k in op:
                    meta[k] = op[k]

        else:
            raise ValueError(f"{slug}: unknown action {action!r}")

        # Repack after every op so subsequent ops see a stable 1..N.
        tracks.sort(key=lambda t: t["sequence"])
        for i, t in enumerate(tracks, start=1):
            t["sequence"] = i

    return data


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--plan", required=True)
    p.add_argument("--dry-run", action="store_true",
                   help="Resolve and print results without writing")
    args = p.parse_args()

    if not os.path.isfile(args.plan):
        print(f"error: plan not found: {args.plan}", file=sys.stderr)
        return 1
    with open(args.plan) as f:
        plan = json.load(f)

    library = plio.load_library()

    # Phase 1: resolve everything. Fail fast.
    resolved = []
    try:
        for spec in plan.get("playlists", []):
            slug = spec["slug"]
            plio.validate_slug(slug)
            data = _resolve_one(slug, spec, library)
            resolved.append((slug, data, spec))
    except ValueError as e:
        print(f"error: plan validation failed: {e}", file=sys.stderr)
        return 3

    if args.dry_run:
        out = {
            "dry_run": True,
            "plan_name": plan.get("name", ""),
            "playlists": [
                {"slug": slug,
                 "track_count": len(data["tracks"]),
                 "tracks": [{"sequence": t["sequence"], "track_id": t["track_id"],
                             "comment": t.get("comment", "")} for t in data["tracks"]],
                 "playlist": data.get("playlist", {})}
                for slug, data, _ in resolved
            ],
        }
        json.dump(out, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
        return 0

    # Phase 2: write each resolved playlist.
    written = []
    for slug, data, _ in resolved:
        plio.write_playlist(slug, data)
        written.append({"slug": slug, "track_count": len(data["tracks"])})

    json.dump({"ok": True, "plan_name": plan.get("name", ""),
               "playlists_written": written},
              sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
