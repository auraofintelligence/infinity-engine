# Recon watcher

The watcher keeps the engine current without you babysitting Hugging Face. It scans for new and surging models per category and drops the notable ones into the Recon area, where you vet them on a cheap pass before anything reaches the working stack. It never changes the active registry on its own; it only proposes.

This is the discover step of the loop:

```
watcher → recon-queue.yaml → you vet in Recon → promote to catalog/models.yaml → pickers → patterns/jobs
```

## What it does

`python tools/watch_models.py`:

1. Queries the public Hugging Face API for the top models by likes in each tracked category.
2. Compares against what it saw last run (`catalog/.seen.json`) and what's already known (the recon queue plus `catalog/models.yaml`).
3. Flags anything that is brand new with real traction, or has surged in likes since last time, appending it to `recon-queue.yaml` with a reason and date.
4. Updates its like snapshot so next run can detect surges.

No auth, no dependencies beyond PyYAML. It fails soft: if a category can't be fetched, it logs and moves on.

## Categories and thresholds

Tracked categories map to Hugging Face pipeline tags in `tools/watch_models.py` (`CATEGORIES`): video, image, tts, stt, lipsync. Add a line to that dict to track a new category (for example `text-generation` for LLMs, or a control tag once HF standardises one).

Tunable at the top of the script:

- `TOP_N` how many top-by-likes to pull per category (default 25)
- `SURGE` likes gained since last run to count as hype (default 150)
- `NEW_FLOOR` minimum likes for a brand-new model to be worth flagging (default 120)

Raise the floors if the queue gets noisy; lower them to catch things earlier.

## Scheduling it (Windows)

Mirror the existing traffic-digest scheduled task. Register a weekly run:

```
schtasks /create /tn "InfinityEngine-ReconWatcher" /tr ^
  "python C:\Users\sbt41\githublocal\infinity-engine\tools\watch_models.py" ^
  /sc weekly /d SUN /st 07:00
```

Weekly is plenty; the open-model world moves fast but not daily. After it runs, regenerate the site (`python -m engine site`) so the Recon page shows the new candidates, or add that as a second line in a small wrapper script.

## Prices and the manual scan

Model discovery is automated because Hugging Face has a clean API. GPU pricing does not, and rates on the marketplace hosts drift, so `catalog/compute.yaml` is refreshed by a periodic manual pass rather than a scraper: roughly quarterly, or before any big batch, re-run the dated compute research (the same web scan that seeded the file), update the AUD figures at the current conversion rate, and note the date. The watcher's job is to surface new compute options worth a look; committing a price is a human call.

## Vetting flow

On the Recon page, each candidate carries its category, why it was flagged, and a link to source. For each one:

1. Run it through a cheap Recon-lane pass on a real song or shot.
2. If it beats the incumbent on your own material, promote it: add an entry to `catalog/models.yaml` with `status: active` and set the queue item to `adopted`.
3. If not, set it to `rejected` with a one-line why.

New models only ever enter through Recon. That's the risk gate: nothing hits a Hero render until it has earned its place on your own footage.
