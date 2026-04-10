from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from importlib import resources
from typing import Any

from jsonschema import Draft202012Validator

from app.core.errors import NotFoundError, ValidationError
from app.db.models import JOB_TABLE_SQL
from app.db.session import get_connection
from app.llm.adapters import build_adapter
from app.llm.base import GenerationRequest
from app.services import registry_service, rendering_service

PASS_ORDER = ["gloss", "literal", "phrase", "concept", "lyric", "metered_lyric"]
PASS_DEPENDENCIES = {
    "gloss": [],
    "literal": ["gloss"],
    "phrase": ["literal"],
    "concept": ["literal", "phrase"],
    "lyric": ["gloss", "literal", "concept"],
    "metered_lyric": ["lyric"],
}
PROMPT_FILES = {
    "gloss": "pass_01_gloss.md",
    "literal": "pass_02_literal.md",
    "phrase": "pass_03_phrase.md",
    "concept": "pass_04_concept.md",
    "lyric": "pass_05_lyric.md",
    "metered_lyric": "pass_06_metered_lyric.md",
}
INPUT_VALIDATOR = Draft202012Validator(
    json.loads(resources.files("app.llm.contracts").joinpath("generation_input.schema.json").read_text(encoding="utf-8"))
)
OUTPUT_VALIDATOR = Draft202012Validator(
    json.loads(resources.files("app.llm.contracts").joinpath("generation_output.schema.json").read_text(encoding="utf-8"))
)


def _ensure_job_table() -> None:
    with get_connection() as connection:
        connection.executescript(JOB_TABLE_SQL)


def _canonical_rendering(unit: dict[str, Any], layer: str) -> dict[str, Any] | None:
    return next(
        (item for item in unit.get("renderings", []) if item["layer"] == layer and item["status"] == "canonical"),
        None,
    )


def _load_prompt(layer: str) -> tuple[str, str]:
    prompt_name = PROMPT_FILES[layer]
    prompt_version = prompt_name.replace(".md", "")
    prompt_text = resources.files("app.llm.prompts").joinpath(prompt_name).read_text(encoding="utf-8").strip()
    return prompt_version, prompt_text


def _style_profile(style_profile: str) -> dict[str, Any]:
    project = registry_service.load_project()
    for item in project.get("style_profiles", []):
        if item["style_profile_id"] == style_profile:
            return item
    raise NotFoundError(f"Unknown style profile: {style_profile}")


def _model_profile(model_profile: str | None) -> dict[str, Any]:
    project = registry_service.load_project()
    model_profile_id = model_profile or project["default_model_profile"]
    for item in project.get("local_model_profiles", []):
        if item["model_profile_id"] == model_profile_id:
            return item
    raise NotFoundError(f"Unknown model profile: {model_profile_id}")


def _locked_inputs(unit: dict[str, Any], layer: str) -> dict[str, Any]:
    locked_inputs: dict[str, Any] = {
        "hebrew_tokens": [
            {
                "token_id": token["token_id"],
                "surface": token["surface"],
                "lemma": token.get("lemma"),
                "strong": token.get("strong"),
                "morph_code": token.get("morph_code"),
                "transliteration": token.get("transliteration"),
            }
            for token in unit.get("tokens", [])
        ]
    }
    for dependency in PASS_DEPENDENCIES[layer]:
        rendering = _canonical_rendering(unit, dependency)
        if rendering is None:
            raise ValidationError(f"{layer} requires canonical {dependency} input for {unit['unit_id']}")
        locked_inputs[f"{dependency}_rendering_id"] = rendering["rendering_id"]
        locked_inputs[f"{dependency}_text"] = rendering["text"]
    return locked_inputs


def _job_payload(
    unit_id: str,
    layer: str,
    style_profile: str,
    model_profile: str | None,
    seed: int,
    candidate_count: int,
) -> dict[str, Any]:
    unit = registry_service.load_unit(unit_id)
    payload = {
        "unit_id": unit_id,
        "layer": layer,
        "locked_inputs": _locked_inputs(unit, layer),
        "style_profile": _style_profile(style_profile),
        "candidate_count": candidate_count,
        "seed": seed,
        "model_profile_id": _model_profile(model_profile)["model_profile_id"],
    }
    errors = sorted(INPUT_VALIDATOR.iter_errors(payload), key=lambda item: list(item.path))
    if errors:
        raise ValidationError(f"Generation input contract failed: {errors[0].message}")
    return payload


def _job_identity(payload: dict[str, Any], prompt_version: str, model_profile: dict[str, Any]) -> tuple[str, str]:
    identity_payload = {
        "input_hash": registry_service.file_hash(payload),
        "prompt_version": prompt_version,
        "model_profile": model_profile["model_profile_id"],
        "seed": payload["seed"],
    }
    digest = hashlib.sha256(registry_service.deterministic_json(identity_payload).encode("utf-8")).hexdigest()
    return digest[:12], identity_payload["input_hash"]


