#!/usr/bin/env python3
"""Edit one playlist. Verb-based, like set_cue.py.

Sequences are always re-packed to 1..N after every edit — no gaps.

Subcommands
-----------

    # Insert a track at the end (default), or at a specific sequence.
    # If --sequence is given, all later sequences shift up by 1.
    playlist_edit.py add-track --slug X --track-id Y [--sequence N] [--comment "..."]

    # Remove a track. Pick by sequence (preferred) or by track-id (fails if non-unique in this set).
    playlist_edit.py remove-track --slug X (--sequence N | --track-id Y)

    # Re-order: move the track currently at --from to position --to.
    playlist_edit.py move-track --slug X --from N --to M

    # Edit per-track comment.
    playlist_edit.py set-comment --slug X --sequence N --comment "..."

    # Edit playlist header (any subset of fields).
    playlist_edit.py set-meta --slug X [--name ...] [--description ...] [--lane ...] [--target-duration-min N]

All add-track / move-track / remove-track validate track_id against playlists/_library.json
unless --no-validate is passed.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _playlist_io as plio  # noqa: E402


def _load(slug: str) -> dict:
    try:
        return plio.load_playlist(slug)
    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)


def _ok(action: str, slug: str, data: dict, **extra) -> int:
    plio.write_playlist(slug, data)
    out = {
        "ok": True,
        "action": action,
        "slug": slug,
        "track_count": len(data["tracks"]),
        "tracks": [{"sequence": t["sequence"], "track_id": t["track_id"],
                    "comment": t.get("comment", "")} for t in data["tracks"]],
        **extra,
    }
    json.dump(out, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


def cmd_add_track(args) -> int:
    data = _load(args.slug)
    tracks = data.setdefault("tracks", [])

    if not args.no_validate:
        try:
            plio.assert_track_in_library(plio.load_library(), args.track_id)
        except ValueError as e:
            print(f"error: {e}", file=sys.stderr)
            return 3

    new_track = {
        "track_id": str(args.track_id),
        "sequence": 0,  # placeholder, repacked below
        "comment": args.comment or "",
    }

    if args.sequence is None:
        # append
        new_track["sequence"] = len(tracks) + 1
        tracks.append(new_track)
        inserted_at = len(tracks)
    else:
        target = args.sequence
        if target < 1 or target > len(tracks) + 1:
            print(f"error: --sequence must be 1..{len(tracks) + 1}", file=sys.stderr)
            return 1
        for t in tracks:
            if t["sequence"] >= target:
                t["sequence"] += 1
        new_track["sequence"] = target
        tracks.append(new_track)
        inserted_at = target

    return _ok("add-track", args.slug, data, inserted_at=inserted_at,
               added_track_id=str(args.track_id))


def cmd_remove_track(args) -> int:
    data = _load(args.slug)
    tracks = data.setdefault("tracks", [])

    if args.sequence is not None and args.track_id is not None:
        print("error: pass either --sequence or --track-id, not both", file=sys.stderr)
        return 1
    if args.sequence is None and args.track_id is None:
        print("error: pass --sequence or --track-id", file=sys.stderr)
        return 1

    if args.sequence is not None:
        matches = [t for t in tracks if t["sequence"] == args.sequence]
        if not matches:
            print(f"error: no track at sequence {args.sequence}", file=sys.stderr)
            return 2
    else:
        matches = [t for t in tracks if t["track_id"] == str(args.track_id)]
        if not matches:
            print(f"error: no track with track_id {args.track_id}", file=sys.stderr)
            return 2
        if len(matches) > 1:
            print(f"error: track_id {args.track_id} appears {len(matches)} times; "
                  "remove by --sequence to disambiguate", file=sys.stderr)
            return 2

    victim = matches[0]
    tracks.remove(victim)
    # repack handled by write_playlist

    return _ok("remove-track", args.slug, data,
               removed_track_id=victim["track_id"],
               removed_from_sequence=victim["sequence"])


def cmd_move_track(args) -> int:
    data = _load(args.slug)
    tracks = data.setdefault("tracks", [])
    n = len(tracks)
    if not (1 <= args.from_seq <= n and 1 <= args.to_seq <= n):
        print(f"error: --from and --to must be 1..{n}", file=sys.stderr)
        return 1
    if args.from_seq == args.to_seq:
        return _ok("move-track", args.slug, data, note="no-op")

    tracks.sort(key=lambda t: t["sequence"])
    moving = next(t for t in tracks if t["sequence"] == args.from_seq)
    tracks.remove(moving)
    # tracks is now n-1 long; sequences are stale but we'll repack on write.
    # Insert at to_seq - 1 (0-indexed) after the removal.
    insert_at = args.to_seq - 1
    tracks.insert(insert_at, moving)
    # Re-stamp by position so repack-on-write yields the right order.
    for i, t in enumerate(tracks, start=1):
        t["sequence"] = i

    return _ok("move-track", args.slug, data,
               moved_track_id=moving["track_id"],
               from_seq=args.from_seq, to_seq=args.to_seq)


def cmd_set_comment(args) -> int:
    data = _load(args.slug)
    tracks = data.setdefault("tracks", [])
    matches = [t for t in tracks if t["sequence"] == args.sequence]
    if not matches:
        print(f"error: no track at sequence {args.sequence}", file=sys.stderr)
        return 2
    matches[0]["comment"] = args.comment
    return _ok("set-comment", args.slug, data,
               sequence=args.sequence, comment=args.comment)


def cmd_set_meta(args) -> int:
    data = _load(args.slug)
    meta = data.setdefault("playlist", {})
    changed = {}
    if args.name is not None:
        meta["name"] = args.name
        changed["name"] = args.name
    if args.description is not None:
        meta["description"] = args.description
        changed["description"] = args.description
    if args.lane is not None:
        meta["lane"] = args.lane
        changed["lane"] = args.lane
    if args.target_duration_min is not None:
        meta["target_duration_min"] = args.target_duration_min
        changed["target_duration_min"] = args.target_duration_min
    if not changed:
        print("error: pass at least one of --name / --description / --lane / --target-duration-min",
              file=sys.stderr)
        return 1
    plio.write_playlist(args.slug, data)
    out = {"ok": True, "action": "set-meta", "slug": args.slug, "changed": changed,
           "playlist": meta}
    json.dump(out, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--slug", required=True)

    sp = sub.add_parser("add-track", parents=[common])
    sp.add_argument("--track-id", required=True)
    sp.add_argument("--sequence", type=int, default=None,
                    help="1-based position; default = append")
    sp.add_argument("--comment", default=None)
    sp.add_argument("--no-validate", action="store_true",
                    help="Skip library-snapshot validation")
    sp.set_defaults(func=cmd_add_track)

    sp = sub.add_parser("remove-track", parents=[common])
    sp.add_argument("--sequence", type=int, default=None)
    sp.add_argument("--track-id", default=None)
    sp.set_defaults(func=cmd_remove_track)

    sp = sub.add_parser("move-track", parents=[common])
    sp.add_argument("--from", dest="from_seq", type=int, required=True)
    sp.add_argument("--to", dest="to_seq", type=int, required=True)
    sp.set_defaults(func=cmd_move_track)

    sp = sub.add_parser("set-comment", parents=[common])
    sp.add_argument("--sequence", type=int, required=True)
    sp.add_argument("--comment", required=True)
    sp.set_defaults(func=cmd_set_comment)

    sp = sub.add_parser("set-meta", parents=[common])
    sp.add_argument("--name", default=None)
    sp.add_argument("--description", default=None)
    sp.add_argument("--lane", default=None)
    sp.add_argument("--target-duration-min", type=int, default=None)
    sp.set_defaults(func=cmd_set_meta)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
