# Invisible Local Render

Points an Invisible Computers e-paper display at this add-on instead of the
cloud. The add-on fetches a PNG from a URL on your Home Assistant network,
converts it to the panel buffer, and serves `/render` and `/ack`.

## Configuration

- **Image URL** — HTTP endpoint that returns an image. Examples:
  - Local file in `/config/www`: `http://homeassistant:8123/local/display.png`
  - Camera snapshot: `http://supervisor/core/api/camera_proxy/camera.your_camera`
  - Any other LAN API that returns PNG/JPEG
- **Display size** — `7_5_inch` (800×480) or `10_2_inch` (960×640)
- **Bearer token** — optional. Leave empty for `/local/` files. For Home
  Assistant REST API URLs the add-on sends the supervisor token automatically.

Images that are not the exact panel size are resized.

## Device setup

1. Start this add-on and confirm port **8080** is mapped in the add-on Network
   settings.
2. On the display, use **Set up a local device** and enter
   `http://<home-assistant-lan-ip>:8080`.
3. Use plain HTTP, not HTTPS.

The display must already have firmware that supports local mode.
