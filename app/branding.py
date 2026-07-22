# -*- coding: utf-8 -*-
"""System tokenów wizualnych (kolory, typografia, promienie, cienie) i znak
graficzny kalkulatora — jedno źródło prawdy współdzielone przez `app.py`
(interfejs Streamlit) i `report_builder.py` (raport HTML/PDF), żeby oba
środowiska renderowania wyglądały identycznie.

Znak: sześciokątna plakietka z monogramem "K" (Kalkulator). Własny, oryginalny
symbol kalkulatora — NIE logo kancelarii KRS Guard (świadoma decyzja, patrz
plany/redesign-graficzny-i-raport-pdf-*.md). Budowany jako inline SVG (kod,
nie plik graficzny) — zero emoji, zero zależności od plików spoza repo, ostry
w każdym rozmiarze.

(22.07.2026) Poprzednia wersja znaku (tarcza z 3 rosnącymi słupkami)
zastąpiona tym monogramem po przeglądzie propozycji z użytkownikiem: motyw
"3 słupki = 4-stopniowa skala ryzyka" był niewidoczny dla klienta końcowego —
widział po prostu białą literę, bez dostępu do zamierzonego znaczenia. Nowy
znak to czysty monogram, oceniany wyłącznie na tym, co faktycznie widać.
Litera K jest rysowana W TYM SAMYM kolorze co reszta znaków dwukolorowych w
tym pliku ("bars" — patrz `logo_svg()`) — na jednolitym tle (granatowy
nagłówek / biały raport) efekt jest wizualnie nie do odróżnienia od
prawdziwego wycięcia w plakietce, bez potrzeby maski SVG (i bez odpowiednika
maski do budowania w PIL/reportlab).
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
    # (21.07.2026) Niebieska rodzina "notice/CTA" — spójny odcień dla banerów
    # informacyjnych (dawniej pomarańczowe) i dla boxa CTA na końcu raportu
    # (dawniej niemal czarny `ink`, wyglądał jak "żałobna klepsydra" — decyzja
    # użytkownika: jasny niebieski panel z granatowym tekstem i akcentem).
    # Współdzielone przez app.py (banery) i report_builder.py (box CTA).
    "notice_bg": "#eaf1f8",
    "notice_border": "#cbdcef",
}

# Mapowania kod ryzyka → kolor/tło pigułki — jedno źródło współdzielone przez
# app.py (Faza A, colored_risk_box) i report_builder.py (Faza B, raport
# PDF/HTML), żeby aplikacja i dokument wynikowy używały identycznych kolorów.
RISK_COLORS = {
    "RISK_LOW":    TOKENS["risk_low"],
    "RISK_MEDIUM": TOKENS["risk_medium"],
    "RISK_HIGH":   TOKENS["risk_high"],
    "RISK_URGENT": TOKENS["risk_urgent"],
}

RISK_BG = {
    "RISK_LOW":    TOKENS["risk_low_bg"],
    "RISK_MEDIUM": TOKENS["risk_medium_bg"],
    "RISK_HIGH":   TOKENS["risk_high_bg"],
    "RISK_URGENT": TOKENS["risk_urgent_bg"],
}

_LOGO_TEMPLATE = """<svg viewBox="0 0 32 32" width="{size}" height="{size}" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Znak kalkulatora ryzyka">
  <path d="M16 1.5 L28.56 8.75 L28.56 23.25 L16 30.5 L3.44 23.25 L3.44 8.75 Z" fill="{shield}"/>
  <rect x="10.6" y="6.3" width="3.6" height="19.4" rx="0.6" fill="{bars}"/>
  <polygon points="15.37,17.59 23.67,8.69 21.33,6.51 13.03,15.41" fill="{bars}"/>
  <polygon points="15.37,15.41 23.67,24.31 21.33,26.49 13.03,17.59" fill="{bars}"/>
