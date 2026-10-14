"""Gemini Multimodal Document Structure Extractor.

Extracts hierarchical document structure (PAPER, BOOK, SLIDE) directly from PDF bytes
using the google.genai SDK with structured JSON schemas.
"""

import logging
import os
import re
from typing import Any, Optional
from config.settings import settings
from core.schemas import DocumentStructure

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert document layout and academic curriculum analyzer.
Analyze the attached PDF document thoroughly.

Your objectives:
1. Classify the document_type into exactly one of:
   - 'SLIDE': Presentation slides, lecture slide decks, or keynotes.
   - 'PAPER': Academic papers, journal articles, technical reports, conference preprints.
   - 'BOOK': Textbooks, comprehensive coursebooks, manuals, multi-chapter books.
2. Extract the canonical document_title.
3. Detect the total_pages (1-based physical PDF pages).
4. Provide a concise 2-3 sentence pedagogical summary of the core subject matter.
5. Extract the complete hierarchical outline tree:
   - For 'SLIDE':
     * Each ChapterOrTopicNode represents a major Topic or Module.
     * Each SectionNode represents an atomic Slide (e.g. 'Slide 1: Introduction', 'Slide 2: Background') with exact 1-based start_page and end_page (typically start_page == end_page).
   - For 'PAPER':
     * Each ChapterOrTopicNode represents a Major Section (e.g. '1. Introduction', '2. Methodology', '3. Results').
     * SectionNodes represent secondary subsections (e.g. '2.1 Dataset', '2.2 Architecture').
   - For 'BOOK':
     * Each ChapterOrTopicNode represents a Chapter (e.g. 'Chapter 1: Foundations of Deep Learning').
     * Each SectionNode represents a Section (e.g. '1.1 Optimization Algorithms').
     * Each SubSectionNode represents a Subsection (e.g. '1.1.1 Stochastic Gradient Descent'). You MUST drill down to the subsection level for books.

Critical constraints:
- All page numbers must be 1-based physical PDF page numbers matching the document layout.
- Ensure 1 <= start_page <= end_page <= total_pages.
- Never invent sections or hallucinate non-existent page boundaries.
"""


class GeminiStructureExtractor:
    """Multimodal structure extractor leveraging Gemini Flash and structured schemas."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = "gemini-2.5-flash",
        client: Optional[Any] = None,
    ):
        """Initialize the extractor with optional API key, model name, or pre-configured client."""
        self.api_key = (
            api_key
            or getattr(settings, "google_api_key", "")
            or os.environ.get("GOOGLE_API_KEY", "")
            or os.environ.get("GEMINI_API_KEY", "")
        )
        self.model_name = model_name
        self._client = client

    def _get_client(self) -> Optional[Any]:
        """Obtain or initialize the google.genai Client."""
        if self._client is not None:
            return self._client
        key = str(self.api_key or os.environ.get("GOOGLE_API_KEY", "") or os.environ.get("GEMINI_API_KEY", "")).strip()
        if not key:
            return None
        try:
            from google import genai
            self._client = genai.Client(api_key=key)
            return self._client
        except Exception as exc:
            logger.warning(
                f"[GeminiStructureExtractor] Failed to initialize google.genai Client: {exc}"
            )
            return None

    def extract_structure(
        self,
        file_bytes: bytes,
        total_pages: Optional[int] = None,
    ) -> Optional[DocumentStructure]:
        """Extract hierarchical document outline from PDF bytes via Gemini multimodal vision.

        Returns:
            DocumentStructure if extraction succeeds; None if API key is missing,
            network fails, or quota (429) is exceeded.
        """
        if not file_bytes:
            logger.warning("[GeminiStructureExtractor] Empty PDF bytes provided.")
            return None

        client = self._get_client()
        if client is None:
            logger.info(
                "[GeminiStructureExtractor] No Google API key configured or client unavailable. Gracefully falling back to local processor."
            )
            return None

        try:
            from google.genai import types

            pdf_part = types.Part.from_bytes(data=file_bytes, mime_type="application/pdf")
            prompt = SYSTEM_PROMPT
            if total_pages and total_pages > 0:
                prompt += f"\nNote: The physical PDF has {total_pages} total pages."

            config = types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=DocumentStructure,
                temperature=0.0,
            )

            logger.info(
                f"[GeminiStructureExtractor] Calling {self.model_name} for multimodal document structure extraction..."
            )
            response = client.models.generate_content(
                model=self.model_name,
                contents=[pdf_part, prompt],
                config=config,
            )

            # Retrieve structured result
            if hasattr(response, "parsed") and response.parsed is not None:
                if isinstance(response.parsed, DocumentStructure):
                    return response.parsed
                if isinstance(response.parsed, dict):
                    return DocumentStructure.model_validate(response.parsed)

            if hasattr(response, "text") and response.text:
                clean_text = response.text.strip()
                if clean_text.startswith("```"):
                    clean_text = re.sub(r"^```(?:json)?\s*", "", clean_text)
                    clean_text = re.sub(r"\s*```$", "", clean_text)
                return DocumentStructure.model_validate_json(clean_text)

            logger.warning(
                "[GeminiStructureExtractor] Response did not contain parsed DocumentStructure or text."
            )
            return None

        except Exception as exc:
            logger.warning(
                f"[GeminiStructureExtractor] Error during multimodal extraction: {exc}. Gracefully falling back to local processor."
            )
            return None
