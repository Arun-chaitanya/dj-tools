# CLAUDE.md

This file gives Claude Code the project context for `dj-tools`.

## What this repo is

A set of Claude Code skills + a small reader app that support the user's DJ practice (the user is a hobbyist DJ learning from a teacher).

There are now two surfaces:

1. **`dj-research-agent` skill** — given a YouTube DJ mix URL, extracts the tracklist, researches each track, downloads what it can with `yt-dlp` + `ffmpeg`, and arranges files into `~/Desktop/DJ-Music/`.
2. **`dj-lessons` skill + `reader/` Next.js app** — the user dictates lesson reflections (via Spokenly) into the Claude Code chat; the skill writes structured notes in three lengths (short/medium/long) to `lessons/<slug>/`. The reader app at `reader/` renders them Kindle-style in the browser, with a variant switcher and a "Set as primary" button.

The user runs `claude` inside this repo and chats with both skills (each auto-invokes from its own description triggers). The reader app runs locally with `cd reader && pnpm dev`.

## Surfaces

- `.claude/skills/dj-research-agent/` — tracklist extraction, track research, download, library arrangement.
- `.claude/skills/dj-lessons/` — lesson capture + edit, three-variant generation, identity-aware.
- `reader/` — Next.js 15 App Router reader. Renders lessons (Kindle-style), mixes (crate catalogs), and sets (performable running orders). Read-only + one mutation (set primary variant). No AI, no DB, no auth.
- `lessons/` — gitignored, holds the user's lesson notes (`<slug>/{meta.json,short.md,medium.md,long.md}`) and `_identity.md`.
- `mixes/` — gitignored, holds per-mix tracklist working data (used by `dj-research-agent`). These are **collection-style lane catalogs** (often 100s of tracks) — source pools, not performable orderings.
- `sets/` — gitignored, holds **performable sets** (`<slug>/set.json`) — a curated ordered subset of tracks picked from `mixes/` or rekordbox, with per-track `sequence` and `comment`. This is what gets pushed to rekordbox as a playlist.

## How the dj-research-agent skill is structured

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

- **Per-mix working data**: `mixes/<mix-id>/` — gitignored. `<mix-id>` is either a YouTube video ID (when the mix came from one) or a slug like `telugu-9xm-feels-v1` (for curated lane mixes). Contains `tracklist.json` (the canonical structured tracklist — see "Tracklist schema" below), `raw-description.txt` (unparsed YouTube description if applicable), `README.md` (curation notes), and per-phase harvest JSONs for resumable work.
- **Per-set working data**: `sets/<set-id>/set.json` — gitignored. A performable running order. References tracks by rekordbox `DjmdContent.ID` (the stable handle), with denormalized title/artist/bpm/key for display and the two per-set annotations: `sequence` (playback order) and `comment` (free-form note for this set only — solves the "rekordbox comment is global" problem). See "Set schema" below.
- **Final music library**: `~/Desktop/DJ-Music/<Genre>/<Artist> - <Title>.mp3` — outside the repo entirely. Files are organised by genre (`Bollywood`, `Bollywood Tech House`, `Telugu`, `English`, `Hip Hop`, `Punjabi`, etc.), one canonical home per track, no per-mix subfolders. The user builds gig playlists in record box separately. See `SKILL.md` → "Library layout" for the full rules.
- **Lesson notes**: `lessons/<slug>/{meta.json,short.md,medium.md,long.md}` — gitignored. The reader app reads these from disk at request time; the `dj-lessons` skill writes them.
- **Identity**: `lessons/_identity.md` — gitignored. Self-description used by the lessons skill to keep the level/genres/vocabulary consistent. Edited by hand or by the skill (with user approval).
- **Reader app**: `reader/` — Next.js 15 App Router project. `reader/app/page.tsx` is the lesson list, `reader/app/lessons/[slug]/page.tsx` is the reader view. `reader/lib/lessons.ts` is the fs reader; `reader/lib/actions.ts` has the one server action (set-primary-variant).
- **Secrets**: `.env` at repo root, gitignored. Currently just `YOUTUBE_API_KEY=...`. Source it before running scripts: `source .env`. The reader app does NOT need any secrets.

