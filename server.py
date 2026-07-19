"""Minimal reference implementation of a local render server.

Serves a PNG file to an Invisible Computers display. The file is re-read on
every request, so just overwrite it to change what the display shows.

Usage:
    python server.py image.png --device-type GDEY075T7 --port 8080

Requires: pillow, numpy
"""

import argparse
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

import numpy
from PIL import Image

RESOLUTION_FROM_TYPE = {
    "GDEY075T7": (800, 480),
    "GDEM102T91": (960, 640),
}


def get_buffer(image_path: str, device_type: str) -> tuple[bytes, str]:
    """Convert the PNG to the packed 1-bit display buffer.

    Must match the backend's EPD.get_buffer exactly:
    1-bit image, GDEM102T91 flipped top-to-bottom, pixel order reversed,
    packed 8 pixels per byte MSB-first.
    Returns (buffer, hash-of-1bit-image) - the hash identifies the render.
    """
    image = Image.open(image_path).convert("1")
    if image.size != RESOLUTION_FROM_TYPE[device_type]:
        raise Exception(
            f"Image size {image.size} does not match "
            f"{device_type} {RESOLUTION_FROM_TYPE[device_type]}"
        )
    render_hash = hashlib.sha224(image.tobytes()).hexdigest()
    if device_type == "GDEM102T91":
        image = image.transpose(Image.FLIP_TOP_BOTTOM)
    pixels = numpy.asarray(image).ravel()  # row-major, same order as PIL getdata()
    pixels = numpy.flip(pixels)
    return numpy.packbits(pixels > 0).tobytes(), render_hash


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("image")
    parser.add_argument("--device-type", choices=RESOLUTION_FROM_TYPE, default="GDEY075T7")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()

    # Two-phase confirmation, like the backend: a render only counts as "seen"
    # once the device acks it, so a failed draw gets the buffer again.
    state = {"unconfirmed": None, "confirmed": None}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            url = urlparse(self.path)
            if url.path == "/render":
                buffer, render_hash = get_buffer(args.image, args.device_type)
                if render_hash == state["confirmed"]:
                    body = b""  # Unchanged: the device skips the redraw.
                else:
                    body = buffer
                    state["unconfirmed"] = render_hash
                self.send_response(200)
                if args.device_type == "GDEM102T91":
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

    print(f"Serving {args.image} for {args.device_type} on port {args.port}")
    HTTPServer(("0.0.0.0", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
