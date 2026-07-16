# -*- coding: utf-8 -*-
"""OCR dokumentów: kaskada Azure DI → Claude Haiku (eskalacja przy niskiej
jakości) → Tesseract (fallback wyłącznie bez klucza Anthropic)."""
from __future__ import annotations
import base64
import io
import time
from typing import Callable
from doc_ingestion import PageDict

_CLAUDE_PROMPT = (
    "Przepisz dokładnie tekst z obrazu. To jest polskie pismo prawne lub sądowe. "
    "Zachowaj oryginalną interpunkcję i układ akapitów. "
    "Jeśli tekst jest nieczytelny lub obraz jest zbyt rozmyty, napisz [NIECZYTELNE]. "
    "Zwróć TYLKO tekst dokumentu, bez żadnych komentarzy ani wstępów."
)


def ocr_with_fallback(
    pages: list[PageDict],
    raw_bytes: bytes,
    ext: str,
    secrets: dict,
    on_progress: Callable[[str], None] | None = None,
) -> tuple[str, float, str, str]:
    """
    Kaskada OCR: Azure DI → Claude Haiku (eskalacja gdy Azure poniżej progu
    jakości — nie tylko gdy tekst jest pusty) → Tesseract (prawdziwa ostatnia
    deska ratunku, używana tylko gdy brak klucza Anthropic).
    Zwraca (full_text, confidence, engine_used, notes).
    engine_used: 'azure' | 'tesseract' | 'claude' | 'none'
    notes: log dlaczego silniki były pomijane
    on_progress: opcjonalny callback(str) — komunikat postępu dla UI (patrz
    app.py, st.status). Domyślnie None — brak zmiany zachowania dla
    dotychczasowych wywołań (np. tools/regression_test.py).
    """
    notes: list[str] = []
    claude_key = secrets.get("ANTHROPIC_API_KEY", "")

    # Silnik 1: Azure Document Intelligence (cały plik naraz)
    azure_key = secrets.get("AZURE_DI_KEY", "")
    azure_endpoint = secrets.get("AZURE_DI_ENDPOINT", "")
    azure_candidate: tuple[str, float] | None = None
    if azure_key and azure_endpoint:
        if on_progress:
            on_progress("OCR: analizuję dokument...")
        azure_result, azure_error = _ocr_azure(
            raw_bytes, azure_key, azure_endpoint, pages, on_progress=on_progress
        )
        if azure_result is not None:
            text, conf = azure_result
            # Próg 0.75 = ten sam próg, którego doc_processor.py używa do etykiety
            # jakości "NISKA"/"WYSOKA" w panelu technicznym — wynik poniżej progu
            # nie jest już akceptowany od razu, tylko eskalowany dalej.
            if conf >= 0.75:
                return text, conf, "azure", ""
            notes.append(f"Azure: niska pewność ({conf:.2f} < 0.75) — eskalacja")
            azure_candidate = (text, conf)
        else:
            notes.append(f"Azure: błąd — {azure_error}")
    else:
        notes.append("Azure: brak klucza/endpointu w secrets")

    # Silnik 2: Claude Haiku — eskalacja zawsze, gdy Azure nie osiągnął progu
    # jakości (nie tylko gdy tekst jest kompletnie pusty). Claude czyta każdą
    # stronę z obrazu niezależnie, więc jest odporniejszy na zaburzony układ
    # dwukolumnowy/wielotabelowy niż Tesseract.
    if claude_key:
        if on_progress and azure_candidate is not None:
            on_progress("OCR: doprecyzowuję odczyt dokumentu...")
        text, conf = _ocr_claude(pages, claude_key, on_progress=on_progress)
        return text, conf, "claude", " | ".join(notes)

    # Silnik 3: Tesseract — prawdziwa ostatnia deska ratunku, tylko gdy brak
    # klucza Anthropic (bez niego nie ma czym eskalować).
    tess_result = _ocr_tesseract(pages, on_progress=on_progress)
    if tess_result is not None and tess_result[0].strip():
        text, conf = tess_result
        return text, conf, "tesseract", " | ".join(notes)
    notes.append("Tesseract: brak tekstu lub błąd")

    if azure_candidate is not None:
        text, conf = azure_candidate
        return text, conf, "azure", " | ".join(notes)

    return "", 0.0, "none", " | ".join(notes) + " | Claude: brak klucza"


def _preprocess_for_tesseract(img):
    """Upscaling + autokontrast + odszum — poprawia wyniki Tesseract dla zdjęć i skanów."""
    from PIL import ImageOps, ImageFilter
    img = img.convert("L")
    if max(img.size) < 2200:
        w, h = img.size
        img = img.resize((int(w * 1.5), int(h * 1.5)), img.Resampling.LANCZOS)
    img = ImageOps.autocontrast(img)
    img = img.filter(ImageFilter.MedianFilter(3)).filter(ImageFilter.SHARPEN)
    return img


