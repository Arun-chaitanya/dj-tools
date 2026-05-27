# Rekordbox internals — what we've learned

A working reference for any agent that needs to read or reason about a rekordbox library on this machine. Everything below is split into:

- **CONFIRMED** — verified by direct inspection of files in `~/Library/Pioneer/rekordbox/` and the XML export at `rekordbox-export.xml` on `2026-05-09` against a live rekordbox 7.2.14 install (880 tracks, 5 playlists, 27 cued tracks).
- **REFERENCE** — drawn from public reverse-engineering (Deep Symmetry's `dysentery`/`crate-digger`, the `pyrekordbox` project, Pioneer's own published XML interop spec). Treat as guidance, not ground truth — verify before relying on field-level details.

If you find something that contradicts what's here, update this file in the same change.

---

## 1. On-disk layout (CONFIRMED)

Rekordbox 6/7 stores its library under a single user folder:

```
~/Library/Pioneer/rekordbox/
├── master.db                  ← SQLCipher-encrypted SQLite. Live library. The truth.
├── master.db-shm              ← SQLite shared-memory file (live)
├── master.db-wal              ← Write-ahead log (live; can be MBs of pending writes)
├── master.backup.db           ← Periodic backups (plaintext SQLite? — not verified)
├── master.backup2.db
├── master.backup3.db
├── networkAnalyze6.db         ← Plaintext SQLite, single table `manage_tbl` — sync state
├── networkRecommend.db        ← Plaintext SQLite, single table `manage_tbl` — sync state
├── product.db                 ← Encrypted (data magic, not SQLite)
├── ExtData.edb / .backup.edb  ← Small (~3KB) — purpose unknown
├── datafile.edb / .backup.edb ← Small (~3KB) — purpose unknown
├── automixPlaylist6.xml       ← Tiny — auto-mix playlist state
├── masterPlaylists6.xml       ← Top-level playlist tree manifest (tiny, plaintext)
├── PIONEER/                   ← Empty in our install
└── share/PIONEER/
    ├── Artwork/               ← Album art cache
    └── USBANLZ/<3-hex>/<rest>/
        ├── ANLZ0000.DAT       ← Legacy analysis (CDJ-2000 era)
        ├── ANLZ0000.EXT       ← Extended analysis (CDJ-2000NXS2 era)
        ├── ANLZ0000.2EX       ← Newer-CDJ analysis (CDJ-3000)
        └── ANLZ0000.3EX       ← MessagePack — AI/embedding data (newest)
```

**Live vs. encrypted vs. inert:**

| File / folder | State | Decryptable? | Read it? |
|---|---|---|---|
| `master.db` | Encrypted SQLCipher | Yes (well-known key, used by `pyrekordbox`) | Possible read-only on a *copy*; never touch the live file |
| `master.backup*.db` | Probably encrypted | Same key | Same caveat |
| `product.db` | Encrypted, format unclear | Not used by tools we've seen | Skip |
| `network*.db` | Plaintext SQLite | n/a | Empty/uninteresting (single `manage_tbl` table) |
| `*.edb` | Tiny binary | Unknown | Skip |
| `share/PIONEER/USBANLZ/**` | Binary, format public | n/a | Yes — but see §5: cues may not be there |
| `*.xml` (root-level) | Plaintext | n/a | Read freely |

**Rule of thumb:** if you need ground truth about cues, BPM, playlists *as the user sees them right now*, the source is `master.db`. The XML export and the ANLZ files are derived/cached views. See §5 for a critical caveat about ANLZ.

---

## 2. The XML export — primary read surface (CONFIRMED)

Triggered from rekordbox: **File menu → Export Collection in xml format**. The output path is configured in **Preferences → Advanced → Database → rekordbox xml → Imported Library** (Browse to set; default is `~/Library/rekordbox/rekordbox.xml`).

This is the **safe** way to read a library — no encryption, no live-DB risk. Loses some internal IDs and sync metadata but keeps everything we need for cue analysis, playlist structure, and audio metadata.

### Top-level shape

