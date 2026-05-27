# yt-dlp + ffmpeg — what you actually get

## Format selection used by `download_audio.sh`

```
-f 'bestaudio/best'
```

This picks the highest-bitrate audio-only stream available. If no audio-only stream exists, it falls back to the best combined stream.

## Realistic source bitrates

| Source | Container | Codec | Typical bitrate | Notes |
|---|---|---|---|---|
| YouTube (most videos) | webm | Opus | 128–160 kbps | Highest tier `bestaudio` picks |
| YouTube (older/some) | m4a | AAC | 128 kbps | Fallback codec |
| YouTube Music premium | webm | Opus | up to 256 kbps | Requires auth, not used here |
| SoundCloud (Go+ tier) | mp3 | MP3 | 256 kbps | Auth required; we get the public stream |
| SoundCloud (public) | mp3/opus | MP3 or Opus | 128 kbps | What yt-dlp gets without auth |
| Bandcamp (free DL) | mp3/flac | MP3 or FLAC | 320 / lossless | Best quality available legally |
| Mixcloud | m4a | AAC | 64–128 kbps | DJ mixes only, low quality |

**Honest labeling rule:** the script reports `source_bitrate_kbps`. Always store this in `tracklist.json` alongside `transcoded_to_kbps: 320`. If `source_bitrate_kbps < 320`, the file is **transcoded-up** — bigger file, same audible quality as the source.

## Why we transcode to 320 MP3 anyway

DJ software (Serato, Rekordbox, Traktor) prefers consistent containers + bitrates. 320 MP3 is the de facto DJ standard. Transcoding doesn't *improve* the source, but it normalizes the library.

## Common yt-dlp failures

- `HTTP 403 Forbidden` — usually rate-limit or geo-block. Try again later, or pass `--cookies-from-browser chrome`.
- `Unsupported URL` — yt-dlp doesn't have an extractor for that site. Hand off to the user.
- `Sign in to confirm your age` — restricted video. Pass `--cookies-from-browser` if the user is signed in.
- `Video unavailable` — deleted or region-locked.

## Useful manual commands

List available formats without downloading:
```bash
yt-dlp -F "<URL>"
```

Download with browser cookies (for restricted content):
```bash
yt-dlp --cookies-from-browser chrome -f bestaudio "<URL>"
```

## "Most replayed" heatmap (used by `youtube_heatmap.py`)

yt-dlp returns a `heatmap` field in `--dump-single-json` output when YouTube exposes the "most replayed" graph for a video. Probe it directly:

```bash
yt-dlp --dump-single-json --skip-download --no-warnings "<URL>" \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('heatmap'))"
```

**Shape:** list of 100 buckets, each `{start_time, end_time, value}` where `value` is in [0, 1] (1.0 = most replayed point in the video). Buckets divide the full video duration into 100 equal slices.

**Absent heatmap:** `heatmap` is `None`/missing for some videos — typically low view count, age-restricted, or recently uploaded. This is not an error; treat as "no signal available". `youtube_heatmap.py` reports `has_heatmap: false` and exits 0.

**Peak derivation (in `youtube_heatmap.py`):**

- Threshold = `mean + 1 stddev` of all 100 values.
- Buckets at or above threshold form regions; single-bucket gaps are bridged (so a brief dip in the middle of a chorus doesn't split the peak).
- Each region returns `{start_sec, end_sec, intensity_avg, intensity_max, duration_sec, rank}`. Ranked by avg intensity.
- A typical 3–4 min song yields 1–3 peaks. The top peak is usually the chorus / hook.

**Why heatmap over view-count alone:** view count tells you a song is popular; the heatmap tells you *which seconds within that song* listeners rewind to. That's the "famous part" — exactly what we want when picking the anchor region of a track for a DJ set.
