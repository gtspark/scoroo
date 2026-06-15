"""Team logo sprites for the Pixoo.

Downloads ESPN team logos once (cached on disk), downscales them to the requested
pixel size, and caches the scaled result in memory. Returns None on any failure so
the renderer can fall back to a colored 2-letter crest.
"""
import hashlib
import io
import logging
import os

import requests
from PIL import Image

log = logging.getLogger("logos")

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "assets", "logos")
os.makedirs(CACHE, exist_ok=True)

_mem = {}      # (url, size) -> RGBA sprite or None
_raw = {}      # url -> full-res RGBA (or None)


def _raw_logo(url):
    if url in _raw:
        return _raw[url]
    if not url:
        _raw[url] = None
        return None
    path = os.path.join(CACHE, hashlib.md5(url.encode()).hexdigest() + ".png")
    try:
        if not os.path.exists(path):
            r = requests.get(url, timeout=12)
            r.raise_for_status()
            with open(path, "wb") as f:
                f.write(r.content)
        im = Image.open(path).convert("RGBA")
        _raw[url] = im
        return im
    except Exception as e:  # noqa: BLE001
        log.warning("logo fetch failed %s: %s", url, e)
        _raw[url] = None
        return None


def sprite(url, size):
    """RGBA logo scaled to size x size, or None if unavailable."""
    key = (url, size)
    if key in _mem:
        return _mem[key]
    raw = _raw_logo(url)
    s = None
    if raw is not None:
        try:
            s = raw.resize((size, size), Image.LANCZOS)
        except Exception as e:  # noqa: BLE001
            log.warning("logo resize failed: %s", e)
    _mem[key] = s
    return s
