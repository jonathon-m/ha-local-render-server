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
GET requests against the configured base URL. **Use plain `http://`.** 
(The device uses HTTPS when in non-local cloud mode.)

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

The two query parameters describe the device's firmware version and panel hardware
model. They are informational — you can ignore them.

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

`server.py` converts an image to the panel buffer. Pass a PNG on disk, or a URL that
returns an image (re-fetched on every `/render`).

```bash
pip install pillow numpy
python server.py image.png --display 7_5_inch --port 8080
python server.py --url http://192.168.1.10:8123/local/display.png --display 7_5_inch
```

`--display` accepts `7_5_inch` or `10_2_inch`. `--token` sends a Bearer token when
fetching `--url`. Images that are not the exact panel size are resized.

The image is converted to 1-bit with dithering.

## Home Assistant OS

This repo is a Home Assistant add-on repository. The add-on lives in
`invisible_local_render/`.

### Install from GitHub

The repository must be **public**. Home Assistant clones it with no GitHub login.

1. Push this repo to GitHub. Change the `url` fields in `repository.yaml` and
   `invisible_local_render/config.yaml` to your repo if you want.
2. In Home Assistant: **Settings → Add-ons → Add-on Store → ⋮ → Repositories**.
3. Paste `https://github.com/<you>/<repo>` and add it.
4. Refresh the store, install **Invisible Local Render**, then start it.

Home Assistant builds the container on the machine (first install takes a few
minutes). After that, bump `version` in `invisible_local_render/config.yaml`
whenever you want the store to offer an update.

Private GitHub repos will not work unless you copy the `invisible_local_render`
folder onto the HAOS **addons** share instead.

### Configure

- **Image URL** — an HTTP endpoint that returns PNG/JPEG, for example
  `http://homeassistant:8123/local/display.png` for a file in `/config/www/`
- **Display size** — matching your panel
- **Bearer token** — only if the URL requires auth. Home Assistant `/api/` URLs
  (use `http://supervisor/core/api/...`) pick up the supervisor token automatically

Keep port **8080** published, and point the display at
`http://<home-assistant-lan-ip>:8080`.

## Buffer format

The body of a `/render` response is the raw e-paper buffer:

| Display           | Resolution | Buffer size |
|-------------------|------------|-------------|
| 7.5 inch display  | 800 × 480  | 48000 bytes |
| 10.2 inch display | 960 × 640  | 76800 bytes |

Starting from a 1-bit black/white image (white = 1):

1. **10.2 inch display only:** flip the image top-to-bottom.
2. Flatten to a pixel sequence in row-major order, then **reverse the whole sequence**.
3. Pack 8 pixels per byte, most significant bit first.

In Python: `numpy.packbits(numpy.flip(pixels) > 0).tobytes()` — see `server.py`.
The device rejects (and reboots on) any body whose size is neither 0 nor exactly the
buffer size.
