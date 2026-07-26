"""Minimal reference implementation of a local render server.

Serves a PNG file to an Invisible Computers display. The file is re-read on
every request, so just overwrite it to change what the display shows.

Usage:
    python server.py image.png --display 7_5_inch --port 8080

Requires: pillow, numpy
"""

import argparse
import hashlib
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


def get_buffer(image_path: str, display: str) -> tuple[bytes, str]:
    """Convert the PNG to the packed 1-bit display buffer.

    1-bit image, flipped top-to-bottom on some displays, pixel order reversed,
    packed 8 pixels per byte MSB-first.
    Returns (buffer, hash-of-1bit-image) - the hash identifies the render.
    """
    image = Image.open(image_path).convert("1")
    if image.size != RESOLUTIONS[display]:
        raise Exception(
            f"Image size {image.size} does not match {display} {RESOLUTIONS[display]}"
        )
    render_hash = hashlib.sha224(image.tobytes()).hexdigest()
    if display in FLIPPED_DISPLAYS:
        image = image.transpose(Image.FLIP_TOP_BOTTOM)
    pixels = numpy.asarray(image).ravel()  # row-major, same order as PIL getdata()
    pixels = numpy.flip(pixels)
    return numpy.packbits(pixels > 0).tobytes(), render_hash


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("image")
    parser.add_argument("--display", choices=RESOLUTIONS, default="7_5_inch")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()

    # Two-phase confirmation, like the backend: a render only counts as "seen"
    # once the device acks it, so a failed draw gets the buffer again.
    state = {"unconfirmed": None, "confirmed": None}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            url = urlparse(self.path)
            if url.path == "/render":
                buffer, render_hash = get_buffer(args.image, args.display)
                if render_hash == state["confirmed"]:
                    body = b""  # Unchanged: the device skips the redraw.
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

    print(f"Serving {args.image} for {args.display} on port {args.port}")
    HTTPServer(("0.0.0.0", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
