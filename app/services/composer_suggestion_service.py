from __future__ import annotations

import json
from typing import Any

from app.core.errors import GenerationError, NotFoundError, ValidationError
from app.llm.adapters import build_adapter
from app.llm.base import GenerationRequest
from app.services import registry_service

STAGES = {"phrase", "concept", "lyric"}


def _model_profile(model_profile: str | None) -> dict[str, Any]:
    project = registry_service.load_project()
    model_profile_id = model_profile or project["default_model_profile"]
    for item in project.get("local_model_profiles", []):
        if item["model_profile_id"] == model_profile_id:
            return item
    raise NotFoundError(f"Unknown model profile: {model_profile_id}")


def _validate_chunks(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for index, chunk in enumerate(chunks):
        chunk_id = str(chunk.get("chunk_id") or "").strip()
        text = str(chunk.get("text") or "").strip()
        if not chunk_id or not text:
            raise ValidationError(f"Chunk {index + 1} is missing chunk_id or text")
        normalized.append(
            {
                "chunk_id": chunk_id,
                "start": int(chunk.get("start", 0)),
                "end": int(chunk.get("end", chunk.get("start", 0))),
                "text": text,
                "source_text": str(chunk.get("source_text") or "").strip(),
                "confidence": float(chunk.get("confidence", 0.0)),
                "confidence_reasons": [str(item) for item in chunk.get("confidence_reasons", [])],
            }
        )
    return normalized


def _contract(candidate_count: int) -> dict[str, Any]:
    return {
        "type": "object",
        "required": ["unit_id", "stage", "chunks"],
        "additionalProperties": False,
        "properties": {
            "unit_id": {"type": "string"},
            "stage": {"type": "string", "enum": sorted(STAGES)},
            "chunks": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["chunk_id", "candidates"],
                    "additionalProperties": False,
                    "properties": {
                        "chunk_id": {"type": "string"},
                        "candidates": {
                            "type": "array",
                            "minItems": 1,
                            "maxItems": candidate_count,
                            "items": {
                                "type": "object",
                                "required": ["text", "rationale", "alignment_hints", "drift_flags", "metrics"],
                                "additionalProperties": False,
                                "properties": {
                                    "text": {"type": "string"},
                                    "rationale": {"type": "string"},
                                    "alignment_hints": {"type": "array", "items": {"type": "string"}},
                                    "drift_flags": {"type": "array", "items": {"type": "string"}},
                                    "metrics": {"type": "object"},
                                },
                            },
                        },
                    },
                },
            },
        },
    }


def _prompt(unit: dict[str, Any], stage: str, chunks: list[dict[str, Any]], candidate_count: int) -> str:
    witness_payload = [
        {
            "source_id": witness.get("source_id"),
            "versionTitle": witness.get("versionTitle"),
            "text": witness.get("text"),
        }
        for witness in unit.get("witnesses", [])
        if witness.get("text")
    ]
    stage_guidance = {
        "phrase": "Return conservative, near-literal English chunk alternatives.",
        "concept": "Return compressed semantic alternatives that keep the same roles and imagery.",
        "lyric": "Return cadence-smoothed alternatives without adding doctrine or drifting from the chunk meaning.",
    }[stage]
    return (
        "You are assisting a Hebrew-to-English translation workbench.\n"
        "Return strict JSON only. Do not include markdown.\n"
        f"{stage_guidance}\n"
        "Use the witness texts only as validation context. Do not copy their wording unless the phrasing is unavoidable.\n"
        f"Produce exactly {candidate_count} candidates per chunk, unless a chunk is too constrained, in which case produce fewer.\n\n"
        f"Unit context:\n{registry_service.deterministic_json({'unit_id': unit['unit_id'], 'ref': unit['ref'], 'source_hebrew': unit['source_hebrew'], 'tokens': unit.get('tokens', []), 'witnesses': witness_payload})}\n"
        f"Chunk input:\n{registry_service.deterministic_json({'unit_id': unit['unit_id'], 'stage': stage, 'chunks': chunks})}\n"
        f"Output contract:\n{json.dumps(_contract(candidate_count), indent=2, sort_keys=True)}"
    )


def suggest_for_unit(
    unit_id: str,
    stage: str,
    chunks: list[dict[str, Any]],
    candidate_count: int = 3,
    model_profile: str | None = None,
) -> dict[str, Any]:
    if stage not in STAGES:
        raise ValidationError(f"Unsupported composer suggestion stage: {stage}")
    if candidate_count < 1 or candidate_count > 5:
        raise ValidationError("candidate_count must be between 1 and 5")
    normalized_chunks = _validate_chunks(chunks)
    if not normalized_chunks:
        return {"unit_id": unit_id, "stage": stage, "available": False, "chunks": []}

    unit = registry_service.load_unit(unit_id)
    profile = _model_profile(model_profile)
    adapter = build_adapter(profile)
    try:
        response = adapter.generate_json(
            GenerationRequest(
                prompt=_prompt(unit, stage, normalized_chunks, candidate_count),
                contract=_contract(candidate_count),
                model=str(profile["model"]),
                seed=42,
                temperature=float(profile.get("temperature", 0.2)),
                max_tokens=int(profile.get("max_tokens", 768)),
                system_prompt="Return valid JSON matching the requested contract exactly.",
                candidate_count=1,
                timeout_seconds=int(profile.get("timeout_seconds", 30)),
                metadata={"unit_id": unit_id, "stage": stage},
            )
        )
    except GenerationError:
        return {"unit_id": unit_id, "stage": stage, "available": False, "chunks": []}

    payload = response.payload
    if payload.get("unit_id") != unit_id or payload.get("stage") != stage:
        raise ValidationError("Composer suggestion response returned the wrong unit or stage")
    return {"unit_id": unit_id, "stage": stage, "available": True, "chunks": payload.get("chunks", [])}
