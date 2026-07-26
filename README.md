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

Local mode is not supported by older firmware versions. Firmware upgrades are rolled out gradually, 
contact info@invisible-computers.com for an expedited upgrade. 

## Protocol

The device wakes roughly every minute, connects to Wi-Fi, and makes one or two HTTP
GET requests against the configured base URL. **Use plain `http://`.** The firmware
ships a single trust anchor — the Invisible Computers root certificate — and no public
root certificates at all, so it cannot validate a normal HTTPS certificate: a
certificate from a public authority such as Let's Encrypt is rejected just like a
self-signed one. Since the traffic stays on your own network and carries no
credentials, plain HTTP is the intended setup.

### `GET <base>/render`

Some displays additionally include `?measured-temperature=<float>`.

Respond with either:

- **The full display buffer** (`width * height / 8` bytes, see below) — the device
  draws it, then calls `/ack`.
- **An empty body** — meaning "unchanged since the last confirmed render"; the device
  goes back to sleep without redrawing. 
  
Serving the buffer on every request works, but causes a visible full-screen refresh every wake cycle. 

To maximise long-term image quality of e-paper displays and prevent burn-in, 
make sure that a refresh is performed at least once a day.


If the display included a measured temperature in the url arguments, 
you may set the response header `Temperature-To-Assume`
(integer °C). E-Paper displays have temperature-dependent refresh protocols, 
the temperature you submit is the temperature that display refresh driver will assume. 
*By default, you can just mirror back the measured-temperature that the device submitted.*

A local device sends no authentication headers.

### `GET <base>/ack?software-version=<v>&device-type=<t>`

Called after a successful draw. **Implement this** — it is what tells your server the
render actually reached the panel, so it can treat that render as confirmed and start
returning empty bodies. A server that ignores acks keeps serving a full buffer on every
request, and the display does a visible full refresh every wake cycle.

It is a two-phase commit: if the device downloads a buffer but fails to draw it, it
never acks, and your server should serve the same buffer again.

This endpoint has an additional optional response header: 
`Reset-Device: true` makes the device erase its configuration (factory reset). 
Serve an all-white render first so the screen ends up
blank.


## Reference server

`server.py` implements the protocol for a PNG file on disk, re-reading it on every
request — overwrite the PNG to update the display.

```bash
pip install pillow numpy
python server.py image.png --device-type GDEY075T7 --port 8080
```

The image must exactly match the display resolution (e.g. 800×480). Any image mode
works; it is converted to 1-bit with a threshold.


## Buffer format

The body of a `/render` response is the raw e-paper buffer:

| Device type       | Identifier   | Resolution | Buffer size |
|-------------------|--------------|------------|-------------|
| 7.5 inch display  | `GDEY075T7`  | 800 × 480  | 48000 bytes |
| 10.2 inch display | `GDEM102T91` | 960 × 640  | 76800 bytes |

The identifier is what the device reports as `device-type` on `/ack`, and what
`server.py` expects for `--device-type`.

Starting from a 1-bit black/white image (white = 1):

1. **10.2 inch display only:** flip the image top-to-bottom.
2. Flatten to a pixel sequence in row-major order, then **reverse the whole sequence**.
3. Pack 8 pixels per byte, most significant bit first.

In Python: `numpy.packbits(numpy.flip(pixels) > 0).tobytes()` — see `server.py`.
The device rejects (and reboots on) any body whose size is neither 0 nor exactly the
buffer size.