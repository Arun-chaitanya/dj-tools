# Source priority — where to look and what to expect

The right Tier 1 depends on the track's catalog. Pick the lane first, then work down within it.

---

## Lane A — Indian / regional commercial catalog
*(Bollywood Hindi-film, Tollywood/Telugu, Kollywood/Tamil, Punjabi, Bhojpuri, Marathi, etc.)*

Major-label India catalog (T-Series, YRF Music, Sony Music India, Zee Music, Saregama, Tips, Lahari) is **not on Bandcamp / SoundCloud free-DL / iTunes-with-DRM-free-MP3**. The realistic free-MP3 sources are the so-called "free download" sites. The user has authorised their use for personal DJ library building.

### Tier 1 — Free MP3 sites (claimed 320, verify with `ffprobe`)

Known-good sites, ranked by typical reliability:

1. **pagalfree.com** — usually serves a real `.mp3`, supports both 128 and 320 variants, fewer ad redirects.
2. **raag.fm** — direct `.mp3` download, decent catalog, lower ad density.
3. **mrjatt.com.se / djjohal.com** — strong for Punjabi.
4. **pagalworld.com.sb / pagalworlds.com** — large catalog but heavy ad redirects; the actual download URL is often a CDN like `pagalworldfree.com`.
5. **djmaza.info / djpunjab.is** — DJ remixes / Bollywood-house edits.
6. **bestwap.in / pagalsong.in / wapking** — fallback only.

**How to use:**
- WebFetch the candidate page and pull the direct `.mp3` URL out of the HTML (look for `<source src=...>`, `<audio src=...>`, or links with `download` attribute).
- Pass that URL to `download_audio.sh` — `yt-dlp` handles direct file URLs fine. If `yt-dlp` rejects it, fall back to `curl -L -o "<artist> - <title>.mp3" "<url>"`.
- **Always run `probe_audio.sh` after download.** Many sites mislabel re-encoded 128 kbps files as "320". Record both `claimed_bitrate_kbps` and the measured bitrate.
- **Cookie/redirect traps**: some sites use a "click here to download" interstitial that loads ads first. If `yt-dlp`/`curl` returns HTML instead of MP3 (check `file <output>` or that size > 1 MB), report failure and move on — don't try to script through ad shells.
- **Malware flags**: if Chrome / `curl` warns about the certificate or the file ext doesn't match (page promised MP3 but you got `.exe` or `.html`), abort and tell the user.

### Tier 2 — Paid, real quality

- **iTunes Store / Apple Music (purchase, not subscription)** — 256 kbps AAC, DRM-free since 2009. Search `<artist> <title> site:music.apple.com`.
- **Amazon Music (buy MP3)** — 256 kbps MP3, DRM-free. Often unavailable for India region; check before recommending.
- **JioSaavn Pro / Wynk** — streaming only, no download you can use outside the app.
- **Saregama Carvaan / saregama.com** — older catalog, sometimes sells.

Hand the link to the user. Don't try to scrape these.

### Tier 3 — YouTube transcode (last resort)

- yt-dlp the official audio (Topic channel preferred), transcode to 320 MP3.
- Source is 128–160 kbps Opus. Label as `transcoded_from_~128kbps_opus` in the JSON.
- Worse than a real Tier-1 MP3 from the free-MP3 sites — only fall back if the song isn't on those sites (rare for Bollywood, more common for very new releases or B-sides).

---

## Lane B — Electronic / indie / English-language

### Tier 1 — Free, lossless or true 320

**Bandcamp**
- Search: `"<artist> <title>" site:bandcamp.com`
- Quality: FLAC + 320 MP3 available on most releases.
- Cost: Often "name your price" (can be $0). Some are paid.
- Auto-download: Free releases yes (yt-dlp supports Bandcamp). Paid: hand to user.

**Artist's own site / SoundCloud "free download" link**
- Many electronic artists post promo tracks via Hypeddit, ToneDen, or direct Mediafire/Dropbox.
- Search: `"<artist> <title>" "free download"`
- Quality: Usually 320 MP3.
- Auto-download: yt-dlp handles SoundCloud and direct file URLs.

### Tier 2 — Free, 128–256 kbps

**SoundCloud (artist's official upload, no free DL flag)**
- Quality: 128 kbps MP3 (public stream). Flag as `source_bitrate_kbps: 128`.

**YouTube (Topic channel or official upload)**
- Quality: 128–160 kbps Opus → transcode to 320 MP3, flag as transcoded.

### Tier 3 — Paid

**Beatport** — DJ store, 320 MP3 / WAV / AIFF / FLAC. ~$1.49–$2.99.
**Juno Download / Traxsource** — same model, different catalogs.
**Bandcamp (paid releases)** — same as Tier 1 but if it's not free, user has to buy.

### Tier 4 — Last resort

- **1001tracklists.com** — not a download source, a tracklist database.
- **YouTube random re-uploads** — some "extended mixes" are bootlegs. Use only if all other tiers fail; flag heavily in `notes`.

---

## What to put in `candidates[]` when handing off

```json
{
  "candidates": [
    {
      "url": "https://pagalfree.com/download/...",
      "source": "Pagalfree",
      "expected_quality": "320 MP3 (claimed)",
      "cost": "free",
      "notes": "Direct .mp3 link. Verify measured bitrate after download."
    },
    {
      "url": "https://music.apple.com/...",
      "source": "iTunes",
      "expected_quality": "256 AAC",
      "cost": "₹15–₹25",
      "notes": "DRM-free, real measured bitrate."
    }
  ]
}
```

Always rank Tier 1 > Tier 2 > Tier 3 > Tier 4 within the chosen lane. If a track plausibly belongs to both lanes (e.g. a Bollywood × Tech House edit by a Western producer), list both lanes' best options and let the user pick.