```xml
<?xml version="1.0" encoding="UTF-8"?>
<DJ_PLAYLISTS Version="1.0.0">
  <PRODUCT Name="rekordbox" Version="7.2.14" Company="AlphaTheta"/>
  <COLLECTION Entries="880">
    <TRACK ...>
      <TEMPO .../>            ← beat grid markers (see §2.2)
      <POSITION_MARK .../>    ← cues / loops / memory cues (see §2.3)
    </TRACK>
    ...
  </COLLECTION>
  <PLAYLISTS>
    <NODE Type="0" Name="ROOT" Count="N">     ← root folder
      <NODE Type="1" Name="..." Entries="N">  ← leaf playlist
        <TRACK Key="<TrackID>"/>              ← playlist members reference COLLECTION tracks
      </NODE>
    </NODE>
  </PLAYLISTS>
</DJ_PLAYLISTS>
```

The root attribute `Version="1.0.0"` has been stable for years. `PRODUCT.Company` flipped from `Pioneer DJ` to `AlphaTheta` after the 2024 corporate rename — both string values appear in the wild.

`COLLECTION.Entries` matches the actual count of `<TRACK>` children. Tracks appear *twice* in the XML structurally — once inside `<COLLECTION>` (full attributes) and once inside each `<NODE Type="1">` they're a member of (only the `Key` reference) — so a naive `grep -c '<TRACK '` overcounts.

### 2.1 `<TRACK>` attributes (CONFIRMED — full set)

All 25 attributes seen in our export:

| Attribute | Type | Notes |
|---|---|---|
| `TrackID` | int (string-encoded) | Stable internal ID. Use as primary key. Random-looking 8-9 digits. |
| `Name` | string | Track title |
| `Artist` | string | Comma-joined when multiple |
| `Composer` | string | Often non-empty for film music |
| `Album` | string | Film/album name for film music |
| `Grouping` | string | Free-form tag — almost always empty in our library |
| `Genre` | string | Free-form. *Note:* in our library this sometimes contains film-name-y values, not actual genres — user hasn't standardised it |
| `Kind` | string | `"MP3 File"`, `"WAV File"`, etc. |
| `Size` | int | bytes |
| `TotalTime` | int | **seconds** (not ms) |
| `DiscNumber` | int | almost always `0` |
| `TrackNumber` | int | almost always `0` |
| `Year` | int | `0` if unknown |
| `AverageBpm` | float | 2dp string e.g. `"90.00"`. **Average** — true BPM may vary; see `<TEMPO>` for grid |
| `DateAdded` | string | ISO `YYYY-MM-DD` |
| `BitRate` | int | kbps |
| `SampleRate` | int | Hz, e.g. `44100` |
| `Comments` | string | **User's free-form field — see §6** |
| `PlayCount` | int | rekordbox-tracked play counter |
| `Rating` | int | 0–5 stars × 51 (so values are 0, 51, 102, 153, 204, 255). Empty/0 in our library. |
| `Location` | URI | `file://localhost/<percent-encoded-path>`. Decode with `urllib.parse.unquote` after stripping `file://localhost`. |
| `Remixer` | string | usually empty |
| `Tonality` | string | **Key**, e.g. `D`, `Dm`, `Eb`, `F#m`. Lowercase `m` = minor. **Not Camelot** — it's musical key notation. |
| `Label` | string | Record label. In our library sometimes contains the *download source* e.g. `"Pagalfree"` — manually entered |
| `Mix` | string | Remix descriptor. Usually empty. |

**No `Energy` field** despite some reverse-engineering blogs mentioning it — rekordbox 7.2.x XML does not export an energy column.

### 2.2 `<TEMPO>` — beat grid markers (CONFIRMED)

Each tempo entry marks **one beat** on the grid. A track with stable BPM usually has just one entry (the first beat); a track with tempo changes has many.

```xml
<TEMPO Inizio="0.638" Bpm="90.00" Metro="4/4" Battito="1"/>
```

| Attribute | Meaning |
|---|---|
| `Inizio` | Position in **seconds** (float, 3dp) |
| `Bpm` | Tempo at this point (float, 2dp) |
| `Metro` | Time signature, almost always `"4/4"` |
| `Battito` | Beat number within the bar — **1, 2, 3, or 4** for 4/4. The downbeat is `1`. |

**Computing bar/phrase position from a time `t` (seconds), assuming constant BPM:**
```
first = TEMPO[0]
beats_from_first = (t - first.Inizio) * (first.Bpm / 60)
bar_index_1based  = int(beats_from_first // 4) + 1
beat_in_bar_1based = (beats_from_first % 4) + 1.0
phrase_16bar       = (bar_index_1based - 1) // 16 + 1
bar_in_phrase      = (bar_index_1based - 1) % 16 + 1
```

