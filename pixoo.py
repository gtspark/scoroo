"""Minimal Pixoo 64 client.

Talks directly to the device's HTTP image API (Draw/SendHttpGif). We push raw
64x64 RGB frames rendered with Pillow. No third-party device lib so there are no
surprises on Python 3.13.
"""
import base64
import logging
import time

import requests

log = logging.getLogger("pixoo")

SIZE = 64


class Pixoo:
    """The Pixoo64's HTTP server is single-threaded, slow (~0.3-1.5s/push) and
    occasionally drops connections under load, so every command retries with a
    short backoff and uses split (connect, read) timeouts."""

    def __init__(self, host, connect_timeout=4, read_timeout=15, retries=3):
        self.url = f"http://{host}/post"
        self.timeout = (connect_timeout, read_timeout)
        self.retries = retries
        self._pic_id = 1
        self._session = requests.Session()
        self.reset_counter()

    def _command(self, payload):
        last = None
        for attempt in range(self.retries):
            try:
                r = self._session.post(self.url, json=payload, timeout=self.timeout)
                r.raise_for_status()
                try:
                    data = r.json()
                except ValueError:
                    return {}
                if data.get("error_code", 0) not in (0, None):
                    raise RuntimeError(f"Pixoo error: {data}")
                return data
            except Exception as e:  # noqa: BLE001
                last = e
                # give the device a moment to recover before retrying
                time.sleep(0.6 * (attempt + 1))
        raise last

    def reset_counter(self):
        """Reset the device-side GIF frame id. Call on start and whenever the
        counter drifts (the device silently ignores frames with a stale id)."""
        try:
            self._command({"Command": "Draw/ResetHttpGifId"})
            self._pic_id = 1
        except Exception as e:  # noqa: BLE001 - non-fatal, just log
            log.warning("reset_counter failed: %s", e)

    def set_brightness(self, pct):
        pct = max(0, min(100, int(pct)))
        self._command({"Command": "Channel/SetBrightness", "Brightness": pct})

    def push(self, img):
        """Push a Pillow image (will be coerced to 64x64 RGB) to the screen."""
        if img.mode != "RGB":
            img = img.convert("RGB")
        if img.size != (SIZE, SIZE):
            img = img.resize((SIZE, SIZE))
        data = base64.b64encode(img.tobytes()).decode("ascii")
        payload = {
            "Command": "Draw/SendHttpGif",
            "PicNum": 1,
            "PicWidth": SIZE,
            "PicOffset": 0,
            "PicID": self._pic_id,
            "PicSpeed": 1000,
            "PicData": data,
        }
        try:
            self._command(payload)
            self._pic_id += 1
            # The device's id space is finite; periodically reset to stay safe.
            if self._pic_id > 2_000_000_000:
                self.reset_counter()
        except Exception as e:  # noqa: BLE001
            log.warning("push failed (%s); resetting counter", e)
            self.reset_counter()
            raise
