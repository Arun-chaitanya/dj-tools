#!/usr/bin/env python3
"""Read-only inspector for a rekordbox XML export.

Usage:
    /usr/bin/python3 dj-cueing/inspect_rekordbox.py [xml_path]

Defaults to ./rekordbox-export.xml at the repo root. Pin to /usr/bin/python3:
Homebrew Python 3.14 ships with broken pyexpat bindings on this machine.

Outputs a JSON summary to stdout and writes per-mode reports to dj-cueing/reports/.
Stderr only on errors. Non-zero exit on failure.

Reports written:
  - reports/summary.json          machine-readable overview
  - reports/playlists.md          playlist tree, entry counts, per-playlist cued tracks
  - reports/cued-tracks.md        every track with cues — bar/beat-aligned cue list
  - reports/cue-conventions.md    aggregate analysis: pad slot usage, colour usage,
                                  bar-position histogram, loop usage, memory-cue count
"""

from __future__ import annotations

import json
import os
import sys
import urllib.parse
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_XML = REPO_ROOT / "rekordbox-export.xml"
OUT_DIR = Path(__file__).resolve().parent / "reports"

# rekordbox POSITION_MARK Type codes
TYPE_HOT_CUE = "0"     # also used for memory cues (distinguished by Num=-1)
TYPE_LOOP = "4"
TYPE_FADE_IN = "1"
TYPE_FADE_OUT = "2"
TYPE_LOAD = "3"

# Pad letters for Num 0..15
PAD_LETTERS = list("ABCDEFGHIJKLMNOP")


@dataclass
class Cue:
    type_code: str
    num: int            # -1 = memory cue, 0..15 = pad slot
    start_sec: float
    end_sec: Optional[float]
    name: str
    color_rgb: Optional[tuple]  # (r,g,b) or None

    @property
    def kind(self) -> str:
        if self.type_code == TYPE_LOOP:
            return "loop"
        if self.type_code == TYPE_HOT_CUE and self.num == -1:
            return "memory_cue"
        if self.type_code == TYPE_HOT_CUE:
            return "hot_cue"
        return {TYPE_FADE_IN: "fade_in", TYPE_FADE_OUT: "fade_out", TYPE_LOAD: "load"}.get(
            self.type_code, f"type_{self.type_code}"
        )

    @property
    def pad_letter(self) -> Optional[str]:
        if self.num is None or self.num < 0 or self.num >= len(PAD_LETTERS):
            return None
        return PAD_LETTERS[self.num]


@dataclass
class Tempo:
    inizio_sec: float    # position of this beat marker in seconds
    bpm: float
    metro: str           # e.g. "4/4"
    battito: int         # which beat in the bar (1..4)


@dataclass
class Track:
    track_id: str
    name: str
    artist: str
    bpm: float
    total_time_sec: int
    tonality: str
    location: str        # decoded local path
    tempos: list = field(default_factory=list)
    cues: list = field(default_factory=list)


def _decode_location(loc: str) -> str:
    """rekordbox stores Location as 'file://localhost/path' with %xx escapes."""
    if loc.startswith("file://localhost"):
        loc = loc[len("file://localhost"):]
    elif loc.startswith("file://"):
        loc = loc[len("file://"):]
    return urllib.parse.unquote(loc)


def _parse_color(attrib: dict) -> Optional[tuple]:
    if "Red" in attrib and "Green" in attrib and "Blue" in attrib:
        return (int(attrib["Red"]), int(attrib["Green"]), int(attrib["Blue"]))
    return None


