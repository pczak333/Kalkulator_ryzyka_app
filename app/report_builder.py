# -*- coding: utf-8 -*-
"""Buduje raport wyniku z gotowego słownika `text_builder.build()` — podgląd
HTML (osadzany na stronie przez `st.components.v1.html`) i plik PDF do
pobrania. Oba renderery czerpią z TYCH SAMYCH danych i tokenów wizualnych
(`branding.py`), więc mimo osobnego kodu renderującego wyglądają jak ta sama
tożsamość wizualna.

DECYZJA TECHNICZNA (16.07.2026): pierwotny plan zakładał JEDEN wspólny
szablon HTML+CSS konwertowany do PDF (WeasyPrint). Po testach lokalnych
zmieniona na DWA niezależne renderery:
- WeasyPrint wymaga natywnych bibliotek systemowych (Pango/Cairo/GDK-Pixbuf),
  niedostępnych na tym Windowsie bez dodatkowej instalacji — `pip install`
  się udaje, ale `import weasyprint` rzuca OSError przy ładowaniu DLL.
- xhtml2pdf (czysty Python, rozważany jako alternatywa) INSTALUJE się i
  DZIAŁA, ale jego obsługa `@font-face`/rejestracji czcionek jest
  niewiarygodna — w teście polskie znaki diakrytyczne (ą/ć/ę/ł/ń/ó/ś/ź/ż)
  renderowały się jako puste kwadraty (zweryfikowane WIZUALNIE, renderując
  stronę PDF jako obraz — nie tylko przez ekstrakcję tekstu, która osobno
  też była błędna). Nie do zaakceptowania dla polskiego dokumentu prawnego.
- Surowy reportlab z bezpośrednio zarejestrowanym fontem TTF (DejaVu Sans/
  Serif, dołączone w `app/assets/fonts/`, MIT/Bitstream-podobna licencja
  pozwalająca na redystrybucję — patrz `app/assets/fonts/LICENSE.txt`)
  renderuje polskie znaki poprawnie — zweryfikowane tym samym sposobem
  (render strony jako obraz, wizualna inspekcja). DejaVu wybrane, bo ma
  PEŁNE pokrycie Latin Extended-A (w odróżnieniu od np. Bitstream Vera,
  dołączonego do samego reportlab, które tego pokrycia NIE ma — sprawdzone
  tym samym testem, litery ą/ę/ł/ń/ś/ź/ż wyszły jako puste kwadraty).

Znak graficzny (plakietka + monogram K, od 22.07.2026 — patrz branding.py)
narysowany natywnie w reportlab (`_logo_drawing`, te same współrzędne co SVG
w `branding.py`/PNG w `tools/generate_favicon.py`) — reportlab nie renderuje
SVG bez dodatkowej zależności (svglib), a to tylko kilka prostych kształtów,
niewartych nowej zależności.
"""
from __future__ import annotations
import html
import io
import os
import re
from datetime import date

from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)
from reportlab.graphics.shapes import Drawing, Polygon, Rect

from branding import TOKENS, RISK_COLORS, RISK_BG, logo_svg_light_on_dark, css_variables

_FONT_DIR = os.path.join(os.path.dirname(__file__), "assets", "fonts")
_FONTS_REGISTERED = False


def _ensure_fonts() -> None:
    """Rejestruje fonty DejaVu w reportlab (raz na proces). Bez tego
    reportlab spada na wbudowany Helvetica, który nie ma polskich znaków
    diakrytycznych."""
    global _FONTS_REGISTERED
    if _FONTS_REGISTERED:
        return
    pdfmetrics.registerFont(TTFont("DejaVuSans", os.path.join(_FONT_DIR, "DejaVuSans.ttf")))
    pdfmetrics.registerFont(TTFont("DejaVuSans-Bold", os.path.join(_FONT_DIR, "DejaVuSans-Bold.ttf")))
    pdfmetrics.registerFont(TTFont("DejaVuSerif", os.path.join(_FONT_DIR, "DejaVuSerif.ttf")))
    pdfmetrics.registerFont(TTFont("DejaVuSerif-Bold", os.path.join(_FONT_DIR, "DejaVuSerif-Bold.ttf")))
    _FONTS_REGISTERED = True


_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")


