"""Normalize the rahlfs1931-psalter Swete 1896 exports into a locked Greek package.

The exports are read from a pinned git commit, never from the working tree, so the
package records exactly which bytes it was built from. The verse map is generated
from the standard Hebrew/Greek Psalter numbering and every record stays ``proposed``.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import shutil
import subprocess
import tempfile
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.services.greek_package_intake_service import canonical_bytes, stage_package

EDITION_ID = "swete1896"
SOURCE_ID = "swete1896"
PACKAGE_ID = "swete1896.text"
LICENSE_NAME = "CC BY-SA 4.0"
ATTRIBUTION = (
    "H. B. Swete, The Old Testament in Greek according to the Septuagint, vol. 2 "
    "(Cambridge, 1896), Psalms; transcribed from page images by the rahlfs1931-psalter "
    "project, licensed CC BY-SA 4.0"
)
EXPORTS = {
    "text": "output/swete1896_psalms.txt",
    "words": "output/swete1896_psalms.words.tsv",
    "spans": "output/swete1896_psalms.word_spans.jsonl",
    "license": "LICENSE",
}
MAP_PROVENANCE = (
    "Rule-generated from the standard Hebrew/Greek Psalter numbering (MT 9+10 = LXX 9, "
    "MT 11-113 = LXX 10-112, MT 114+115 = LXX 113, MT 116 = LXX 114-115, "
    "MT 117-146 = LXX 116-145, MT 147 = LXX 146-147); verse numbers matched as printed"
)


def _git_bytes(root: Path, commit: str, path: str) -> bytes:
    return subprocess.run(
        ["git", "-C", str(root), "show", f"{commit}:{path}"],
        check=True,
        capture_output=True,
    ).stdout


def _resolve_commit(root: Path, commit: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--verify", f"{commit}^{{commit}}"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def lxx_reference(mt_psalm: int, mt_verse: int) -> tuple[int, int]:
    """The Greek psalm/verse number for an MT psalm/verse under the standard numbering."""
    if mt_psalm <= 8 or mt_psalm >= 148:
        return mt_psalm, mt_verse
    if mt_psalm == 9:
        return 9, mt_verse
    if mt_psalm == 10:
        return 9, mt_verse + 21
    if mt_psalm <= 113:
        return mt_psalm - 1, mt_verse
    if mt_psalm == 114:
        return 113, mt_verse
    if mt_psalm == 115:
        return 113, mt_verse + 8
    if mt_psalm == 116:
        return (114, mt_verse) if mt_verse <= 9 else (115, mt_verse - 9)
    if mt_psalm <= 146:
        return mt_psalm - 1, mt_verse
    return (146, mt_verse) if mt_verse <= 11 else (147, mt_verse - 11)


def _unit_id(revision: str, psalm: int, verse: int) -> str:
    return f"lxx.{EDITION_ID}.{revision}.ps{psalm:03d}.v{verse:03d}.a"


def build_units(exports: dict[str, bytes], revision: str) -> list[dict[str, Any]]:
    """One unit per printed verse; tokens are the export's words, located in verse text."""
    verses: dict[tuple[int, int], str] = {}
    for line in exports["text"].decode("utf-8").splitlines():
        reference, verse_text = line.split("\t")
        psalm_label, verse_label = reference.split(":")
        verses[(int(psalm_label), int(verse_label))] = verse_text
    fragments: dict[tuple[int, int, int], list[dict[str, Any]]] = {}
    for line in exports["spans"].decode("utf-8").splitlines():
        span = json.loads(line)
        fragments[(span["psalm"], int(span["verse"]), span["position"])] = [
            {key: fragment[key] for key in ("leaf", "page", "line", "strip")}
            for fragment in span["fragments"]
        ]
    words: dict[tuple[int, int], list[dict[str, str]]] = defaultdict(list)
    reader = csv.DictReader(io.StringIO(exports["words"].decode("utf-8")), delimiter="\t")
    for row in reader:
        words[(int(row["psalm"]), int(row["verse"]))].append(row)
    if set(words) != set(verses):
        raise ValueError("Swete word table and verse text cover different verses")
    units = []
    for (psalm, verse), text in verses.items():
        unit_id = _unit_id(revision, psalm, verse)
        tokens = []
        offset = 0
        for position, row in enumerate(words[(psalm, verse)], 1):
            start = text.find(row["word"], offset)
            if start < 0:
                raise ValueError(f"Swete word {row['word']!r} not found in {psalm}:{verse}")
            end = start + len(row["word"])
            offset = end
            # The export counts punctuation in its positions; keep its number as the locator.
            export_position = int(row["position"])
            located = fragments.get(
                (psalm, verse, export_position),
                [{key: row[key] for key in ("leaf", "page", "line", "strip")}],
            )
            tokens.append(
                {
                    "token_id": f"{unit_id[:-2]}.t{position:03d}",
                    "position": position,
                    "surface": row["word"],
                    "normalized": unicodedata.normalize("NFC", row["word"]),
                    "text_span": {"start": start, "end": end},
                    "source_locator": {
                        "file": "source/swete1896_psalms.words.tsv",
                        "locator": f"{psalm}:{verse}#{export_position}",
                        "fragments": located,
                    },
                }
            )
        units.append(
            {
                "schema_version": "1.0",
                "unit_id": unit_id,
                "corpus": "lxx",
                "edition_id": EDITION_ID,
                "text_revision_id": revision,
                "psalm_id": f"ps{psalm:03d}",
                "ref": f"Greek Psalm {psalm}:{verse}",
                "source_greek": text,
                "tokens": tokens,
            }
        )
    return units


