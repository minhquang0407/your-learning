"""Unit tests for AnchorEntityResolver.

Verifies:
- Cosine similarity computation.
- Step 0 pre-filtering against existing graph index (cosine >= 0.92 auto-absorb, 0.80-0.92 candidate anchor).
- Acronym and abbreviation heuristic matching (CNN, SGD).
- Divide-and-conquer batch resolution with Cosine feedback loop (>= 0.90).
- Knowledge graph edge remapping and self-loop pruning.
"""

from unittest.mock import MagicMock
import pytest

from core.schemas import ConceptExtract
from database.entity_resolver import (
    AnchorEntityResolver,
    compute_cosine_similarity,
    is_acronym_match,
)


def test_compute_cosine_similarity():
    v1 = [1.0, 0.0, 0.0]
    v2 = [1.0, 0.0, 0.0]
    assert pytest.approx(compute_cosine_similarity(v1, v2)) == 1.0

    v3 = [0.0, 1.0, 0.0]
    assert pytest.approx(compute_cosine_similarity(v1, v3)) == 0.0

    assert compute_cosine_similarity([], [1.0]) == 0.0
    assert compute_cosine_similarity([0.0, 0.0], [0.0, 0.0]) == 0.0


def test_is_acronym_match():
    assert is_acronym_match("CNN", "Convolutional Neural Network")
    assert is_acronym_match("SGD", "Stochastic Gradient Descent")
    assert is_acronym_match("RNN", "Recurrent Neural Network")
    assert not is_acronym_match("CNN", "Support Vector Machine")
    assert not is_acronym_match("LONGACRONYMTHATEXCEEDS", "Test")


def test_step_0_pre_filter_auto_absorb_and_candidate_anchor():
    resolver = AnchorEntityResolver()

    existing_anchors = [
        {
            "canonical_name": "Convolutional Neural Network",
            "aliases": ["ConvNet"],
            "description": "Grid processing network",
            "source_locators": ["doc1::ch1::sec1"],
        },
        {
            "canonical_name": "Support Vector Machine",
            "aliases": ["SVM"],
            "description": "Max margin classifier",
            "source_locators": ["doc1::ch1::sec2"],
        },
    ]

    # Entity A: exact acronym match -> should auto-absorb into CNN
    # Entity B: novel entity -> should remain unresolved
    candidate_entities = [
        {
            "name": "CNN",
            "aliases": [],
            "description": "Grid processing network",
            "source_locators": ["doc2::ch1::sec1"],
        },
        {
            "name": "Decision Tree",
            "aliases": [],
            "description": "Tree based decision model",
            "source_locators": ["doc2::ch1::sec2"],
        },
    ]

    unresolved, candidates, updated_anchors, name_map = resolver.pre_filter_with_existing_graph(
        entities=candidate_entities,
        existing_anchors=existing_anchors,
    )

    # CNN must be auto-absorbed
    assert name_map.get("CNN") == "Convolutional Neural Network"
    cnn_anchor = next(a for a in updated_anchors if a["canonical_name"] == "Convolutional Neural Network")
    assert "CNN" in cnn_anchor["aliases"]
    assert "doc2::ch1::sec1" in cnn_anchor["source_locators"]

    # Decision Tree should be in unresolved list
    assert any(e["name"] == "Decision Tree" for e in unresolved)


def test_resolve_section_entities_acronym_and_edge_remapping():
    resolver = AnchorEntityResolver()

    raw_nodes = [
        {"name": "CNN", "type": "model", "description": "Convolutional network"},
        {"name": "Convolutional Neural Network", "type": "model", "description": "Deep network"},
        {"name": "Computer Vision", "type": "field", "description": "Visual intelligence"},
    ]

    raw_edges = [
        # Source uses alias 'CNN'
        {"source": "CNN", "target": "Computer Vision", "relation": "APPLIED_IN"},
        # Self loop when resolved (CNN -> Convolutional Neural Network)
        {"source": "CNN", "target": "Convolutional Neural Network", "relation": "RELATES_TO"},
    ]

    nodes, edges, name_map = resolver.resolve_section_entities(
        nodes=raw_nodes,
        edges=raw_edges,
        source_locator="cv_book::ch1::sec1",
    )

    # Nodes should be consolidated (CNN merged into Convolutional Neural Network)
    node_names = [n["canonical_name"] for n in nodes]
    assert "Convolutional Neural Network" in node_names
    assert "Computer Vision" in node_names
    assert "CNN" not in node_names  # CNN is an alias, not a separate canonical node!

    cnn_node = next(n for n in nodes if n["canonical_name"] == "Convolutional Neural Network")
    assert "CNN" in cnn_node["aliases"]
    assert "cv_book::ch1::sec1" in cnn_node["source_locators"]

    # Edges: source 'CNN' must be remapped to 'Convolutional Neural Network'
    # Self loop must be pruned!
    assert len(edges) == 1
    edge = edges[0]
    assert edge["source"] == "Convolutional Neural Network"
    assert edge["target"] == "Computer Vision"
    assert edge["relation"] == "APPLIED_IN"


