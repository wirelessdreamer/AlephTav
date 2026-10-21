"""Pinned, owner-authorized dictionary aids for local Greek display previews.

No canonical renderings, reviewed analyses, source text, or release permissions change.
Downloads occur only in the explicit CLI operation; readers use verified local bytes.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from collections.abc import Iterator
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.request import urlopen

from app.core.config import get_settings
from app.core.errors import LicensePolicyError
from app.core.ids import parse_unit_id
from app.services import greek_analysis_service as analysis
from app.services import greek_dictionary_service as dictionary
from app.services import source_capability_service as policy
from app.services.greek_lexical_forms import POSSIBLE_READINGS
from app.services.greek_lexical_lookup_service import LexicalIndex, tonal_key
from app.services.greek_lsj_input_service import parse_lsj_spans, resolve_lsj_cross_references
from app.services.greek_nt_input_service import parse_nestle1904
from app.services.immutable_file_service import (
    atomic_write,
    install_immutable,
    sha256_file,
    workspace_lock,
)
from app.services.package_audit_service import record_package_mutation
from app.services.registry_service import deterministic_json, file_hash

STEP_REV = "94802ced31e63882ab42a86d79eb0017df4545e3"
MORPH_REV = "46258f8bde173998ef0633d79eff3067b9041575"
STEP_BASE = f"https://raw.githubusercontent.com/STEPBible/STEPBible-Data/{STEP_REV}/"
MORPH_BASE = f"https://raw.githubusercontent.com/QuantForgeSoftware/lxx/{MORPH_REV}/"
CORPUS_CATALOG = json.loads(Path(__file__).with_name("greek_corpus_sources.json").read_text())
FILES = {
    "tbesg.txt": (
        STEP_BASE + "Lexicons/TBESG%20-%20Translators%20Brief%20lexicon%20of%20"
        "Extended%20Strongs%20for%20Greek%20-%20STEPBible.org%20CC%20BY.txt",
        "312f723d7b8ef263bbdfb0451c9b8057125804dfff390b6f8544cff2a84b57f4",
    ),
    "step-readme.txt": (
        STEP_BASE + "README.md",
        "261d5157c0ffeadeedad3f734db945a4c3642e3e4ce5fa28002985b6c52437b1",
    ),
    "morphology.txt": (
        MORPH_BASE + "data/morph-morpheus/024-Ps.txt",
        "ee28652093cfed7f6262f1d3bb167009c146e54adac680cd95fade74cda858dc",
    ),
    "morph-license.txt": (
        MORPH_BASE + "LICENSE",
        "dadd119898dd54ea178be54807b49c8ea7910290cb04f803bbe804376b3e21d6",
    ),
    "tipnr.txt": (
        STEP_BASE + "Proper%20Nouns/TIPNR%20-%20Translators%20Individualised%20Proper%20Names%20"
        "with%20all%20References%20-%20STEPBible.org%20CC%20BY.txt",
        "2f4695da58e7ac5a9e477c1bcb590d52bf3e119d4e640844ae7f45d218c204d8",
    ),
}
FILES.update(
    {
        f"corpus/{book['filename']}": (book["url"], book["sha256"])
        for book in CORPUS_CATALOG["books"]
    }
)
FILES.update(
    {
        f"lsj/{item['filename']}": (item["url"], item["sha256"])
        for item in CORPUS_CATALOG["lsj"]["files"]
    }
)
FILES.update(
    {
        f"nt/{name}": (item["url"], item["sha256"])
        for name, item in CORPUS_CATALOG["new_testament"]["files"].items()
    }
)
SOURCES = [
    {
        "source_id": "step.tbesg",
        "package_revision": STEP_REV,
        "license": "CC BY 4.0",
        "license_text_sha256": FILES["step-readme.txt"][1],
        "required_attribution": (
            "STEP Bible (www.STEPBible.org), based on work at Tyndale House Cambridge; "
            "TBESG brief Greek definitions. Reformatted and matched to proposed lemmas."
        ),
    },
    {
        "source_id": "quantforge.morpheus",
        "package_revision": MORPH_REV,
        "license": "CC BY-SA 4.0",
        "license_text_sha256": FILES["morph-license.txt"][1],
        "required_attribution": (
            "QuantForgeSoftware/lxx; Morpheus analyses of the First1KGreek Swete "
            "transcription. Matched to local Swete spellings; unreviewed candidates."
        ),
    },
    {
        "source_id": "step.tipnr",
        "package_revision": STEP_REV,
        "license": "CC BY 4.0",
        "license_text_sha256": FILES["step-readme.txt"][1],
        "required_attribution": "STEP Bible (www.STEPBible.org), Tyndale House Cambridge; "
        "TIPNR conventional proper names. Proposed links to Greek spellings; biographies omitted.",
    },
    {
        "source_id": "nestle1904.morph",
        "package_revision": CORPUS_CATALOG["new_testament"]["revision"],
        "license": "Public Domain",
        "license_text_sha256": FILES["nt/license.txt"][1],
        "required_attribution": "Nestle 1904 Greek New Testament; base text by Diego Renato "
        "dos Santos. Morphology and lemmas by Ulrik Sandborg-Petersen, with Maurice A. Robinson; "
        "Biblical Humanities, CC0 dedication. Source tags retained; dictionary links are proposed.",
    },
    {
        "source_id": "perseus.lsj",
        "package_revision": CORPUS_CATALOG["lsj"]["revision"],
        "license": "CC BY-SA 4.0",
        "license_text_sha256": FILES["lsj/README.md"][1],
        "required_attribution": "A Greek-English Lexicon, Liddell, Scott, Jones and McKenzie, "
        "Clarendon Press. Text provided under CC BY-SA by Perseus Digital Library, "
        "with funding from the National Endowment for the Humanities. Data accessed from "
        "https://github.com/PerseusDL/lexica/ on 2026-10-20. Beta Code converted; quantity "
        "marks omitted from lookup keys. First four English translation spans shown; "
        "explicit dictionary cross-references retained. Original files and headers preserved.",
    },
]


def _resolver_hash() -> str:
    root = Path(__file__).parent
    return hashlib.sha256(
        b"".join(
            (root / name).read_bytes()
            for name in (
                "greek_lexical_lookup_service.py",
                "greek_lexical_forms.py",
                "greek_corpus_sources.json",
                "greek_analysis_service.py",
                "greek_lexical_preview_service.py",
                "greek_nt_input_service.py",
                "greek_lsj_input_service.py",
            )
        )
    ).hexdigest()


def _paths() -> tuple[Path, Path]:
    settings = get_settings()
    root = settings.derived_dir / "greek_lexical_inputs" / "r0001"
    approval = settings.content_dir / "study_snapshots" / "lexical_preview.json"
    if any(not p.resolve().is_relative_to(settings.root_dir.resolve()) for p in (root, approval)):
        raise ValueError("Greek lexical preview escapes workspace")
    return root, approval


def _read_inputs(root: Path) -> dict[str, bytes]:
    inputs = {}
    for name, (_, expected) in FILES.items():
        data = (root / name).read_bytes()
        if hashlib.sha256(data).hexdigest() != expected:
            raise ValueError(f"Greek lexical source checksum mismatch: {name}")
        inputs[name] = data
    return inputs


def _verify_inputs(root: Path) -> None:
    """Verify cached dictionary sources without retaining hundreds of MB per read."""
    for name, (_, expected) in FILES.items():
        if sha256_file(root / name) != expected:
            raise ValueError(f"Greek lexical source checksum mismatch: {name}")


def _corpus_books(
    inputs: dict[str, bytes],
) -> Iterator[tuple[dict[str, Any], list[dict[str, Any]]]]:
    """Yield each source book with its own edition-qualified rows."""
    for book in CORPUS_CATALOG["books"]:
        key = f"corpus/{book['filename']}"
        if key not in inputs:
            raise ValueError(f"Missing full-corpus source: {key}")
        yield (
            {**book, "corpus": "lxx"},
            analysis.parse_quantforge(
                inputs[key].decode("utf-8-sig"),
                package_id=f"quantforge.morpheus.{book['book_code']:03}",
                book_code=book["book_code"],
            ),
        )
    nt = CORPUS_CATALOG.get("new_testament")
    if nt:
        by_book = defaultdict(list)
        for row in parse_nestle1904(
            inputs["nt/morphology.tsv"].decode("utf-8-sig"), package_id="nestle1904.morph"
        ):
            by_book[row["book_code"]].append(row)
        if set(by_book) != {book["book_id"] for book in nt["books"]}:
            raise ValueError("New Testament source differs from its pinned book catalog")
        for book in nt["books"]:
            yield (
                {
                    **book,
                    "book_code": book["book_id"],
                    "name": book["book_id"],
                    "sha256": nt["files"]["morphology.tsv"]["sha256"],
                    "corpus": "nt",
                },
                by_book[book["book_id"]],
            )


@lru_cache(maxsize=2)
def _parsed(root: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    inputs = _read_inputs(Path(root))
    result = dictionary.parse_step_dictionary(
        inputs["tbesg.txt"].decode("utf-8-sig"),
        package_id="step.tbesg",
        source_file=FILES["tbesg.txt"][0],
        attribution=SOURCES[0],
    ).require_valid()
    names = (
        dictionary.parse_tipnr_names(
            inputs["tipnr.txt"].decode("utf-8-sig"),
            attribution=SOURCES[2],
        )
        if "tipnr.txt" in inputs
        else []
    )
    rows = analysis.parse_quantforge(
        inputs["morphology.txt"].decode("utf-8-sig"),
        package_id="quantforge.morpheus",
    )
    # Keep complete occurrence analyses for the displayed Psalter. Other books
    # contribute distinct form/lemma evidence only, never borrowed verse grammar.
    forms = {}
    for book, book_rows in _corpus_books(inputs):
        if book["corpus"] == "lxx" and book["book_code"] == 24:
            continue
        for row in book_rows:
            if not row["synthetic"]:
                forms.setdefault(
                    (row["word"], row["lemma"], tuple(row.get("lexical_identifiers", []))),
                    {
                        k: row[k]
                        for k in (
                            "row_id",
                            "reference",
                            "word",
                            "lemma",
                            "synthetic",
                            "lexical_identifiers",
                        )
                        if k in row
                    },
                )
    rows.extend(forms.values())
    lsj_entries = []
    lsj_accounting: Counter[str] = Counter()
    for name, raw in inputs.items():
        if name.startswith("lsj/") and name.endswith(".xml"):
            part, accounting = parse_lsj_spans(
                raw.decode("utf-8-sig"), source_file=name, attribution=SOURCES[4]
            )
            lsj_entries.extend(part)
            lsj_accounting.update(accounting)
    lsj_entries = resolve_lsj_cross_references(lsj_entries)
    return {
        "entries": [*result.entries, *names, *lsj_entries],
        "lsj_accounting": dict(lsj_accounting),
        "name_entries": len(names),
        "accounting": result.accounting,
        "findings": result.findings,
    }, rows


@lru_cache(maxsize=2)
def _lookup_index(root: str) -> LexicalIndex:
    parsed, rows = _parsed(root)
    return LexicalIndex(parsed["entries"], rows)


def enable(*, reviewer_id: str, rationale: str) -> dict[str, Any]:
    """Download exact pinned bytes and audit the user's local display authorization."""
    from app.services.greek_preview_service import load_preview

    preview = load_preview()
    if preview is None:
        raise ValueError("Enable a Greek source-text preview first")
    root, approval = _paths()
    with workspace_lock(get_settings().derived_dir / "locks" / "greek-lexical-preview.lock"):
        for name, (url, expected) in FILES.items():
            data = (
                (root / name).read_bytes()
                if (root / name).exists()
                else urlopen(url, timeout=45).read()
            )
            if hashlib.sha256(data).hexdigest() != expected:
                raise ValueError(f"Greek lexical download checksum mismatch: {name}")
            install_immutable(root / name, data)
        parsed, rows = _parsed(str(root))
        record = {
            "scope": "local_display_preview",
            "decision": "approve",
            "role": "owner",
            "reviewer_id": reviewer_id,
            "rationale": rationale,
            "text_manifest_sha256": preview["manifest_sha256"],
            "files": {name: {"url": url, "sha256": sha} for name, (url, sha) in FILES.items()},
            "sources": SOURCES,
            "resolver_sha256": _resolver_hash(),
        }
        _require_policy()
        before = (
            hashlib.sha256(approval.read_bytes()).hexdigest() if approval.exists() else "0" * 64
        )
        audit = record_package_mutation(
            package_id="greek_lexical_preview",
            before_hash=before,
            after_hash=file_hash(record),
            summary="Load pinned Greek dictionary and lemma candidates for local review",
            rationale=rationale,
            created_by=reviewer_id,
            checks=[
                "pinned_source_hashes",
                "dictionary_row_accounting",
                "morphology_parser",
                "owner_local_display_authorization",
            ],
        )
        atomic_write(approval, deterministic_json(record).encode("utf-8"))
        report = {
            "entries": len(parsed["entries"]),
            "morphology_rows": len(rows),
            "accounting": parsed["accounting"],
            "findings": parsed["findings"],
            "lsj_accounting": parsed["lsj_accounting"],
            "audit_id": audit["audit_id"],
            "sources": SOURCES,
            "resolver_sha256": record["resolver_sha256"],
        }
        atomic_write(root / "import_report.json", deterministic_json(report).encode("utf-8"))
    return report


