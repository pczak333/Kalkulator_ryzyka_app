# -*- coding: utf-8 -*-
"""Odczytuje wgrane pliki i zwraca listę stron z tekstem lub bajtami obrazu."""
from __future__ import annotations
import io
from typing import TypedDict

import pdfplumber
from PIL import Image
from docx import Document as DocxDocument


MIN_TEXT_CHARS = 50  # poniżej tej liczby stronę traktujemy jako skan


class PageDict(TypedDict):
    page_num: int
    text: str
    is_scan: bool
    image_bytes: bytes | None


def _pdf_page_to_png(page) -> bytes:
    """Renderuje stronę PDF jako PNG (300 dpi)."""
    img = page.to_image(resolution=300)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def extract_pages(uploaded_file) -> list[PageDict]:
    """
    Przyjmuje obiekt UploadedFile ze Streamlit (lub obiekt z atrybutem .name i .read()).
    Zwraca listę PageDict — po jednym na stronę PDF / cały DOCX / obraz.
    """
    name = getattr(uploaded_file, "name", "")
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""

    raw = uploaded_file.read()
    if hasattr(uploaded_file, "seek"):
        uploaded_file.seek(0)

    if ext == "pdf":
        return _extract_pdf(raw)
    elif ext == "docx":
        return _extract_docx(raw)
    elif ext in ("jpg", "jpeg", "png"):
        return _extract_image(raw)
    else:
        # nieznany format — próbuj PDF
        return _extract_pdf(raw)


def _extract_pdf(raw: bytes) -> list[PageDict]:
    pages: list[PageDict] = []
    with pdfplumber.open(io.BytesIO(raw)) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            text = (page.extract_text() or "").strip()
            is_scan = len(text) < MIN_TEXT_CHARS
            image_bytes = _pdf_page_to_png(page) if is_scan else None
            pages.append({
                "page_num": i,
                "text": text,
                "is_scan": is_scan,
                "image_bytes": image_bytes,
            })
    return pages


def _extract_docx(raw: bytes) -> list[PageDict]:
    doc = DocxDocument(io.BytesIO(raw))
    text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    return [{
        "page_num": 1,
        "text": text,
        "is_scan": False,
        "image_bytes": None,
    }]


def _extract_image(raw: bytes) -> list[PageDict]:
    # Sprawdź czy obraz jest czytelny
    try:
        Image.open(io.BytesIO(raw))
    except Exception:
        pass
    return [{
        "page_num": 1,
        "text": "",
        "is_scan": True,
        "image_bytes": raw,
    }]