## Tracklist schema

Every `mixes/<mix-id>/tracklist.json` follows this canonical shape. **All mixes use the same schema** so the reader app, the dj-research-agent skill, and any future tooling can read any mix without special-casing.

```jsonc
{
  "_comment": "Free-form provenance note. Optional but recommended.",
  "mix": {
    "mix_id": "telugu-9xm-feels-v1",       // string slug or YouTube video ID
    "title": "Telugu 9XM Feels — V1",      // human-readable
    "description": "...",                   // 1–3 sentence vibe summary
    "lane_profile": ".claude/skills/dj-research-agent/reference/vibe-telugu-9xm-feels.md",
    "created": "2026-04-30",                // ISO date (YYYY-MM-DD)
    "total_tracks": 280,
    "popularity_floor": "pre-2018 ≥ 2M views, 2018+ ≥ 10M"  // optional; only if mix applies a floor
  },
  "tracks": [
    {
      // — Identity (required) —
      "title": "Crazy Feeling",
      "artists": "Karthik, Devi Sri Prasad",  // composers + singers, comma-joined; null if unknown
      "film": "Nenu Sailaja",                  // film/album name; null for non-film
      "year": 2016,                            // integer; null if unknown

      // — YouTube canonical reference (required when downloadable) —
      "video_id": "QCTtc36u-Kk",               // 11-char YouTube ID; null if unresolved
      "youtube_url": "https://www.youtube.com/watch?v=QCTtc36u-Kk",
      "youtube_title": "Crazy Feeling Full Video Song | …",  // full YT title — useful for fuzzy match
      "youtube_channel": "Ram Pothineni",
      "view_count": 192300000,                 // raw integer (not "192.3M") — UI formats as needed

      // — Curation provenance —
      "sources": ["Happy Vibes Telugu", "Feel Good Telugu"],  // playlist names that surfaced this track
      "appears_in_playlists_count": 2,         // = len(sources); denormalized for sort
      "passes_popularity_floor": true,         // optional; present only when mix.popularity_floor is set

      // — Lane judgment (optional) —
      "phase": "p1+2",                         // freeform harvest-phase tag
      "why_in": "famous Nenu Sailaja peppy duet — lane anchor",
      "boundary": false,                       // true = flagged for user review

      // — Download state (required) —
      "status": "planned"                      // "planned" | "downloaded" | "needs_manual" | "skipped"
    }
  ]
}
```

**Naming and conventions:**

- **Field names use snake_case** (matches Python skill scripts; the reader maps to TS at the type boundary in `reader/lib/mixes.ts`).
- **`view_count` is a raw integer**, not "192.3M" or "192M". Format on render. (Old V1 mixes used `views_M` as a float — the migration multiplied by 1e6.)
- **`null` over missing keys** for optional-but-known-empty values (`artists: null`, not omit). For optional-and-not-applicable (`why_in`, `boundary`, `phase`, `passes_popularity_floor`), omit the key entirely.
- **Track order is meaningful** — there's no `index` field; the array index is the index. Sort before write if needed.
- **`status` defaults to `"planned"`** when a track is harvested but not yet downloaded. Update to `"downloaded"` after `download_audio.sh` succeeds.

**When extending the schema:** add new optional fields freely; never rename or remove existing ones without migrating all `mixes/*/tracklist.json` files. The reader's `Track` type in `reader/lib/mixes.ts` is the source of truth for the TS side — keep it in sync.

**Per-mix harvest files** (curation working data, not the canonical output): `phase1-*.json`, `phase2-*.json`, `phase3-*.json`, `spotify-merged-filtered.json`, etc. These can have any shape — they're internal to the curation run. Only `tracklist.json` is the canonical artifact that downstream tools (reader, downloader, library arranger) read.

## Set schema

Every `sets/<set-id>/set.json` follows this shape. A set is a performable running order — distinct from a `mixes/<id>/tracklist.json` collection (which is a source pool).

