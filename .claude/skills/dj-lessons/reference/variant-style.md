# Variant Style Reference

Concrete examples of the three variant lengths for one fictional lesson. Use these as anchors when generating new lessons — same lesson, three different shapes.

The source dump for these examples:

> "For Bollywood originals you can mix instrumental to instrumental, instrumental to vocal, and vocal to instrumental, but never vocal to vocal — the two melodic lines clash. Pick the first phrase or the middle phrase, not the chorus, because the chorus is too dense. 8 bars of overlap at 130 BPM, 4 bars at 100 BPM. The slower the song, the shorter the mix, otherwise it drags."

---

## short.md (≈ 110 words)

```markdown
# Bollywood Original — Mixing Rules

- **Vocal-to-vocal: never.** Two melodic lines clash.
- **OK pairings:** instrumental→instrumental, instrumental→vocal, vocal→instrumental.
- **Pick the phrase:** first or middle. Not the chorus — too dense.
- **Mix length by BPM:**
  - 130 BPM → 8 bars
  - 100 BPM → 4 bars
- **Rule of thumb:** slower song, shorter mix. Long mixes on slow songs drag.
```

Notes on shape:
- Bullets only, no prose.
- Bold the rule, plain the reason.
- One screen on a phone.
- Skips rationale beyond a six-word reason — that's what medium is for.

---

## medium.md (≈ 380 words)

```markdown
# Bollywood Original — Mixing Rules

For mixing original Bollywood tracks (not edits or remixes), the constraint is melodic, not rhythmic — two vocal lines on top of each other clash, even if the keys are compatible.

## Allowed pairings

- Instrumental → instrumental ✓
- Instrumental → vocal ✓
- Vocal → instrumental ✓
- **Vocal → vocal ✗** — the two melody lines fight.

This is specifically a Bollywood-originals rule. For tech-house edits where the vocal is chopped into a hook, normal mixing rules apply.

## Phrase to mix on

Pick the **first phrase** (intro into the first vocal entry) or the **middle phrase** (between verse and chorus, or between chorus and bridge). Avoid mixing on the chorus — too many elements stacked, no room for a second track underneath.

## Mix length by BPM

The slower the song, the shorter the mix should be — long overlaps on slow songs drag and the energy dips.

| BPM | Bars to overlap |
|-----|-----------------|
| 130 | 8               |
| 100 | 4               |

For BPMs in between, scale linearly (≈ 6 bars at 115 BPM as a starting point, adjust by feel).

## Why this works

Vocal-to-vocal in Bollywood specifically clashes because both vocals are usually in the same melodic register and ornamentation style. Instrumental layers (strings, dholak, synths) blend more forgivingly because they sit in different frequency bands. Mixing on first/middle phrases gives the incoming track room to establish itself before its own dense section arrives.
```

Notes on shape:
- Headings break it into scannable sections.
- One short prose paragraph per section, then bullets or a table.
- Includes rationale, but keeps it tight (one paragraph, not three).
- Bar-count table is the centerpiece.

---

## long.md (unbounded, ≈ 700 words)

```markdown
# Bollywood Original — Mixing Rules

These are the rules my teacher gave me for mixing original Bollywood tracks (the actual film versions, not edits or remixes — those follow different rules because the vocal is usually chopped into a hook).

## The core constraint: vocal-to-vocal clashes

The single hard rule is: **never mix vocal to vocal**. Even when the keys are compatible (Camelot says they should blend), Bollywood vocals sit in the same melodic register and use similar ornamentation (harkat, taan, glides), so two of them on top of each other create a muddy clash that the audience hears as "wrong" even if they can't articulate why.

The allowed pairings are:

- **Instrumental → instrumental** — easiest. Strings, dholak, pads, synths layer naturally.
- **Instrumental → vocal** — bring the new track in under the outgoing instrumental, swap when the vocal enters.
- **Vocal → instrumental** — let the outgoing vocal finish its phrase, then bring the new instrumental forward.
- **Vocal → vocal** — never.

> Teacher's exact words: "Two voices is a fight. The crowd doesn't know why it sounds bad, but they feel it."

## Picking the phrase to mix on

Bollywood tracks are structured in 4- or 8-bar phrases: intro, verse 1, pre-chorus, chorus, instrumental break, verse 2, chorus, outro. Some have a bridge.

The two safe places to mix are:

1. **First phrase** — the intro into the first vocal entry. The track is still building, so a second track underneath doesn't compete.
2. **Middle phrase** — between verse and chorus, or between chorus and bridge. A natural arc point.

The place to **avoid** is the chorus itself. Choruses in Bollywood are typically the densest section: full vocal, full strings, dholak/tabla, often a counter-melody on flute or sarangi. There's no room underneath for a second track, and any mix here will sound stacked rather than blended.

## Mix length scales inversely with BPM

The slower the song, the shorter the mix should be. A long overlap on a slow song drags — the energy dips, the dance floor checks their phones.

| BPM   | Bars to overlap |
|-------|-----------------|
| 130   | 8               |
| 115   | ~6 (interpolate)|
| 100   | 4               |
| 90    | 4 (don't go shorter — needs at least one full phrase) |

The intuition: at 130 BPM, 8 bars is ~15 seconds. At 100 BPM, 4 bars is ~10 seconds. Roughly equal time, just expressed in fewer bars at the slower tempo.

## Why this works (mostly my notes)

The vocal-to-vocal rule is specifically about Bollywood because of the melodic density. In tech house or hip-hop, two vocals can co-exist if one is a sparse hook and the other is the main lyric — the registers don't compete. Bollywood doesn't have that — every vocal is "the main vocal".

The phrase-pick rule generalizes: mix on the **least dense section**, whatever that is for the genre. For Bollywood that's first/middle phrase. For tech house it's often the breakdown. For hip-hop it's the instrumental section between verses.

The BPM-bars rule is partly about energy management and partly about how long the audience tolerates "two things at once". Faster track = ear has more energy to parse layers. Slower track = ear gets tired faster of competing elements.

## Things to practice this week

- Pick three Bollywood originals at 130 BPM, find their first phrase entry points, label cue points in rekordbox.
- Same for three at 100 BPM, with 4-bar cues.
- Try one vocal-to-vocal mix deliberately, just to hear how bad it is.
```

Notes on shape:
- Includes rationale, exact teacher quotes, the user's own asides ("mostly my notes"), and a practice section.
- Headings every 2–3 paragraphs for scannability.
- BPM table is more detailed than the medium one.
- Practice section is unique to long — short and medium don't need it.
- Word count is unbounded, but don't pad. If the source dump is 80 words, long can be 400 — not 1500.

---

## How to apply these patterns

When generating a new lesson:

1. **short** = bullets only, ≤ 150 words, one rule per bullet, bold the rule.
2. **medium** = bullets + short prose, headings, one table or list as centerpiece, ≈ 300–500 words.
3. **long** = full notes with rationale, teacher quotes, the user's asides, a "practice" or "things to try" section if applicable. No upper bound, but proportional to the source dump.

When editing an existing variant:

- Preserve the variant's shape (don't add prose to short, don't strip bullets from long).
- Only change what the user asks ("drop the table" → drop only the table, leave everything else).
