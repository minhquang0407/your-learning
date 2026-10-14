"""Document processor supporting multi-format ingestion and structural hierarchy preservation.

Features:
- Multi-format ingestion: Markdown, PDF, PPTX, DOCX via MarkItDown with graceful fallbacks.
- 4-layer structural defense against lost headers:
  1. Natural slide boundary handling (<!-- slide --> treated as section unit).
  2. Heuristic Regex preprocessor (auto_inject_markdown_headers) for Chapter and Section numbering.
  3. Table of Contents fallback logic.
  4. Fallback chunking via RecursiveCharacterTextSplitter if headers are absent.
- Hierarchical Hybrid Chunking & Structural Provenance Injection:
  - Sections > 1,200 words sub-chunked into 600-800 word blocks with 150-word overlap.
  - Context header prepended: [Pedagogical Context: {Chapter} > {Section}]
"""

import io
import os
import re
import tempfile
from typing import Any, Dict, List, Optional, Tuple, Union

from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

HEADERS_TO_SPLIT_ON = [
    ("#", "Chapter"),
    ("##", "Section"),
]


def auto_inject_markdown_headers(raw_text: str) -> str:
    """Detect Chapter/Section numbering heuristics and inject '#' and '##' headers.

    Preserves lines that already start with '#' Markdown headers.
    Matches:
    - Chapter patterns: Chapter \\d+, Chapter [IVXLCDM]+, Chương \\d+, Phần \\d+, Part \\d+ -> #
    - Section patterns: \\d+\\.\\d+, Roman numerals (I., II.), Section \\d+, Section \\d+\\.\\d+, Mục \\d+ -> ##
    - Numbered sections: 1 Quy mô..., 2 Quy trình..., 1. Overview -> ##
    - Document title: First prominent non-list title line becomes '#' if no chapter exists.
    """
    lines = raw_text.splitlines()
    injected_lines: List[str] = []

    chapter_pattern = re.compile(
        r"^\s*(?:Chapter|Chương|Phần|Part|Appendix|Phụ lục)\s+(?:\d+|[IVXLCDM]+|[A-Z])(?:[:\s.-].*)?$",
        re.IGNORECASE,
    )
    multi_dot_section_pattern = re.compile(
        r"^\s*(?:(?:(?:[1-9]\d?|[A-Z])\.\d+(?:\.\d+)*|[IVXLCDM]+\.)\s+([A-ZÀ-Ỹ][^\n.]{1,80})|(?:Section|Mục)\s+(?:\d+(?:\.\d+)*|[IVXLCDM]+)(?:[:\s.-].*)?)$",
        re.IGNORECASE,
    )
    single_num_section_pattern = re.compile(
        r"^\s*([1-9]\d?|[A-Z])(?:\s+|\.\s+)([A-ZÀ-Ỹ].*)$"
    )
    keyword_section_pattern = re.compile(
        r"^\s*(?:Abstract|Tóm tắt|References|Tài liệu tham khảo|Acknowledgment[s]?|Limitations)(?:[:\s.-].*)?$",
        re.IGNORECASE,
    )

    vietnamese_keywords = {"quy", "cách", "bảng", "phần", "chương", "bài", "mục", "tổng", "thực", "nghiên", "kết", "phân", "giới"}
    english_keywords = {
        "introduction", "materials", "methods", "results", "discussion",
        "conclusion", "baseline", "datasets", "analysis", "model",
        "overview", "evaluation", "measurement", "process", "background",
        "related", "system", "architecture", "approach", "framework",
        "methodology", "pipeline", "experiment", "experiments", "implementation",
        "work", "future", "limitation", "limitations", "appendix", "details",
    }

    def is_valid_section_title(title_str: str) -> bool:
        words = title_str.strip().split()
        if len(words) >= 3:
            return True
        t_lower = title_str.lower()
        return any(k in t_lower for k in (vietnamese_keywords | english_keywords))

    has_explicit_chapter = any(
        line.strip().startswith("# ") or (chapter_pattern.match(line.strip()) and not line.strip().endswith((".", ";", ",")))
        for line in lines
    )
    first_title_injected = False
    skip_until_idx = -1

    for i, line in enumerate(lines):
        if i <= skip_until_idx:
            continue

        stripped = line.strip()
        if not stripped:
            injected_lines.append(line)
            continue

        # If already formatted as a Markdown header, preserve it
        if stripped.startswith("#"):
            injected_lines.append(line)
            continue

        # Preserve slide and horizontal rule markers
        if stripped.startswith("<!--") or stripped.startswith("---"):
            injected_lines.append(line)
            continue

        # Detect chapter-level numbering (Chapter 1, Chương 2, Appendix A, etc.)
        if chapter_pattern.match(stripped) and not stripped.endswith((".", ";", ",")):
            injected_lines.append(f"# {stripped}")
            has_explicit_chapter = True
            continue

        # If no explicit chapter exists in the document, treat the first prominent title line as # Document Chapter
        if not has_explicit_chapter and not first_title_injected:
            if (
                len(stripped) < 100
                and not stripped.endswith((".", ";", ","))
                and not stripped.startswith(("•", "-", "*", "|"))
            ):
                if stripped.endswith(":"):
                    nxt_idx = i + 1
                    while nxt_idx < len(lines) and not lines[nxt_idx].strip():
                        nxt_idx += 1
                    if nxt_idx < len(lines):
                        nxt = lines[nxt_idx].strip()
                        if (
                            nxt
                            and len(nxt) < 100
                            and not nxt.endswith((".", ";", ":", ","))
                            and not nxt.startswith(("•", "-", "*", "|"))
                        ):
                            injected_lines.append(f"# {stripped} {nxt}")
                            first_title_injected = True
                            skip_until_idx = nxt_idx
                            continue
                if not stripped.endswith(":"):
                    injected_lines.append(f"# {stripped}")
                    first_title_injected = True
                    continue

        # Detect academic keyword sections: Abstract, Tóm tắt, References, Limitations, etc.
        if keyword_section_pattern.match(stripped):
            injected_lines.append(f"## {stripped}")
            continue

        # Detect single-number/letter major sections: 1 Introduction, 2 Materials and Methods, A Details -> # Chapter
        m = single_num_section_pattern.match(stripped)
        if m:
            content = m.group(2).strip()
            # Distinguish headings from numbered list items or short table data cells
            if is_valid_section_title(content) and not (":" in content and len(content.split(":", 1)[1].strip()) > 30):
                if len(stripped) < 90 and not stripped.endswith((".", ";", ",")):
                    injected_lines.append(f"# {stripped}")
                    continue

        # Detect section-level multi-dot numbering: 1.1, 2.1, 3.2.1, A.1, II., Section 1, Mục 2 -> ## Section
        m_dot = multi_dot_section_pattern.match(stripped)
        if m_dot:
            title_part = m_dot.group(1) or ""
            # Exclude table floats and metric phrases
            if (
                not any(sym in title_part for sym in ["±", "/", "<", ">", "=", "%", "("])
                and "or lower" not in title_part.lower()
                and "and above" not in title_part.lower()
            ):
                injected_lines.append(f"## {stripped}")
                continue

        injected_lines.append(line)

    return "\n".join(injected_lines)


