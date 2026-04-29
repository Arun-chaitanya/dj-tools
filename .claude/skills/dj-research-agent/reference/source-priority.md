# Source priority — where to look and what to expect

When researching a track, work down this list. Stop as soon as you find a clearly better source than what you already have.

## Tier 1 — Best (free, lossless or true 320)

### Bandcamp
- Search: `"<artist> <title>" site:bandcamp.com`
- Quality: FLAC + 320 MP3 available on most releases.
- Cost: Often "name your price" (can be $0). Some are paid.
- Auto-download: Free releases yes (yt-dlp supports Bandcamp). Paid: hand to user.

### Artist's own site / SoundCloud "free download" link
- Many electronic artists post promo tracks via Hypeddit, ToneDen, or direct Mediafire/Dropbox.
- Search: `"<artist> <title>" "free download"`
- Quality: Usually 320 MP3.
- Auto-download: yt-dlp handles SoundCloud and direct file URLs.

## Tier 2 — Good (free, 128–256 kbps)

### SoundCloud (artist's official upload, no free DL flag)
- Search: `"<artist> <title>" site:soundcloud.com`
- Quality: 128 kbps MP3 (public stream).
- Auto-download: Yes, but flag as `source_bitrate_kbps: 128`.

### YouTube (Topic channel or official upload)
- Prefer "<Artist> - Topic" channels (auto-generated, often higher bitrate audio).
- Search: `"<artist> <title>" topic site:youtube.com`
- Quality: 128–160 kbps Opus.
- Auto-download: Yes, transcode to 320 MP3, flag as transcoded.

## Tier 3 — Paid (return link, do not download)

### Beatport
- The DJ store. 320 MP3, WAV, AIFF, FLAC.
- Cost: ~$1.49–$2.99 per track.
- Action: Return URL with note "Beatport — paid, 320/WAV available". User buys.

### Juno Download / Traxsource
- Same model as Beatport, different catalogs.
- Action: Return URL with cost note.

### Bandcamp (paid releases)
- Same as Tier 1 but if it's not free, user has to buy.

## Tier 4 — Last resort

### 1001tracklists.com
- Not a download source — a tracklist database. Useful when YouTube description has no tracklist.

### YouTube random re-upload
- Some 10-min "extended mixes" are bootlegs. Quality is whatever the uploader had. Use only if all other tiers fail and flag heavily in `notes`.

## What to put in `candidates[]` when handing off

```json
{
  "candidates": [
    {
      "url": "https://artist.bandcamp.com/track/...",
      "source": "Bandcamp",
      "expected_quality": "FLAC / 320 MP3",
      "cost": "name your price",
      "notes": "Official release, 2023"
    },
    {
      "url": "https://www.beatport.com/track/...",
      "source": "Beatport",
      "expected_quality": "320 MP3 / WAV",
      "cost": "$1.99",
      "notes": "Original Mix"
    }
  ]
}
```

Always rank Tier 1 > Tier 2 > Tier 3 > Tier 4 in the array.
