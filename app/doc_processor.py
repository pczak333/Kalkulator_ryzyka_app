# -*- coding: utf-8 -*-
"""Orkiestrator etapu 2: łączy ingestion → OCR → ekstrakcję → klasyfikację → selekcję."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date, timedelta

from doc_ingestion import extract_pages, PageDict
from doc_ocr import ocr_with_fallback
from doc_extractor import extract_fields
from doc_classifier import classify_document
from doc_selector import select_main_document
from ocr_cleanup import clean_ocr_text
from calendar_utils import compute_deadline_date

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
    "PISMO_PROCESOWE_SADOWE":             "K1_INNE_NIE_WIEM",
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
    ocr_engine: str           # "azure" | "tesseract" | "claude" | "native" | "none"
    raw_text: str
    status: str               # "GLOWNY" | "POMOCNICZY" | ...
    deadline_date: date | None = None
    page_range: tuple[int, int] = field(default_factory=lambda: (1, 1))
    classifier_confidence: float = 0.0
    sygnatura: str | None = None
    sad_organ: str | None = None
    powod: str | None = None
    pozwany: str | None = None
    ocr_notes: str = ""
    file_ext: str = ""


def _process_single_doc(
    pages: list[PageDict],
    raw_bytes: bytes,
    ext: str,
    secrets: dict,
    file_ext: str = "",
) -> dict:
    """Przetwarza listę stron jako jeden logiczny dokument."""
    has_scans = any(p["is_scan"] for p in pages)

    ocr_notes = ""
    if has_scans:
        full_text, ocr_confidence, ocr_engine, ocr_notes = ocr_with_fallback(
            pages, raw_bytes, ext, secrets
        )
    else:
        full_text = "\n".join(p["text"] for p in pages)
        ocr_confidence = 1.0
        ocr_engine = "native"

    full_text = full_text.strip()
    # Czyść tekst OCR przed ekstrakcją (tylko skany — natywny PDF nie wymaga)
    if ocr_engine != "native":
        full_text = clean_ocr_text(full_text)
    ocr_quality = "LOW" if ocr_confidence < 0.75 else "HIGH"

    fields = extract_fields(full_text)
    doc_type, clf_conf = classify_document(full_text, fields)
    k1_code = _DOC_TYPE_TO_K1.get(doc_type, "K1_INNE_NIE_WIEM")

    # Oblicz termin końcowy z uwzględnieniem polskich świąt (art. 115 KPC)
    days_left: int | None = None
    deadline_date_val: date | None = None
    k2_code = "K2_DAYS_LEFT_UNKNOWN"
    if fields["delivery_date"] and fields["deadline_days"]:
        deadline_date_val = compute_deadline_date(
            fields["delivery_date"], fields["deadline_days"]
        )
        days_left = (deadline_date_val - date.today()).days
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
        "ocr_engine": ocr_engine,
        "raw_text": full_text,
        "classifier_confidence": clf_conf,
        "page_range": (pages[0]["page_num"], pages[-1]["page_num"]),
        "sygnatura": fields.get("sygnatura"),
        "sad_organ": fields.get("sad_organ"),
        "powod": fields.get("powod"),
        "pozwany": fields.get("pozwany"),
        "ocr_notes": ocr_notes,
        "file_ext": file_ext,
        "deadline_date": deadline_date_val,
    }


def process_files(
    uploaded_files,
    secrets: dict | None = None,
) -> tuple[ProcessedDocument, list[ProcessedDocument]]:
    """
    Główna funkcja etapu 2. Przyjmuje listę UploadedFile ze Streamlit.
    Zwraca (dokument_główny, [dokumenty_pomocnicze]) jako ProcessedDocument.
    secrets: słownik z kluczami AZURE_DI_KEY, AZURE_DI_ENDPOINT, ANTHROPIC_API_KEY.
    """
    if secrets is None:
        secrets = {}
    all_candidates: list[dict] = []

    for uf in uploaded_files:
        raw_bytes = uf.read()
        uf.seek(0)
        ext = uf.name.rsplit(".", 1)[-1].lower()
        pages = extract_pages(uf)
        if pages:
            candidate = _process_single_doc(pages, raw_bytes, ext, secrets, file_ext=ext)
            all_candidates.append(candidate)

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
            ocr_engine="none",
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
            ocr_engine=d.get("ocr_engine", "none"),
            raw_text=d.get("raw_text", ""),
            status=d.get("status", "GLOWNY"),
            page_range=d.get("page_range", (1, 1)),
            classifier_confidence=d.get("classifier_confidence", 0.0),
            sygnatura=d.get("sygnatura"),
            sad_organ=d.get("sad_organ"),
            powod=d.get("powod"),
            pozwany=d.get("pozwany"),
            ocr_notes=d.get("ocr_notes", ""),
            file_ext=d.get("file_ext", ""),
            deadline_date=d.get("deadline_date"),
        )

    return to_pd(main_dict), [to_pd(d) for d in aux_dicts]
