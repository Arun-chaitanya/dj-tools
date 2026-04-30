#!/usr/bin/env python3
"""Fetch a YouTube playlist's items (title + channel + video_id) via the YouTube Data API v3.

Output: JSON to stdout. Errors: JSON to stderr, non-zero exit.

Usage:
    python3 youtube_playlist_fetch.py --url "<playlist-url-or-id>" --api-key "$YOUTUBE_API_KEY"

Notes:
- Pages through up to `--max-items` (default 200) results.
- For very large playlists (5000+ items), API quota may matter; default cap protects against runaway calls.
"""
import argparse
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

API_BASE = "https://www.googleapis.com/youtube/v3"

_KEYS = {"primary": None, "fallback": None, "active": "primary", "switched_logged": False}
_QUOTA_REASONS = {"quotaExceeded", "dailyLimitExceeded", "rateLimitExceeded", "userRateLimitExceeded"}


def extract_playlist_id(url_or_id: str) -> str:
    # Bare playlist IDs start with PL, OL, UU, FL, RD, LL and have 18-34 chars
    if re.fullmatch(r"(PL|OL|UU|FL|RD|LL|UC)[A-Za-z0-9_-]{16,40}", url_or_id):
        return url_or_id
    parsed = urllib.parse.urlparse(url_or_id)
    qs = urllib.parse.parse_qs(parsed.query)
    if "list" in qs:
        return qs["list"][0]
    raise ValueError(f"Could not extract playlist ID from: {url_or_id}")


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
                print("[youtube_playlist_fetch] primary key quota exhausted; switching to fallback", file=sys.stderr)
                _KEYS["switched_logged"] = True
            _KEYS["active"] = "fallback"
            return _request(endpoint, params, _KEYS["fallback"])
        if _is_quota_error(e) and active == "fallback":
            raise RuntimeError("Both primary and fallback YouTube API keys are quota-exhausted") from e
        raise


def fetch_playlist_meta(playlist_id: str) -> dict:
    data = api_get("playlists", {
        "id": playlist_id,
        "part": "snippet,contentDetails",
    })
    items = data.get("items", [])
    if not items:
        raise ValueError(f"Playlist not found: {playlist_id}")
    p = items[0]
    return {
        "playlist_id": p["id"],
        "title": p["snippet"]["title"],
        "channel": p["snippet"]["channelTitle"],
        "channel_id": p["snippet"]["channelId"],
        "description": p["snippet"].get("description", ""),
        "item_count": p["contentDetails"]["itemCount"],
        "published_at": p["snippet"].get("publishedAt"),
    }


def fetch_playlist_items(playlist_id: str, max_items: int) -> list:
    items = []
    page_token = None
    while True:
        params = {
            "playlistId": playlist_id,
            "part": "snippet,contentDetails",
            "maxResults": 50,
        }
        if page_token:
            params["pageToken"] = page_token
        data = api_get("playlistItems", params)
        for it in data.get("items", []):
            sn = it["snippet"]
            items.append({
                "position": sn.get("position"),
                "video_id": it["contentDetails"]["videoId"],
                "title": sn.get("title"),
                "video_owner_channel": sn.get("videoOwnerChannelTitle"),
                "video_owner_channel_id": sn.get("videoOwnerChannelId"),
                "published_at": it["contentDetails"].get("videoPublishedAt"),
            })
            if len(items) >= max_items:
                return items
        page_token = data.get("nextPageToken")
        if not page_token:
            break
    return items


def main():
    parser = argparse.ArgumentParser(description="Fetch YouTube playlist metadata + items")
    parser.add_argument("--url", required=True, help="YouTube playlist URL or ID")
    parser.add_argument("--api-key", required=True, help="YouTube Data API v3 key (primary)")
    parser.add_argument("--fallback-api-key", help="Optional second key used when primary hits quota")
    parser.add_argument("--max-items", type=int, default=200,
                        help="Cap items returned (default 200)")
    args = parser.parse_args()

    _KEYS["primary"] = args.api_key
    _KEYS["fallback"] = args.fallback_api_key

    try:
        playlist_id = extract_playlist_id(args.url)
        meta = fetch_playlist_meta(playlist_id)
        items = fetch_playlist_items(playlist_id, args.max_items)
        out = {
            "playlist": meta,
            "items": items,
            "items_returned": len(items),
            "items_capped_at": args.max_items if len(items) >= args.max_items else None,
        }
        json.dump(out, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
    except Exception as e:
        json.dump({"error": str(e), "type": type(e).__name__}, sys.stderr)
        sys.stderr.write("\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
