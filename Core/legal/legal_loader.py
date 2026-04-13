import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from bs4 import BeautifulSoup
from pdf2image import convert_from_path
from pypdf import PdfReader
import pytesseract

from config.paths import LEGAL_MEMORY_PATH, TESSERACT_CMD
from core.legal.doc_reader import read_doc, read_docx, read_txt


class LegalLoader:
    """
    Single legal-document entry point.

    Performance strategy:
    - Only scan treaty-focused directories by default.
    - Extract embedded PDF text first (fast path).
    - Run OCR only when embedded text is missing/low-quality.
    - Use GPU OCR automatically when CUDA + easyocr are available.
    """

    def __init__(
        self,
        use_gpu: bool = True,
        dpi: int = 220,
        max_workers: int = None,
        include_nested: bool = False,
        roots: tuple[str, ...] | None = None,
        ocr_fallback: bool = True,
    ):
        self.documents = {}
        self.loaded = False
        self.allowed_roots = roots or ("global", "trade", "countries")
        self.dpi = dpi
        self.max_workers = max_workers or max(1, (os.cpu_count() or 4) - 1)
        self.include_nested = include_nested
        self.ocr_fallback = ocr_fallback
        self._easyocr_reader = None
        self._ocr_mode = "tesseract-cpu"

        if TESSERACT_CMD:
            pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD

        self._setup_ocr_engine(use_gpu=use_gpu)

    def _setup_ocr_engine(self, use_gpu: bool) -> None:
        if not use_gpu:
            return

        try:
            import torch

            if not torch.cuda.is_available():
                return

            import easyocr

            # GPU path (if installed and CUDA-enabled in Python env)
            self._easyocr_reader = easyocr.Reader(["en"], gpu=True, verbose=False)
            self._ocr_mode = "easyocr-gpu"
        except Exception:
            self._easyocr_reader = None
            self._ocr_mode = "tesseract-cpu"

    def _is_usable_text(self, text: str) -> bool:
        if not text:
            return False

        stripped = text.strip()
        if len(stripped) < 300:
            return False

        words = stripped.split()
        if len(words) < 50:
            return False

        alpha_count = sum(1 for ch in stripped if ch.isalpha())
        alpha_ratio = alpha_count / max(1, len(stripped))
        return alpha_ratio >= 0.20

    def _extract_pdf_text_layer(self, path: Path) -> str:
        try:
            reader = PdfReader(str(path))
            chunks = []
            for page in reader.pages:
                extracted = page.extract_text() or ""
                if extracted.strip():
                    chunks.append(extracted)
            return "\n".join(chunks)
        except Exception:
            return ""

    def _ocr_page(self, page_image) -> str:
        if self._easyocr_reader is not None:
            try:
                import numpy as np

                results = self._easyocr_reader.readtext(
                    np.array(page_image), detail=0, paragraph=True
                )
                return "\n".join(results)
            except Exception:
                # Fall through to tesseract if GPU OCR fails for this page.
                pass

        return pytesseract.image_to_string(page_image)

    def _read_pdf(self, path: Path) -> str:
        # Fast path: many treaty PDFs already contain an extractable text layer.
        text_layer = self._extract_pdf_text_layer(path)
        if self._is_usable_text(text_layer):
            return text_layer

        if not self.ocr_fallback:
            return text_layer

        # OCR fallback path for scanned/low-quality PDFs.
        pages = convert_from_path(str(path), dpi=self.dpi, thread_count=self.max_workers)
        worker_count = min(self.max_workers, max(1, len(pages)))
        with ThreadPoolExecutor(max_workers=worker_count) as pool:
            text = list(pool.map(self._ocr_page, pages))
        return "\n".join(text)

    def _read_html(self, path: Path) -> str:
        with open(path, encoding="utf-8", errors="ignore") as f:
            soup = BeautifulSoup(f, "html.parser")
        return soup.get_text(separator=" ")

    def _iter_legal_files(self):
        for root in self.allowed_roots:
            root_dir = LEGAL_MEMORY_PATH / root
            if not root_dir.exists():
                continue

            file_iter = root_dir.rglob("*") if self.include_nested else root_dir.glob("*")
            for file in file_iter:
                if file.suffix.lower() in [
                    ".pdf",
                    ".html",
                    ".htm",
                    ".txt",
                    ".doc",
                    ".docx",
                ]:
                    yield file

    def load(self):
        """
        Loads legal documents once from a controlled treaty scope.
        """
        if self.loaded:
            return self.documents

        print(
            "LegalLoader start | "
            f"OCR={self._ocr_mode} | roots={','.join(self.allowed_roots)} | "
            f"include_nested={self.include_nested} | ocr_fallback={self.ocr_fallback}"
        )

        for file in self._iter_legal_files():
            suffix = file.suffix.lower()

            if suffix == ".pdf":
                try:
                    print("Reading PDF:", file.name)
                    self.documents[str(file)] = self._read_pdf(file)
                except Exception as e:
                    # Some .pdf files are actually HTML (mis-saved).
                    # Detect and fall back to HTML parsing.
                    try:
                        with open(file, "rb") as fh:
                            header = fh.read(20)
                        if header.lstrip().startswith((b"<!DOC", b"<html", b"<HTML", b"\n<!DO")):
                            print("PDF is actually HTML, re-reading:", file.name)
                            self.documents[str(file)] = self._read_html(file)
                        else:
                            print("Failed PDF:", file.name, e)
                    except Exception:
                        print("Failed PDF:", file.name, e)

            elif suffix in [".html", ".htm"]:
                try:
                    print("Reading HTML:", file.name)
                    self.documents[str(file)] = self._read_html(file)
                except Exception as e:
                    print("Failed HTML:", file.name, e)

            elif suffix == ".txt":
                try:
                    print("Reading TXT:", file.name)
                    self.documents[str(file)] = read_txt(file)
                except Exception as e:
                    print("Failed TXT:", file.name, e)

            elif suffix == ".docx":
                try:
                    print("Reading DOCX:", file.name)
                    self.documents[str(file)] = read_docx(file)
                except Exception as e:
                    print("Failed DOCX:", file.name, e)

            elif suffix == ".doc":
                try:
                    print("Reading DOC:", file.name)
                    self.documents[str(file)] = read_doc(file)
                except Exception as e:
                    print("Failed DOC:", file.name, e)

        self.loaded = True
        return self.documents
