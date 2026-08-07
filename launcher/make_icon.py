"""Draw the launcher icon: candlesticks in the app's own palette.

Regenerate with:  python launcher/make_icon.py
"""
from __future__ import annotations

import pathlib

from PIL import Image, ImageDraw

BACKGROUND = "#131722"
UP = "#26a69a"
DOWN = "#ef5350"

SIZE = 256
OUT = pathlib.Path(__file__).parent / "app.ico"

# (x centre, wick top, body top, body bottom, wick bottom) as fractions of the
# canvas, drawn large enough to still read at 16px.
CANDLES = [
    (0.17, 0.60, 0.68, 0.86, 0.92, UP),
    (0.39, 0.36, 0.44, 0.70, 0.78, UP),
    (0.61, 0.30, 0.38, 0.60, 0.68, DOWN),
    (0.83, 0.10, 0.18, 0.48, 0.56, UP),
]


def draw(size: int) -> Image.Image:
    image = Image.new("RGBA", (size, size), BACKGROUND)
    pen = ImageDraw.Draw(image)

    # Rounded corners read as an app tile rather than a pasted square.
    radius = int(size * 0.18)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, size - 1, size - 1], radius, fill=255)

    body_width = size * 0.13
    wick_width = max(1, int(size * 0.022))

    for x_fraction, wick_top, top, bottom, wick_bottom, colour in CANDLES:
        x = x_fraction * size
        pen.rectangle(
            [x - wick_width / 2, wick_top * size, x + wick_width / 2, wick_bottom * size],
            fill=colour,
        )
        pen.rectangle(
            [x - body_width / 2, top * size, x + body_width / 2, bottom * size],
            fill=colour,
        )

    image.putalpha(mask)
    return image


base = draw(SIZE)
base.save(OUT, sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
print(f"wrote {OUT}")
