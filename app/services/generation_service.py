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
from app.services import poetic_analysis_service, registry_service, rendering_service

PASS_ORDER = ["gloss", "literal", "phrase", "concept", "lyric", "metered_lyric"]
PASS_DEPENDENCIES = {
    "gloss": [],
    "literal": ["gloss"],
    "phrase": ["literal"],
    "concept": ["literal", "phrase"],
    "lyric": ["gloss", "literal", "phrase", "concept"],
    "metered_lyric": ["literal", "phrase", "concept", "lyric"],
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
                "greek": token.get("greek"),
                "greek_strong": token.get("greek_strong"),
            }
            for token in unit.get("tokens", [])
        ]
    }
    lxx_witness = next((item for item in unit.get("witnesses", []) if item.get("source_id") == "lxx"), None)
    if lxx_witness:
        locked_inputs["septuagint_greek_witness"] = {
            "source_id": lxx_witness["source_id"],
            "version_title": lxx_witness["versionTitle"],
            "source_version": lxx_witness.get("source_version"),
            "language": lxx_witness["language"],
            "ref": lxx_witness["ref"],
            "text": lxx_witness["text"],
        }
        locked_inputs["septuagint_greek_tokens"] = [
            {
                "token_id": token["token_id"],
                "greek": token.get("greek"),
                "greek_strong": token.get("greek_strong"),
            }
            for token in unit.get("tokens", [])
            if token.get("greek")
        ]
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


def _source_manifest(source_id: str) -> dict[str, Any] | None:
    project = registry_service.load_project()
    return next((item for item in project.get("source_manifests", []) if item["source_id"] == source_id), None)


def _default_translation_basis() -> dict[str, Any]:
    manifest = _source_manifest("uxlc")
    return {
        "basis_type": "hebrew_to_english",
        "source_ids": ["uxlc", "oshb", "macula"],
        "source_language": "he",
        "source_version": manifest["version"] if manifest else "unknown",
        "basis_note": "Canonical Hebrew-first translation basis.",
    }


def _normalize_translation_basis(payload: dict[str, Any] | None) -> dict[str, Any]:
    basis = dict(payload or {})
    default = _default_translation_basis()
    basis_type = str(basis.get("basis_type") or default["basis_type"]).strip()
    if basis_type == "septuagint_greek_to_english":
        raw_source_ids = basis.get("source_ids") or ["lxx", "macula"]
    else:
        raw_source_ids = basis.get("source_ids") or default["source_ids"]
    source_ids = [str(source_id).strip() for source_id in list(raw_source_ids) if str(source_id).strip()]
    source_language = str(basis.get("source_language") or "").strip()
    source_version = str(basis.get("source_version") or "").strip()
    basis_note = str(basis.get("basis_note") or "").strip()
    if basis_type == "septuagint_greek_to_english":
        manifest = _source_manifest("lxx")
        source_ids = source_ids or ["lxx", "macula"]
        source_language = source_language or "grc"
        source_version = source_version or (manifest["version"] if manifest else "unknown")
        basis_note = basis_note or "Translate directly from the Septuagint Greek witness."
    else:
        source_language = source_language or default["source_language"]
        source_version = source_version or default["source_version"]
        basis_note = basis_note or default["basis_note"]
    return {
        "basis_type": basis_type,
        "source_ids": source_ids,
        "source_language": source_language,
        "source_version": source_version,
        "basis_note": basis_note,
    }


def _normalize_variation_basis(layer: str, values: list[str] | None) -> list[str]:
    items = [str(item).strip() for item in (values or []) if str(item).strip()]
    if items:
        return items
    if layer in {"literal", "phrase"}:
        return ["source_grounded_rendering"]
    if layer in {"concept", "lyric", "metered_lyric"}:
        return ["cadence_or_emphasis_shift"]
    return ["deterministic_rendering"]


