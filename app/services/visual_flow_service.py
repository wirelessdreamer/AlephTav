from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.core.errors import NotFoundError
from app.services import registry_service

TOKEN_PATTERN = re.compile(r"[A-Za-z0-9']+")
PSALM_REF_PATTERN = re.compile(r"^Psalm\s+\d+:(\d+)[a-z]?$", re.IGNORECASE)
STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "be",
    "for",
    "from",
    "in",
    "is",
    "of",
    "on",
    "or",
    "the",
    "to",
    "with",
}
TITLE_STOP_WORDS = STOP_WORDS | {
    "all",
    "among",
    "come",
    "do",
    "does",
    "for",
    "give",
    "has",
    "have",
    "he",
    "his",
    "how",
    "i",
    "let",
    "make",
    "me",
    "my",
    "not",
    "our",
    "shall",
    "so",
    "us",
    "we",
    "who",
    "will",
    "with",
    "you",
    "your",
}
RANKING_WEIGHTS = {
    "vector_score": 0.45,
    "phrase_concept_overlap": 0.20,
    "literal_priority": 0.15,
    "approval_priority": 0.10,
    "scope_bonus": 0.10,
}
LYRIC_LAYERS = {"lyric", "metered_lyric", "parallelism_lyric"}
WITNESS_PRIORITY = ("web", "asv", "kjv")
CORRELATION_RELATIONSHIPS = {
    "close_anchor": "Close anchor",
    "interpretive_shift": "Interpretive shift",
    "added_reframed": "Added / reframed",
    "added_repetition": "Added repetition",
    "omitted_detail": "Omitted detail",
}
PSALM_CORRELATION_SECTIONS = {
    "ps066": [
        {"start": 1, "end": 4, "label": "Universal praise", "arrangement": "Opening verse"},
        {"start": 5, "end": 7, "label": "Exodus memory and rule", "arrangement": "Second verse"},
        {
            "start": 8,
            "end": 9,
            "label": "Communal preservation",
            "arrangement": "Pre-chorus / refrain",
        },
        {
            "start": 10,
            "end": 12,
            "label": "Testing, oppression, deliverance",
            "arrangement": "Chorus expansion",
        },
        {"start": 13, "end": 15, "label": "Vows and offerings", "arrangement": "Offering verse"},
        {"start": 16, "end": 20, "label": "Personal testimony", "arrangement": "Bridge / outro"},
    ]
}


def _vector_dir() -> Path:
    return get_settings().indexes_dir / "vector"


def _vector_path() -> Path:
    return _vector_dir() / "visual_flow_index.json"


def _stable_id(prefix: str, parts: list[str]) -> str:
    digest = hashlib.sha1("::".join(parts).encode("utf-8")).hexdigest()[:10]
    return f"{prefix}.{digest}"


def _normalize_text(value: str | None) -> str:
    return " ".join((value or "").split()).strip()


def _tokenize(value: str | None) -> list[str]:
    tokens = [item.lower() for item in TOKEN_PATTERN.findall(_normalize_text(value))]
    return [item for item in tokens if item not in STOP_WORDS]


def _approval_priority(status: str) -> float:
    if status == "canonical":
        return 1.0
    if status == "accepted_as_alternate":
        return 0.8
    if status == "under_review":
        return 0.45
    if status == "proposed":
        return 0.3
    return 0.1


def _pick_default_rendering(unit: dict[str, Any]) -> dict[str, Any] | None:
    renderings = unit.get("renderings", [])
    priorities = [
        ("literal", "canonical"),
        ("literal", "accepted_as_alternate"),
        ("gloss", "canonical"),
        ("phrase", "canonical"),
    ]
    for layer, status in priorities:
        candidate = next(
            (item for item in renderings if item["layer"] == layer and item["status"] == status),
            None,
        )
        if candidate:
            return candidate
    return renderings[0] if renderings else None


