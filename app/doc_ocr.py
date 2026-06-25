# -*- coding: utf-8 -*-
"""OCR dokumentów: kaskada Azure DI → Tesseract → Claude Haiku."""
from __future__ import annotations
import base64
import io
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
) -> tuple[str, float, str]:
    """
    Kaskada OCR: Azure DI → Tesseract → Claude Haiku.
    Zwraca (full_text, confidence, engine_used).
    engine_used: 'azure' | 'tesseract' | 'claude' | 'none'
    """
    # Silnik 1: Azure Document Intelligence (cały plik naraz)
    azure_key = secrets.get("AZURE_DI_KEY", "")
    azure_endpoint = secrets.get("AZURE_DI_ENDPOINT", "")
    if azure_key and azure_endpoint:
        result = _ocr_azure(raw_bytes, azure_key, azure_endpoint, pages)
        if result is not None:
            text, conf = result
            if conf >= 0.6:
                return text, conf, "azure"

    # Silnik 2: Tesseract z polskim pakietem (per strona)
    result = _ocr_tesseract(pages)
    if result is not None:
        text, conf = result
        if text.strip():
            return text, conf, "tesseract"

    # Silnik 3: Claude Haiku (ostatni resort, per strona)
    claude_key = secrets.get("ANTHROPIC_API_KEY", "")
    if claude_key:
        text, conf = _ocr_claude(pages, claude_key)
        return text, conf, "claude"

    return "", 0.0, "none"


def _ocr_tesseract_pages(scan_pages: list[PageDict]) -> str:
    """Tesseract na podanej liście stron. Zwraca połączony tekst lub ''."""
    try:
        import pytesseract
        from PIL import Image

        texts: list[str] = []
        for page in scan_pages:
            img_bytes = page.get("image_bytes")
            if not img_bytes:
                continue
            img = Image.open(io.BytesIO(img_bytes))
            text = pytesseract.image_to_string(img, lang="pol+eng")
            if text.strip():
                texts.append(text)
        return "\n".join(texts)
    except Exception:
        return ""


def _ocr_azure(
    raw_bytes: bytes,
    key: str,
    endpoint: str,
    pages: list[PageDict],
) -> tuple[str, float] | None:
    """
    Azure Document Intelligence — przyjmuje surowe bajty pliku.
    Jeśli plan darmowy zwrócił mniej stron niż ma dokument, brakujące strony
    przetwarza Tesseract i doklejamy wynik do tekstu Azure.
    """
    try:
        from azure.ai.documentintelligence import DocumentIntelligenceClient
        from azure.core.credentials import AzureKeyCredential

        client = DocumentIntelligenceClient(endpoint, AzureKeyCredential(key))
        poller = client.begin_analyze_document(
            "prebuilt-read",
            analyze_request=raw_bytes,
            content_type="application/octet-stream",
        )
        result = poller.result()

        lines: list[str] = []
        confidences: list[float] = []
        azure_page_count = 0
        for page in (result.pages or []):
            azure_page_count += 1
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
            extra_text = _ocr_tesseract_pages(remaining)
            if extra_text.strip():
                full_text = full_text + "\n--- [strony OCR Tesseract] ---\n" + extra_text

        return full_text, avg_conf
    except Exception:
        return None


def _ocr_tesseract(pages: list[PageDict]) -> tuple[str, float] | None:
    """Tesseract per strona. Wymaga: binarki Tesseract + pakietu językowego pol."""
    combined = _ocr_tesseract_pages(pages)
    return (combined, 0.75) if combined.strip() else None


def _ocr_claude(pages: list[PageDict], api_key: str) -> tuple[str, float]:
    """Claude Haiku per strona — absolutny fallback."""
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    texts: list[str] = []
    all_confident = True

    for page in pages:
        img_bytes = page.get("image_bytes")
        if not img_bytes:
            if page.get("text"):
                texts.append(page["text"])
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
        texts.append(text)
        if "[NIECZYTELNE]" in text:
            all_confident = False

    combined = "\n\n".join(texts)
    confidence = 0.85 if all_confident else 0.3
    return combined, confidence