def _downstream_layers(layer: str) -> list[str]:
    start = PASS_ORDER.index(layer)
    return PASS_ORDER[start + 1 :]


def _invalidate_downstream(unit_id: str, layer: str) -> list[str]:
    invalidated_ids: list[str] = []

    def mutator(unit: dict[str, Any]) -> dict[str, Any]:
        downstream_layers = set([layer, *_downstream_layers(layer)])
        kept_renderings = []
        kept_alternates = []
        kept_canonical = []
        for rendering in unit.get("renderings", []):
            if rendering["layer"] not in downstream_layers:
                kept_renderings.append(rendering)
                continue
            if rendering["status"] == "canonical":
                kept_renderings.append(rendering)
                kept_canonical.append(rendering["rendering_id"])
                continue
            invalidated_ids.append(rendering["rendering_id"])
        for rendering_id in unit.get("alternate_rendering_ids", []):
            if rendering_id not in invalidated_ids:
                kept_alternates.append(rendering_id)
        for rendering_id in unit.get("canonical_rendering_ids", []):
            if rendering_id in invalidated_ids:
                continue
            kept_canonical.append(rendering_id)
        unit["renderings"] = kept_renderings
        unit["alternate_rendering_ids"] = sorted(set(kept_alternates))
        unit["canonical_rendering_ids"] = sorted(set(kept_canonical))
        return unit

    registry_service.update_unit(unit_id, mutator)
    return invalidated_ids


def _assert_layer_rules(unit: dict[str, Any], layer: str) -> None:
    if layer not in PASS_ORDER:
        raise ValidationError(f"Unknown generation layer: {layer}")
    locked_layers = set(unit.get("current_layer_state", {}).get("locked_layers", []))
    if layer in locked_layers:
        raise ValidationError(f"Layer {layer} is locked for {unit['unit_id']}")
    if "lexical" in locked_layers and layer == "gloss":
        raise ValidationError(f"Lexical lock prevents rerunning {layer} for {unit['unit_id']}")


def _alignment_hints(unit: dict[str, Any], layer: str) -> list[str]:
    return [item["alignment_id"] for item in unit.get("alignments", []) if item["layer"] in {layer, "gloss", "literal"}]


def _candidate_to_rendering(
    unit: dict[str, Any],
    layer: str,
    style_profile: str,
    model_profile: dict[str, Any],
    prompt_version: str,
    candidate: dict[str, Any],
    job_id: str,
) -> dict[str, Any]:
    return rendering_service.create_rendering(
        unit_id=unit["unit_id"],
        layer=layer,
        text=candidate["text"],
        status="proposed",
        rationale=candidate["rationale"],
        created_by="generation-service",
        style_tags=[layer, style_profile, model_profile["model_profile_id"]],
        alignment_ids=candidate.get("alignment_hints") or _alignment_hints(unit, layer),
        drift_flags=candidate.get("drift_flags", []),
        metrics=candidate.get("metrics", {}),
        provenance={
            "source_ids": ["uxlc", "oshb", "macula"],
            "generator": "generation-service",
            "model_profile_id": model_profile["model_profile_id"],
            "job_id": job_id,
            "prompt_version": prompt_version,
        },
    )


def _mark_latest_layer(unit_id: str, layer: str) -> None:
    def mutator(unit: dict[str, Any]) -> dict[str, Any]:
        state = unit.setdefault("current_layer_state", {})
        state["latest_layer"] = layer
        state.setdefault("locked_layers", [])
        return unit

    registry_service.update_unit(unit_id, mutator)


