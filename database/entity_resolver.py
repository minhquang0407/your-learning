"""Anchor Entity Resolution Engine.

Implements Method 1: Anchor-based clustering algorithm for entity deduplication,
multilingual alignment (EN/VN), and alias harmonization across curriculum sections.
"""

import json
import math
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from core.schemas import Concept, ConceptExtract


def compute_cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """Compute cosine similarity between two numeric vectors."""
    if not vec1 or not vec2 or len(vec1) != len(vec2):
        return 0.0
    dot = sum(a * b for a, b in zip(vec1, vec2))
    norm1 = math.sqrt(sum(a * a for a in vec1))
    norm2 = math.sqrt(sum(b * b for b in vec2))
    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0
    return dot / (norm1 * norm2)


def is_acronym_match(short_name: str, long_name: str) -> bool:
    """Check if short_name is an acronym abbreviation of long_name.

    Example: 'CNN' or 'C.N.N.' matches 'Convolutional Neural Network'.
    """
    s_raw = short_name.strip()
    l_raw = long_name.strip()
    if not s_raw or not l_raw or len(s_raw) >= len(l_raw):
        return False

    # Normalize short name by stripping punctuation/dots
    s = re.sub(r"[^A-Za-z0-9]", "", s_raw).upper()
    if not s or len(s) > 8:
        return False

    # Extract uppercase initials of words
    words = re.findall(r"[A-Za-z0-9]+", l_raw)
    if not words or len(words) < len(s):
        return False

    initials = "".join(w[0].upper() for w in words)
    if s == initials:
        return True

    # Check excluding common grammatical stopwords
    stopwords = {"and", "of", "the", "in", "for", "with", "to", "a", "an"}
    sig_words = [w for w in words if w.lower() not in stopwords]
    if sig_words:
        sig_initials = "".join(w[0].upper() for w in sig_words)
        if s == sig_initials:
            return True

    # Check hyphenated words or common compound structures
    alt_initials = "".join(w[0].upper() for w in words[: len(s)])
    return s == alt_initials


