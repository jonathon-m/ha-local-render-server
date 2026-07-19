# Local render server

Protocol documentation and reference implementation for serving Invisible Computers
displays from your own machine.

Invisible Computers displays can be pointed at a **local render server** instead of the
cloud backend. During device setup in the app, choose "Set up a local device" and enter
the base URL of your server (for example `http://192.168.1.50:8080`). From then on the
display fetches its pre-rendered frames exclusively from that URL — it never contacts
the backend, receives no over-the-air firmware updates, and needs no account.

To switch a device back to cloud mode, power-cycle it and run the normal setup again.

## Firmware requirement

Local mode requires firmware version **16** (GDEY075T7 calendar display) or **6**
(GDEM102T91 temperature display). The version is visible in the device's Bluetooth
name during setup (e.g. `INVISIBLE_GDEY075T7_V16`), and the app checks it for you.
Older devices must complete one normal (cloud) setup first — the device then updates
itself automatically, which can take a while. Power-cycle it afterwards and run setup
again. If it still shows as unsupported, contact support.

## Protocol

The device wakes roughly every minute, connects to Wi-Fi, and makes one or two HTTP
GET requests against the configured base URL. Plain `http://` is recommended; `https://`
only works with a certificate signed by the CA bundled in the firmware, so self-signed
certificates will not work.

### `GET <base>/render`

The temperature display appends `?measured-temperature=<float>`.

Respond with either:

- **The full display buffer** (`width * height / 8` bytes, see below) — the device
  draws it, then calls `/ack`.
- **An empty body** — meaning "unchanged since the last confirmed render"; the device
  goes back to sleep without redrawing. Serving the buffer on every request works, but
  causes a visible full-screen refresh every wake cycle.

For the temperature display you may set the response header `Temperature-To-Assume`
(integer °C); the device renders its temperature widget with that value.

The device sends `Authorization: Basic local` (a placeholder) and possibly a
`Token-Authorization` header. Ignore them.

### `GET <base>/ack?software-version=<v>&device-type=<t>`

Called after a successful draw. Use it to mark the last-served render as confirmed
(two-phase commit: if the device downloads a buffer but fails to draw it, it never
acks, and your server should serve the buffer again). The call is best-effort — the
device tolerates failures.

One response header is honored: `Reset-Device: true` makes the device erase its
configuration (factory reset). Serve an all-white render first so the screen ends up
blank. The `Software-Upgrade-Recommended` and `Device-Auth-Token` headers used by the
cloud backend are ignored in local mode.

## Buffer format

The body of a `/render` response is the raw e-paper buffer:

| Device type | Resolution | Buffer size |
|-------------|-----------|-------------|
| GDEY075T7   | 800 × 480 | 48000 bytes |
| GDEM102T91  | 960 × 640 | 76800 bytes |

Starting from a 1-bit black/white image (white = 1):

1. **GDEM102T91 only:** flip the image top-to-bottom.
2. Flatten to a pixel sequence in row-major order, then **reverse the whole sequence**.
3. Pack 8 pixels per byte, most significant bit first.

In Python: `numpy.packbits(numpy.flip(pixels) > 0).tobytes()` — see `server.py`.
The device rejects (and reboots on) any body whose size is neither 0 nor exactly the
buffer size.

## Reference server

`server.py` implements the protocol for a PNG file on disk, re-reading it on every
request — overwrite the PNG to update the display.

```bash
pip install pillow numpy
python server.py image.png --device-type GDEY075T7 --port 8080
```

The image must exactly match the display resolution (e.g. 800×480). Any image mode
works; it is converted to 1-bit with a threshold.
