# -*- coding: utf-8 -*-
"""System tokenów wizualnych (kolory, typografia, promienie, cienie) i znak
graficzny kalkulatora — jedno źródło prawdy współdzielone przez `app.py`
(interfejs Streamlit) i `report_builder.py` (raport HTML/PDF), żeby oba
środowiska renderowania wyglądały identycznie.

Znak: stylizowana tarcza z trzema rosnącymi słupkami w środku — nawiązuje
wprost do 4-stopniowej skali ryzyka tego kalkulatora (niższe → średnie →
wysokie → pilne). Własny, oryginalny symbol kalkulatora — NIE logo kancelarii
KRS Guard (świadoma decyzja, patrz plany/redesign-graficzny-i-raport-pdf-*.md).
Budowany jako inline SVG (kod, nie plik graficzny) — zero emoji, zero
zależności od plików spoza repo, ostry w każdym rozmiarze.
"""

TOKENS = {
    "ink": "#0f1b2d",
    "navy": "#1a3a5c",
    "navy_light": "#2c5580",
    "paper": "#ffffff",
    "mist": "#f0f4f8",
    "mist_border": "#dbe4ee",
    "ink_muted": "#5b6b7d",
    "radius": "14px",
    "radius_sm": "8px",
    "shadow": "0 8px 24px rgba(15,27,45,0.08)",
    "font_display": (
        "Georgia, 'Iowan Old Style', 'Palatino Linotype', 'Book Antiqua', serif"
    ),
    "font_body": (
        "-apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
    ),
    "font_mono": "'SF Mono', 'Cascadia Code', Consolas, monospace",
    # Skala ryzyka celowo jako gradient nasilenia (zielony→bursztyn→czerwony→
    # ciemna czerwień) zamiast dotychczasowych niepowiązanych kolorów
    # (zielony/pomarańczowy/czerwony/fioletowy) — fiolet nie czyta się
    # intuicyjnie jako "poważniejszy niż czerwony"; ten gradient tak.
    "risk_low": "#1f7a4d",
    "risk_low_bg": "#eaf6ef",
    "risk_medium": "#b5750a",
    "risk_medium_bg": "#fbf1e0",
    "risk_high": "#a83232",
    "risk_high_bg": "#faeaea",
    "risk_urgent": "#6b1220",
    "risk_urgent_bg": "#f6e4e7",
}

_LOGO_TEMPLATE = """<svg viewBox="0 0 32 32" width="{size}" height="{size}" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Znak kalkulatora ryzyka">
  <path d="M16 2.2 L27 6.4 V15 C27 22.3 22.1 27.9 16 29.8 C9.9 27.9 5 22.3 5 15 V6.4 Z" fill="{shield}"/>
  <rect x="10.4" y="17.4" width="3" height="6.2" rx="1" fill="{bars}"/>
  <rect x="14.5" y="13.4" width="3" height="10.2" rx="1" fill="{bars}"/>
  <rect x="18.6" y="9.4" width="3" height="14.2" rx="1" fill="{bars}"/>
</svg>"""


def logo_svg(size: int = 40, shield: str | None = None, bars: str | None = None) -> str:
    """Inline SVG znaku kalkulatora, w podanym rozmiarze i kolorach."""
    return _LOGO_TEMPLATE.format(
        size=size,
        shield=shield or TOKENS["navy"],
        bars=bars or TOKENS["paper"],
    )


def logo_svg_light_on_dark(size: int = 40) -> str:
    """Wariant do użycia na ciemnym (granatowym) tle nagłówka — jasna tarcza,
    granatowe słupki dla kontrastu."""
    return logo_svg(size, shield=TOKENS["paper"], bars=TOKENS["navy"])


def logo_svg_dark_on_light(size: int = 40) -> str:
    """Wariant do użycia na jasnym tle (np. stopka raportu PDF) — granatowa
    tarcza, białe słupki."""
    return logo_svg(size, shield=TOKENS["navy"], bars=TOKENS["paper"])


def css_variables() -> str:
    """Blok `:root{--token:wartość}` generowany z `TOKENS` — jedno źródło dla
    CSS wstrzykiwanego w `app.py` i osadzanego w szablonie raportu."""
    lines = [f"  --{k.replace('_', '-')}: {v};" for k, v in TOKENS.items()]
    return ":root {\n" + "\n".join(lines) + "\n}"
