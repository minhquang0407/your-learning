"""Unit tests for document processor upgrade.

Verifies:
- 4-layer header defense:
  1. Slide boundaries handling.
  2. Heuristic regex header injection.
  3. Table of contents fallback.
  4. RecursiveCharacterTextSplitter fallback.
- Hierarchical hybrid sub-chunking and context prefix injection.
- Multi-format ingestion and graceful fallbacks.
"""

from unittest.mock import MagicMock, patch
import pytest

from database.document_processor import (
    MathAwareDocumentProcessor,
    auto_inject_markdown_headers,
    handle_slide_boundaries,
    sub_chunk_section,
)


def test_auto_inject_markdown_headers_chapters_and_sections():
    raw = """Chapter 1: Foundations of Deep Learning
This is the introductory paragraph.

1.1 Neural Networks Overview
Neurons and synapses form the basic computational units.

1.1.2 Activation Functions
ReLU is commonly used.

II. Backpropagation Algorithm
Gradient descent calculates parameter updates.

Regular text mentioning Chapter 1 in the middle should not be modified.
"""
    result = auto_inject_markdown_headers(raw)
    lines = result.splitlines()

    assert "# Chapter 1: Foundations of Deep Learning" in lines
    assert "## 1.1 Neural Networks Overview" in lines
    assert "## 1.1.2 Activation Functions" in lines
    assert "## II. Backpropagation Algorithm" in lines
    assert "Regular text mentioning Chapter 1 in the middle should not be modified." in lines


def test_auto_inject_markdown_headers_vietnamese_and_existing():
    raw = """# Already Level One Header
## 1.0 Already Level Two Header
Chương 2: Đạo hàm và Tối ưu hoá
Mục 1: Cực trị của hàm số
"""
    result = auto_inject_markdown_headers(raw)
    lines = result.splitlines()

    # Pre-existing markdown headers must remain untouched
    assert "# Already Level One Header" in lines
    assert "## 1.0 Already Level Two Header" in lines
    # Vietnamese numbering
    assert "# Chương 2: Đạo hàm và Tối ưu hoá" in lines
    assert "## Mục 1: Cực trị của hàm số" in lines


def test_handle_slide_boundaries():
    slide_text = """<!-- slide: 1 -->
Linear Regression Concepts
Introduction to linear models and loss functions.

<!-- slide: 2 -->
Cost Function Minimization
Using mean squared error.
"""
    result = handle_slide_boundaries(slide_text)
    assert "# Presentation Slides" in result
    assert "## Slide 1" in result
    assert "## Slide 2" in result


def test_sub_chunk_section_short_text():
    short_text = "This is a short section with only a few words."
    chunks = sub_chunk_section(
        section_text=short_text,
        chapter="Chapter 1: Intro",
        section="1.1 Overview",
        max_words=1200,
    )
    assert len(chunks) == 1
    assert chunks[0].startswith("[Pedagogical Context: Chapter 1: Intro > 1.1 Overview]\n\n")
    assert "This is a short section with only a few words." in chunks[0]


def test_sub_chunk_section_long_text_overlap():
    words = [f"word{i}" for i in range(1500)]
    long_text = " ".join(words)

    chunks = sub_chunk_section(
        section_text=long_text,
        chapter="Chapter 2: Scaling",
        section="2.1 Large Corpora",
        max_words=1200,
        target_chunk_words=700,
        overlap_words=150,
    )

    # 1500 words with step 550 yields 3 chunks (0-700, 550-1250, 1100-1500)
    assert len(chunks) >= 2
    for chunk in chunks:
        assert chunk.startswith("[Pedagogical Context: Chapter 2: Scaling > 2.1 Large Corpora]\n\n")

    # Verify overlap: words around index 600 should appear in chunk 0 and chunk 1
    assert "word600" in chunks[0]
    assert "word600" in chunks[1]


def test_process_markdown_full_pipeline():
    processor = MathAwareDocumentProcessor()
    text = """Chapter 1: Introduction to AI
This is overview content.

1.1 Machine Learning
Machine learning learns patterns from data.

1.2 Deep Learning
Deep learning uses multi-layer neural networks.
"""
    documents, toc = processor.process_markdown(text)

    assert len(documents) >= 2
    assert "Chapter 1: Introduction to AI" in toc
    assert "1.1 Machine Learning" in toc["Chapter 1: Introduction to AI"]
    assert "1.2 Deep Learning" in toc["Chapter 1: Introduction to AI"]

    # Check pedagogical context prefix
    for doc in documents:
        assert "[Pedagogical Context:" in doc["page_content"]
        assert "metadata" in doc
        assert "Chapter" in doc["metadata"]
        assert "Section" in doc["metadata"]


