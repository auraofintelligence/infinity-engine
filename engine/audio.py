"""Audio stem reading for ingestion: WAV specs, silence detection and
role mapping, straight from a Suno stem export (a folder or a zip of WAVs).

Stdlib only (wave, audioop) so it runs today with no ML install. The
heavier analysis (timed sections via All-In-One, word timing via WhisperX,
energy via Essentia) plugs in as a later layer; this core proves the
pipeline reads the real export and produces the arrangement map.
"""
from __future__ import annotations

import array
import io
import math
import re
import struct
import zipfile
from pathlib import Path

# Suno track name -> (role, group). Group drives visual meaning: rhythm
# for cuts, vocal for lyric focus, low/harmony/texture for energy layers.
ROLE_MAP = {
    "vocals": ("vocals", "vocal"),
    "backing_vocals": ("backing vocals", "vocal"),
    "drums": ("drums", "rhythm"),
    "percussion": ("percussion", "rhythm"),
    "bass": ("bass", "low"),
    "guitar": ("guitar", "harmony"),
    "keyboard": ("keyboard", "harmony"),
    "keys": ("keys", "harmony"),
    "piano": ("piano", "harmony"),
    "strings": ("strings", "harmony"),
    "brass": ("brass", "harmony"),
    "woodwinds": ("woodwinds", "harmony"),
    "synth": ("synth", "texture"),
    "fx": ("fx", "texture"),
}
SILENCE_DBFS = -45.0   # a stem quieter than this across the song is empty


def role_from_name(name: str) -> tuple[str, str]:
    """Map a stem filename to (role, group). Handles Suno's 'N Name.wav'."""
    stem = Path(name).stem
    m = re.match(r"\s*\d+[\s._-]+(.+)", stem)     # strip a leading order number
    core = (m.group(1) if m else stem).strip().lower()
    core = re.sub(r"[^a-z_]+", "_", core).strip("_")
    if core in ROLE_MAP:
        return ROLE_MAP[core]
    for key, val in ROLE_MAP.items():             # substring fallback
        if key in core:
            return val
    return (core.replace("_", " ") or "unknown", "other")


def _read_riff(fobj) -> tuple[dict, int, int]:
    """Minimal WAV parser: handles PCM (fmt 1), IEEE float (fmt 3) and the
    WAVE_FORMAT_EXTENSIBLE (fmt 0xFFFE) that Suno's float exports use.
    Returns (fmt, data_offset, data_size). Stdlib only."""
    head = fobj.read(12)
    if head[:4] != b"RIFF" or head[8:12] != b"WAVE":
        raise ValueError("not a RIFF/WAVE file")
    fmt, data_off, data_size = None, None, 0
    while True:
        hdr = fobj.read(8)
        if len(hdr) < 8:
            break
        cid, size = hdr[:4], struct.unpack("<I", hdr[4:8])[0]
        if cid == b"fmt ":
            b = fobj.read(size)
            af, ch, sr, _br, _ba, bits = struct.unpack("<HHIIHH", b[:16])
            if af == 0xFFFE and size >= 40:      # EXTENSIBLE: real tag at +24
                af = struct.unpack("<H", b[24:26])[0]
            fmt = {"format": af, "channels": ch, "sample_rate": sr, "bits": bits}
        elif cid == b"data":
            data_off, data_size = fobj.tell(), size
            fobj.seek(size + (size & 1), 1)
        else:
            fobj.seek(size + (size & 1), 1)
    if not fmt or data_off is None:
        raise ValueError("missing fmt or data chunk")
    return fmt, data_off, data_size


