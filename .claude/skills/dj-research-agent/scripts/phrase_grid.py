#!/usr/bin/env python3
"""Read rekordbox's beat grid + phrase analysis for one track.

Reads master.db for the track's AnalysisDataPath, then parses the .DAT (beat
grid) and .EXT (song structure / PSSI) ANLZ files via pyrekordbox.

Output: JSON object on stdout with bars[] and phrases[]. See the rekordbox
phrase-grid section of reference/rekordbox-extraction.md for the schema.

Usage:
    .venv/bin/python phrase_grid.py --track-id 67810230
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import sys


REKORDBOX_SHARE = os.path.expanduser("~/Library/Pioneer/rekordbox/share")


PHRASE_LABELS_BY_MOOD: dict[int, dict[int, str]] = {
    # Low mood — most detailed phrase set
    3: {
        1: "intro",
        2: "verse-1",
        3: "verse-2",
        4: "verse-3",
        5: "verse-4",
        6: "verse-5",
        7: "verse-6",
        8: "bridge",
        9: "chorus",
        10: "outro",
    },
    # Mid mood — coarser
    2: {
        1: "intro",
        2: "verse-1",
        3: "verse-2",
        4: "chorus",
        5: "bridge",
        6: "outro",
    },
    # High mood — energy-focused; sub-flavors encoded in higher kind ints
    1: {
        1: "intro",
        2: "up",
        3: "down",
        5: "chorus",
        6: "outro",
        7: "up",
    },
}

MOOD_LABEL = {1: "high", 2: "mid", 3: "low"}


def resolve_anlz_paths(rel_path: str) -> tuple[str, str]:
    """PIONEER-relative path → absolute (.DAT, .EXT) tuple."""
    base = REKORDBOX_SHARE + rel_path
    if not base.endswith(".DAT"):
        raise ValueError(f"AnalysisDataPath should end in .DAT, got: {rel_path}")
    ext = base[:-4] + ".EXT"
    return base, ext


def load_track(track_id: str) -> dict:
    """Return {AnalysisDataPath, Title, ArtistName, BPM, Length} for one track."""
    sink = io.StringIO()
    with contextlib.redirect_stdout(sink):
        from pyrekordbox import Rekordbox6Database
        db = Rekordbox6Database()
        c = db.get_content(ID=track_id)
        if c is None:
            raise SystemExit(f"track_id {track_id} not found in master.db")
        out = {
            "track_id": str(c.ID),
            "title": c.Title or "",
            "analysis_data_path": c.AnalysisDataPath,
            "bpm": (c.BPM / 100.0) if c.BPM else None,
            "duration_sec": int(c.Length) if c.Length else None,
            "file_path": c.FolderPath,
        }
    return out


def parse_beats(dat_path: str) -> list[dict]:
    """Parse PQTZ beats from the .DAT file.

    Returns a list of {time_ms, beat_in_bar (1-4), tempo_bpm} dicts.
    """
    from pyrekordbox.anlz import AnlzFile
    f = AnlzFile.parse_file(dat_path)
    beats = []
    for t in f.tags:
        if t.type != "PQTZ":
            continue
        for e in t.content.entries:
            beats.append({
                "time_ms": int(e.time),
                "beat_in_bar": int(e.beat),
                "tempo_bpm": int(e.tempo) / 100.0,
            })
    return beats


def parse_phrases(ext_path: str) -> tuple[int | None, list[dict]] | None:
    """Parse PSSI song structure from the .EXT file.

    Returns (mood, raw_phrases) or None if PSSI is absent.
    raw_phrases items: {index, beat_number_1based, kind_int}
    """
    if not os.path.exists(ext_path):
        return None
    from pyrekordbox.anlz import AnlzFile
    f = AnlzFile.parse_file(ext_path)
    for t in f.tags:
        if t.type != "PSSI":
            continue
        c = t.content
        mood = int(c.mood)
        phrases = []
        for e in c.entries:
            phrases.append({
                "index": int(e.index),
                "beat": int(e.beat),
                "kind": int(e.kind),
            })
        return mood, phrases
    return None


def beat_to_time_ms(beat_1based: int, beats: list[dict]) -> int | None:
    """Translate a 1-based beat number to its time_ms from the PQTZ entries."""
    idx = beat_1based - 1
    if idx < 0 or idx >= len(beats):
        return None
    return beats[idx]["time_ms"]


def build_bars(beats: list[dict]) -> list[dict]:
    """Group beats into bars (each bar = 4 beats starting at beat_in_bar==1)."""
    bars = []
    cur = None
    for i, b in enumerate(beats):
        if b["beat_in_bar"] == 1:
            if cur is not None:
                cur["end_ms"] = b["time_ms"]
                bars.append(cur)
            cur = {
                "bar_index": len(bars),
                "start_ms": b["time_ms"],
                "first_beat_index": i,
            }
    if cur is not None:
        cur["end_ms"] = None  # unknown; trailing bar
        bars.append(cur)
    return bars


def label_phrase(mood: int, kind_int: int) -> str:
    table = PHRASE_LABELS_BY_MOOD.get(mood, {})
    return table.get(kind_int, f"unknown-{kind_int}")


def build_phrases(
    mood: int,
    raw_phrases: list[dict],
    beats: list[dict],
    duration_sec: int | None,
) -> list[dict]:
    """Convert raw PSSI entries into time-aware phrase records."""
    out = []
    for i, p in enumerate(raw_phrases):
        start_ms = beat_to_time_ms(p["beat"], beats)
        # End is the next phrase's start, or end of track
        if i + 1 < len(raw_phrases):
            end_ms = beat_to_time_ms(raw_phrases[i + 1]["beat"], beats)
        else:
            end_ms = (duration_sec * 1000) if duration_sec else None
        out.append({
            "index": p["index"],
            "label": label_phrase(mood, p["kind"]),
            "kind_int": p["kind"],
            "start_beat": p["beat"],
            "start_sec": (start_ms / 1000.0) if start_ms is not None else None,
            "end_sec": (end_ms / 1000.0) if end_ms is not None else None,
        })
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--track-id", required=True, help="DjmdContent.ID")
    args = ap.parse_args()

    track = load_track(args.track_id)
    if not track["analysis_data_path"]:
        sys.stderr.write("track has no AnalysisDataPath — analyze it in rekordbox first\n")
        return 2

    dat_path, ext_path = resolve_anlz_paths(track["analysis_data_path"])
    if not os.path.exists(dat_path):
        sys.stderr.write(f"missing .DAT: {dat_path}\n")
        return 2

    beats = parse_beats(dat_path)
    bars = build_bars(beats)

    phrase_data = parse_phrases(ext_path)
    if phrase_data is None:
        phrases = []
        mood = None
        mood_label = None
    else:
        mood, raw_phrases = phrase_data
        phrases = build_phrases(mood, raw_phrases, beats, track["duration_sec"])
        mood_label = MOOD_LABEL.get(mood)

    out = {
        "track": track,
        "mood": mood,
        "mood_label": mood_label,
        "total_beats": len(beats),
        "total_bars": len(bars),
        "has_phrases": bool(phrases),
        "phrases": phrases,
        "bars": bars,
        "beats": beats,
    }

    json.dump(out, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
