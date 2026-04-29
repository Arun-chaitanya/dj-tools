#!/usr/bin/env python3
"""Fetch YouTube video metadata + top comments via the YouTube Data API v3.

Output: JSON to stdout. Errors: JSON to stderr, non-zero exit.
"""
import argparse
import json
import re
import sys
import urllib.parse
import urllib.request

API_BASE = "https://www.googleapis.com/youtube/v3"


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


def api_get(endpoint: str, params: dict) -> dict:
    qs = urllib.parse.urlencode(params)
    req = urllib.request.Request(f"{API_BASE}/{endpoint}?{qs}")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_video(video_id: str, api_key: str) -> dict:
    data = api_get("videos", {
        "id": video_id,
        "key": api_key,
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


def fetch_comments(video_id: str, api_key: str, max_total: int = 50) -> list:
    out = []
    page_token = None
    while len(out) < max_total:
        params = {
            "videoId": video_id,
            "key": api_key,
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
    p.add_argument("--api-key", required=True, help="YouTube Data API v3 key")
    p.add_argument("--max-comments", type=int, default=50)
    p.add_argument("--no-comments", action="store_true")
    args = p.parse_args()

    try:
        video_id = extract_video_id(args.url)
        video = fetch_video(video_id, args.api_key)
        comments = [] if args.no_comments else fetch_comments(video_id, args.api_key, args.max_comments)
        print(json.dumps({"video": video, "comments": comments}, indent=2, ensure_ascii=False))
        return 0
    except Exception as e:
        print(json.dumps({"error": str(e), "type": type(e).__name__}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