For tracks with multiple `<TEMPO>` entries (BPM changes), you have to walk segments piecewise — we haven't implemented this yet because none of the user's cued tracks have it.

**Caveat:** the user's library has some `Inizio` values like `0.025` (Demo Track 1) or `0.114` — that's the rekordbox auto-detected first downbeat, not the absolute file start. Always compute relative to `first.Inizio`, not zero.

### 2.3 `<POSITION_MARK>` — cues, loops, memory cues (CONFIRMED)

```xml
<POSITION_MARK Name="" Type="0" Start="16.638" Num="1" Red="69" Green="172" Blue="219"/>
```

| Attribute | Meaning |
|---|---|
| `Name` | User-entered cue name. **Always empty in our library** — feature is supported but unused. |
| `Type` | See table below. |
| `Start` | Position in **seconds** (float, 3dp). |
| `End` | (loops only) End position in seconds. Absent on non-loops. |
| `Num` | Pad slot. **`-1` = memory cue** (no pad assignment). **`0..15` = hot-cue / loop pads A..P**. |
| `Red`, `Green`, `Blue` | Cue colour, integers 0–255. May be absent on default-coloured cues (we always see them present). |

**Type codes (CONFIRMED for 0 and 4; REFERENCE for 1/2/3):**

| Type | Meaning | Has `End`? | In our library |
|---|---|---|---|
| `"0"` | Hot cue (or memory cue if `Num=-1`) | No | 93 instances |
| `"1"` | Fade-in marker | REFERENCE | 0 |
| `"2"` | Fade-out marker | REFERENCE | 0 |
| `"3"` | Load marker | REFERENCE | 0 |
| `"4"` | Loop | **Yes** | 1 instance |

**Pad numbering (CONFIRMED for 0–7; REFERENCE for 8–15):**

| `Num` | Pad | Page |
|---|---|---|
| 0 | A | 1 |
| 1 | B | 1 |
| 2 | C | 1 |
| 3 | D | 1 |
| 4 | E | 1 |
| 5 | F | 1 |
| 6 | G | 1 |
| 7 | H | 1 |
| 8 | I | 2 (REFERENCE — not exercised in our library) |
| ... | ... | ... |
| 15 | P | 2 |
| **-1** | **memory cue** (no pad) | n/a |

**Loops** occupy a hot-cue pad — they're a `Type=4` mark with both `Start` and `End`, and a `Num` in 0–15. Pressing the pad jumps to `Start` and triggers a loop to `End`. The user has exactly one loop in the library: *Kurchi Madathapetti* on slot A (`Num=0`), 88.799s → 100.434s, ~11.6 seconds ≈ 16 beats at 115 BPM.

### 2.4 `<PLAYLISTS>` — tree of folders and leaf playlists (CONFIRMED)

The structure is recursive `<NODE>` elements. Two node types:

| `Type` | Meaning | Attributes |
|---|---|---|
| `"0"` | **Folder** (contains other NODEs) | `Name`, `Type="0"`, `Count` |
| `"1"` | **Leaf playlist** (contains track refs) | `Name`, `Type="1"`, `KeyType`, `Entries` |

`Count` on folders = number of immediate child NODEs. `Entries` on leaves = number of tracks. `KeyType="0"` means children's `<TRACK Key="...">` references use `TrackID` (the only mode we've seen).

Inside a leaf, members are listed in playlist order:
```xml
<NODE Type="1" Name="Bollywood" KeyType="0" Entries="26">
  <TRACK Key="140962206"/>
  <TRACK Key="..."/>
</NODE>
```

These `<TRACK>` elements inside a NODE are *references*, not full track records — they have only the `Key` attribute. Look up the full record in `<COLLECTION>` by matching `TrackID == Key`.

**Top-level folder is always `<NODE Type="0" Name="ROOT" Count="N">`** even when there's no user-created folder structure. Our library has 5 leaf playlists at root level: `DHH` (467), `30th April Homework` (0), `CUE Analysis Playlist` (25), `Bollywood` (26), `Telugu` (274).

---

## 3. `master.db` — SQLCipher-encrypted (REFERENCE)

We have not opened this file directly in this session. What's known publicly:

- Encrypted with **SQLCipher** (AES-256-CBC, 64000 PBKDF2 iterations, SHA1 HMAC).
- The encryption key is **derived from a hardcoded value in the rekordbox binary** — same on every install. The community project `pyrekordbox` knows how to extract and use it.
- Once decrypted, it's a normal SQLite database with tables like `djmdContent` (tracks), `djmdCue` (hot cues), `djmdHotCueBanklist`, `djmdPlaylist`, `djmdSongPlaylist`, `djmdAlbum`, `djmdArtist`, etc.
- **It contains everything the XML export contains, plus things the XML drops**: cloud sync state, beat-grid analysis status, internal artwork references, lock state, the full hot-cue colour palette, "my tag" (mood/scene) data, and (on rekordbox 7+) AI track-recommendation embeddings.

When we eventually open it (with the user's permission), the workflow is:

1. **Quit rekordbox.** A live `master.db-wal` means there are uncommitted writes.
2. **Copy `master.db` to a working location.** Never operate on the live file.
3. Use `pyrekordbox` (Python venv) or another SQLCipher-capable tool to open the copy read-only.
4. If we want to write back, the safer path is: use the rekordbox XML *import* feature, not direct writes — Pioneer treats the encrypted DB as private and can change schema between point releases.

For this repo's planned cueing module the read-only workflow is enough; we don't need to write to `master.db`.

---

## 4. ANLZ binary files (CONFIRMED structure, NOT used as a cue source)

Each track in the collection has a corresponding folder under `share/PIONEER/USBANLZ/` named `<3-hex-prefix>/<UUID-tail>` — when concatenated they form a standard 32-char hex UUID, e.g. `aa276fdd-80a2-4a6f-bf9c-838fa12b3ded`. The 3-char prefix is just sharding (≤4096 buckets to avoid one giant directory).

Inside each folder are up to four files:

| File | Purpose | Format |
|---|---|---|
| `ANLZ0000.DAT` | Legacy analysis for older CDJs (CDJ-2000) | Tag-based binary, big-endian |
| `ANLZ0000.EXT` | Extended analysis (CDJ-2000NXS2, XDJ-1000MK2) | Tag-based binary |
| `ANLZ0000.2EX` | Newest-CDJ analysis (CDJ-3000 era) | Tag-based binary |
| `ANLZ0000.3EX` | AI/embedding data | **MessagePack** (different format!) |

### 4.1 ANLZ binary container format (CONFIRMED for `.DAT`/`.EXT`/`.2EX`)

All three start with a 28-byte file header tag `PMAI`, then a sequence of tagged sections. Every section starts with:

```
offset  size  field
0       4     tag (4-char ASCII, always starts with 'P')
4       4     header_len   (uint32 BE — bytes from tag start to body start)
8       4     body_len     (uint32 BE — bytes from tag start to next section)
12      ...   tag-specific header fields
header_len   body bytes
```

**Tags found in our 5 sample files (CONFIRMED present in every track):**

| Tag | File | Meaning |
|---|---|---|
| `PMAI` | DAT, EXT, 2EX | File header (always first) |
| `PPTH` | DAT, EXT, 2EX | Path to source audio file (UTF-16-BE; see §4.2) |
| `PVBR` | DAT only | Variable bit rate / bitrate-by-frame info |
| `PQTZ` | DAT | Beat grid (Quantized Tempo) |
| `PWAV` | DAT | Low-resolution waveform preview |
| `PWV2` | DAT | Tiny-resolution waveform preview |
| `PCOB` | DAT, EXT | Cue list — **but see §5: empty in our library** |
| `PWV3` | EXT | Detailed waveform |
| `PWV4` / `PWV5` | EXT | Colour waveform tiers |
| `PCO2` | EXT | Extended cue list (with names, expanded colours) — **also empty in our library** |
| `PQT2` | EXT | Extended beat grid |
| `PWV6` / `PWV7` / `PWVC` | 2EX | CDJ-3000 colour waveform tiers |

The remaining unique tags seen (`PFHF`, `PMOY`, `PTQG`, `PPGG`, `PEHK`, `PX4Q`, `PYTZ`, `PV0V`, `PDJQ`, `PQQP`, `PFER`, `PPQM`, `P2WV`, `P3L0`, `PVV2`, `PONO`, `P730`, `PKMN`, `P7P7`, `P7H6`, `P787`, `PW46`, `P7L3`, `PWTW`, `PVTV`, `P68V`, `P13L`, `P90J`, `P3KK`, plus dozens more under `.2EX`) appear in some tracks and not others. They're **not documented in any public source we trust**. Many appear once across our sample. Treat them as opaque unless we hit a specific need.

### 4.2 PPTH path encoding (CONFIRMED)

```
4   tag        "PPTH"
4   header_len 0x00000010 (16)
4   body_len   variable
4   path_len   bytes of UTF-16-BE path data
N   path       UTF-16-BE, big-endian
```

The path is stored as **`?/<filename>`** — just the filename, prefixed with the literal 2-byte sequence `?/`. The `?` is a placeholder for the volume/drive root that rekordbox resolves at use-time. **It does NOT include the directory path.** This matters for tooling: you can't reliably reverse-map an ANLZ folder to a track by full path; you have to match by filename.

We confirmed this by matching all 27 cued tracks' filenames to their ANLZ folders — 27/27 success.

### 4.3 PCOB / PCO2 cue chunk layout (REFERENCE)

For the cue tags `PCOB` (DAT) and `PCO2` (EXT), the header continues:

```
12   2    cue_list_type  (0 = hot cues + memory cues)
14   2    unused / padding
16   4    count          (number of cue entries)
20   ...  cue entries (fixed size for PCOB; variable for PCO2 because of optional name string)
```

PCOB cue entry size is reported as `0x38` bytes by Deep Symmetry; PCO2 entries are variable-length and contain a UTF-16 name. We have not parsed individual cue entries because **count was zero in every cued track we checked** — see §5.

---

## 5. Critical finding: ANLZ does NOT contain hot cues for the live library (CONFIRMED)

This is the most important thing in this document for a future agent.

We checked all **27 cued tracks** (those with at least one `POSITION_MARK` in the XML) and read their `PCOB` (DAT) and `PCO2` (EXT) cue chunks. **In every single track, `count == 0`** — zero cues stored on disk in ANLZ — even when the XML clearly shows 1–8 hot cues for that track.

**Conclusion:** ANLZ files are **export-time scratch files**. They get populated when the user actually exports a playlist to a USB stick (rekordbox writes the cues into ANLZ in the format the CDJs expect). Until then, the cue data lives only in `master.db`. Beat grid and waveform DO get written into ANLZ during normal track analysis (so `PQTZ`, `PWAV`, `PWV3` etc. are useful), but **cue data is not**.

**If you need to read the user's hot cues:**
- ✅ Use the XML export (after asking the user to re-export).
- ✅ Use `master.db` via `pyrekordbox` on a copy.
- ❌ Do not read ANLZ — you'll see all-zero counts and miss every cue.

**If you need to read beat grid or waveforms:**
- ✅ ANLZ is fine — `PQTZ` (beat grid) and `PWAV`/`PWV3` (waveforms) are populated.
- ✅ XML covers beat grid via `<TEMPO>` too, but at lower fidelity (one entry per BPM change, not per beat).

---

## 6. The `Comments` field — user's sequencing system (CONFIRMED)

The user uses the `Comments` column for **sort/serial numbers**, not free-text notes. Observed values in our library:

```
"01", "02", "03", "05", "06", "07", "08", "08.5", "10", "11", "12", "14", "15", "16",
"17", "18", "19", "20", "21", "22", "24", "904"
```

Plus a few different-style entries:
```
"4-Floor / Breaks Kit (A-1)"   ← appears on Pioneer-bundled sample tracks; presumably auto-tagged
"Tracks by www.loopmasters.com"
```

The float-style `"08.5"` shows insertion-between-integers — the user is treating this as a **sortable position marker** for ordering tracks within a setlist or practice rotation. The presence of `"904"` (much higher than other values) suggests an outlier, possibly a "deprioritise" tag or just a typo.

The `reader/` app in this repo currently surfaces this column under the heading **"comment"** (one of the 6 columns shown — along with album/title/musician/BPM/keys/serial number). When operating on the user's library, treat `Comments` as a numeric-ish ordering key, not as descriptive text.

---

## 7. The user's cueing conventions (CONFIRMED from this library)

For the planned cueing module, these are the user's actual habits as of 2026-05-09:

- **Almost exclusively uses pads A–D** (page 1, slots 0–3): A=24, B=21, C=22, D=21 cues across 27 tracks. E=1, F=1, G=1, H=2, I–P=0.
- **Each pad has a fixed colour**:
  - **A** = pink/red `#FF376F` (255, 55, 111)
  - **B** = cyan `#45ACDB` (69, 172, 219)
  - **C** = green `#7DC13D` (125, 193, 61)
  - **D** = purple `#AA72FF` (170, 114, 255)
- **Cue placement is mix-action centric, not song-structure centric.** A and B mark the **intro / mix-IN points** (median A at 2.9% of track, B at 10.2%). C and D mark the **vocal-end / mix-OUT points** for the track (median C at 30.1%, D at 34.8%). This is specific to **Indian original songs** (Bollywood, Telugu) where the mixing rule is: don't overlap two vocals, fade out under instrumentation as the leaving track's vocal phrase ends. **"Outro" in the user's vocabulary means "vocal-ending point I mix out from", NOT the literal end of the track.** See `~/.claude/.../memory/feedback_dj_cueing_vocabulary.md`.
- **Phrase-boundary discipline**: Bar-in-phrase histogram peaks at bar 1 (14 hits — phrase boundary), bar 9 (11 hits — mid-phrase 8-bar mark), bar 13 (8 hits — pre-drop build). Plus a noisy cluster at bars 4/6/8 where the actual musical event (vocal entry, drop) doesn't sit cleanly on the grid.
- **Cue names are not used.** Every `POSITION_MARK.Name` is empty.
- **Memory cues are not used** (Num=-1 entries: 0 in our library).
- **Loops are barely used** — exactly one (Kurchi Madathapetti, ~12 sec).
- **Pad page 2 (I–P) is unused** — 8 slots of unused canvas for any future "second page = reference / actions" convention.

---

## 8. Practical guidance for tools in this repo

### Reading the library

Use the XML export. Path can be either `./rekordbox-export.xml` (preferred, user puts it there explicitly) or `~/Library/rekordbox/rekordbox.xml` (rekordbox default). The inspection script at `dj-cueing/inspect_rekordbox.py` reads the former by default.

**Pin Python to `/usr/bin/python3`** in scripts that parse the XML — Homebrew Python 3.14 on this machine has broken `pyexpat` bindings (`Symbol not found: _XML_SetAllocTrackerActivationThreshold`).

### XML re-export workflow

The XML is **not auto-updated**. Each time the user wants their tooling to see fresh cues/playlists, they must:
1. Open rekordbox.
2. **File menu → Export Collection in xml format**.
3. The file is overwritten at the path configured in *Preferences → Advanced → Database → rekordbox xml → Imported Library*.

So any agent that operates on `rekordbox-export.xml` should be explicit that it's working off a snapshot, and prompt the user to re-export when it matters.

### Mutating cues / playlists

**We don't.** Not in the current scope. If we ever do, the path is:
1. Build a new XML with the desired changes.
2. Rekordbox can **import** XML via *File → Import Playlist → XML* (this creates new playlists; it does NOT overwrite hot cues on existing tracks — the import preserves the imported tracks' cues only when adding them, and on existing tracks the user-side cues win).
3. Direct writes to `master.db` are technically possible via `pyrekordbox` but Pioneer treats the schema as private — risky.

There's no public, supported way to programmatically push hot-cue changes back into a running rekordbox library. Plan accordingly.

### Tracking 880 tracks ↔ 880 ANLZ folders

The mapping is by **filename** (the `?/` path inside `PPTH`), not by the full path or `TrackID`. If two tracks have the same filename, they'd collide on this mapping — we haven't seen that yet but it's worth a check before relying on it for a large library.

---

## 9. Open questions / not investigated

- **Exact PCOB/PCO2 entry layout for hot cues** — we haven't decoded a non-empty one because our library doesn't have any. When we eventually decrypt `master.db`, we'll get cues from there directly and skip ANLZ.
- **What `master.db-wal` contains during a session** — we know it has uncommitted writes; haven't probed format.
- **`product.db`** — encrypted with a different magic than master.db. Unknown purpose.
- **`*.edb` files** — tiny, format unknown, untouched.
- **Memory-cue colour and naming** — Num=-1 entries can have colours and names too; we haven't seen any in our library to verify.
- **MyTag / Track Color / Hot Cue Bank** — rekordbox 6+ features not exported in the XML at all; only available via `master.db`.
- **Cloud-sync metadata** — present in `master.db` per `pyrekordbox` docs; not relevant unless user enables cloud sync.

---

*Sources for REFERENCE-marked claims: Deep Symmetry's `crate-digger` and `dysentery` projects (Java; the canonical reverse-engineering work for Pro DJ Link / ANLZ formats); the `pyrekordbox` Python project (active community SQLCipher tooling for rekordbox 6/7); Pioneer's XML interop spec circa 2014 (still accurate for the XML container format).*
