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


def chromium_available() -> str:
    candidates = [
        Path("/tmp/contextgraph_browsers/chromium-1208/chrome-mac/Chromium.app/Contents/MacOS/Chromium"),
        Path(
            "/tmp/contextgraph_browsers/chromium-1208/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"
        ),
        Path(
            "/tmp/contextgraph_browsers/chromium_headless_shell-1208/chrome-headless-shell-mac-arm64/chrome-headless-shell"
        ),
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    raise RuntimeError(
        "Chromium for Playwright is not installed. Run:\n"
        "PLAYWRIGHT_BROWSERS_PATH=/tmp/contextgraph_browsers PYTHONPATH=/tmp/contextgraph_video_deps python3 -m playwright install chromium"
    )


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
    chromium_path = chromium_available()
    try:
        from playwright.sync_api import sync_playwright
    except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(
            "Playwright is required. Install it first, for example:\n"
            "PYTHONPATH=/tmp/contextgraph_video_deps python3 -m pip install --target /tmp/contextgraph_video_deps playwright"
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
                    executable_path=chromium_path,
                    args=["--hide-scrollbars"],
                )
                context = browser.new_context(
                    viewport={"width": 1440, "height": 900},
                    record_video_dir=str(video_dir),
                    record_video_size={"width": 1440, "height": 900},
                    color_scheme="dark",
                )
                page = context.new_page()

                page.goto(f"{base_url}/console", wait_until="networkidle")
                page.wait_for_timeout(600)

                page.fill("#api_key", demo.procurement_api_key)
                page.click("button[type=submit]")
                page.wait_for_timeout(1200)

                page.click('a[data-page="overview"]')
                page.wait_for_timeout(1200)
                page.locator(".mini-card", has_text="TSMC semiconductor lead times").click()
                page.wait_for_timeout(1100)
                page.click("#panel-close")
                page.wait_for_timeout(400)

                page.click('a[data-page="agents"]')
                page.wait_for_timeout(1000)

                page.click('a[data-page="feed"]')
                page.wait_for_timeout(1000)
                page.locator(".card", has_text="TSMC semiconductor lead times").click()
                page.wait_for_timeout(1200)
                page.click("#panel-close")
                page.wait_for_timeout(500)

                page.goto(f"{base_url}/console/logout", wait_until="networkidle")
                page.wait_for_timeout(1000)

                page.fill("#api_key", demo.globex_api_key)
                page.click("button[type=submit]")
                page.wait_for_timeout(1200)

                page.click('a[data-page="overview"]')
                page.wait_for_timeout(1200)
                page.locator(".mini-card", has_text="Premium semiconductor supplier analysis").click()
                page.wait_for_timeout(1300)
                page.click("#panel-close")
                page.wait_for_timeout(500)

                page.click('a[data-page="feed"]')
                page.wait_for_timeout(900)
                page.locator(".card", has_text="Premium semiconductor supplier analysis").click()
                page.wait_for_timeout(1800)

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
