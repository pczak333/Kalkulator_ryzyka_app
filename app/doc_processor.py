# -*- coding: utf-8 -*-
"""Orkiestrator etapu 2: łączy ingestion → OCR → ekstrakcję → klasyfikację → selekcję."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date, timedelta

from doc_ingestion import extract_pages, PageDict
from doc_ocr import ocr_page
from doc_extractor import extract_fields
from doc_classifier import classify_document
from doc_selector import select_main_document

# Mapowanie doc_type_code → kod K1 formularza
_DOC_TYPE_TO_K1: dict[str, str] = {
    "POZEW_CZLONEK_ZARZADU":              "K1_POZEW_CZLONEK_ZARZADU",
    "POZEW_SPOLKA":                       "K1_POZEW_SPOLKA",
    "NAKAZ_CZLONEK_ZARZADU":              "K1_NAKAZ_CZLONEK_ZARZADU",
    "NAKAZ_SPOLKA":                       "K1_NAKAZ_SPOLKA",
    "EPU_NAKAZ_SPOLKA":                   "K1_NAKAZ_SPOLKA",
    "EPU_POZEW_SPOLKA":                   "K1_POZEW_SPOLKA",
    "EPU_POZEW_CZLONEK_ZARZADU":          "K1_POZEW_CZLONEK_ZARZADU",
    "EPU_NAKAZ_CZLONEK_ZARZADU":          "K1_NAKAZ_CZLONEK_ZARZADU",
    "WEZWANIE_SADOWE_CZLONEK_ZARZADU":    "K1_WEZWANIE_SADOWE_CZLONEK_ZARZADU",
    "WEZWANIE_SADOWE_SPOLKA":             "K1_WEZWANIE_SADOWE_SPOLKA",
    "DECYZJA_ZUS_CZLONEK_ZARZADU":        "K1_ORGAN_PUBLICZNY_CZLONEK_ZARZADU",
    "DECYZJA_US_CZLONEK_ZARZADU":         "K1_ORGAN_PUBLICZNY_CZLONEK_ZARZADU",
    "ORGAN_PUBLICZNY_CZLONEK_ZARZADU":    "K1_ORGAN_PUBLICZNY_CZLONEK_ZARZADU",
}

# Mapowanie liczby dni na bucket K2
def _days_to_k2(days: int) -> str:
    if days <= 0:
        return "K2_DAYS_LEFT_0_3"
    if days <= 3:
        return "K2_DAYS_LEFT_0_3"
    if days <= 7:
        return "K2_DAYS_LEFT_4_7"
    if days <= 14:
        return "K2_DAYS_LEFT_8_14"
    return "K2_DAYS_LEFT_ABOVE_14"


@dataclass
class ProcessedDocument:
    doc_type_code: str
    k1_code: str
    epu: bool
    delivery_date: date | None
    deadline_days: int | None
    days_left: int | None
    k2_code: str
    days_left_exact: int | None
    amount: float | None
    k7_code: str
    addressee: str | None
    confidence: float
    ocr_quality: str          # "HIGH" | "LOW"
    raw_text: str
    status: str               # "GLOWNY" | "POMOCNICZY" | ...
    page_range: tuple[int, int] = field(default_factory=lambda: (1, 1))
    classifier_confidence: float = 0.0


def _process_single_doc(
    pages: list[PageDict],
    api_key: str | None,
) -> dict:
    """Przetwarza listę stron jako jeden logiczny dokument."""
    full_text = ""
    ocr_confidence = 1.0

    for page in pages:
        if page["is_scan"] and api_key:
            text, conf = ocr_page(page, api_key)
            full_text += "\n" + text
            ocr_confidence = min(ocr_confidence, conf)
        else:
            full_text += "\n" + page["text"]

    full_text = full_text.strip()
    ocr_quality = "LOW" if ocr_confidence < 0.6 else "HIGH"

    fields = extract_fields(full_text)
    doc_type, clf_conf = classify_document(full_text, fields)
    k1_code = _DOC_TYPE_TO_K1.get(doc_type, "K1_INNE_NIE_WIEM")

    # Oblicz dni pozostałe
    days_left: int | None = None
    k2_code = "K2_DAYS_LEFT_UNKNOWN"
    if fields["delivery_date"] and fields["deadline_days"]:
        delta = (fields["delivery_date"] + timedelta(days=fields["deadline_days"])) - date.today()
        days_left = delta.days
        k2_code = _days_to_k2(days_left)

    confidence = round(
        clf_conf * 0.6
        + (fields["adresat_confidence"] * 0.2)
        + (0.2 if fields["delivery_date"] else 0.0),
        3,
    )

    return {
        "doc_type_code": doc_type,
        "k1_code": k1_code,
        "epu": fields["epu"],
        "delivery_date": fields["delivery_date"],
        "deadline_days": fields["deadline_days"],
        "days_left": days_left,
        "k2_code": k2_code,
        "days_left_exact": days_left,
        "amount": fields["amount"],
        "k7_code": fields["k7_code"],
        "addressee": fields["adresat"],
        "confidence": confidence,
        "ocr_quality": ocr_quality,
        "raw_text": full_text,
        "classifier_confidence": clf_conf,
        "page_range": (pages[0]["page_num"], pages[-1]["page_num"]),
    }


def _segment_pages(pages: list[PageDict], api_key: str | None) -> list[dict]:
    """Traktuje cały plik jako jeden logiczny dokument."""
    if not pages:
        return []
    return [_process_single_doc(pages, api_key)]


def process_files(
    uploaded_files,
    api_key: str | None = None,
) -> tuple[ProcessedDocument, list[ProcessedDocument]]:
    """
    Główna funkcja etapu 2. Przyjmuje listę UploadedFile ze Streamlit.
    Zwraca (dokument_główny, [dokumenty_pomocnicze]) jako ProcessedDocument.
    """
    all_candidates: list[dict] = []

    for uf in uploaded_files:
        pages = extract_pages(uf)
        candidates = _segment_pages(pages, api_key)
        all_candidates.extend(candidates)

    if not all_candidates:
        # Fallback — pusty dokument nieustalony
        empty = ProcessedDocument(
            doc_type_code="DOKUMENT_NIEUSTALONY_PRAWNY",
            k1_code="K1_INNE_NIE_WIEM",
            epu=False,
            delivery_date=None,
            deadline_days=None,
            days_left=None,
            k2_code="K2_DAYS_LEFT_UNKNOWN",
            days_left_exact=None,
            amount=None,
            k7_code="K7_AMOUNT_UNKNOWN",
            addressee=None,
            confidence=0.0,
            ocr_quality="LOW",
            raw_text="",
            status="GLOWNY",
        )
        return empty, []

    main_dict, aux_dicts = select_main_document(all_candidates)

    def to_pd(d: dict) -> ProcessedDocument:
        return ProcessedDocument(
            doc_type_code=d.get("doc_type_code", "DOKUMENT_NIEUSTALONY_PRAWNY"),
            k1_code=d.get("k1_code", "K1_INNE_NIE_WIEM"),
            epu=d.get("epu", False),
            delivery_date=d.get("delivery_date"),
            deadline_days=d.get("deadline_days"),
            days_left=d.get("days_left"),
            k2_code=d.get("k2_code", "K2_DAYS_LEFT_UNKNOWN"),
            days_left_exact=d.get("days_left_exact"),
            amount=d.get("amount"),
            k7_code=d.get("k7_code", "K7_AMOUNT_UNKNOWN"),
            addressee=d.get("addressee"),
            confidence=d.get("confidence", 0.0),
            ocr_quality=d.get("ocr_quality", "HIGH"),
            raw_text=d.get("raw_text", ""),
            status=d.get("status", "GLOWNY"),
            page_range=d.get("page_range", (1, 1)),
            classifier_confidence=d.get("classifier_confidence", 0.0),
        )

    return to_pd(main_dict), [to_pd(d) for d in aux_dicts]
