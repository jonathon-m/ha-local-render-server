"""Minimal reference implementation of a local render server.

Serves an image to an Invisible Computers display. The source is re-read on
every request, so change the file (or the URL's response) to update the panel.

Usage:
    python server.py image.png --display 7_5_inch --port 8080
    python server.py --url http://192.168.1.10:8123/local/display.png --display 7_5_inch

Requires: pillow, numpy
"""

from __future__ import annotations

import argparse
import hashlib
import io
import os
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

import numpy
from PIL import Image

RESOLUTIONS = {
    "7_5_inch": (800, 480),
    "10_2_inch": (960, 640),
}

# The 10.2 inch panel is mounted upside down relative to the 7.5 inch one.
FLIPPED_DISPLAYS = {"10_2_inch"}

# Only the 10.2 inch display reports a measured temperature and expects one back.
DISPLAYS_WITH_TEMPERATURE_SENSOR = {"10_2_inch"}

HOME_ASSISTANT_URL_HINTS = ("homeassistant", "supervisor", "hassio")


def _headers(source: str, token: str | None) -> dict[str, str]:
    headers = {"User-Agent": "invisible-local-render-server"}
    resolved = token
    if not resolved and any(hint in source for hint in HOME_ASSISTANT_URL_HINTS):
        resolved = os.environ.get("SUPERVISOR_TOKEN")
    if resolved:
        headers["Authorization"] = f"Bearer {resolved}"
    return headers


def _open_image(source: str, token: str | None) -> Image.Image:
    if source.startswith(("http://", "https://")):
        request = urllib.request.Request(source, headers=_headers(source, token))
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = response.read()
        image = Image.open(io.BytesIO(payload))
        image.load()
        return image
    return Image.open(source)


def get_buffer(source: str, display: str, token: str | None = None) -> tuple[bytes, str]:
    """Convert the source image to the packed 1-bit display buffer.

    1-bit image, resized if needed, flipped top-to-bottom on some displays,
    pixel order reversed, packed 8 pixels per byte MSB-first.
    Returns (buffer, hash-of-1bit-image) - the hash identifies the render.
    """
    size = RESOLUTIONS[display]
    image = _open_image(source, token)
    if image.size != size:
        image = image.convert("L").resize(size, Image.Resampling.LANCZOS)
    image = image.convert("1")
    render_hash = hashlib.sha224(image.tobytes()).hexdigest()
    if display in FLIPPED_DISPLAYS:
        image = image.transpose(Image.FLIP_TOP_BOTTOM)
    pixels = numpy.asarray(image).ravel()  # row-major, same order as PIL getdata()
    pixels = numpy.flip(pixels)
    return numpy.packbits(pixels > 0).tobytes(), render_hash


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("image", nargs="?", help="PNG path (or use --url)")
    parser.add_argument("--url", help="HTTP(S) URL that returns a PNG or other image")
    parser.add_argument("--token", help="Bearer token sent when fetching --url")
    parser.add_argument("--display", choices=RESOLUTIONS, default="7_5_inch")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    source = args.url or args.image
    if not source:
        parser.error("provide an image path or --url")

    # Two-phase confirmation, like the backend: a render only counts as "seen"
    # once the device acks it, so a failed draw gets the buffer again.
    # last_* keeps the previous good frame if the URL/file cannot be read.
    state = {
        "unconfirmed": None,
        "confirmed": None,
        "last_buffer": None,
        "last_hash": None,
    }

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            url = urlparse(self.path)
            if url.path == "/health":
                self.send_response(200)
                self.send_header("Content-Length", "2")
                self.end_headers()
                self.wfile.write(b"ok")
            elif url.path == "/render":
                try:
                    buffer, render_hash = get_buffer(source, args.display, args.token)
                    state["last_buffer"] = buffer
                    state["last_hash"] = render_hash
                except (OSError, urllib.error.URLError, ValueError) as exc:
                    self.log_error("Failed to load image from %s: %s", source, exc)
                    if state["last_buffer"] is None:
                        buffer, render_hash = b"", None
                    else:
                        buffer, render_hash = state["last_buffer"], state["last_hash"]
                if render_hash is None or render_hash == state["confirmed"]:
                    body = b""  # Unchanged or unavailable: the device skips the redraw.
                else:
                    body = buffer
                    state["unconfirmed"] = render_hash
                self.send_response(200)
                if args.display in DISPLAYS_WITH_TEMPERATURE_SENSOR:
                    measured = parse_qs(url.query).get("measured-temperature", ["22"])[0]
                    self.send_header("Temperature-To-Assume", str(round(float(measured))))
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif url.path == "/ack":
                state["confirmed"] = state["unconfirmed"]
                self.send_response(200)
                self.send_header("Content-Length", "0")
                self.end_headers()
            else:
                self.send_error(404)

    print(f"Serving {source} for {args.display} on port {args.port}")
    HTTPServer(("0.0.0.0", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