def test_process_markdown_fallback_layer_4():
    processor = MathAwareDocumentProcessor()
    # Raw plain text without any markdown headers or numbers
    plain_text = (
        "In artificial intelligence, agents perceive their environment through sensors "
        "and act upon that environment through actuators. A rational agent is one that "
        "acts so as to achieve the best outcome or, when there is uncertainty, the best expected outcome."
    )
    documents, toc = processor.process_markdown(plain_text)

    assert len(documents) >= 1
    assert "General Chapter: Overview" in toc
    assert "Section 1: Overview" in toc["General Chapter: Overview"]
    assert "[Pedagogical Context: General Chapter: Overview > Section 1: Overview]" in documents[0]["page_content"]


def test_convert_to_markdown_plain_text_and_markdown():
    processor = MathAwareDocumentProcessor()
    md_content = "# Title\n\nContent"
    result = processor.convert_to_markdown(content_or_bytes=md_content, filename="doc.md")
    assert result == md_content

    raw_bytes = b"# Byte Title\n\nByte Content"
    result_bytes = processor.convert_to_markdown(file_bytes=raw_bytes, filename="doc.txt")
    assert result_bytes == "# Byte Title\n\nByte Content"


def test_convert_to_markdown_docx_fallback():
    processor = MathAwareDocumentProcessor()
    with patch("docx.Document") as mock_docx:
        p1 = MagicMock()
        p1.text = "Heading Text"
        p1.style.name = "Heading 1"
        p2 = MagicMock()
        p2.text = "Paragraph text."
        p2.style.name = "Normal"
        mock_docx.return_value.paragraphs = [p1, p2]

        fallback_res = processor._parse_docx_fallback(file_bytes=b"dummy docx bytes", file_path=None)
        assert "# Heading Text" in fallback_res
        assert "Paragraph text." in fallback_res

        # Test through convert_to_markdown when markitdown fails
        with patch("markitdown.MarkItDown.convert", side_effect=Exception("MarkItDown failed")):
            result = processor.convert_to_markdown(file_bytes=b"dummy docx bytes", filename="lecture.docx")
            assert "# Heading Text" in result
            assert "Paragraph text." in result


def test_auto_inject_markdown_headers_roman_and_dots():
    raw = """Chapter 1. Foundations of AI
Intro text.

Chapter IV: Attention Mechanisms
Attention is all you need.

Section 1.1: Convolutions
CNN details.

Section 2 - Recurrent Units
RNN details.
"""
    result = auto_inject_markdown_headers(raw)
    lines = result.splitlines()

    assert "# Chapter 1. Foundations of AI" in lines
    assert "# Chapter IV: Attention Mechanisms" in lines
    assert "## Section 1.1: Convolutions" in lines
    assert "## Section 2 - Recurrent Units" in lines


def test_handle_slide_boundaries_preamble_and_alt_syntax():
    text = """# Main Presentation Title
This is preamble text before the first slide.

--- slide: 5 ---
Slide Five Title
Slide Five Body

--- slide ---
Slide Six Title
Slide Six Body

<!-- slide: 7 -->
Slide Seven Title
### Subsection inside slide
Detail note.
"""
    result = handle_slide_boundaries(text)
    # Preamble should not become Slide 1
    assert "This is preamble text before the first slide." in result
    assert "## Slide 5: Slide Five Title" in result
    assert "## Slide 6: Slide Six Title" in result
    assert "## Slide 7: Slide Seven Title" in result
    assert "### Subsection inside slide" in result


def test_sub_chunk_section_preserves_multiline_formatting_and_empty():
    assert sub_chunk_section("", "Ch1", "Sec1") == []
    assert sub_chunk_section("   \n\n  ", "Ch1", "Sec1") == []

    multiline_body = """Here is python code:
```python
def compute(x):
    return x * 2
```
And LaTeX formula:
$$
E = mc^2
$$
""" + ("word " * 1400)

    chunks = sub_chunk_section(multiline_body, "Chapter 1", "Section 1", max_words=1200)
    assert len(chunks) >= 2
    # Verify multiline code block wasn't collapsed to single-line spaces
    first_chunk = chunks[0]
    assert "```python\ndef compute(x):\n    return x * 2\n```" in first_chunk
    assert "$$\nE = mc^2\n$$" in first_chunk


def test_apply_toc_fallback_with_page_numbers():
    processor = MathAwareDocumentProcessor()
    doc = """Table of Contents:
1. Introduction ..... 1
2. Deep Architectures ..... 15

Introduction
Here we introduce deep learning.

Deep Architectures
Here we discuss layers.
"""
    result = processor._apply_toc_fallback(doc)
    assert "## Introduction" in result
    assert "## Deep Architectures" in result

