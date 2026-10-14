"""Unit tests for deterministic PageBoundsValidator."""

import pytest
from core.schemas import (
    ChapterOrTopicNode,
    DocumentStructure,
    DocumentType,
    SectionNode,
    SubSectionNode,
)
from database.page_validator import PageBoundsValidator


@pytest.fixture
def validator():
    return PageBoundsValidator()


def test_sanitize_bounds_normal(validator):
    """Normal bounds within range should remain unchanged."""
    start, end = validator.sanitize_bounds(start_page=3, end_page=7, total_pages=10)
    assert start == 3
    assert end == 7


def test_sanitize_bounds_inverted(validator):
    """Inverted bounds (start > end) should be corrected so end >= start."""
    start, end = validator.sanitize_bounds(start_page=8, end_page=3, total_pages=10)
    assert start == 8
    assert end == 8


def test_sanitize_bounds_out_of_bounds(validator):
    """Negative or excessive page numbers should be clamped to 1..total_pages."""
    start, end = validator.sanitize_bounds(start_page=-5, end_page=100, total_pages=20)
    assert start == 1
    assert end == 20


def test_validate_and_sanitize_none(validator):
    """None structure returns None without error."""
    assert validator.validate_and_sanitize(None, 10) is None


def test_validate_and_sanitize_empty_hierarchy(validator):
    """Empty hierarchy structure preserves metadata and clamps total pages."""
    doc = DocumentStructure(
        document_type=DocumentType.PAPER,
        document_title="Empty Outline",
        total_pages=0,
        hierarchy=[],
    )
    result = validator.validate_and_sanitize(doc, total_pages=5)
    assert result.total_pages == 5
    assert result.hierarchy == []


def test_monotonic_continuity_enforcement(validator):
    """Non-monotonic sibling nodes (start_{i+1} < start_i) must be aligned forward."""
    doc = DocumentStructure(
        document_type=DocumentType.BOOK,
        document_title="Deep Learning Manual",
        total_pages=50,
        hierarchy=[
            ChapterOrTopicNode(
                name="Chapter 1: Basics",
                start_page=1,
                end_page=15,
                sections=[
                    SectionNode(title="1.1 Overview", start_page=5, end_page=10),
                    SectionNode(title="1.2 Retroactive", start_page=2, end_page=8),  # 2 < 5
                ],
            ),
            ChapterOrTopicNode(
                name="Chapter 2: Optimization",
                start_page=10,  # 10 < 15
                end_page=25,
                sections=[],
            ),
        ],
    )

    sanitized = validator.validate_and_sanitize(doc, total_pages=50)

    # Section 1.2 should have been clamped to at least section 1.1's start_page (5)
    sec1 = sanitized.hierarchy[0].sections[0]
    sec2 = sanitized.hierarchy[0].sections[1]
    assert sec2.start_page >= sec1.start_page
    assert sec2.start_page == 5
    assert sec2.end_page >= sec2.start_page

    # Chapter 2 should start at or after Chapter 1's start_page
    chap1 = sanitized.hierarchy[0]
    chap2 = sanitized.hierarchy[1]
    assert chap2.start_page >= chap1.start_page


def test_parent_envelopment_of_children(validator):
    """Parent chapters/sections must envelop their child sections/subsections."""
    doc = DocumentStructure(
        document_type=DocumentType.BOOK,
        document_title="AI Architecture",
        total_pages=100,
        hierarchy=[
            ChapterOrTopicNode(
                name="Chapter 1",
                start_page=10,  # hallucinated late
                end_page=12,    # hallucinated early
                sections=[
                    SectionNode(
                        title="1.1 Intro",
                        start_page=5,  # earlier than chapter start
                        end_page=15,   # later than chapter end
                        subsections=[
                            SubSectionNode(title="1.1.1 Detail", start_page=3, end_page=18)
                        ],
                    )
                ],
            )
        ],
    )

    sanitized = validator.validate_and_sanitize(doc, total_pages=100)
    chap = sanitized.hierarchy[0]
    sec = chap.sections[0]
    sub = sec.subsections[0]

    # Section must envelop subsection
    assert sec.start_page <= sub.start_page
    assert sec.end_page >= sub.end_page

    # Chapter must envelop section
    assert chap.start_page <= sec.start_page
    assert chap.end_page >= sec.end_page


