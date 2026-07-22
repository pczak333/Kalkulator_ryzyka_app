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

    # Sześciokątna plakietka — dokładne wierzchołki z branding.py (kontur to
    # same proste odcinki, w odróżnieniu od poprzedniej tarczy nie trzeba już
    # przybliżać krzywej Beziera).
    hex_points = [
        _pt(16, 1.5), _pt(28.56, 8.75), _pt(28.56, 23.25),
        _pt(16, 30.5), _pt(3.44, 23.25), _pt(3.44, 8.75),
    ]
    draw.polygon(hex_points, fill=shield_color)

    # Monogram "K": trzon (zaokrąglony prostokąt) + dwa ramiona (poligony) —
    # te same współrzędne co SVG w branding.py.
    draw.rounded_rectangle(
        [_pt(10.6, 6.3), _pt(14.2, 25.7)], radius=0.6 * _SCALE, fill=bar_color
    )
    draw.polygon(
        [_pt(15.37, 17.59), _pt(23.67, 8.69), _pt(21.33, 6.51), _pt(13.03, 15.41)],
        fill=bar_color,
    )
    draw.polygon(
        [_pt(15.37, 15.41), _pt(23.67, 24.31), _pt(21.33, 26.49), _pt(13.03, 17.59)],
        fill=bar_color,
    )

    return img


if __name__ == "__main__":
    out_dir = os.path.join(os.path.dirname(__file__), "..", "app", "assets")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "favicon.png")
    build_favicon().save(out_path)
    print(f"Zapisano: {out_path}")