def parse_xml(xml_path: Path) -> tuple[dict[str, Track], list]:
    """Returns (tracks_by_id, playlist_tree). playlist_tree is the raw root NODE element."""
    tree = ET.parse(xml_path)
    root = tree.getroot()
    tracks: dict[str, Track] = {}

    collection = root.find("COLLECTION")
    if collection is None:
        raise ValueError("XML has no <COLLECTION> element — wrong file?")

    for tr in collection.findall("TRACK"):
        tid = tr.get("TrackID")
        if not tid:
            continue
        track = Track(
            track_id=tid,
            name=tr.get("Name", ""),
            artist=tr.get("Artist", ""),
            bpm=float(tr.get("AverageBpm", "0") or 0),
            total_time_sec=int(tr.get("TotalTime", "0") or 0),
            tonality=tr.get("Tonality", ""),
            location=_decode_location(tr.get("Location", "")),
        )
        for tempo in tr.findall("TEMPO"):
            track.tempos.append(Tempo(
                inizio_sec=float(tempo.get("Inizio", "0") or 0),
                bpm=float(tempo.get("Bpm", "0") or 0),
                metro=tempo.get("Metro", ""),
                battito=int(tempo.get("Battito", "0") or 0),
            ))
        for pm in tr.findall("POSITION_MARK"):
            start = float(pm.get("Start", "0") or 0)
            end_attr = pm.get("End")
            track.cues.append(Cue(
                type_code=pm.get("Type", ""),
                num=int(pm.get("Num", "-1") or -1),
                start_sec=start,
                end_sec=float(end_attr) if end_attr else None,
                name=pm.get("Name", ""),
                color_rgb=_parse_color(pm.attrib),
            ))
        tracks[tid] = track

    playlists_root = root.find("PLAYLISTS")
    return tracks, playlists_root


