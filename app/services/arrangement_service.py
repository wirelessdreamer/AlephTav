"""Song settings of a psalm: sections of English lines free of the verse boundaries.

A verse rendering follows its verse. An arrangement does not have to: its lines are
grouped into sections (verse, chorus, bridge), a section can be sung again by
reference, and a line can carry words from several verses, compress, reorder, or add
what the Hebrew does not say. That freedom is paid for in the open. Every line is
anchored to the Hebrew tokens it renders and names how it departs from them; the
Hebrew left uncarried is computed from the anchors, never assumed; and departures
that need review collect approvals under the project's review policy.

Arrangements live on the psalm meta file beside the psalm analyses. Their audit
records are anchored on the psalm's first unit, as the analyses' are, because an
audit id is patterned to a unit.
"""

from __future__ import annotations

import re
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from app.core.errors import NotFoundError, ReviewRequiredError, ValidationError
from app.services import audit_service, registry_service, review_service
from app.services import psalm_translations_service as translations

LINE_LIBERTIES = ("tracks", "compressed", "expanded", "reordered", "added")
SECTION_KINDS = ("verse", "chorus", "refrain", "bridge", "intro", "outro", "other")
STATUSES = ("draft", "proposed", "accepted", "superseded")

#: Distinct reviewers each kind of departure needs before a setting can be accepted.
#: A project can override these under review_policy.arrangement_required_approvals.
DEFAULT_REQUIRED_APPROVALS = {
    "tracks": 0,
    "reordered": 0,
    "repeated": 0,
    "compressed": 1,
    "expanded": 1,
    "added": 1,
    "dropped": 2,
}

#: A refrain is at least this many words the Hebrew repeats in two or more verses.
MIN_REFRAIN_LENGTH = 3

_POINTS = re.compile(r"[֑-ׇ]")


def _now() -> str:
    return datetime.now(UTC).isoformat()


def required_approvals() -> dict[str, int]:
    policy = review_service.review_policy()
    return {**DEFAULT_REQUIRED_APPROVALS, **policy.get("arrangement_required_approvals", {})}


# -- Lookups -------------------------------------------------------------------


def _token_index(psalm: dict[str, Any]) -> dict[str, tuple[str, dict[str, Any]]]:
    """token_id -> (unit_id, token) for every token of the psalm."""
    return {
        token["token_id"]: (unit["unit_id"], token)
        for unit in psalm["units"]
        for token in unit.get("tokens", [])
    }


def _find_arrangement(meta: dict[str, Any], arrangement_id: str) -> dict[str, Any]:
    for arrangement in meta.get("arrangements", []):
        if arrangement["arrangement_id"] == arrangement_id:
            return arrangement
    raise NotFoundError(f"Arrangement not found: {arrangement_id}")


def _find_section(arrangement: dict[str, Any], section_id: str) -> dict[str, Any]:
    for section in arrangement["sections"]:
        if section["section_id"] == section_id:
            return section
    raise NotFoundError(f"Section not found: {section_id}")


