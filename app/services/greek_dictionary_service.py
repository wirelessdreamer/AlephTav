"""Strict offline adapters for attributed Greek dictionary packages.

These functions do not grant source permissions, write canonical content, or activate
packages. The resulting presentation tree is data, never upstream HTML.
"""

from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlsplit

PARSER_VERSION = "greek-dictionaries-v1"
_ID = re.compile(r"([GH])0*(\d+)([A-Za-z]*)\Z")
_ID_IN_EXPRESSION = re.compile(r"(?<![A-Za-z0-9])([GH]\d+[A-Za-z]*)(?![A-Za-z0-9])")
_STEP_REF = re.compile(r"<ref\s*=\s*(['\"])(.*?)\1\s*>", re.IGNORECASE)


def normalize_external_id(value: str, *, default_prefix: str | None = None) -> str:
    """Normalize source padding only; preserve extended ranges and suffix identity."""
    candidate = value.strip()
    if default_prefix and re.fullmatch(r"\d+[A-Za-z]*", candidate):
        candidate = default_prefix + candidate
    match = _ID.fullmatch(candidate)
    if not match or int(match[2]) < 1:
        raise ValueError(f"Malformed external identifier: {value!r}")
    return f"{match[1]}{int(match[2])}{match[3]}"


@dataclass(frozen=True)
class AdapterResult:
    entries: list[dict[str, Any]]
    accounting: dict[str, int]
    findings: list[dict[str, Any]]
    parser_version: str = PARSER_VERSION

    def require_valid(self) -> AdapterResult:
        errors = [finding for finding in self.findings if finding.get("severity") == "error"]
        if errors:
            raise ValueError(f"Dictionary input has {len(errors)} invalid rows: {errors}")
        return self