class AnchorEntityResolver:
    """Anchor-based entity resolution engine implementing Method 1 clustering.

    Harmonizes entity duplicates, acronyms, and multilingual variants into canonical graph nodes.
    """

    def __init__(
        self,
        vector_store: Optional[Any] = None,
        graph_store: Optional[Any] = None,
        llm_service: Optional[Any] = None,
        embed_model: Optional[Any] = None,
        auto_absorb_threshold: float = 0.92,
        candidate_anchor_threshold: float = 0.80,
        feedback_loop_threshold: float = 0.90,
        batch_size: int = 15,
    ):
        self.vector_store = vector_store
        self.graph_store = graph_store
        self.llm_service = llm_service
        self.auto_absorb_threshold = auto_absorb_threshold
        self.candidate_anchor_threshold = candidate_anchor_threshold
        self.feedback_loop_threshold = feedback_loop_threshold
        self.batch_size = batch_size
        self._accumulated_anchors: List[Dict[str, Any]] = []

        if embed_model is not None:
            self.embed_model = embed_model
        elif vector_store is not None and hasattr(vector_store, "embed_model"):
            self.embed_model = vector_store.embed_model
        else:
            try:
                from langchain_community.embeddings.fastembed import FastEmbedEmbeddings

                self.embed_model = FastEmbedEmbeddings(
                    model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
                )
            except Exception:
                self.embed_model = None

    def get_embedding(self, text: str) -> List[float]:
        """Compute normalized vector embedding for a text snippet."""
        clean_text = text.strip()
        if not clean_text:
            return [0.0] * 64

        if self.embed_model is not None:
            try:
                if hasattr(self.embed_model, "embed_query"):
                    return self.embed_model.embed_query(clean_text)
                elif hasattr(self.embed_model, "embed_documents"):
                    return self.embed_model.embed_documents([clean_text])[0]
            except Exception as e:
                print(f"[AnchorEntityResolver] Embedding model query error: {e}. Using deterministic fallback.")

        # Deterministic character-ngram hashing fallback (128 dimensions)
        return self._fallback_embedding(clean_text)

    def _fallback_embedding(self, text: str, dim: int = 128) -> List[float]:
        """Deterministic lightweight character n-gram embedding fallback."""
        vec = [0.0] * dim
        lower_text = f" {text.lower()} "
        for i in range(len(lower_text) - 2):
            trigram = lower_text[i : i + 3]
            h = hash(trigram) % dim
            vec[h] += 1.0

        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            return [v / norm for v in vec]
        return vec

    def _normalize_entity_dict(self, entity: Any) -> Dict[str, Any]:
        """Normalize entity representation into a standard dictionary."""
        if isinstance(entity, ConceptExtract):
            canonical = entity.name_en.strip()
            aliases = []
            if entity.name_vn:
                aliases.append(entity.name_vn.strip())
            if entity.acronym:
                aliases.append(entity.acronym.strip())
            return {
                "name": canonical,
                "canonical_name": canonical,
                "aliases": aliases,
                "type": "concept",
                "description": entity.context_snippet,
                "source_locators": [entity.source_location] if entity.source_location else [],
            }
        elif isinstance(entity, Concept):
            canonical = entity.canonical_name or entity.name or entity.id or ""
            return {
                "name": canonical,
                "canonical_name": canonical,
                "aliases": list(entity.aliases),
                "type": entity.type,
                "description": entity.description,
                "source_locators": list(entity.source_locators),
            }
        elif isinstance(entity, dict):
            name = str(entity.get("name") or entity.get("canonical_name") or entity.get("id") or "").strip()
            canonical = str(entity.get("canonical_name") or name).strip()
            aliases = entity.get("aliases", [])
            if not isinstance(aliases, list):
                aliases = [str(aliases)]
            return {
                "name": name,
                "canonical_name": canonical,
                "aliases": [str(a).strip() for a in aliases if str(a).strip()],
                "type": str(entity.get("type", "concept")),
                "description": str(entity.get("description", "")),
                "source_locators": list(entity.get("source_locators", [])),
            }
        else:
            name_str = str(entity).strip()
            return {
                "name": name_str,
                "canonical_name": name_str,
                "aliases": [],
                "type": "concept",
                "description": "",
                "source_locators": [],
            }

    def pre_filter_with_existing_graph(
        self,
        entities: List[Dict[str, Any]],
        existing_anchors: List[Dict[str, Any]],
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, str]]:
        """Step 0: Pre-filter candidate entities against existing graph anchors.

        Rules:
        - Cosine >= 0.92: Auto-absorbs into existing node aliases.
        - 0.80 <= Cosine < 0.92: Marks existing node as candidate anchor for LLM arbitration.
        - Cosine < 0.80: Retained as unassigned entity candidate.

        Returns:
            Tuple of (unresolved_entities, candidate_anchors, updated_existing_anchors, name_map)
        """
        unresolved_entities: List[Dict[str, Any]] = []
        candidate_anchors_set: Dict[str, Dict[str, Any]] = {}
        name_map: Dict[str, str] = {}

        if not existing_anchors:
            return entities, [], existing_anchors, name_map

        # Pre-compute embeddings for existing anchors
        anchor_embeddings = [
            (
                anchor,
                self.get_embedding(
                    f"{anchor.get('canonical_name', '')} {' '.join(anchor.get('aliases', []))} {anchor.get('description', '')}"
                ),
            )
            for anchor in existing_anchors
        ]

        for ent in entities:
            ent_name = ent.get("canonical_name") or ent.get("name", "")
            ent_text = f"{ent_name} {' '.join(ent.get('aliases', []))} {ent.get('description', '')}"
            ent_vec = self.get_embedding(ent_text)

            best_sim = -1.0
            best_anchor: Optional[Dict[str, Any]] = None

            for anchor, anchor_vec in anchor_embeddings:
                sim = compute_cosine_similarity(ent_vec, anchor_vec)
                # Check acronym match
                if is_acronym_match(ent_name, anchor.get("canonical_name", "")) or is_acronym_match(
                    anchor.get("canonical_name", ""), ent_name
                ):
                    sim = max(sim, 0.95)

                if sim > best_sim:
                    best_sim = sim
                    best_anchor = anchor

            if best_sim >= self.auto_absorb_threshold and best_anchor is not None:
                # Auto-absorb into existing node aliases
                canonical_name = best_anchor.get("canonical_name", "")
                name_map[ent_name] = canonical_name
                if ent.get("name"):
                    name_map[ent["name"]] = canonical_name
                for a in ent.get("aliases", []):
                    name_map[a] = canonical_name

                # Add aliases
                alias_set = set(best_anchor.get("aliases", []))
                if ent_name != canonical_name:
                    alias_set.add(ent_name)
                for a in ent.get("aliases", []):
                    alias_set.add(a)
                best_anchor["aliases"] = [a for a in alias_set if a != canonical_name]

                # Merge source locators
                locs = set(best_anchor.get("source_locators", []))
                for loc in ent.get("source_locators", []):
                    locs.add(loc)
                best_anchor["source_locators"] = list(locs)

            elif best_sim >= self.candidate_anchor_threshold and best_anchor is not None:
                # Mark as candidate anchor for LLM arbitration
                anchor_id = best_anchor.get("canonical_name", "")
                candidate_anchors_set[anchor_id] = best_anchor
                unresolved_entities.append(ent)
            else:
                unresolved_entities.append(ent)

        return (
            unresolved_entities,
            list(candidate_anchors_set.values()),
            existing_anchors,
            name_map,
        )

    def _resolve_batch_with_llm(
        self,
        batch: List[Dict[str, Any]],
        candidate_anchors: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Prompt LLM for merge/split decisions on a batch of entities."""
        if not self.llm_service:
            return self._heuristic_batch_resolution(batch, candidate_anchors)

        prompt = (
            "You are an Academic Entity Resolution Engine.\n"
            "Analyze the following batch of concept candidates and candidate anchors.\n"
            "Task: Determine which entities refer to the exact same academic concept "
            "(including English canonical name, Vietnamese translations, and abbreviations/acronyms).\n"
            "Group equivalent mentions into a canonical concept with:\n"
            "- 'canonical_name': Canonical English name (e.g. 'Convolutional Neural Network')\n"
            "- 'aliases': List of alternative names, Vietnamese equivalents, and acronyms (e.g. ['CNN', 'Mạng nơ-ron tích chập'])\n"
            "- 'type': Category string (e.g. 'architecture', 'algorithm', 'concept')\n"
            "- 'description': One-sentence definition\n"
            "Distinct concepts MUST NOT be merged.\n\n"
            f"Candidate Entities:\n{json.dumps(batch, ensure_ascii=False)}\n\n"
            f"Candidate Anchors:\n{json.dumps(candidate_anchors, ensure_ascii=False)}\n\n"
            "Return strictly a raw JSON array of resolved canonical entities."
        )

        try:
            target_llm = (
                getattr(self.llm_service, "llm", None)
                or getattr(self.llm_service, "chat_llm", None)
                or self.llm_service
            )
            response = target_llm.invoke(prompt)
            content = getattr(response, "content", str(response)).strip()

            # Extract JSON block
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            data = json.loads(content)
            if isinstance(data, list):
                return data
        except Exception as e:
            print(f"[AnchorEntityResolver] LLM resolution failed: {e}. Falling back to heuristic resolution.")

        return self._heuristic_batch_resolution(batch, candidate_anchors)

    def _heuristic_batch_resolution(
        self,
        batch: List[Dict[str, Any]],
        candidate_anchors: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Heuristic fallback for clustering synonyms, acronyms, and aliases without live LLM."""
        clusters: List[Dict[str, Any]] = []

        # Start with candidate anchors
        for anchor in candidate_anchors:
            c_name = anchor.get("canonical_name", "")
            aliases = [a for a in anchor.get("aliases", []) if a.lower() != c_name.lower()]
            clusters.append({
                "canonical_name": c_name,
                "aliases": list(dict.fromkeys(aliases)),
                "type": anchor.get("type", "concept"),
                "description": anchor.get("description", ""),
                "source_locators": list(anchor.get("source_locators", [])),
            })

        for ent in batch:
            ent_name = ent.get("canonical_name") or ent.get("name", "")
            merged = False

            for cluster in clusters:
                c_name = cluster["canonical_name"]
                c_aliases = cluster["aliases"]

                # Check exact name or alias match
                if ent_name.lower() == c_name.lower() or any(ent_name.lower() == a.lower() for a in c_aliases):
                    merged = True
                # Check acronym match
                elif is_acronym_match(c_name, ent_name):
                    # c_name was an acronym (e.g. CNN), ent_name is full name (Convolutional Neural Network)
                    # Promote ent_name to canonical_name!
                    merged = True
                    cluster["canonical_name"] = ent_name
                    if c_name not in cluster["aliases"] and c_name.lower() != ent_name.lower():
                        cluster["aliases"].append(c_name)
                    c_name = ent_name
                elif is_acronym_match(ent_name, c_name):
                    # ent_name is acronym (e.g. CNN), c_name is already full name
                    merged = True
                    if ent_name not in cluster["aliases"] and ent_name.lower() != c_name.lower():
                        cluster["aliases"].append(ent_name)
                # Check high lexical similarity
                elif len(ent_name) > 4 and len(c_name) > 4 and (ent_name.lower() in c_name.lower() or c_name.lower() in ent_name.lower()):
                    merged = True
                    # Prefer longer name as canonical
                    if len(ent_name) > len(c_name):
                        cluster["canonical_name"] = ent_name
                        if c_name not in cluster["aliases"]:
                            cluster["aliases"].append(c_name)
                        c_name = ent_name

                if merged:
                    if ent_name != c_name and ent_name not in cluster["aliases"]:
                        cluster["aliases"].append(ent_name)
                    for a in ent.get("aliases", []):
                        if a not in cluster["aliases"] and a != c_name:
                            cluster["aliases"].append(a)
                    # Deduplicate and ensure canonical_name is not in aliases
                    cluster["aliases"] = [a for a in dict.fromkeys(cluster["aliases"]) if a.lower() != cluster["canonical_name"].lower()]
                    # Merge source locators
                    for loc in ent.get("source_locators", []):
                        if loc not in cluster["source_locators"]:
                            cluster["source_locators"].append(loc)
                    break

            if not merged:
                canonical = ent_name
                aliases = list(ent.get("aliases", []))
                # Promote full name if canonical is an acronym or an alias is longer and not an acronym
                for a in list(aliases):
                    if len(a) > len(canonical) and (is_acronym_match(canonical, a) or not is_acronym_match(a, canonical)):
                        aliases.append(canonical)
                        canonical = a
                        aliases.remove(a)
                        break

                clean_aliases = [a for a in dict.fromkeys(aliases) if a.lower() != canonical.lower()]
                clusters.append({
                    "canonical_name": canonical,
                    "aliases": clean_aliases,
                    "type": ent.get("type", "concept"),
                    "description": ent.get("description", ""),
                    "source_locators": list(ent.get("source_locators", [])),
                })

        return clusters

    def resolve_batch_anchors(
        self,
        unresolved_entities: List[Dict[str, Any]],
        candidate_anchors: List[Dict[str, Any]],
        batch_size: Optional[int] = None,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
        """Divide-and-conquer batch resolution with Cosine feedback loop.

        Divides entities into batches of 15-20, resolves them into canonical anchors,
        and applies a Cosine feedback loop (>= 0.90) to absorb remaining items.
        """
        bsize = batch_size or self.batch_size
        canonical_anchors: List[Dict[str, Any]] = list(candidate_anchors)
        name_map: Dict[str, str] = {}

        # Initialize name_map for candidate anchors
        for anchor in candidate_anchors:
            c_name = anchor.get("canonical_name", "")
            for a in anchor.get("aliases", []):
                name_map[a] = c_name

        remaining = list(unresolved_entities)

        while remaining:
            # 1. Take batch of 15-20 items
            batch = remaining[:bsize]
            remaining = remaining[bsize:]

            # 2. Resolve batch with LLM (or heuristic)
            resolved_clusters = self._resolve_batch_with_llm(batch, canonical_anchors)

            # 3. Update canonical anchors list
            for cluster in resolved_clusters:
                c_name = cluster.get("canonical_name", "").strip()
                if not c_name:
                    continue

                # Record mappings
                name_map[c_name] = c_name
                for a in cluster.get("aliases", []):
                    name_map[a] = c_name

                # Check if already present in canonical_anchors
                existing = next(
                    (ca for ca in canonical_anchors if ca.get("canonical_name", "").lower() == c_name.lower()),
                    None,
                )
                if existing:
                    existing_aliases = set(existing.get("aliases", []))
                    existing_aliases.update(cluster.get("aliases", []))
                    existing["aliases"] = [a for a in existing_aliases if a.lower() != c_name.lower()]
                    for loc in cluster.get("source_locators", []):
                        if loc not in existing.setdefault("source_locators", []):
                            existing["source_locators"].append(loc)
                else:
                    canonical_anchors.append(cluster)

            # 4. Cosine Feedback Loop: Scan remaining items against updated anchors
            if remaining and canonical_anchors:
                anchor_vectors = [
                    (
                        anchor,
                        self.get_embedding(
                            f"{anchor.get('canonical_name', '')} {' '.join(anchor.get('aliases', []))}"
                        ),
                    )
                    for anchor in canonical_anchors
                ]

                still_remaining = []
                for item in remaining:
                    item_name = item.get("canonical_name") or item.get("name", "")
                    item_vec = self.get_embedding(item_name)
                    absorbed = False

                    for anchor, a_vec in anchor_vectors:
                        sim = compute_cosine_similarity(item_vec, a_vec)
                        if is_acronym_match(item_name, anchor.get("canonical_name", "")):
                            sim = max(sim, 0.95)

                        if sim >= self.feedback_loop_threshold:
                            canonical_target = anchor.get("canonical_name", "")
                            name_map[item_name] = canonical_target
                            if item.get("name"):
                                name_map[item["name"]] = canonical_target
                            for a in item.get("aliases", []):
                                name_map[a] = canonical_target

                            aliases = anchor.setdefault("aliases", [])
                            if item_name not in aliases and item_name.lower() != canonical_target.lower():
                                aliases.append(item_name)
                            for a in item.get("aliases", []):
                                if a not in aliases and a.lower() != canonical_target.lower():
                                    aliases.append(a)

                            for loc in item.get("source_locators", []):
                                if loc not in anchor.setdefault("source_locators", []):
                                    anchor["source_locators"].append(loc)

                            absorbed = True
                            break

                    if not absorbed:
                        still_remaining.append(item)

                remaining = still_remaining

        return canonical_anchors, name_map

    def resolve_section_entities(
        self,
        nodes: List[Dict[str, Any]],
        edges: List[Dict[str, Any]],
        source_locator: str = "",
        existing_anchors: Optional[List[Dict[str, Any]]] = None,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, str]]:
        """Run full anchor entity resolution pipeline on a section's nodes and edges.

        Step 0: Pre-filter against Qdrant/Graph index.
        Step 1: Divide-and-conquer batch resolution + Cosine feedback loop.
        Step 2: Remap knowledge graph edges to canonical node IDs.
        """
        normalized_nodes = [self._normalize_entity_dict(n) for n in nodes]

        if existing_anchors is None:
            anchors_pool: List[Dict[str, Any]] = []
            if self.graph_store and hasattr(self.graph_store, "get_all_concepts"):
                try:
                    anchors_pool.extend(self.graph_store.get_all_concepts())
                except Exception as e:
                    print(f"[AnchorEntityResolver] Graph store fetch error: {e}")
            for acc in self._accumulated_anchors:
                if not any(ea.get("canonical_name", "").lower() == acc.get("canonical_name", "").lower() for ea in anchors_pool):
                    anchors_pool.append(acc)
        else:
            anchors_pool = list(existing_anchors)

        # Step 0: Pre-filter against existing anchors
        unresolved, candidate_anchors, updated_anchors, name_map = self.pre_filter_with_existing_graph(
            entities=normalized_nodes,
            existing_anchors=anchors_pool,
        )

        # Step 1: Batch resolution
        resolved_anchors, batch_map = self.resolve_batch_anchors(
            unresolved_entities=unresolved,
            candidate_anchors=candidate_anchors,
        )
        name_map.update(batch_map)

        # Identify anchors from Step 0 that absorbed entities in this section
        absorbed_anchors = [
            anchor
            for anchor in updated_anchors
            if anchor.get("canonical_name") in name_map.values()
        ]

        # Combine resolved anchors and absorbed anchors for this section
        all_section_anchors = list(resolved_anchors)
        for abs_anchor in absorbed_anchors:
            if not any(a.get("canonical_name", "").lower() == abs_anchor.get("canonical_name", "").lower() for a in all_section_anchors):
                all_section_anchors.append(abs_anchor)

        # Format final nodes
        final_nodes: List[Dict[str, Any]] = []
        seen_canonical: Set[str] = set()

        for anchor in all_section_anchors:
            c_name = anchor.get("canonical_name", "").strip()
            if not c_name or c_name in seen_canonical:
                continue
            seen_canonical.add(c_name)

            locators = list(anchor.get("source_locators", []))
            if source_locator and source_locator not in locators:
                locators.append(source_locator)

            aliases = [a for a in anchor.get("aliases", []) if a.lower() != c_name.lower()]
            final_nodes.append({
                "name": c_name,
                "canonical_name": c_name,
                "aliases": list(dict.fromkeys(aliases)),
                "type": anchor.get("type", "concept"),
                "description": anchor.get("description", ""),
                "source_locators": locators,
            })

        # Update accumulated anchor cache
        for fn in final_nodes:
            if not any(acc.get("canonical_name", "").lower() == fn["canonical_name"].lower() for acc in self._accumulated_anchors):
                self._accumulated_anchors.append(fn)

        # Helper for case-insensitive and stripped lookup in name_map
        lower_name_map = {k.lower(): v for k, v in name_map.items()}

        def get_canonical_target(name: str) -> str:
            clean = name.strip()
            if clean in name_map:
                return name_map[clean]
            if clean.lower() in lower_name_map:
                return lower_name_map[clean.lower()]
            return clean

        # Step 2: Remap Edges using name_map
        resolved_edges: List[Dict[str, Any]] = []
        seen_edges: Set[Tuple[str, str, str]] = set()

        for e in edges:
            raw_src = str(e.get("source", "")).strip()
            raw_tgt = str(e.get("target", "")).strip()
            rel = str(e.get("relation", "RELATES_TO")).strip().upper().replace(" ", "_")

            src = get_canonical_target(raw_src)
            tgt = get_canonical_target(raw_tgt)

            # Prevent self-loops and empty entities
            if src and tgt and src != tgt:
                edge_key = (src, tgt, rel)
                if edge_key not in seen_edges:
                    seen_edges.add(edge_key)
                    resolved_edges.append({
                        "source": src,
                        "target": tgt,
                        "relation": rel,
                    })

        return final_nodes, resolved_edges, name_map
