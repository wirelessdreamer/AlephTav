"""Source-script checks shared by translation generation paths."""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from app.core.errors import LicensePolicyError

_HEBREW_TEXT_RE = re.compile(r"[\u0590-\u05FF]")


class GreekGenerationUnavailableError(LicensePolicyError):
    """Greek may be visible for study without being an eligible generation source."""


def generation_prompt_rules(layer: str, psalm_id: str | None = None) -> str:
    """Describe the same source restriction enforced at the output/apply boundary."""
    from app.services import registry_service, source_capability_service

    sources = [
        f"{source['source_id']} ({source.get('version', 'version not recorded')})"
        for source in registry_service.load_project().get("source_manifests", [])
        if source.get("source_language") not in {"grc", "en"}
        and source_capability_service.effective_capabilities(source["source_id"])["generation"]
    ]
    from app.services import greek_generation_service

    greek = greek_generation_service.context(psalm_id) if psalm_id else None
    rules = [
        "## Source limits for this generation request",
        (
            "Greek-source generation is enabled for the exact approved evidence supplied below."
            if greek
            else "Greek-source generation is not enabled. Greek text visible in study or "
            "mentioned in briefing choices is not a supplied, approved generation source."
        ),
        f"Permitted Hebrew sources: {', '.join(sources) or '(none)'}.",
        "Use translation_basis.basis_type=hebrew_to_english and source_language=he "
        "for Hebrew-based output; source_anchor.source_language must also be he. "
        "Use only the listed source_ids and their actual versions, and quote the supplied "
        "Hebrew in source_anchor.source_text. Do not invent Greek text or source identities.",
    ]
    if layer in {"gloss", "literal"}:
        rules.append(
            "This is the shared Hebrew baseline. Preserve the Hebrew reading even when a "
            "briefing answer requests a Greek variant for the English setting. Defer that "
            "variant to the setting; identify that deferral in accuracy_note."
        )
    elif not greek:
        rules.append(
            "If a saved decision requires an unavailable Greek reading, return that unit "
            "with candidates=[] rather than silently substituting a Hebrew reading or "
            "labeling a Greek-derived rendering as Hebrew. Still translate the other units "
            "whose decisions the permitted Hebrew source supports."
        )
    return "\n".join(rules)


def require_generation_basis_available(
    candidate: dict[str, Any], unit_id: str | None = None
) -> dict[str, Any] | None:
    """Recheck exact source permission, revision, tokens and target map before saving."""
    basis = candidate.get("translation_basis") or {}
    anchor = candidate.get("source_anchor") or {}
    source_ids = basis.get("source_ids") or []
    if (
        basis.get("basis_type") == "septuagint_greek_to_english"
        or str(basis.get("source_language", "")).casefold() in {"grc", "greek", "ell"}
        or str(anchor.get("source_language", "")).casefold() in {"grc", "greek", "ell"}
        or any(str(source) == "lxx" or str(source).startswith("lxx.") for source in source_ids)
        or any(str(token).startswith("lxx.") for token in anchor.get("token_ids", []))
        or any(
            character.isalpha() and "GREEK" in unicodedata.name(character, "")
            for character in anchor.get("source_text", "")
        )
    ):
        from app.services import greek_generation_service

        if not unit_id:
            raise GreekGenerationUnavailableError(
                "Greek generation requires an approved revision/token source and target unit"
            )
        try:
            return greek_generation_service.resolve(candidate, unit_id)
        except (ValueError, OSError, KeyError) as error:
            raise LicensePolicyError(f"Greek source could not be verified: {error}") from error
    return None


def greek_source_anchor_problem(source_text: str) -> str | None:
    if _HEBREW_TEXT_RE.search(source_text):
        return "Septuagint-derived source_anchor.source_text contains Hebrew text"
    if not any(
        character.isalpha() and "GREEK" in unicodedata.name(character, "")
        for character in source_text
    ):
        return "Septuagint-derived source_anchor.source_text lacks Greek text"
    return None
