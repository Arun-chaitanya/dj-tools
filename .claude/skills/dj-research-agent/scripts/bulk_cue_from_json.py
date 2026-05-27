#!/usr/bin/env python3
"""Apply a batch of hot-cue edits across many tracks from a JSON plan.

This is the write target for analyze_structure.py (the future structural-
analysis module). It takes a plan that says "for track X, add a hot cue at
slot Y at time T with color C", and applies all of it in one transaction.

SAFETY:
- Refuses to write if rekordbox is running (unless --force).
- Backs up master.db before any change.
- --dry-run prints the resolved plan (what would actually happen, with the
  before/after state of each track) without writing anything.
- The whole batch is one transaction — if any edit errors, nothing is written.

USAGE
    bulk_cue_from_json.py --plan plan.json [--dry-run] [--force]

PLAN FORMAT (the JSON file)

    {
      "name": "Telugu 9XM mix-in/mix-out cues, v1",   // freeform, optional
      "edits": [
        {
          "track_id": "140962206",                  // required
          "ops": [
            {"action": "add",    "slot": "F", "start_sec": 32.5, "color": "green", "name": "MIX-IN"},
            {"action": "add",    "slot": "G", "start_sec": 178.0, "color": "red",   "name": "MIX-OUT"},
            {"action": "update", "slot": "A", "start_sec": 6.0},
            {"action": "delete", "slot": "H"}
          ]
        },
        { "track_id": "...", "ops": [ ... ] }
      ]
    }

Action semantics:
- add: slot must be empty. Fails the batch if slot is already used.
- update: slot must be non-empty. Partial fields are allowed (omit any of
  start_sec / color / name).
- delete: slot must be non-empty.

Slots are A..H. Colors: pink, orange, yellow, green, blue, purple, red, none.
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
    "pink": 0, "orange": 1, "yellow": 2, "green": 3,
    "blue": 4, "purple": 5, "red": 6, "none": -1,
}


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


def parse_slot(s: str) -> int:
    s = s.upper().strip()
    if s not in SLOT_TO_KIND:
        raise ValueError(f"slot must be A..H, got {s!r}")
    return SLOT_TO_KIND[s]


def parse_color(s) -> int:
    if s is None:
        return -1
    if isinstance(s, int):
        return s
    s = s.lower().strip()
    if s not in COLOR_NAMES:
        raise ValueError(f"color must be one of {sorted(COLOR_NAMES)}, got {s!r}")
    return COLOR_NAMES[s]


def make_cue(track_id, content_uuid, kind, start_sec, color, name):
    from pyrekordbox.db6.tables import DjmdCue
    return DjmdCue(
        ID=str(uuid.uuid4().int % 10**10),
        ContentID=str(track_id),
        InMsec=int(round(start_sec * 1000)),
        InFrame=0, InMpegFrame=0, InMpegAbs=0,
        OutMsec=-1, OutFrame=0, OutMpegFrame=0, OutMpegAbs=0,
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


def resolve_plan(db, plan: dict) -> dict:
    """Walk the plan, validating against the DB, returning a resolved diff.

    Raises ValueError on any plan error. Doesn't mutate the DB.
    Returns:
      {
        "tracks": [
          {"track_id": "...", "title": "...", "before": [...hot_cues...], "ops_resolved": [...]}
        ]
      }
    """
    resolved_tracks = []
    for edit in plan.get("edits", []):
        track_id = str(edit["track_id"])
        track = list(db.get_content().filter_by(ID=track_id))
        if not track:
            raise ValueError(f"unknown track_id {track_id!r}")
        track = track[0]

        before = sorted(
            [
                {
                    "slot": KIND_TO_SLOT.get(c.Kind, f"?{c.Kind}"),
                    "kind": c.Kind,
                    "start_sec": (c.InMsec / 1000.0) if c.InMsec >= 0 else None,
                    "color": c.Color,
                    "name": c.Comment or "",
                    "cue_id": str(c.ID),
                }
                for c in track.Cues if c.is_hot_cue
            ],
            key=lambda d: d["kind"],
        )
        slots_taken = {b["kind"] for b in before}

        ops_resolved = []
        for op in edit["ops"]:
            action = op["action"]
            kind = parse_slot(op["slot"])
            r = {"action": action, "slot": op["slot"].upper(), "kind": kind}

            if action == "add":
                if kind in slots_taken:
                    raise ValueError(f"track {track_id} ({track.Title}): slot {op['slot']} already used; use update or delete first")
                if op.get("start_sec") is None:
                    raise ValueError(f"track {track_id}: add requires start_sec")
                r["start_sec"] = float(op["start_sec"])
                r["color"] = parse_color(op.get("color"))
                r["name"] = op.get("name") or ""
                slots_taken.add(kind)
            elif action == "update":
                if kind not in slots_taken:
                    raise ValueError(f"track {track_id}: slot {op['slot']} has no cue to update")
                r["start_sec"] = float(op["start_sec"]) if op.get("start_sec") is not None else None
                r["color"] = parse_color(op["color"]) if op.get("color") is not None else None
                r["name"] = op["name"] if op.get("name") is not None else None
            elif action == "delete":
                if kind not in slots_taken:
                    raise ValueError(f"track {track_id}: slot {op['slot']} has no cue to delete")
                slots_taken.discard(kind)
            else:
                raise ValueError(f"unknown action {action!r}")

            ops_resolved.append(r)

        resolved_tracks.append({
            "track_id": track_id,
            "title": track.Title,
            "artists": track.ArtistName,
            "before": before,
            "ops": ops_resolved,
            "_orm_track": track,  # carried internally, stripped before JSON output
        })

    return {"tracks": resolved_tracks}


def apply_plan(db, resolved: dict) -> None:
    """Apply the resolved plan to the DB session. Caller commits."""
    from pyrekordbox.db6.tables import DjmdCue

    for rt in resolved["tracks"]:
        track = rt["_orm_track"]
        existing_by_kind = {c.Kind: c for c in track.Cues if c.is_hot_cue}

        for op in rt["ops"]:
            kind = op["kind"]
            if op["action"] == "add":
                db.add(make_cue(
                    track_id=track.ID,
                    content_uuid=track.UUID,
                    kind=kind,
                    start_sec=op["start_sec"],
                    color=op["color"],
                    name=op["name"],
                ))
            elif op["action"] == "update":
                cue = existing_by_kind[kind]
                if op["start_sec"] is not None:
                    cue.InMsec = int(round(op["start_sec"] * 1000))
                if op["color"] is not None:
                    cue.Color = op["color"]
                if op["name"] is not None:
                    cue.Comment = op["name"]
            elif op["action"] == "delete":
                db.delete(existing_by_kind[kind])


def strip_internal(resolved: dict) -> dict:
    return {
        "tracks": [
            {k: v for k, v in t.items() if not k.startswith("_")}
            for t in resolved["tracks"]
        ]
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--plan", required=True, help="Path to plan JSON file")
    p.add_argument("--dry-run", action="store_true",
                   help="Resolve and print the plan without writing")
    p.add_argument("--force", action="store_true",
                   help="Write even if rekordbox is running (dangerous)")
    p.add_argument("--auto-close-rekordbox", action="store_true",
                   help="If rekordbox is open, quit it before writing, then "
                        "reopen after (graceful quit only — fails if a "
                        "save-dialog blocks the quit).")
    args = p.parse_args()

    if not os.path.isfile(args.plan):
        print(f"error: plan file not found: {args.plan}", file=sys.stderr)
        return 1

    with open(args.plan) as f:
        plan = json.load(f)

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
        try:
            resolved = resolve_plan(db, plan)
        except ValueError as e:
            print(f"error: plan validation failed: {e}", file=sys.stderr)
            return 3

    if args.dry_run:
        out = {
            "dry_run": True,
            "plan_name": plan.get("name", ""),
            "track_count": len(resolved["tracks"]),
            "op_count": sum(len(t["ops"]) for t in resolved["tracks"]),
            **strip_internal(resolved),
        }
        json.dump(out, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
        return 0

    backup_path = backup_master_db()
    with contextlib.redirect_stdout(io.StringIO()):
        try:
            apply_plan(db, resolved)
            db.commit()
        except Exception as e:
            db.rollback()
            print(f"error: write failed, rolled back: {e}", file=sys.stderr)
            print(f"backup is intact at: {backup_path}", file=sys.stderr)
            return 4

    reopened = False
    if was_running and args.auto_close_rekordbox:
        ok, _ = rblife.reopen()
        reopened = ok

    out = {
        "ok": True,
        "plan_name": plan.get("name", ""),
        "tracks_changed": len(resolved["tracks"]),
        "ops_applied": sum(len(t["ops"]) for t in resolved["tracks"]),
        "backup": backup_path,
        "rekordbox_was_running": was_running,
        "rekordbox_reopened": reopened,
    }
    json.dump(out, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
