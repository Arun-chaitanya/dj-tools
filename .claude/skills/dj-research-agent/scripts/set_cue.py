#!/usr/bin/env python3
"""Write a single hot cue to the rekordbox master.db.

Add, update, or delete one hot cue on one track. Designed as the lowest-level
write primitive — bulk_cue_from_json.py wraps this logic for batches.

SAFETY:
- Refuses to write if rekordbox is running (pgrep rekordbox).
- Backs up master.db to master.db.bak-<timestamp> before any write.
- --dry-run shows what would happen without writing.

USAGE
    # Add hot cue B at 32.5s with color "red" on track 140962206
    set_cue.py add --track-id 140962206 --slot B --start-sec 32.5 --color red --name "DROP"

    # Update existing slot B (changes start / color / name; keeps slot)
    set_cue.py update --track-id 140962206 --slot B --start-sec 30.0

    # Delete slot B
    set_cue.py delete --track-id 140962206 --slot B

    # List current hot cues (no write)
    set_cue.py list --track-id 140962206

Slot letters A..H map to Kind 1..8 in the rekordbox schema.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import io
import json
import os
import shutil
import subprocess
import sys
import uuid


SLOT_LETTERS = ["A", "B", "C", "D", "E", "F", "G", "H"]
SLOT_TO_KIND = {letter: i + 1 for i, letter in enumerate(SLOT_LETTERS)}
KIND_TO_SLOT = {v: k for k, v in SLOT_TO_KIND.items()}

COLOR_NAMES = {
    "pink":   0,
    "orange": 1,
    "yellow": 2,
    "green":  3,
    "blue":   4,
    "purple": 5,
    "red":    6,
    "none":  -1,
}


def parse_slot(s: str) -> int:
    s = s.upper().strip()
    if s not in SLOT_TO_KIND:
        raise argparse.ArgumentTypeError(f"slot must be A..H, got {s!r}")
    return SLOT_TO_KIND[s]


def parse_color(s: str) -> int:
    s = s.lower().strip()
    if s not in COLOR_NAMES:
        raise argparse.ArgumentTypeError(
            f"color must be one of {sorted(COLOR_NAMES)}, got {s!r}"
        )
    return COLOR_NAMES[s]


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


def make_cue(track_id: str, content_uuid: str, kind: int, start_sec: float,
             color: int, name: str | None):
    """Build a DjmdCue row mirroring the structure of a real hot cue."""
    from pyrekordbox.db6.tables import DjmdCue

    in_msec = int(round(start_sec * 1000))
    return DjmdCue(
        ID=str(uuid.uuid4().int % 10**10),
        ContentID=str(track_id),
        InMsec=in_msec,
        InFrame=0,
        InMpegFrame=0,
        InMpegAbs=0,
        OutMsec=-1,
        OutFrame=0,
        OutMpegFrame=0,
        OutMpegAbs=0,
        Kind=kind,
        Color=color,
        ActiveLoop=0,
        Comment=name or "",
        BeatLoopSize=0,
        CueMicrosec=0,
        InPointSeekInfo="",
        OutPointSeekInfo="",
        ContentUUID=content_uuid,
        UUID=str(uuid.uuid4()),
    )


def cmd_list(args) -> int:
    from pyrekordbox import Rekordbox6Database
    with contextlib.redirect_stdout(io.StringIO()):
        db = Rekordbox6Database()
        track = list(db.get_content().filter_by(ID=str(args.track_id)))

    if not track:
        print(f"error: no track with ID {args.track_id}", file=sys.stderr)
        return 1
    track = track[0]
    hot = sorted(
        [c for c in track.Cues if c.is_hot_cue],
        key=lambda c: c.Kind,
    )
    out = {
        "track_id": str(track.ID),
        "title": track.Title,
        "artists": track.ArtistName,
        "hot_cues": [
            {
                "slot": KIND_TO_SLOT.get(c.Kind, f"?{c.Kind}"),
                "kind": c.Kind,
                "start_sec": c.InMsec / 1000.0 if c.InMsec >= 0 else None,
                "color": c.Color,
                "name": c.Comment or "",
                "is_loop": c.OutMsec is not None and c.OutMsec > 0,
                "cue_id": str(c.ID),
            }
            for c in hot
        ],
    }
    json.dump(out, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


def cmd_write(args, action: str) -> int:
    was_running = rekordbox_running()
    if was_running and not args.dry_run:
        if args.auto_close_rekordbox:
            ok, reason = rblife.graceful_quit()
            if not ok:
                print(f"error: could not close rekordbox: {reason}", file=sys.stderr)
                return 2
        elif not args.force:
            print("error: rekordbox is running. Close it before writing cues, "
                  "pass --auto-close-rekordbox to close it automatically, "
                  "or --force to write anyway (dangerous).", file=sys.stderr)
            return 2

    from pyrekordbox import Rekordbox6Database
    with contextlib.redirect_stdout(io.StringIO()):
        db = Rekordbox6Database()
        track = list(db.get_content().filter_by(ID=str(args.track_id)))

    if not track:
        print(f"error: no track with ID {args.track_id}", file=sys.stderr)
        return 1
    track = track[0]

    kind = parse_slot(args.slot)
    slot_label = args.slot.upper()

    existing = next((c for c in track.Cues if c.is_hot_cue and c.Kind == kind), None)

    if action == "add":
        if existing:
            print(f"error: slot {slot_label} already has a cue at {existing.InMsec/1000:.3f}s. Use 'update' or 'delete' first.", file=sys.stderr)
            return 3
        if args.start_sec is None:
            print("error: --start-sec required for add", file=sys.stderr)
            return 1
        color = parse_color(args.color) if args.color else -1
        new_cue = make_cue(
            track_id=track.ID,
            content_uuid=track.UUID,
            kind=kind,
            start_sec=args.start_sec,
            color=color,
            name=args.name,
        )
        plan = {"action": "add", "slot": slot_label, "start_sec": args.start_sec, "color": args.color or "none", "name": args.name or ""}
    elif action == "update":
        if not existing:
            print(f"error: slot {slot_label} has no cue to update. Use 'add' first.", file=sys.stderr)
            return 3
        plan = {"action": "update", "slot": slot_label, "before": {"start_sec": existing.InMsec/1000, "color": existing.Color, "name": existing.Comment}}
        if args.start_sec is not None:
            existing.InMsec = int(round(args.start_sec * 1000))
        if args.color is not None:
            existing.Color = parse_color(args.color)
        if args.name is not None:
            existing.Comment = args.name
        plan["after"] = {"start_sec": existing.InMsec/1000, "color": existing.Color, "name": existing.Comment}
    elif action == "delete":
        if not existing:
            print(f"error: slot {slot_label} has no cue to delete.", file=sys.stderr)
            return 3
        plan = {"action": "delete", "slot": slot_label, "deleted": {"start_sec": existing.InMsec/1000, "color": existing.Color, "name": existing.Comment}}
    else:
        raise ValueError(action)

    if args.dry_run:
        json.dump({"dry_run": True, "track": {"id": str(track.ID), "title": track.Title}, "plan": plan}, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
        return 0

    backup_path = backup_master_db()

    with contextlib.redirect_stdout(io.StringIO()):
        if action == "add":
            db.add(new_cue)
        elif action == "delete":
            db.delete(existing)
        # update mutations already applied to the tracked instance
        db.commit()

    reopened = False
    if was_running and args.auto_close_rekordbox:
        ok, _ = rblife.reopen()
        reopened = ok

    result = {
        "ok": True,
        "track": {"id": str(track.ID), "title": track.Title},
        "plan": plan,
        "backup": backup_path,
        "rekordbox_was_running": was_running,
        "rekordbox_reopened": reopened,
    }
    json.dump(result, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--track-id", required=True, help="DjmdContent.ID of the track")

    p_list = sub.add_parser("list", parents=[common], help="List current hot cues on a track")
    p_list.set_defaults(func=cmd_list)

    for action in ("add", "update", "delete"):
        sp = sub.add_parser(action, parents=[common], help=f"{action} a hot cue")
        sp.add_argument("--slot", required=True, help="Hot cue slot A..H")
        if action != "delete":
            sp.add_argument("--start-sec", type=float,
                            default=None,
                            help="Cue position in seconds (float)")
            sp.add_argument("--color",
                            default=None,
                            help=f"Color name: {', '.join(sorted(COLOR_NAMES))}")
            sp.add_argument("--name",
                            default=None,
                            help='Cue label (e.g. "INTRO", "DROP")')
        sp.add_argument("--dry-run", action="store_true",
                        help="Print plan without writing")
        sp.add_argument("--force", action="store_true",
                        help="Write even if rekordbox is running (dangerous)")
        sp.add_argument("--auto-close-rekordbox", action="store_true",
                        help="If rekordbox is open, quit it before writing, "
                             "then reopen after (graceful quit only — fails "
                             "if a save-dialog blocks the quit).")
        sp.set_defaults(func=lambda args, _a=action: cmd_write(args, _a))

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