def handle_slide_boundaries(raw_text: str) -> str:
    """Normalize slide boundary markers and ensure each slide acts as a section unit.

    Detects <!-- slide -->, <!-- slide: N -->, and --- slide --- comments.
    Preserves preamble and explicit slide numbering without clobbering existing headers.
    """
    pattern = re.compile(
        r"(?:<!--\s*slide(?::\s*(\d+))?\s*-->|---\s*slide(?::\s*(\d+))?\s*---)",
        re.IGNORECASE,
    )
    matches = list(pattern.finditer(raw_text))
    if not matches:
        return raw_text

    processed_blocks: List[str] = []
    has_chapter = bool(re.search(r"^\s*#\s+", raw_text, flags=re.MULTILINE))
    if not has_chapter:
        processed_blocks.append("# Presentation Slides\n")

    preamble = raw_text[: matches[0].start()].strip()
    if preamble:
        processed_blocks.append(preamble)

    fallback_counter = 1
    for i, match in enumerate(matches):
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(raw_text)
        block = raw_text[start:end].strip()
        if not block:
            continue

        slide_num_str = match.group(1) or match.group(2)
        if slide_num_str and slide_num_str.isdigit():
            slide_num = int(slide_num_str)
            fallback_counter = slide_num + 1
        else:
            slide_num = fallback_counter
            fallback_counter += 1

        # Check if block already has # or ## header
        if not re.search(r"^\s*#{1,2}\s+", block, flags=re.MULTILINE):
            lines = block.splitlines()
            first_line = lines[0].strip()
            if len(first_line) < 80 and not first_line.endswith((".", ":")):
                remaining = "\n".join(lines[1:]).strip()
                if remaining:
                    processed_blocks.append(f"## Slide {slide_num}: {first_line}\n\n{remaining}")
                else:
                    processed_blocks.append(f"## Slide {slide_num}: {first_line}")
            else:
                processed_blocks.append(f"## Slide {slide_num}\n\n{block}")
        else:
            processed_blocks.append(block)

    return "\n\n".join(processed_blocks)


