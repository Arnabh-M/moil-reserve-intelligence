"""
MOIL Reserve Intelligence — Shared Raster Post-Processing Utilities
====================================================================
Presentation-only helpers applied to already-computed raster tiles (mock or
real GEE thumbnails) before they're saved for the frontend. Nothing here
touches pixel *values* or the underlying data pipeline — it only affects how
the exported PNG looks once placed on the MapLibre basemap.
"""

import numpy as np
from PIL import Image


def feather_edges(img: Image.Image, feather_px: int = 48) -> Image.Image:
    """
    Fades the alpha channel to 0 near the image's outer edges so a raster
    overlay blends into the basemap instead of showing a hard rectangular
    cut line. `feather_px` is the width of the fade band, in pixels, on
    each side.
    """
    img = img.convert("RGBA")
    w, h = img.size
    feather_px = max(0, min(feather_px, w // 2, h // 2))
    if feather_px == 0:
        return img

    arr = np.array(img).astype(np.float32)
    ramp = np.linspace(0.0, 1.0, feather_px, dtype=np.float32)

    fade = np.ones((h, w), dtype=np.float32)
    fade[:feather_px, :] *= ramp[:, None]
    fade[-feather_px:, :] *= ramp[::-1][:, None]
    fade[:, :feather_px] *= ramp[None, :]
    fade[:, -feather_px:] *= ramp[::-1][None, :]

    arr[:, :, 3] = arr[:, :, 3] * fade
    return Image.fromarray(arr.astype(np.uint8), mode="RGBA")
