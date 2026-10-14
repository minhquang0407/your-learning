"""Deterministic Page Bounds & Continuity Validator.

Ensures LLM-extracted document structures adhere to strict physical page boundaries,
monotonic ordering, parent envelopment, and same-page subsection resolution.
"""

from typing import Optional, Tuple
from core.schemas import DocumentStructure, ChapterOrTopicNode, SectionNode, SubSectionNode


class PageBoundsValidator:
    """Pure-logic validator for hierarchical document page ranges."""

    @staticmethod
    def sanitize_bounds(start_page: int, end_page: int, total_pages: int) -> Tuple[int, int]:
        """Clamp page bounds to 1 <= start <= end <= total_pages and fix inverted bounds."""
        total = max(1, total_pages)
        # Fix inverted bounds: if start > end, set end = start
        if start_page > end_page:
            end_page = start_page

        clamped_start = max(1, min(start_page, total))
        clamped_end = max(clamped_start, min(end_page, total))
        return clamped_start, clamped_end

    def validate_and_sanitize(
        self,
        structure: Optional[DocumentStructure],
        total_pages: int,
    ) -> Optional[DocumentStructure]:
        """Validate and sanitize a DocumentStructure in-place, returning the sanitized instance.

        Enforces:
        1. Hard bounds clamping: 1 <= start_page <= end_page <= total_pages.
        2. Inverted bounds fix: if start > end, end = start.
        3. Monotonic non-decreasing order: start_{i+1} >= start_i.
        4. Parent-child span integrity: parent envelops all child ranges.
        5. Same-page section and subsection resolution: marks is_same_page=True when multiple
           siblings share a single physical page.
        """
        if structure is None:
            return None

        total = max(1, total_pages or structure.total_pages)
        structure.total_pages = total

        if not structure.hierarchy:
            return structure

        # Pass 1: Initial clamp on every node and safe None-checks
        for chapter in structure.hierarchy:
            chapter.sections = chapter.sections or []
            chapter.start_page, chapter.end_page = self.sanitize_bounds(
                chapter.start_page, chapter.end_page, total
            )
            for section in chapter.sections:
                section.subsections = section.subsections or []
                section.start_page, section.end_page = self.sanitize_bounds(
                    section.start_page, section.end_page, total
                )
                for sub in section.subsections:
                    sub.start_page, sub.end_page = self.sanitize_bounds(
                        sub.start_page, sub.end_page, total
                    )

        # Pass 2: Bottom-Up Initial Parent Envelopment (expand parent if children report wider span)
        for chapter in structure.hierarchy:
            for section in chapter.sections:
                subsections = section.subsections or []
                if subsections:
                    min_sub = min(s.start_page for s in subsections)
                    max_sub = max(s.end_page for s in subsections)
                    section.start_page = min(section.start_page, min_sub)
                    section.end_page = max(section.end_page, max_sub)

            sections = chapter.sections or []
            if sections:
                min_sec = min(s.start_page for s in sections)
                max_sec = max(s.end_page for s in sections)
                chapter.start_page = min(chapter.start_page, min_sec)
                chapter.end_page = max(chapter.end_page, max_sec)

        # Pass 3: Top-Down Monotonic Continuity Enforcement (start_{i+1} >= start_i)
        chap_prev_start = 1
        for chapter in structure.hierarchy:
            if chapter.start_page < chap_prev_start:
                chapter.start_page = chap_prev_start
            if chapter.end_page < chapter.start_page:
                chapter.end_page = chapter.start_page
            chap_prev_start = chapter.start_page

            sec_prev_start = chapter.start_page
            for section in chapter.sections or []:
                if section.start_page < sec_prev_start:
                    section.start_page = sec_prev_start
                if section.end_page < section.start_page:
                    section.end_page = section.start_page
                sec_prev_start = section.start_page

                sub_prev_start = section.start_page
                for sub in section.subsections or []:
                    if sub.start_page < sub_prev_start:
                        sub.start_page = sub_prev_start
                    if sub.end_page < sub.start_page:
                        sub.end_page = sub.start_page
                    sub_prev_start = sub.start_page

        # Pass 4: Post-Shift Parent Envelopment Re-Verification
        for chapter in structure.hierarchy:
            for section in chapter.sections or []:
                subsections = section.subsections or []
                if subsections:
                    section.end_page = max(section.end_page, max(s.end_page for s in subsections))
            sections = chapter.sections or []
            if sections:
                chapter.end_page = max(chapter.end_page, max(s.end_page for s in sections))

        # Pass 5: Final hard bounds clamp to total_pages on all nodes
        for chapter in structure.hierarchy:
            chapter.start_page, chapter.end_page = self.sanitize_bounds(
                chapter.start_page, chapter.end_page, total
            )
            for section in chapter.sections or []:
                section.start_page, section.end_page = self.sanitize_bounds(
                    section.start_page, section.end_page, total
                )
                for sub in section.subsections or []:
                    sub.start_page, sub.end_page = self.sanitize_bounds(
                        sub.start_page, sub.end_page, total
                    )

        # Pass 6: Deterministic Same-Page Resolution for Subsections and Sections
        for chapter in structure.hierarchy:
            sections = chapter.sections or []
            if len(sections) > 1:
                for sec in sections:
                    overlap = any(
                        other is not sec and (
                            other.start_page <= sec.start_page <= other.end_page
                            or sec.start_page <= other.start_page <= sec.end_page
                        )
                        for other in sections
                    )
                    if overlap and sec.start_page == sec.end_page:
                        sec.is_same_page = True

            for section in sections:
                subsections = section.subsections or []
                if len(subsections) > 1:
                    for sub in subsections:
                        overlap = any(
                            other is not sub and (
                                other.start_page <= sub.start_page <= other.end_page
                                or sub.start_page <= other.start_page <= sub.end_page
                            )
                            for other in subsections
                        )
                        if overlap and sub.start_page == sub.end_page:
                            sub.is_same_page = True

        return structure