def sub_chunk_section(
    section_text: str,
    chapter: str,
    section: str,
    max_words: int = 1200,
    target_chunk_words: int = 700,
    overlap_words: int = 150,
) -> List[str]:
    """Sub-chunk long section texts if they exceed the max_words threshold.

    Prepends context header '[Pedagogical Context: {Chapter} > {Section}]' to each sub-chunk text.
    Blocks are 600-800 words with 150-word overlap while preserving internal newlines and math/code formatting.
    """
    context_prefix = f"[Pedagogical Context: {chapter} > {section}]"

    # Strip existing context prefix if present to prevent duplication
    clean_text = section_text.strip()
    if clean_text.startswith("[Pedagogical Context:"):
        parts = clean_text.split("]\n\n", 1)
        if len(parts) == 2:
            clean_text = parts[1].strip()

    if not clean_text:
        return []

    word_matches = list(re.finditer(r"\S+", clean_text))
    total_words = len(word_matches)

    if total_words == 0:
        return []

    if total_words <= max_words:
        return [f"{context_prefix}\n\n{clean_text}"]

    sub_chunks: List[str] = []
    start = 0
    step = max(1, target_chunk_words - overlap_words)

    while start < total_words:
        end = min(start + target_chunk_words, total_words)
        char_start = word_matches[start].start()
        char_end = word_matches[end - 1].end()
        chunk_body = clean_text[char_start:char_end].strip()
        sub_chunks.append(f"{context_prefix}\n\n{chunk_body}")

        if end >= total_words:
            break
        start += step

    return sub_chunks


