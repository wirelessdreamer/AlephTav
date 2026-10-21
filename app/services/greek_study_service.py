"""Read-only Greek study queries over an immutable, policy-checked catalog view.

No source package is installed or activated by this module. Catalog publication and
current capability policy remain the authority for every read, including old cursors.
"""

from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any, Literal

from app.core.errors import NotFoundError, ValidationError


class StaleStudyError(ValidationError):
    """Restart the complete view; its snapshot or policy is no longer available."""


def load_public_view(snapshot_id: str | None = None, policy_id: str | None = None) -> StudyView:
    from jsonschema import ValidationError as SchemaValidationError  # type: ignore[import-untyped]

    from app.core.errors import LicensePolicyError
    from app.services.greek_study_export_service import availability

    try:
        view = load_view(snapshot_id, policy_id)
        if not availability(view.descriptor):
            raise LicensePolicyError("Greek study is awaiting applicable source release approvals")
        return view
    except (LicensePolicyError, NotFoundError, StaleStudyError):
        raise
    except (OSError, ValueError, KeyError, TypeError, ValidationError, SchemaValidationError) as error:
        # Strict schema diagnostics can embed source text. Public callers need
        # a bounded unavailable state, not the unpublished package payload.
        raise LicensePolicyError("Greek study source could not be verified") from error


def load_view(snapshot_id: str | None = None, policy_id: str | None = None) -> StudyView:
    from app.core.ids import parse_unit_id
    from app.services.greek_catalog_projection_service import canonical_projection
    from app.services.source_capability_service import policy_revision
    from app.services.study_snapshot_service import active_snapshot

    # Bind before active_snapshot performs its first permission check. A later
    # revocation cannot be returned as if these bytes had passed the new policy.
    current_policy = policy_revision()
    if policy_id is not None and policy_id != current_policy:
        raise StaleStudyError("study_stale: source policy changed; restart the complete view")
    descriptor = active_snapshot(snapshot_id)
    payload = canonical_projection(descriptor)
    flattened = []
    unit_ids: set[str] = set()
    token_ids: set[str] = set()
    for unit in payload["units"]:
        identity = parse_unit_id(unit["unit_id"], require_versioned=True)
        if (
            identity.corpus != "lxx"
            or identity.edition_id != descriptor["edition_id"]
            or identity.text_revision_id != descriptor["text_revision_id"]
            or unit["unit_id"] in unit_ids
        ):
            raise ValidationError("Greek catalog unit scope mismatch/duplicate")
        unit_ids.add(unit["unit_id"])
        for token in unit["tokens"]:
            if token["token_id"] in token_ids:
                raise ValidationError("Greek catalog token ownership mismatch/duplicate")
            token_ids.add(token["token_id"])
            flattened.append(
                {
                    **token,
                    "unit_id": unit["unit_id"],
                    "psalm": int(identity.psalm_id[2:]),
                    "verse": identity.verse,
                }
            )
    payload["tokens"] = flattened
    if policy_revision() != current_policy:
        raise StaleStudyError("study_stale: source policy changed during read")
    return StudyView(descriptor, payload, current_policy)


@dataclass(frozen=True)
class ConcordanceQuery:
    study_snapshot_id: str
    policy_revision_id: str
    query_kind: Literal["lexeme_id", "lemma_text", "identifier", "surface"]
    value: str
    identifier_scheme: str | None = None
    analysis_scope: Literal["reviewed", "proposed", "all"] = "all"
    analysis_selection: Literal["selected", "possible"] = "possible"
    match_unit: Literal["token", "expression"] = "token"
    expand_components: bool = False

    def validate(self) -> None:
        if self.query_kind not in {"lexeme_id", "lemma_text", "identifier", "surface"}:
            raise ValidationError("Unknown query kind")
        if self.analysis_scope not in {"reviewed", "proposed", "all"}:
            raise ValidationError("Unknown analysis scope")
        if self.analysis_selection not in {"selected", "possible"}:
            raise ValidationError("Unknown analysis selection")
        if self.match_unit not in {"token", "expression"} or not self.value:
            raise ValidationError("Invalid match unit or empty query")
        if (self.query_kind == "identifier") != bool(self.identifier_scheme):
            raise ValidationError("Identifier queries require an explicit scheme only")


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def _scope(analysis: dict[str, Any], query: ConcordanceQuery) -> bool:
    status = analysis.get("status", "unresolved")
    if query.analysis_scope == "reviewed" and status != "reviewed":
        return False
    if query.analysis_scope == "proposed" and status != "proposed":
        return False
    return status in {"reviewed", "proposed"}


