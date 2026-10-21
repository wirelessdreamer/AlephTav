"""Display-only lexical lookup: source citation forms and attested inflections.

Inflections found elsewhere are dictionary aids, not occurrence-level grammar.
Source surfaces, token IDs, and canonical annotations are never changed here.
"""

from __future__ import annotations

import html
import re
import unicodedata
from collections import defaultdict
from typing import Any

from app.services.greek_analysis_service import normalize_greek
from app.services.greek_lexical_forms import (
    CITATION_FORMS,
    INFLECTED_FORMS,
    NAME_FORMS,
    POSSIBLE_READINGS,
    READING_REFERENCES,
    RELATED_FORMS,
)

_GREEK = r"[\u0370-\u03ff\u1f00-\u1fff\u0300-\u036f]"
_WORD = re.compile(rf"{_GREEK}+(?:[-–]{_GREEK}+)*")
_OPTIONAL = re.compile(rf"({_GREEK}+)\(({_GREEK}+)\)({_GREEK}+)")
_ELISIONS = {
    "ἀλλ'": "ἀλλά",
    "παρ'": "παρά",
    "δι'": "διά",
    "δ'": "δέ",
    "μετ'": "μετά",
    "μεθ'": "μετά",
    "κατ'": "κατά",
    "καθ'": "κατά",
    "ἀπ'": "ἀπό",
    "ἀφ'": "ἀπό",
    "ἐπ'": "ἐπί",
    "ἐφ'": "ἐπί",
    "ὑπ'": "ὑπό",
    "ὑφ'": "ὑπό",
    "ἀνθ'": "ἀντί",
    "ἀντ'": "ἀντί",
}


def tonal_key(text: str) -> str:
    """Ignore movable stress accents; keep breathing and iota distinctions intact."""
    normalized = normalize_greek(text, normalize_elision=True)
    return "".join(
        c for c in unicodedata.normalize("NFD", normalized) if c not in "\u0300\u0301\u0342"
    )


def _unmarked_key(text: str) -> str | None:
    key = normalize_greek(text, mark_insensitive=True).strip("᾿῾᾽")
    # Leave short particles unresolved; preserve iota through casefold expansion.
    if len(key) < 3 or any("GREEK" not in unicodedata.name(c, "") for c in key):
        return None
    return key


def citation_variants(entry: dict[str, Any]) -> list[str]:
    variants = [part.strip() for part in entry["headword"].split(",") if part.strip()]
    # The leading bold citation is a headword, unlike Greek quotations later in
    # the definition. Preserve the original entry and its complete attribution.
    raw = entry.get("raw_fields", [])
    match = re.match(r"\s*<b>(.*?)</b>", raw[7], re.S | re.I) if len(raw) == 8 else None
    if match:
        citation = html.unescape(re.sub(r"<[^>]*>", "", match[1]))
        citation = _OPTIONAL.sub(lambda m: f"{m[1]}{m[3]} {m[1]}{m[2]}{m[3]}", citation)
        variants.extend(word.replace("-", "").replace("–", "") for word in _WORD.findall(citation))
    return list(dict.fromkeys(variants))


