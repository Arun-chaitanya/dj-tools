#!/usr/bin/env python3
"""Fetch the YouTube "most replayed" heatmap for a track.

Given a rekordbox track_id, looks up Title + Artist in master.db, searches
YouTube, picks the candidate whose duration is closest to the track's
length, and pulls the 100-bucket heatmap via yt-dlp. Derives peak regions
(contiguous high-intensity windows merged together) on top of the raw
buckets.

If YouTube doesn't expose a heatmap for the chosen video (some tracks just
don't have one), the script returns ``has_heatmap: false`` and exits 0 —
this is not an error.

Usage:
    youtube_heatmap.py --track-id 67810230
    youtube_heatmap.py --track-id 67810230 --top-n 5
    youtube_heatmap.py --url https://www.youtube.com/watch?v=...
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

API_BASE = "https://www.googleapis.com/youtube/v3"

# Quota-aware key handling — same shape as youtube_search_topn.py
_KEYS = {"primary": None, "fallback": None, "active": "primary", "switched_logged": False}
_QUOTA_REASONS = {"quotaExceeded", "dailyLimitExceeded", "rateLimitExceeded", "userRateLimitExceeded"}


def _is_quota_error(err: urllib.error.HTTPError) -> bool:
    if err.code != 403:
        return False
    try:
        body = json.loads(err.read().decode("utf-8"))
        for e in body.get("error", {}).get("errors", []):
            if e.get("reason") in _QUOTA_REASONS:
                return True
        return body.get("error", {}).get("status") in ("RESOURCE_EXHAUSTED",)
    except Exception:
        return False


def _request(endpoint: str, params: dict, key: str) -> dict:
    p = {**params, "key": key}
    qs = urllib.parse.urlencode(p)
    req = urllib.request.Request(f"{API_BASE}/{endpoint}?{qs}")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def api_get(endpoint: str, params: dict) -> dict:
    params = {k: v for k, v in params.items() if k != "key"}
    active = _KEYS["active"]
    key = _KEYS[active]
    if not key:
        raise RuntimeError("No YouTube API key configured (set YOUTUBE_API_KEY)")
    try:
        return _request(endpoint, params, key)
    except urllib.error.HTTPError as e:
        if _is_quota_error(e) and active == "primary" and _KEYS["fallback"]:
            if not _KEYS["switched_logged"]:
                sys.stderr.write("[youtube_heatmap] primary key quota exhausted; switching to fallback\n")
                _KEYS["switched_logged"] = True
            _KEYS["active"] = "fallback"
            return _request(endpoint, params, _KEYS["fallback"])
        if _is_quota_error(e) and active == "fallback":
            raise RuntimeError("Both primary and fallback YouTube API keys are quota-exhausted") from e
        raise


# ---------- rekordbox lookup ----------

def load_track_meta(track_id: str) -> dict:
    sink = io.StringIO()
    with contextlib.redirect_stdout(sink):
        from pyrekordbox import Rekordbox6Database
        db = Rekordbox6Database()
        c = db.get_content(ID=track_id)
        if c is None:
            raise SystemExit(f"track_id {track_id} not found in master.db")
        artist_name = None
        try:
            if c.Artist is not None:
                artist_name = c.Artist.Name
        except Exception:
            pass
        return {
            "track_id": str(c.ID),
            "title": c.Title or "",
            "artist": artist_name,
            "duration_sec": int(c.Length) if c.Length else None,
        }


# ---------- YouTube search + duration match ----------

_ISO_DURATION_RE = re.compile(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?")


def iso8601_to_seconds(s: str) -> int:
    """PT3M53S -> 233. Returns 0 if unparseable."""
    if not s:
        return 0
    m = _ISO_DURATION_RE.match(s)
    if not m:
        return 0
    h, mi, se = m.groups()
    return int(h or 0) * 3600 + int(mi or 0) * 60 + int(se or 0)


def search_candidates(query: str, top_n: int) -> list:
    data = api_get("search", {
        "q": query,
        "part": "snippet",
        "type": "video",
        "maxResults": min(top_n, 50),
        "order": "relevance",
    })
    cands = []
    for it in data.get("items", []):
        cands.append({
            "video_id": it["id"]["videoId"],
            "title": it["snippet"]["title"],
            "channel": it["snippet"]["channelTitle"],
        })
    return cands


def fetch_video_durations(video_ids: list) -> dict:
    if not video_ids:
        return {}
    out = {}
    for i in range(0, len(video_ids), 50):
        chunk = video_ids[i:i+50]
        data = api_get("videos", {
            "id": ",".join(chunk),
            "part": "contentDetails,statistics",
        })
        for it in data.get("items", []):
            out[it["id"]] = {
                "duration_sec": iso8601_to_seconds(it["contentDetails"]["duration"]),
                "view_count": int(it.get("statistics", {}).get("viewCount", 0)),
            }
    return out


def pick_best_candidate(cands: list, target_sec: int | None) -> dict | None:
    """Pick the candidate whose duration is within ±15% of target_sec. If no
    target is available, fall back to the first result (YT's relevance order).
    """
    if not cands:
        return None
    if target_sec is None or target_sec <= 0:
        return cands[0]
    tol = max(15, int(target_sec * 0.15))
    in_window = [c for c in cands if abs(c.get("duration_sec", 0) - target_sec) <= tol]
    if in_window:
        # Closest match wins
        in_window.sort(key=lambda c: abs(c["duration_sec"] - target_sec))
        return in_window[0]
    # No duration match — return None so caller can report it instead of
    # silently fetching a wrong video.
    return None


# ---------- yt-dlp heatmap fetch ----------

def fetch_heatmap(youtube_url: str) -> dict:
    """Run yt-dlp --dump-single-json --skip-download. Returns the parsed
    dict (or raises SystemExit with stderr on failure)."""
    try:
        r = subprocess.run(
            ["yt-dlp", "--dump-single-json", "--skip-download", "--no-warnings", youtube_url],
            capture_output=True, text=True, timeout=60,
        )
    except FileNotFoundError:
        raise SystemExit("yt-dlp not found. brew install yt-dlp")
    except subprocess.TimeoutExpired:
        raise SystemExit(f"yt-dlp timed out on {youtube_url}")
    if r.returncode != 0:
        raise SystemExit(f"yt-dlp failed: {r.stderr.strip()[:500]}")
    return json.loads(r.stdout)


# ---------- peak derivation ----------

def derive_peaks(buckets: list, top_n: int = 5) -> list:
    """Group adjacent high-intensity buckets into peak regions.

    Threshold = mean + 1 stddev. Adjacent (or 1-bucket-apart) high buckets
    merge into one region; report each region's start/end time + avg
    intensity. Returns top N by avg intensity.
    """
    if not buckets:
        return []
    values = [b["value"] for b in buckets]
    n = len(values)
    mean = sum(values) / n
    var = sum((v - mean) ** 2 for v in values) / n
    sd = var ** 0.5
    threshold = mean + sd

    regions = []
    cur = None
    for i, b in enumerate(buckets):
        if b["value"] >= threshold:
            if cur is None:
                cur = {"start_idx": i, "end_idx": i}
            else:
                cur["end_idx"] = i
        else:
            # Bridge single-bucket gaps so a dip mid-chorus doesn't split it.
            if cur is not None and i - cur["end_idx"] > 1:
                regions.append(cur)
                cur = None
    if cur is not None:
        regions.append(cur)

    peaks = []
    for r in regions:
        slc = buckets[r["start_idx"]:r["end_idx"] + 1]
        peaks.append({
            "start_sec": round(slc[0]["start_time"], 2),
            "end_sec": round(slc[-1]["end_time"], 2),
            "intensity_avg": round(sum(b["value"] for b in slc) / len(slc), 4),
            "intensity_max": round(max(b["value"] for b in slc), 4),
            "duration_sec": round(slc[-1]["end_time"] - slc[0]["start_time"], 2),
        })

    peaks.sort(key=lambda p: p["intensity_avg"], reverse=True)
    for i, p in enumerate(peaks[:top_n], start=1):
        p["rank"] = i
    return peaks[:top_n]


# ---------- main ----------

def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--track-id", help="DjmdContent.ID — script looks up title/artist + searches YT")
    g.add_argument("--url", help="Direct YouTube URL (bypasses rekordbox lookup + search)")
    ap.add_argument("--search-results", type=int, default=10,
                    help="How many YT candidates to fetch before picking duration-match (default 10)")
    ap.add_argument("--top-peaks", type=int, default=5,
                    help="How many peak regions to derive (default 5)")
    ap.add_argument("--api-key", default=os.environ.get("YOUTUBE_API_KEY"),
                    help="YouTube Data API v3 key (or set YOUTUBE_API_KEY)")
    ap.add_argument("--fallback-api-key", default=os.environ.get("YOUTUBE_API_KEY_FALLBACK"),
                    help="Optional fallback key (or set YOUTUBE_API_KEY_FALLBACK)")
    args = ap.parse_args()

    track_meta: dict[str, Any] = {}
    chosen: dict[str, Any] = {}
    youtube_url: str

    if args.url:
        youtube_url = args.url
    else:
        if not args.api_key:
            raise SystemExit("YOUTUBE_API_KEY required for --track-id mode (or pass --api-key)")
        _KEYS["primary"] = args.api_key
        _KEYS["fallback"] = args.fallback_api_key

        track_meta = load_track_meta(args.track_id)
        query_parts = [track_meta["title"]]
        if track_meta.get("artist"):
            query_parts.append(track_meta["artist"])
        query = " ".join(p for p in query_parts if p)
        if not query.strip():
            raise SystemExit(f"track_id {args.track_id} has no Title — cannot build search query")

        cands = search_candidates(query, top_n=args.search_results)
        if not cands:
            json.dump({
                "track": track_meta,
                "query": query,
                "has_heatmap": False,
                "reason": "no_youtube_results",
            }, sys.stdout, indent=2, ensure_ascii=False)
            sys.stdout.write("\n")
            return 0

        durations = fetch_video_durations([c["video_id"] for c in cands])
        for c in cands:
            c.update(durations.get(c["video_id"], {}))

        picked = pick_best_candidate(cands, track_meta.get("duration_sec"))
        if picked is None:
            json.dump({
                "track": track_meta,
                "query": query,
                "candidates": cands,
                "has_heatmap": False,
                "reason": "no_duration_match",
            }, sys.stdout, indent=2, ensure_ascii=False)
            sys.stdout.write("\n")
            return 0
        chosen = picked
        youtube_url = f"https://www.youtube.com/watch?v={picked['video_id']}"

    info = fetch_heatmap(youtube_url)
    heatmap = info.get("heatmap")
    duration = info.get("duration")
    video_id = info.get("id")

    out: dict[str, Any] = {
        "track": track_meta or None,
        "youtube_url": youtube_url,
        "video_id": video_id,
        "youtube_title": info.get("title"),
        "youtube_channel": info.get("channel") or info.get("uploader"),
        "duration_sec": duration,
        "view_count": info.get("view_count"),
        "chosen_candidate": chosen or None,
    }

    if not heatmap:
        out["has_heatmap"] = False
        json.dump(out, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
        return 0

    buckets = [
        {"start_sec": round(b["start_time"], 2),
         "end_sec": round(b["end_time"], 2),
         "intensity": round(b["value"], 4)}
        for b in heatmap
    ]
    # derive_peaks expects start_time/end_time/value — feed it the raw shape
    peaks = derive_peaks(heatmap, top_n=args.top_peaks)

    out.update({
        "has_heatmap": True,
        "bucket_count": len(buckets),
        "buckets": buckets,
        "peaks": peaks,
    })
    json.dump(out, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
