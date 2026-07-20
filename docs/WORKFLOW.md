# Infinity Engine: how to drive it

This is the operator's manual. It explains what happens at each stage, what you (Luke) actually do, where files go, and how to judge each pass. Read [PLAN.md](PLAN.md) for the why; this is the how.

Two things up front:

- **What is built today:** stages 1-3 (ingest, analyse, the human gate). Commands: `ingest`, `status`, `validate`, `brief`, `merge`, `jobs`, `dashboard`, `site`.
- **What is designed but not built yet:** stages 4-7 (panels, keyframes, video, publish). The job/runner scaffolding exists, but the workers that generate images and video do not. Those are Phases 1-4.

Everything runs from the repo root: `cd infinity-engine` then `python -m engine <command>`.

---

## The one idea to hold in your head

Each song is a single markdown file in `vault/`. That file **is** the state of that song. Its `status:` field says which stage it has reached. Everything the engine does is: read those files, do one stage of work, write the result back into the file, bump the status. Git is the history; the SQLite log is just for tracking generation cost.

```
status flow:  ingested → analysed → briefed → panels → keyframes → video → published
              \______ built today ______/   \____________ designed, Phase 1-4 ____________/
              cheap text, no GPU cost         a human gate here      real GPU spend starts here
```

Cheap thinking first. A human gate in the middle (you). Expensive generation only ever runs on ideas you already approved.

---

## Where everything lives

```
infinity-engine/
├── config.yaml          you edit: where sources are, which albums, which runner per tier
├── providers.yaml       you edit: which model + which GPU host for each job type
├── ontology.yaml        you edit rarely: the fixed vocabulary of tags/statuses
├── vault/               the brain: one <song-slug>.md per song  (gitignored, never shipped)
├── jobs/
│   ├── prompts/         ideation packets: <slug>.prompt.txt
│   ├── <job-id>/        one folder per generation job: spec.json + results/
│   └── engine.db        SQLite log of every generation job and its cost
├── docs/                the public monitor site (this folder) + these guides
└── engine/              the code
```

The rule that keeps your data safe: **the vault and orchestration never leave your machine.** The only thing that ever goes to a rented GPU is one job folder (`spec.json` plus reference images). A rented box sees one song's payload, nothing else.

---

## Stage 1 — ingest  *(built)*

**What happens:** `python -m engine ingest` reads the universe repo's `catalogue.json` and each song's HTML page, and writes one note per song into `vault/`. It pulls in title, album, track number, release link, the album's visual world, and the full lyrics, plus a crude keyword guess at themes so no note is blank.

**Your action:** run it. That's all. It is safe to re-run any time you push new songs to the universe repo; it only refreshes the imported fields and lyrics, and never overwrites analysis or a status you have advanced.

**Which songs:** controlled by the `albums:` allowlist in `config.yaml`. Right now that is the four core albums. Add a slug there to bring an album in.

**Files:** `vault/<slug>.md` created/updated.

**How to evaluate the pass:**
- `python -m engine status` — counts by album and by stage. Check the totals match what you expect.
- `python -m engine validate` — every note checked against `ontology.yaml`. Must say all notes clean.
- Open any `vault/*.md` and read it. The frontmatter is the metadata; the body is the lyrics.

---

## Stage 2 — analyse  *(built)*

This is the cheap text-thinking layer. It turns lyrics into a visual plan before a cent is spent on generation.

**What happens:** `python -m engine brief <slug>` writes a self-contained prompt into `jobs/prompts/<slug>.prompt.txt`. That prompt asks an LLM to return a JSON object with: `themes`, `mood`, `narrative_structure`, `visual_motifs` (filmable images from the lyrics), `emotional_arc`, `story_seed` (a micro-drama premise), and `panel_beats` (8-12 comic panels in order). Then `merge` folds that JSON back into the note and moves its status to `analysed`.

**Your action, two ways:**
- *Hands-off:* `python -m engine brief <slug> --run-claude` runs the packet through your local `claude` CLI and merges the answer automatically.
- *Hands-on:* `python -m engine brief <slug>`, open the `.prompt.txt`, paste it into any chat (Claude, a local Qwen, whatever), save the JSON reply to a file, then `python -m engine merge <slug> that-file.json`.

Do many at once with `python -m engine brief --all` (every song still at `ingested`).

**Files:** `jobs/prompts/<slug>.prompt.txt` in; the note's frontmatter gains the analysis fields.

**How to evaluate the pass:** open the note and read `story_seed` and `panel_beats`. This is the cheapest place to iterate, so be picky. Does the story seed catch what the song is actually about? Do the panel beats make a sequence you would want to see? If not, either re-run the brief (models vary) or just edit the note by hand. This is where your taste enters the machine.

---

## Stage 3 — briefed: the human gate  *(built, manual)*

**What happens:** nothing automatic. This is you deciding a song is ready to cost money.

**Your action:** open the note and:
- confirm or rewrite the `panel_beats` until they are the shot list you want,
- set `lanes:` to what you are actually making (`lyric-video`, `comic`, `micro-drama`, `course-video`, `album-aggregate`),
- set `status: briefed`.

Then `python -m engine site` and the song moves a notch on the public monitor.

**How to evaluate:** one question — is this idea worth GPU spend, and which shots carry it? Everything downstream renders what you approve here, so a weak brief wastes money later. Songs can sit at `analysed` indefinitely; only gate the ones you mean to make.

