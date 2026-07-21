# Infinity Engine master plan (v2)

Written 2026-07-21, superseding the v1 plan. v1 covered the vault and the model registries; since then the system has grown audio ingestion, treatments, a karaoke renderer design, cast/LoRA registries, a recon loop, and now the distribution layer. This plan makes all the moving parts one flow.

Prices in AUD (converted at AUD/USD 0.70, 2026-07-20 unless noted). Honest tense throughout: **built** means running today, **designed** means agreed shape not yet coded, **horizon** means intentionally later.

---

## 1. North star

Turn the i C. infinity catalogue into film across three lanes: **Recon** (fast, rough, cheap: test models, harvest LoRA data, learn), **Release** (publishable, teachable, community-facing), **Hero** (A Protopian Gambit and festival shorts, fully directed). Earlier albums are deliberately the R&D lab and community on-ramp. Everything ships from a pipeline Luke owns end to end: open-weight first, rented GPUs on demand, nothing locked to a vendor.

## 2. The one diagram

```
                    SOURCES (stay on trusted machines)
  lyrics (universe repo)   Suno stems (WAV+MIDI)   human cockpit signals
        │                        │                        │
        ▼                        ▼                        ▼
  ┌────────────────────── INGESTION (built / designed) ─────────────────────┐
  │ structure.py: verses/chorus,   ingest-audio: timed sections, beat grid, │
  │ keywords, motifs (BUILT)       per-stem energy, lyric word timestamps,  │
  │                                active-stem list (DESIGNED, next build)  │
  └──────────────────────────────────┬───────────────────────────────────---┘
                                     ▼
             THE NOTE (vault/<slug>.md = the song's single source of truth)
      structure + motifs + audio block + analysis + section_plan + productions
                                     ▼
  analyse (LLM brief, per-section set/scene/energy/transition)  ── BUILT
                                     ▼
  ██ GATE: Luke approves direction, picks treatments ██  (status: briefed)
                                     ▼
  ┌───────────────────────── TREATMENTS (per song, each own status) ────────┐
  │ karaoke lyric video   artistic film        complex film                 │
  │ timing+style render   supports/contradicts  band/acted/CGI transpose    │
  │ no GPU, local, fast   lyrics (mid cost)     cast+motion rig (Hero)      │
  └──────────────────────────────────┬──────────────────────────────────────┘
                                     ▼
  FORMAT RENDERS (one treatment → many platform formats, from one master)
                                     ▼
  RELEASE PACK (agent-ready folder per song/album, asset-guide families)
                                     ▼
  PLATFORMS (YouTube, Shorts, IG, TikTok, Spotify Canvas, Bandcamp, site...)
```

Rule that never changes: **sources and the vault stay local; only small derived data (JSON, timings) and approved renders move.** Stems are ~470 MB a song; their feature block is a few KB. Same privacy rule as the lyrics.

## 3. Ingestion (the nuance layer)

Three inputs, one note:

1. **Lyric structure** (BUILT): marker-aware parsing (Verse/Chorus/Bridge labels when present, hook-line detection when not), per-section keywords, song-wide motifs.
2. **Audio** (DESIGNED, next build): from the Suno stem export per song. Verified reality: WAV 24-bit/44.1k + optional MIDI, track-based stems with silent placeholder tracks. `engine ingest-audio` will: enumerate WAVs, map roles by track name, RMS-skip silent stems, record the **active-stem list** (arrangement density = a visual signal), run All-In-One (timed sections, beats, downbeats, tempo), WhisperX on the Vocals stem against the known lyrics (word timestamps; never ASR guessing, which kills the CapCut problem at the root), Essentia energy curves per stem. Output: an `audio` block + `timing.json` per song.
3. **Human cockpit** (DESIGNED): the 001 Human Listen page's signals (quick notes, pads, per-timestamp feelings) finally get a home as a `human_signals` block on the note. Objective + subjective, one source of truth.

Reconciliation: parsed lyric sections + timed audio sections + energy = a **timestamped, energy-aware `section_plan`**. That is the spine every treatment reads.

## 4. Treatments

A song has one spine status (ingested → analysed → briefed) and then **one status per treatment** in a `productions:` list on the note:

```yaml
productions:
  - lane: karaoke          # karaoke | artistic | complex | comic | course | micro-drama
    tier: release          # recon | release | hero
    relationship: support  # support | counterpoint | tangent (artistic/complex)
    status: rendered       # planned | briefed | panels | shots | assembled | rendered | released
    formats: {yt: released, shorts: rendered, ig-feed: queued, canvas: planned}
```

- **Karaoke lyric video** (first rung): timing.json + a style skin → ASS subtitles (native per-syllable wipe) → ffmpeg render. Guitar-hero flow rules: fixed focal anchor, progressive fill, ~120ms anticipation lead, beat-coupled pulses, 2-line max, safe areas. Restyle = swap skin, re-render in seconds. Every song can have one with zero GPU spend. Existing CapCut-era YouTube videos get recorded as legacy releases.
- **Artistic film**: generated imagery in a stated relationship to the lyrics (`support`/`counterpoint`/`tangent`, a one-word directorial decision that changes every image).
- **Complex film**: performance/acted/CGI-transposed, drawing on the cast LoRAs, motion capture and control rig. Hero lane.
- Comic, course video, micro-drama and album aggregates remain lanes on the same spine (pattern library already covers them).