def _ocr_tesseract_pages(
    scan_pages: list[PageDict],
    on_progress: Callable[[str], None] | None = None,
) -> str:
    """Tesseract na podanej liście stron. Zwraca połączony tekst lub ''."""
    try:
        import pytesseract
        from PIL import Image

        texts: list[str] = []
        for i, page in enumerate(scan_pages, start=1):
            img_bytes = page.get("image_bytes")
            if not img_bytes:
                continue
            if on_progress:
                on_progress(f"OCR: strona {i}/{len(scan_pages)}...")
            img = Image.open(io.BytesIO(img_bytes))
            img = _preprocess_for_tesseract(img)
            text = pytesseract.image_to_string(img, lang="pol+eng")
            if text.strip():
                page_num = page.get("page_num", i)
                texts.append(f"--- STRONA {page_num} ---\n{text}")
        return "\n".join(texts)
    except Exception:
        return ""


def _ocr_azure(
    raw_bytes: bytes,
    key: str,
    endpoint: str,
    pages: list[PageDict],
    on_progress: Callable[[str], None] | None = None,
) -> tuple[tuple[str, float] | None, str]:
    """
    Azure Document Intelligence — przyjmuje surowe bajty pliku.
    Jeśli plan darmowy zwrócił mniej stron niż ma dokument, brakujące strony
    przetwarza Tesseract i doklejamy wynik do tekstu Azure.
    Zwraca ((text, conf), "") w razie sukcesu lub (None, error_msg) w razie błędu.
    """
    try:
        from azure.ai.documentintelligence import DocumentIntelligenceClient
        from azure.core.credentials import AzureKeyCredential

        client = DocumentIntelligenceClient(endpoint, AzureKeyCredential(key))
        poller = client.begin_analyze_document(
            "prebuilt-read",
            body=raw_bytes,
            content_type="application/octet-stream",
        )
        # (15.07.2026) Ręczne odpytywanie zamiast `poller.result()` wprost —
        # to jedno wywołanie bywa NAJDŁUŻSZYM pojedynczym blokiem w całym
        # pipeline (skany wielostronicowe), bez żadnej informacji zwrotnej
        # dla użytkownika (zgłoszenie: statyczny spinner wygląda jak
        # zawieszenie się aplikacji). `poller.done()` pozwala odpytywać co
        # kilka sekund i zgłaszać narastający czas — `poller.result()` na
        # końcu nadal zwraca/rzuca dokładnie to samo, co przy wywołaniu
        # bezpośrednim (błędy Azure nadal łapane przez `except` niżej).
        elapsed = 0
        while not poller.done():
            time.sleep(2)
            elapsed += 2
            if on_progress:
                on_progress(f"OCR: przetwarzam dokument... {elapsed}s")
        result = poller.result()

        lines: list[str] = []
        confidences: list[float] = []
        azure_page_count = 0
        for page_idx, page in enumerate((result.pages or []), start=1):
            azure_page_count += 1
            page_num = getattr(page, "page_number", page_idx)
            lines.append(f"--- STRONA {page_num} ---")
            for line in (page.lines or []):
                lines.append(line.content)
            for word in (page.words or []):
                if word.confidence is not None:
                    confidences.append(word.confidence)

        full_text = "\n".join(lines)
        avg_conf = sum(confidences) / len(confidences) if confidences else 0.5

        # Uzupełnij brakujące strony Tesseractem (limit planu darmowego Azure)
        total_pages = len(pages)
        if azure_page_count < total_pages:
            remaining = pages[azure_page_count:]
            extra_text = _ocr_tesseract_pages(remaining, on_progress=on_progress)
            if extra_text.strip():
                full_text = full_text + "\n--- [strony OCR Tesseract] ---\n" + extra_text

        return (full_text, avg_conf), ""
    except Exception as exc:
        return None, str(exc)


def _ocr_tesseract(
    pages: list[PageDict],
    on_progress: Callable[[str], None] | None = None,
) -> tuple[str, float] | None:
    """Tesseract per strona. Wymaga: binarki Tesseract + pakietu językowego pol."""
    combined = _ocr_tesseract_pages(pages, on_progress=on_progress)
    return (combined, 0.75) if combined.strip() else None


def _ocr_claude(
    pages: list[PageDict],
    api_key: str,
    on_progress: Callable[[str], None] | None = None,
) -> tuple[str, float]:
    """Claude Haiku per strona — eskalacja jakościowa, nie tylko fallback na pusty tekst."""
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    texts: list[str] = []
    all_confident = True

    for i, page in enumerate(pages, start=1):
        page_num = page.get("page_num", i)
        if on_progress:
            on_progress(f"OCR: strona {i}/{len(pages)}...")
        img_bytes = page.get("image_bytes")
        if not img_bytes:
            if page.get("text"):
                texts.append(f"--- STRONA {page_num} ---\n{page['text']}")
            continue

        b64 = base64.standard_b64encode(img_bytes).decode("utf-8")
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=4096,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": b64,
                        },
                    },
                    {"type": "text", "text": _CLAUDE_PROMPT},
                ],
            }],
        )
        text = response.content[0].text.strip()
        texts.append(f"--- STRONA {page_num} ---\n{text}")
        if "[NIECZYTELNE]" in text:
            all_confident = False

    combined = "\n\n".join(texts)
    confidence = 0.85 if all_confident else 0.3
    return combined, confidence