> There is no `gate` command yet — you hand-edit the note. If that gets tedious across many songs I can add `python -m engine gate <slug> --lane micro-drama` to do it in one line. Say the word.

---

## Stage 4 — panels  *(designed, Phase 1 — not built)*

**Intended shape:** `engine make panels <slug>` builds a job folder. `spec.json` carries the `panel_beats`, the album's visual world, style references, and a character LoRA for any recurring cast. A ComfyUI workflow (Qwen-Image) renders 8-12 still panels. For drafts this runs on your production box via the `local` runner; no rented GPU needed.

**Your action (future):** run the command, then look at the panels.

**Files (future):** `jobs/<slug>-panels-<id>/spec.json` in, `results/panel-01.png …` out.

**How you will evaluate:** do the stills read as a coherent visual story, in your world, on-model for the cast? Stills are cheap and fast to re-roll, so this is the second cheap gate before video. You approve the strongest panels; those become the keyframes.

**To bring this online you need:** ComfyUI installed on the production box, the Qwen-Image weights, one working panel workflow, and a one-off character-LoRA train per recurring character (about A$2-7 of rented A100 time each, converted at AUD/USD 0.70). This is the next build step whenever you want it.

---

## Stage 5 — keyframes  *(designed, Phase 2 prep — not built)*

**Intended shape:** the approved panels become the start/end frames of video shots. Largely a selection-and-crop step: you pick which panel pairs bookend each motion.

**Files (future):** `keyframes/` inside the same job folder.

**How you will evaluate:** which pairs of stills imply good motion between them.

---

## Stage 6 — video  *(designed, Phase 2 — not built)*

**Intended shape:** `engine make video <slug>` builds a job whose `spec.json` carries keyframe pairs plus a motion prompt. It runs an open video model (Wan 2.2 or HunyuanVideo 1.5) on a **rented** GPU via the `remote_pod` runner. The job folder is pushed to the pod over SSH, the model renders short clips, results come back, and the cost is written to `jobs/engine.db`.

**Your action (future):** spin up a Vast.ai or RunPod pod, put its address into `providers.yaml` under `runners.remote_pod.host`, run the command. Draft clips cost a few cents each; a full draft sweep of all 96 songs is roughly A$18-22.

**Files (future):** `jobs/<slug>-video-<id>/results/shot-01.mp4 …`

**How you will evaluate:** watch the clips. Look for the usual generative-video failures — faces morphing, objects drifting, hands. Re-roll the bad shots (they are individually cheap), approve the keepers.

**To bring this online you need:** a worker image (ComfyUI + the video model) on the pod, and the `remote_pod.command` in `providers.yaml` pointed at it. The runner plumbing already exists; only the worker is missing.

---

## Stage 7 — published  *(designed, Phase 4 — not built)*

**Intended shape:** approved clips are assembled to the beat (a `librosa` cut list driving `ffmpeg`), rendered per platform (9:16 vertical, 1:1, 16:9), and checked against a per-platform publish list. For micro-dramas and course videos, Phase 3 slots in first: TTS (Qwen3-TTS) for dialogue and lip-sync (LatentSync / InfiniteTalk) before assembly.

**Files (future):** `final/<platform>/<slug>.mp4`.

**How you will evaluate:** does it cut on the beat, hold up in the target aspect ratio, and clear your publish checklist.

---

## How the pieces connect (the runner model)

A **job** is a folder: `spec.json` + any reference assets, with an empty `results/` waiting. That folder is the unit of work and the only thing that travels.

A **runner** decides where that folder executes. Three kinds, chosen per tier in `config.yaml` (`default_runners:`) and configured in `providers.yaml` (`runners:`):

| Runner | What it does | Use for |
|---|---|---|
| `local` | runs a command on this machine against the job folder | draft panels, anything your own GPU can handle |
| `remote_pod` | SSHes the folder to a rented GPU, runs one command, pulls `results/` back | standard/premium video on Vast.ai or RunPod |
| `saas` | calls a hosted per-output API (fal.ai) — stub for now | a hero shot where a hosted model beats self-hosting |

So "connecting a piece" means: pick the model in `providers.yaml`, pick the runner for that tier, and (for `remote_pod`) drop the live pod address in when you rent one. Workflow code never changes — only config. Swapping Wan for a newer model next year is a two-line edit.

---

## The loop, in one screen

```
push new songs to the universe repo
        │
        ▼
python -m engine ingest         # stage 1  → notes appear/update in vault/
python -m engine validate       #            sanity check
        │
        ▼
python -m engine brief <slug> --run-claude   # stage 2 → analysis in the note
        │  (read it, fix it — cheap)
        ▼
edit the note: set panel_beats, lanes, status: briefed   # stage 3 → YOUR gate
        │
        ▼
[Phase 1+]  engine make panels <slug>   → review stills
            engine make video  <slug>   → review clips     (rented GPU, logged cost)
            engine assemble    <slug>   → per-platform renders
        │
        ▼
python -m engine site           # regenerate the monitor
git add -A && git commit && git push    # the live site updates
```

The monitor at auraofintelligence.github.io/infinity-engine shows every song's stage and updates each time you run `site` and push.

---

## What to do next

Right now you can run stages 1-3 across all 96 songs for essentially free — that alone gives you a complete, edited visual plan (story seeds + panel beats) for the whole catalogue. The natural next build is **Phase 1 (panels)**, because it is the first stage that produces something you can look at, and it is the second cheap gate before any real spend. When you want it, that is the next thing I build.
