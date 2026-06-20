"""Screen capture and coordinate scaling for macOS (Retina-aware).

The hard part of computer use on a Mac is three coordinate spaces:

  1. logical points  — what pyautogui clicks in, e.g. 1512 x 982 (pyautogui.size()).
  2. physical pixels — what a screenshot actually contains on a Retina display,
                       e.g. 3024 x 1964 (2x). mss/Pillow capture in this space.
  3. model space     — the dimensions of the (downscaled) image we send to Claude,
                       which we also declare as display_width_px/display_height_px.
                       Claude returns click coordinates in THIS space.

This module captures in physical space, downscales to model space (to stay under the
model's image-size limit), and converts Claude's model-space coordinates back to the
logical points pyautogui needs to actually click.
"""
from __future__ import annotations

import base64
import io

import mss
import pyautogui
from PIL import Image

from .config import Config


class Screen:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.logical_w, self.logical_h = pyautogui.size()  # actuation space
        # Decide the model-image dimensions once, preserving the logical aspect ratio
        # and fitting the long edge under the configured target.
        long_edge = max(self.logical_w, self.logical_h)
        scale = min(1.0, cfg.effective_long_edge / long_edge)
        self.model_w = max(1, round(self.logical_w * scale))
        self.model_h = max(1, round(self.logical_h * scale))

    # ---- what the tool definition advertises to Claude ----
    @property
    def display_width_px(self) -> int:
        return self.model_w

    @property
    def display_height_px(self) -> int:
        return self.model_h

    # ---- capture ----
    def _grab_physical(self) -> Image.Image:
        """Full primary-display screenshot in physical pixels."""
        factory = getattr(mss, "MSS", None) or mss.mss  # MSS in mss>=10, mss() factory older
        with factory() as sct:
            mon = sct.monitors[1]  # [0] is the virtual union of all monitors; [1] is primary
            raw = sct.grab(mon)
        return Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")

    def capture_b64(self) -> str:
        """Full screen, downscaled to model dimensions, returned as base64 PNG."""
        img = self._grab_physical().resize((self.model_w, self.model_h), Image.LANCZOS)
        return _png_b64(img)

    def capture_region_b64(self, x1: int, y1: int, x2: int, y2: int) -> str:
        """Zoom: crop a model-space region from the FULL-resolution capture and
        return it at native detail (downscaled only if it still exceeds the limit).
        Lets Claude read small text it couldn't resolve in the full screenshot."""
        phys = self._grab_physical()
        # model space -> physical space
        sx = phys.width / self.model_w
        sy = phys.height / self.model_h
        box = (
            max(0, int(x1 * sx)), max(0, int(y1 * sy)),
            min(phys.width, int(x2 * sx)), min(phys.height, int(y2 * sy)),
        )
        crop = phys.crop(box)
        limit = self.cfg.image_long_edge_limit
        if max(crop.size) > limit:
            s = limit / max(crop.size)
            crop = crop.resize((max(1, int(crop.width * s)), max(1, int(crop.height * s))), Image.LANCZOS)
        return _png_b64(crop)

    # ---- coordinate mapping: model space -> logical points (for pyautogui) ----
    def to_logical(self, mx: float, my: float) -> tuple[int, int]:
        x = mx * self.logical_w / self.model_w
        y = my * self.logical_h / self.model_h
        # clamp into the screen so a slightly-off coordinate never escapes bounds
        x = min(max(0, x), self.logical_w - 1)
        y = min(max(0, y), self.logical_h - 1)
        return int(round(x)), int(round(y))


def _png_b64(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.standard_b64encode(buf.getvalue()).decode("ascii")