def build_map(
    units: list[dict[str, Any]], mt_units: list[dict[str, Any]], revision: str
) -> tuple[dict[str, Any], dict[str, list[str]]]:
    """Proposed MT→Swete records plus what the numbering rule could not place."""
    greek = {unit["unit_id"]: unit for unit in units}
    targeted: set[str] = set()
    records = []
    unmapped_mt = []
    for mt in sorted(mt_units, key=lambda unit: unit["unit_id"]):
        mt_psalm, mt_verse = int(mt["unit_id"][2:5]), int(mt["unit_id"][7:10])
        psalm, verse = lxx_reference(mt_psalm, mt_verse)
        target = _unit_id(revision, psalm, verse)
        if target not in greek:
            unmapped_mt.append(f"MT {mt_psalm}:{mt_verse} -> Swete {psalm}:{verse}")
            continue
        targeted.add(target)
        records.append(
            {
                "mapping_id": f"{EDITION_ID}.{revision}.{mt['unit_id']}",
                "relation": "equivalent",
                "sources": [{"baseline": "MT", "reference": mt["ref"], "unit_id": mt["unit_id"]}],
                "targets": [
                    {
                        "baseline": "Swete 1896",
                        "reference": f"Psalm {psalm}:{verse}",
                        "unit_id": target,
                    }
                ],
                "provenance": MAP_PROVENANCE,
                "status": "proposed",
            }
        )
    untargeted = []
    for unit_id, unit in greek.items():
        if unit_id in targeted:
            continue
        if unit["psalm_id"] == "ps151":
            records.append(
                {
                    "mapping_id": f"{EDITION_ID}.{revision}.{unit_id}",
                    "relation": "greek_only",
                    "sources": [],
                    "targets": [
                        {
                            "baseline": "Swete 1896",
                            "reference": unit["ref"].removeprefix("Greek "),
                            "unit_id": unit_id,
                        }
                    ],
                    "provenance": "Psalm 151 is absent from the MT 150-psalm corpus",
                    "status": "proposed",
                }
            )
        else:
            untargeted.append(unit["ref"])
    payload = {
        "schema_version": "1.0",
        "edition_id": EDITION_ID,
        "text_revision_id": revision,
        "records": records,
        "witness_spans": [],
    }
    return payload, {"unmapped_mt": unmapped_mt, "untargeted_greek": untargeted}


def _write_package(target: Path, files: dict[str, bytes], manifest: dict[str, Any]) -> None:
    for relative, data in files.items():
        path = target / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    (target / "package.json").write_bytes(canonical_bytes(manifest))


def build_and_stage(
    sibling_root: Path, *, commit: str = "HEAD", revision: str = "r0001"
) -> dict[str, Any]:
    """Build the normalized package from a pinned commit and stage it under data/derived."""
    from app.services import registry_service

    settings = get_settings()
    sha = _resolve_commit(sibling_root, commit)
    exports = {name: _git_bytes(sibling_root, sha, path) for name, path in EXPORTS.items()}
    units = build_units(exports, revision)
    mt_units = [
        unit
        for psalm_id in registry_service.list_psalm_ids()
        for unit in registry_service.load_psalm(psalm_id)["units"]
    ]
    verse_map, gaps = build_map(units, mt_units, revision)
    files = {
        "LICENSE": exports["license"],
        "source/swete1896_psalms.txt": exports["text"],
        "source/swete1896_psalms.words.tsv": exports["words"],
        "source/swete1896_psalms.word_spans.jsonl": exports["spans"],
        "versification/map.json": canonical_bytes(verse_map),
        **{
            f"psalms/{unit['psalm_id']}/{unit['unit_id'].rsplit('.', 2)[1]}.json": canonical_bytes(
                unit
            )
            for unit in units
        },
    }
    manifest = {
        "schema_version": "1.0",
        "package_id": PACKAGE_ID,
        "source_id": SOURCE_ID,
        "package_revision": revision,
        "kind": "source_text",
        "files": [
            {
                "path": path,
                "sha256": hashlib.sha256(data).hexdigest(),
                "size_bytes": len(data),
            }
            for path, data in sorted(files.items())
        ],
        "dependencies": [],
        "provenance": {
            "upstream_url": sibling_root.resolve().as_uri(),
            "upstream_revision": sha,
            "license": LICENSE_NAME,
            "license_text_sha256": hashlib.sha256(exports["license"]).hexdigest(),
            "attribution": ATTRIBUTION,
        },
        "review_status": "pending",
    }
    build_dir = Path(tempfile.mkdtemp(prefix="swete-build-"))
    try:
        _write_package(build_dir, files, manifest)
        staged = stage_package(build_dir, settings.derived_dir / "greek_staging")
    finally:
        shutil.rmtree(build_dir, ignore_errors=True)
    report = {
        "package_id": PACKAGE_ID,
        "package_revision": revision,
        "manifest_sha256": hashlib.sha256(canonical_bytes(manifest)).hexdigest(),
        "upstream_revision": sha,
        "staged_path": staged["path"],
        "changed": staged["changed"],
        "unit_count": staged["unit_count"],
        "token_count": staged["token_count"],
        "map_records": len(verse_map["records"]),
        **gaps,
    }
    report_path = settings.reports_dir / "greek" / f"{PACKAGE_ID}.{revision}.build.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", "utf-8")
    return {**report, "report_path": str(report_path)}