```jsonc
{
  "set": {
    "set_id": "telugu-9xm-30min-v1",   // slug; matches folder name
    "title": "Telugu 9XM — 30 min v1",
    "description": "...",               // optional
    "lane": "telugu-9xm",               // optional — which collection(s) it draws from
    "target_duration_min": 30,          // optional
    "created": "2026-05-27",            // ISO date (YYYY-MM-DD)
    "updated": "2026-05-27",
    "total_tracks": 16
  },
  "tracks": [
    {
      "track_id": "68643951",           // rekordbox DjmdContent.ID — stable handle
      "title": "Adhento gaani vunnapaatuga",
      "artists": "...",
      "film": null,                      // optional
      "bpm": 79.0,
      "key": "D",
      "duration_sec": 238,
      "sequence": 1,                     // playback order in the set; null = not placed
      "comment": "open with this; mix-in at hot cue C @ 32.5s"  // per-set, free-form
    }
  ]
}
```

**Why `sequence` and `comment` per-track-per-set:** rekordbox's Comment field is global on a track, so the same song in three playlists shares one comment. A set's `comment` is local to that set — you can write "drop the build at 1:20" for one set and "use long intro, no drop" for another, on the same track.

**`track_id` is the rekordbox `DjmdContent.ID`** — the stable handle that survives across library re-indexing. Title/artist/bpm/key/duration are denormalized so the reader can render without hitting `master.db`.

**Source of truth for set authorship:** the JSON file. The reader is read-only. A future `dj-research-agent` capability (or the planned `sync_set_to_rekordbox.py`) will push a finalized `set.json` into rekordbox as a playlist.

## Required external tools

- `yt-dlp` (>= 2026.03) — `brew install yt-dlp` (used by `dj-research-agent`)
- `ffmpeg` + `ffprobe` — `brew install ffmpeg` (used by `dj-research-agent`)
- `python3` — system Python 3 is fine; scripts use only stdlib
- `pnpm` — `brew install pnpm` (used by the `reader/` app)
- `node` ≥ 20 — for the reader app

If a research-agent dependency is missing, the bundled scripts exit with a clear error. The reader app's deps are managed by pnpm inside `reader/`.

## Working principles

These apply to every change you make in this repo:

1. **Skills are the primary product; the reader app is a thin viewer.** Most edits will be to a `SKILL.md` (changing how an agent behaves) or to bundled scripts. The `reader/` app is intentionally small — read-only file viewing + one mutation (set-primary-variant). It has no AI calls, no DB, no auth. Don't add new web surfaces beyond `reader/` unless asked.
2. **Scripts: stdout = JSON, stderr = errors, non-zero exit = failure.** Every script in `.claude/skills/*/scripts/` follows this contract so the agent can parse results reliably. Preserve it.
3. **Honest about audio quality.** YouTube tops out at ~128–160 kbps Opus. Free-MP3 sites (pagalfree, pagalworld, mrjatt, djmaza, raag.fm) often mislabel 128 kbps re-encodes as "320 kbps". The agent records both the page's *claimed* bitrate and the *measured* bitrate (`ffprobe` after download). Never let the agent claim a quality it didn't actually fetch.
4. **Free-MP3 sites are the realistic Tier-1 source for Indian/regional commercial catalog** (Bollywood, Telugu, Tamil, Punjabi, etc.) — major-label India catalog isn't on Bandcamp / SoundCloud free-DL. The user has authorised personal-use downloads from these sites. For electronic/indie/English catalog, the old Tier-1 (Bandcamp / SoundCloud / artist site) still applies. See `reference/source-priority.md` for the lane-based ranking.
5. **The agent never invents download URLs.** If a track can only be bought (Beatport/Juno/iTunes) or has no findable free source, the agent populates `candidates[]` in the tracklist JSON and hands off to the user. See `reference/source-priority.md`.
6. **One step at a time, agentic not scripted.** Each skill does what the user asks (extract / research / download / arrange / save lesson / edit lesson) — not the whole pipeline unless told.
7. **Lesson notes are identity-aware.** The `dj-lessons` skill always reads `lessons/_identity.md` before writing or editing. Don't write notes at a level beyond what's there (e.g., don't assume pro gigs, don't use jargon the user hasn't introduced).

## How to test changes

There's no test suite (the skills are prompts + scripts; the reader app is small enough to smoke-test by hand). To verify changes:

### Skills

1. Smoke-test research-agent scripts directly:
   ```bash
   source .env
   python3 .claude/skills/dj-research-agent/scripts/youtube_fetch.py --url "<some-mix-url>" --api-key "$YOUTUBE_API_KEY"
   ```
2. Open the repo in `claude` and try a representative prompt — `"get the tracklist from …"` for `dj-research-agent`, `"I learned today …"` for `dj-lessons`. The matching skill should auto-trigger; verify it reads from its `SKILL.md` and writes to the right folder (`mixes/<id>/` or `lessons/<slug>/`).
3. Edits to `SKILL.md` take effect in the current `claude` session immediately. New scripts or new skill folders need a session restart.

### Reader app

```bash
cd reader
pnpm install   # first time only
pnpm dev
```

Open `http://localhost:3000`. The list shows lessons sorted by `created` desc; click one to read; toggle variants; click "Set as primary" and verify the chip on the list updates after a refresh.

## Common edits

- **Change a skill's behavior** → edit `.claude/skills/<skill>/SKILL.md`. Frontmatter rules: `description` is what triggers auto-invocation; `allowed-tools` pre-approves tools.
- **Add a new capability a skill can call** → bundle a CLI script in `<skill>/scripts/` (stdout-JSON contract), then document it in `SKILL.md` under "Capabilities & how to use them" with the exact invocation syntax.
- **Add long-form reference material** → drop a markdown file in `<skill>/reference/` and link to it from `SKILL.md`. Keeps the main skill file lean (the agent reads reference docs on demand).
- **Change the canonical tracklist shape** → update the "Tracklist schema" section in this `CLAUDE.md` (the source of truth), the TS `Track` type in `reader/lib/mixes.ts`, and the example file `.claude/skills/dj-research-agent/examples/tracklist.schema.json`. **Migrate all existing `mixes/*/tracklist.json` files** in the same change — the reader assumes uniform schema across mixes.
- **Change the lesson meta shape** → update `.claude/skills/dj-lessons/SKILL.md` (the meta.json schema section) AND the TypeScript types in `reader/lib/lessons.ts`. Keep them in sync.
- **Change the reader UI** → edit files under `reader/app/` and `reader/components/`. The app reads markdown via server components — no API layer to update.

## What NOT to do

- Don't add new web surfaces beyond `reader/` unless explicitly asked. The `reader/` app is intentionally minimal (read-only file viewer + one mutation).
- Don't add AI / API calls / auth / a database to the reader app. It's a file viewer, not a generator.
- Don't add a package manager or `node_modules` to the skill folders — skills use only stdlib Python + system binaries. The reader app has its own pnpm setup at `reader/`, that's the only Node footprint in the repo.
- Don't commit `.env`, anything in `mixes/` or `lessons/`, or downloaded audio files. `.gitignore` already covers these.
- **All browser-automation artifacts go under `.playwright/`** (a single gitignored folder, matched at any depth via `**/.playwright/`). Don't create `.playwright-*` sibling folders (e.g. `.playwright-profile-foo/`, `.playwright-cli/`, `.playwright-mcp/`), and don't create them inside subdirs either (e.g. `reader/.playwright-cli/`, `mixes/<id>/.playwright-cli/`). Use subdirs of `.playwright/` instead — `.playwright/profile-telugu-1/`, `.playwright/cli/`, `.playwright/mcp/`. One gitignore rule covers everything.
- Don't write tests, CI, or documentation files (other than `CLAUDE.md` and `README.md`) unless explicitly asked.
- Don't write `primary_variant` from the skill after first creation — that's the reader app's mutation. And don't write `updated` from the reader app — that belongs to the skill (otherwise toggling primary churns the list ordering).

## Reference: skill authoring

For background on how Claude Code skills work (frontmatter fields, progressive disclosure, `${CLAUDE_SKILL_DIR}`, allowed-tools, etc.), see https://code.claude.com/docs/en/skills.md. The pattern this repo uses is "bundled CLI scripts documented in SKILL.md, agent invokes via Bash" — Anthropic's recommended pattern for skills that need custom tooling.