def markup_bold(text: str) -> str:
    """Tekst z **pogrubieniami** markdown → znacznik `<b>`, rozumiany
    zarówno przez przeglądarkę (HTML), jak i mini-markup `reportlab.
    Paragraph` (PDF) — jedno miejsce współdzielone przez oba renderery.
    Publiczna (nie `_markup`) — reużywana też w app.py dla zajawki wyniku
    (`output["lead"]` zawiera markdown **pogrubienia**, ale zajawka jest
    wstrzykiwana jako surowy HTML przez `unsafe_allow_html=True`, który NIE
    interpretuje składni markdown — bez tej konwersji gwiazdki wychodziły
    dosłownie na ekranie)."""
    escaped = html.escape(text, quote=False)
    return _BOLD_RE.sub(r"<b>\1</b>", escaped)


def _body_paragraphs(output: dict) -> list[str]:
    """Akapity do niezależnego renderowania, wyciągnięte z gotowego
    `output['full_text']` (już złożonego i zsanityzowanego przez
    `text_builder.build()`) — bez ponownego odtwarzania logiki składania
    sekcji. Usuwa nagłówek `### ...` (pigułka ryzyka już go pokazuje osobno)
    oraz akapity CTA/zastrzeżenia (renderowane osobno, wyróżnione)."""
    parts = [p.strip() for p in (output.get("full_text") or "").split("\n\n") if p.strip()]
    cta_norm = (output.get("cta") or "").strip()
    disclaimer_norm = (output.get("disclaimer") or "").strip()
    result = []
    for p in parts:
        if p.startswith("### "):
            continue
        if p == cta_norm:
            continue
        if p.startswith("---") or (disclaimer_norm and disclaimer_norm in p):
            continue
        result.append(p)
    return result


# ── Podgląd HTML (st.components.v1.html) ────────────────────────────────────

def build_report_html(output: dict, risk_code: str) -> str:
    risk_label = output.get("risk_label", "")
    color = RISK_COLORS.get(risk_code, TOKENS["navy"])
    bg = RISK_BG.get(risk_code, TOKENS["mist"])
    today = date.today().strftime("%d.%m.%Y")

    body_html = "\n".join(f"<p>{markup_bold(p)}</p>" for p in _body_paragraphs(output))

    epu_html = ""
    if output.get("epu_block_text"):
        heading = output.get("epu_block_heading") or "Dodatkowa informacja: EPU / e-Sąd"
        epu_html = (
            f'<div class="kg-report-box"><h3>{html.escape(heading)}</h3>'
            f'<p>{markup_bold(output["epu_block_text"])}</p>'
        )
        if output.get("epu_block_disclaimer"):
            epu_html += f'<p class="kg-report-muted">{markup_bold(output["epu_block_disclaimer"])}</p>'
        epu_html += "</div>"

    cta_html = ""
    if output.get("cta"):
        cta_html = f'<div class="kg-report-cta"><p>{markup_bold(output["cta"])}</p></div>'

    return f"""<!doctype html>
<html lang="pl"><head><meta charset="utf-8">
<style>
{css_variables()}
* {{ box-sizing: border-box; }}
body {{ font-family: var(--font-body); color: var(--ink); background: var(--paper); margin: 0; }}
.kg-report {{ max-width: 720px; margin: 0 auto; padding: 28px 26px 40px; }}
.kg-report-header {{ background: var(--navy); border-radius: var(--radius); padding: 22px 26px;
  display: flex; align-items: center; gap: 16px; margin-bottom: 22px; }}
.kg-report-header h1 {{ color: #fff; font-family: var(--font-display); font-size: 1.25rem; margin: 0 0 2px; }}
.kg-report-header p {{ color: var(--mist); margin: 0; font-size: 0.8rem; opacity: .85; }}
.kg-report-pill {{ display: inline-block; background: {bg}; color: {color}; border: 1.5px solid {color}33;
  padding: 9px 18px; border-radius: 999px; font-weight: 700; font-size: 1rem; margin-bottom: 18px; }}
.kg-report p {{ line-height: 1.6; font-size: 0.95rem; margin: 0 0 13px; }}
.kg-report-box {{ background: var(--mist); border: 1px solid var(--mist-border); border-radius: var(--radius-sm);
  padding: 15px 18px; margin: 18px 0; }}
.kg-report-box h3 {{ font-family: var(--font-display); margin: 0 0 7px; font-size: 1rem; color: var(--ink); }}
.kg-report-muted {{ color: var(--ink-muted); font-size: 0.82rem; }}
.kg-report-cta {{ background: var(--notice-bg); border: 1px solid var(--notice-border);
  border-left: 4px solid var(--navy); border-radius: var(--radius-sm); padding: 16px 20px; margin: 22px 0 14px; }}
.kg-report-cta p {{ margin: 0; color: var(--ink); font-weight: 600; }}
.kg-report-footer {{ border-top: 2px solid var(--mist-border); margin-top: 24px; padding-top: 14px;
  color: var(--ink); font-size: 0.9rem; line-height: 1.5; }}
.kg-report-footer b {{ color: var(--ink); }}
</style></head>
<body>
<div class="kg-report">
  <div class="kg-report-header">
    {logo_svg_light_on_dark(38)}
    <div>
      <h1>KRS Guard — Kalkulator Ryzyka Prawnego</h1>
      <p>Raport oceny ryzyka &middot; wygenerowano {today}</p>
    </div>
  </div>
  <div class="kg-report-pill">{html.escape(risk_label)}</div>
  {body_html}
  {epu_html}
  {cta_html}
  <div class="kg-report-footer">{markup_bold(output.get("disclaimer", ""))}</div>
</div>
</body></html>"""


