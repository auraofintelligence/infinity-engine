# Infinity Engine

A model-agnostic pipeline that turns i C. infinity songs into visuals: lyric videos, comics, vertical micro-dramas, avatar course videos, and album aggregates. Cheap text thinking first, human direction points, expensive generation last.

Luke × Claude.

## How it works

1. **Vault** (`vault/`, gitignored): one markdown note per song with YAML frontmatter against a fixed ontology (`ontology.yaml`). Built by `ingest` from the album-pack repo and/or a private local lyrics folder. Plain files and git, no app lock-in.
2. **Ideation**: `brief` writes a self-contained prompt packet per song. Run it through any LLM (or `--run-claude` to use the claude CLI directly) and `merge` folds the JSON answer back into the note. Status moves `ingested → analysed`.
3. **Human gate**: Luke edits the note, picks a direction, sets status to `briefed`.
4. **Generation**: jobs (comic panels, keyframes, video shots, TTS, lip-sync) are folders of `spec.json` + assets. A `runner` executes them: local box, rented GPU pod over SSH, or a hosted API. Which model and which host is pure config in `providers.yaml`. Runs are logged to SQLite.
5. **Review**: `dashboard` renders a static HTML view of the whole catalogue and where every song sits.

The knowledge base and orchestration stay on the trusted machine. Only per-job payloads travel to GPU workers, which are treated as stateless and untrusted.

## Setup

```
pip install -r requirements.txt
python -m engine ingest
python -m engine status
python -m engine dashboard
```

Point `config.yaml` at your sources. On the production machine, set `sources.local_lyrics` to the cleaned lyrics folder.

## Commands

| Command | Does |
|---|---|
| `python -m engine ingest` | build/refresh the vault from sources (safe to re-run) |
| `python -m engine status` | counts by album and pipeline status |
| `python -m engine validate` | check every note against the ontology |
| `python -m engine brief SLUG` / `--all` | write ideation prompt packets |
| `python -m engine brief SLUG --run-claude` | run packet through claude CLI and merge |
| `python -m engine merge SLUG FILE` | merge an analysis JSON by hand |
| `python -m engine jobs` | recent generation job log |
| `python -m engine dashboard` | regenerate `dashboard.html` |

## Model and compute choices

`providers.yaml` holds the current registry (researched 2026-07-20): draft/standard/premium tiers for video, lip-sync, TTS, image, LLM and embeddings, plus where to rent GPUs and what it costs. Swapping a model or vendor is a config edit, never a code change. Licence notes are inline because the universe is commercial: everything in the default path is Apache 2.0 or MIT.

How to actually drive it, stage by stage, lives in the [operator guide](docs/WORKFLOW.md). The deeper plan lives in [docs/PLAN.md](docs/PLAN.md).
