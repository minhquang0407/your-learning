"""Unit tests for pedagogical relations and concept schemas.

Verifies:
- ConceptExtract and Concept Pydantic schemas.
- PedagogicalRelationType enum.
- Neo4jManager knowledge graph persistence for EXEMPLIFIES and APPLIED_IN.
"""

from unittest.mock import MagicMock
import pytest
from pydantic import ValidationError

from core.schemas import (
    Concept,
    ConceptExtract,
    PedagogicalRelation,
    PedagogicalRelationType,
)
from database.semantic_dag import Neo4jManager


def test_concept_extract_schema_validation():
    extract = ConceptExtract(
        name_en="Convolutional Neural Network",
        name_vn="Mạng nơ-ron tích chập",
        acronym="CNN",
        context_snippet="CNNs are widely used in computer vision.",
        source_location="slide:12",
    )
    assert extract.name_en == "Convolutional Neural Network"
    assert extract.name_vn == "Mạng nơ-ron tích chập"
    assert extract.acronym == "CNN"
    assert extract.source_location == "slide:12"


def test_concept_extract_minimal_and_invalid():
    # Only name_en is required
    minimal = ConceptExtract(name_en="Support Vector Machine")
    assert minimal.name_en == "Support Vector Machine"
    assert minimal.name_vn is None
    assert minimal.acronym is None

    # Missing name_en should raise ValidationError
    with pytest.raises(ValidationError):
        ConceptExtract()  # type: ignore


def test_concept_model_canonical_and_aliases():
    concept = Concept(
        id="cnn_node",
        canonical_name="Convolutional Neural Network",
        aliases=["CNN", "ConvNet", "Mạng nơ-ron tích chập"],
        source_locators=["lecture1.pdf::p4"],
        type="architecture",
        description="A specialized neural network for grid-like data.",
    )
    assert concept.canonical_name == "Convolutional Neural Network"
    assert len(concept.aliases) == 3
    assert "CNN" in concept.aliases
    assert concept.source_locators == ["lecture1.pdf::p4"]


def test_pedagogical_relation_type_enum():
    expected_relations = {
        "PREREQUISITE_OF",
        "RELATES_TO",
        "PART_OF",
        "DESCRIBES",
        "VERSUS",
        "EXEMPLIFIES",
        "APPLIED_IN",
    }
    actual_relations = {r.value for r in PedagogicalRelationType}
    assert actual_relations == expected_relations
    assert PedagogicalRelation == PedagogicalRelationType


def test_neo4j_save_knowledge_graph_persists_new_relations():
    manager = Neo4jManager.__new__(Neo4jManager)
    manager.is_connected = True
    manager.driver = MagicMock()

    mock_session = MagicMock()
    manager.driver.session.return_value.__enter__.return_value = mock_session

    nodes = [
        {
            "name": "Convolutional Neural Network",
            "canonical_name": "Convolutional Neural Network",
            "aliases": ["CNN", "ConvNet"],
            "type": "architecture",
            "description": "Grid processing network",
        },
        {
            "name": "Image Classification",
            "canonical_name": "Image Classification",
            "aliases": [],
            "type": "task",
            "description": "Visual task",
        },
        {
            "name": "ResNet",
            "canonical_name": "Residual Network",
            "aliases": ["ResNet"],
            "type": "model",
            "description": "Deep residual network",
        },
    ]

    edges = [
        {
            "source": "Convolutional Neural Network",
            "target": "Image Classification",
            "relation": "APPLIED_IN",
        },
        {
            "source": "ResNet",
            "target": "Convolutional Neural Network",
            "relation": "EXEMPLIFIES",
        },
        {
            "source": "ResNet",
            "target": "Image Classification",
            "relation": "NON_STANDARD_RELATION",  # Should fallback to RELATES_TO
        },
    ]

    manager.save_knowledge_graph(
        nodes=nodes,
        edges=edges,
        file_name="vision.md",
        chapter_name="Chapter 1",
        section_title="CNNs",
        main_entities=["Convolutional Neural Network"],
    )

    # Verify session run calls
    executed_queries = [call.args[0] for call in mock_session.run.call_args_list]

    # Verify nodes with canonical_name and aliases were merged
    assert any("canonical_name = $canonical_name" in q for q in executed_queries)
    assert any("aliases = [a IN coalesce(n.aliases, [])" in q for q in executed_queries)

    # Verify edges were created with allowed relations
    edge_queries = [q for q in executed_queries if "MERGE (c1)-[rel:" in q]
    assert len(edge_queries) == 3

    assert any("rel:APPLIED_IN" in q for q in edge_queries)
    assert any("rel:EXEMPLIFIES" in q for q in edge_queries)
    assert any("rel:RELATES_TO" in q for q in edge_queries)


def test_neo4j_save_knowledge_graph_keys_on_canonical_name():
    manager = Neo4jManager.__new__(Neo4jManager)
    manager.is_connected = True
    manager.driver = MagicMock()
    mock_session = MagicMock()
    manager.driver.session.return_value.__enter__.return_value = mock_session

    nodes = [
        {
            "name": "CNN",
            "canonical_name": "Convolutional Neural Network",
            "type": "architecture",
            "description": "Deep network",
        }
    ]
    edges = [
        {
            "source": "Convolutional Neural Network",
            "target": "Computer Vision",
            "relation": "APPLIED_IN",
        }
    ]

    manager.save_knowledge_graph(
        nodes=nodes,
        edges=edges,
        file_name="vision.md",
        chapter_name="Chapter 1",
        section_title="CNNs",
        main_entities=[],
    )

    # Verify node creation was keyed on canonical_name
    node_run_calls = [
        call.kwargs for call in mock_session.run.call_args_list if "MERGE (n:Concept {id: $id})" in call.args[0]
    ]
    assert len(node_run_calls) == 1
    assert node_run_calls[0]["id"] == "Convolutional Neural Network"
    assert "CNN" in node_run_calls[0]["aliases"]


def test_neo4j_manager_get_all_concepts():
    manager = Neo4jManager.__new__(Neo4jManager)
    manager.is_connected = True
    manager.driver = MagicMock()
    mock_session = MagicMock()
    manager.driver.session.return_value.__enter__.return_value = mock_session

    mock_record = {
        "id": "Convolutional Neural Network",
        "canonical_name": "Convolutional Neural Network",
        "aliases": ["CNN"],
        "description": "Grid processing network",
        "type": "architecture",
        "source_locators": ["doc1::ch1::sec1"],
    }
    mock_session.run.return_value = [mock_record]

    concepts = manager.get_all_concepts()
    assert len(concepts) == 1
    assert concepts[0]["canonical_name"] == "Convolutional Neural Network"
    assert concepts[0]["aliases"] == ["CNN"]