# ── PDF (reportlab) ──────────────────────────────────────────────────────────

def _logo_drawing(size: float, shield_hex: str, bar_hex: str) -> Drawing:
    """Znak kalkulatora (plakietka z monogramem K) narysowany natywnie w
    reportlab — te same współrzędne (viewBox 0-32) co SVG w `branding.py`/PNG
    w `tools/generate_favicon.py`. Kontur plakietki to sześciokąt (proste
    odcinki, bez przybliżania krzywych)."""
    scale = size / 32.0
    d = Drawing(size, size)

    def flip(x: float, y: float) -> tuple[float, float]:
        return x * scale, size - y * scale  # SVG y rośnie w dół, reportlab w górę

    hex_pts: list[float] = []
    for x, y in [(16, 1.5), (28.56, 8.75), (28.56, 23.25),
                 (16, 30.5), (3.44, 23.25), (3.44, 8.75)]:
        px, py = flip(x, y)
        hex_pts.extend([px, py])
    d.add(Polygon(hex_pts, fillColor=HexColor(shield_hex), strokeColor=None))

    stem_x0, stem_y0, stem_x1, stem_y1 = 10.6, 6.3, 14.2, 25.7
    rx, ry = stem_x0 * scale, size - stem_y1 * scale
    d.add(Rect(rx, ry, (stem_x1 - stem_x0) * scale, (stem_y1 - stem_y0) * scale,
                fillColor=HexColor(bar_hex), strokeColor=None,
                rx=0.6 * scale, ry=0.6 * scale))

    for arm in [[(15.37, 17.59), (23.67, 8.69), (21.33, 6.51), (13.03, 15.41)],
                [(15.37, 15.41), (23.67, 24.31), (21.33, 26.49), (13.03, 17.59)]]:
        arm_pts: list[float] = []
        for x, y in arm:
            px, py = flip(x, y)
            arm_pts.extend([px, py])
        d.add(Polygon(arm_pts, fillColor=HexColor(bar_hex), strokeColor=None))

    return d