def _find_line(arrangement: dict[str, Any], line_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    for section in arrangement["sections"]:
        for line in section["lines"]:
            if line["line_id"] == line_id:
                return section, line
    raise NotFoundError(f"Line not found: {line_id}")


def _next_id(prefix: str, existing: list[str]) -> str:
    numbers = [int(value.rsplit(".", 1)[1]) for value in existing if value.startswith(prefix)]
    return f"{prefix}{max(numbers, default=0) + 1:04d}"


def _next_section_id(arrangement: dict[str, Any]) -> str:
    return _next_id("sec.", [s["section_id"] for s in arrangement["sections"]])


def _next_line_id(arrangement: dict[str, Any]) -> str:
    return _next_id(
        "ln.", [line["line_id"] for s in arrangement["sections"] for line in s["lines"]]
    )


def list_arrangements(psalm_id: str, translation_id: str | None = None) -> list[dict[str, Any]]:
    """One translation's song settings, newest last."""
    return [
        arrangement
        for arrangement in registry_service.load_psalm_meta(psalm_id).get("arrangements", [])
        if translations.in_translation(arrangement, translation_id)
    ]


def get_arrangement(psalm_id: str, arrangement_id: str) -> dict[str, Any]:
    return _find_arrangement(registry_service.load_psalm_meta(psalm_id), arrangement_id)


# -- Validation of what a line says it renders ---------------------------------------


def anchors_from_tokens(psalm: dict[str, Any], token_ids: list[str]) -> list[dict[str, Any]]:
    """Group token ids by their unit, in the Hebrew's order. Unknown ids are refused."""
    index = _token_index(psalm)
    unknown = [token_id for token_id in token_ids if token_id not in index]
    if unknown:
        raise ValidationError(f"Tokens not in {psalm['psalm_id']}: {', '.join(unknown)}")
    order = {token_id: position for position, token_id in enumerate(index)}
    grouped: dict[str, list[str]] = {}
    for token_id in sorted(set(token_ids), key=order.__getitem__):
        grouped.setdefault(index[token_id][0], []).append(token_id)
    return [{"unit_id": unit_id, "token_ids": ids} for unit_id, ids in grouped.items()]


def _clean_anchors(psalm: dict[str, Any], anchors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    index = _token_index(psalm)
    token_ids: list[str] = []
    for anchor in anchors:
        for token_id in anchor.get("token_ids", []):
            owner = index.get(token_id)
            if owner is not None and owner[0] != anchor.get("unit_id"):
                raise ValidationError(f"{token_id} is not in {anchor.get('unit_id')}")
            token_ids.append(token_id)
    return anchors_from_tokens(psalm, token_ids)


def _clean_liberty(liberty: str, anchors: list[dict[str, Any]]) -> str:
    if liberty not in LINE_LIBERTIES:
        raise ValidationError(f"Unknown liberty: {liberty}")
    # A line that renders no Hebrew is added, whatever it was called.
    return liberty if anchors else "added"


def _new_line(
    arrangement: dict[str, Any],
    psalm: dict[str, Any],
    text: str,
    anchors: list[dict[str, Any]],
    liberty: str,
    rationale: str,
) -> dict[str, Any]:
    cleaned = text.strip()
    if not cleaned:
        raise ValidationError("A line needs text")
    anchors = _clean_anchors(psalm, anchors)
    return {
        "line_id": _next_line_id(arrangement),
        "text": cleaned,
        "anchors": anchors,
        "liberty": _clean_liberty(liberty, anchors),
        "rationale": rationale.strip(),
        "approvals": [],
    }


def _clean_kind(kind: str) -> str:
    if kind not in SECTION_KINDS:
        raise ValidationError(f"Unknown section kind: {kind}")
    return kind


def _check_repeat_of(arrangement: dict[str, Any], repeat_of: str | None) -> None:
    if repeat_of is None:
        return
    source = _find_section(arrangement, repeat_of)
    if source["repeat_of"] is not None:
        raise ValidationError("A repeat repeats a written section, not another repeat")


# -- Writing, always audited ---------------------------------------------------------


def _audit(
    psalm_id: str,
    meta: dict[str, Any],
    arrangement: dict[str, Any],
    before: Any,
    summary: str,
    rationale: str,
    created_by: str,
    change_type: str,
) -> None:
    """Record the change on the psalm's first unit, then save the meta with its audit id."""
    anchor = registry_service.load_unit(meta["unit_ids"][0])
    record = audit_service.create_audit_record(
        anchor,
        before_hash=registry_service.file_hash(before),
        after_hash=registry_service.file_hash(
            {k: v for k, v in arrangement.items() if k != "audit_ids"}
        ),
        summary=summary,
        rationale=rationale,
        created_by=created_by,
        entity_type="arrangement",
        entity_id=arrangement["arrangement_id"],
        change_type=change_type,
    )
    registry_service.save_unit(anchor)
    arrangement["audit_ids"].append(record["audit_id"])
    registry_service.save_psalm_meta(psalm_id, meta)


def _mutate(
    psalm_id: str,
    arrangement_id: str,
    mutator: Any,
    summary: str,
    rationale: str,
    created_by: str,
) -> dict[str, Any]:
    """Apply ``mutator`` to the arrangement, audit it, and return the arrangement's view."""
    meta = registry_service.load_psalm_meta(psalm_id)
    arrangement = _find_arrangement(meta, arrangement_id)
    before = deepcopy(arrangement)
    before.pop("audit_ids", None)
    mutator(arrangement, registry_service.load_psalm(psalm_id))
    arrangement["updated_at"] = _now()
    _audit(psalm_id, meta, arrangement, before, summary, rationale, created_by, "update")
    return arrangement_view(psalm_id, arrangement_id)


def build_sections(
    psalm: dict[str, Any], arrangement: dict[str, Any], specs: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Sections from plain specs, where ``repeat_of`` names another spec's ``key``.

    Lines give either ``anchors`` or bare ``token_ids``; ids are assigned here.
    """
    keys: dict[str, str] = {}
    for spec in specs:
        section_id = _next_id("sec.", [*keys.values()])
        if spec.get("key") in keys:
            raise ValidationError(f"Two sections share the key {spec['key']}")
        keys[str(spec.get("key", section_id))] = section_id
    arrangement["sections"] = []
    for spec, section_id in zip(specs, keys.values(), strict=True):
        repeat_key = spec.get("repeat_of")
        repeat_of = None
        if repeat_key is not None:
            if repeat_key not in keys:
                raise ValidationError(f"{spec.get('label')} repeats an unknown section")
            repeat_of = keys[repeat_key]
        section: dict[str, Any] = {
            "section_id": section_id,
            "kind": _clean_kind(spec.get("kind", "verse")),
            "label": str(spec.get("label", "")).strip(),
            "repeat_of": repeat_of,
            "lines": [],
        }
        arrangement["sections"].append(section)
        for line in spec.get("lines", []):
            anchors = line.get("anchors")
            if anchors is None:
                anchors = anchors_from_tokens(psalm, line.get("token_ids", []))
            section["lines"].append(
                _new_line(
                    arrangement,
                    psalm,
                    line.get("text", ""),
                    anchors,
                    line.get("liberty", "tracks"),
                    line.get("rationale", ""),
                )
            )
    for section in arrangement["sections"]:
        _check_repeat_of(arrangement, section["repeat_of"])
    return arrangement["sections"]


def create_arrangement(
    psalm_id: str,
    *,
    layer: str = "lyric",
    title: str = "Song setting",
    created_by: str = "reviewer",
    sections: list[dict[str, Any]] | None = None,
    omissions: list[dict[str, Any]] | None = None,
    created_via: str = "human",
    generation_run_id: str | None = None,
    prompt_template_version: str | None = None,
    status: str = "draft",
    guidance: str = "",
    translation_id: str | None = None,
) -> dict[str, Any]:
    """A new setting, empty or from section specs (see ``build_sections``)."""
    if status not in STATUSES:
        raise ValidationError(f"Unknown status: {status}")
    translations.require(psalm_id, translation_id)
    psalm = registry_service.load_psalm(psalm_id)
    meta = registry_service.load_psalm_meta(psalm_id)
    existing = [a["arrangement_id"] for a in meta.get("arrangements", [])]
    now = _now()
    arrangement: dict[str, Any] = {
        "arrangement_id": _next_id(f"arr.{psalm_id}.", existing),
        "psalm_id": psalm_id,
        "title": title.strip() or "Song setting",
        "layer": layer,
        "status": status,
        "guidance": guidance,
        "sections": [],
        "omissions": [],
        "created_by": created_by,
        "created_via": created_via,
        "generation_run_id": generation_run_id,
        "prompt_template_version": prompt_template_version,
        "created_at": now,
        "updated_at": now,
        "audit_ids": [],
    }
    translations.tag(arrangement, translation_id)
    build_sections(psalm, arrangement, sections or [])
    for omission in omissions or []:
        anchors = anchors_from_tokens(psalm, omission.get("token_ids", []))
        for anchor in anchors:
            arrangement["omissions"].append(
                {
                    "unit_id": anchor["unit_id"],
                    "token_ids": anchor["token_ids"],
                    "rationale": str(omission.get("rationale", "")).strip(),
                    "approvals": [],
                }
            )
    meta.setdefault("arrangements", []).append(arrangement)
    _audit(
        psalm_id,
        meta,
        arrangement,
        {},
        summary=f"Create song setting “{arrangement['title']}”",
        rationale=f"{created_via} arrangement",
        created_by=created_by,
        change_type="create",
    )
    return arrangement_view(psalm_id, arrangement["arrangement_id"])


def delete_arrangement(
    psalm_id: str,
    arrangement_id: str,
    *,
    created_by: str = "reviewer",
    rationale: str = "remove song setting",
) -> dict[str, str]:
    """Delete one song setting while retaining an audit record of the removal."""
    meta = registry_service.load_psalm_meta(psalm_id)
    arrangement = _find_arrangement(meta, arrangement_id)
    before = deepcopy(arrangement)
    before.pop("audit_ids", None)
    meta["arrangements"].remove(arrangement)

    anchor = registry_service.load_unit(meta["unit_ids"][0])
    record = audit_service.create_audit_record(
        anchor,
        before_hash=registry_service.file_hash(before),
        after_hash=registry_service.file_hash({}),
        summary=f"Delete song setting “{arrangement['title']}”",
        rationale=rationale,
        created_by=created_by,
        entity_type="arrangement",
        entity_id=arrangement_id,
        change_type="delete",
    )
    registry_service.save_unit(anchor)
    registry_service.save_psalm_meta(psalm_id, meta)
    return {"deleted": arrangement_id, "audit_id": record["audit_id"]}


def update_arrangement(
    psalm_id: str,
    arrangement_id: str,
    *,
    created_by: str,
    title: str | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    if status is not None and status not in STATUSES:
        raise ValidationError(f"Unknown status: {status}")
    if status == "accepted":
        view = arrangement_view(psalm_id, arrangement_id)
        unsettled = [item for item in view["liberties"] if not item["settled"]]
        if unsettled:
            raise ReviewRequiredError(
                f"{len(unsettled)} liberties still need approval before the setting is accepted"
            )

    def apply(arrangement: dict[str, Any], _psalm: dict[str, Any]) -> None:
        if title is not None:
            arrangement["title"] = title.strip() or arrangement["title"]
        if status is not None:
            arrangement["status"] = status

    view = _mutate(
        psalm_id,
        arrangement_id,
        apply,
        summary="Update song setting",
        rationale=f"status {status}" if status else "title",
        created_by=created_by,
    )
    if status == "accepted":
        _supersede_others(psalm_id, view["arrangement"], created_by)
    return view


def move_arrangement_to_translation(
    psalm_id: str,
    arrangement_id: str,
    translation_id: str | None,
    *,
    created_by: str = "reviewer",
) -> dict[str, Any]:
    """Reassign a song setting without rebuilding its sections or provenance."""
    translations.require(psalm_id, translation_id)
    current = get_arrangement(psalm_id, arrangement_id)
    previous = current.get("translation_id")
    if previous == translation_id:
        return arrangement_view(psalm_id, arrangement_id)

    def apply(arrangement: dict[str, Any], _psalm: dict[str, Any]) -> None:
        if translation_id is None:
            arrangement.pop("translation_id", None)
        else:
            arrangement["translation_id"] = translation_id

    return _mutate(
        psalm_id,
        arrangement_id,
        apply,
        summary=f"Move song setting to {translation_id or 'the main translation'}",
        rationale=f"from {previous or 'the main translation'}",
        created_by=created_by,
    )


def _supersede_others(psalm_id: str, accepted: dict[str, Any], created_by: str) -> None:
    """An accepted setting replaces its translation's earlier one for the same layer."""
    for other in list_arrangements(psalm_id, accepted.get("translation_id")):
        same_layer = other["layer"] == accepted["layer"]
        if other["arrangement_id"] != accepted["arrangement_id"] and same_layer:
            if other["status"] == "accepted":
                update_arrangement(
                    psalm_id, other["arrangement_id"], created_by=created_by, status="superseded"
                )


def add_section(
    psalm_id: str,
    arrangement_id: str,
    *,
    kind: str,
    label: str,
    created_by: str,
    repeat_of: str | None = None,
    index: int | None = None,
) -> dict[str, Any]:
    def apply(arrangement: dict[str, Any], _psalm: dict[str, Any]) -> None:
        _check_repeat_of(arrangement, repeat_of)
        section: dict[str, Any] = {
            "section_id": _next_section_id(arrangement),
            "kind": _clean_kind(kind),
            "label": label.strip(),
            "repeat_of": repeat_of,
            "lines": [],
        }
        position = len(arrangement["sections"]) if index is None else index
        arrangement["sections"].insert(max(0, position), section)

    what = "a repeat" if repeat_of else f"a {kind}"
    return _mutate(psalm_id, arrangement_id, apply, f"Add {what} section", label, created_by)


def update_section(
    psalm_id: str,
    arrangement_id: str,
    section_id: str,
    *,
    created_by: str,
    kind: str | None = None,
    label: str | None = None,
    index: int | None = None,
) -> dict[str, Any]:
    def apply(arrangement: dict[str, Any], _psalm: dict[str, Any]) -> None:
        section = _find_section(arrangement, section_id)
        if kind is not None:
            section["kind"] = _clean_kind(kind)
        if label is not None:
            section["label"] = label.strip()
        if index is not None:
            arrangement["sections"].remove(section)
            bounded = min(max(0, index), len(arrangement["sections"]))
            arrangement["sections"].insert(bounded, section)

    return _mutate(psalm_id, arrangement_id, apply, "Update section", section_id, created_by)


def remove_section(
    psalm_id: str, arrangement_id: str, section_id: str, *, created_by: str
) -> dict[str, Any]:
    def apply(arrangement: dict[str, Any], _psalm: dict[str, Any]) -> None:
        section = _find_section(arrangement, section_id)
        repeats = [s["label"] for s in arrangement["sections"] if s["repeat_of"] == section_id]
        if repeats:
            raise ValidationError(f"Sung again as {', '.join(repeats)}; remove those first")
        arrangement["sections"].remove(section)

    return _mutate(psalm_id, arrangement_id, apply, "Remove section", section_id, created_by)


def add_line(
    psalm_id: str,
    arrangement_id: str,
    section_id: str,
    *,
    text: str,
    created_by: str,
    anchors: list[dict[str, Any]] | None = None,
    liberty: str = "tracks",
    rationale: str = "",
    index: int | None = None,
) -> dict[str, Any]:
    def apply(arrangement: dict[str, Any], psalm: dict[str, Any]) -> None:
        section = _find_section(arrangement, section_id)
        line = _new_line(arrangement, psalm, text, anchors or [], liberty, rationale)
        position = len(section["lines"]) if index is None else index
        section["lines"].insert(max(0, position), line)

    return _mutate(psalm_id, arrangement_id, apply, "Add line", text.strip(), created_by)


def update_line(
    psalm_id: str,
    arrangement_id: str,
    line_id: str,
    *,
    created_by: str,
    text: str | None = None,
    anchors: list[dict[str, Any]] | None = None,
    liberty: str | None = None,
    rationale: str | None = None,
    index: int | None = None,
) -> dict[str, Any]:
    """Edit a line. Approvals are dropped when what was approved changes."""

    def apply(arrangement: dict[str, Any], psalm: dict[str, Any]) -> None:
        section, line = _find_line(arrangement, line_id)
        before = deepcopy(line)
        if text is not None:
            if not text.strip():
                raise ValidationError("A line needs text")
            line["text"] = text.strip()
        if anchors is not None:
            line["anchors"] = _clean_anchors(psalm, anchors)
        if liberty is not None or anchors is not None:
            line["liberty"] = _clean_liberty(liberty or line["liberty"], line["anchors"])
        if rationale is not None:
            line["rationale"] = rationale.strip()
        if {k: v for k, v in line.items() if k != "approvals"} != {
            k: v for k, v in before.items() if k != "approvals"
        }:
            line["approvals"] = []
        if index is not None:
            section["lines"].remove(line)
            bounded = min(max(0, index), len(section["lines"]))
            section["lines"].insert(bounded, line)

    return _mutate(psalm_id, arrangement_id, apply, "Update line", line_id, created_by)


def remove_line(
    psalm_id: str, arrangement_id: str, line_id: str, *, created_by: str
) -> dict[str, Any]:
    def apply(arrangement: dict[str, Any], _psalm: dict[str, Any]) -> None:
        section, line = _find_line(arrangement, line_id)
        section["lines"].remove(line)

    return _mutate(psalm_id, arrangement_id, apply, "Remove line", line_id, created_by)


def _approval(reviewer: str, reviewer_role: str, note: str) -> dict[str, Any]:
    reviewer, reviewer_role = review_service.validate_reviewer_identity(reviewer, reviewer_role)
    return {
        "reviewer": reviewer,
        "reviewer_role": reviewer_role,
        "note": note.strip(),
        "created_at": _now(),
    }


def _add_approval(approvals: list[dict[str, Any]], approval: dict[str, Any]) -> None:
    """One approval per reviewer: approving again replaces the earlier one."""
    approvals[:] = [a for a in approvals if a["reviewer"] != approval["reviewer"]]
    approvals.append(approval)


def approve_line(
    psalm_id: str,
    arrangement_id: str,
    line_id: str,
    *,
    reviewer: str,
    reviewer_role: str,
    note: str = "",
) -> dict[str, Any]:
    approval = _approval(reviewer, reviewer_role, note)

    def apply(arrangement: dict[str, Any], _psalm: dict[str, Any]) -> None:
        _section, line = _find_line(arrangement, line_id)
        _add_approval(line["approvals"], approval)

    return _mutate(
        psalm_id,
        arrangement_id,
        apply,
        f"Approve the {line_id} liberty",
        note or f"{reviewer_role} approval",
        reviewer,
    )


def approve_omission(
    psalm_id: str,
    arrangement_id: str,
    *,
    unit_id: str,
    token_ids: list[str],
    reviewer: str,
    reviewer_role: str,
    rationale: str = "",
    note: str = "",
) -> dict[str, Any]:
    """Approve leaving Hebrew uncarried. The first approval must say why."""
    if not token_ids:
        raise ValidationError("Name the Hebrew tokens left out")
    approval = _approval(reviewer, reviewer_role, note)

    def apply(arrangement: dict[str, Any], psalm: dict[str, Any]) -> None:
        anchors = _clean_anchors(psalm, [{"unit_id": unit_id, "token_ids": token_ids}])
        wanted = set(anchors[0]["token_ids"]) if anchors else set()
        omission = next(
            (
                o
                for o in arrangement["omissions"]
                if o["unit_id"] == unit_id and set(o["token_ids"]) == wanted
            ),
            None,
        )
        if omission is None:
            if not rationale.strip():
                raise ValidationError("Say why this Hebrew is left out")
            omission = {
                "unit_id": unit_id,
                "token_ids": anchors[0]["token_ids"],
                "rationale": rationale.strip(),
                "approvals": [],
            }
            arrangement["omissions"].append(omission)
        elif rationale.strip():
            omission["rationale"] = rationale.strip()
        _add_approval(omission["approvals"], approval)

    return _mutate(
        psalm_id,
        arrangement_id,
        apply,
        f"Approve leaving out {len(token_ids)} word(s) of {unit_id}",
        rationale or note or f"{reviewer_role} approval",
        reviewer,
    )


# -- Reading a setting as sung ---------------------------------------------------------


def sung_lines(arrangement: dict[str, Any]) -> list[dict[str, Any]]:
    """Every line in the order it is sung, repeats expanded.

    ``time`` counts how often the written section has been sung so far, so the
    chorus's second singing says 2; ``repeat`` marks a line sung again from where it
    was written, and ``variation`` a line a repeat adds for that time only.
    """
    sections = {s["section_id"]: s for s in arrangement["sections"]}
    times: dict[str, int] = {}
    sung: list[dict[str, Any]] = []
    for section in arrangement["sections"]:
        source_id = section["repeat_of"] or section["section_id"]
        times[source_id] = times.get(source_id, 0) + 1
        source = sections.get(source_id)
        if source is None:
            continue
        lines = [(line, section["repeat_of"] is not None, False) for line in source["lines"]]
        if section["repeat_of"]:
            lines += [(line, False, True) for line in section["lines"]]
        for line, repeat, variation in lines:
            sung.append(
                {
                    "position": len(sung) + 1,
                    "section_id": section["section_id"],
                    "section_label": section["label"],
                    "kind": section["kind"],
                    "written_in": section["section_id"] if variation else source_id,
                    "time": times[source_id],
                    "repeat": repeat,
                    "variation": variation,
                    "line": line,
                }
            )
    return sung


def coverage(psalm: dict[str, Any], sung: list[dict[str, Any]]) -> dict[str, Any]:
    """How many times the setting sings each Hebrew token."""
    counts: dict[str, int] = {}
    for item in sung:
        for anchor in item["line"]["anchors"]:
            for token_id in anchor["token_ids"]:
                counts[token_id] = counts.get(token_id, 0) + 1
    units = []
    totals = {"words": 0, "once": 0, "repeated": 0, "dropped": 0}
    for unit in psalm["units"]:
        tokens = []
        for token in unit.get("tokens", []):
            count = counts.get(token["token_id"], 0)
            tokens.append(
                {
                    "token_id": token["token_id"],
                    "surface": token["surface"],
                    "gloss": token.get("display_gloss") or "",
                    "count": count,
                }
            )
            totals["words"] += 1
            totals["dropped" if count == 0 else "once" if count == 1 else "repeated"] += 1
        units.append({"unit_id": unit["unit_id"], "ref": unit["ref"], "tokens": tokens})
    return {"units": units, "totals": totals}


def _dropped_runs(cov: dict[str, Any]) -> list[dict[str, Any]]:
    """Uncarried tokens, grouped into runs of neighbours within a unit."""
    runs: list[dict[str, Any]] = []
    for unit in cov["units"]:
        current: list[dict[str, Any]] = []
        for token in [*unit["tokens"], None]:
            if token is not None and token["count"] == 0:
                current.append(token)
                continue
            if current:
                runs.append({"unit_id": unit["unit_id"], "ref": unit["ref"], "tokens": current})
                current = []
    return runs


def _settled(approvals: list[dict[str, Any]], required: int) -> bool:
    return len({a["reviewer"] for a in approvals}) >= required


def liberties(
    psalm: dict[str, Any], arrangement: dict[str, Any], cov: dict[str, Any]
) -> list[dict[str, Any]]:
    """Every departure from the Hebrew, with what it needs and what it has."""
    rules = required_approvals()
    index = _token_index(psalm)
    sections = {s["section_id"]: s for s in arrangement["sections"]}

    def hebrew(anchors: list[dict[str, Any]]) -> str:
        return " ".join(index[t][1]["surface"] for a in anchors for t in a["token_ids"])

    items: list[dict[str, Any]] = []
    for section in arrangement["sections"]:
        if section["repeat_of"]:
            source = sections.get(section["repeat_of"], {})
            items.append(
                {
                    "key": section["section_id"],
                    "kind": "repeated",
                    "section_id": section["section_id"],
                    "label": section["label"],
                    "text": f"{source.get('label', 'A section')} sung again",
                    "hebrew": "",
                    "rationale": "",
                    "required": rules["repeated"],
                    "approvals": [],
                    "settled": rules["repeated"] == 0,
                }
            )
        for line in section["lines"]:
            if line["liberty"] == "tracks":
                continue
            required = rules[line["liberty"]]
            items.append(
                {
                    "key": line["line_id"],
                    "kind": line["liberty"],
                    "line_id": line["line_id"],
                    "section_id": section["section_id"],
                    "label": section["label"],
                    "text": line["text"],
                    "hebrew": hebrew(line["anchors"]),
                    "rationale": line["rationale"],
                    "required": required,
                    "approvals": line["approvals"],
                    "settled": _settled(line["approvals"], required),
                }
            )
    for run in _dropped_runs(cov):
        token_ids = [t["token_id"] for t in run["tokens"]]
        omission = next(
            (
                o
                for o in arrangement["omissions"]
                if o["unit_id"] == run["unit_id"] and set(o["token_ids"]) == set(token_ids)
            ),
            None,
        )
        approvals = omission["approvals"] if omission else []
        items.append(
            {
                "key": f"drop:{run['unit_id']}:{token_ids[0]}",
                "kind": "dropped",
                "unit_id": run["unit_id"],
                "ref": run["ref"],
                "token_ids": token_ids,
                "label": run["ref"],
                "text": "",
                "hebrew": " ".join(t["surface"] for t in run["tokens"]),
                "rationale": omission["rationale"] if omission else "",
                "required": rules["dropped"],
                "approvals": approvals,
                "settled": _settled(approvals, rules["dropped"]),
            }
        )
    return items


def arrangement_view(psalm_id: str, arrangement_id: str) -> dict[str, Any]:
    """The setting with everything the views read: sung order, coverage, liberties."""
    psalm = registry_service.load_psalm(psalm_id)
    arrangement = _find_arrangement(psalm, arrangement_id)
    sung = sung_lines(arrangement)
    cov = coverage(psalm, sung)
    items = liberties(psalm, arrangement, cov)
    by_kind: dict[str, int] = {}
    for item in sung:
        if not item["repeat"]:
            kind = item["line"]["liberty"]
            by_kind[kind] = by_kind.get(kind, 0) + 1
    by_kind["repeated"] = sum(1 for item in items if item["kind"] == "repeated")
    by_kind["dropped"] = cov["totals"]["dropped"]
    return {
        "arrangement": arrangement,
        "sung": sung,
        "coverage": cov,
        "liberties": items,
        "summary": {
            "sung_lines": len(sung),
            "open": sum(1 for item in items if not item["settled"]),
            "by_kind": by_kind,
        },
        "required_approvals": required_approvals(),
    }


# -- Refrains the Hebrew itself repeats ------------------------------------------------


_FINAL_FORMS = str.maketrans("ךםןףץ", "כמנפצ")
_NOT_LETTERS = re.compile(r"[^א-ת]")


def _word_key(token: dict[str, Any]) -> str:
    """A word's consonants without vowel letters, so spelling variants match.

    לְעֹלָם and לְעוֹלָם are one word; so are יְשׁוּעוֹת and יְשׁוּעֹת. Lemmas are not
    used: a word with a pronoun suffix can carry the pronoun's lemma, which would
    make unrelated words match.
    """
    letters = _NOT_LETTERS.sub("", _POINTS.sub("", token.get("surface", "")))
    letters = letters.translate(_FINAL_FORMS)
    return letters[:1] + letters[1:].replace("ו", "").replace("י", "")


def find_refrains(
    units: list[dict[str, Any]], min_length: int = MIN_REFRAIN_LENGTH
) -> list[dict[str, Any]]:
    """Word sequences the Hebrew repeats in two or more units, longest and widest first."""
    places: dict[tuple[str, ...], dict[str, int]] = {}
    for unit in units:
        keys = [_word_key(token) for token in unit.get("tokens", [])]
        for start in range(len(keys)):
            for end in range(start + min_length, len(keys) + 1):
                gram = tuple(keys[start:end])
                places.setdefault(gram, {}).setdefault(unit["unit_id"], start)
    repeated = {gram: at for gram, at in places.items() if len(at) >= 2}

    chosen: list[tuple[tuple[str, ...], dict[str, int]]] = []
    for gram, at in sorted(repeated.items(), key=lambda item: (-len(item[0]), -len(item[1]))):
        # A shorter run inside a longer one sung in the same places is the same refrain.
        if any(_contains(big, gram) and set(at) <= set(big_at) for big, big_at in chosen):
            continue
        chosen.append((gram, at))

    by_unit = {unit["unit_id"]: unit for unit in units}
    refrains = []
    for gram, at in chosen:
        instances = []
        for unit_id, start in at.items():
            tokens = by_unit[unit_id]["tokens"][start : start + len(gram)]
            instances.append(
                {
                    "unit_id": unit_id,
                    "ref": by_unit[unit_id].get("ref", unit_id),
                    "token_ids": [t["token_id"] for t in tokens],
                    "surface": " ".join(_POINTS.sub("", t["surface"]) for t in tokens),
                    "text": " ".join(t["surface"] for t in tokens),
                }
            )
        surfaces = [instance["surface"] for instance in instances]
        refrains.append(
            {
                "length": len(gram),
                "text": instances[0]["text"],
                "instances": instances,
                "variants": len(set(surfaces)),
            }
        )
    refrains.sort(key=lambda r: (-len(r["instances"]), -r["length"]))
    return refrains


def _contains(big: tuple[str, ...], small: tuple[str, ...]) -> bool:
    return any(big[i : i + len(small)] == small for i in range(len(big) - len(small) + 1))


def detect_refrains(psalm_id: str) -> list[dict[str, Any]]:
    return find_refrains(registry_service.load_psalm(psalm_id)["units"])
