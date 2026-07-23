"""Make a lyric video with no GPU, no models, no accounts.

The free half of the ladder: audio + typography + timing, rendered locally
with ffmpeg. Everything else in the engine needs a rented GPU; this needs
a laptop. That matters, because someone with no budget can finish this one.

How the timing works, honestly:
  A vocals stem tells us WHERE singing happens (energy above the floor),
  but not where one line ends and the next begins, because singing runs
  continuously. So we treat the sung regions as one "singing timeline",
  spread the lyric lines across it weighted by syllable count, then map
  back to wall-clock. Lines land in the right section and roughly the
  right place inside it. It is section-accurate, not karaoke-accurate.
  For true per-line timing you need forced alignment (a speech model).

Usage:
  python tools/lyric_video.py --audio media/mix.wav --vocals media/vocals.wav \
      --lyrics media/lyrics.txt --cover path/to/cover.jpg --out media/out.mp4 \
      --title "Song Title"
"""
from __future__ import annotations

import argparse
import math
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from engine.audio import _read_riff, _rms_fraction  # noqa: E402

WIN_S = 0.04          # analysis window
MERGE_GAP_S = 0.35    # gaps shorter than this are inside one phrase
MIN_PHRASE_S = 0.25
MIN_LINE_S = 0.9      # never flash a line
MAX_LINE_S = 7.0      # never leave one hanging


def voiced_blocks(vocals: Path) -> tuple[list[tuple[float, float]], float]:
    """Regions where the vocal is actually singing, plus track duration."""
    with open(vocals, "rb") as f:
        fmt, off, size = _read_riff(f)
        sr, ch, bits, code = (fmt["sample_rate"], fmt["channels"],
                              fmt["bits"], fmt["format"])
        bps = bits // 8
        frame = int(sr * WIN_S) * ch * bps
        f.seek(off)
        env, read = [], 0
        while read < size:
            chunk = f.read(min(frame, size - read))
            if not chunk:
                break
            read += len(chunk)
            r = _rms_fraction(chunk, code, bits)
            env.append(20 * math.log10(r) if r > 1e-9 else -120.0)
    duration = size / (sr * ch * bps)

    ordered = sorted(env)
    floor = ordered[int(len(ordered) * 0.20)]
    loud = ordered[int(len(ordered) * 0.97)]
    thr = max(floor + 8, loud - 26)

    regions, start = [], None
    for i, e in enumerate(env):
        if e > thr and start is None:
            start = i
        elif e <= thr and start is not None:
            regions.append((start, i))
            start = None
    if start is not None:
        regions.append((start, len(env)))

    merged: list[list[int]] = []
    for a, b in regions:
        if merged and (a - merged[-1][1]) * WIN_S < MERGE_GAP_S:
            merged[-1][1] = b
        else:
            merged.append([a, b])
    blocks = [(a * WIN_S, b * WIN_S) for a, b in merged
              if (b - a) * WIN_S >= MIN_PHRASE_S]
    return blocks, duration


def syllables(line: str) -> int:
    """Rough syllable count: vowel groups, with a floor of one."""
    groups = re.findall(r"[aeiouy]+", line.lower())
    return max(1, len(groups))


def place_lines(lines: list[str], blocks: list[tuple[float, float]]) -> list:
    """Spread lines across the singing timeline by syllable weight, then map
    back to wall-clock through the blocks."""
    spans = [b - a for a, b in blocks]
    total_sung = sum(spans)
    weights = [syllables(l) for l in lines]
    total_w = sum(weights)

    def to_wall(pos: float) -> float:
        """Map a position along the concatenated sung timeline to real time."""
        acc = 0.0
        for (a, b), span in zip(blocks, spans):
            if pos <= acc + span:
                return a + (pos - acc)
            acc += span
        return blocks[-1][1]

    out, cum = [], 0.0
    for line, w in zip(lines, weights):
        start = to_wall(cum / total_w * total_sung)
        cum += w
        end = to_wall(cum / total_w * total_sung)
        dur = min(max(end - start, MIN_LINE_S), MAX_LINE_S)
        out.append((start, start + dur, line))
    return out


def ts(seconds: float) -> str:
    seconds = max(0.0, seconds)
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h}:{m:02d}:{s:05.2f}"