def build_report_pdf(output: dict, risk_code: str) -> bytes:
    _ensure_fonts()

    navy = HexColor(TOKENS["navy"])
    ink = HexColor(TOKENS["ink"])
    ink_muted = HexColor(TOKENS["ink_muted"])
    mist = HexColor(TOKENS["mist"])
    mist_border = HexColor(TOKENS["mist_border"])
    notice_bg = HexColor(TOKENS["notice_bg"])
    notice_border = HexColor(TOKENS["notice_border"])
    risk_color = HexColor(RISK_COLORS.get(risk_code, TOKENS["navy"]))
    risk_bg = HexColor(RISK_BG.get(risk_code, TOKENS["mist"]))

    st_h1 = ParagraphStyle("h1", fontName="DejaVuSerif-Bold", fontSize=14.5,
                            leading=17, textColor=colors.white)
    st_sub = ParagraphStyle("sub", fontName="DejaVuSans", fontSize=8.3,
                             leading=12, textColor=HexColor(TOKENS["mist"]))
    st_pill = ParagraphStyle("pill", fontName="DejaVuSans-Bold", fontSize=12,
                              leading=15, textColor=risk_color)
    st_body = ParagraphStyle("body", fontName="DejaVuSans", fontSize=10,
                              leading=15, textColor=ink, spaceAfter=9,
                              alignment=TA_LEFT)
    st_box_h = ParagraphStyle("box_h", fontName="DejaVuSerif-Bold", fontSize=11,
                               leading=13, textColor=ink, spaceAfter=5)
    st_box_body = ParagraphStyle("box_body", fontName="DejaVuSans", fontSize=9.3,
                                  leading=13.5, textColor=ink)
    st_muted = ParagraphStyle("muted", fontName="DejaVuSans", fontSize=8,
                               leading=11.5, textColor=ink_muted, spaceBefore=4)
    st_cta = ParagraphStyle("cta", fontName="DejaVuSans-Bold", fontSize=10,
                             leading=14.5, textColor=ink)
    st_footer = ParagraphStyle("footer", fontName="DejaVuSans", fontSize=9,
                                leading=13, textColor=ink)

    story = []

    logo = _logo_drawing(32, shield_hex="#ffffff", bar_hex=TOKENS["navy"])
    today = date.today().strftime("%d.%m.%Y")
    header_cell = [
        Paragraph("KRS Guard — Kalkulator Ryzyka Prawnego", st_h1),
        Paragraph(f"Raport oceny ryzyka &middot; wygenerowano {today}", st_sub),
    ]
    header = Table([[logo, header_cell]], colWidths=[44, None])
    header.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), navy),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (0, 0), 16),
        ("LEFTPADDING", (1, 0), (1, 0), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 14),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
        ("RIGHTPADDING", (1, 0), (1, 0), 14),
    ]))
    story.append(header)
    story.append(Spacer(1, 14))

    pill = Table([[Paragraph(html.escape(output.get("risk_label", "")), st_pill)]])
    pill.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), risk_bg),
        ("BOX", (0, 0), (-1, -1), 0.75, risk_color),
        ("LEFTPADDING", (0, 0), (-1, -1), 16),
        ("RIGHTPADDING", (0, 0), (-1, -1), 16),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    story.append(pill)
    story.append(Spacer(1, 12))

    for p in _body_paragraphs(output):
        story.append(Paragraph(markup_bold(p), st_body))

    if output.get("epu_block_text"):
        heading = output.get("epu_block_heading") or "Dodatkowa informacja: EPU / e-Sąd"
        box_content = [Paragraph(html.escape(heading), st_box_h),
                        Paragraph(markup_bold(output["epu_block_text"]), st_box_body)]
        if output.get("epu_block_disclaimer"):
            box_content.append(Paragraph(markup_bold(output["epu_block_disclaimer"]), st_muted))
        box = Table([[box_content]])
        box.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), mist),
            ("BOX", (0, 0), (-1, -1), 0.75, mist_border),
            ("LEFTPADDING", (0, 0), (-1, -1), 14),
            ("RIGHTPADDING", (0, 0), (-1, -1), 14),
            ("TOPPADDING", (0, 0), (-1, -1), 11),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 11),
        ]))
        story.append(Spacer(1, 4))
        story.append(box)

    if output.get("cta"):
        cta_box = Table([[Paragraph(markup_bold(output["cta"]), st_cta)]])
        cta_box.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), notice_bg),
            ("BOX", (0, 0), (-1, -1), 0.75, notice_border),
            # lewy granatowy akcent — odpowiednik border-left w wersji HTML
            ("LINEBEFORE", (0, 0), (0, -1), 3, navy),
            ("LEFTPADDING", (0, 0), (-1, -1), 16),
            ("RIGHTPADDING", (0, 0), (-1, -1), 16),
            ("TOPPADDING", (0, 0), (-1, -1), 12),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
        ]))
        story.append(Spacer(1, 12))
        story.append(cta_box)

    story.append(Spacer(1, 16))
    story.append(HRFlowable(width="100%", thickness=1, color=mist_border))
    story.append(Spacer(1, 7))
    story.append(Paragraph(markup_bold(output.get("disclaimer", "")), st_footer))

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=16 * mm, bottomMargin=16 * mm,
        title="Ocena ryzyka — KRS Guard",
    )
    doc.build(story)
    return buf.getvalue()
