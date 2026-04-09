from __future__ import annotations

import re

ID_PATTERNS = {
    "project_id": re.compile(r"^proj\.[a-z0-9_]+$"),
    "psalm_id": re.compile(r"^ps\d{3}$"),
    "unit_id": re.compile(r"^ps\d{3}\.v\d{3}\.[a-z]$"),
    "token_id": re.compile(r"^ps\d{3}\.v\d{3}\.t\d{3}$"),
    "alignment_id": re.compile(r"^aln\.ps\d{3}\.v\d{3}\.[a-z]\.[a-z_]+\.\d{4}$"),
    "rendering_id": re.compile(r"^rnd\.ps\d{3}\.v\d{3}\.[a-z]\.[a-z_]+\.(can|alt)\.\d{4}$"),
    "alternate_id": re.compile(r"^rnd\.ps\d{3}\.v\d{3}\.[a-z]\.[a-z_]+\.alt\.\d{4}$"),
    "span_id": re.compile(r"^spn\.ps\d{3}\.v\d{3}\.[a-z]\.[a-z_]+\.\d{4}$"),
    "concept_id": re.compile(r"^cpt\.ps\d{3}\.v\d{3}\.[a-z]\.\d{4}$"),
    "audit_id": re.compile(r"^aud\.ps\d{3}\.v\d{3}\.[a-z]\.\d{4}$"),
    "issue_link_id": re.compile(r"^iss\.\d{6}$"),
    "pr_link_id": re.compile(r"^pr\.\d{6}$"),
    "decision_id": re.compile(r"^rev\.ps\d{3}\.v\d{3}\.[a-z]\.\d{4}$"),
    "job_id": re.compile(r"^job\.\d{8}$"),
}


def ensure_id(kind: str, value: str) -> str:
    pattern = ID_PATTERNS[kind]
    if not pattern.match(value):
        raise ValueError(f"Invalid {kind}: {value}")
    return value


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


def alignment_id(unit_id: str, layer: str, existing_ids: list[str]) -> str:
    return f"aln.{unit_id}.{layer}.{next_suffix(existing_ids, f'aln.{unit_id}.{layer}.')}"


def rendering_id(unit_id: str, layer: str, status_hint: str, existing_ids: list[str]) -> str:
    suffix = next_suffix(existing_ids, f"rnd.{unit_id}.{layer}.{status_hint}.")
    return f"rnd.{unit_id}.{layer}.{status_hint}.{suffix}"


def span_id(unit_id: str, layer: str, existing_ids: list[str]) -> str:
    return f"spn.{unit_id}.{layer}.{next_suffix(existing_ids, f'spn.{unit_id}.{layer}.')}"
