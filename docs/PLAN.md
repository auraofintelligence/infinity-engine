# Infinity Engine plan

Written 2026-07-20, replacing the late-2025 notes. The durable architecture from the original brief stands: model-agnostic registry, knowledge base as the brain, cheap ideation before expensive generation, human gates, comic pre-viz whose panels become video keyframes, five lanes on one spine, personal-use-first.

## What changed from the old plan

- **The vault bootstraps itself.** The album-pack repo already carries 92 songs with full lyrics, meaning layers, album visual worlds and release metadata in machine-readable pages. Phase 0 ingests from there today; the private cleaned-lyrics folder on the production machine is a second source, not a prerequisite.
- **Ideation is text-in/text-out, not API-wired.** Prompt packets are plain files. They can go through the claude CLI (already paid for), a local Qwen, or any future model. No LLM SDK dependency in the core.
- **Jobs are folders, runners are config.** A job = `spec.json` + reference assets in one directory; results come back into it. That folder is the only thing that ever touches a GPU worker.

## Pipeline spine

```
ingest → analyse (LLM) → brief (Luke gate) → panels → keyframes → video → publish
          cheap text        human gate       images    stills      $$$
```

Every stage advances `status` in the note's frontmatter, so the vault itself is the state machine and git is the audit log. The SQLite db only logs generation jobs and costs.

## Five lanes, one spine

| Lane | Reuses | Adds |
|---|---|---|
| lyric-video | analyse + panels + keyframes | beat-synced assembly (librosa cut lists + ffmpeg) |
| comic / graphic novel | analyse + panels | page layout, lettering (Qwen-Image text rendering) |
| course-video | analyse + TTS | avatar presenter (InfiniteTalk / HunyuanVideo-Avatar) |
| micro-drama | analyse (story_seed) + panels + keyframes | dialogue TTS + lip-sync, vertical framing |
| album-aggregate | everything above | sequencing across an album's notes |

## Phases

- **Phase 0 (this repo, done):** vault + ontology + ingest + ideation packets + claude-CLI loop + validate + dashboard + runner/job scaffolding + researched providers.yaml.
- **Phase 1, comic pre-viz:** a ComfyUI workflow (Qwen-Image) driven by `panel_beats`, wrapped as a `panels` job the local runner can execute on the RTX 3060/production box for drafts. Character LoRA training for the recurring cast (one-off, ~US$1-5 per character on a rented A100).
- **Phase 2, remote video:** worker image (ComfyUI + Wan 2.2 / HunyuanVideo 1.5) for Vast.ai interruptible 4090s; `keyframes → video` jobs via the remote_pod runner; per-job cost written back to the log. First full lyric video end to end.
- **Phase 3, sound and mouths:** TTS (Qwen3-TTS) + lip-sync (LatentSync/InfiniteTalk) jobs; first micro-drama.
- **Phase 4, assembly and publish:** beat-synced cutting (librosa + ffmpeg), platform renders (9:16, 1:1, 16:9), publish checklists per platform.

Model refresh is a recurring chore, not a rebuild: re-run the research pass, edit `providers.yaml`, done.

## Cost picture (2026-07-20)

- Draft video batch: Vast.ai interruptible 4090 ~US$0.30/hr; a 6 s draft clip costs a few cents of GPU time.
- Premium runs: RunPod secure A100 80GB ~US$1.39/hr or H100 ~US$2.99/hr with a network volume so 30 GB of weights persists between sessions.
- Zero-ops fallback: fal.ai per-output (hosted Wan ~US$0.05/s of video) when a hosted model beats self-hosting for a hero shot.
- Whole-album maths: 100 songs × ~40 draft clips × 6 s ≈ 40 hrs of 4090 time ≈ US$12-15 per full draft sweep. The expensive tier only ever renders approved shots.
