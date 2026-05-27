#!/usr/bin/env python3
"""Single-op CRUD on rekordbox playlists.

Wraps pyrekordbox's high-level playlist API. Designed as the lowest-level
playlist write primitive — sync_set_to_rekordbox.py wraps this for batches.

Subcommands
    list                  List playlists (optionally with track membership)
    create                Create an empty playlist
    rename                Rename a playlist by ID
    delete                Delete a playlist (membership rows go too; underlying
                          tracks are untouched)
    add-track             Add one track to a playlist
    remove-track          Remove one membership row from a playlist
    reorder               Change a track's position within a playlist

SAFETY
    - Refuses to write if rekordbox is running (pgrep rekordbox), unless
      --force or --auto-close-rekordbox is passed.
    - Backs up master.db to master.db.bak-<timestamp> before any write.
    - --dry-run shows what would happen without writing.

EXAMPLES
    # Read
    set_playlist.py list
    set_playlist.py list --name "Telugu 9XM" --with-tracks

    # Create + populate
    set_playlist.py create --name "Telugu 9XM 30min v1"
    set_playlist.py add-track --playlist-id 1234567890 --track-id 68643951
    set_playlist.py add-track --playlist-id 1234567890 --track-id 163512415 --position 2

    # Modify
    set_playlist.py rename --playlist-id 1234567890 --name "Telugu 9XM 30min v2"
    set_playlist.py reorder --playlist-id 1234567890 --track-id 68643951 --position 5
    set_playlist.py remove-track --playlist-id 1234567890 --track-id 163512415

    # Destroy
    set_playlist.py delete --playlist-id 1234567890
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


def serialize_playlist(pl, with_tracks: bool = False) -> dict:
    row = {
        "id": str(pl.ID),
        "name": pl.Name,
        "parent_id": str(pl.ParentID) if pl.ParentID is not None else None,
        "seq": pl.Seq,
        "attribute": pl.Attribute,
        "uuid": pl.UUID,
    }
    with contextlib.redirect_stdout(io.StringIO()):
        songs = sorted(
            [s for s in pl.Songs],
            key=lambda s: (s.TrackNo if s.TrackNo is not None else 1_000_000),
        )
    row["track_count"] = len(songs)
    if with_tracks:
        tracks = []
        for s in songs:
            with contextlib.redirect_stdout(io.StringIO()):
                content = s.Content
            tracks.append({
                "track_no": s.TrackNo,
                "track_id": str(s.ContentID),
                "membership_id": str(s.ID),
                "title": getattr(content, "Title", None) if content else None,
            })
        row["tracks"] = tracks
    return row


def find_playlist(db, *, playlist_id=None, name=None):
    with contextlib.redirect_stdout(io.StringIO()):
        all_pls = list(db.get_playlist())
    if playlist_id is not None:
        for pl in all_pls:
            if str(pl.ID) == str(playlist_id):
                return pl
        return None
    if name is not None:
        matches = [pl for pl in all_pls if pl.Name == name]
        if len(matches) == 0:
            return None
        if len(matches) > 1:
            raise ValueError(f"name {name!r} is ambiguous: {len(matches)} matches; pass --playlist-id instead")
        return matches[0]
    return None


def find_membership(pl, track_id: str):
    with contextlib.redirect_stdout(io.StringIO()):
        for s in pl.Songs:
            if str(s.ContentID) == str(track_id):
                return s
    return None


def cmd_list(args, db) -> int:
    if args.playlist_id or args.name:
        pl = find_playlist(db, playlist_id=args.playlist_id, name=args.name)
        if not pl:
            print("error: no matching playlist", file=sys.stderr)
            return 1
        out = {"playlists": [serialize_playlist(pl, with_tracks=args.with_tracks)]}
    else:
        with contextlib.redirect_stdout(io.StringIO()):
            pls = list(db.get_playlist())
        out = {"playlists": [serialize_playlist(pl, with_tracks=args.with_tracks) for pl in pls]}
    json.dump(out, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


def cmd_create(args, db) -> int:
    plan = {"action": "create", "name": args.name, "parent": args.parent}
    if args.dry_run:
        json.dump({"dry_run": True, "plan": plan}, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
        return 0

    with contextlib.redirect_stdout(io.StringIO()):
        pl = db.create_playlist(args.name, parent=args.parent)
        db.commit()

    out = {"ok": True, "plan": plan, "playlist": serialize_playlist(pl)}
    json.dump(out, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


def cmd_rename(args, db) -> int:
    pl = find_playlist(db, playlist_id=args.playlist_id, name=args.match_name)
    if not pl:
        print("error: no matching playlist", file=sys.stderr)
        return 1
    plan = {"action": "rename", "playlist_id": str(pl.ID), "before": pl.Name, "after": args.name}
    if args.dry_run:
        json.dump({"dry_run": True, "plan": plan}, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
        return 0

    with contextlib.redirect_stdout(io.StringIO()):
        db.rename_playlist(pl, args.name)
        db.commit()
    json.dump({"ok": True, "plan": plan}, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


def cmd_delete(args, db) -> int:
    pl = find_playlist(db, playlist_id=args.playlist_id, name=args.name)
    if not pl:
        print("error: no matching playlist", file=sys.stderr)
        return 1
    with contextlib.redirect_stdout(io.StringIO()):
        track_count = len(list(pl.Songs))
    plan = {"action": "delete", "playlist_id": str(pl.ID), "name": pl.Name, "track_count": track_count}
    if args.dry_run:
        json.dump({"dry_run": True, "plan": plan}, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
        return 0

    with contextlib.redirect_stdout(io.StringIO()):
        db.delete_playlist(pl)
        db.commit()
    json.dump({"ok": True, "plan": plan}, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


def cmd_add_track(args, db) -> int:
    pl = find_playlist(db, playlist_id=args.playlist_id, name=args.playlist_name)
    if not pl:
        print("error: no matching playlist", file=sys.stderr)
        return 1
    if find_membership(pl, args.track_id):
        print(f"error: track {args.track_id} already in playlist {pl.Name!r}", file=sys.stderr)
        return 3

    plan = {
        "action": "add-track",
        "playlist_id": str(pl.ID),
        "playlist_name": pl.Name,
        "track_id": args.track_id,
        "position": args.position,
    }
    if args.dry_run:
        json.dump({"dry_run": True, "plan": plan}, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
        return 0

    with contextlib.redirect_stdout(io.StringIO()):
        row = db.add_to_playlist(pl, args.track_id, track_no=args.position)
        db.commit()
    plan["membership_id"] = str(row.ID)
    plan["track_no"] = row.TrackNo
    json.dump({"ok": True, "plan": plan}, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


def cmd_remove_track(args, db) -> int:
    pl = find_playlist(db, playlist_id=args.playlist_id, name=args.playlist_name)
    if not pl:
        print("error: no matching playlist", file=sys.stderr)
        return 1
    membership = find_membership(pl, args.track_id)
    if not membership:
        print(f"error: track {args.track_id} not in playlist {pl.Name!r}", file=sys.stderr)
        return 3
    plan = {
        "action": "remove-track",
        "playlist_id": str(pl.ID),
        "playlist_name": pl.Name,
        "track_id": args.track_id,
        "track_no": membership.TrackNo,
    }
    if args.dry_run:
        json.dump({"dry_run": True, "plan": plan}, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
        return 0

    with contextlib.redirect_stdout(io.StringIO()):
        db.remove_from_playlist(pl, membership)
        db.commit()
    json.dump({"ok": True, "plan": plan}, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


def cmd_reorder(args, db) -> int:
    pl = find_playlist(db, playlist_id=args.playlist_id, name=args.playlist_name)
    if not pl:
        print("error: no matching playlist", file=sys.stderr)
        return 1
    membership = find_membership(pl, args.track_id)
    if not membership:
        print(f"error: track {args.track_id} not in playlist {pl.Name!r}", file=sys.stderr)
        return 3
    plan = {
        "action": "reorder",
        "playlist_id": str(pl.ID),
        "track_id": args.track_id,
        "before": membership.TrackNo,
        "after": args.position,
    }
    if args.dry_run:
        json.dump({"dry_run": True, "plan": plan}, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
        return 0

    with contextlib.redirect_stdout(io.StringIO()):
        db.move_song_in_playlist(pl, membership, args.position)
        db.commit()
    json.dump({"ok": True, "plan": plan}, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


def with_safety(args, fn):
    """Wrapper: handle rekordbox-running check + backup before calling fn(args, db)."""
    is_write = not getattr(args, "_read_only", False)
    was_running = rekordbox_running()
    if is_write and was_running and not args.dry_run:
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

    if is_write and not args.dry_run:
        backup_path = backup_master_db()
    else:
        backup_path = None

    try:
        rc = fn(args, db)
    except Exception as e:
        with contextlib.redirect_stdout(io.StringIO()):
            try:
                db.rollback()
            except Exception:
                pass
        print(f"error: {e}", file=sys.stderr)
        if backup_path:
            print(f"backup is intact at: {backup_path}", file=sys.stderr)
        return 4

    if is_write and was_running and args.auto_close_rekordbox and not args.dry_run:
        rblife.reopen()

    if backup_path and rc == 0:
        # Append backup info to the last JSON object on stdout — handled inline above
        # by appending to the message; for simplicity we print a trailing comment.
        pass
    return rc


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)

    def add_write_flags(sp):
        sp.add_argument("--dry-run", action="store_true",
                        help="Print plan without writing")
        sp.add_argument("--force", action="store_true",
                        help="Write even if rekordbox is running (dangerous)")
        sp.add_argument("--auto-close-rekordbox", action="store_true",
                        help="If rekordbox is open, quit it before writing, then reopen after")

    # list
    sp = sub.add_parser("list", help="List playlists")
    sp.add_argument("--name", default=None, help="Filter by exact name")
    sp.add_argument("--playlist-id", default=None)
    sp.add_argument("--with-tracks", action="store_true")
    sp.set_defaults(func=cmd_list, _read_only=True)

    # create
    sp = sub.add_parser("create", help="Create an empty playlist")
    sp.add_argument("--name", required=True)
    sp.add_argument("--parent", default=None,
                    help="Parent playlist/folder ID (default: root)")
    add_write_flags(sp)
    sp.set_defaults(func=cmd_create)

    # rename
    sp = sub.add_parser("rename", help="Rename a playlist")
    sp.add_argument("--playlist-id", default=None)
    sp.add_argument("--match-name", default=None,
                    help="Find playlist by current name (alternative to --playlist-id)")
    sp.add_argument("--name", required=True, help="New name")
    add_write_flags(sp)
    sp.set_defaults(func=cmd_rename)

    # delete
    sp = sub.add_parser("delete", help="Delete a playlist (membership rows go too)")
    sp.add_argument("--playlist-id", default=None)
    sp.add_argument("--name", default=None,
                    help="Find playlist by name (alternative to --playlist-id)")
    add_write_flags(sp)
    sp.set_defaults(func=cmd_delete)

    # add-track
    sp = sub.add_parser("add-track", help="Add a track to a playlist")
    sp.add_argument("--playlist-id", default=None)
    sp.add_argument("--playlist-name", default=None)
    sp.add_argument("--track-id", required=True, help="DjmdContent.ID of the track")
    sp.add_argument("--position", type=int, default=None,
                    help="1-based TrackNo. Default = append to end.")
    add_write_flags(sp)
    sp.set_defaults(func=cmd_add_track)

    # remove-track
    sp = sub.add_parser("remove-track", help="Remove a track from a playlist")
    sp.add_argument("--playlist-id", default=None)
    sp.add_argument("--playlist-name", default=None)
    sp.add_argument("--track-id", required=True)
    add_write_flags(sp)
    sp.set_defaults(func=cmd_remove_track)

    # reorder
    sp = sub.add_parser("reorder", help="Move a track to a new position within a playlist")
    sp.add_argument("--playlist-id", default=None)
    sp.add_argument("--playlist-name", default=None)
    sp.add_argument("--track-id", required=True)
    sp.add_argument("--position", type=int, required=True, help="New 1-based TrackNo")
    add_write_flags(sp)
    sp.set_defaults(func=cmd_reorder)

    args = p.parse_args()
    return with_safety(args, args.func)


if __name__ == "__main__":
    sys.exit(main())