def sec_to_bar_beat(sec: float, track: Track) -> tuple[Optional[int], Optional[float]]:
    """Convert a time in seconds to (bar_number_from_first_beat, beat_in_bar 1.0..4.99).

    Uses the first TEMPO entry (which marks beat 1 of the first bar). Assumes 4/4
    and constant BPM — fine for almost all our material; tracks with multiple TEMPO
    entries would need piecewise math which we skip for now.

    Returns (None, None) if track has no tempo info.
    """
    if not track.tempos or track.bpm <= 0:
        return None, None
    first = track.tempos[0]
    bps = first.bpm / 60.0
    delta = sec - first.inizio_sec
    if delta < 0:
        return None, None
    total_beats = delta * bps
    bar = int(total_beats // 4) + 1   # 1-indexed bar
    beat_in_bar = (total_beats % 4) + 1.0  # 1.0..4.99
    return bar, round(beat_in_bar, 2)


def sec_to_bar_phrase(sec: float, track: Track) -> tuple[Optional[int], Optional[int]]:
    """Convert seconds to (16-bar phrase number, bar within phrase 1..16).

    Phrase boundaries at 16, 32, 48, 64 bars are how DJs think structurally.
    """
    bar, _ = sec_to_bar_beat(sec, track)
    if bar is None:
        return None, None
    phrase = (bar - 1) // 16 + 1
    bar_in_phrase = (bar - 1) % 16 + 1
    return phrase, bar_in_phrase


def walk_playlists(node, depth=0, path=None) -> list[dict]:
    """Flatten the playlist tree into [{'path': 'A/B', 'name', 'type', 'entries', 'track_ids'}]."""
    if path is None:
        path = []
    out = []
    for child in node:
        if child.tag != "NODE":
            continue
        name = child.get("Name", "")
        ntype = child.get("Type", "")
        new_path = path + [name]
        if ntype == "0":  # folder
            out.extend(walk_playlists(child, depth + 1, new_path))
        elif ntype == "1":  # leaf playlist
            track_ids = [tr.get("Key", "") for tr in child.findall("TRACK")]
            out.append({
                "path": "/".join(new_path),
                "name": name,
                "entries": int(child.get("Entries", "0") or 0),
                "track_ids": track_ids,
            })
    return out


def build_summary(tracks: dict[str, Track], playlists: list[dict]) -> dict:
    cued_tracks = [t for t in tracks.values() if t.cues]
    total_marks = sum(len(t.cues) for t in tracks.values())
    pad_usage = Counter()
    color_usage = Counter()
    kind_usage = Counter()
    bar_in_phrase_hist = Counter()
    phrase_hist = Counter()
    for t in cued_tracks:
        for c in t.cues:
            kind_usage[c.kind] += 1
            if c.color_rgb:
                color_usage[c.color_rgb] += 1
            if c.kind == "hot_cue" and c.pad_letter:
                pad_usage[c.pad_letter] += 1
            phrase, bar_in_phrase = sec_to_bar_phrase(c.start_sec, t)
            if phrase is not None:
                phrase_hist[phrase] += 1
                bar_in_phrase_hist[bar_in_phrase] += 1
    return {
        "total_tracks": len(tracks),
        "tracks_with_cues": len(cued_tracks),
        "total_position_marks": total_marks,
        "kind_usage": dict(kind_usage),
        "pad_slot_usage_A_to_P": {k: pad_usage.get(k, 0) for k in PAD_LETTERS},
        "color_usage": [{"rgb": list(rgb), "count": c} for rgb, c in color_usage.most_common()],
        "phrase_position_hist": dict(sorted(phrase_hist.items())),
        "bar_in_phrase_hist_1_to_16": {i: bar_in_phrase_hist.get(i, 0) for i in range(1, 17)},
        "playlists": [
            {"name": pl["name"], "entries": pl["entries"], "path": pl["path"]}
            for pl in playlists
        ],
    }


def render_playlists_md(tracks: dict[str, Track], playlists: list[dict]) -> str:
    lines = ["# Playlists", ""]
    for pl in playlists:
        cued_in_pl = sum(1 for tid in pl["track_ids"] if tid in tracks and tracks[tid].cues)
        lines.append(f"## {pl['path']}  *(entries: {pl['entries']}, with cues: {cued_in_pl})*")
        lines.append("")
        if not pl["track_ids"]:
            lines.append("_(empty)_")
            lines.append("")
            continue
        lines.append("| # | Track | Artist | BPM | Key | Cues |")
        lines.append("|---|-------|--------|-----|-----|------|")
        for i, tid in enumerate(pl["track_ids"], 1):
            t = tracks.get(tid)
            if not t:
                lines.append(f"| {i} | _(missing track {tid})_ | | | | |")
                continue
            cue_count = len([c for c in t.cues if c.kind in ("hot_cue", "memory_cue", "loop")])
            star = "★" if cue_count else ""
            lines.append(
                f"| {i} | {t.name} | {t.artist} | {t.bpm:g} | {t.tonality} | {cue_count}{star} |"
            )
        lines.append("")
    return "\n".join(lines)


def render_cued_tracks_md(tracks: dict[str, Track]) -> str:
    cued = [t for t in tracks.values() if t.cues]
    cued.sort(key=lambda t: (t.artist.lower(), t.name.lower()))
    lines = [
        "# Cued tracks",
        "",
        f"_{len(cued)} tracks have at least one cue/loop/memory mark._",
        "",
        "Bar/phrase columns count from the **first beat** (TEMPO Inizio). "
        "`P:b` = phrase number (16 bars each) and bar within phrase. "
        "Hot-cue pad slot shown as A–P; memory cues have no slot.",
        "",
    ]
    for t in cued:
        lines.append(f"## {t.name} — {t.artist}")
        first_beat = t.tempos[0].inizio_sec if t.tempos else 0.0
        lines.append(
            f"_BPM {t.bpm:g} · {t.tonality or '?'} · {t.total_time_sec}s · "
            f"first beat at {first_beat:.3f}s_"
        )
        lines.append("")
        lines.append("| Slot | Kind | Time (s) | Bar | P:b in phrase | Color (R,G,B) | Loop length |")
        lines.append("|------|------|----------|-----|---------------|---------------|-------------|")
        cues_sorted = sorted(t.cues, key=lambda c: c.start_sec)
        for c in cues_sorted:
            bar, _ = sec_to_bar_beat(c.start_sec, t)
            phrase, bip = sec_to_bar_phrase(c.start_sec, t)
            slot = c.pad_letter or ("mem" if c.kind == "memory_cue" else "-")
            color = ",".join(str(x) for x in c.color_rgb) if c.color_rgb else "-"
            loop_len = ""
            if c.kind == "loop" and c.end_sec is not None:
                loop_sec = c.end_sec - c.start_sec
                if t.bpm > 0:
                    loop_beats = loop_sec * t.bpm / 60.0
                    loop_len = f"{loop_sec:.2f}s ≈ {loop_beats:.1f} beats"
                else:
                    loop_len = f"{loop_sec:.2f}s"
            bar_str = str(bar) if bar is not None else "-"
            phrase_str = f"{phrase}:{bip}" if phrase is not None else "-"
            lines.append(
                f"| {slot} | {c.kind} | {c.start_sec:.2f} | {bar_str} | "
                f"{phrase_str} | {color} | {loop_len} |"
            )
        lines.append("")
    return "\n".join(lines)


def render_conventions_md(summary: dict) -> str:
    lines = ["# Cue conventions — aggregate", ""]
    lines.append(f"- Tracks in collection: **{summary['total_tracks']}**")
    lines.append(f"- Tracks with cues: **{summary['tracks_with_cues']}**")
    lines.append(f"- Total position marks: **{summary['total_position_marks']}**")
    lines.append("")

    lines.append("## By kind")
    lines.append("")
    for k, v in summary["kind_usage"].items():
        lines.append(f"- {k}: **{v}**")
    lines.append("")

    lines.append("## Hot-cue pad slot usage (A–P)")
    lines.append("")
    lines.append("| Slot | Count |")
    lines.append("|------|-------|")
    for letter in PAD_LETTERS:
        lines.append(f"| {letter} | {summary['pad_slot_usage_A_to_P'][letter]} |")
    lines.append("")

    lines.append("## Bar-within-phrase histogram (1..16)")
    lines.append("")
    lines.append(
        "_Where in a 16-bar phrase your cues land. Strong DJs cluster on bar 1 "
        "(phrase boundary); secondary clusters on 9 (mid-phrase) and 13 (build) "
        "are also musical._"
    )
    lines.append("")
    lines.append("| Bar in phrase | Count |")
    lines.append("|---------------|-------|")
    for bar in range(1, 17):
        c = summary["bar_in_phrase_hist_1_to_16"][bar]
        marker = " ←" if bar in (1, 9, 13) and c else ""
        lines.append(f"| {bar} | {c}{marker} |")
    lines.append("")

    lines.append("## Phrase position histogram")
    lines.append("")
    lines.append(
        "_Which 16-bar phrase from track start each cue is in. Phrase 1 = bars 1-16, "
        "phrase 2 = 17-32, etc._"
    )
    lines.append("")
    lines.append("| Phrase | Count |")
    lines.append("|--------|-------|")
    for ph in sorted(summary["phrase_position_hist"].keys()):
        lines.append(f"| {ph} | {summary['phrase_position_hist'][ph]} |")
    lines.append("")

    lines.append("## Cue colour usage")
    lines.append("")
    lines.append("| RGB | Count | Hex |")
    lines.append("|-----|-------|-----|")
    for entry in summary["color_usage"]:
        r, g, b = entry["rgb"]
        hex_color = f"#{r:02X}{g:02X}{b:02X}"
        lines.append(f"| ({r},{g},{b}) | {entry['count']} | `{hex_color}` |")
    lines.append("")
    return "\n".join(lines)


def main():
    xml_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_XML
    if not xml_path.exists():
        print(f"error: xml not found at {xml_path}", file=sys.stderr)
        sys.exit(1)

    tracks, playlists_root = parse_xml(xml_path)
    playlists = walk_playlists(playlists_root) if playlists_root is not None else []

    summary = build_summary(tracks, playlists)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2))
    (OUT_DIR / "playlists.md").write_text(render_playlists_md(tracks, playlists))
    (OUT_DIR / "cued-tracks.md").write_text(render_cued_tracks_md(tracks))
    (OUT_DIR / "cue-conventions.md").write_text(render_conventions_md(summary))

    # stdout summary for the agent
    print(json.dumps({
        "xml_path": str(xml_path),
        "out_dir": str(OUT_DIR),
        "summary": summary,
    }, indent=2))


if __name__ == "__main__":
    main()
