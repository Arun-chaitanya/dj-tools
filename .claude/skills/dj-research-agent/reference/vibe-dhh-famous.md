# Vibe profile — "DHH Famous" (Desi Hip Hop, broad starter)

A reusable curation profile for **Desi Hip Hop** lane mixes. The user is a hobbyist DJ; this is the v1 "famous DHH starter pack" — both club-energy anthems AND the critically-acclaimed canon, Hindi + Punjabi rap together.

Use this when the user asks for: "DHH mix", "Desi Hip Hop", "Indian rap", "Hindi rap", "Punjabi rap" (when bundled with DHH), or names anchor artists like Divine, Naezy, Seedhe Maut, KR$NA, Karan Aujla, Sidhu Moose Wala.

## The mood in one paragraph

Indian-language rap, 2015–2025. Club-energy peak-time anthems sit alongside the hip-hop-head canon. Mid-to-uptempo (~80–110 BPM rap tempo, but plenty of trap/drill at 140 half-time). The lane spans:

- **Hindi street rap** — Mumbai's Gully Gang lineage (Divine, Naezy), Delhi (Seedhe Maut, KR$NA, Prabh Deep), Kolkata (Cizzy), and the post-Gully-Boy mainstream wave.
- **Punjabi rap / hip-hop** — Sidhu Moose Wala's drill-influenced canon, Karan Aujla, AP Dhillon, Shubh, Talwiinder. (Bhangra-pop like Diljit Dosanjh's pure dance-floor stuff is a different lane — keep this one rap-leaning.)
- **Crossover / mainstream-rap** — Badshah, Raftaar, Honey Singh's rap side, Emiway Bantai's mass anthems.

This is **DJ-functional**: tracks that work in a hip-hop set, that crowds in India recognise, that you can mix in/out of with confidence.

## What's IN — track shape

- **Indian-language rap as the dominant element** — Hindi, Punjabi, occasionally Marathi/Tamil/Telugu rap. Bilingual (Hindi + English) is fine; pure-English by an Indian rapper is fine if it's the canonical track (e.g. Hanumankind's "Big Dawgs").
- **Famous / chartable / canon-established** — view-count floor applies (see below). Either club anthems (Brown Munde, Insane, 295, Mera Bhai) or critically-recognised hip-hop (Mere Gully Mein, Aafat!, 101, Class-Sikh material).
- **Modern-skewed**: 2018–2025 dominates. The genre essentially didn't exist as a mainstream commercial category before *Gully Boy* (2019) outside Bohemia + Honey Singh.
- **Both labels and indie** — Mass Appeal India, Azadi Records, Def Jam India, Times Music, plus self-released hits.

## What's OUT — and why

- **Pure Bhangra / Bhangra-pop** that isn't rap-leaning — Diljit's wedding-dance hits, AP Dhillon's slow-ballad side ("With You", "Insane" is borderline-fine because of the trap drums). The line: is the lead element a rapper rapping, or a singer singing over a beat? Rapper → in. Singer → out.
- **Bollywood film rap** unless it's canonical-DHH — Honey Singh film tracks are mostly out (Lungi Dance, Saturday Saturday). Exception: Apna Time Aayega (Gully Boy), Mere Gully Mein, Asli Hip Hop — those are DHH that *appeared* in film, not Bollywood-rap.
- **Devotional rap, kids' rap, novelty** — out.
- **Ultra-underground / sub-100k-views** — the popularity floor exists for a reason. If a track that *should* be in (e.g. an iconic Naezy verse) is below the floor, flag with `boundary: true` and let the user decide.

## Anchor artists (the harvest spine)

The artists below are the curation anchors. Each gets `youtube_search_topn.py --queries "<artist>" --top-n 25 --order viewCount` to surface their most-viewed catalog, then we filter for in-lane.

**Hindi rap — canonical**:
- **Divine** (Gully Gang, Mumbai) — Mere Gully Mein, Farak, Kohinoor, Punya Paap, Mirchi
- **Naezy** (Mumbai) — Aafat!, Asli Hip Hop, Tujhe Pata Hai
- **Seedhe Maut** (Delhi, duo) — 101, Nanchaku, Class-Sikh, Khatta Flow
- **KR$NA** (Delhi) — Vyanjan, Nuk, Still Here, No Cap
- **Prabh Deep** (Delhi/Punjabi-Hindi) — Class-Sikh, Suno
- **Talhah Yunus** (Pakistani-Punjabi) — Hor Nai, Pasoori-adjacent stuff
- **Hanumankind** (Bengaluru/English-rap) — Big Dawgs, Run It Up
- **Talha Anjum + Talhah Yunus** (Young Stunners) — Pakistani; included for crossover canon