</svg>"""


def logo_svg(size: int = 40, shield: str | None = None, bars: str | None = None) -> str:
    """Inline SVG znaku kalkulatora, w podanym rozmiarze i kolorach."""
    return _LOGO_TEMPLATE.format(
        size=size,
        shield=shield or TOKENS["navy"],
        bars=bars or TOKENS["paper"],
    )


def logo_svg_light_on_dark(size: int = 40) -> str:
    """Wariant do użycia na ciemnym (granatowym) tle nagłówka — jasna
    plakietka, granatowa litera K (na granatowym tle nagłówka efekt = litera
    "wtapia się" w tło, jak prawdziwe wycięcie)."""
    return logo_svg(size, shield=TOKENS["paper"], bars=TOKENS["navy"])


def logo_svg_dark_on_light(size: int = 40) -> str:
    """Wariant do użycia na jasnym tle (np. stopka raportu PDF) — granatowa
    plakietka, biała/papierowa litera K (na białym tle raportu efekt jak
    wyżej — litera wtapia się w otoczenie)."""
    return logo_svg(size, shield=TOKENS["navy"], bars=TOKENS["paper"])


def css_variables() -> str:
    """Blok `:root{--token:wartość}` generowany z `TOKENS` — jedno źródło dla
    CSS wstrzykiwanego w `app.py` i osadzanego w szablonie raportu."""
    lines = [f"  --{k.replace('_', '-')}: {v};" for k, v in TOKENS.items()]
    return ":root {\n" + "\n".join(lines) + "\n}"


# ─────────────────────────────────────────────────────────────────────────
# (21.07.2026) Monochromatyczne ikony SVG — zastępują emoji w banerach HTML
# (st.markdown), które nie przyjmują ikon Material Symbols (te są tylko w
# widgetach natywnych Streamlit: expander/przycisk/info — patrz app.py).
# Ta sama technika co logo: inline SVG budowany przez str.format, wstrzykiwany
# przez unsafe_allow_html. Ścieżki to standardowe ikony Material Symbols (24dp),
# jednokolorowe (fill), domyślnie w granacie — profesjonalny, "prawny"
# charakter zamiast kolorowych emoji. `d` bez własnego fill → dziedziczy z <svg>.
# ─────────────────────────────────────────────────────────────────────────
_ICON_PATHS = {
    # dokument z liniami tekstu (description)
    "document": "M14 2H6c-1.1 0-1.99.9-1.99 2L4 20c0 1.1.89 2 1.99 2H18c1.1 0 2-.9 2-2V8l-6-6zm2 16H8v-2h8v2zm0-4H8v-2h8v2zm-3-5V3.5L18.5 9H13z",
    # skaner dokumentów (document_scanner — dla pism ze skanu/OCR)
    "scan": "M4 5h2V3H4c-1.1 0-2 .9-2 2v2h2V5zm16-2h-2v2h2v2h2V5c0-1.1-.9-2-2-2zM4 19v-2H2v2c0 1.1.9 2 2 2h2v-2H4zm16 0h-2v2h2c1.1 0 2-.9 2-2v-2h-2v2zM7 7h1.5v10H7zm3 0h1v10h-1zm3 0h2v10h-2zm4 0h1v10h-1z",
    # aparat / obraz (photo_camera — dla dokumentu-zdjęcia)
    "photo": "M12 15.2a3.2 3.2 0 100-6.4 3.2 3.2 0 000 6.4zM9 2 7.17 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2h-3.17L15 2H9zm3 15c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5z",
    # tarcza z ptaszkiem (gpp_good — dokument wiarygodny/cyfrowy)
    "verified": "M12 1 3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4zm-2 16-4-4 1.41-1.41L10 14.17l6.59-6.59L18 9l-8 8z",
    # kłódka (lock — ochrona danych)
    "lock": "M18 8h-1V6c0-2.76-2.24-5-5-5S7 3.24 7 6v2H6c-1.1 0-2 .9-2 2v10c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V10c0-1.1-.9-2-2-2zM9 6c0-1.66 1.34-3 3-3s3 1.34 3 3v2H9V6zm3 11c-1.1 0-2-.9-2-2s.9-2 2-2 2 .9 2 2-.9 2-2 2z",
    # informacja (info)
    "info": "M11 7h2v2h-2zm0 4h2v6h-2zm1-9C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8z",
    # ostrzeżenie (warning triangle)
    "warning": "M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z",
    # lista kontrolna (fact_check — "zanim wgrasz")
    "checklist": "M20 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h15c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-9 14-4-4 1.41-1.41L11 14.17l5.59-5.59L18 10l-7 7z",
    # edycja (edit)
    "edit": "M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04c.39-.39.39-1.02 0-1.41l-2.34-2.34c-.39-.39-1.02-.39-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z",
}

_ICON_TEMPLATE = (
    '<svg viewBox="0 0 24 24" width="{size}" height="{size}" fill="{color}" '
    'xmlns="http://www.w3.org/2000/svg" aria-hidden="true" '
    'style="vertical-align:-0.18em;flex:none;display:inline-block">'
    '<path d="{path}"/></svg>'
)


def icon_svg(name: str, color: str | None = None, size: int = 18) -> str:
    """Inline SVG ikony monochromatycznej (Material Symbols 24dp) w podanym
    kolorze/rozmiarze — do banerów HTML w app.py. Domyślnie granat (`navy`).
    Nieznana nazwa → ikona `info` (bezpieczny fallback)."""
    path = _ICON_PATHS.get(name, _ICON_PATHS["info"])
    return _ICON_TEMPLATE.format(
        size=size, color=color or TOKENS["navy"], path=path
    )
