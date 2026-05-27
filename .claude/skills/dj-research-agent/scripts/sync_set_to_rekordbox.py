#!/usr/bin/env python3
"""Push a sets/<slug>/set.json into rekordbox as a playlist.

Idempotent: if the playlist already exists (matched by name), diff current
membership against the set.json and apply only the needed add/remove/reorder
ops. Re-running the same set is a no-op.

USAGE
    sync_set_to_rekordbox.py --set telugu-9xm-30min-v1 [--dry-run] [--force]
                             [--auto-close-rekordbox] [--playlist-name "Custom Name"]

Default playlist name = set.json's `set.title`. Override with --playlist-name.

SCOPE
    Sync covers tracks in set.json that have a non-null `sequence`. Tracks with
    sequence=null are treated as "not yet placed" and are skipped — they won't
    be added to or removed from the rekordbox playlist. This lets you incrementally
    build a set in the JSON without prematurely pushing half-placed tracks.

ORDER
    TrackNo in the rekordbox playlist mirrors `sequence` in set.json.
    Sequence values can be any positive ints; the resulting playlist is sorted
    by sequence asc and re-numbered 1..N for rekordbox.

SAFETY
    - Refuses to write if rekordbox is running, unless --auto-close-rekordbox
      or --force.
    - Backs up master.db before any write.
    - Whole sync runs as one transaction — rolls back on any error.
    - --dry-run prints the resolved diff (creates / adds / removes / reorders)
      without writing.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import io
import json
import os
import shutil
import sys


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _rekordbox_lifecycle as rblife  # noqa: E402


def rekordbox_running() -> bool:
    return rblife.is_running()


def backup_master_db() -> str:
    src = os.path.expanduser("~/Library/Pioneer/rekordbox/master.db")
    ts = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    dst = f"{src}.bak-{ts}"
    shutil.copy2(src, dst)
    return dst


def repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(here, "..", "..", "..", ".."))


def load_set(set_slug: str) -> dict:
    path = os.path.join(repo_root(), "sets", set_slug, "set.json")
    if not os.path.isfile(path):
        raise FileNotFoundError(f"set.json not found: {path}")
    with open(path) as f:
        return json.load(f)


def resolve_diff(db, set_data: dict, playlist_name: str) -> dict:
    """Build the plan: create-or-find playlist, then diff membership.

    Returns a dict describing every op. Does not mutate.
    """
    placed = [
        t for t in set_data.get("tracks", [])
        if t.get("sequence") is not None
    ]
    # Re-number 1..N by sequence asc; this is what rekordbox's TrackNo will hold
    placed_sorted = sorted(placed, key=lambda t: t["sequence"])
    desired = [
        {"track_no": i + 1, "track_id": str(t["track_id"]), "title": t.get("title", "")}
        for i, t in enumerate(placed_sorted)
    ]

    with contextlib.redirect_stdout(io.StringIO()):
        all_pls = list(db.get_playlist())
    matches = [pl for pl in all_pls if pl.Name == playlist_name]

    if len(matches) > 1:
        raise ValueError(f"playlist name {playlist_name!r} is ambiguous in rekordbox ({len(matches)} matches)")

    create_playlist = matches[0] is None if matches else True
    pl = matches[0] if matches else None

    if pl is None:
        # All desired tracks become adds
        return {
            "playlist": {"action": "create", "name": playlist_name, "id": None},
            "adds": desired,
            "removes": [],
            "reorders": [],
            "noops": [],
            "desired": desired,
        }

    # Compare existing membership to desired
    with contextlib.redirect_stdout(io.StringIO()):
        existing_songs = sorted(
            [s for s in pl.Songs],
            key=lambda s: (s.TrackNo if s.TrackNo is not None else 1_000_000),
        )
    existing_by_track = {str(s.ContentID): s for s in existing_songs}
    desired_by_track = {d["track_id"]: d for d in desired}

    adds = [d for d in desired if d["track_id"] not in existing_by_track]
    removes = [
        {"track_id": str(s.ContentID), "track_no": s.TrackNo, "membership_id": str(s.ID)}
        for s in existing_songs
        if str(s.ContentID) not in desired_by_track
    ]
    reorders = []
    noops = []
    for d in desired:
        s = existing_by_track.get(d["track_id"])
        if s is None:
            continue
        if s.TrackNo != d["track_no"]:
            reorders.append({
                "track_id": d["track_id"],
                "before": s.TrackNo,
                "after": d["track_no"],
                "membership_id": str(s.ID),
            })
        else:
            noops.append({"track_id": d["track_id"], "track_no": d["track_no"]})

    return {
        "playlist": {
            "action": "update" if (adds or removes or reorders) else "noop",
            "name": pl.Name,
            "id": str(pl.ID),
        },
        "adds": adds,
        "removes": removes,
        "reorders": reorders,
        "noops": noops,
        "desired": desired,
    }


def apply_diff(db, diff: dict) -> dict:
    """Apply the resolved diff. Returns the same diff with side-effects recorded."""
    pl_info = diff["playlist"]
    if pl_info["action"] == "create":
        with contextlib.redirect_stdout(io.StringIO()):
            pl = db.create_playlist(pl_info["name"])
        pl_info["id"] = str(pl.ID)
    else:
        with contextlib.redirect_stdout(io.StringIO()):
            all_pls = list(db.get_playlist())
        pl = next((p for p in all_pls if str(p.ID) == pl_info["id"]), None)
        if pl is None:
            raise RuntimeError(f"playlist disappeared between resolve and apply: {pl_info['id']}")

    # Removes first (frees up TrackNo slots), then reorders, then adds.
    for rm in diff["removes"]:
        with contextlib.redirect_stdout(io.StringIO()):
            membership = next(s for s in pl.Songs if str(s.ID) == rm["membership_id"])
            db.remove_from_playlist(pl, membership)

    for ro in diff["reorders"]:
        with contextlib.redirect_stdout(io.StringIO()):
            membership = next(s for s in pl.Songs if str(s.ID) == ro["membership_id"])
            db.move_song_in_playlist(pl, membership, ro["after"])

    for ad in diff["adds"]:
        with contextlib.redirect_stdout(io.StringIO()):
            row = db.add_to_playlist(pl, ad["track_id"], track_no=ad["track_no"])
            ad["membership_id"] = str(row.ID)

    return diff


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--set", required=True, dest="set_slug",
                   help="Set slug (folder name under sets/)")
    p.add_argument("--playlist-name", default=None,
                   help="Override rekordbox playlist name (default: set.title)")
    p.add_argument("--dry-run", action="store_true",
                   help="Resolve and print the diff without writing")
    p.add_argument("--force", action="store_true",
                   help="Write even if rekordbox is running (dangerous)")
    p.add_argument("--auto-close-rekordbox", action="store_true",
                   help="If rekordbox is open, quit it before writing, then reopen after")
    args = p.parse_args()

    try:
        set_data = load_set(args.set_slug)
    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    playlist_name = args.playlist_name or set_data["set"]["title"]

    was_running = rekordbox_running()
    if was_running and not args.dry_run:
        if args.auto_close_rekordbox:
            ok, reason = rblife.graceful_quit()
            if not ok:
                print(f"error: could not close rekordbox: {reason}", file=sys.stderr)
                return 2
        elif not args.force:
            print("error: rekordbox is running. Close it before writing, "
                  "pass --auto-close-rekordbox to close it automatically, "
                  "or --force to write anyway (dangerous).", file=sys.stderr)
            return 2

    from pyrekordbox import Rekordbox6Database
    with contextlib.redirect_stdout(io.StringIO()):
        db = Rekordbox6Database()

    try:
        diff = resolve_diff(db, set_data, playlist_name)
    except ValueError as e:
        print(f"error: resolve failed: {e}", file=sys.stderr)
        return 3

    summary = {
        "set_slug": args.set_slug,
        "playlist_name": playlist_name,
        "playlist": diff["playlist"],
        "counts": {
            "adds": len(diff["adds"]),
            "removes": len(diff["removes"]),
            "reorders": len(diff["reorders"]),
            "noops": len(diff["noops"]),
            "desired_total": len(diff["desired"]),
        },
    }

    if args.dry_run:
        out = {"dry_run": True, **summary, "diff": diff}
        json.dump(out, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
        return 0

    if summary["playlist"]["action"] == "noop":
        out = {"ok": True, "noop": True, **summary}
        json.dump(out, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
        if was_running and args.auto_close_rekordbox:
            rblife.reopen()
        return 0

    backup_path = backup_master_db()
    try:
        applied = apply_diff(db, diff)
        with contextlib.redirect_stdout(io.StringIO()):
            db.commit()
    except Exception as e:
        with contextlib.redirect_stdout(io.StringIO()):
            try:
                db.rollback()
            except Exception:
                pass
        print(f"error: sync failed, rolled back: {e}", file=sys.stderr)
        print(f"backup is intact at: {backup_path}", file=sys.stderr)
        return 4

    reopened = False
    if was_running and args.auto_close_rekordbox:
        ok, _ = rblife.reopen()
        reopened = ok

    out = {
        "ok": True,
        **summary,
        "playlist_id": applied["playlist"]["id"],
        "backup": backup_path,
        "rekordbox_was_running": was_running,
        "rekordbox_reopened": reopened,
    }
    json.dump(out, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
