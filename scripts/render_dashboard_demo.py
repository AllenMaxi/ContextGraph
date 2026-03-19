from __future__ import annotations

import shutil
import socket
import subprocess
import tempfile
import threading
import time
from pathlib import Path

import uvicorn

from contextgraph.config import Settings
from contextgraph.demo import seed_dashboard_demo
from contextgraph.service import ContextGraphService
from contextgraph.web import create_app

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "docs" / "assets"
MP4_PATH = ASSETS / "contextgraph-dashboard-demo.mp4"
GIF_PATH = ASSETS / "contextgraph-dashboard-demo.gif"


def wait_for_port(host: str, port: int, timeout: float = 10.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket() as sock:
            sock.settimeout(0.2)
            if sock.connect_ex((host, port)) == 0:
                return
        time.sleep(0.1)
    raise RuntimeError(f"Timed out waiting for server on {host}:{port}")


def ffmpeg_available() -> str:
    path = shutil.which("ffmpeg")
    if not path:
        raise RuntimeError("ffmpeg is required to render demo assets.")
    return path


def render_gif(ffmpeg_path: str, source_path: Path, target_path: Path) -> None:
    palette_path = target_path.with_suffix(".palette.png")
    subprocess.run(
        [
            ffmpeg_path,
            "-y",
            "-i",
            str(source_path),
            "-vf",
            "fps=12,scale=1280:-1:flags=lanczos,palettegen",
            str(palette_path),
        ],
        cwd=ROOT,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    subprocess.run(
        [
            ffmpeg_path,
            "-y",
            "-i",
            str(source_path),
            "-i",
            str(palette_path),
            "-filter_complex",
            "fps=12,scale=1280:-1:flags=lanczos[x];[x][1:v]paletteuse",
            str(target_path),
        ],
        cwd=ROOT,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    palette_path.unlink(missing_ok=True)


def main() -> None:
    ffmpeg_path = ffmpeg_available()
    try:
        from playwright.sync_api import sync_playwright
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Playwright is required. Install it first:\n"
            "pip install playwright && playwright install chromium"
        ) from exc

    host = "127.0.0.1"
    port = 8765
    base_url = f"http://{host}:{port}"

    service = ContextGraphService(app_settings=Settings(enable_payments=True, enable_claim_expiry_sweeps=False))
    demo = seed_dashboard_demo(service, base_url=base_url)
    app = create_app(service)

    config = uvicorn.Config(app, host=host, port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    wait_for_port(host, port)

    ASSETS.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="contextgraph_dashboard_video_") as tmp:
        video_dir = Path(tmp) / "videos"
        video_dir.mkdir(parents=True, exist_ok=True)

        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(
                    headless=True,
                    args=["--hide-scrollbars"],
                )
                context = browser.new_context(
                    viewport={"width": 1440, "height": 900},
                    record_video_dir=str(video_dir),
                    record_video_size={"width": 1440, "height": 900},
                    color_scheme="dark",
                )
                page = context.new_page()

                # --- Login as procurement-bot (same-org) ---
                page.goto(f"{base_url}/dashboard", wait_until="networkidle")
                page.wait_for_timeout(800)

                page.fill('input[name="api_key"]', demo.procurement_api_key)
                page.click('button[type="submit"]')
                page.wait_for_timeout(1500)

                # --- Overview page ---
                page.goto(f"{base_url}/dashboard/overview", wait_until="networkidle")
                page.wait_for_timeout(1500)

                # --- Knowledge page (claims, provenance, impact) ---
                page.goto(f"{base_url}/dashboard/knowledge", wait_until="networkidle")
                page.wait_for_timeout(1500)

                # --- Agents page ---
                page.goto(f"{base_url}/dashboard/agents", wait_until="networkidle")
                page.wait_for_timeout(1200)

                # --- Feed page ---
                page.goto(f"{base_url}/dashboard/feed", wait_until="networkidle")
                page.wait_for_timeout(1500)

                # --- Graph Explorer ---
                page.goto(f"{base_url}/dashboard/graph", wait_until="networkidle")
                page.wait_for_timeout(2000)

                # --- Notifications ---
                page.goto(f"{base_url}/dashboard/notifications", wait_until="networkidle")
                page.wait_for_timeout(1200)

                # --- Logout, login as globex (cross-org) ---
                page.goto(f"{base_url}/dashboard-logout", wait_until="networkidle")
                page.wait_for_timeout(800)

                page.fill('input[name="api_key"]', demo.globex_api_key)
                page.click('button[type="submit"]')
                page.wait_for_timeout(1500)

                # --- Overview as cross-org ---
                page.goto(f"{base_url}/dashboard/overview", wait_until="networkidle")
                page.wait_for_timeout(1500)

                # --- Feed as cross-org (locked content) ---
                page.goto(f"{base_url}/dashboard/feed", wait_until="networkidle")
                page.wait_for_timeout(2000)

                video = page.video
                page.close()
                context.close()
                browser.close()

                if video is None:
                    raise RuntimeError("Playwright did not produce a dashboard video.")

                webm_path = Path(video.path())
                subprocess.run(
                    [
                        ffmpeg_path,
                        "-y",
                        "-i",
                        str(webm_path),
                        "-vf",
                        "fps=30,scale=1440:-1:flags=lanczos",
                        "-c:v",
                        "libx264",
                        "-pix_fmt",
                        "yuv420p",
                        str(MP4_PATH),
                    ],
                    cwd=ROOT,
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                render_gif(ffmpeg_path, MP4_PATH, GIF_PATH)
        finally:
            server.should_exit = True
            thread.join(timeout=10)
            service.close()

    print(f"wrote {MP4_PATH}")
    print(f"wrote {GIF_PATH}")


if __name__ == "__main__":
    main()