def _rms_fraction(chunk: bytes, fmt_code: int, bits: int) -> float:
    """RMS of a byte chunk as a fraction of full scale [0,1]."""
    if not chunk:
        return 0.0
    if fmt_code == 3 and bits == 32:             # IEEE float32, already [-1,1]
        n = len(chunk) // 4
        vals = array.array("f")
        vals.frombytes(chunk[:n * 4])
        norm = 1.0
    elif fmt_code == 1 and bits == 16:
        n = len(chunk) // 2
        vals = array.array("h")
        vals.frombytes(chunk[:n * 2])
        norm = 32768.0
    elif fmt_code == 1 and bits == 32:
        n = len(chunk) // 4
        vals = array.array("i")
        vals.frombytes(chunk[:n * 4])
        norm = 2147483648.0
    elif fmt_code == 1 and bits == 24:           # unpack 3-byte little-endian
        step = 8                                 # decimate: every 8th sample
        acc = cnt = 0
        for i in range(0, len(chunk) - 2, 3 * step):
            v = int.from_bytes(chunk[i:i + 3], "little", signed=True)
            acc += (v / 8388608.0) ** 2
            cnt += 1
        return math.sqrt(acc / cnt) if cnt else 0.0
    else:
        return 0.0
    step = max(1, len(vals) // 20000)            # decimate large windows
    acc = cnt = 0
    for i in range(0, len(vals), step):
        x = vals[i] / norm
        acc += x * x
        cnt += 1
    return math.sqrt(acc / cnt) if cnt else 0.0


def _analyse_wav(fobj, windows: int = 5, win_s: float = 3.0) -> dict:
    fmt, data_off, data_size = _read_riff(fobj)
    ch, bits, sr = fmt["channels"], fmt["bits"], fmt["sample_rate"]
    frame = ch * bits // 8
    total = data_size // frame if frame else 0
    duration = round(total / sr, 2) if sr else 0.0
    win = int(sr * win_s)
    span = max(0, total - win)
    best = 0.0
    for k in range(max(1, windows)):
        pos = int(span * k / (windows - 1)) if windows > 1 and span else 0
        fobj.seek(data_off + pos * frame)
        chunk = fobj.read(min(win, total) * frame)
        best = max(best, _rms_fraction(chunk, fmt["format"], bits))
    db = round(20 * math.log10(best), 1) if best > 0 else -120.0
    return {"channels": ch, "bit_depth": bits, "sample_rate": sr,
            "duration_s": duration, "rms_dbfs": db, "active": db > SILENCE_DBFS,
            "float": fmt["format"] == 3}


def _iter_wavs(source: Path):
    """Yield (name, file-like) for each WAV in a folder or a zip."""
    if source.is_dir():
        for p in sorted(source.glob("*.wav")):
            with open(p, "rb") as fh:
                yield p.name, io.BytesIO(fh.read())
    elif source.suffix.lower() == ".zip":
        with zipfile.ZipFile(source) as zf:
            for name in sorted(n for n in zf.namelist()
                               if n.lower().endswith(".wav")):
                yield Path(name).name, io.BytesIO(zf.read(name))
    else:
        raise ValueError(f"expected a folder or a .zip of WAVs: {source}")


def density_label(active: int, total: int) -> str:
    if not total:
        return "empty"
    frac = active / total
    if frac <= 0.34:
        return "sparse"
    if frac <= 0.66:
        return "medium"
    return "full"


def analyse_stems(source: Path, bpm: int | None = None) -> dict:
    """Build the audio block from a Suno stem export (folder or zip)."""
    stems = []
    specs = {}
    for name, fobj in _iter_wavs(source):
        info = _analyse_wav(fobj)
        role, group = role_from_name(name)
        # Suno numbers the tracks; track 0 is the full mix (master).
        order = re.match(r"\s*(\d+)", Path(name).stem)
        if (order and order.group(1) == "0") or group == "other":
            role, group = ("full mix", "mix")
        stems.append({"file": name, "role": role, "group": group,
                      "active": info["active"], "rms_dbfs": info["rms_dbfs"]})
        specs = {"sample_rate": info["sample_rate"],
                 "bit_depth": info["bit_depth"], "channels": info["channels"],
                 "encoding": "float" if info["float"] else "int",
                 "duration_s": info["duration_s"]}
    playable = [s for s in stems if s["group"] != "mix"]
    active = [s for s in playable if s["active"]]
    return {
        "source": source.name,
        **specs,
        "tempo_bpm": bpm,
        "stem_count": len(playable),
        "active_stems": [s["role"] for s in active],
        "arrangement": density_label(len(active), len(playable)),
        "arrangement_density": f"{len(active)}/{len(playable)}",
        "stems": stems,
    }