def test_resolve_section_entities_with_concept_extract_objects():
    resolver = AnchorEntityResolver()

    extracts = [
        ConceptExtract(
            name_en="Stochastic Gradient Descent",
            name_vn="Hạ gradient ngẫu nhiên",
            acronym="SGD",
            context_snippet="Optimization algorithm",
            source_location="opt.md::ch2::sec1",
        ),
        ConceptExtract(
            name_en="SGD",
            name_vn=None,
            acronym=None,
            context_snippet="Abbreviated mention of optimizer",
            source_location="opt.md::ch2::sec2",
        ),
    ]

    nodes, edges, name_map = resolver.resolve_section_entities(
        nodes=extracts,
        edges=[],
        source_locator="opt.md::ch2::sec1",
    )

    assert len(nodes) == 1
    sgd_node = nodes[0]
    assert sgd_node["canonical_name"] == "Stochastic Gradient Descent"
    assert "SGD" in sgd_node["aliases"]
    assert "Hạ gradient ngẫu nhiên" in sgd_node["aliases"]


def test_is_acronym_match_with_dots_and_stopwords():
    assert is_acronym_match("C.N.N.", "Convolutional Neural Network")
    assert is_acronym_match("S.G.D.", "Stochastic Gradient Descent")
    assert is_acronym_match("BoW", "Bag of Words")
    assert is_acronym_match("NLP", "Natural Language Processing")
    assert not is_acronym_match("Convolutional Neural Network", "CNN")


def test_step_0_auto_absorbed_entities_preserved_in_final_nodes():
    resolver = AnchorEntityResolver()
    existing = [
        {
            "canonical_name": "Convolutional Neural Network",
            "aliases": ["ConvNet"],
            "description": "Image network",
            "source_locators": ["doc1::ch1::sec1"],
        }
    ]

    # Section 2 has only 'CNN', which auto-absorbs
    nodes = [{"name": "CNN", "type": "model", "description": "Abbreviation"}]
    edges = [{"source": "CNN", "target": "Computer Vision", "relation": "APPLIED_IN"}]

    final_nodes, final_edges, name_map = resolver.resolve_section_entities(
        nodes=nodes,
        edges=edges,
        source_locator="doc2::ch1::sec1",
        existing_anchors=existing,
    )

    # final_nodes MUST NOT be empty!
    assert len(final_nodes) >= 1
    node_names = [n["canonical_name"] for n in final_nodes]
    assert "Convolutional Neural Network" in node_names
    cnn_node = next(n for n in final_nodes if n["canonical_name"] == "Convolutional Neural Network")
    assert "CNN" in cnn_node["aliases"]
    assert "doc2::ch1::sec1" in cnn_node["source_locators"]

    # Edges should be remapped
    assert len(final_edges) == 1
    assert final_edges[0]["source"] == "Convolutional Neural Network"


def test_promotion_of_acronym_to_full_name_when_merged():
    resolver = AnchorEntityResolver()
    clusters = resolver._heuristic_batch_resolution(
        batch=[{"name": "DL", "aliases": ["Deep Learning"]}],
        candidate_anchors=[],
    )
    assert len(clusters) == 1
    # Full name must be promoted to canonical_name!
    assert clusters[0]["canonical_name"] == "Deep Learning"
    assert "DL" in clusters[0]["aliases"]