**Hindi rap — mainstream / crossover**:
- **Raftaar** — Naachne ka Shaunq, Mantoiyat, Damn
- **Badshah** — Genda Phool, Paani Paani, Jugnu (the rap-leaning ones; skip his pop-only)
- **Emiway Bantai** — Machayenge, Firse Machayenge, Khatam, Bantai
- **MC Stan** (Pune) — Ek Din Pyaar, Tadipaar, Astaghfirullah, Insaan
- **Yo Yo Honey Singh** — Brown Rang, Blue Eyes, the original-canon side

**Punjabi rap / hip-hop**:
- **Sidhu Moose Wala** — 295, So High, Same Beef, The Last Ride, Legend
- **Karan Aujla** — Tauba Tauba (with Diljit), Players, Don't Look, Try Me, Softly
- **AP Dhillon** — Brown Munde, Excuses, With You, Insane
- **Shubh** — Cheques, We Rollin, Elevated, Baller
- **Talwiinder** — Naina, Maharani (his rap-adjacent side)

**Hindi underground / next-wave** (smaller view counts but canon):
- **Tienas**, **Kr$na's collabs**, **Yashraj** (Lord Gaya / Ganpat), **Ikka** (Same Beef etc.), **Rashmeet Kaur + producers**

## Era weighting

- **2022–2025**: ~40% — the post-Gully-Boy mainstream wave, MC Stan's Bigg Boss-era takeover, Karan Aujla's peak, Hanumankind, Seedhe Maut's recent material.
- **2019–2021**: ~35% — Gully Boy soundtrack, Sidhu's run, Emiway-Raftaar beef era, AP Dhillon's Brown Munde moment.
- **2015–2018**: ~20% — Naezy/Divine pre-Gully-Boy, KR$NA's earlier work, Bohemia legacy.
- **Pre-2015**: ~5% — Honey Singh's original canon, Bohemia, very early Brodha V.

## Popularity floor

Default for v1: **2018+ tracks ≥ 20M views**, **pre-2018 ≥ 5M views**.

The floor reflects that DHH is a YouTube-native genre — view counts are the honest popularity signal here (more so than Spotify, since most of the audience consumes via YT). Apply the floor at merge time; record `passes_popularity_floor` per track.

If a canonical track misses the floor (e.g. Naezy's "Aafat!" original cut), include with `boundary: true` and a `why_in` note.

## Anchor tracks (the "if you only had 25" core)

The genre-defining picks — what every DHH starter playlist must contain:

1. **Mere Gully Mein** — Divine ft. Naezy (2015) — the lane's origin point
2. **Apna Time Aayega** — Ranveer Singh / Divine (2019, Gully Boy) — anthem
3. **Asli Hip Hop** — Ranveer / Divine (2019, Gully Boy)
4. **Aafat!** — Naezy (2014) — the freestyle that started it all
5. **Kohinoor** — Divine (2018)
6. **101** — Seedhe Maut + Sez on the Beat (2019)
7. **Nanchaku** — Seedhe Maut + KR$NA (2022)
8. **Class-Sikh Maut Vol. II** — Seedhe Maut (2022)
9. **Vyanjan** — KR$NA (2024)
10. **Machayenge** — Emiway (2018) — peak-time anthem
11. **Firse Machayenge** — Emiway + Memax (2022)
12. **Tadipaar** — MC Stan (2020)
13. **Ek Din Pyaar** — MC Stan (2021)
14. **295** — Sidhu Moose Wala (2021) — anthem
15. **So High** — Sidhu Moose Wala (2017)
16. **The Last Ride** — Sidhu Moose Wala (2022)
17. **Brown Munde** — AP Dhillon (2020) — biggest-DHH-track-of-its-era
18. **Excuses** — AP Dhillon (2020)
19. **Tauba Tauba** — Karan Aujla / Diljit (2024)
20. **Players** — Karan Aujla (2023)
21. **Cheques** — Shubh (2022)
22. **We Rollin** — Shubh (2021)
23. **Big Dawgs** — Hanumankind (2024)
24. **Genda Phool** — Badshah (2020)
25. **Brown Rang** — Honey Singh (2012) — original canon

## Sources to harvest

In priority order:

1. **Anchor-artist top-N via Data API** (`youtube_search_topn.py --queries "<artist>" --order viewCount`). Cheapest, highest signal.
2. **YouTube DHH-mix descriptions** — search "DHH mix", "Desi Hip Hop best of", "Indian rap mix", "Hindi rap mix" via Data API; pull descriptions of the top mixes for tracklists.
3. **Label channels via Playwright** — Mass Appeal India (`@MassAppealIndia`), Azadi Records (`@AzadiRecordsHQ`), Def Jam India, Times Music; "most popular" tab.
4. **Spotify editorial via Playwright** — "Most Necessary", "Hot Hits Hindi", "Desi Hip Hop", "Hip Hop Hindi" — for cross-validation against YouTube view-count signal.

## Notes on file disposition

- Genre folder for downloads: `~/Desktop/DJ-Music/DHH/`
- One canonical home per track, even if it appears across multiple sub-styles. Don't split into `DHH-Hindi/` vs `DHH-Punjabi/` — the genre is one bucket.