## 5. Formats and platforms (the new layer)

One treatment renders to many formats. The format matrix comes straight from the asset guide (ai-native-indie-distribution/asset-guide.html) and lives in the repo as **`formats.yaml`** so it is data, not prose:

| Key | Size | Platform / use | Notes |
|---|---|---|---|
| `yt` | 1920x1080 16:9 | YouTube main | H.264/AAC, thumbnail 1280x720 |
| `shorts` | 1080x1920 9:16 | Shorts / Reels / TikTok shared master | captions safe, hook timestamp, loop point |
| `ig-feed` | 1080x1080 1:1 | Instagram feed | still or video |
| `ig-portrait` | 1080x1350 4:5 | Instagram portrait | |
| `canvas` | 9:16, 3-8s loop | Spotify Canvas | 720-1080px tall, MP4 |
| `story` | 1080x1920 | story frame still | |
| `cover` | 3000x3000 | DSP cover master | + 1080 square, WebP web copies |
| `site` | responsive | release page embed | + compressed poster frame |

Per-format rules a skin must respect (safe zones, caption areas, hook-first cutdown for vertical) are fields in formats.yaml. **One master render per treatment, then automated crops/cutdowns per format**, vertical is reframed, not squashed.

**Status icons + priority.** Each production's `formats:` map drives the site: a compact icon strip per song/treatment (done / rendering / queued / planned per format). Priority is config, not vibes: a default platform order per lane in formats.yaml (karaoke default: `yt → shorts → canvas → ig-feed`), and the site computes **"next up"**: the highest-priority undone format across the catalogue. That answers "what do I render next, for which platform" at a glance.

## 6. Release packs and distribution

Every song (and album) accumulates an **agent-ready release folder** matching the asset guide's structure: `/audio /artwork /video /copy /metadata /licensing /public /private + manifest.md`. The engine fills what it produces (video formats, captions SRT, timing-derived metadata like BPM/key/hook timestamp, lyric sheet); Luke and other tools fill the rest (cover art, credits, ISRC/UPC). `engine release <slug>` (designed) assembles the folder and writes the manifest with per-asset status and the asset-guide checklist. The release pack is the handoff point to distribution workflows (ai-native-indie-distribution builders) and to the paid packages on strange-but-true / right-place-right-time, including the **fan-custom karaoke render** perk (pick song + skin, rendered in seconds, near-zero marginal cost).

## 7. Progress, authority and the site

One tree, rolled up everywhere:

```
Catalogue → Album → Song → Treatment → Format
Collections (course, short film, series) → reference treatments across albums
```

- Progress bars per album exist today; they extend to treatment bars and format icon strips. Collections get their own rollup pages.
- **Gates carry authority**: each stage is `auto`, `review` (machine proposes, Luke approves) or `luke` (only Luke: the briefed gate, hero shots). Site shows gold gates (Luke's) vs teal (automated). The trust dial = flipping a gate in config as a pattern proves out.
- **Error correction is structural**: stages write to the note, git is history, re-running a stage resets downstream statuses for that treatment; the site marks `stale` when upstream changed.
- Per-song page (designed): spine timeline, treatments side by side, format strip, gates coloured, artefacts as they appear.

## 8. Registries and the recon loop (built)

Patterns, Cast (41), LoRA plan, open Models (44 incl. audio + worlds), Frontier (46 with verified affiliates), Compute (AUD), Sources, and the watcher → recon queue → vet → promote loop. Content notes (unfiltered/filtered/strict) on every model. These stay current via the watcher plus dated research passes; nothing enters Hero without earning it on our own footage.

## 9. Build order (revised)

| # | Piece | State | Exit test |
|---|---|---|---|
| 1 | `ingest-audio` (timing.json + audio block) | next | Be The Legend's map matches ears + Suno screenshot; word timing is karaoke-tight |
| 2 | Karaoke renderer (ASS + skins + format renders) | designed | one song, two skins, yt+shorts out; restyle in seconds |
| 3 | `productions`/formats data model + site icons, next-up queue | designed | site shows per-treatment/per-format truth |
| 4 | `engine release` pack assembler | designed | one complete agent-ready folder from real artefacts |
| 5 | Human cockpit → `human_signals` | designed | cockpit saves into a note |
| 6 | Comic pre-viz worker (panels from section_plan) | designed | first panel set on the production box |
| 7 | Remote video worker (Wan 2.2 on rented GPU) | designed | first artistic-film shots, cost logged in A$ |
| 8 | Cast LoRA foundry | designed | first validated character LoRA |
| 9 | Control rig (pose/motion, shot unit) | horizon | first directed hero shot |

Full karaoke catalogue sweep (96 songs) becomes possible at step 2 and costs ~nothing but render time; that is the community-facing win while the generative lanes mature.

## 10. Cost picture (unchanged fundamentals)

Karaoke lane: A$0 GPU, local ffmpeg. Draft generative: Vast.ai 4090 ~A$0.45/hr. Hero: RunPod A100 ~A$2.00/hr / H100 ~A$4.30/hr. LoRA training ~A$2-7 per character. Full draft-clip sweep of the catalogue ~A$18-22. Stems stay local (~45 GB catalogue-wide); only KB-scale derived data moves.