class LexicalIndex:
    def __init__(self, entries: list[dict[str, Any]], rows: list[dict[str, Any]]):
        self.headwords: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.citations: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.forms: dict[str, dict[tuple[str, tuple[str, ...]], dict[str, Any]]] = defaultdict(dict)
        self.identifiers: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self._unmarked_forms: dict[str, list[dict[str, Any]]] | None = None
        self._unmarked_heads: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
        self.curated = {
            tonal_key(form): lemma
            for lemma, forms in INFLECTED_FORMS.items()
            for form in forms.split()
        }
        self.name_forms = {
            tonal_key(form): name for name, forms in NAME_FORMS.items() for form in forms.split()
        }
        self.names: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for entry in entries:
            # A keyed source row with an empty brief definition is not usable
            # literal context and must not mask a defined supplemental entry.
            if not entry.get("gloss"):
                continue
            for identifier in entry.get("identifiers", []):
                if identifier.get("scheme") == "eStrong" and identifier.get("relation") == "entry":
                    self.identifiers[identifier["value"]].append(entry)
            if entry.get("name_record"):
                self.names[entry["headword"].casefold()].append(entry)
                continue
            for variant in entry["headword"].split(","):
                if variant.strip():
                    self.headwords[normalize_greek(variant.strip())].append(entry)
            for variant in citation_variants(entry):
                self.citations[tonal_key(variant)].append(entry)
        for row in rows:
            if not row["synthetic"]:
                # Keep each possible lemma, not a single supposedly correct parse.
                self.forms[tonal_key(row["word"])].setdefault(
                    (row["lemma"], tuple(row.get("lexical_identifiers", []))), row
                )

    def lemma(self, lemma: str) -> list[dict[str, Any]]:
        matches = self.headwords.get(normalize_greek(lemma), [])
        citations = self.citations.get(tonal_key(lemma.replace("-", "")), [])
        if not matches or all(e.get("fallback_dictionary") for e in matches):
            matches = [*matches, *citations]
        if (
            not matches or all(e.get("fallback_dictionary") for e in matches)
        ) and lemma in CITATION_FORMS:
            target = CITATION_FORMS[lemma]
            aliases = self.headwords.get(normalize_greek(target), []) or self.citations.get(
                tonal_key(target), []
            )
            matches = [*matches, *aliases]
        matches = [entry for entry in matches if not entry.get("fallback_dictionary")] or matches
        return list({entry["entry_id"]: entry for entry in matches}.values())

    def row_entries(self, row: dict[str, Any]) -> list[dict[str, Any]]:
        """Use a source's lexical identifiers only when its lemma has no entry."""
        matches = self.lemma(row["lemma"])
        if not matches:
            matches = [
                entry
                for value in row.get("lexical_identifiers", [])
                for entry in self.identifiers.get(value, [])
            ]
        return list({entry["entry_id"]: entry for entry in matches}.values())

    def fallback(
        self, token: dict[str, Any], *, allow_mark_variants: bool = False
    ) -> list[dict[str, Any]]:
        surface = token.get("lookup_word", token["surface"])
        result = []
        for printed, (reading, target) in POSSIBLE_READINGS.items():
            if (
                token.get("source_reference") is not None
                and token["source_reference"] not in (READING_REFERENCES[printed])
            ):
                continue
            if tonal_key(printed) == tonal_key(surface):
                entries = (
                    self.names.get(target[1:].casefold(), [])
                    if target.startswith("@")
                    else self.lemma(target)
                )
                if entries:
                    candidate = self._candidate(
                        token,
                        reading,
                        entries,
                        "Possible source reading",
                        f"Printed {surface}; possible reading {reading}. "
                        "This is a context suggestion, "
                        "not a correction to the Greek source; the reading needs review.",
                        "possible_source_reading",
                    )
                    return [{**candidate, "lookup_status": "possible_variant"}]
        for printed, (target, note) in RELATED_FORMS.items():
            if tonal_key(printed) == tonal_key(surface) and (entries := self.lemma(target)):
                return [
                    {
                        **self._candidate(
                            token,
                            target,
                            entries,
                            "Related dictionary context",
                            note,
                            "related_entry",
                        ),
                        "lookup_status": "related_entry",
                    }
                ]
        target = self.curated.get(tonal_key(surface))
        if target and (entries := self.lemma(target)):
            return [
                self._candidate(
                    token,
                    target,
                    entries,
                    "Inflection dictionary",
                    f"Proposed dictionary link for this printed form: {target}. "
                    "Source spelling is retained; occurrence grammar is not inferred.",
                    "curated_inflection",
                )
            ]
        name = self.name_forms.get(tonal_key(surface))
        if name and (entries := self.names.get(name.casefold())):
            return [
                self._candidate(
                    token,
                    name,
                    entries,
                    "Name dictionary",
                    f"Proposed identification as {name.replace('_', ' ')}. TIPNR supplies the "
                    "conventional name, not this Greek spelling "
                    "or a selected biographical identity.",
                    "proposed_name_identification",
                )
            ]
        for row in self.forms.get(tonal_key(surface), {}).values():
            lemma = row["lemma"]
            entries = self.row_entries(row)
            if entries:
                result.append(
                    self._candidate(
                        token,
                        lemma,
                        entries,
                        "Inflected form lookup",
                        "This spelling is attested elsewhere in the analysis corpus. "
                        "These are possible dictionary meanings; "
                        "grammar in this verse is unresolved.",
                        "attested_inflection",
                        source_row_ids=[row["row_id"]],
                    )
                )
        if result:
            return result
        expanded = _ELISIONS.get(
            normalize_greek(token["surface"].strip('.,;··:!?“”"()[]{}'), normalize_elision=True)
        )
        if expanded and (entries := self.lemma(expanded)):
            return [
                self._candidate(
                    token,
                    expanded,
                    entries,
                    "Elided form lookup",
                    f"Elided spelling of {expanded}; expanded for dictionary lookup only.",
                    "elision",
                )
            ]
        direct = self.headwords.get(normalize_greek(surface), []) or self.citations.get(
            tonal_key(surface), []
        )
        # STEP G:D contains form-specific entries such as τοῦ = "his". A bare
        # surface cannot choose that sense over the article without form evidence.
        direct = [entry for entry in direct if entry.get("lexical_pos_raw") != "G:D"]
        direct = [entry for entry in direct if not entry.get("fallback_dictionary")] or direct
        if direct:
            return [
                self._candidate(
                    token,
                    surface,
                    direct,
                    "Dictionary headword",
                    "Dictionary citation-form match; occurrence grammar has not been inferred.",
                    "dictionary_headword",
                )
            ]
        if allow_mark_variants:
            return self.mark_variants(token)
        return []

    def mark_variants(self, token: dict[str, Any]) -> list[dict[str, Any]]:
        """Offer marked, unselected contexts for attested accent/breathing variants."""
        key = _unmarked_key(token.get("lookup_word", token["surface"]))
        if key is None:
            return []
        if self._unmarked_forms is None:
            self._unmarked_forms = defaultdict(list)
            for forms in self.forms.values():
                for row in forms.values():
                    if form_key := _unmarked_key(row["word"]):
                        self._unmarked_forms[form_key].append(row)
            for headword, entries in self.citations.items():
                if head_key := _unmarked_key(headword):
                    for entry in entries:
                        if entry.get("lexical_pos_raw") != "G:D":
                            self._unmarked_heads[head_key][entry["entry_id"]] = entry
        contexts: dict[str, dict[str, Any]] = {}
        for row in self._unmarked_forms.get(key, []):
            if entries := self.row_entries(row):
                item = contexts.setdefault(row["lemma"], {"entries": {}, "rows": []})
                item["entries"].update({e["entry_id"]: e for e in entries})
                item["rows"].append(row["row_id"])
        for entry in self._unmarked_heads.get(key, {}).values():
            item = contexts.setdefault(entry["headword"], {"entries": {}, "rows": []})
            item["entries"][entry["entry_id"]] = entry
        if not contexts or len(contexts) > 8:
            return []  # Never choose an arbitrary top match and hide alternatives.
        for item in contexts.values():
            primary = {
                key: entry
                for key, entry in item["entries"].items()
                if not entry.get("fallback_dictionary")
            }
            item["entries"] = primary or item["entries"]
        return [
            {
                **self._candidate(
                    token,
                    lemma,
                    list(item["entries"].values()),
                    "Accent/breathing variant context",
                    f"Printed {token['surface']}; possible dictionary context for {lemma} after "
                    "ignoring accent/breathing marks. Greek letters and iota are retained. "
                    "This is a suggestion needing review, "
                    "not a source correction or selected sense.",
                    "unmarked_variant_suggestion",
                    source_row_ids=list(dict.fromkeys(item["rows"])),
                ),
                "lookup_status": "mark_variant",
            }
            for lemma, item in contexts.items()
        ]

    @staticmethod
    def _candidate(
        token: dict[str, Any],
        lemma: str,
        entries: list[dict[str, Any]],
        scheme: str,
        note: str,
        method: str,
        **evidence: Any,
    ) -> dict[str, Any]:
        return {
            "token_id": token["token_id"],
            "lemma": lemma,
            "status": "proposed",
            "scheme": scheme,
            "raw_tag": "",
            "features": {},
            "lookup_note": note,
            "dictionary_entries": list({e["entry_id"]: e for e in entries}.values()),
            "evidence": {
                "method": method,
                "token_ids": [token["token_id"]],
                "entry_ids": list(dict.fromkeys(e["entry_id"] for e in entries)),
                **evidence,
            },
        }
