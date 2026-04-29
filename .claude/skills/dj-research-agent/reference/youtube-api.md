# YouTube Data API v3 — quick reference

## Endpoints we use

- `videos` — `id, key, part=snippet,contentDetails,statistics` → title, description, channel, duration.
- `commentThreads` — `videoId, key, part=snippet, order=relevance, maxResults=100` → top comments. Tracklists are often pinned in comments.

## Quotas

Default daily quota: **10,000 units**. Costs:
- `videos.list` = 1 unit
- `commentThreads.list` = 1 unit
- `search.list` = **100 units** (avoid; use targeted endpoints)

So one tracklist extraction costs ~2 units. You can do ~5,000 mixes/day.

## Tracklist parsing tips

Description formats seen in the wild:

```
1. Artist - Title [02:34]
01) Artist - Title (Original Mix)
[02:34] Artist - Title
02:34 Artist - Title
Artist - Title — 02:34
```

Common gotchas:
- Some DJs list **only the artist** ("Disclosure b2b Eats Everything") — flag as ambiguous.
- "ID - ID" or "?" means unidentified track. Skip with `status: "unknown"`.
- "w/ vocals from X" or "feat. Y" — keep as part of title.
- Bracketed labels like `[Drumcode]` are the **record label**, not the title — strip into a separate field if you want.

If description has no tracklist:
1. Check pinned comment.
2. Check top-rated comments (often a fan posts the tracklist).
3. As a last resort: search 1001tracklists.com via `WebSearch` for `"<channel> <video title> tracklist site:1001tracklists.com"` and `WebFetch` the page.

## Auth

API key only — no OAuth needed for public video data. Key is in the repo's `.env` as `YOUTUBE_API_KEY`. Source `.env` before running scripts:

```bash
source .env
python3 scripts/youtube_fetch.py --url "..." --api-key "$YOUTUBE_API_KEY"
```
