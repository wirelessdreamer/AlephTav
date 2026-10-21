from __future__ import annotations

import re
from dataclasses import dataclass

SLUG_PATTERN = r"[a-z][a-z0-9]*(?:[-_][a-z0-9]+)*"
GREEK_PREFIX_PATTERN = rf"lxx\.{SLUG_PATTERN}\.r[0-9]{{4,}}\."
CORPUS_PREFIX_PATTERN = rf"(?:(?:{GREEK_PREFIX_PATTERN})|lxx\.)?"
UNIT_PATTERN = rf"{CORPUS_PREFIX_PATTERN}ps\d{{3}}\.v\d{{3}}\.[a-z]"

ID_PATTERNS = {
    "project_id": re.compile(r"^proj\.[a-z0-9_]+$"),
    "psalm_id": re.compile(r"^ps\d{3}$"),
    "unit_id": re.compile(rf"^{UNIT_PATTERN}$"),
    "token_id": re.compile(rf"^{CORPUS_PREFIX_PATTERN}ps\d{{3}}\.v\d{{3}}\.t\d{{3}}$"),
    "alignment_id": re.compile(rf"^aln\.{UNIT_PATTERN}\.[a-z_]+\.\d{{4}}$"),
    "rendering_id": re.compile(rf"^rnd\.{UNIT_PATTERN}\.[a-z_]+\.(can|alt)\.\d{{4}}$"),
    "alternate_id": re.compile(rf"^rnd\.{UNIT_PATTERN}\.[a-z_]+\.alt\.\d{{4}}$"),
    "span_id": re.compile(rf"^spn\.{UNIT_PATTERN}\.[a-z_]+\.\d{{4}}$"),
    "concept_id": re.compile(rf"^cpt\.{UNIT_PATTERN}\.\d{{4}}$"),
    "audit_id": re.compile(rf"^aud\.{UNIT_PATTERN}\.\d{{4}}$"),
    "comparison_id": re.compile(rf"^cmp\.{UNIT_PATTERN}\.\d{{4}}$"),
    # Psalm-scoped rather than unit-scoped: an analysis describes a whole psalm.
    "psalm_analysis_id": re.compile(r"^anl\.ps\d{3}\.\d{4}$"),
    "issue_link_id": re.compile(r"^iss\.\d{6}$"),
    "pr_link_id": re.compile(r"^pr\.\d{6}$"),
    "decision_id": re.compile(rf"^rev\.{UNIT_PATTERN}\.\d{{4}}$"),
    "job_id": re.compile(r"^job\.[0-9a-f]{12}$"),
}


@dataclass(frozen=True)
class UnitIdentity:
    corpus: str
    edition_id: str | None
    text_revision_id: str | None
    psalm_id: str
    verse: int
    segment: str

    @property
    def is_legacy(self) -> bool:
        return self.corpus == "lxx" and self.edition_id is None

    @property
    def unit_id(self) -> str:
        prefix = ""
        if self.corpus == "lxx":
            prefix = "lxx."
            if self.edition_id is not None:
                prefix += f"{self.edition_id}.{self.text_revision_id}."
        return f"{prefix}{self.psalm_id}.v{self.verse:03d}.{self.segment}"


def parse_unit_id(value: str, *, require_versioned: bool = False) -> UnitIdentity:
    ensure_id("unit_id", value)
    parts = value.split(".")
    corpus = "lxx" if parts[0] == "lxx" else "mt"
    edition = parts[1] if len(parts) == 6 else None
    revision = parts[2] if len(parts) == 6 else None
    psalm, verse, segment = parts[-3:]
    identity = UnitIdentity(corpus, edition, revision, psalm, int(verse[1:]), segment)
    if require_versioned and identity.is_legacy:
        raise ValueError("Legacy Greek locator requires an explicit edition and text revision")
    return identity


def ensure_id(kind: str, value: str) -> str:
    pattern = ID_PATTERNS[kind]
    if not pattern.fullmatch(value):
        raise ValueError(f"Invalid {kind}: {value}")
    return value


def unit_id_from_entity_id(kind: str, value: str) -> str:
    """Recover a unit-scoped entity's unit ID, preserving its optional corpus prefix."""
    ensure_id(kind, value)
    match = re.match(rf"^[a-z]+\.({UNIT_PATTERN})\.", value)
    if match is None:
        raise ValueError(f"ID does not identify a unit-scoped entity: {value}")
    return match.group(1)


def next_suffix(existing_ids: list[str], prefix: str, width: int = 4) -> str:
    highest = 0
    for item in existing_ids:
        if item.startswith(prefix):
            try:
                highest = max(highest, int(item.rsplit(".", 1)[-1]))
            except ValueError:
                continue
    return f"{highest + 1:0{width}d}"


def issue_link_id(number: int) -> str:
    return f"iss.{number:06d}"


def pr_link_id(number: int) -> str:
    return f"pr.{number:06d}"


def audit_id(unit_id: str, existing_ids: list[str]) -> str:
    return f"aud.{unit_id}.{next_suffix(existing_ids, f'aud.{unit_id}.')}"


def decision_id(unit_id: str, existing_ids: list[str]) -> str:
    return f"rev.{unit_id}.{next_suffix(existing_ids, f'rev.{unit_id}.')}"


def comparison_id(unit_id: str, existing_ids: list[str]) -> str:
    return f"cmp.{unit_id}.{next_suffix(existing_ids, f'cmp.{unit_id}.')}"


def psalm_analysis_id(psalm_id: str, existing_ids: list[str]) -> str:
    return f"anl.{psalm_id}.{next_suffix(existing_ids, f'anl.{psalm_id}.')}"


def alignment_id(unit_id: str, layer: str, existing_ids: list[str]) -> str:
    return f"aln.{unit_id}.{layer}.{next_suffix(existing_ids, f'aln.{unit_id}.{layer}.')}"


def rendering_id(unit_id: str, layer: str, status_hint: str, existing_ids: list[str]) -> str:
    suffix = next_suffix(existing_ids, f"rnd.{unit_id}.{layer}.{status_hint}.")
    return f"rnd.{unit_id}.{layer}.{status_hint}.{suffix}"


def span_id(unit_id: str, layer: str, existing_ids: list[str]) -> str:
    return f"spn.{unit_id}.{layer}.{next_suffix(existing_ids, f'spn.{unit_id}.{layer}.')}"