ASS_HEAD = """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Lyric,Segoe UI Semibold,78,&H00FFE6EA,&H000000FF,&H0014060A,&H90000000,0,0,0,0,100,100,0,0,1,4.5,3,5,150,150,0,1
Style: Chorus,Segoe UI Semibold,80,&H006ECFFF,&H000000FF,&H0014060A,&H90000000,0,0,0,0,100,100,0,0,1,4.5,3,5,150,150,0,1
Style: Title,Segoe UI Semibold,58,&H00C2E32B,&H000000FF,&H0014060A,&H90000000,0,0,0,0,100,100,2,0,1,3.5,2,5,150,150,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def write_ass(path: Path, timed: list, title: str, artist: str) -> None:
    # A line the lyric repeats is almost always the hook. Colouring those
    # gold gives the video visible structure for free.
    counts: dict[str, int] = {}
    for _, _, line in timed:
        counts[line] = counts.get(line, 0) + 1
    rows = []
    first = timed[0][0] if timed else 3.0
    if first > 2.2:                       # room for a title card
        rows.append(f"Dialogue: 0,{ts(0.6)},{ts(first - 0.35)},Title,,0,0,0,,"
                    f"{{\\fad(500,400)}}{title}\\N{{\\fs38}}{artist}")
    for start, end, line in timed:
        text = line.replace("{", "(").replace("}", ")")
        style = "Chorus" if counts.get(line, 0) > 1 else "Lyric"
        rows.append(f"Dialogue: 0,{ts(start)},{ts(end)},{style},,0,0,0,,"
                    f"{{\\fad(220,220)}}{text}")
    path.write_text(ASS_HEAD + "\n".join(rows) + "\n", encoding="utf-8")


def render(cover: Path, audio: Path, ass: Path, out: Path) -> None:
    """Blurred, darkened cover art with a slow push in, lyrics burned over."""
    vf = (
        "[0:v]scale=1920:-1:force_original_aspect_ratio=increase,"
        "crop=1920:1080,boxblur=10:1,eq=brightness=-0.16:saturation=1.08:contrast=1.06,"
        "vignette=PI/4.2,"
        "zoompan=z='min(1+0.00006*on,1.10)':d=1:"
        "x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1920x1080:fps=25,"
        f"ass={ass.as_posix()}[v]"
    )
    cmd = ["ffmpeg", "-y", "-loop", "1", "-i", str(cover), "-i", str(audio),
           "-filter_complex", vf, "-map", "[v]", "-map", "1:a",
           "-c:v", "libx264", "-preset", "medium", "-crf", "20",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
           "-shortest", str(out)]
    proc = subprocess.run(cmd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        sys.exit("ffmpeg failed:\n" + (proc.stderr or "")[-2500:])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--audio", required=True)
    p.add_argument("--vocals", required=True)
    p.add_argument("--lyrics", required=True)
    p.add_argument("--cover", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--title", default="")
    p.add_argument("--artist", default="i C. infinity")
    p.add_argument("--timing", help="a timing.json to render instead of "
                   "computing timing here (list of line/start/end)")
    args = p.parse_args()

    lines = [l.strip() for l in
             Path(args.lyrics).read_text(encoding="utf-8").splitlines()
             if l.strip()]
    if args.timing:
        import json
        rows = json.loads(Path(args.timing).read_text(encoding="utf-8"))
        timed = [(r["start"], r["end"], r["line"]) for r in rows]
        print(f"  using supplied timing: {len(timed)} lines")
    else:
        blocks, duration = voiced_blocks(Path(args.vocals))
        sung = sum(b - a for a, b in blocks)
        print(f"  {len(lines)} lines, {len(blocks)} sung blocks, "
              f"{sung:.0f}s singing of {duration:.0f}s")
        timed = place_lines(lines, blocks)
    ass = Path(args.out).with_suffix(".ass")
    write_ass(ass, timed, args.title or Path(args.audio).stem, args.artist)
    print(f"  wrote {ass.name}; first line at {timed[0][0]:.1f}s, "
          f"last ends {timed[-1][1]:.1f}s")

    print("  rendering ...")
    render(Path(args.cover), Path(args.audio), ass, Path(args.out))
    print(f"  done -> {args.out}")


if __name__ == "__main__":
    main()
