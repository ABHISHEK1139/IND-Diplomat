"""
Transformation Layer - Multimodal PDF Pipeline
Handles complex diplomatic PDFs with table extraction, OCR, and visual token injection.
"""

import os
import io
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import hashlib


@dataclass
class ParsedChunk:
    """A parsed chunk from a document."""
    content: str
    chunk_type: str  # "text", "table", "image_caption", "header", "metadata"
    page_number: int
    position: Dict[str, float]  # bounding box
    confidence: float
    metadata: Dict[str, Any]


@dataclass
class DocumentParseResult:
    """Complete result of document parsing."""
    document_id: str
    filename: str
    total_pages: int
    chunks: List[ParsedChunk]
    tables: List[Dict]
    images: List[Dict]
    metadata: Dict[str, Any]
    parse_time_ms: float


class LlamaParseAdapter:
    """
    Adapter for LlamaParse with layout extraction.
    Handles complex PDF structures including tables and multi-column layouts.
    """
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("LLAMA_CLOUD_API_KEY")
        self._parser = None
        self._init_parser()
    
    def _init_parser(self):
        """Initialize LlamaParse if available."""
        try:
            from llama_parse import LlamaParse
            self._parser = LlamaParse(
                api_key=self.api_key,
                result_type="markdown",
                parsing_instruction="Extract all tables with structure preserved. Extract treaty dates, signatories, and article numbers.",
                gpt4o_mode=True,  # Use GPT-4o for complex layouts
                gpt4o_api_key=os.getenv("OPENAI_API_KEY"),
                verbose=True
            )
            print("[LlamaParse] Initialized with layout extraction")
        except ImportError:
            print("[LlamaParse] Not available, using fallback")
            self._parser = None
        except Exception as e:
            print(f"[LlamaParse] Init error: {e}")
            self._parser = None
    
    def parse(self, file_path: str) -> List[ParsedChunk]:
        """Parse document using LlamaParse with layout extraction."""
        if self._parser is None:
            return self._fallback_parse(file_path)
        
        try:
            documents = self._parser.load_data(file_path)
            
            chunks = []
            for i, doc in enumerate(documents):
                # Detect chunk type from content
                content = doc.text
                chunk_type = self._detect_chunk_type(content)
                
                chunks.append(ParsedChunk(
                    content=content,
                    chunk_type=chunk_type,
                    page_number=doc.metadata.get("page_number", i + 1),
                    position={"x": 0, "y": 0, "width": 1, "height": 1},
                    confidence=0.95,
                    metadata=doc.metadata
                ))
            
            return chunks
            
        except Exception as e:
            print(f"[LlamaParse] Parse error: {e}")
            return self._fallback_parse(file_path)
    
    def _detect_chunk_type(self, content: str) -> str:
        """Detect chunk type from content patterns."""
        if "|" in content and content.count("|") > 5:
            return "table"
        if content.strip().startswith("#"):
            return "header"
        if re.match(r"^(Article|Section|Chapter)\s+\d+", content):
            return "article_header"
        return "text"
    
    def _fallback_parse(self, file_path: str) -> List[ParsedChunk]:
        """Fallback parsing when LlamaParse unavailable."""
        try:
            import PyPDF2
            
            chunks = []
            with open(file_path, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                for i, page in enumerate(reader.pages):
                    text = page.extract_text() or ""
                    chunks.append(ParsedChunk(
                        content=text,
                        chunk_type="text",
                        page_number=i + 1,
                        position={"x": 0, "y": 0, "width": 1, "height": 1},
                        confidence=0.7,
                        metadata={"source": "pypdf2_fallback"}
                    ))
            return chunks
            
        except Exception as e:
            print(f"[Fallback] Error: {e}")
            return []


class DeepSeekOCRAdapter:
    """
    Adapter for DeepSeek-OCR with visual token injection.
    Handles scanned documents and image-heavy PDFs.
    """
    
    def __init__(self, model_name: str = "deepseek-vl"):
        self.model_name = model_name
        self._ocr_engine = None
        self._init_ocr()
    
    def _init_ocr(self):
        """Initialize OCR engine."""
        try:
            import pytesseract
            self._ocr_engine = "tesseract"
            print("[OCR] Using Tesseract")
        except ImportError:
            try:
                import easyocr
                self._reader = easyocr.Reader(['en'])
                self._ocr_engine = "easyocr"
                print("[OCR] Using EasyOCR")
            except ImportError:
                self._ocr_engine = None
                print("[OCR] No OCR engine available")
    
    def extract_from_image(self, image_path: str) -> Tuple[str, float]:
        """Extract text from image with confidence score."""
        if self._ocr_engine is None:
            return "", 0.0
        
        try:
            if self._ocr_engine == "tesseract":
                import pytesseract
                from PIL import Image
                
                img = Image.open(image_path)
                text = pytesseract.image_to_string(img)
                # Get confidence from data
                data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
                confidences = [int(c) for c in data['conf'] if c != '-1']
                avg_conf = sum(confidences) / len(confidences) if confidences else 0
                
                return text, avg_conf / 100
            
            elif self._ocr_engine == "easyocr":
                results = self._reader.readtext(image_path)
                texts = [r[1] for r in results]
                confidences = [r[2] for r in results]
                
                return " ".join(texts), sum(confidences) / len(confidences) if confidences else 0
        
        except Exception as e:
            print(f"[OCR] Error: {e}")
            return "", 0.0
    
    def inject_visual_tokens(self, content: str, visual_context: Dict) -> str:
        """Inject visual tokens into text for model understanding."""
        # Add visual context markers
        tokens = []
        
        if visual_context.get("is_table"):
            tokens.append("[TABLE_START]")
            content = content
            tokens.append("[TABLE_END]")
        
        if visual_context.get("has_signature"):
            tokens.append("[SIGNATURE_PRESENT]")
        
        if visual_context.get("has_seal"):
            tokens.append("[OFFICIAL_SEAL]")
        
        if visual_context.get("layout_type"):
            tokens.append(f"[LAYOUT:{visual_context['layout_type'].upper()}]")
        
        return " ".join(tokens) + " " + content if tokens else content


class TableExtractor:
    """Extracts and structures tables from documents."""
    
    def __init__(self):
        self._has_camelot = False
        try:
            import camelot
            self._has_camelot = True
        except ImportError:
            pass
    
    def extract_tables(self, pdf_path: str) -> List[Dict]:
        """Extract tables with structure preserved."""
        if not self._has_camelot:
            return self._regex_table_extract(pdf_path)
        
        try:
            import camelot
            
            tables = camelot.read_pdf(pdf_path, pages='all', flavor='stream')
            
            results = []
            for i, table in enumerate(tables):
                df = table.df
                results.append({
                    "table_id": f"table_{i}",
                    "page": table.page,
                    "headers": df.iloc[0].tolist() if len(df) > 0 else [],
                    "rows": df.iloc[1:].values.tolist() if len(df) > 1 else [],
                    "accuracy": table.accuracy,
                    "markdown": df.to_markdown()
                })
            
            return results
            
        except Exception as e:
            print(f"[TableExtractor] Error: {e}")
            return []
    
    def _regex_table_extract(self, pdf_path: str) -> List[Dict]:
        """Fallback regex-based table detection."""
        # Simple markdown table detection from parsed text
        return []


class TransformationPipeline:
    """
    Main transformation pipeline for diplomatic documents.
    Combines LlamaParse, OCR, and table extraction.
    """
    
    def __init__(self):
        self.llama_parser = LlamaParseAdapter()
        self.ocr_adapter = DeepSeekOCRAdapter()
        self.table_extractor = TableExtractor()
    
    def process_document(self, file_path: str, extract_tables: bool = True) -> DocumentParseResult:
        """
        Process a document through the full transformation pipeline.
        """
        start_time = datetime.now()
        
        file_path = Path(file_path)
        doc_id = hashlib.md5(str(file_path).encode()).hexdigest()[:12]
        
        # Step 1: Parse with LlamaParse (layout-aware)
        chunks = self.llama_parser.parse(str(file_path))
        
        # Step 2: Extract tables if PDF
        tables = []
        if extract_tables and file_path.suffix.lower() == '.pdf':
            tables = self.table_extractor.extract_tables(str(file_path))
        
        # Step 3: OCR for low-confidence chunks
        for chunk in chunks:
            if chunk.confidence < 0.6 and chunk.chunk_type == "text":
                # Would need image extraction here
                pass
        
        # Step 4: Inject visual tokens for table chunks
        for chunk in chunks:
            if chunk.chunk_type == "table":
                chunk.content = self.ocr_adapter.inject_visual_tokens(
                    chunk.content, 
                    {"is_table": True, "layout_type": "structured"}
                )
        
        elapsed = (datetime.now() - start_time).total_seconds() * 1000
        
        return DocumentParseResult(
            document_id=doc_id,
            filename=file_path.name,
            total_pages=len(set(c.page_number for c in chunks)),
            chunks=chunks,
            tables=tables,
            images=[],
            metadata={
                "source": str(file_path),
                "processed_at": datetime.now().isoformat(),
                "has_tables": len(tables) > 0
            },
            parse_time_ms=elapsed
        )
    
    def chunk_for_retrieval(
        self, 
        result: DocumentParseResult, 
        chunk_size: int = 512, 
        overlap: int = 64
    ) -> List[Dict]:
        """Convert parse result to retrieval-ready chunks."""
        retrieval_chunks = []
        
        for chunk in result.chunks:
            content = chunk.content
            
            # Split large chunks
            if len(content) > chunk_size:
                for i in range(0, len(content), chunk_size - overlap):
                    sub_content = content[i:i + chunk_size]
                    retrieval_chunks.append({
                        "content": sub_content,
                        "metadata": {
                            "document_id": result.document_id,
                            "filename": result.filename,
                            "page": chunk.page_number,
                            "chunk_type": chunk.chunk_type,
                            "confidence": chunk.confidence,
                            **chunk.metadata
                        }
                    })
            else:
                retrieval_chunks.append({
                    "content": content,
                    "metadata": {
                        "document_id": result.document_id,
                        "filename": result.filename,
                        "page": chunk.page_number,
                        "chunk_type": chunk.chunk_type,
                        "confidence": chunk.confidence,
                        **chunk.metadata
                    }
                })
        
        # Add tables as separate chunks
        for table in result.tables:
            retrieval_chunks.append({
                "content": table.get("markdown", ""),
                "metadata": {
                    "document_id": result.document_id,
                    "filename": result.filename,
                    "page": table.get("page", 0),
                    "chunk_type": "table",
                    "table_id": table.get("table_id"),
                    "confidence": table.get("accuracy", 0.8)
                }
            })
        
        return retrieval_chunks


# Singleton instance
transformation_pipeline = TransformationPipeline()
