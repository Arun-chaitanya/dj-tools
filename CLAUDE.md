# CLAUDE.md

This file gives Claude Code the project context for `dj-tools`.

## What this repo is

A Claude Code skill that turns Claude into a DJ research assistant for the user (a working DJ). Given a YouTube DJ mix URL, the agent extracts the tracklist, researches each track on the open web, downloads what it can with `yt-dlp` + `ffmpeg`, and arranges the files into a music library at `~/Desktop/DJ-Music/`.

There is **no app code** here — the "product" is the skill at `.claude/skills/dj-research-agent/SKILL.md` plus the bundled scripts and reference docs. The user runs `claude` inside this repo and chats with the agent.

## How the skill is structured

```
.claude/skills/dj-research-agent/
├── SKILL.md              ← agent instructions + operating principles. Read this first.
├── scripts/
│   ├── youtube_fetch.py  ← YouTube Data API v3 client (video meta + top comments)
│   ├── download_audio.sh ← yt-dlp + ffmpeg wrapper, transcodes to 320 MP3
│   └── probe_audio.sh    ← ffprobe wrapper for reading tags + bitrate
├── reference/            ← long-form docs the agent loads on demand
│   ├── youtube-api.md
│   ├── yt-dlp-formats.md
│   └── source-priority.md
└── examples/
    └── tracklist.schema.json  ← canonical shape of mixes/<id>/tracklist.json
```

The skill auto-invokes whenever the user mentions DJ mixes, tracklists, downloading songs, or arranging music. It is **not** invoked manually via slash command — `disable-model-invocation` is unset so Claude picks it up from the description match.

## Where things live

- **Per-mix working data**: `mixes/<youtube-video-id>/` — gitignored. Contains `tracklist.json` (the canonical structured tracklist), `raw-description.txt` (unparsed YouTube description, kept for re-parsing), and `notes.md` (anything that doesn't fit the schema).
- **Final music library**: `~/Desktop/DJ-Music/<sanitized-mix-title>/` — outside the repo entirely. This is the user's actual DJ library; downloaded files end up here.
- **Secrets**: `.env` at repo root, gitignored. Currently just `YOUTUBE_API_KEY=...`. Source it before running scripts: `source .env`.

## Required external tools

- `yt-dlp` (>= 2026.03) — `brew install yt-dlp`
- `ffmpeg` + `ffprobe` — `brew install ffmpeg`
- `python3` — system Python 3 is fine; scripts use only stdlib

If any are missing, the bundled scripts exit with a clear error.

## Working principles

These apply to every change you make in this repo:

1. **The skill is the product.** Most edits will be to `SKILL.md` (changing how the agent behaves) or to the bundled scripts (changing what tools the agent has). Don't add a Next.js app, web UI, or other surfaces unless explicitly asked — the chat-in-`claude` interface is intentional.
2. **Scripts: stdout = JSON, stderr = errors, non-zero exit = failure.** Every script in `scripts/` follows this contract so the agent can parse results reliably. Preserve it.
3. **Honest about audio quality.** YouTube tops out at ~128–160 kbps Opus. The downloader transcodes to 320 MP3 (DJ standard) but always records the **source** bitrate. Never let the agent (or scripts) claim a quality they didn't actually fetch.
4. **The agent never invents download URLs.** If a track can only be bought (Beatport/Juno) or has no findable source, the agent populates `candidates[]` in the tracklist JSON and hands off to the user. See `reference/source-priority.md`.
5. **One step at a time, agentic not scripted.** The agent does what the user asks (extract / research / download / arrange) — not the whole pipeline unless told.

## How to test changes to the skill

There's no test suite (the skill is a prompt + scripts). To verify changes:

1. Smoke-test scripts directly:
   ```bash
   source .env
   python3 .claude/skills/dj-research-agent/scripts/youtube_fetch.py --url "<some-mix-url>" --api-key "$YOUTUBE_API_KEY"
   ```
2. Open the repo in `claude` and try a representative prompt ("get the tracklist from …"). The skill should auto-trigger; check the agent reads from `SKILL.md` correctly and writes to `mixes/<id>/`.
3. Edits to `SKILL.md` take effect in the current `claude` session immediately. New scripts or new skill folders need a session restart.

## Common edits

- **Change agent behavior** → edit `.claude/skills/dj-research-agent/SKILL.md`. Frontmatter rules: `description` is what triggers auto-invocation; `allowed-tools` pre-approves tools (currently `Bash WebFetch WebSearch Read Write Edit`).
- **Add a new capability the agent can call** → bundle a CLI script in `scripts/` (stdout-JSON contract), then document it in `SKILL.md` under "Capabilities & how to use them" with the exact invocation syntax.
- **Add long-form reference material** → drop a markdown file in `reference/` and link to it from `SKILL.md`. Keeps the main skill file lean (the agent reads reference docs on demand).
- **Change the canonical tracklist shape** → update `examples/tracklist.schema.json` and the matching language in `SKILL.md`.

## What NOT to do

- Don't add code that lives outside `.claude/skills/dj-research-agent/` unless the user asks for a new surface (e.g., a Next.js UI). Keep this repo skill-shaped.
- Don't commit `.env`, anything in `mixes/`, or downloaded audio files. `.gitignore` already covers these.
- Don't add a package manager / `node_modules` / Python venv. The scripts use only stdlib + system binaries on purpose — no install step beyond `brew install yt-dlp ffmpeg`.
- Don't write tests, CI, or documentation files (other than this `CLAUDE.md` and `README.md`) unless explicitly asked.

## Reference: skill authoring

For background on how Claude Code skills work (frontmatter fields, progressive disclosure, `${CLAUDE_SKILL_DIR}`, allowed-tools, etc.), see https://code.claude.com/docs/en/skills.md. The pattern this repo uses is "bundled CLI scripts documented in SKILL.md, agent invokes via Bash" — Anthropic's recommended pattern for skills that need custom tooling.
