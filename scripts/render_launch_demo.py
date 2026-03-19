from __future__ import annotations

import re
import shutil
import subprocess
import textwrap
from pathlib import Path

import imageio.v2 as imageio
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "docs" / "assets"
FONT_PATH = Path("/System/Library/Fonts/SFNSMono.ttf")
GIF_PATH = ASSETS / "contextgraph-demo.gif"
MP4_PATH = ASSETS / "contextgraph-demo.mp4"

WIDTH = 1440
HEIGHT = 912
PADDING_X = 56
PADDING_Y = 100
LINE_HEIGHT = 30
FONT_SIZE = 20
MAX_VISIBLE = 24  # lines visible at once (scroll window)

BACKGROUND = "#0B1220"
WINDOW = "#111827"
WINDOW_BAR = "#1F2937"
TEXT = "#E5E7EB"
MUTED = "#9CA3AF"
PROMPT = "#93C5FD"
SUCCESS = "#A7F3D0"
WARNING = "#FCA5A5"
SECTION = "#FBBF24"
SEPARATOR = "#4B5563"


def normalize_output(text: str) -> list[str]:
    text = re.sub(r"agt_[a-z0-9]+", "agt_research", text)
    text = re.sub(r"mem_[a-z0-9]+", "mem_priced", text)
    text = re.sub(r"clm_[a-z0-9]+", "clm_claim01", text)
    lines: list[str] = []
    for raw_line in text.splitlines():
        wrapped = textwrap.wrap(raw_line, width=90) or [""]
        lines.extend(wrapped)
    return lines


def line_color(line: str) -> str:
    if line.startswith("$ "):
        return PROMPT
    if line.startswith("=" * 10) or line.startswith("-" * 10):
        return SEPARATOR
    if "Provenance" in line or "Impact" in line or "Pattern" in line or "Payment" in line or "Demo complete" in line:
        if not line.startswith(" "):
            return SECTION
    if "payment required:" in line:
        return WARNING
    if "same-org feed content:" in line or "unlocked memory:" in line or "Demo complete" in line:
        return SUCCESS
    if line.startswith("agent_id:") or line.startswith("priced memory id:"):
        return MUTED
    if line.strip().startswith("["):
        return PROMPT
    if "quorum met: True" in line or "attestation count:" in line or "notifications:" in line:
        return SUCCESS
    if "quorum met: False" in line:
        return WARNING
    if "impact:" in line or "quorum required:" in line:
        return MUTED
    return TEXT


def draw_window(lines: list[str], command: str) -> Image.Image:
    image = Image.new("RGB", (WIDTH, HEIGHT), BACKGROUND)
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(str(FONT_PATH), FONT_SIZE)
    title_font = ImageFont.truetype(str(FONT_PATH), 18)

    draw.rounded_rectangle((28, 28, WIDTH - 28, HEIGHT - 28), radius=22, fill=WINDOW)
    draw.rounded_rectangle((28, 28, WIDTH - 28, 82), radius=22, fill=WINDOW_BAR)
    draw.ellipse((56, 52, 72, 68), fill="#F87171")
    draw.ellipse((84, 52, 100, 68), fill="#FBBF24")
    draw.ellipse((112, 52, 128, 68), fill="#34D399")
    draw.text((152, 46), "ContextGraph v0.3.0 — launch demo", fill=TEXT, font=title_font)

    draw.text((PADDING_X, PADDING_Y), command, fill=PROMPT, font=font)

    y = PADDING_Y + LINE_HEIGHT + 14
    for line in lines[-MAX_VISIBLE:]:
        draw.text((PADDING_X, y), line, fill=line_color(line), font=font)
        y += LINE_HEIGHT

    return image


def build_frames(lines: list[str]) -> tuple[list[Image.Image], list[float]]:
    command = "$ python3 examples/launch_demo.py"
    frames: list[Image.Image] = []
    durations: list[float] = []

    # Typing animation
    for idx in range(1, len(command) + 1, 2):
        frames.append(draw_window([], command[:idx]))
        durations.append(0.04)

    frames.append(draw_window([], command))
    durations.append(0.6)

    # Reveal lines progressively
    visible: list[str] = []
    for line in lines:
        visible.append(line)
        frames.append(draw_window(visible, command))

        # Section headers get a longer pause
        if line.startswith("=" * 10) or line.startswith("-" * 10):
            durations.append(0.6)
        elif line == "":
            durations.append(0.15)
        elif "Demo complete" in line:
            durations.append(1.0)
        else:
            durations.append(0.35)

    # Hold final frame
    for _ in range(15):
        frames.append(draw_window(visible, command))
        durations.append(0.16)

    return frames, durations


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["python3", "examples/launch_demo.py"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    lines = normalize_output(result.stdout.strip())
    frames, durations = build_frames(lines)

    imageio.mimsave(GIF_PATH, frames, duration=durations, loop=0)

    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        subprocess.run(
            [
                ffmpeg_path,
                "-y",
                "-i",
                str(GIF_PATH),
                "-movflags",
                "faststart",
                "-pix_fmt",
                "yuv420p",
                str(MP4_PATH),
            ],
            cwd=ROOT,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        fps = 12
        with imageio.get_writer(MP4_PATH, fps=fps, codec="libx264", quality=8) as writer:
            for frame, duration in zip(frames, durations, strict=True):
                repeat = max(1, round(duration * fps))
                frame_array = np.asarray(frame)
                for _ in range(repeat):
                    writer.append_data(frame_array)

    print(f"wrote {GIF_PATH}")
    print(f"wrote {MP4_PATH}")


if __name__ == "__main__":
    main()
