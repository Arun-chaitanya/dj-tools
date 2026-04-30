#!/usr/bin/env python3
"""For a list of (artist/film, title) queries, find the most-viewed canonical YouTube
video for each track and return view count + video ID + channel.

Strategy:
1. For each query, run search.list (100 quota) ordered by relevance, top 3 results.
2. Pick the result with the highest view count among the top 3 (channels like
   Aditya Music / Mango Music / Lahari Music tend to host the canonical video).
3. Skip "lo-fi", "remix", "cover", "trailer", "making" titles when picking.

Output: JSON to stdout — one line per input query, in input order.
Input: stdin newline-delimited queries, OR --queries comma-separated.
"""
import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

API_BASE = "https://www.googleapis.com/youtube/v3"

EXCLUDE_KEYWORDS = ["lo-fi", "lofi", "remix", "cover", "trailer", "making",
                    "promo", "teaser", "audio launch", "behind the scenes",
                    "reaction", "lyrical version", "instrumental", "karaoke"]

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
                print("[youtube_track_views] primary key quota exhausted; switching to fallback", file=sys.stderr)
                _KEYS["switched_logged"] = True
            _KEYS["active"] = "fallback"
            return _request(endpoint, params, _KEYS["fallback"])
        if _is_quota_error(e) and active == "fallback":
            raise RuntimeError("Both primary and fallback YouTube API keys are quota-exhausted") from e
        raise


def search_track(query: str, top_n: int = 5) -> list:
    data = api_get("search", {
        "q": query,
        "part": "snippet",
        "type": "video",
        "maxResults": top_n,
        "order": "relevance",
    })
    out = []
    for it in data.get("items", []):
        out.append({
            "video_id": it["id"]["videoId"],
            "title": it["snippet"]["title"],
            "channel": it["snippet"]["channelTitle"],
            "published_at": it["snippet"]["publishedAt"],
        })
    return out


def fetch_video_stats(video_ids: list) -> dict:
    if not video_ids:
        return {}
    data = api_get("videos", {
        "id": ",".join(video_ids),
        "part": "statistics,contentDetails",
    })
    out = {}
    for it in data.get("items", []):
        out[it["id"]] = {
            "view_count": int(it.get("statistics", {}).get("viewCount", 0)),
            "duration": it["contentDetails"]["duration"],
        }
    return out


def is_excluded(title: str) -> bool:
    low = title.lower()
    return any(k in low for k in EXCLUDE_KEYWORDS)


def pick_best(candidates: list, stats: dict) -> dict:
    eligible = [c for c in candidates
                if not is_excluded(c["title"]) and c["video_id"] in stats]
    if not eligible:
        eligible = [c for c in candidates if c["video_id"] in stats]
    if not eligible:
        return None
    eligible.sort(key=lambda c: stats[c["video_id"]]["view_count"], reverse=True)
    best = eligible[0]
    best.update(stats[best["video_id"]])
    return best


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--api-key", required=True, help="YouTube Data API v3 key (primary)")
    p.add_argument("--fallback-api-key", help="Optional second key used when primary hits quota")
    p.add_argument("--queries", help="Comma-separated queries (otherwise read stdin)")
    args = p.parse_args()

    _KEYS["primary"] = args.api_key
    _KEYS["fallback"] = args.fallback_api_key

    if args.queries:
        queries = [q.strip() for q in args.queries.split("||") if q.strip()]
    else:
        queries = [line.strip() for line in sys.stdin if line.strip()]

    results = []
    for q in queries:
        try:
            cands = search_track(q, top_n=5)
            stats = fetch_video_stats([c["video_id"] for c in cands])
            best = pick_best(cands, stats)
            results.append({
                "query": q,
                "best": best,
                "all_candidates": [
                    {**c, **stats.get(c["video_id"], {})} for c in cands
                ],
            })
        except Exception as e:
            results.append({"query": q, "error": str(e)})

    json.dump(results, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