def _concept_entries(unit: dict[str, Any]) -> list[dict[str, Any]]:
    labels: list[str] = []
    for token in unit.get("tokens", []):
        for field_name in ("display_gloss", "word_sense", "semantic_role", "referent"):
            value = _normalize_text(token.get(field_name))
            if value and value not in labels:
                labels.append(value)
    entries: list[dict[str, Any]] = []
    for index, concept_id in enumerate(unit.get("concept_ids", []), start=1):
        label = (
            labels[index - 1]
            if index - 1 < len(labels)
            else unit.get("source_transliteration") or unit.get("source_hebrew")
        )
        text = label.replace("/", " ")
        entries.append(
            {
                "doc_id": _stable_id("doc", [concept_id, unit["unit_id"], "concept"]),
                "psalm_id": unit["psalm_id"],
                "unit_id": unit["unit_id"],
                "ref": unit["ref"],
                "layer": "concept",
                "status": "derived",
                "source_type": "concept",
                "label": text,
                "text": text,
                "concept_ids": [concept_id],
                "style_tags": ["concept"],
                "tokens": _tokenize(text),
            }
        )
    return entries


def _phrase_entries(unit: dict[str, Any]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for rendering in unit.get("renderings", []):
        if not rendering.get("target_spans"):
            continue
        for span in rendering["target_spans"]:
            text = _normalize_text(span.get("text"))
            if not text:
                continue
            entries.append(
                {
                    "doc_id": _stable_id(
                        "doc", [rendering["rendering_id"], span["span_id"], "phrase"]
                    ),
                    "psalm_id": unit["psalm_id"],
                    "unit_id": unit["unit_id"],
                    "ref": unit["ref"],
                    "layer": rendering["layer"],
                    "status": rendering["status"],
                    "source_type": "phrase",
                    "label": text,
                    "text": text,
                    "rendering_id": rendering["rendering_id"],
                    "concept_ids": list(unit.get("concept_ids", [])),
                    "style_tags": list(rendering.get("style_tags", [])),
                    "tokens": _tokenize(text),
                }
            )
    return entries


def _rendering_entries(unit: dict[str, Any]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for rendering in unit.get("renderings", []):
        text = _normalize_text(rendering.get("text"))
        if not text:
            continue
        entries.append(
            {
                "doc_id": _stable_id("doc", [rendering["rendering_id"], "rendering"]),
                "psalm_id": unit["psalm_id"],
                "unit_id": unit["unit_id"],
                "ref": unit["ref"],
                "layer": rendering["layer"],
                "status": rendering["status"],
                "source_type": "rendering",
                "label": text,
                "text": text,
                "rendering_id": rendering["rendering_id"],
                "concept_ids": list(unit.get("concept_ids", [])),
                "style_tags": list(rendering.get("style_tags", [])),
                "tokens": _tokenize(text),
            }
        )
    return entries


def rebuild_vector_index() -> dict[str, Any]:
    docs: list[dict[str, Any]] = []
    for unit in registry_service.list_units():
        docs.extend(_rendering_entries(unit))
        docs.extend(_phrase_entries(unit))
        docs.extend(_concept_entries(unit))
    payload = {
        "index_version": 1,
        "embedding_model": "local-token-overlap-v1",
        "embedding_version": "2026-04-12",
        "documents": docs,
    }
    _vector_dir().mkdir(parents=True, exist_ok=True)
    _vector_path().write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return {
        "index_path": str(_vector_path()),
        "documents": len(docs),
        "embedding_model": payload["embedding_model"],
        "embedding_version": payload["embedding_version"],
    }


def _load_index() -> dict[str, Any]:
    path = _vector_path()
    if not path.exists():
        rebuild_vector_index()
    return json.loads(path.read_text(encoding="utf-8"))


def _scope_documents(index: dict[str, Any], psalm_id: str, scope: str) -> list[dict[str, Any]]:
    documents = index.get("documents", [])
    if scope == "selected_psalm":
        return [item for item in documents if item["psalm_id"] == psalm_id]
    return documents


def _build_cloud_nodes(
    psalm_id: str, scope: str = "selected_psalm", limit: int = 24
) -> dict[str, Any]:
    index = _load_index()
    documents = _scope_documents(index, psalm_id, scope)
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for item in documents:
        if item["source_type"] not in {"phrase", "concept"}:
            continue
        key = (item["source_type"], item["label"].casefold())
        node_id = _stable_id("node", [psalm_id, item["source_type"], item["label"]])
        existing = grouped.setdefault(
            key,
            {
                "node_id": node_id,
                "label": item["label"],
                "kind": item["source_type"],
                "psalm_id": psalm_id,
                "source_text": item["text"],
                "weight": 0.0,
                "support_count": 0,
                "unit_ids": [],
                "concept_ids": [],
            },
        )
        existing["support_count"] += 1
        existing["weight"] += 1.0 if item["psalm_id"] == psalm_id else 0.35
        if item["unit_id"] not in existing["unit_ids"]:
            existing["unit_ids"].append(item["unit_id"])
        for concept_id in item.get("concept_ids", []):
            if concept_id not in existing["concept_ids"]:
                existing["concept_ids"].append(concept_id)
    nodes = sorted(grouped.values(), key=lambda item: (-item["weight"], item["label"]))[:limit]
    return {
        "psalm_id": psalm_id,
        "scope": scope,
        "retrieval_status": "ready",
        "embedding_model": index["embedding_model"],
        "embedding_version": index["embedding_version"],
        "nodes": nodes,
    }


def _score_document(
    node: dict[str, Any], document: dict[str, Any], psalm_id: str
) -> dict[str, float]:
    node_tokens = set(_tokenize(node["source_text"]))
    doc_tokens = set(document.get("tokens", []))
    union = node_tokens | doc_tokens
    intersection = node_tokens & doc_tokens
    vector_score = len(intersection) / len(union) if union else 0.0
    phrase_concept_overlap = 0.0
    if set(node.get("concept_ids", [])) & set(document.get("concept_ids", [])):
        phrase_concept_overlap = 1.0
    elif document["label"].casefold() == node["label"].casefold():
        phrase_concept_overlap = 0.75
    elif intersection:
        phrase_concept_overlap = min(0.6, len(intersection) / max(len(node_tokens), 1))
    literal_priority = 1.0 if document.get("layer") == "literal" else 0.0
    approval_priority = _approval_priority(document.get("status", ""))
    scope_bonus = 1.0 if document["psalm_id"] == psalm_id else 0.0
    final_score = (
        vector_score * RANKING_WEIGHTS["vector_score"]
        + phrase_concept_overlap * RANKING_WEIGHTS["phrase_concept_overlap"]
        + literal_priority * RANKING_WEIGHTS["literal_priority"]
        + approval_priority * RANKING_WEIGHTS["approval_priority"]
        + scope_bonus * RANKING_WEIGHTS["scope_bonus"]
    )
    return {
        "vector_score": round(vector_score, 4),
        "phrase_concept_overlap": round(phrase_concept_overlap, 4),
        "literal_priority": round(literal_priority, 4),
        "approval_priority": round(approval_priority, 4),
        "scope_bonus": round(scope_bonus, 4),
        "final_score": round(final_score, 4),
    }


def get_cloud(psalm_id: str, scope: str = "selected_psalm", limit: int = 24) -> dict[str, Any]:
    return _build_cloud_nodes(psalm_id=psalm_id, scope=scope, limit=limit)


def get_retrieval(
    psalm_id: str,
    node_id: str,
    scope: str = "selected_psalm",
    include_cross_psalm: bool = True,
    limit: int = 12,
) -> dict[str, Any]:
    cloud = _build_cloud_nodes(
        psalm_id=psalm_id, scope="all_psalms" if include_cross_psalm else scope, limit=96
    )
    node = next((item for item in cloud["nodes"] if item["node_id"] == node_id), None)
    if not node:
        raise NotFoundError(f"Cloud node not found: {node_id}")
    index = _load_index()
    documents = _scope_documents(index, psalm_id, "all_psalms" if include_cross_psalm else scope)
    hits = []
    for item in documents:
        if item["source_type"] not in {"rendering", "phrase"}:
            continue
        scores = _score_document(node, item, psalm_id)
        if scores["final_score"] <= 0:
            continue
        hits.append(
            {
                "hit_id": _stable_id("hit", [node_id, item["doc_id"]]),
                "unit_id": item["unit_id"],
                "psalm_id": item["psalm_id"],
                "ref": item["ref"],
                "label": item["label"],
                "layer": item["layer"],
                "status": item["status"],
                "source_type": item["source_type"],
                "rendering_id": item.get("rendering_id"),
                "scope": "same_psalm" if item["psalm_id"] == psalm_id else "cross_psalm",
                "explanation": {
                    "matched_concept_ids": list(
                        set(node.get("concept_ids", [])) & set(item.get("concept_ids", []))
                    ),
                    "matched_phrase": item["label"]
                    if item["label"].casefold() == node["label"].casefold()
                    else None,
                    **scores,
                },
            }
        )
    hits = sorted(
        hits,
        key=lambda item: (
            item["scope"] != "same_psalm",
            -item["explanation"]["final_score"],
            item["ref"],
            item["label"],
        ),
    )[:limit]
    return {
        "psalm_id": psalm_id,
        "node": node,
        "scope": scope,
        "include_cross_psalm": include_cross_psalm,
        "retrieval_status": "ready",
        "hits": hits,
    }


def _verse_number(unit: dict[str, Any]) -> int | None:
    match = PSALM_REF_PATTERN.match(str(unit.get("ref") or "").strip())
    return int(match.group(1)) if match else None


def _verse_label(units: list[dict[str, Any]]) -> str:
    numbers = [number for unit in units if (number := _verse_number(unit)) is not None]
    if not numbers:
        return "source range"
    first = min(numbers)
    last = max(numbers)
    return f"v. {first}" if first == last else f"vv. {first}-{last}"


def _section_window_size(unit_count: int) -> int:
    if unit_count <= 8:
        return 1
    if unit_count <= 18:
        return 2
    if unit_count <= 34:
        return 3
    if unit_count <= 80:
        return 5
    return 8


def _section_plan(psalm: dict[str, Any]) -> list[dict[str, Any]]:
    psalm_id = str(psalm.get("psalm_id") or "")
    if psalm_id in PSALM_CORRELATION_SECTIONS:
        return PSALM_CORRELATION_SECTIONS[psalm_id]

    units = [unit for unit in psalm.get("units", []) if _verse_number(unit) is not None]
    if not units:
        return []

    window_size = _section_window_size(len(units))
    sections: list[dict[str, Any]] = []
    for index in range(0, len(units), window_size):
        section_units = units[index : index + window_size]
        first = _verse_number(section_units[0])
        last = _verse_number(section_units[-1])
        if first is None or last is None:
            continue
        sections.append({"start": first, "end": last, "arrangement": _verse_label(section_units)})
    return sections


def _units_for_section(
    units: list[dict[str, Any]], section: dict[str, Any]
) -> list[dict[str, Any]]:
    start = int(section["start"])
    end = int(section["end"])
    return [
        unit
        for unit in units
        if (number := _verse_number(unit)) is not None and start <= number <= end
    ]


def _gloss_for_token(token: dict[str, Any]) -> str:
    value = _normalize_text(token.get("display_gloss") or token.get("word_sense"))
    if value:
        return value
    features = token.get("compiler_features") or {}
    english_parts = features.get("english_parts")
    if isinstance(english_parts, list):
        return _normalize_text(" ".join(str(part) for part in english_parts if part))
    gloss_parts = token.get("gloss_parts")
    if isinstance(gloss_parts, list):
        return _normalize_text(" ".join(str(part) for part in gloss_parts if part))
    return _normalize_text(token.get("transliteration") or token.get("normalized"))


def _source_scaffold_text(units: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for unit in units:
        token_text = " ".join(
            part for token in unit.get("tokens", []) if (part := _gloss_for_token(token))
        )
        lines.append(_normalize_text(token_text))
    return " ".join(line for line in lines if line)


def _preferred_witness(unit: dict[str, Any]) -> dict[str, Any] | None:
    witnesses = unit.get("witnesses") or []
    for source_id in WITNESS_PRIORITY:
        witness = next((item for item in witnesses if item.get("source_id") == source_id), None)
        if witness and _normalize_text(witness.get("text")):
            return witness
    return next(
        (
            item
            for item in witnesses
            if item.get("language") == "en" and _normalize_text(item.get("text"))
        ),
        None,
    )


def _source_english_text(units: list[dict[str, Any]], fallback: str) -> tuple[str, str]:
    texts: list[str] = []
    labels: list[str] = []
    for unit in units:
        witness = _preferred_witness(unit)
        if not witness:
            continue
        texts.append(_normalize_text(witness.get("text")))
        raw_label = _normalize_text(witness.get("source_id") or witness.get("versionTitle"))
        label = raw_label.upper() if len(raw_label) <= 4 else raw_label
        if label and label not in labels:
            labels.append(label)

    if texts:
        return " ".join(texts), " / ".join(labels)
    return fallback, "derived gloss scaffold"


def _preferred_lyric_rendering(unit: dict[str, Any]) -> dict[str, Any] | None:
    layer_priority = {"parallelism_lyric": 3, "metered_lyric": 2, "lyric": 1}
    renderings = [
        rendering
        for rendering in unit.get("renderings", [])
        if rendering.get("layer") in LYRIC_LAYERS and _normalize_text(rendering.get("text"))
    ]
    if not renderings:
        return None
    return sorted(
        renderings,
        key=lambda rendering: (
            -_approval_priority(str(rendering.get("status") or "")),
            -layer_priority.get(str(rendering.get("layer") or ""), 0),
            str(rendering.get("rendering_id") or ""),
        ),
    )[0]


def _lyric_text(units: list[dict[str, Any]]) -> tuple[str, str, str]:
    texts: list[str] = []
    statuses: list[str] = []
    layers: list[str] = []
    for unit in units:
        rendering = _preferred_lyric_rendering(unit)
        if not rendering:
            continue
        texts.append(_normalize_text(rendering.get("text")))
        status = str(rendering.get("status") or "")
        layer = str(rendering.get("layer") or "")
        if status and status not in statuses:
            statuses.append(status)
        if layer and layer not in layers:
            layers.append(layer)
    return "\n".join(texts), " / ".join(statuses), " / ".join(layers)


def _title_tokens(value: str) -> list[str]:
    return [
        token.lower()
        for token in TOKEN_PATTERN.findall(value)
        if token.lower() not in TITLE_STOP_WORDS and len(token) > 2
    ]


def _section_title(units: list[dict[str, Any]], explicit_label: str | None) -> str:
    if explicit_label:
        return explicit_label
    counts = Counter(_title_tokens(_source_scaffold_text(units)))
    if not counts:
        return "Source movement"
    return " / ".join(word.title() for word, _count in counts.most_common(3))


def _has_repetition_pressure(text: str) -> bool:
    lines = [line.strip().casefold() for line in text.splitlines() if line.strip()]
    if len(lines) != len(set(lines)):
        return True
    counts = Counter(token for token in _title_tokens(text) if token not in STOP_WORDS)
    return any(count >= 3 for count in counts.values())


def _relationship_for_text(source_english: str, lyric: str) -> tuple[str, float, str]:
    if not lyric:
        return (
            "omitted_detail",
            0.0,
            "No lyric rendering is stored for this range.",
        )

    source_tokens = set(_tokenize(source_english))
    lyric_tokens = set(_tokenize(lyric))
    if not source_tokens:
        return (
            "added_reframed",
            0.0,
            "Song text exists, but no close English source scaffold is available.",
        )

    overlap = len(source_tokens & lyric_tokens) / max(len(source_tokens), 1)
    if _has_repetition_pressure(lyric):
        return (
            "added_repetition",
            overlap,
            "Lyric text repeats or extends source language for performance shape.",
        )
    if overlap >= 0.42:
        return "close_anchor", overlap, "High overlap with the close English source witness."
    if overlap >= 0.18:
        return (
            "interpretive_shift",
            overlap,
            "Source imagery remains visible, but wording is recast for lyric delivery.",
        )
    return (
        "added_reframed",
        overlap,
        "Lyric wording reframes the source range and needs reviewer attention.",
    )


def _build_correlation_rows(psalm: dict[str, Any]) -> list[dict[str, Any]]:
    units = psalm.get("units", [])
    rows: list[dict[str, Any]] = []
    for section in _section_plan(psalm):
        section_units = _units_for_section(units, section)
        if not section_units:
            continue
        source_scaffold = _source_scaffold_text(section_units)
        source_english, source_english_label = _source_english_text(
            section_units,
            source_scaffold,
        )
        lyric, lyric_status, lyric_layer = _lyric_text(section_units)
        relationship_kind, overlap, relationship_note = _relationship_for_text(
            source_english,
            lyric,
        )
        verse_numbers = [
            number for unit in section_units if (number := _verse_number(unit)) is not None
        ]
        start = min(verse_numbers) if verse_numbers else section.get("start")
        end = max(verse_numbers) if verse_numbers else section.get("end")
        rows.append(
            {
                "row_id": f"corr.{psalm['psalm_id']}.{int(start):03d}-{int(end):03d}",
                "ref": _verse_label(section_units),
                "section_label": _section_title(section_units, section.get("label")),
                "source_unit_ids": [unit["unit_id"] for unit in section_units],
                "source_refs": [unit["ref"] for unit in section_units],
                "source_hebrew": " ".join(unit["source_hebrew"] for unit in section_units),
                "source_close_english": source_english,
                "source_english_label": source_english_label,
                "source_scaffold_text": source_scaffold,
                "arrangement_label": section.get("arrangement") or _verse_label(section_units),
                "lyric_text": lyric,
                "lyric_status": lyric_status or "not_recorded",
                "lyric_layer": lyric_layer or None,
                "relationship_kind": relationship_kind,
                "relationship_label": CORRELATION_RELATIONSHIPS[relationship_kind],
                "relationship_note": relationship_note,
                "overlap_score": round(overlap, 4),
            }
        )
    return rows


def _correlation_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    counts = Counter(row["relationship_kind"] for row in rows)
    mapped_rows = sum(1 for row in rows if row.get("lyric_text"))
    return {
        "row_count": len(rows),
        "mapped_row_count": mapped_rows,
        "source_only_row_count": len(rows) - mapped_rows,
        "relationship_counts": dict(counts),
    }


def get_visual_flow(psalm_id: str) -> dict[str, Any]:
    psalm = registry_service.load_psalm(psalm_id)
    cloud = _build_cloud_nodes(psalm_id=psalm_id)
    correlation_rows = _build_correlation_rows(psalm)
    units: list[dict[str, Any]] = []
    for unit in psalm["units"]:
        default_rendering = _pick_default_rendering(unit)
        unit_cloud = [item for item in cloud["nodes"] if unit["unit_id"] in item["unit_ids"]][:6]
        units.append(
            {
                "unit_id": unit["unit_id"],
                "ref": unit["ref"],
                "source_hebrew": unit["source_hebrew"],
                "tokens": unit.get("tokens", []),
                "concept_ids": unit.get("concept_ids", []),
                "default_rendering": default_rendering,
                "supporting_nodes": unit_cloud,
            }
        )
    return {
        "psalm_id": psalm["psalm_id"],
        "title": psalm["title"],
        "retrieval_status": cloud["retrieval_status"],
        "embedding_model": cloud["embedding_model"],
        "embedding_version": cloud["embedding_version"],
        "units": units,
        "cloud_nodes": cloud["nodes"],
        "correlation_rows": correlation_rows,
        "correlation_summary": _correlation_summary(correlation_rows),
    }
