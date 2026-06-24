# -*- coding: utf-8 -*-
"""OCR skanów przez Claude Vision API."""
from __future__ import annotations
import base64
from doc_ingestion import PageDict

_PROMPT = (
    "Przepisz dokładnie tekst z obrazu. To jest polskie pismo prawne lub sądowe. "
    "Zachowaj oryginalną interpunkcję i układ akapitów. "
    "Jeśli tekst jest nieczytelny lub obraz jest zbyt rozmyty, napisz [NIECZYTELNE]. "
    "Zwróć TYLKO tekst dokumentu, bez żadnych komentarzy ani wstępów."
)


def ocr_page(page: PageDict, api_key: str) -> tuple[str, float]:
    """
    Zwraca (text, confidence) dla strony będącej skanem.
    confidence: 0.9 = dobry odczyt, 0.3 = nieczytelny fragment.
    """
    import anthropic

    image_bytes = page.get("image_bytes")
    if not image_bytes:
        return page.get("text", ""), 1.0

    b64 = base64.standard_b64encode(image_bytes).decode("utf-8")
    client = anthropic.Anthropic(api_key=api_key)

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2000,
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
                {"type": "text", "text": _PROMPT},
            ],
        }],
    )

    text = response.content[0].text.strip()
    confidence = 0.3 if "[NIECZYTELNE]" in text else 0.9
    return text, confidence
