#!/usr/bin/env python3
"""Fetch YouTube video metadata + top comments via the YouTube Data API v3.

Output: JSON to stdout. Errors: JSON to stderr, non-zero exit.
"""
import argparse
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

API_BASE = "https://www.googleapis.com/youtube/v3"

# Mutable, module-level: set once by main(), consulted by api_get on 403.
_KEYS = {"primary": None, "fallback": None, "active": "primary", "switched_logged": False}

# YouTube Data API quota-related error reasons we'll fall back on.
_QUOTA_REASONS = {"quotaExceeded", "dailyLimitExceeded", "rateLimitExceeded", "userRateLimitExceeded"}


def extract_video_id(url_or_id: str) -> str:
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", url_or_id):
        return url_or_id
    parsed = urllib.parse.urlparse(url_or_id)
    if parsed.hostname in ("youtu.be",):
        return parsed.path.lstrip("/")
    qs = urllib.parse.parse_qs(parsed.query)
    if "v" in qs:
        return qs["v"][0]
    m = re.search(r"/(?:embed|shorts)/([A-Za-z0-9_-]{11})", parsed.path)
    if m:
        return m.group(1)
    raise ValueError(f"Could not extract video ID from: {url_or_id}")


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
    """Call the YouTube API; if the active key hits quota and a fallback key is
    configured, swap to the fallback and retry transparently.
    Callers must NOT include 'key' in params — _KEYS controls the key used."""
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
                print("[youtube_fetch] primary key quota exhausted; switching to fallback", file=sys.stderr)
                _KEYS["switched_logged"] = True
            _KEYS["active"] = "fallback"
            return _request(endpoint, params, _KEYS["fallback"])
        if _is_quota_error(e) and active == "fallback":
            raise RuntimeError("Both primary and fallback YouTube API keys are quota-exhausted") from e
        raise


def fetch_video(video_id: str) -> dict:
    data = api_get("videos", {
        "id": video_id,
        "part": "snippet,contentDetails,statistics",
    })
    items = data.get("items", [])
    if not items:
        raise ValueError(f"Video not found: {video_id}")
    v = items[0]
    return {
        "video_id": v["id"],
        "title": v["snippet"]["title"],
        "channel": v["snippet"]["channelTitle"],
        "channel_id": v["snippet"]["channelId"],
        "published_at": v["snippet"]["publishedAt"],
        "duration": v["contentDetails"]["duration"],
        "view_count": v.get("statistics", {}).get("viewCount"),
        "description": v["snippet"]["description"],
    }


def fetch_comments(video_id: str, max_total: int = 50) -> list:
    out = []
    page_token = None
    while len(out) < max_total:
        params = {
            "videoId": video_id,
            "part": "snippet",
            "maxResults": min(100, max_total - len(out)),
            "order": "relevance",
            "textFormat": "plainText",
        }
        if page_token:
            params["pageToken"] = page_token
        try:
            data = api_get("commentThreads", params)
        except urllib.error.HTTPError as e:
            # Comments-disabled returns 403 with reason 'commentsDisabled' — not a quota issue.
            if e.code == 403:
                return [{"error": "Comments disabled or not accessible", "items": []}]
            raise
        for item in data.get("items", []):
            top = item["snippet"]["topLevelComment"]["snippet"]
            out.append({
                "author": top["authorDisplayName"],
                "text": top["textDisplay"],
                "like_count": top.get("likeCount", 0),
                "published_at": top["publishedAt"],
            })
        page_token = data.get("nextPageToken")
        if not page_token:
            break
    return out


def main() -> int:
    p = argparse.ArgumentParser(description="Fetch YouTube video metadata + comments")
    p.add_argument("--url", required=True, help="YouTube URL or 11-char video ID")
    p.add_argument("--api-key", required=True, help="YouTube Data API v3 key (primary)")
    p.add_argument("--fallback-api-key", help="Optional second key used when primary hits quota")
    p.add_argument("--max-comments", type=int, default=50)
    p.add_argument("--no-comments", action="store_true")
    args = p.parse_args()

    _KEYS["primary"] = args.api_key
    _KEYS["fallback"] = args.fallback_api_key

    try:
        video_id = extract_video_id(args.url)
        video = fetch_video(video_id)
        comments = [] if args.no_comments else fetch_comments(video_id, args.max_comments)
        print(json.dumps({"video": video, "comments": comments}, indent=2, ensure_ascii=False))
        return 0
    except Exception as e:
        print(json.dumps({"error": str(e), "type": type(e).__name__}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