def _normalize_preserved_source_images(images: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for image in images or []:
        label = str(image.get("label") or "").strip()
        if not label:
            continue
        item = {"label": label}
        source_id = str(image.get("source_id") or "").strip()
        if source_id:
            item["source_id"] = source_id
        token_ids = [str(token_id).strip() for token_id in list(image.get("token_ids") or []) if str(token_id).strip()]
        if token_ids:
            item["token_ids"] = token_ids
        note = str(image.get("note") or "").strip()
        if note:
            item["note"] = note
        normalized.append(item)
    return normalized


def _candidate_key(text: str) -> str:
    return " ".join("".join(character.lower() if character.isalnum() else " " for character in text).split())


def _candidate_word_set(text: str) -> set[str]:
    return {word for word in _candidate_key(text).split() if word}


def _normalize_candidate_text(text: str, preserve_line_breaks: bool = False) -> str:
    raw = str(text).strip()
    if not preserve_line_breaks:
        return " ".join(raw.split()).strip()
    lines = [" ".join(line.split()).strip() for line in raw.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    return "\n".join(line for line in lines if line).strip()


def _too_similar(left: str, right: str) -> bool:
    left_words = _candidate_word_set(left)
    right_words = _candidate_word_set(right)
    if not left_words or not right_words:
        return False
    overlap = len(left_words & right_words) / max(len(left_words | right_words), 1)
    return overlap >= 0.88 and abs(len(left_words) - len(right_words)) <= 1


def _distinctness_score(text: str, prior_texts: list[str]) -> float:
    if not prior_texts:
        return 1.0
    overlaps = []
    current = _candidate_word_set(text)
    for prior in prior_texts:
        prior_words = _candidate_word_set(prior)
        if not current or not prior_words:
            continue
        overlaps.append(len(current & prior_words) / max(len(current | prior_words), 1))
    if not overlaps:
        return 1.0
    return round(max(0.0, 1.0 - max(overlaps)), 2)


def _normalized_drift_flags(flags: list[dict[str, Any] | str] | None) -> list[dict[str, Any]]:
    return [poetic_analysis_service.normalize_flag(flag) for flag in (flags or [])]


def _candidate_sort_key(candidate: dict[str, Any]) -> tuple[Any, ...]:
    flags = candidate.get("drift_flags", [])
    has_high = any(flag.get("severity") == "high" for flag in flags)
    has_medium = any(flag.get("severity") == "medium" for flag in flags)
    basis_type = candidate["translation_basis"]["basis_type"]
    basis_rank = 0 if basis_type == "hebrew_to_english" else 1
    grounding = float(candidate.get("grounding_confidence", 0.0))
    distinctness = float(candidate.get("metrics", {}).get("distinctness_score", 0.0))
    return (has_high, has_medium, -grounding, basis_rank, -distinctness, candidate["text"].casefold())


def _normalize_candidates(layer: str, unit: dict[str, Any], candidates: list[dict[str, Any]], candidate_count: int) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    preserve_line_breaks = layer in {"lyric", "metered_lyric"}
    for candidate in candidates:
        text = _normalize_candidate_text(candidate.get("text") or "", preserve_line_breaks=preserve_line_breaks)
        if not text:
            continue
        key = _candidate_key(text)
        if not key or key in seen:
            continue
        item = {
            "text": text,
            "rationale": _normalize_candidate_text(candidate.get("rationale") or "Generated from grounded source inputs."),
            "alignment_hints": [str(value).strip() for value in list(candidate.get("alignment_hints") or []) if str(value).strip()],
            "drift_flags": _normalized_drift_flags(candidate.get("drift_flags")),
            "metrics": dict(candidate.get("metrics") or {}),
            "variation_basis": _normalize_variation_basis(layer, candidate.get("variation_basis")),
            "preserved_source_images": _normalize_preserved_source_images(candidate.get("preserved_source_images")),
            "differentiator": _normalize_candidate_text(candidate.get("differentiator") or "") or "grounded alternate",
            "grounding_confidence": round(float(candidate.get("grounding_confidence", candidate.get("metrics", {}).get("grounding_score", 0.72))), 2),
            "translation_basis": _normalize_translation_basis(candidate.get("translation_basis")),
        }
        if not item["preserved_source_images"]:
            source_image = next((token.get("display_gloss") for token in unit.get("tokens", []) if token.get("display_gloss")), None)
            if source_image:
                item["preserved_source_images"] = [{"label": str(source_image), "source_id": item["translation_basis"]["source_ids"][0]}]
        seen.add(key)
        normalized.append(item)
    ranked = sorted(normalized, key=_candidate_sort_key)
    kept: list[dict[str, Any]] = []
    prior_texts: list[str] = []
    for candidate in ranked:
        if any(_too_similar(candidate["text"], prior) for prior in prior_texts):
            continue
        metrics = dict(candidate.get("metrics") or {})
        metrics.setdefault("grounding_score", candidate["grounding_confidence"])
        metrics["distinctness_score"] = _distinctness_score(candidate["text"], prior_texts)
        candidate["metrics"] = metrics
        kept.append(candidate)
        prior_texts.append(candidate["text"])
        if len(kept) >= candidate_count:
            break
    return kept


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
        translation_basis=candidate.get("translation_basis"),
        variation_basis=candidate.get("variation_basis"),
        preserved_source_images=candidate.get("preserved_source_images"),
        differentiator=candidate.get("differentiator"),
        grounding_confidence=candidate.get("grounding_confidence"),
        provenance={
            "source_ids": candidate.get("translation_basis", {}).get("source_ids", ["uxlc", "oshb", "macula"]),
            "generator": "generation-service",
            "model_profile_id": model_profile["model_profile_id"],
            "job_id": job_id,
            "prompt_version": prompt_version,
            "translation_basis": candidate.get("translation_basis"),
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
    if candidate_count < 1 or candidate_count > 5:
        raise ValidationError("candidate_count must be between 1 and 5")
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

    normalized_candidates = _normalize_candidates(layer, unit, response.payload["candidates"], candidate_count)
    created_renderings = [
        _candidate_to_rendering(unit, layer, style_profile, model_profile_payload, prompt_version, candidate, job_id)
        for candidate in normalized_candidates
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
                    "variation_basis": item.get("variation_basis", []),
                    "preserved_source_images": item.get("preserved_source_images", []),
                    "differentiator": item.get("differentiator"),
                    "grounding_confidence": item.get("grounding_confidence"),
                    "translation_basis": item.get("translation_basis"),
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
