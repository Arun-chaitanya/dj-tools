#!/usr/bin/env python3
"""Lock or unlock a track in rekordbox.

Lock = set bit 7 (0x80) of DjmdContent.Analysed. When locked, rekordbox
preserves cues / beat grid / phrase analysis on re-analyze instead of
overwriting them.

Backs up master.db before any write. Refuses to write while rekordbox is
running unless --force is passed.

Usage:
    lock_track.py --track-id 67810230 --lock
    lock_track.py --track-id 67810230 --unlock
    lock_track.py --track-id 67810230 --lock --dry-run
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

LOCK_BIT = 0x80


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--track-id", required=True, help="DjmdContent.ID")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--lock", action="store_true")
    g.add_argument("--unlock", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--auto-close-rekordbox", action="store_true",
                    help="if rekordbox is open, quit it before writing, then reopen after")
    ap.add_argument("--force", action="store_true",
                    help="write even if rekordbox is running (skips quit/reopen)")
    args = ap.parse_args()

    sink = io.StringIO()
    with contextlib.redirect_stdout(sink):
        from pyrekordbox import Rekordbox6Database
        db = Rekordbox6Database()
        c = db.get_content(ID=args.track_id)
        if c is None:
            sys.stderr.write(f"track_id {args.track_id} not found\n")
            return 2
        before = int(c.Analysed or 0)
        after = (before | LOCK_BIT) if args.lock else (before & ~LOCK_BIT)
        title = c.Title or ""

    out: dict = {
        "track_id": args.track_id,
        "title": title,
        "action": "lock" if args.lock else "unlock",
        "analysed_before": before,
        "analysed_after": after,
        "locked_before": bool(before & LOCK_BIT),
        "locked_after": bool(after & LOCK_BIT),
    }

    if before == after:
        out["already"] = True
        json.dump(out, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0

    if args.dry_run:
        out["dry_run"] = True
        json.dump(out, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0

    was_running = rblife.is_running()
    if was_running and not args.force:
        if args.auto_close_rekordbox:
            ok, reason = rblife.graceful_quit()
            if not ok:
                sys.stderr.write(f"could not quit rekordbox: {reason}\n")
                return 2
        else:
            sys.stderr.write(
                "rekordbox is running. "
                "pass --auto-close-rekordbox to close it automatically, "
                "or --force to write anyway.\n")
            return 2

    # Backup master.db
    master_db = os.path.expanduser("~/Library/Pioneer/rekordbox/master.db")
    ts = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = f"{master_db}.bak-{ts}"
    shutil.copy2(master_db, backup)
    out["backup"] = backup

    sink2 = io.StringIO()
    with contextlib.redirect_stdout(sink2):
        from pyrekordbox import Rekordbox6Database
        db = Rekordbox6Database()
        c = db.get_content(ID=args.track_id)
        c.Analysed = after
        db.commit()

    reopened = False
    if was_running and args.auto_close_rekordbox:
        ok, _ = rblife.reopen()
        reopened = ok
    out["rekordbox_was_running"] = was_running
    out["rekordbox_reopened"] = reopened

    json.dump(out, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