class _SafeMarkup(HTMLParser):
    def __init__(self, entry_id: str, baseline: str) -> None:
        super().__init__(convert_charrefs=True)
        self.root: dict[str, Any] = {"type": "root", "children": []}
        self.stack = [("root", self.root)]
        self.entry_id = entry_id
        self.baseline = baseline
        self.citations: list[dict[str, Any]] = []
        self.findings: list[dict[str, Any]] = []
        self.node_count = 0

    def _append(self, node: dict[str, Any]) -> None:
        self.node_count += 1
        if self.node_count > 100_000 or len(self.stack) > 100:
            raise ValueError("Dictionary markup exceeds node/depth limits")
        self.stack[-1][1]["children"].append(node)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        types = {
            "b": "strong",
            "strong": "strong",
            "i": "emphasis",
            "em": "emphasis",
            "emph": "emphasis",
            "p": "paragraph",
            "br": "break",
            "ref": "reference",
        }
        node_type = types.get(tag)
        if tag == "a":
            href = attributes.get("href") or ""
            parsed = urlsplit(href)
            if parsed.scheme in {"http", "https"} and parsed.hostname and not parsed.username:
                node_type = "link"
            else:
                self.findings.append({"code": "unsafe_link", "severity": "warning"})
        if any(key.lower().startswith("on") for key in attributes):
            self.findings.append({"code": "event_attribute_removed", "severity": "warning"})
        if node_type is None:
            self.findings.append({"code": "unsupported_markup", "tag": tag, "severity": "warning"})
            self.handle_data(self.get_starttag_text() or f"<{tag}>")
            return
        node: dict[str, Any] = {"type": node_type}
        if node_type != "break":
            node["children"] = []
        if node_type == "link":
            node["href"] = attributes["href"]
        if node_type == "reference":
            machine_ref = attributes.get("data-reference") or attributes.get("osisref")
            citation = {
                "original_label": "",
                "machine_reference": machine_ref,
                "baseline": self.baseline,
                "source_entry_id": self.entry_id,
                "resolution": "unresolved",
                "target": None,
            }
            self.citations.append(citation)
            node["citation_index"] = len(self.citations) - 1
        self._append(node)
        if node_type != "break":
            self.stack.append((tag, node))

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag != "br":
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        for position in range(len(self.stack) - 1, 0, -1):
            if self.stack[position][0] == tag:
                del self.stack[position:]
                return
        if tag != "br":
            self.handle_data(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        if data:
            self._append({"type": "text", "text": data})
            for tag, node in self.stack:
                if tag == "ref":
                    self.citations[node["citation_index"]]["original_label"] += data


def safe_presentation(
    markup: str, *, entry_id: str, baseline: str
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    if len(markup) > 2_000_000:
        raise ValueError("Dictionary entry exceeds maximum size")
    normalized = _STEP_REF.sub(
        lambda match: '<ref data-reference="' + html.escape(match[2], quote=True) + '">', markup
    )
    parser = _SafeMarkup(entry_id, baseline)
    parser.feed(normalized)
    parser.close()
    return parser.root, parser.citations, parser.findings


def _identifiers(fields: list[str], entry_id: str) -> list[dict[str, Any]]:
    assignments = []
    for scheme, expression in zip(("eStrong", "dStrong", "uStrong"), fields[:3], strict=True):
        matches = list(_ID_IN_EXPRESSION.finditer(expression))
        if expression.strip() and not matches:
            raise ValueError(f"No identifier in {scheme} expression")
        for index, match in enumerate(matches):
            relation = "entry" if index == 0 else "related"
            if match[1].startswith("H"):
                relation = "hebrew_cross_reference"
            if index > 0 and "+" in expression:
                relation = (
                    "crasis_component"
                    if normalize_external_id(fields[0]) == "G2504"
                    else "combination_component"
                )
            # This is a source relationship, never an occurrence or equivalence expansion.
            assignments.append(
                {
                    "scheme": scheme,
                    "value": normalize_external_id(match[1]),
                    "raw_value": match[1],
                    "raw_expression": expression,
                    "relation": relation,
                    "source_entry_id": entry_id,
                    "status": "source_asserted",
                }
            )
    if len([item for item in assignments if item["scheme"] == "eStrong"]) != 1:
        raise ValueError("eStrong column must identify exactly one source entry")
    return assignments


def parse_step_dictionary(
    text: str,
    *,
    package_id: str,
    source_file: str,
    attribution: dict[str, Any],
    dictionary: str = "tbesg",
    baseline: str = "english_kjv",
) -> AdapterResult:
    """TBESG and each TFLSJ file have eight columns after the documentary preamble."""
    if dictionary not in {"tbesg", "tflsj_main", "tflsj_extra"}:
        raise ValueError("Unknown STEP dictionary adapter")
    accounting = {
        "input_lines": 0,
        "blank_lines": 0,
        "preamble_lines": 0,
        "header_lines": 0,
        "unkeyed_rows": 0,
        "data_rows": 0,
        "invalid_rows": 0,
    }
    entries = []
    findings = []
    started = False
    for line_number, line in enumerate(text.lstrip("\ufeff").splitlines(), 1):
        accounting["input_lines"] += 1
        if not line.strip():
            accounting["blank_lines"] += 1
            continue
        if set(line.strip()) == {"="}:
            accounting["preamble_lines"] += 1
            continue
        fields = line.split("\t")
        if len(fields) == 8 and [item.lower() for item in fields[:3]] == [
            "estrong",
            "dstrong",
            "ustrong",
        ]:
            accounting["header_lines"] += 1
            started = True
            continue
        looks_like_data = bool(re.match(r"^G\d", fields[0]))
        if not started and not looks_like_data:
            accounting["preamble_lines"] += 1
            continue
        started = True
        entry_id = f"{package_id}:{dictionary}:line:{line_number}"
        try:
            if len(fields) != 8:
                raise ValueError("Expected eight TSV fields")
            identifiers = _identifiers(fields, entry_id)
            if not fields[3].strip():
                accounting["unkeyed_rows"] += 1
                findings.append(
                    {
                        "code": "dictionary_row_without_headword",
                        "severity": "warning",
                        "file": source_file,
                        "line": line_number,
                        "raw_fields": fields,
                        "message": "Retained in report; excluded from Greek headword lookup.",
                    }
                )
                continue
            presentation, citations, markup_findings = safe_presentation(
                fields[7], entry_id=entry_id, baseline=baseline
            )
            entries.append(
                {
                    "schema_version": "1.0",
                    "entry_id": entry_id,
                    "package_id": package_id,
                    "dictionary": dictionary,
                    "headword": fields[3],
                    "transliteration": fields[4],
                    "lexical_pos_raw": fields[5],
                    "gloss": fields[6],
                    "lexeme_id": None,
                    "identifiers": identifiers,
                    "source_locator": {"file": source_file, "line": line_number},
                    "attribution": dict(attribution),
                    "presentation": presentation,
                    "citations": citations,
                    "findings": markup_findings,
                    "raw_fields": fields,
                }
            )
            accounting["data_rows"] += 1
        except ValueError as error:
            accounting["invalid_rows"] += 1
            findings.append(
                {
                    "code": "invalid_dictionary_row",
                    "severity": "error",
                    "file": source_file,
                    "line": line_number,
                    "message": str(error),
                }
            )
    if not entries and not accounting["invalid_rows"]:
        findings.append({"code": "no_dictionary_rows", "severity": "error", "file": source_file})
    return AdapterResult(entries, accounting, findings)


def parse_tflsj(
    main: str, extra: str, *, package_id: str, attribution: dict[str, Any]
) -> AdapterResult:
    """Require both files rather than silently dropping LXX-only vocabulary."""
    results = [
        parse_step_dictionary(
            text,
            package_id=package_id,
            source_file=filename,
            attribution=attribution,
            dictionary=kind,
        )
        for text, filename, kind in (
            (main, "TFLSJ-main", "tflsj_main"),
            (extra, "TFLSJ-extra", "tflsj_extra"),
        )
    ]
    return AdapterResult(
        [entry for result in results for entry in result.entries],
        {key: sum(result.accounting[key] for result in results) for key in results[0].accounting},
        [finding for result in results for finding in result.findings],
    )


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def parse_abbott_smith(
    text: str,
    *,
    package_id: str,
    source_file: str,
    attribution: dict[str, Any],
    baseline: str = "english_kjv",
) -> AdapterResult:
    """Namespaced TEI; DTDs/entities are refused before the XML parser sees them."""
    if re.search(r"<!\s*(DOCTYPE|ENTITY)\b", text, re.IGNORECASE):
        raise ValueError("DTD and entity declarations are forbidden in dictionary packages")
    root = ET.fromstring(text)
    entries = []
    findings = []
    for index, element in enumerate(
        (item for item in root.iter() if _local_name(item.tag) in {"entry", "entryFree"}), 1
    ):
        locator = element.get("{http://www.w3.org/XML/1998/namespace}id") or element.get("n")
        entry_id = f"{package_id}:abbott_smith:entry:{index}"
        orths = [item for item in element.iter() if _local_name(item.tag) == "orth"]
        headword = "".join(orths[0].itertext()) if orths else ""
        if not headword:
            findings.append({"code": "missing_headword", "severity": "error", "entry": index})
            continue
        identifiers = []
        # Abbott-Smith uses entry@n='headword|G1'; a missing G-number is legitimate.
        identifier_text = (element.get("n") or "").split("|", 1)
        if len(identifier_text) == 2:
            try:
                identifiers.append(
                    {
                        "scheme": "Strong",
                        "value": normalize_external_id(identifier_text[1]),
                        "raw_value": identifier_text[1],
                        "raw_expression": element.get("n"),
                        "relation": "entry",
                        "source_entry_id": entry_id,
                        "status": "source_asserted",
                    }
                )
            except ValueError:
                findings.append(
                    {"code": "invalid_entry_identifier", "severity": "error", "entry": index}
                )
                continue

        # Serialize a tiny allowlist into the same safe presentation parser, retaining text/tails.
        def markup(node: ET.Element, entry_index: int = index) -> str:
            tag = _local_name(node.tag)
            content = html.escape(node.text or "")
            for child in node:
                content += markup(child) + html.escape(child.tail or "")
            if tag == "ref":
                target = node.get("osisRef") or node.get("target") or ""
                return f'<ref data-reference="{html.escape(target, quote=True)}">{content}</ref>'
            mapped = {"emph": "em", "hi": "em", "p": "p", "lb": "br"}.get(tag)
            if mapped:
                return f"<{mapped}>{content}</{mapped}>"
            if tag not in {
                "entry",
                "entryFree",
                "form",
                "orth",
                "foreign",
                "sense",
                "def",
                "cit",
                "quote",
                "bibl",
                "gramGrp",
                "gram",
                "usg",
                "etym",
            }:
                findings.append(
                    {
                        "code": "unsupported_tei_markup",
                        "tag": tag,
                        "severity": "warning",
                        "entry": entry_index,
                    }
                )
            return content

        presentation, citations, markup_findings = safe_presentation(
            markup(element), entry_id=entry_id, baseline=baseline
        )
        entries.append(
            {
                "schema_version": "1.0",
                "entry_id": entry_id,
                "package_id": package_id,
                "dictionary": "abbott_smith",
                "headword": headword,
                "transliteration": "",
                "lexical_pos_raw": "",
                "gloss": "",
                "lexeme_id": None,
                "identifiers": identifiers,
                "source_locator": {"file": source_file, "locator": locator or str(index)},
                "attribution": dict(attribution),
                "presentation": presentation,
                "citations": citations,
                "findings": markup_findings,
                "raw_fields": [],
            }
        )
    invalid = len([item for item in findings if item["severity"] == "error"])
    if not entries and not invalid:
        findings.append({"code": "no_dictionary_entries", "severity": "error"})
    return AdapterResult(
        entries,
        {
            "input_entries": len(entries) + invalid,
            "data_rows": len(entries),
            "invalid_rows": invalid,
        },
        findings,
    )


def resolve_citation(
    citation: dict[str, Any],
    mappings: list[dict[str, Any]],
    *,
    edition_id: str,
    text_revision_id: str,
) -> dict[str, Any]:
    """Resolve only an explicit baseline/edition/revision record, including title offsets."""
    targets = [
        mapping["target"]
        for mapping in mappings
        if mapping["baseline"] == citation["baseline"]
        and mapping["machine_reference"] == citation["machine_reference"]
        and mapping["edition_id"] == edition_id
        and mapping["text_revision_id"] == text_revision_id
    ]
    return {
        **citation,
        "resolution": "resolved" if len(targets) == 1 else "unresolved",
        "target": targets[0] if len(targets) == 1 else None,
    }


def normalized_dictionary_files(result: AdapterResult) -> dict[str, bytes]:
    """Produce deterministic candidate bytes; a caller must lock, stage and audit installation."""
    from app.services.foundation_contract_service import validate_contract
    from app.services.greek_package_intake_service import canonical_bytes

    result.require_valid()
    seen = set()
    for entry in result.entries:
        validate_contract("greek_dictionary_entry.schema.json", entry)
        if entry["entry_id"] in seen:
            raise ValueError("Duplicate package-scoped dictionary entry identity")
        seen.add(entry["entry_id"])
    import json

    entries = b"".join(
        (
            json.dumps(entry, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        ).encode()
        for entry in result.entries
    )
    report = {
        "parser_version": result.parser_version,
        "accounting": result.accounting,
        "findings": result.findings,
        "entry_count": len(result.entries),
        "review_status": "pending",
    }
    return {"entries.jsonl": entries, "adapter_report.json": canonical_bytes(report)}


def parse_tipnr_names(text: str, *, attribution: dict[str, Any]) -> list[dict[str, Any]]:
    """Read name/identity headers only, not generated biographies or Greek attestations.

    TIPNR documents that most LXX spellings are not listed. A separate proposed
    spelling link must identify its conventional-name record; homonyms stay separate.
    """
    entries = []
    for line_number, line in enumerate(text.lstrip("\ufeff").splitlines(), 1):
        fields = line.split("\t")
        header = fields[0]
        match = re.fullmatch(r"([^@=\t]+)@([^=\t]+)=([GH]\d+[A-Za-z]*)", header)
        if match:
            name, reference, identifier = match.groups()
            entries.append(
                {
                    "entry_id": f"step.tipnr:line:{line_number}",
                    "headword": name,
                    "gloss": name.replace("_", " "),
                    "lexical_pos_raw": "N:Name",
                    "name_record": header,
                    "name_reference": reference,
                    "identifiers": [{"scheme": "uStrong", "value": identifier}],
                    "source_locator": {"file": "tipnr.txt", "line": line_number},
                    "attribution": dict(attribution),
                }
            )
        elif (
            header in {"– Named", "– Group", "– Spelled", "– Greek", "– Aramaic"}
            and len(fields) >= 4
        ):
            # Only short translated-name labels; descriptions are never imported.
            for index, alternate in enumerate(fields[3].split(";")):
                label = alternate.split("=")[0].strip()
                variants = {
                    re.sub(r"\([^)]*\)", "", label).strip(),
                    label.replace("(", "").replace(")", ""),
                }
                for variant_index, name in enumerate(sorted(variants)):
                    if not re.fullmatch(r"[A-Za-z][A-Za-z '\-]*", name):
                        continue
                    entries.append(
                        {
                            "entry_id": f"step.tipnr:line:{line_number}:{index}:{variant_index}",
                            "headword": name,
                            "gloss": name,
                            "lexical_pos_raw": "N:Name",
                            "name_record": fields[1],
                            "name_reference": fields[1].partition("@")[2],
                            "source_locator": {"file": "tipnr.txt", "line": line_number},
                            "attribution": dict(attribution),
                        }
                    )
    if not entries:
        raise ValueError("TIPNR contains no recognizable name records")
    return entries
