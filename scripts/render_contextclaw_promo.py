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
GIF_PATH = ASSETS / "contextclaw-promo.gif"
MP4_PATH = ASSETS / "contextclaw-promo.mp4"

WIDTH = 1080
HEIGHT = 1920
WINDOW_WIDTH = 948
WINDOW_HEIGHT = 1120
WINDOW_X = (WIDTH - WINDOW_WIDTH) // 2
WINDOW_Y = 300
PADDING_X = WINDOW_X + 42
PADDING_Y = WINDOW_Y + 88
LINE_HEIGHT = 32
FONT_SIZE = 22
MAX_VISIBLE = 26

BACKGROUND_TOP = "#08111F"
BACKGROUND_BOTTOM = "#132A1C"
WINDOW = "#0F172A"
WINDOW_BAR = "#1E293B"
TEXT = "#E2E8F0"
MUTED = "#94A3B8"
PROMPT = "#7DD3FC"
SUCCESS = "#86EFAC"
WARNING = "#FCA5A5"
SECTION = "#FDE68A"
ACCENT = "#67E8F9"
SEPARATOR = "#334155"


def normalize_output(text: str) -> list[str]:
    text = re.sub(r"/var/folders/[^ ]+", "/workspace", text)
    text = re.sub(r"/tmp/contextclaw_promo_[^/]+", "/workspace", text)
    text = re.sub(r"/private/tmp/contextclaw_promo_[^/]+", "/workspace", text)
    lines: list[str] = []
    for raw_line in text.splitlines():
        wrapped = textwrap.wrap(raw_line, width=58) or [""]
        lines.extend(wrapped)
    return lines


def line_color(line: str) -> str:
    if line.startswith("$ "):
        return PROMPT
    if line.startswith("[tool]"):
        return ACCENT
    if line.startswith("[result]"):
        return SUCCESS
    if line.startswith("[ContextGraph]"):
        return SUCCESS
    if line.startswith("=========="):
        return SECTION
    if line.startswith("workspace:"):
        return MUTED
    if "blocked" in line.lower():
        return WARNING
    if line.startswith("Assistant:"):
        return TEXT
    if line.startswith("Research agent:") or line.startswith("Coder agent:") or line.startswith("Memory agent:"):
        return SECTION
    return TEXT


def draw_background(draw: ImageDraw.ImageDraw) -> None:
    for y in range(HEIGHT):
        blend = y / HEIGHT
        top = (8, 17, 31)
        bottom = (19, 42, 28)
        r = int(top[0] * (1 - blend) + bottom[0] * blend)
        g = int(top[1] * (1 - blend) + bottom[1] * blend)
        b = int(top[2] * (1 - blend) + bottom[2] * blend)
        draw.line((0, y, WIDTH, y), fill=(r, g, b))


def draw_window(lines: list[str], command: str) -> Image.Image:
    image = Image.new("RGB", (WIDTH, HEIGHT), BACKGROUND_TOP)
    draw = ImageDraw.Draw(image)
    mono = ImageFont.truetype(str(FONT_PATH), FONT_SIZE)
    title_font = ImageFont.truetype(str(FONT_PATH), 30)
    subtitle_font = ImageFont.truetype(str(FONT_PATH), 19)

    draw_background(draw)
    draw.text((92, 110), "ContextClaw", fill=TEXT, font=title_font)
    draw.text((92, 154), "Agents with MCP, delegation, checkpoints, and memory", fill=MUTED, font=subtitle_font)
    draw.rounded_rectangle(
        (WINDOW_X, WINDOW_Y, WINDOW_X + WINDOW_WIDTH, WINDOW_Y + WINDOW_HEIGHT),
        radius=28,
        fill=WINDOW,
    )
    draw.rounded_rectangle(
        (WINDOW_X, WINDOW_Y, WINDOW_X + WINDOW_WIDTH, WINDOW_Y + 58),
        radius=28,
        fill=WINDOW_BAR,
    )
    draw.ellipse((WINDOW_X + 28, WINDOW_Y + 20, WINDOW_X + 42, WINDOW_Y + 34), fill="#FB7185")
    draw.ellipse((WINDOW_X + 54, WINDOW_Y + 20, WINDOW_X + 68, WINDOW_Y + 34), fill="#FBBF24")
    draw.ellipse((WINDOW_X + 80, WINDOW_Y + 20, WINDOW_X + 94, WINDOW_Y + 34), fill="#34D399")
    draw.text((WINDOW_X + 126, WINDOW_Y + 16), "TikTok promo demo", fill=TEXT, font=subtitle_font)

    draw.text((PADDING_X, PADDING_Y), command, fill=PROMPT, font=mono)
    y = PADDING_Y + 48
    for line in lines[-MAX_VISIBLE:]:
        draw.text((PADDING_X, y), line, fill=line_color(line), font=mono)
        y += LINE_HEIGHT

    footer = "ContextClaw runs the agents. ContextGraph shares the memory."
    draw.text((92, 1520), footer, fill=TEXT, font=subtitle_font)
    draw.text((92, 1560), "MCP • Task delegation • Checkpoints • Complementary memory", fill=MUTED, font=subtitle_font)
    return image


def build_frames(lines: list[str]) -> tuple[list[Image.Image], list[float]]:
    command = "$ python3 examples/contextclaw_promo.py"
    frames: list[Image.Image] = []
    durations: list[float] = []

    for idx in range(1, len(command) + 1, 2):
        frames.append(draw_window([], command[:idx]))
        durations.append(0.035)

    frames.append(draw_window([], command))
    durations.append(0.6)

    visible: list[str] = []
    for line in lines:
        visible.append(line)
        frames.append(draw_window(visible, command))
        if line.startswith("=========="):
            durations.append(0.55)
        elif line.startswith("[tool]") or line.startswith("[ContextGraph]"):
            durations.append(0.45)
        elif "ContextClaw + ContextGraph" in line:
            durations.append(1.1)
        elif not line:
            durations.append(0.12)
        else:
            durations.append(0.28)

    for _ in range(18):
        frames.append(draw_window(visible, command))
        durations.append(0.15)

    return frames, durations


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["python3", "examples/contextclaw_promo.py"],
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