def _require_policy() -> None:
    registered = {source["source_id"] for source in policy._registry()["sources"]}
    for source, capability, filename in (
        (SOURCES[0], "dictionary", "tbesg.txt"),
        (SOURCES[1], "analysis", "morphology.txt"),
        (SOURCES[2], "dictionary", "tipnr.txt"),
        (SOURCES[3], "analysis", "nt/morphology.tsv"),
        (SOURCES[4], "dictionary", "lsj/grc.lsj.perseus-eng1.xml"),
    ):
        if source["source_id"] in registered:
            policy.require_package_capability(
                source["source_id"],
                source["source_id"],
                FILES[filename][1],
                capability,
            )


def lexical_candidates(
    units: list[dict[str, Any]],
    entries: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    *,
    index: LexicalIndex | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Match analysis lemmas and explicit dictionary headwords, preserving source variants."""
    index = index or LexicalIndex(entries, rows)
    verse_map: dict[str, list[str]] = defaultdict(list)
    for unit in units:
        identity = parse_unit_id(unit["unit_id"], require_versioned=True)
        verse_map[f"024{identity.psalm_id[2:]}{identity.verse:03}"].append(unit["unit_id"])
    proposed = analysis.propose_analyses(
        units,
        rows,
        verse_map=verse_map,
        analysis_set_id="lexical.local-preview.r0001",
    )
    result = {}
    reference_by_unit = {
        unit_id: reference for reference, unit_ids in verse_map.items() for unit_id in unit_ids
    }
    tokens = {
        token["token_id"]: {**token, "source_reference": reference_by_unit[unit["unit_id"]]}
        for unit in units
        for token in unit["tokens"]
    }
    reading_keys = {tonal_key(form) for form in POSSIBLE_READINGS}
    for annotation in proposed["annotations"]:
        token = tokens[annotation["token_id"]]
        if tonal_key(token["surface"]) in reading_keys:
            reading = index.fallback(token)
            if reading and reading[0].get("lookup_status") == "possible_variant":
                result[annotation["token_id"]] = reading
                continue
        candidates = []
        for candidate in annotation["analyses"]:
            if candidate["synthetic"]:
                continue
            matches = index.lemma(candidate["lemma"])
            candidates.append({**candidate, "dictionary_entries": matches})
        if not any(item["dictionary_entries"] for item in candidates):
            token = tokens[annotation["token_id"]]
            candidates.extend(index.fallback(token, allow_mark_variants=True))
        result[annotation["token_id"]] = candidates
    return result


def enrich(units: list[dict[str, Any]], text_manifest_sha256: str | None) -> dict[str, Any]:
    """Enrich response copies only; changed/withdrawn inputs never expose cached glosses."""
    root, approval = _paths()
    if not approval.exists():
        return {}
    try:
        raw_approval = approval.read_bytes()
        record = json.loads(raw_approval)
        if record.get("decision") != "approve":
            return {}
        if (
            (record.get("scope"), record.get("role"), record.get("text_manifest_sha256"))
            != (
                "local_display_preview",
                "owner",
                text_manifest_sha256,
            )
            or record.get("files")
            != {name: {"url": url, "sha256": sha} for name, (url, sha) in FILES.items()}
            or record.get("sources") != SOURCES
            or record.get("resolver_sha256") != _resolver_hash()
        ):
            raise ValueError("Greek lexical authorization differs from its pinned sources")
        policy_id = policy.policy_revision()
        _require_policy()
        _verify_inputs(root)  # Cache reuse never skips immutable-byte verification.
        parsed, rows = _parsed(str(root))
        candidates = lexical_candidates(
            units, parsed["entries"], rows, index=_lookup_index(str(root))
        )
        if approval.read_bytes() != raw_approval or policy.policy_revision() != policy_id:
            raise ValueError("Greek lexical authorization changed during read")
    except (OSError, ValueError, KeyError, TypeError, LicensePolicyError):
        return {
            "lexical_message": (
                "Greek dictionary data is unavailable or changed; reload after repair."
            )
        }
    for unit in units:
        for token in unit["tokens"]:
            matches = candidates.get(token["token_id"], [])
            # Do not display a failed parser guess alongside a resolved dictionary
            # link as though both were equally supported lexical alternatives.
            matches = [item for item in matches if item["dictionary_entries"]] or matches
            statuses = {item.get("lookup_status") for item in matches}
            token["lookup_status"] = (
                "possible_variant"
                if "possible_variant" in statuses
                else (
                    "mark_variant"
                    if "mark_variant" in statuses
                    else ("related_entry" if "related_entry" in statuses else "matched")
                )
            )
            token["analyses"] = [
                {
                    k: item[k]
                    for k in ("lemma", "status", "scheme", "raw_tag", "features", "lookup_note")
                    if k in item
                }
                for item in matches
            ]
            dictionary_entries = {
                entry["entry_id"]: entry for item in matches for entry in item["dictionary_entries"]
            }
            token["dictionary_entries"] = [
                {k: entry[k] for k in ("entry_id", "headword", "gloss", "attribution")}
                for entry in dictionary_entries.values()
            ]
            token["gloss"] = (
                " / ".join(
                    dict.fromkeys(
                        entry["gloss"]
                        for entry in dictionary_entries.values()
                        if entry.get("gloss")
                    )
                )
                or None
            )
            if not token["gloss"]:
                token["lookup_status"] = "unresolved"
        unit["literal_text"] = " · ".join(
            f"[{token['gloss']}?]"
            if token.get("gloss")
            and token.get("lookup_status")
            in {
                "possible_variant",
                "related_entry",
                "mark_variant",
            }
            else token["gloss"] or f"[unresolved: {token['surface']}]"
            for token in unit["tokens"]
        )
    return {
        "lexical_preview": True,
        "source_attribution": [
            {"attribution": source["required_attribution"], "license": source["license"]}
            for source in SOURCES
        ],
    }


def audit_corpus_lookups() -> dict[str, Any]:
    """Audit all books in the pinned corpus, independently of the displayed book."""
    root, approval = _paths()
    approval_bytes = approval.read_bytes()
    record = json.loads(approval_bytes)
    if (
        record.get("decision") != "approve"
        or (record.get("scope"), record.get("role")) != ("local_display_preview", "owner")
        or record.get("sources") != SOURCES
        or record.get("resolver_sha256") != _resolver_hash()
        or record.get("files")
        != {name: {"url": url, "sha256": sha} for name, (url, sha) in FILES.items()}
    ):
        raise ValueError("Reload the full-corpus Greek lexical preview before auditing")
    policy_id = policy.policy_revision()
    _require_policy()
    inputs = _read_inputs(root)
    parsed, rows = _parsed(str(root))
    index = LexicalIndex(parsed["entries"], rows)
    counts: Counter[str] = Counter()
    books = []
    unresolved = {}
    cache = {}
    possible_reading_keys = {tonal_key(form) for form in POSSIBLE_READINGS}
    corpus_counts: dict[str, Counter[str]] = defaultdict(Counter)
    for book, book_rows in _corpus_books(inputs):
        book_counts: Counter[str] = Counter()
        findings = []
        for row in book_rows:
            identity = (
                row["surface"],
                row["word"],
                row["lemma"],
                row["synthetic"],
                tuple(row.get("lexical_identifiers", [])),
                row["reference"] if tonal_key(row["word"]) in possible_reading_keys else None,
            )
            if identity not in cache:
                entries = [] if row["synthetic"] else index.row_entries(row)
                source_token = {
                    "token_id": row["row_id"],
                    "surface": row["surface"],
                    "lookup_word": row["word"],
                    "source_reference": row["reference"],
                }
                reading = (
                    index.fallback(source_token)
                    if tonal_key(row["word"]) in possible_reading_keys
                    else []
                )
                if reading and reading[0].get("lookup_status") == "possible_variant":
                    entries = []
                fallback = (
                    []
                    if entries
                    else reading or index.fallback(source_token, allow_mark_variants=True)
                )
                status = "matched" if entries else "unresolved"
                if not entries and fallback:
                    entries = [e for c in fallback for e in c["dictionary_entries"]]
                    status = fallback[0].get("lookup_status", "matched")
                cache[identity] = (bool(entries), status)
            matched, status = cache[identity]
            book_counts["total_tokens"] += 1
            book_counts["with_dictionary_context" if matched else "unmatched"] += 1
            book_counts[status] += 1
            if row["findings"]:
                findings.append(
                    {
                        "row_id": row["row_id"],
                        "raw_lemma": row["raw_lemma"],
                        "findings": row["findings"],
                    }
                )
            if not matched:
                gap = unresolved.setdefault(
                    (book["corpus"], row["word"], row["lemma"], row["synthetic"]),
                    {
                        "word": row["word"],
                        "corpus": book["corpus"],
                        "proposed_lemma": row["lemma"],
                        "synthetic": row["synthetic"],
                        "count": 0,
                        "references": [],
                    },
                )
                gap["count"] += 1
                if len(gap["references"]) < 10:
                    gap["references"].append(
                        {"reference": row["reference"], "row_id": row["row_id"]}
                    )
        if book_counts["total_tokens"] != book["tokens"]:
            raise ValueError(
                f"Corpus row accounting mismatch: {book['corpus']}/{book['book_code']}"
            )
        book_counts["unmatched"] += 0
        book_counts["unresolved"] += 0
        counts.update(book_counts)
        corpus_counts[book["corpus"]].update(book_counts)
        books.append(
            {
                "book_code": book["book_code"],
                "corpus": book["corpus"],
                "name": book["name"],
                "source_sha256": book["sha256"],
                "counts": dict(book_counts),
                "findings": findings,
            }
        )
    report = {
        "scope": "full_pinned_greek_corpus",
        "source_revision": MORPH_REV,
        "source_revisions": {
            "lxx": MORPH_REV,
            "nt": CORPUS_CATALOG.get("new_testament", {}).get("revision"),
        },
        "corpus_counts": {name: dict(values) for name, values in corpus_counts.items()},
        "book_count": len(books),
        "books": books,
        "counts": dict(counts),
        "resolver_sha256": _resolver_hash(),
        "unmatched_forms": sorted(unresolved.values(), key=lambda item: -item["count"]),
        "meaning": "Every row in every pinned source book is counted. Dictionary aids "
        "are proposed context, not reviewed sentence translations. Unresolved forms "
        "remain explicit; synthetic proper-name guesses are not dictionary meanings.",
    }
    destination = get_settings().reports_dir / "greek" / "corpus_lexical_lookup_audit.json"
    if approval.read_bytes() != approval_bytes or policy.policy_revision() != policy_id:
        raise ValueError("Greek lexical authorization changed during audit")
    atomic_write(destination, deterministic_json(report).encode("utf-8"))
    return {k: v for k, v in report.items() if k not in {"books", "unmatched_forms"}} | {
        "report_path": str(destination),
        "unmatched_form_count": len(unresolved),
    }


def audit_lookups() -> dict[str, Any]:
    """Verify every approved preview token and write a reproducible coverage report."""
    from app.services.greek_preview_service import load_preview

    preview = load_preview()
    if preview is None:
        raise ValueError("No approved Greek text preview")
    units = preview["units"]
    source_before = file_hash(units)
    evidence = enrich(units, preview["manifest_sha256"])
    if not evidence.get("lexical_preview"):
        raise ValueError(evidence.get("lexical_message", "Greek lexical preview is not enabled"))
    counts: Counter[str] = Counter()
    review = []
    for unit in units:
        for token in unit["tokens"]:
            counts["total_tokens"] += 1
            counts["with_dictionary_context" if token.get("gloss") else "unmatched"] += 1
            counts[token.get("lookup_status", "unresolved")] += 1
            if not token.get("gloss") or token.get("lookup_status") != "matched":
                review.append(
                    {
                        "token_id": token["token_id"],
                        "ref": unit["ref"],
                        "surface": token["surface"],
                        "gloss": token.get("gloss"),
                        "status": token.get("lookup_status"),
                        "notes": [
                            a["lookup_note"] for a in token["analyses"] if a.get("lookup_note")
                        ],
                    }
                )
    report = {
        "edition_id": preview["edition_id"],
        "text_revision_id": preview["text_revision_id"],
        "text_manifest_sha256": preview["manifest_sha256"],
        "source_payload_sha256": source_before,
        "resolver_sha256": _resolver_hash(),
        "source_files": {name: sha for name, (_, sha) in FILES.items()},
        "unit_count": len(units),
        "counts": {**counts, "unmatched": counts["unmatched"]},
        "review_items": review,
        "meaning": (
            "Dictionary context includes proposed form/name links. Bracketed possible readings "
            "and related-word aids are not accepted source corrections or sentence translations."
        ),
    }
    destination = get_settings().reports_dir / "greek" / "lexical_lookup_audit.json"
    atomic_write(destination, deterministic_json(report).encode("utf-8"))
    return {
        **{key: value for key, value in report.items() if key != "review_items"},
        "report_path": str(destination),
    }
