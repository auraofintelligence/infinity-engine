#!/usr/bin/env bash
# Bootstrap a fresh rented GPU box (Vast.ai / RunPod / any Ubuntu + NVIDIA)
# into a ComfyUI render node the Infinity Engine can drive.
#
# Run this ON THE POD, once, after you rent it:
#   bash pod_bootstrap.sh
#
# It installs ComfyUI + the Manager and starts the server on :8188 bound to
# localhost. You then reach it one of two ways (see docs/GPU-SETUP.md):
#   - SSH tunnel from your laptop  ->  engine work --server http://127.0.0.1:8188
#   - or run the engine on the pod itself
#
# It does NOT download model weights: which checkpoints you need is decided
# by catalog/comfy.yaml (the ckpt_name in each recipe). The MODELS section
# at the bottom shows where they go; fill in the download lines for the
# weights your recipes name, then re-run just that part.
set -euo pipefail

COMFY_DIR="${COMFY_DIR:-$HOME/ComfyUI}"
PORT="${PORT:-8188}"

echo "==> system deps"
if command -v apt-get >/dev/null; then
  sudo apt-get update -y
  sudo apt-get install -y git python3-venv python3-pip ffmpeg
fi

echo "==> ComfyUI into $COMFY_DIR"
if [ ! -d "$COMFY_DIR" ]; then
  git clone https://github.com/comfyanonymous/ComfyUI "$COMFY_DIR"
fi
cd "$COMFY_DIR"

echo "==> python venv + deps"
python3 -m venv venv
# shellcheck disable=SC1091
source venv/bin/activate
pip install --upgrade pip
# Torch matched to the pod's CUDA; most rented images ship a working torch
# already, so only install if it is missing.
python -c "import torch" 2>/dev/null || pip install torch torchvision torchaudio
pip install -r requirements.txt

echo "==> ComfyUI-Manager (easy node/model installs later)"
mkdir -p custom_nodes
if [ ! -d custom_nodes/ComfyUI-Manager ]; then
  git clone https://github.com/ltdrdata/ComfyUI-Manager custom_nodes/ComfyUI-Manager
fi

cat <<'MODELS'

==> MODELS (do this bit yourself)
    Put the weights your recipes name (catalog/comfy.yaml -> ckpt_name)
    under:  $COMFY_DIR/models/checkpoints/
    e.g.
      cd "$COMFY_DIR/models/checkpoints"
      # download the safetensors your recipe points at, for example:
      # wget -O qwen-image.safetensors  "<hugging face resolve url>"
    Check what is expected any time with:  engine doctor

MODELS

echo "==> starting ComfyUI on 127.0.0.1:$PORT (Ctrl-C to stop)"
echo "    keep this running; reach it via SSH tunnel or on-pod engine work"
exec python main.py --listen 127.0.0.1 --port "$PORT"
