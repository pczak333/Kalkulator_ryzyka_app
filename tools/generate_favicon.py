# -*- coding: utf-8 -*-
"""Generuje app/assets/favicon.png — rastrowa wersja znaku kalkulatora
(branding.py) na potrzeby st.set_page_config(page_icon=...), które nie zawsze
przyjmuje surowe SVG. Znak sam w sobie (inline SVG) żyje w branding.py i jest
używany bezpośrednio w nagłówku aplikacji i w raporcie PDF/HTML — ten skrypt
dotyczy WYŁĄCZNIE favicony karty przeglądarki.

Uruchomienie (jednorazowo, przy zmianie wyglądu znaku):
    python tools/generate_favicon.py
"""
from __future__ import annotations
import os
import sys
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))
from branding import TOKENS  # noqa: E402

_SCALE = 8  # render at 256x256, Streamlit/browsers downscale as needed
_SIZE = 32 * _SCALE


def _pt(x: float, y: float) -> tuple[float, float]:
    return (x * _SCALE, y * _SCALE)


def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))


def build_favicon() -> Image.Image:
    img = Image.new("RGBA", (_SIZE, _SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    shield_color = _hex_to_rgb(TOKENS["navy"])
    bar_color = _hex_to_rgb(TOKENS["paper"])

    # Poligonowe przybliżenie tarczy z branding.py (proste odcinki zamiast
    # krzywych Beziera — przy rozmiarze favicony różnica jest niewidoczna).
    shield_points = [
        _pt(16, 2), _pt(27, 6.4), _pt(27, 15), _pt(25, 20.5),
        _pt(21, 26), _pt(16, 29.8), _pt(11, 26), _pt(7, 20.5),
        _pt(5, 15), _pt(5, 6.4),
    ]
    draw.polygon(shield_points, fill=shield_color)

    bars = [
        (10.4, 17.4, 13.4, 23.6),
        (14.5, 13.4, 17.5, 23.6),
        (18.6, 9.4, 21.6, 23.6),
    ]
    for x0, y0, x1, y1 in bars:
        draw.rounded_rectangle(
            [_pt(x0, y0), _pt(x1, y1)], radius=1 * _SCALE, fill=bar_color
        )

    return img


if __name__ == "__main__":
    out_dir = os.path.join(os.path.dirname(__file__), "..", "app", "assets")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "favicon.png")
    build_favicon().save(out_path)
    print(f"Zapisano: {out_path}")
