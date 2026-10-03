"""
learning_graph.py — Lifelong Learning Knowledge Topology & Graph Assembler for Project Anara.

Unifies learned procedural skills (from skill_library) and durable memory chunks
(from USER.md & MEMORY.md) into a coherent directed acyclic knowledge graph (DAG)
with SHA-256 fingerprinting, category clustering, and lexical overlap edges.
"""

from __future__ import annotations

import hashlib
import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("anara.cognition.learning_graph")


def _compute_chunk_fingerprint(text: str) -> str:
    """Computes a 12-character SHA-256 fingerprint for a discrete memory chunk."""
    cleaned = re.sub(r"\s+", " ", text).strip()
    return hashlib.sha256(cleaned.encode("utf-8")).hexdigest()[:12]


def _tokenize_for_matching(text: str) -> Set[str]:
    """Extracts alphanumeric tokens (length >= 3) for lexical overlap calculation."""
    tokens = set(re.findall(r"\b[a-zA-Z0-9_-]{3,}\b", text.lower()))
    stopwords = {"and", "the", "for", "with", "this", "that", "from", "user", "agent", "anara"}
    return tokens - stopwords


def assemble_learning_graph() -> Dict[str, Any]:
    """
    Assembles the complete knowledge graph for the Star Map / Learning Graph visualizer.
    Returns: {
        "nodes": [...],
        "edges": [...],
        "clusters": [...],
        "memory": [...],
        "stats": {...}
    }
    """
    from core.skill_library import skill_library
    from memory.file_memory import FileMemoryManager

    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []
    clusters_map: Dict[str, int] = {}
    memory_cards: List[Dict[str, Any]] = []

    # 1. Collect Skills as First-Class Nodes
    skills = skill_library.list_skills()
    skill_token_map: Dict[str, Tuple[str, Set[str]]] = {}

    for s in skills:
        s_slug = s.get("slug") or s.get("name") or "skill"
        s_id = f"skill:{s_slug}"
        s_name = s.get("name") or s_slug
        category = s.get("category") or "general"
        clusters_map[category] = clusters_map.get(category, 0) + 1

        tokens = _tokenize_for_matching(f"{s_name} {s.get('description', '')}")
        skill_token_map[s_id] = (s_name.lower(), tokens)

        nodes.append({
            "id": s_id,
            "label": s_name,
            "kind": "skill",
            "category": category,
            "useCount": s.get("use_count", 1),
            "state": "active" if s.get("is_active", True) else "disabled",
            "createdBy": s.get("source") or "agent",
            "pinned": bool(s.get("pinned", False)),
        })

    # 2. Collect Memory Chunks from USER.md and MEMORY.md
    for source in ("user", "memory"):
        try:
            content = FileMemoryManager.get_user_profile() if source == "user" else FileMemoryManager.get_memory_facts()
            lines = [ln.strip() for ln in content.splitlines() if ln.strip() and not ln.startswith("#")]

            for idx, line in enumerate(lines):
                # Clean leading bullets or timestamps
                clean_text = re.sub(r"^[-*•\d\.\s\[\]\-\:\/]+\s*", "", line).strip()
                if len(clean_text) < 5:
                    continue

                fp = _compute_chunk_fingerprint(clean_text)
                node_id = f"memory:{source}:{idx}:{fp}"
                title = clean_text[:45] + ("..." if len(clean_text) > 45 else "")
                clusters_map[source] = clusters_map.get(source, 0) + 1

                nodes.append({
                    "id": node_id,
                    "label": title,
                    "kind": "memory",
                    "memorySource": source,
                    "category": source,
                    "useCount": 1,
                    "state": "active",
                    "createdBy": "self_improvement",
                    "pinned": False,
                })

                memory_cards.append({
                    "source": source,
                    "title": title,
                    "body": clean_text,
                    "fingerprint": fp,
                })

                # Compute Lexical Overlap Edges to Skills
                mem_tokens = _tokenize_for_matching(clean_text)
                for s_id, (s_name_lower, s_tokens) in skill_token_map.items():
                    # Direct phrase match has high weight
                    if s_name_lower in clean_text.lower():
                        edges.append({
                            "source": node_id,
                            "target": s_id,
                            "weight": 6,
                            "kind": "exact_match",
                        })
                    else:
                        overlap = mem_tokens.intersection(s_tokens)
                        if len(overlap) >= 2:
                            edges.append({
                                "source": node_id,
                                "target": s_id,
                                "weight": len(overlap),
                                "kind": "lexical_overlap",
                            })
        except Exception as e_mem:
            logger.debug(f"[LearningGraph] Memory scan notice for {source}: {e_mem}")

    # 3. Form Clusters Array and Statistics
    clusters = [{"category": cat, "count": count} for cat, count in clusters_map.items()]

    stats = {
        "total_nodes": len(nodes),
        "total_edges": len(edges),
        "total_skills": len(skills),
        "total_memory_cards": len(memory_cards),
        "density": round(len(edges) / max(len(nodes), 1), 2),
    }

    return {
        "nodes": nodes,
        "edges": edges,
        "clusters": clusters,
        "memory": memory_cards,
        "stats": stats,
    }
