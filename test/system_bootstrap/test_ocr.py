"""Validate OCR pipeline: PDF download -> image conversion -> Tesseract extraction."""

from __future__ import annotations

import re
import shutil
import sys
import tempfile
from pathlib import Path

import requests
import pytesseract
from pdf2image import convert_from_path

SAMPLE_PDF_URLS = [
    "https://www.africau.edu/images/default/sample.pdf",
    "https://arxiv.org/pdf/1706.03762.pdf",
    "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf",
]

TESSERACT_CANDIDATES = [
    Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
    Path(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"),
]

POPPLER_CANDIDATES = [
    Path(r"C:\Program Files\poppler\Library\bin"),
    Path(r"C:\Program Files\poppler\bin"),
]


def fail(reason: str) -> int:
    print(f"OCR_FAILED: {reason}")
    return 1


def main() -> int:
    poppler_path: str | None = None
    for candidate in POPPLER_CANDIDATES:
        if candidate.exists():
            poppler_path = str(candidate)
            break

    if shutil.which("tesseract") is None:
        for candidate in TESSERACT_CANDIDATES:
            if candidate.exists():
                pytesseract.pytesseract.tesseract_cmd = str(candidate)
                break

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        pdf_path = tmp_path / "sample.pdf"

        download_errors = []
        downloaded = False
        for url in SAMPLE_PDF_URLS:
            try:
                response = requests.get(
                    url,
                    timeout=45,
                    headers={"User-Agent": "Mozilla/5.0"},
                )
                response.raise_for_status()
                pdf_path.write_bytes(response.content)
                downloaded = True
                break
            except Exception as exc:
                download_errors.append(f"{url} -> {exc}")
        if not downloaded:
            return fail(f"PDF download failed. Attempts: {' | '.join(download_errors)}")

        try:
            kwargs = {"dpi": 300, "first_page": 1, "last_page": 1}
            if poppler_path:
                kwargs["poppler_path"] = poppler_path
            pages = convert_from_path(str(pdf_path), **kwargs)
        except Exception as exc:
            return fail(f"pdf2image conversion failed (Poppler likely missing): {exc}")
        if not pages:
            return fail("No pages produced by pdf2image")

        try:
            text = pytesseract.image_to_string(pages[0])
        except Exception as exc:
            return fail(f"Tesseract OCR failed: {exc}")

        readable = re.sub(r"\s+", " ", "".join(ch for ch in text if ch.isprintable())).strip()
        if len(readable) < 50:
            return fail(f"Readable OCR text too short: {len(readable)} chars")

        print(f"OCR_OK: extracted_chars={len(readable)}")
        print(readable[:240])
        return 0


if __name__ == "__main__":
    sys.exit(main())