def test_same_page_subsection_resolution(validator):
    """Subsections sharing the same page should be flagged with is_same_page=True."""
    doc = DocumentStructure(
        document_type=DocumentType.BOOK,
        document_title="Compact Algorithms",
        total_pages=20,
        hierarchy=[
            ChapterOrTopicNode(
                name="Chapter 1",
                start_page=1,
                end_page=5,
                sections=[
                    SectionNode(
                        title="1.1 Sorting",
                        start_page=3,
                        end_page=3,
                        subsections=[
                            SubSectionNode(title="1.1.1 QuickSort", start_page=3, end_page=3),
                            SubSectionNode(title="1.1.2 MergeSort", start_page=3, end_page=3),
                        ],
                    )
                ],
            )
        ],
    )

    sanitized = validator.validate_and_sanitize(doc, total_pages=20)
    sub1 = sanitized.hierarchy[0].sections[0].subsections[0]
    sub2 = sanitized.hierarchy[0].sections[0].subsections[1]

    assert sub1.is_same_page is True
    assert sub2.is_same_page is True


def test_bounds_clamping_to_total_pages(validator):
    """All page ranges exceeding total_pages should be clamped to total_pages."""
    doc = DocumentStructure(
        document_type=DocumentType.SLIDE,
        document_title="Lecture Decks",
        total_pages=10,
        hierarchy=[
            ChapterOrTopicNode(
                name="Topic 1",
                start_page=15,
                end_page=30,
                sections=[
                    SectionNode(title="Slide 1", start_page=18, end_page=45)
                ],
            )
        ],
    )

    sanitized = validator.validate_and_sanitize(doc, total_pages=10)
    chap = sanitized.hierarchy[0]
    sec = chap.sections[0]

    assert chap.start_page == 10
    assert chap.end_page == 10
    assert sec.start_page == 10
    assert sec.end_page == 10


def test_validate_and_sanitize_none_sections_safe(validator):
    """Chapter with sections=None should not raise TypeError."""
    doc = DocumentStructure.model_construct(
        document_type=DocumentType.BOOK,
        document_title="Safe Book",
        total_pages=10,
        hierarchy=[
            ChapterOrTopicNode.model_construct(
                name="Chapter 1",
                start_page=1,
                end_page=5,
                sections=None,
            )
        ],
    )
    sanitized = validator.validate_and_sanitize(doc, total_pages=10)
    assert sanitized is not None
    assert sanitized.hierarchy[0].sections == []


def test_section_is_same_page_resolution(validator):
    """Sibling sections sharing the same page should be flagged with is_same_page=True."""
    doc = DocumentStructure(
        document_type=DocumentType.PAPER,
        document_title="Two Column Paper",
        total_pages=5,
        hierarchy=[
            ChapterOrTopicNode(
                name="Main Content",
                start_page=1,
                end_page=5,
                sections=[
                    SectionNode(title="1. Introduction", start_page=1, end_page=1),
                    SectionNode(title="2. Related Work", start_page=1, end_page=1),
                    SectionNode(title="3. Methodology", start_page=2, end_page=2),
                ],
            )
        ],
    )
    sanitized = validator.validate_and_sanitize(doc, total_pages=5)
    sec1 = sanitized.hierarchy[0].sections[0]
    sec2 = sanitized.hierarchy[0].sections[1]
    sec3 = sanitized.hierarchy[0].sections[2]

    assert sec1.is_same_page is True
    assert sec2.is_same_page is True
    assert sec3.is_same_page is False


def test_multi_chapter_monotonicity_progression(validator):
    """Chapter 2 must not start before Chapter 1 start_page even if children have hallucinated bounds."""
    doc = DocumentStructure(
        document_type=DocumentType.BOOK,
        document_title="Comprehensive Text",
        total_pages=50,
        hierarchy=[
            ChapterOrTopicNode(
                name="Chapter 1: Foundations",
                start_page=10,
                end_page=20,
                sections=[
                    SectionNode(title="1.1 Overview", start_page=10, end_page=20),
                ],
            ),
            ChapterOrTopicNode(
                name="Chapter 2: Advanced Topics",
                start_page=5,  # Hallucinated early
                end_page=30,
                sections=[
                    SectionNode(title="2.1 Introduction", start_page=2, end_page=25),  # Hallucinated earlier than Ch1
                ],
            ),
        ],
    )
    sanitized = validator.validate_and_sanitize(doc, total_pages=50)
    chap1 = sanitized.hierarchy[0]
    chap2 = sanitized.hierarchy[1]

    assert chap2.start_page >= chap1.start_page
    assert chap2.sections[0].start_page >= chap2.start_page
    assert chap2.end_page >= chap2.sections[0].end_page
