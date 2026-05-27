#!/usr/bin/env python3
"""Harvest mode: for each query, return the top-N YouTube videos sorted by view count.

Use this when you want a *list* of candidates per query (e.g. "all of composer X's
upbeat Telugu songs") rather than picking the single best video. Returns enough
metadata that the agent can apply its own lane filter downstream.

Output: JSON to stdout — list of {query, candidates: [{video_id, title, channel,
published_at, view_count, duration}, ...]}.

Usage:
    python3 youtube_search_topn.py \
        --api-key "$YOUTUBE_API_KEY" \
        --fallback-api-key "$YOUTUBE_API_KEY_FALLBACK" \
        --queries 'Composer X Telugu hits||Composer Y Telugu jukebox' \
        --top-n 25 \
        --order viewCount

Quota: each query consumes ~101 units (search.list = 100, videos.list = 1).
"""
import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

API_BASE = "https://www.googleapis.com/youtube/v3"

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
        raise RuntimeError("No YouTube API key configured")
    try:
        return _request(endpoint, params, key)
    except urllib.error.HTTPError as e:
        if _is_quota_error(e) and active == "primary" and _KEYS["fallback"]:
            if not _KEYS["switched_logged"]:
                print("[youtube_search_topn] primary key quota exhausted; switching to fallback", file=sys.stderr)
                _KEYS["switched_logged"] = True
            _KEYS["active"] = "fallback"
            return _request(endpoint, params, _KEYS["fallback"])
        if _is_quota_error(e) and active == "fallback":
            raise RuntimeError("Both primary and fallback YouTube API keys are quota-exhausted") from e
        raise


def search(query: str, top_n: int, order: str) -> list:
    data = api_get("search", {
        "q": query,
        "part": "snippet",
        "type": "video",
        "maxResults": min(top_n, 50),
        "order": order,
    })
    out = []
    for it in data.get("items", []):
        out.append({
            "video_id": it["id"]["videoId"],
            "title": it["snippet"]["title"],
            "channel": it["snippet"]["channelTitle"],
            "channel_id": it["snippet"]["channelId"],
            "published_at": it["snippet"]["publishedAt"],
        })
    return out


def fetch_video_stats(video_ids: list) -> dict:
    if not video_ids:
        return {}
    out = {}
    # /videos endpoint accepts up to 50 IDs per call
    for i in range(0, len(video_ids), 50):
        chunk = video_ids[i:i+50]
        data = api_get("videos", {
            "id": ",".join(chunk),
            "part": "statistics,contentDetails",
        })
        for it in data.get("items", []):
            out[it["id"]] = {
                "view_count": int(it.get("statistics", {}).get("viewCount", 0)),
                "duration": it["contentDetails"]["duration"],
            }
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--api-key", required=True, help="YouTube Data API v3 key (primary)")
    p.add_argument("--fallback-api-key", help="Optional second key used when primary hits quota")
    p.add_argument("--queries", required=True, help="Queries separated by ||")
    p.add_argument("--top-n", type=int, default=20, help="Max candidates per query (1-50)")
    p.add_argument("--order", default="viewCount",
                   choices=["viewCount", "relevance", "date", "rating"],
                   help="Search ordering — viewCount surfaces popular tracks, relevance is YouTube's default")
    args = p.parse_args()

    _KEYS["primary"] = args.api_key
    _KEYS["fallback"] = args.fallback_api_key

    queries = [q.strip() for q in args.queries.split("||") if q.strip()]
    results = []
    for q in queries:
        try:
            cands = search(q, top_n=args.top_n, order=args.order)
            stats = fetch_video_stats([c["video_id"] for c in cands])
            for c in cands:
                c.update(stats.get(c["video_id"], {}))
            cands.sort(key=lambda c: c.get("view_count", 0), reverse=True)
            results.append({"query": q, "candidates": cands, "count": len(cands)})
        except Exception as e:
            results.append({"query": q, "error": str(e), "type": type(e).__name__})

    json.dump(results, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