def _matches(analysis: dict[str, Any], query: ConcordanceQuery) -> bool:
    if not _scope(analysis, query):
        return False
    if query.query_kind in {"lexeme_id", "lemma_text"}:
        return (
            analysis.get("lexeme_id" if query.query_kind == "lexeme_id" else "lemma") == query.value
        )
    direct_relations = {"entry", "equivalent", "exact", "assignment"}
    identifiers = [
        item
        for item in analysis.get("identifiers", [])
        if item.get("relation", "assignment") in direct_relations
    ]
    if query.expand_components:
        identifiers = [
            *identifiers,
            *analysis.get("component_identifiers", []),
            *[
                item
                for item in analysis.get("identifiers", [])
                if item.get("relation") in {"combination_component", "crasis_component"}
            ],
        ]
    return any(
        item.get("scheme") == query.identifier_scheme and item.get("value") == query.value
        for item in identifiers
    )


class StudyView:
    """One immutable catalog payload; the caller must recheck policy before creating it."""

    def __init__(self, descriptor: dict[str, Any], payload: dict[str, Any], policy_id: str):
        self.descriptor = descriptor
        self.payload = payload
        self.snapshot_id = descriptor["study_snapshot_id"]
        self.policy_id = policy_id
        self.tokens = {token["token_id"]: token for token in payload.get("tokens", [])}
        self.analyses: dict[str, list[dict[str, Any]]] = {}
        for analysis in payload.get("analyses", []):
            self.analyses.setdefault(analysis["token_id"], []).append(analysis)

    def identity(self) -> dict[str, str]:
        return {"study_snapshot_id": self.snapshot_id, "policy_revision_id": self.policy_id}

    def require_identity(self, snapshot_id: str, policy_id: str) -> None:
        if snapshot_id != self.snapshot_id or policy_id != self.policy_id:
            raise StaleStudyError("study_stale: restart the complete study view")

    def concordance(
        self, query: ConcordanceQuery, *, page_size: int = 50, cursor: str | None = None
    ) -> dict[str, Any]:
        query.validate()
        self.require_identity(query.study_snapshot_id, query.policy_revision_id)
        if not 1 <= page_size <= 200:
            raise ValidationError("Page size must be between 1 and 200")
        fingerprint = _digest(asdict(query))
        offset = 0
        if cursor:
            try:
                state = json.loads(base64.urlsafe_b64decode(cursor.encode()))
                if state["query"] != fingerprint or type(state["offset"]) is not int:
                    raise ValueError
                offset = state["offset"]
                if offset <= 0:
                    raise ValueError
            except (ValueError, KeyError, TypeError) as error:
                raise StaleStudyError("study_stale: cursor does not bind this query") from error
        candidates = (
            list(self.tokens.values())
            if query.match_unit == "token"
            else self.payload.get("expressions", [])
        )
        matches = []
        unresolved = 0
        for occurrence in candidates:
            token_ids = (
                [occurrence["token_id"]] if query.match_unit == "token" else occurrence["token_ids"]
            )
            analyses = (
                self.analyses.get(token_ids[0], [])
                if query.match_unit == "token"
                else occurrence.get("analyses", [])
            )
            if not analyses or all(a.get("status") == "unresolved" for a in analyses):
                unresolved += 1
            if query.analysis_selection == "selected":
                selected = occurrence.get("selected_analysis_id")
                analyses = [
                    a
                    for a in analyses
                    if a.get("analysis_id") == selected and a.get("status") == "reviewed"
                ]
            evidence = [a for a in analyses if _matches(a, query)]
            surface_match = (
                query.query_kind == "surface" and occurrence.get("surface") == query.value
            )
            if surface_match:
                evidence = [a for a in analyses if _scope(a, query)]
                if query.analysis_scope != "all" or query.analysis_selection != "possible":
                    surface_match = bool(evidence)
            if not evidence and not surface_match:
                continue
            first = self.tokens[token_ids[0]]
            matches.append(
                {
                    "occurrence_id": occurrence.get("occurrence_id", token_ids[0]),
                    "token_ids": token_ids,
                    "unit_id": first["unit_id"],
                    "psalm": first["psalm"],
                    "verse": first["verse"],
                    "position": first["position"],
                    "surface": occurrence.get("surface", first["surface"]),
                    "analysis_statuses": sorted({a["status"] for a in evidence}),
                }
            )
        matches.sort(
            key=lambda row: (row["psalm"], row["verse"], row["position"], row["occurrence_id"])
        )
        if offset > len(matches):
            raise StaleStudyError("study_stale: invalid cursor offset")
        page = matches[offset : offset + page_size]
        next_offset = offset + len(page)
        next_cursor = None
        if next_offset < len(matches):
            next_cursor = base64.urlsafe_b64encode(
                json.dumps(
                    {
                        "query": fingerprint,
                        "offset": next_offset,
                    }
                ).encode()
            ).decode()
        return {
            **self.identity(),
            "query": asdict(query),
            "match_unit": query.match_unit,
            "total_matches": len(matches),
            "total_tokens": len({t for row in matches for t in row["token_ids"]}),
            "total_verses": len({(row["psalm"], row["verse"]) for row in matches}),
            "counts_by_analysis_status": {
                status: sum(status in row["analysis_statuses"] for row in matches)
                for status in ("reviewed", "proposed")
            },
            "coverage": {
                "total_occurrences": len(candidates),
                "unresolved": unresolved,
                "statement": "Unresolved analyses are not proven nonmatches.",
            },
            "matches": page,
            "next_cursor": next_cursor,
        }

    def card(self, token_id: str) -> dict[str, Any]:
        if token_id not in self.tokens:
            raise NotFoundError(f"Greek token not found: {token_id}")
        token = self.tokens[token_id]
        query = ConcordanceQuery(
            study_snapshot_id=self.snapshot_id,
            policy_revision_id=self.policy_id,
            query_kind="surface",
            value=token["surface"],
        )
        counts = self.concordance(query)
        return {
            **self.identity(),
            "token": token,
            "analyses": self.analyses.get(token_id, []),
            "query": asdict(query),
            "counts": {
                key: counts[key]
                for key in ("total_matches", "total_tokens", "total_verses", "coverage")
            },
            "dictionary_entries": self._token_entries(token_id),
            "source_attribution": self.payload.get("source_attribution", []),
        }

    def _token_entries(self, token_id: str) -> list[dict[str, Any]]:
        entry_ids = {
            entry_id for a in self.analyses.get(token_id, []) for entry_id in a.get("entry_ids", [])
        }
        return [
            {
                key: entry[key]
                for key in ("entry_id", "headword", "gloss", "attribution")
                if key in entry
            }
            for entry in self.payload.get("entries", [])
            if entry["entry_id"] in entry_ids
        ]

    def entry(self, entry_id: str) -> dict[str, Any]:
        for entry in self.payload.get("entries", []):
            if entry["entry_id"] == entry_id:
                return {**self.identity(), "entry": entry}
        raise NotFoundError(f"Greek dictionary entry not found: {entry_id}")

    def identifiers(self, scheme: str, value: str) -> dict[str, Any]:
        entries = [
            entry
            for entry in self.payload.get("entries", [])
            if any(
                item["scheme"] == scheme
                and item["value"] == value
                and item.get("relation", "entry") in {"entry", "equivalent", "exact", "assignment"}
                for item in entry.get("identifiers", [])
            )
        ]
        relationships = [
            {"entry_id": entry["entry_id"], "identifier": identifier}
            for entry in self.payload.get("entries", [])
            for identifier in entry.get("identifiers", [])
            if identifier["scheme"] == scheme
            and identifier["value"] == value
            and identifier.get("relation", "entry")
            not in {"entry", "equivalent", "exact", "assignment"}
        ]
        return {
            **self.identity(),
            "scheme": scheme,
            "value": value,
            "entries": entries,
            "total_entries": len(entries),
            "relationships": relationships,
        }