def generate_for_unit(
    unit_id: str,
    layer: str,
    style_profile: str = "study_literal",
    model_profile: str | None = None,
    seed: int = 42,
    candidate_count: int = 1,
    force: bool = False,
) -> dict[str, Any]:
    _ensure_job_table()
    unit = registry_service.load_unit(unit_id)
    _assert_layer_rules(unit, layer)
    prompt_version, prompt_template = _load_prompt(layer)
    payload = _job_payload(unit_id, layer, style_profile, model_profile, seed, candidate_count)
    model_profile_payload = _model_profile(model_profile)
    job_suffix, input_hash = _job_identity(payload, prompt_version, model_profile_payload)
    job_id = f"job.{job_suffix}"

    with get_connection() as connection:
        existing = connection.execute("SELECT * FROM generation_jobs WHERE job_id = ?", (job_id,)).fetchone()
        if existing is not None and force:
            connection.execute("DELETE FROM generation_jobs WHERE job_id = ?", (job_id,))
            existing = None
    if existing is not None:
        return _deserialize_job(dict(existing))

    adapter = build_adapter(model_profile_payload)
    system_prompt = (
        "Return strict JSON only. Do not include markdown fences or commentary. "
        "Match the provided output contract exactly."
    )
    response = adapter.generate_json(
        GenerationRequest(
            prompt=(
                f"{prompt_template}\n\n"
                f"Generation input:\n{registry_service.deterministic_json(payload)}\n"
                f"Output contract:\n{resources.files('app.llm.contracts').joinpath('generation_output.schema.json').read_text(encoding='utf-8')}"
            ),
            contract=json.loads(
                resources.files("app.llm.contracts").joinpath("generation_output.schema.json").read_text(encoding="utf-8")
            ),
            model=model_profile_payload["model"],
            seed=seed,
            temperature=float(model_profile_payload.get("temperature", 0.0)),
            max_tokens=int(model_profile_payload.get("max_tokens", 512)),
            system_prompt=system_prompt,
            candidate_count=candidate_count,
            timeout_seconds=int(model_profile_payload.get("timeout_seconds", 30)),
            metadata={"unit_id": unit_id, "layer": layer, "style_profile": style_profile},
        )
    )
    errors = sorted(OUTPUT_VALIDATOR.iter_errors(response.payload), key=lambda item: list(item.path))
    if errors:
        raise ValidationError(f"Generation output contract failed: {errors[0].message}")
    if response.payload["unit_id"] != unit_id or response.payload["layer"] != layer:
        raise ValidationError("Generation output returned the wrong unit or layer")

    created_renderings = [
        _candidate_to_rendering(unit, layer, style_profile, model_profile_payload, prompt_version, candidate, job_id)
        for candidate in response.payload["candidates"]
    ]
    _mark_latest_layer(unit_id, layer)
    job = {
        "job_id": job_id,
        "unit_id": unit_id,
        "layer": layer,
        "status": "completed",
        "input_hash": input_hash,
        "model_profile": model_profile_payload["model_profile_id"],
        "prompt_version": prompt_version,
        "seed": seed,
        "runtime_metadata": {
            "adapter": adapter.name,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "candidate_count": len(created_renderings),
            "created_rendering_ids": [item["rendering_id"] for item in created_renderings],
            "downstream_layers": _downstream_layers(layer),
            **response.runtime_metadata,
        },
        "output": {
            "unit_id": unit_id,
            "layer": layer,
            "candidates": [
                {
                    "text": item["text"],
                    "rationale": item["rationale"],
                    "alignment_hints": item.get("alignment_ids", []),
                    "drift_flags": item.get("drift_flags", []),
                    "metrics": item.get("metrics", {}),
                }
                for item in created_renderings
            ],
        },
    }
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO generation_jobs(
                job_id, unit_id, layer, status, input_hash, model_profile, prompt_version, seed, runtime_metadata, output_payload
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job["job_id"],
                job["unit_id"],
                job["layer"],
                job["status"],
                job["input_hash"],
                job["model_profile"],
                job["prompt_version"],
                job["seed"],
                json.dumps(job["runtime_metadata"], sort_keys=True),
                json.dumps(job["output"], sort_keys=True),
            ),
        )
    return job


def generate_for_psalm(
    psalm_id: str,
    layer: str,
    style_profile: str = "study_literal",
    model_profile: str | None = None,
    seed: int = 42,
    candidate_count: int = 1,
) -> list[dict[str, Any]]:
    psalm = registry_service.load_psalm(psalm_id)
    return [
        generate_for_unit(
            unit["unit_id"],
            layer=layer,
            style_profile=style_profile,
            model_profile=model_profile,
            seed=seed,
            candidate_count=candidate_count,
        )
        for unit in psalm["units"]
    ]


def _deserialize_job(row: dict[str, Any]) -> dict[str, Any]:
    row["runtime_metadata"] = json.loads(row["runtime_metadata"])
    output_payload = row.get("output_payload")
    row["output"] = json.loads(output_payload) if output_payload else None
    row.pop("output_payload", None)
    return row


def get_job(job_id: str) -> dict[str, Any]:
    _ensure_job_table()
    with get_connection() as connection:
        row = connection.execute("SELECT * FROM generation_jobs WHERE job_id = ?", (job_id,)).fetchone()
    if row is None:
        raise NotFoundError(job_id)
    return _deserialize_job(dict(row))


def rerun_layer(
    unit_id: str,
    layer: str,
    style_profile: str = "study_literal",
    model_profile: str | None = None,
    seed: int = 42,
    candidate_count: int = 1,
) -> dict[str, Any]:
    unit = registry_service.load_unit(unit_id)
    _assert_layer_rules(unit, layer)
    invalidated = _invalidate_downstream(unit_id, layer)
    job = generate_for_unit(
        unit_id=unit_id,
        layer=layer,
        style_profile=style_profile,
        model_profile=model_profile,
        seed=seed,
        candidate_count=candidate_count,
        force=True,
    )
    job["runtime_metadata"]["downstream_invalidated"] = invalidated
    return job
