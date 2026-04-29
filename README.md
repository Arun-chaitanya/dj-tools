# dj-tools

A Claude Code skill that turns Claude into a DJ research assistant: extracts tracklists from YouTube DJ mixes, hunts for clean high-bitrate versions on the open web, downloads what it can, and arranges everything into a music library.

## What it does

You hand the agent a YouTube URL of a DJ set and chat with it:

- *"Get the tracklist from this mix"*
- *"Find clean 320s for tracks 3 to 7"*
- *"Track 4 — give me the candidate links, I'll grab it manually"*
- *"I downloaded those files — arrange them"*

The agent uses the YouTube Data API for metadata, web search + fetch for finding sources, and `yt-dlp` + `ffmpeg` for downloads.

## Setup

```bash
# 1. Tools (one-time)
brew install yt-dlp ffmpeg

# 2. API key
cp .env.example .env
# edit .env and paste your YouTube Data API v3 key

# 3. Make scripts executable
chmod +x .claude/skills/dj-research-agent/scripts/*.sh .claude/skills/dj-research-agent/scripts/*.py

# 4. Open in Claude Code
claude
```

The skill lives at `.claude/skills/dj-research-agent/SKILL.md`. Claude auto-loads it when you ask anything about DJ mixes / tracklists / downloading songs.

## Folders

- `.claude/skills/dj-research-agent/` — the skill itself (SKILL.md + scripts + reference docs)
- `mixes/<video-id>/` — per-mix working data (tracklist JSON, raw description, notes). Gitignored.
- `~/Desktop/DJ-Music/<mix-name>/` — final downloaded library (outside the repo)

## Honest about quality

YouTube's best audio stream is ~128–160 kbps Opus. We transcode to 320 MP3 because that's the DJ standard, but the agent records the **source** bitrate in the tracklist JSON so you always know what's a true 320 vs. a transcoded-up file. For real 320 / lossless, the agent prefers Bandcamp / artist sites / Beatport.

## YouTube Data API key

Get one free at https://console.cloud.google.com/apis/credentials → enable "YouTube Data API v3" → create an API key. Default quota of 10,000 units/day is plenty (one tracklist costs ~2 units).
