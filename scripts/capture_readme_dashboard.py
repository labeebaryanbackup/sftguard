"""Capture the README viewer screenshot from the checked-in confirmatory artifact.

The script builds the static viewer, serves it only on loopback, and asks a
local Chromium browser for a fixed-size screenshot.  The companion receipt
binds the PNG to the exact evidence artifact used by the viewer.
"""

from __future__ import annotations

import argparse
import hashlib
import http.server
import json
import os
import shutil
import struct
import subprocess
import tempfile
import threading
from functools import partial
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
DIST = WEB / "dist"
EVIDENCE = ROOT / "evidence" / "v0.1.0-confirmatory.json"
OUTPUT = ROOT / "docs" / "assets" / "sftguard-confirmatory-dashboard.png"
RECEIPT = ROOT / "docs" / "assets" / "sftguard-confirmatory-dashboard.receipt.json"
VIEWPORT = (1440, 900)


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, _format: str, *_args: object) -> None:
        return


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _png_dimensions(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        raise ValueError(f"not a valid PNG: {path}")
    return struct.unpack(">II", data[16:24])


def _browser(override: str | None) -> Path:
    candidates = [
        override,
        os.environ.get("SFTGUARD_BROWSER"),
        shutil.which("google-chrome"),
        shutil.which("chromium"),
        shutil.which("chromium-browser"),
        shutil.which("chrome"),
        shutil.which("msedge"),
    ]
    if os.name == "nt":
        candidates.extend(
            [
                str(
                    Path(os.environ.get("PROGRAMFILES", ""))
                    / "Google/Chrome/Application/chrome.exe"
                ),
                str(
                    Path(os.environ.get("PROGRAMFILES(X86)", ""))
                    / "Google/Chrome/Application/chrome.exe"
                ),
                str(
                    Path(os.environ.get("LOCALAPPDATA", ""))
                    / "Google/Chrome/Application/chrome.exe"
                ),
                str(
                    Path(os.environ.get("PROGRAMFILES", ""))
                    / "Microsoft/Edge/Application/msedge.exe"
                ),
            ]
        )
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return Path(candidate)
    raise FileNotFoundError(
        "Chromium browser not found. Set SFTGUARD_BROWSER or pass --browser PATH."
    )


def _npm() -> str:
    executable = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    if not executable:
        raise FileNotFoundError("npm was not found on PATH")
    return executable


def _receipt() -> dict[str, object]:
    width, height = _png_dimensions(OUTPUT)
    return {
        "schema_version": "sftguard.readme-capture.v1",
        "source_artifact": EVIDENCE.relative_to(ROOT).as_posix(),
        "source_artifact_sha256": _sha256(EVIDENCE),
        "viewer_fixture": "default checked-in confirmatory evidence",
        "capture": OUTPUT.relative_to(ROOT).as_posix(),
        "capture_sha256": _sha256(OUTPUT),
        "viewport": {"width": width, "height": height, "device_scale_factor": 1},
        "network_boundary": "loopback-only static build",
    }


def _check() -> None:
    stored = json.loads(RECEIPT.read_text(encoding="utf-8"))
    expected = _receipt()
    if stored != expected:
        raise SystemExit("stale dashboard screenshot or capture receipt")
    viewport = expected.get("viewport")
    if (
        not isinstance(viewport, dict)
        or (
            viewport.get("width"),
            viewport.get("height"),
        )
        != VIEWPORT
    ):
        raise SystemExit("dashboard screenshot viewport is not the frozen README size")
    print("SFTGuard dashboard screenshot and source receipt are current.")


def _capture(browser: Path, *, skip_build: bool) -> None:
    if not skip_build:
        subprocess.run([_npm(), "run", "build"], cwd=WEB, check=True)
    if not (DIST / "index.html").is_file():
        raise SystemExit("web/dist is missing; run without --skip-build")

    handler = partial(_QuietHandler, directory=str(DIST))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(prefix="sftguard-browser-") as profile:
            url = f"http://127.0.0.1:{server.server_port}/"
            command = [
                str(browser),
                "--headless=new",
                "--disable-gpu",
                "--hide-scrollbars",
                "--run-all-compositor-stages-before-draw",
                "--virtual-time-budget=3000",
                f"--window-size={VIEWPORT[0]},{VIEWPORT[1]}",
                "--force-device-scale-factor=1",
                f"--user-data-dir={profile}",
                f"--screenshot={OUTPUT}",
                url,
            ]
            subprocess.run(command, check=True, capture_output=True, text=True)
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()

    if _png_dimensions(OUTPUT) != VIEWPORT:
        raise SystemExit(f"browser did not produce the frozen {VIEWPORT[0]}x{VIEWPORT[1]} viewport")
    RECEIPT.write_text(
        json.dumps(_receipt(), indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    print(f"wrote {OUTPUT.relative_to(ROOT)} sha256={_sha256(OUTPUT)}")
    print(f"wrote {RECEIPT.relative_to(ROOT)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--browser", help="path to a Chrome, Chromium, or Edge executable")
    parser.add_argument(
        "--skip-build", action="store_true", help="reuse an existing web/dist build"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify the PNG and receipt without launching a browser",
    )
    args = parser.parse_args()
    if args.check:
        _check()
    else:
        _capture(_browser(args.browser), skip_build=args.skip_build)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