class MathAwareDocumentProcessor:
    """Document processor with multi-format support, 4-layer header defense, and hybrid sub-chunking."""

    def __init__(self):
        """Initialize the document processor."""
        pass

    def convert_to_markdown(
        self,
        content_or_bytes: Union[str, bytes, None] = None,
        file_path: Optional[str] = None,
        file_bytes: Optional[bytes] = None,
        filename: str = "",
    ) -> str:
        """Convert multi-format documents (PDF, PPTX, DOCX, Markdown, Text) into clean Markdown.

        Prefers MarkItDown, gracefully falling back to native format parsers (fitz/pypdf, python-docx, python-pptx).
        """
        # Resolve bytes and path
        ext = ""
        if filename:
            ext = os.path.splitext(filename)[1].lower()
        elif file_path:
            ext = os.path.splitext(file_path)[1].lower()

        if file_bytes is None and isinstance(content_or_bytes, bytes):
            file_bytes = content_or_bytes
        elif file_bytes is None and isinstance(content_or_bytes, str):
            # If string contains file path on disk
            if os.path.exists(content_or_bytes) and os.path.isfile(content_or_bytes):
                file_path = content_or_bytes
            elif ext in (".pdf", ".docx", ".pptx"):
                import base64

                clean_content = content_or_bytes.strip()
                if clean_content.startswith("data:") and ";base64," in clean_content:
                    clean_content = clean_content.split(";base64,")[1]
                try:
                    decoded = base64.b64decode(clean_content, validate=True)
                    if len(decoded) > 0:
                        file_bytes = decoded
                except Exception:
                    file_bytes = content_or_bytes.encode("latin1", errors="replace")
            else:
                # Direct string content (Markdown or plain text)
                return content_or_bytes

        # If it's pure markdown or txt string
        if ext in (".md", ".txt") and file_bytes is not None:
            return file_bytes.decode("utf-8", errors="replace")

        # For PDF documents, prefer high-fidelity layout extraction (pdfplumber / fitz / pypdf)
        # to avoid fragmented pipe tables generated by layout heuristics.
        if ext == ".pdf":
            parsed_pdf = self._parse_pdf_fallback(file_bytes=file_bytes, file_path=file_path)
            if parsed_pdf and parsed_pdf.strip():
                return parsed_pdf

        # Attempt conversion with MarkItDown for DOCX, PPTX, HTML, and other formats
        try:
            from markitdown import MarkItDown

            md = MarkItDown()
            if file_path and os.path.exists(file_path):
                res = md.convert(file_path)
                if res and getattr(res, "text_content", None) and res.text_content.strip():
                    return res.text_content
            elif file_bytes:
                suffix = ext or ".bin"
                with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                    tmp.write(file_bytes)
                    tmp_path = tmp.name
                try:
                    res = md.convert(tmp_path)
                    if res and getattr(res, "text_content", None) and res.text_content.strip():
                        return res.text_content
                finally:
                    if os.path.exists(tmp_path):
                        try:
                            os.remove(tmp_path)
                        except OSError:
                            pass
        except Exception as markitdown_err:
            print(f"[DocumentProcessor] MarkItDown conversion error: {markitdown_err}. Using fallback parser.")

        # Graceful Fallbacks by extension
        if ext == ".pdf":
            return self._parse_pdf_fallback(file_bytes=file_bytes, file_path=file_path)
        elif ext == ".docx":
            return self._parse_docx_fallback(file_bytes=file_bytes, file_path=file_path)
        elif ext == ".pptx":
            return self._parse_pptx_fallback(file_bytes=file_bytes, file_path=file_path)

        # Fallback to UTF-8 decoding
        if file_bytes:
            return file_bytes.decode("utf-8", errors="replace")
        if file_path and os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                return f.read()

        return str(content_or_bytes or "")

    def _parse_pdf_fallback(self, file_bytes: Optional[bytes], file_path: Optional[str]) -> str:
        """Parse PDF document using PyMuPDF (fitz), pdfplumber, or pypdf."""
        # Try PyMuPDF (fitz) with block reading order and standalone section number merging
        try:
            import fitz

            doc = fitz.open(stream=file_bytes, filetype="pdf") if file_bytes else fitz.open(file_path)
            pages: List[str] = []
            for idx, page in enumerate(doc, 1):
                blocks = page.get_text("blocks")
                text_blocks = [b for b in blocks if b[6] == 0 and b[4].strip()]
                lines: List[str] = []
                for b in text_blocks:
                    b_lines = b[4].splitlines()
                    i = 0
                    while i < len(b_lines):
                        l = b_lines[i].strip()
                        # Standalone section number merge (e.g. '1', '2', '2.1', '3', 'A', 'A.1')
                        if (
                            re.match(r"^(?:[1-9]\d?|[A-Z]|\d+\.\d+(?:\.\d+)*|[A-Z]\.\d+(?:\.\d+)*|[IVXLCDM]+)$", l)
                            and i + 1 < len(b_lines)
                        ):
                            nxt = b_lines[i + 1].strip()
                            if nxt and re.match(r"^[A-ZÀ-Ỹ]", nxt) and len(nxt) < 80 and not nxt.endswith((".", ";", ":")):
                                lines.append(f"{l} {nxt}")
                                i += 2
                                continue
                        lines.append(b_lines[i])
                        i += 1
                page_text = "\n".join(lines)
                if page_text.strip():
                    pages.append(page_text.strip())
            doc.close()
            if pages:
                return "\n\n".join(pages)
        except Exception:
            pass

        # Try pdfplumber with smart multi-column detection as fallback
        try:
            import pdfplumber

            stream = io.BytesIO(file_bytes) if file_bytes else file_path
            with pdfplumber.open(stream) as pdf:
                pages = []
                for idx, page in enumerate(pdf.pages, 1):
                    words = page.extract_words()
                    if not words or len(words) < 30:
                        txt = page.extract_text() or ""
                    else:
                        w = page.width
                        h = page.height
                        gutter = w * 0.5
                        straddling = [wrd for wrd in words if wrd["x0"] < gutter < wrd["x1"]]
                        left_ends = [wrd for wrd in words if w * 0.35 < wrd["x1"] < w * 0.50]
                        right_starts = [wrd for wrd in words if w * 0.50 < wrd["x0"] < w * 0.65]

                        if len(straddling) <= 2 and len(left_ends) >= 5 and len(right_starts) >= 5:
                            col1 = page.crop((0, 0, gutter, h)).extract_text() or ""
                            col2 = page.crop((gutter, 0, w, h)).extract_text() or ""
                            txt = col1.strip() + "\n\n" + col2.strip()
                        else:
                            txt = page.extract_text() or ""

                    if txt.strip():
                        pages.append(txt.strip())
                if pages:
                    return "\n\n".join(pages)
        except Exception:
            pass

        # Try PyMuPDF (fitz)
        try:
            import fitz

            doc = fitz.open(stream=file_bytes, filetype="pdf") if file_bytes else fitz.open(file_path)
            pages = []
            for idx, page in enumerate(doc, 1):
                txt = page.get_text()
                if txt.strip():
                    pages.append(txt.strip())
            doc.close()
            if pages:
                return "\n\n".join(pages)
        except Exception:
            pass

        # Try pypdf
        try:
            import pypdf

            stream = io.BytesIO(file_bytes) if file_bytes else file_path
            reader = pypdf.PdfReader(stream)
            pages = []
            for idx, page in enumerate(reader.pages, 1):
                txt = page.extract_text() or ""
                if txt.strip():
                    pages.append(txt.strip())
            if pages:
                return "\n\n".join(pages)
        except Exception as pdf_err:
            print(f"[DocumentProcessor] PDF fallback failed: {pdf_err}")

        return ""

    def _parse_docx_fallback(self, file_bytes: Optional[bytes], file_path: Optional[str]) -> str:
        """Parse DOCX document using python-docx."""
        try:
            import docx

            stream = io.BytesIO(file_bytes) if file_bytes else file_path
            doc = docx.Document(stream)
            elements: List[str] = []
            for p in doc.paragraphs:
                txt = p.text.strip()
                if not txt:
                    continue
                style_name = (p.style.name if p.style else "").lower()
                if "heading 1" in style_name:
                    elements.append(f"# {txt}")
                elif "heading 2" in style_name:
                    elements.append(f"## {txt}")
                elif "heading 3" in style_name:
                    elements.append(f"### {txt}")
                else:
                    elements.append(txt)
            return "\n\n".join(elements)
        except Exception as docx_err:
            print(f"[DocumentProcessor] DOCX fallback failed: {docx_err}")
            return ""

    def _parse_pptx_fallback(self, file_bytes: Optional[bytes], file_path: Optional[str]) -> str:
        """Parse PPTX document using python-pptx."""
        try:
            import pptx

            stream = io.BytesIO(file_bytes) if file_bytes else file_path
            prs = pptx.Presentation(stream)
            slides_text: List[str] = []
            for idx, slide in enumerate(prs.slides, 1):
                slide_lines: List[str] = []
                for shape in slide.shapes:
                    if hasattr(shape, "text") and shape.text.strip():
                        slide_lines.append(shape.text.strip())
                if slide_lines:
                    content = "\n\n".join(slide_lines)
                    slides_text.append(f"<!-- slide: {idx} -->\n\n## Slide {idx}\n\n{content}")
            return "\n\n".join(slides_text)
        except Exception as pptx_err:
            print(f"[DocumentProcessor] PPTX fallback failed: {pptx_err}")
            return ""

    def _apply_toc_fallback(self, text: str) -> str:
        """Layer 3: Extract TOC entries if present and inject headers into matching body lines."""
        toc_pattern = re.compile(
            r"(?:Table\s+of\s+Contents|Contents|Mục\s+lục)[:\s]*\n((?:(?:\d+\.|\*|-|[A-Z]\.)\s+.*\n)+)",
            re.IGNORECASE,
        )
        match = toc_pattern.search(text)
        if not match:
            return text

        toc_lines = match.group(1).splitlines()
        candidate_titles = []
        for line in toc_lines:
            clean = re.sub(r"^[\d.*-]+\s*", "", line).strip()
            # Strip trailing page numbers and trailing dots/dashes
            clean = re.sub(r"(?:[\s._-]+|\.{2,})\s*\d+\s*$", "", clean).strip()
            if clean and len(clean) > 3:
                candidate_titles.append(clean)

        if not candidate_titles:
            return text

        # Inject ## before matching lines in the rest of the text
        body = text
        for title in candidate_titles:
            escaped = re.escape(title)
            body = re.sub(rf"^(?!#)\s*({escaped})\s*$", rf"## \1", body, flags=re.MULTILINE)

        return body

    def process_markdown(self, markdown_text: str) -> Tuple[List[Dict[str, Any]], Dict[str, List[str]]]:
        """Parse markdown hierarchy with 4-layer defense, hybrid sub-chunking, and pedagogical context injection.

        Returns:
            Tuple containing:
            - final_documents: List of dicts with 'page_content' and 'metadata'.
            - toc: Table of Contents tree (Chapter -> List[Section]).
        """
        print("[*] Section-Level Structural Parsing & TOC Extraction")
        final_documents: List[Dict[str, Any]] = []
        toc: Dict[str, List[str]] = {}

        # Layer 1 & 2 Defense: First run heuristic regex preprocessor so chapters and sections
        # are detected and preserved, then normalize natural slide boundaries without clobbering headings
        preprocessed = auto_inject_markdown_headers(markdown_text)
        preprocessed = handle_slide_boundaries(preprocessed)

        # Layer 3: TOC fallback if headers are still absent
        has_headers = bool(re.search(r"^\s*#{1,2}\s+", preprocessed, flags=re.MULTILINE))
        if not has_headers:
            preprocessed = self._apply_toc_fallback(preprocessed)
            has_headers = bool(re.search(r"^\s*#{1,2}\s+", preprocessed, flags=re.MULTILINE))

        markdown_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=HEADERS_TO_SPLIT_ON)
        splits = markdown_splitter.split_text(preprocessed)

        # Layer 4: Fallback chunking using RecursiveCharacterTextSplitter if no headers detected
        if not splits or not has_headers:
            print("[*] Layer 4 Active: Falling back to RecursiveCharacterTextSplitter")
            text_splitter = RecursiveCharacterTextSplitter(chunk_size=1200, chunk_overlap=150)
            raw_chunks = text_splitter.split_text(preprocessed if preprocessed.strip() else markdown_text)
            
            chapter = "General Chapter: Overview"
            toc[chapter] = []

            for idx, chunk in enumerate(raw_chunks):
                sec_name = f"Section {idx + 1}: Overview"
                if sec_name not in toc[chapter]:
                    toc[chapter].append(sec_name)

                context_prefix = f"[Pedagogical Context: {chapter} > {sec_name}]"
                final_documents.append({
                    "page_content": f"{context_prefix}\n\n{chunk.strip()}",
                    "metadata": {
                        "Chapter": chapter,
                        "Section": sec_name,
                        "seq_id": idx,
                    },
                })
            return final_documents, toc

        # Process structured splits and apply Hierarchical Sub-Chunking
        global_seq_id = 0
        for split in splits:
            content = split.page_content.strip()
            if not content:
                continue
            chapter = split.metadata.get("Chapter", "General Chapter: Introduction")
            section = split.metadata.get("Section") or f"{chapter} (Overview)"

            if chapter not in toc:
                toc[chapter] = []
            if section not in toc[chapter]:
                toc[chapter].append(section)

            # Sub-chunk sections > 1,200 words with 150-word overlap
            sub_chunks = sub_chunk_section(
                section_text=split.page_content,
                chapter=chapter,
                section=section,
                max_words=1200,
                target_chunk_words=700,
                overlap_words=150,
            )

            for sub_idx, sub_text in enumerate(sub_chunks):
                meta = split.metadata.copy()
                meta["Chapter"] = chapter
                meta["Section"] = section
                meta["seq_id"] = global_seq_id
                meta["sub_chunk_index"] = sub_idx
                meta["total_sub_chunks"] = len(sub_chunks)

                final_documents.append({
                    "page_content": sub_text.strip(),
                    "metadata": meta,
                })
                global_seq_id += 1

        print(f"[*] Successfully extracted {len(final_documents)} chunks and built the TOC tree.")
        return final_documents, toc

    def sub_chunk_section(
        self,
        section_text: str,
        chapter_name: str = "",
        section_name: str = "",
        chapter: str = "",
        section: str = "",
        max_words: int = 1200,
        target_chunk_words: int = 700,
        overlap_words: int = 150,
    ) -> List[str]:
        """Sub-chunk long section texts if they exceed the max_words threshold."""
        ch = chapter or chapter_name or "General Chapter"
        sec = section or section_name or "General Section"
        return sub_chunk_section(
            section_text=section_text,
            chapter=ch,
            section=sec,
            max_words=max_words,
            target_chunk_words=target_chunk_words,
            overlap_words=overlap_words,
        )

    def process_file(self, file_path: str) -> Tuple[List[Dict[str, Any]], Dict[str, List[str]]]:
        """Convert a document file on disk to markdown and parse its structure."""
        md_text = self.convert_to_markdown(file_path=file_path, filename=os.path.basename(file_path))
        return self.process_markdown(md_text)