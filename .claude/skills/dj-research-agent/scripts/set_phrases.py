#!/usr/bin/env python3
"""Write a phrase plan (mood + phrases[]) into a track's PSSI tag.

Replaces the PSSI entries in the track's .EXT ANLZ file. Backs up the .EXT
before writing. Optionally also flips the lock bit in master.db
(--auto-lock) so rekordbox preserves the edit on next reanalysis.

Plan JSON shape (see reference/rekordbox-extraction.md):
    {
      "track_id": "67810230",
      "mood": 3,
      "phrases": [
        { "start_beat": 1,   "label": "intro" },
        { "start_beat": 17,  "label": "verse-1" },
        ...
      ]
    }

Usage:
    set_phrases.py --plan plan.json --dry-run
    set_phrases.py --plan plan.json
    set_phrases.py --plan plan.json --auto-lock
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
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _rekordbox_lifecycle as rblife  # noqa: E402

REKORDBOX_SHARE = os.path.expanduser("~/Library/Pioneer/rekordbox/share")

PHRASE_LABELS_BY_MOOD: dict[int, dict[int, str]] = {
    3: {1: "intro", 2: "verse-1", 3: "verse-2", 4: "verse-3", 5: "verse-4",
        6: "verse-5", 7: "verse-6", 8: "bridge", 9: "chorus", 10: "outro"},
    2: {1: "intro", 2: "verse-1", 3: "verse-2", 4: "chorus", 5: "bridge", 6: "outro"},
    1: {1: "intro", 2: "up", 3: "down", 5: "chorus", 6: "outro", 7: "up"},
}

LOCK_BIT = 0x80  # DjmdContent.Analysed bit 7 — locked when set

PSSI_ENTRY_SIZE = 24
PSSI_LEN_HEADER = 32


def label_to_kind_int(mood: int, label: str) -> int:
    table = PHRASE_LABELS_BY_MOOD.get(mood)
    if table is None:
        raise SystemExit(f"unknown mood {mood} (must be 1/2/3)")
    # Reverse-lookup; preserve the first int that maps to this label (mood 1
    # has duplicates for "up" — earlier int wins, matches rekordbox UI).
    for k_int, k_label in table.items():
        if k_label == label:
            return k_int
    valid = sorted(set(table.values()))
    raise SystemExit(f"unknown label {label!r} for mood {mood}. valid: {valid}")


def load_track_meta(track_id: str) -> dict:
    sink = io.StringIO()
    with contextlib.redirect_stdout(sink):
        from pyrekordbox import Rekordbox6Database
        db = Rekordbox6Database()
        c = db.get_content(ID=track_id)
        if c is None:
            raise SystemExit(f"track_id {track_id} not found in master.db")
        return {
            "track_id": str(c.ID),
            "title": c.Title or "",
            "analysis_data_path": c.AnalysisDataPath,
            "bpm": (c.BPM / 100.0) if c.BPM else None,
            "duration_sec": int(c.Length) if c.Length else None,
            "analysed": int(c.Analysed) if c.Analysed is not None else None,
        }


def resolve_ext_path(rel_path: str) -> str:
    base = REKORDBOX_SHARE + rel_path
    if not base.endswith(".DAT"):
        raise SystemExit(f"AnalysisDataPath doesn't end in .DAT: {rel_path}")
    return base[:-4] + ".EXT"


def build_pssi_entries(plan_phrases: list[dict], mood: int) -> list[dict]:
    """Translate plan phrases → PSSI entry dicts (with kind_int + zero fillers)."""
    if not plan_phrases:
        raise SystemExit("plan.phrases must not be empty")
    # Sort by start_beat (defensive — humans may write out of order)
    sorted_phrases = sorted(plan_phrases, key=lambda p: p["start_beat"])
    entries = []
    seen_beats = set()
    for i, p in enumerate(sorted_phrases, start=1):
        sb = int(p["start_beat"])
        if sb < 1:
            raise SystemExit(f"start_beat must be >= 1, got {sb}")
        if sb in seen_beats:
            raise SystemExit(f"duplicate start_beat {sb}")
        seen_beats.add(sb)
        kind = label_to_kind_int(mood, p["label"])
        entries.append({
            "index": i, "beat": sb, "kind": kind,
            # All the u*/k*/b/beat_2..4/fill/beat_fill fields observed as 0
            # in real rekordbox-written PSSI tags across many tracks.
            "u1": 0, "k1": 0, "u2": 0, "k2": 0, "u3": 0, "b": 0,
            "beat_2": 0, "beat_3": 0, "beat_4": 0,
            "u4": 0, "k3": 0, "u5": 0, "fill": 0, "beat_fill": 0,
        })
    return entries


def apply_plan_to_pssi(anlz, plan: dict) -> dict:
    """Mutate the PSSI tag inside an already-parsed AnlzFile. Returns a diff."""
    pssi_tag = None
    for t in anlz.tags:
        if t.type == "PSSI":
            pssi_tag = t
            break
    if pssi_tag is None:
        raise SystemExit("track has no PSSI tag — analyze phrase in rekordbox first")

    c = pssi_tag.content
    new_mood = int(plan["mood"])
    new_entries = build_pssi_entries(plan["phrases"], new_mood)

    diff = {
        "mood_before": int(c.mood),
        "mood_after": new_mood,
        "phrase_count_before": len(c.entries),
        "phrase_count_after": len(new_entries),
    }

    # Set fields (Construct Containers are dict-like)
    c.mood = new_mood
    c.len_entries = len(new_entries)
    # Replace entries — assigning a fresh list works with Construct
    from construct import Container
    c.entries = [Container(**e) for e in new_entries]

    # Recompute the tag's len_tag — PSSI has no custom update_len
    pssi_tag.struct.len_tag = PSSI_LEN_HEADER + len(new_entries) * PSSI_ENTRY_SIZE

    return diff


def write_lock_bit(track_id: str, lock: bool, dry_run: bool) -> dict:
    """Set/clear bit 7 (0x80) of DjmdContent.Analysed. Backs up master.db."""
    sink = io.StringIO()
    with contextlib.redirect_stdout(sink):
        from pyrekordbox import Rekordbox6Database
        db = Rekordbox6Database()
        c = db.get_content(ID=track_id)
        if c is None:
            raise SystemExit(f"track_id {track_id} not found")
        before = int(c.Analysed or 0)
        after = (before | LOCK_BIT) if lock else (before & ~LOCK_BIT)
        if before == after:
            return {"already": True, "analysed": before}
        if dry_run:
            return {"dry_run": True, "analysed_before": before, "analysed_after": after}

        # Backup master.db
        master_db = os.path.expanduser("~/Library/Pioneer/rekordbox/master.db")
        ts = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = f"{master_db}.bak-{ts}"
        shutil.copy2(master_db, backup)

        c.Analysed = after
        db.commit()
        return {"backup": backup, "analysed_before": before, "analysed_after": after}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", required=True, help="path to phrase plan JSON")
    ap.add_argument("--dry-run", action="store_true",
                    help="parse + validate plan, print diff, do not write")
    ap.add_argument("--auto-lock", action="store_true",
                    help="also flip the lock bit (Analysed |= 0x80) after writing PSSI")
    ap.add_argument("--auto-close-rekordbox", action="store_true",
                    help="if rekordbox is open, quit it before writing, then reopen after")
    ap.add_argument("--force", action="store_true",
                    help="write even if rekordbox is running (skips quit/reopen)")
    args = ap.parse_args()

    with open(args.plan) as f:
        plan = json.load(f)
    for k in ("track_id", "mood", "phrases"):
        if k not in plan:
            raise SystemExit(f"plan missing required key: {k}")

    track_id = str(plan["track_id"])
    meta = load_track_meta(track_id)

    if not meta["analysis_data_path"]:
        raise SystemExit("track has no AnalysisDataPath — analyze in rekordbox first")

    ext_path = resolve_ext_path(meta["analysis_data_path"])
    if not os.path.exists(ext_path):
        raise SystemExit(f"missing .EXT: {ext_path}")

    # Parse + apply
    from pyrekordbox.anlz import AnlzFile
    with open(ext_path, "rb") as f:
        original_bytes = f.read()
    anlz = AnlzFile.parse(original_bytes)
    diff = apply_plan_to_pssi(anlz, plan)
    new_bytes = anlz.build()

    if args.dry_run:
        out = {
            "dry_run": True,
            "track": meta,
            "ext_path": ext_path,
            "diff": diff,
            "original_size": len(original_bytes),
            "new_size": len(new_bytes),
            "plan_phrases": plan["phrases"],
        }
        json.dump(out, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0

    # rekordbox lifecycle
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
                "or --force to write anyway (not recommended).\n")
            return 2

    # Backup .EXT
    ts = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = f"{ext_path}.bak-{ts}"
    shutil.copy2(ext_path, backup)

    # Write new .EXT
    with open(ext_path, "wb") as f:
        f.write(new_bytes)

    out: dict[str, Any] = {
        "track": meta,
        "ext_path": ext_path,
        "ext_backup": backup,
        "diff": diff,
    }

    if args.auto_lock:
        out["lock"] = write_lock_bit(track_id, True, dry_run=False)

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
