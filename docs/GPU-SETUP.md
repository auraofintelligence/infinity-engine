# Set up a GPU (spinning up other devices)

The engine does all its thinking on your own machine. The only step that
needs a real GPU is the render: turning a job's shots into images or video
through **ComfyUI**. This page is the concrete "spin up another device"
story, from renting a box to frames landing back on your laptop.

You never install ComfyUI on your laptop. You rent a GPU box by the hour,
run ComfyUI on it, and point the engine at it. When the batch is done, you
stop the box and stop paying.

## The one touchpoint

Everything ComfyUI-related goes through a single URL. Check it any time:

```
engine doctor
```

That prints where the engine expects ComfyUI (`server` in
`catalog/comfy.yaml`, default `http://127.0.0.1:8188`), whether it is
reachable right now, and which checkpoint each recipe expects. When
`reachable` says `YES`, renders will run. Until then, `engine work
--offline` still writes the exact ComfyUI graphs it would submit, so you
can build and inspect the whole pipeline with no GPU at all.

## Rent a box

Any Ubuntu + NVIDIA host works. Good picks (prices AUD, re-check before a
big batch):

- **Vast.ai** interruptible RTX 4090, ~A$0.45/hr, per-second billing:
  best for cheap draft batches.
- **RunPod** community 4090 ~A$0.50/hr, secure A100 80GB ~A$2/hr, H100
  ~A$4.30/hr; has a Sydney region and network volumes that keep weights
  warm between sessions.
- **fal.ai** per-output hosting if you would rather not manage a box at
  all (a different path; this page covers the rent-a-box path).

Pick a GPU with enough VRAM for the recipe tier you want (the vram_gb in
`providers.yaml`): a 4090 (24GB) covers draft and standard image work.

## Bootstrap it

Copy `tools/pod_bootstrap.sh` onto the box and run it once:

```
bash pod_bootstrap.sh
```

It installs ComfyUI + the Manager and starts the server on
`127.0.0.1:8188`. Then you download the weights your recipes name (it
prints where); `engine doctor` lists exactly which ones. Leave ComfyUI
running.

## Connect: two ways

**A. SSH tunnel (simplest, recommended to start).** From your laptop, open
a tunnel so the pod's ComfyUI looks local:

```
ssh -L 8188:localhost:8188 root@POD_ADDRESS
```

Leave that open. Now the engine on your laptop can drive the pod:

```
engine doctor                 # reachable should now say YES
engine make SLUG panels       # assemble a job
engine work                   # renders on the pod, frames land locally
```

The job folder never leaves your machine; only the graph travels over the
tunnel as an HTTP call, and the images come straight back into the job's
`results/`. This is the whole loop, tethered to the pod only while it
runs.

**B. Point straight at the box.** If you would rather not tunnel, expose
the pod's port and pass the address:

```
engine work --server http://POD_ADDRESS:8188
```

Same result. Use a tunnel or a firewall rule so the ComfyUI port is not
open to the world.

**C. Run the engine on the pod (for long unattended batches).** Copy the
repo (or just the queued job folders) to the box, run `engine work` there
against its local ComfyUI, then copy `results/` back. Best when you do not
want your laptop tethered for hours.

## The full loop, once a box is up

```
engine make SLUG panels        # 1-5: data, model, compute, direction -> job folder
engine work                    #  6 : render on the GPU (or --offline to just emit graphs)
#          review results/ and the manifest
engine advance SLUG panels     #  7 : move the song to the next stage
```

Stop the box when the batch is done. Nothing on your side depends on it
staying up: the vault, the jobs and their results are all local.

## Which model renders

You never edit code to swap a model. Each recipe in `catalog/comfy.yaml`
names a `ckpt_name` (the exact file under
`ComfyUI/models/checkpoints/`) and its sampler settings, keyed by category
and tier. Change the model = change that line, put the weights on the pod,
`engine doctor` to confirm. Qwen-Image and FLUX.2 use different loader
nodes than the classic graph; those plug in as new graph builders in
`engine/comfy.py`, still with no change to the render loop.
