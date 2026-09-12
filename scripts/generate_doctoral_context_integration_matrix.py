from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter, defaultdict
from datetime import UTC, datetime
from itertools import combinations
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORT_ROOT = ROOT / "reports" / "research"

SOURCE_PATHS = {
    "canonical_cross_reference": REPORT_ROOT / "canonical_cross_reference_atlas.json",
    "translation_claim_matrix": REPORT_ROOT / "translation_claim_evidence_matrix.json",
    "cultural_historical_atlas": REPORT_ROOT / "cultural_historical_domain_atlas.json",
    "reception_divergence": REPORT_ROOT / "reception_divergence_atlas.json",
    "divine_name_policy": REPORT_ROOT / "divine_name_policy_report.json",
    "superscription_context": REPORT_ROOT / "superscription_context_report.json",
    "poetic_rhetorical_atlas": REPORT_ROOT / "poetic_rhetorical_pressure_atlas.json",
    "witness_divergence": REPORT_ROOT / "witness_divergence_report.json",
    "doctoral_priority_dossier": REPORT_ROOT / "doctoral_priority_dossier_atlas.json",
    "contextual_pressure_atlas": REPORT_ROOT / "contextual_pressure_atlas.json",
}

DEFAULT_JSON_OUTPUT = REPORT_ROOT / "doctoral_context_integration_matrix.json"
DEFAULT_LENS_CSV_OUTPUT = REPORT_ROOT / "doctoral_context_integration_matrix_lenses.csv"
DEFAULT_UNIT_CSV_OUTPUT = REPORT_ROOT / "doctoral_context_integration_matrix_units.csv"
DEFAULT_PSALM_CSV_OUTPUT = REPORT_ROOT / "doctoral_context_integration_matrix_psalms.csv"
DEFAULT_COOCCURRENCE_CSV_OUTPUT = (
    REPORT_ROOT / "doctoral_context_integration_matrix_cooccurrence.csv"
)
DEFAULT_HTML_OUTPUT = REPORT_ROOT / "doctoral_context_integration_matrix.html"

HIGH_PRESSURE_BANDS = {"critical", "highest", "high"}

LENSES = {
    "whole_tanakh_three_division": {
        "label": "Whole-Tanakh three-division anchor",
        "short_label": "Tanakh 3-div.",
        "category": "broader_canon",
        "weight": 9.0,
        "reviewer_role": "Hebrew; lexical; alignment",
        "source_artifact": "canonical_cross_reference_atlas.json",
        "control": "Broader-canon surface anchors route review but are not lemma proof.",
    },
    "high_value_canonical_anchor": {
        "label": "High-value canonical anchor",
        "short_label": "Canon anchor",
        "category": "broader_canon",
        "weight": 7.0,
        "reviewer_role": "Hebrew; lexical",
        "source_artifact": "canonical_cross_reference_atlas.json",
        "control": "Anchor forms must be checked against Hebrew sense before wording claims.",
    },
    "cultural_historical_domain": {
        "label": "Cultural/historical domain",
        "short_label": "Culture",
        "category": "culture_history",
        "weight": 12.0,
        "reviewer_role": "Hebrew; theology",
        "source_artifact": "cultural_historical_domain_atlas.json",
        "control": "Culture claims require labeled rationale and source-packet review.",
    },
    "ancient_culture_pressure": {
        "label": "Ancient-culture pressure",
        "short_label": "Ancient culture",
        "category": "culture_history",
        "weight": 10.0,
        "reviewer_role": "Hebrew; theology",
        "source_artifact": "translation_claim_evidence_matrix.json",
        "control": "Ancient context may explain translation choices but cannot replace Hebrew.",
    },
    "textual_witness_pressure": {
        "label": "Textual-witness pressure",
        "short_label": "Witness pressure",
        "category": "textual_witness",
        "weight": 13.0,
        "reviewer_role": "Hebrew; alignment",
        "source_artifact": "translation_claim_evidence_matrix.json",
        "control": "Witness variants must not silently override the Hebrew basis.",
    },
    "high_english_witness_divergence": {
        "label": "High English-witness divergence",
        "short_label": "English divergence",
        "category": "textual_witness",
        "weight": 14.0,
        "reviewer_role": "alignment; release",
        "source_artifact": "witness_divergence_report.json",
        "control": "English witnesses are comparison evidence and blocked generation sources.",
    },
    "divine_name_policy": {
        "label": "Divine-name/title policy",
        "short_label": "Divine names",
        "category": "theology_policy",
        "weight": 12.0,
        "reviewer_role": "Hebrew; theology; release",
        "source_artifact": "divine_name_policy_report.json",
        "control": "Divine-name rendering must follow an approved policy and review lane.",
    },
    "divine_name_witness_disagreement": {
        "label": "Divine-name witness disagreement",
        "short_label": "Name disagreement",
        "category": "theology_policy",
        "weight": 10.0,
        "reviewer_role": "theology; release",
        "source_artifact": "divine_name_policy_report.json",
        "control": "Witness disagreement signals policy risk, not an automatic rendering.",
    },
    "superscription_context": {
        "label": "Superscription/performance context",
        "short_label": "Superscription",
        "category": "culture_history",
        "weight": 9.0,
        "reviewer_role": "Hebrew; theology",
        "source_artifact": "superscription_context_report.json",
        "control": "Headings, attributions, and performance markers need explicit lane review.",
    },
    "poetic_rhetorical_pressure": {
        "label": "Poetic/rhetorical pressure",
        "short_label": "Poetics",
        "category": "poetics",
        "weight": 12.0,
        "reviewer_role": "lyric; Hebrew",
        "source_artifact": "poetic_rhetorical_pressure_atlas.json",
        "control": "Layered English style must preserve Hebrew rhetoric and alignment.",
    },
    "reception_sensitive": {
        "label": "Reception-sensitive unit",
        "short_label": "Reception",
        "category": "reception",
        "weight": 14.0,
        "reviewer_role": "theology; release",
        "source_artifact": "reception_divergence_atlas.json",
        "control": "Reception belongs in labeled notes unless review justifies wording impact.",
    },
    "jewish_christian_separation": {
        "label": "Jewish/Christian separation required",
        "short_label": "J/C split",
        "category": "reception",
        "weight": 20.0,
        "reviewer_role": "theology; release",
        "source_artifact": "reception_divergence_atlas.json",
        "control": "Jewish and Christian interpretive frames must be separated before signoff.",
    },
    "academic_comparison_required": {
        "label": "Academic comparison required",
        "short_label": "Academic comp.",
        "category": "reception",
        "weight": 12.0,
        "reviewer_role": "theology; release",
        "source_artifact": "reception_divergence_atlas.json",
        "control": (
            "Academic comparison is adjudication evidence, not devotional wording authority."
        ),
    },
    "authority_blocked_dossier": {
        "label": "Authority-blocked dossier",
        "short_label": "Blocked dossier",
        "category": "authority",
        "weight": 10.0,
        "reviewer_role": "release",
        "source_artifact": "doctoral_priority_dossier_atlas.json",
        "control": "Dossier rows remain assignments until reviewer signoff is complete.",
    },
}


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def pct(part: int | float, total: int | float) -> float:
    if not total:
        return 0.0
    return round(float(part) / float(total) * 100, 2)


def mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / len(values), 2)


def rows_by_unit(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row["unit_id"]): row for row in rows}


def safe_float(row: dict[str, Any], key: str, default: float = 0.0) -> float:
    value = row.get(key, default)
    if value in {None, ""}:
        return default
    return float(value)


def safe_int(row: dict[str, Any], key: str, default: int = 0) -> int:
    value = row.get(key, default)
    if value in {None, ""}:
        return default
    return int(value)


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple | set):
        return list(value)
    return [value]


def join_values(values: Any, *, limit: int | None = None) -> str:
    items = [str(value) for value in as_list(values) if str(value)]
    if limit is not None:
        items = items[:limit]
    return "; ".join(items)


def band_for_score(score: float) -> str:
    if score >= 160:
        return "critical"
    if score >= 125:
        return "highest"
    if score >= 95:
        return "high"
    if score >= 65:
        return "elevated"
    return "watch"


def bool_any(*values: Any) -> bool:
    return any(bool(value) for value in values)


def lens_score_bonus(
    *,
    canonical: dict[str, Any],
    cultural: dict[str, Any],
    witness: dict[str, Any],
    reception: dict[str, Any],
    poetic: dict[str, Any],
    dossier: dict[str, Any],
    claim: dict[str, Any],
    contextual: dict[str, Any],
) -> float:
    return round(
        min(20.0, safe_float(canonical, "priority_score") / 20.0)
        + min(14.0, safe_float(cultural, "priority_score") / 20.0)
        + min(15.0, safe_float(witness, "priority_score") / 10.0)
        + min(20.0, safe_float(reception, "reception_divergence_priority_score") / 15.0)
        + min(15.0, safe_float(poetic, "poetic_rhetorical_priority_score") / 20.0)
        + min(25.0, safe_float(dossier, "doctoral_dossier_priority_score") / 25.0)
        + min(15.0, safe_float(claim, "claim_risk_score") / 20.0)
        + min(10.0, safe_float(contextual, "priority_score") / 8.0),
        2,
    )


def active_lenses_for_unit(
    *,
    canonical: dict[str, Any],
    claim: dict[str, Any],
    cultural: dict[str, Any],
    reception: dict[str, Any],
    divine: dict[str, Any],
    superscription: dict[str, Any],
    poetic: dict[str, Any],
    witness: dict[str, Any],
    dossier: dict[str, Any],
) -> list[str]:
    marker_flags = set(as_list(witness.get("marker_flags")))
    active = []
    if canonical.get("has_three_division_evidence"):
        active.append("whole_tanakh_three_division")
    if safe_int(canonical, "high_value_anchor_count") > 0:
        active.append("high_value_canonical_anchor")
    if safe_int(cultural, "domain_count") > 0:
        active.append("cultural_historical_domain")
    if bool_any(
        claim.get("ancient_culture_pressure"),
        cultural.get("ancient_culture_pressure"),
        reception.get("ancient_culture_pressure"),
        dossier.get("ancient_culture_pressure"),
    ):
        active.append("ancient_culture_pressure")
    if bool_any(
        claim.get("textual_witness_pressure"),
        cultural.get("textual_witness_pressure"),
        reception.get("textual_witness_pressure"),
        dossier.get("textual_witness_pressure"),
        witness.get("textual_witness_pressure"),
    ):
        active.append("textual_witness_pressure")
    if "high_english_witness_divergence" in marker_flags:
        active.append("high_english_witness_divergence")
    if safe_int(divine, "divine_title_token_count") > 0:
        active.append("divine_name_policy")
    if divine.get("english_witness_divine_rendering_disagreement"):
        active.append("divine_name_witness_disagreement")
    if safe_int(superscription, "context_token_count") > 0:
        active.append("superscription_context")
    if poetic.get("pressure_band") in HIGH_PRESSURE_BANDS:
        active.append("poetic_rhetorical_pressure")
    if bool_any(
        claim.get("reception_sensitive"),
        cultural.get("reception_sensitive"),
        reception.get("reception_sensitive"),
        dossier.get("reception_sensitive"),
    ):
        active.append("reception_sensitive")
    if bool_any(
        claim.get("has_jewish_reception_frame") and claim.get("has_christian_reception_frame"),
        reception.get("jewish_christian_separation_required"),
        dossier.get("jewish_christian_separation_required"),
    ):
        active.append("jewish_christian_separation")
    if bool_any(
        claim.get("has_academic_comparison_frame"),
        reception.get("has_academic_comparison_frame"),
        "academic_critical_comparison" in as_list(dossier.get("required_frames")),
    ):
        active.append("academic_comparison_required")
    if safe_int(dossier, "blocking_lane_count") > 0:
        active.append("authority_blocked_dossier")
    return active


def reviewer_roles_for_lenses(lenses: list[str]) -> list[str]:
    roles = set()
    for lens_id in lenses:
        roles.update(role.strip() for role in LENSES[lens_id]["reviewer_role"].split(";"))
    return sorted(role for role in roles if role)


def controls_for_lenses(lenses: list[str]) -> list[str]:
    return [str(LENSES[lens_id]["control"]) for lens_id in lenses]


def build_unit_rows(data: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    canonical_rows = rows_by_unit(data["canonical_cross_reference"].get("unit_rows", []))
    claims = rows_by_unit(data["translation_claim_matrix"].get("unit_claim_rows", []))
    cultural_rows = rows_by_unit(data["cultural_historical_atlas"].get("unit_rows", []))
    reception_rows = rows_by_unit(data["reception_divergence"].get("unit_rows", []))
    divine_rows = rows_by_unit(data["divine_name_policy"].get("unit_rows", []))
    superscription_rows = rows_by_unit(data["superscription_context"].get("unit_rows", []))
    poetic_rows = rows_by_unit(data["poetic_rhetorical_atlas"].get("unit_rows", []))
    witness_rows = rows_by_unit(data["witness_divergence"].get("unit_rows", []))
    dossier_rows = rows_by_unit(data["doctoral_priority_dossier"].get("unit_rows", []))
    contextual_rows = rows_by_unit(data["contextual_pressure_atlas"].get("priority_unit_rows", []))

    base_rows: dict[str, dict[str, Any]] = {}
    for source_rows in [
        witness_rows,
        poetic_rows,
        canonical_rows,
        cultural_rows,
        divine_rows,
        superscription_rows,
        claims,
        reception_rows,
        dossier_rows,
        contextual_rows,
    ]:
        for unit_id, row in source_rows.items():
            base = base_rows.setdefault(unit_id, {"unit_id": unit_id})
            for key in ["ref", "psalm_id", "source_hebrew"]:
                if row.get(key) and not base.get(key):
                    base[key] = row[key]

    rows = []
    for unit_id, base in sorted(base_rows.items()):
        canonical = canonical_rows.get(unit_id, {})
        claim = claims.get(unit_id, {})
        cultural = cultural_rows.get(unit_id, {})
        reception = reception_rows.get(unit_id, {})
        divine = divine_rows.get(unit_id, {})
        superscription = superscription_rows.get(unit_id, {})
        poetic = poetic_rows.get(unit_id, {})
        witness = witness_rows.get(unit_id, {})
        dossier = dossier_rows.get(unit_id, {})
        contextual = contextual_rows.get(unit_id, {})
        active_lenses = active_lenses_for_unit(
            canonical=canonical,
            claim=claim,
            cultural=cultural,
            reception=reception,
            divine=divine,
            superscription=superscription,
            poetic=poetic,
            witness=witness,
            dossier=dossier,
        )
        lens_weight_score = sum(float(LENSES[lens_id]["weight"]) for lens_id in active_lenses)
        score = round(
            lens_weight_score
            + lens_score_bonus(
                canonical=canonical,
                cultural=cultural,
                witness=witness,
                reception=reception,
                poetic=poetic,
                dossier=dossier,
                claim=claim,
                contextual=contextual,
            ),
            2,
        )
        band = band_for_score(score)
        row = {
            "unit_id": unit_id,
            "ref": base.get("ref", ""),
            "psalm_id": base.get("psalm_id", ""),
            "integration_pressure_score": score,
            "integration_pressure_band": band,
            "active_lens_count": len(active_lenses),
            "active_lenses": active_lenses,
            "active_lens_labels": [str(LENSES[lens_id]["label"]) for lens_id in active_lenses],
            "required_review_roles": reviewer_roles_for_lenses(active_lenses),
            "translation_controls": controls_for_lenses(active_lenses),
            "whole_tanakh_three_division": "whole_tanakh_three_division" in active_lenses,
            "high_value_canonical_anchor": "high_value_canonical_anchor" in active_lenses,
            "cultural_historical_domain": "cultural_historical_domain" in active_lenses,
            "ancient_culture_pressure": "ancient_culture_pressure" in active_lenses,
            "textual_witness_pressure": "textual_witness_pressure" in active_lenses,
            "high_english_witness_divergence": "high_english_witness_divergence" in active_lenses,
            "divine_name_policy": "divine_name_policy" in active_lenses,
            "divine_name_witness_disagreement": "divine_name_witness_disagreement" in active_lenses,
            "superscription_context": "superscription_context" in active_lenses,
            "poetic_rhetorical_pressure": "poetic_rhetorical_pressure" in active_lenses,
            "reception_sensitive": "reception_sensitive" in active_lenses,
            "jewish_christian_separation": "jewish_christian_separation" in active_lenses,
            "academic_comparison_required": "academic_comparison_required" in active_lenses,
            "authority_blocked_dossier": "authority_blocked_dossier" in active_lenses,
            "canonical_anchor_token_count": safe_int(canonical, "anchor_token_count"),
            "canonical_anchor_token_pct": safe_float(canonical, "anchor_token_pct"),
            "canonical_high_value_anchor_count": safe_int(canonical, "high_value_anchor_count"),
            "canonical_top_anchor_forms": join_values(canonical.get("top_anchor_forms"), limit=8),
            "cultural_domain_count": safe_int(cultural, "domain_count"),
            "cultural_domain_labels": join_values(cultural.get("domain_labels"), limit=8),
            "witness_divergence_pct": safe_float(witness, "mean_english_witness_divergence_pct"),
            "witness_marker_flags": join_values(witness.get("marker_flags"), limit=10),
            "divine_title_token_count": safe_int(divine, "divine_title_token_count"),
            "divine_name_categories": join_values(divine.get("categories"), limit=8),
            "superscription_context_token_count": safe_int(superscription, "context_token_count"),
            "superscription_categories": join_values(superscription.get("categories"), limit=8),
            "poetic_rhetorical_priority_score": safe_float(
                poetic, "poetic_rhetorical_priority_score"
            ),
            "poetic_pressure_band": poetic.get("pressure_band", ""),
            "poetic_feature_flags": join_values(poetic.get("feature_flags"), limit=10),
            "reception_divergence_priority_score": safe_float(
                reception, "reception_divergence_priority_score"
            ),
            "reception_required_frames": join_values(reception.get("required_frames"), limit=8),
            "claim_risk_score": safe_float(claim, "claim_risk_score"),
            "claim_risk_band": claim.get("claim_risk_band", ""),
            "dossier_priority_score": safe_float(dossier, "doctoral_dossier_priority_score"),
            "unit_authority_score_pct": safe_float(dossier, "unit_authority_score_pct"),
            "blocking_lane_count": safe_int(dossier, "blocking_lane_count"),
            "source_hebrew": (
                canonical.get("source_hebrew")
                or poetic.get("source_hebrew")
                or reception.get("source_hebrew")
                or dossier.get("source_hebrew")
                or base.get("source_hebrew", "")
            ),
        }
        rows.append(row)

    rows.sort(key=lambda item: float(item["integration_pressure_score"]), reverse=True)
    for index, row in enumerate(rows, start=1):
        row["rank"] = index
    return rows


def build_lens_rows(unit_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    total_units = len(unit_rows)
    for lens_id, lens in LENSES.items():
        active_rows = [row for row in unit_rows if lens_id in row["active_lenses"]]
        top = active_rows[0] if active_rows else {}
        rows.append(
            {
                "lens_id": lens_id,
                "label": lens["label"],
                "category": lens["category"],
                "unit_count": len(active_rows),
                "unit_pct": pct(len(active_rows), total_units),
                "high_pressure_unit_count": sum(
                    1
                    for row in active_rows
                    if row["integration_pressure_band"] in HIGH_PRESSURE_BANDS
                ),
                "top_ref": top.get("ref", ""),
                "top_unit_id": top.get("unit_id", ""),
                "top_integration_pressure_score": top.get("integration_pressure_score", 0.0),
                "reviewer_role": lens["reviewer_role"],
                "source_artifact": lens["source_artifact"],
                "translation_control": lens["control"],
            }
        )
    return sorted(rows, key=lambda row: int(row["unit_count"]), reverse=True)


def build_cooccurrence_rows(unit_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    lens_sets = {lens_id: set() for lens_id in LENSES}
    pair_counts: Counter[tuple[str, str]] = Counter()
    for row in unit_rows:
        active = sorted(row["active_lenses"])
        for lens_id in active:
            lens_sets[lens_id].add(row["unit_id"])
        for left, right in combinations(active, 2):
            pair_counts[(left, right)] += 1

    rows = []
    for left, right in combinations(sorted(LENSES), 2):
        overlap = int(pair_counts.get((left, right), 0))
        union = len(lens_sets[left] | lens_sets[right])
        rows.append(
            {
                "lens_a": left,
                "lens_a_label": LENSES[left]["label"],
                "lens_b": right,
                "lens_b_label": LENSES[right]["label"],
                "unit_count": overlap,
                "jaccard_pct": pct(overlap, union),
                "combined_label": f"{LENSES[left]['short_label']} + {LENSES[right]['short_label']}",
            }
        )
    return sorted(rows, key=lambda row: (int(row["unit_count"]), row["jaccard_pct"]), reverse=True)


def build_psalm_rows(unit_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in unit_rows:
        grouped[str(row["psalm_id"])].append(row)

    rows = []
    for psalm_id, psalm_units in grouped.items():
        sorted_units = sorted(
            psalm_units,
            key=lambda row: float(row["integration_pressure_score"]),
            reverse=True,
        )
        high_units = [
            row for row in psalm_units if row["integration_pressure_band"] in HIGH_PRESSURE_BANDS
        ]
        lens_counter = Counter()
        for row in psalm_units:
            lens_counter.update(row["active_lenses"])
        rows.append(
            {
                "psalm_id": psalm_id,
                "psalm": f"Psalm {int(psalm_id.removeprefix('ps'))}",
                "unit_count": len(psalm_units),
                "high_pressure_unit_count": len(high_units),
                "high_pressure_unit_pct": pct(len(high_units), len(psalm_units)),
                "mean_integration_pressure_score": mean(
                    [float(row["integration_pressure_score"]) for row in psalm_units]
                ),
                "mean_active_lens_count": mean(
                    [float(row["active_lens_count"]) for row in psalm_units]
                ),
                "top_ref": sorted_units[0]["ref"],
                "top_unit_id": sorted_units[0]["unit_id"],
                "top_integration_pressure_score": sorted_units[0]["integration_pressure_score"],
                "jewish_christian_separation_unit_count": lens_counter[
                    "jewish_christian_separation"
                ],
                "reception_sensitive_unit_count": lens_counter["reception_sensitive"],
                "textual_witness_pressure_unit_count": lens_counter["textual_witness_pressure"],
                "cultural_historical_domain_unit_count": lens_counter["cultural_historical_domain"],
                "divine_name_policy_unit_count": lens_counter["divine_name_policy"],
                "poetic_rhetorical_pressure_unit_count": lens_counter["poetic_rhetorical_pressure"],
                "dominant_lenses": "; ".join(
                    LENSES[lens_id]["short_label"] for lens_id, _ in lens_counter.most_common(6)
                ),
            }
        )
    return sorted(
        rows,
        key=lambda row: (
            float(row["top_integration_pressure_score"]),
            float(row["mean_integration_pressure_score"]),
        ),
        reverse=True,
    )


def csv_unit_rows(unit_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for row in unit_rows:
        csv_row = dict(row)
        csv_row["active_lenses"] = join_values(row["active_lenses"])
        csv_row["active_lens_labels"] = join_values(row["active_lens_labels"])
        csv_row["required_review_roles"] = join_values(row["required_review_roles"])
        csv_row["translation_controls"] = join_values(row["translation_controls"])
        rows.append(csv_row)
    return rows


def compact_unit_rows(unit_rows: list[dict[str, Any]], limit: int = 50) -> list[dict[str, Any]]:
    keys = [
        "rank",
        "unit_id",
        "ref",
        "psalm_id",
        "integration_pressure_score",
        "integration_pressure_band",
        "active_lens_count",
        "active_lens_labels",
        "required_review_roles",
        "canonical_top_anchor_forms",
        "cultural_domain_labels",
        "witness_divergence_pct",
        "divine_name_categories",
        "superscription_categories",
        "poetic_pressure_band",
        "reception_required_frames",
        "claim_risk_score",
        "dossier_priority_score",
        "unit_authority_score_pct",
        "blocking_lane_count",
        "source_hebrew",
    ]
    return [{key: row[key] for key in keys} for row in unit_rows[:limit]]


def build_summary(
    unit_rows: list[dict[str, Any]],
    lens_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    total = len(unit_rows)
    high_rows = [
        row for row in unit_rows if row["integration_pressure_band"] in HIGH_PRESSURE_BANDS
    ]
    top = unit_rows[0] if unit_rows else {}
    lens_counter = Counter()
    for row in unit_rows:
        lens_counter.update(row["active_lenses"])
    multi_lens_rows = [row for row in unit_rows if int(row["active_lens_count"]) >= 6]
    doctoral_collision_rows = [
        row
        for row in unit_rows
        if row["whole_tanakh_three_division"]
        and row["cultural_historical_domain"]
        and row["textual_witness_pressure"]
        and (row["reception_sensitive"] or row["jewish_christian_separation"])
    ]
    return {
        "unit_count": total,
        "lens_count": len(LENSES),
        "high_pressure_unit_count": len(high_rows),
        "high_pressure_unit_pct": pct(len(high_rows), total),
        "multi_lens_unit_count": len(multi_lens_rows),
        "multi_lens_unit_pct": pct(len(multi_lens_rows), total),
        "doctoral_collision_unit_count": len(doctoral_collision_rows),
        "doctoral_collision_unit_pct": pct(len(doctoral_collision_rows), total),
        "top_unit_id": top.get("unit_id", ""),
        "top_ref": top.get("ref", ""),
        "top_integration_pressure_score": top.get("integration_pressure_score", 0.0),
        "top_integration_pressure_band": top.get("integration_pressure_band", ""),
        "top_active_lens_count": top.get("active_lens_count", 0),
        "whole_tanakh_three_division_unit_count": lens_counter["whole_tanakh_three_division"],
        "cultural_historical_domain_unit_count": lens_counter["cultural_historical_domain"],
        "textual_witness_pressure_unit_count": lens_counter["textual_witness_pressure"],
        "high_english_witness_divergence_unit_count": lens_counter[
            "high_english_witness_divergence"
        ],
        "divine_name_policy_unit_count": lens_counter["divine_name_policy"],
        "superscription_context_unit_count": lens_counter["superscription_context"],
        "poetic_rhetorical_pressure_unit_count": lens_counter["poetic_rhetorical_pressure"],
        "reception_sensitive_unit_count": lens_counter["reception_sensitive"],
        "jewish_christian_separation_unit_count": lens_counter["jewish_christian_separation"],
        "authority_blocked_dossier_unit_count": lens_counter["authority_blocked_dossier"],
        "mean_active_lens_count": mean([float(row["active_lens_count"]) for row in unit_rows]),
        "source_artifact_count": len(SOURCE_PATHS),
        "strongest_lens_by_unit_count": lens_rows[0]["lens_id"] if lens_rows else "",
        "authority_verdict": (
            "routing_matrix_not_authority: integrated context pressure is deterministic "
            "review triage only; it does not approve source use, canonical wording, "
            "Jewish/Christian adjudication, or release status."
        ),
    }


def build_visual_data(
    lens_rows: list[dict[str, Any]],
    unit_rows: list[dict[str, Any]],
    psalm_rows: list[dict[str, Any]],
    cooccurrence_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "lens_coverage_rows": [
            {"label": row["label"], "value": row["unit_count"]} for row in lens_rows
        ],
        "top_unit_pressure_rows": [
            {"label": row["ref"], "value": row["integration_pressure_score"]}
            for row in unit_rows[:20]
        ],
        "top_psalm_pressure_rows": [
            {"label": row["psalm"], "value": row["top_integration_pressure_score"]}
            for row in psalm_rows[:20]
        ],
        "cooccurrence_rows": [
            {"label": row["combined_label"], "value": row["unit_count"]}
            for row in cooccurrence_rows[:24]
        ],
    }


def build_report() -> dict[str, Any]:
    data = {key: load_json(path) for key, path in SOURCE_PATHS.items()}
    unit_rows = build_unit_rows(data)
    lens_rows = build_lens_rows(unit_rows)
    cooccurrence_rows = build_cooccurrence_rows(unit_rows)
    psalm_rows = build_psalm_rows(unit_rows)
    summary = build_summary(unit_rows, lens_rows)
    return {
        "generated_on": datetime.now(UTC).date().isoformat(),
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "doctorate-level context integration matrix generated",
        "source_paths": {key: str(path.relative_to(ROOT)) for key, path in SOURCE_PATHS.items()},
        "method": {
            "base_population": (
                "Union of Psalm units from witness, poetic/rhetorical, canonical "
                "cross-reference, cultural, divine-name, superscription, claim, "
                "reception, dossier, and contextual-pressure unit rows; all joins "
                "use unit_id."
            ),
            "score_name": "integration_pressure_score",
            "score_boundary": (
                "Routing score only. It is a deterministic aggregation of existing "
                "report flags and source scores; it is not a translation-quality score "
                "or authority certification."
            ),
            "lens_weights": {lens_id: LENSES[lens_id]["weight"] for lens_id in sorted(LENSES)},
            "high_pressure_bands": sorted(HIGH_PRESSURE_BANDS),
            "doctoral_collision_definition": (
                "Unit has three-division broader-canon evidence, cultural/historical "
                "domain evidence, textual-witness pressure, and either reception "
                "sensitivity or Jewish/Christian separation."
            ),
        },
        "summary": summary,
        "lens_rows": lens_rows,
        "cooccurrence_rows": cooccurrence_rows,
        "psalm_rows": psalm_rows,
        "unit_rows": unit_rows,
        "priority_unit_rows": compact_unit_rows(unit_rows, limit=75),
        "visual_data": build_visual_data(lens_rows, unit_rows, psalm_rows, cooccurrence_rows),
    }


def metric_cards(cards: list[tuple[str, str, str]]) -> str:
    return (
        '<div class="grid">'
        + "".join(
            (
                '<div class="card">'
                f'<div class="metric">{esc(value)}</div>'
                f'<div class="label">{esc(label)}</div>'
                f"<p>{esc(note)}</p>"
                "</div>"
            )
            for label, value, note in cards
        )
        + "</div>"
    )


def table(headers: list[str], rows: list[list[Any]]) -> str:
    head = "".join(f"<th>{esc(header)}</th>" for header in headers)
    body_rows = []
    for row in rows:
        body_rows.append("<tr>" + "".join(f"<td>{esc(cell)}</td>" for cell in row) + "</tr>")
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body_rows)}</tbody></table>"


def svg_horizontal_bars(
    rows: list[dict[str, Any]],
    *,
    label_key: str,
    value_key: str,
    aria_label: str,
    color: str = "#2f6f73",
    limit: int = 20,
) -> str:
    chart_rows = rows[:limit]
    width = 980
    left = 260
    right = 60
    bar_height = 20
    gap = 10
    height = 40 + len(chart_rows) * (bar_height + gap)
    max_value = max([float(row[value_key]) for row in chart_rows] or [1.0])
    items = [
        f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="{esc(aria_label)}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
    ]
    usable_width = width - left - right
    for index, row in enumerate(chart_rows):
        y = 24 + index * (bar_height + gap)
        value = float(row[value_key])
        bar_width = 0 if max_value == 0 else value / max_value * usable_width
        label = str(row[label_key])
        if len(label) > 42:
            label = label[:39] + "..."
        items.append(
            f'<text x="{left - 12}" y="{y + 15}" text-anchor="end" '
            f'font-size="12" fill="#24313a">{esc(label)}</text>'
        )
        items.append(
            f'<rect x="{left}" y="{y}" width="{bar_width:.1f}" height="{bar_height}" '
            f'rx="3" fill="{color}"/>'
        )
        items.append(
            f'<text x="{left + bar_width + 8:.1f}" y="{y + 15}" '
            f'font-size="12" font-weight="700" fill="#24313a">{value:g}</text>'
        )
    items.append("</svg>")
    return "".join(items)


def render_html(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lens_rows = [
        [
            row["label"],
            row["category"],
            row["unit_count"],
            f"{row['unit_pct']:.2f}%",
            row["high_pressure_unit_count"],
            row["top_ref"],
            f"{row['top_integration_pressure_score']:.2f}",
            row["reviewer_role"],
            row["translation_control"],
        ]
        for row in report["lens_rows"]
    ]
    priority_rows = [
        [
            row["rank"],
            row["ref"],
            f"{row['integration_pressure_score']:.2f}",
            row["integration_pressure_band"],
            row["active_lens_count"],
            join_values(row["active_lens_labels"], limit=8),
            join_values(row["required_review_roles"]),
            row["canonical_top_anchor_forms"],
            row["cultural_domain_labels"],
            row["reception_required_frames"],
        ]
        for row in report["priority_unit_rows"][:30]
    ]
    psalm_rows = [
        [
            row["psalm"],
            row["unit_count"],
            row["high_pressure_unit_count"],
            f"{row['high_pressure_unit_pct']:.2f}%",
            f"{row['mean_active_lens_count']:.2f}",
            row["top_ref"],
            f"{row['top_integration_pressure_score']:.2f}",
            row["dominant_lenses"],
        ]
        for row in report["psalm_rows"][:30]
    ]
    cooccurrence_rows = [
        [
            row["lens_a_label"],
            row["lens_b_label"],
            row["unit_count"],
            f"{row['jaccard_pct']:.2f}%",
        ]
        for row in report["cooccurrence_rows"][:40]
    ]
    visual = report["visual_data"]
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Doctoral Context Integration Matrix</title>
  <style>
    :root {{
      --ink: #1f2a33;
      --muted: #667581;
      --line: #d7dde2;
      --band: #f5f7f8;
      --accent: #2f6f73;
      --accent2: #7c5b2f;
      --warn: #9b3d3d;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Arial, Helvetica, sans-serif;
      color: var(--ink);
      background: #fff;
      line-height: 1.48;
    }}
    header {{
      padding: 42px 54px 34px;
      border-bottom: 1px solid var(--line);
      background: linear-gradient(180deg, #ffffff 0%, #f6f8f8 100%);
    }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 30px 34px 54px; }}
    h1 {{ margin: 0 0 12px; font-size: 34px; letter-spacing: 0; }}
    h2 {{
      margin: 34px 0 14px;
      font-size: 22px;
      border-bottom: 1px solid var(--line);
      padding-bottom: 8px;
    }}
    p {{ margin: 0 0 13px; }}
    .lede {{ max-width: 980px; font-size: 17px; color: #33414c; }}
    .meta {{ color: var(--muted); font-size: 13px; margin-top: 12px; }}
    .grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; }}
    .card {{ border: 1px solid var(--line); border-radius: 6px; padding: 16px; }}
    .metric {{ font-size: 30px; font-weight: 700; color: var(--accent); }}
    .label {{
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: .05em;
    }}
    .warning {{
      background: #fff1f1;
      border-left: 4px solid var(--warn);
      padding: 13px 15px;
      margin: 18px 0;
    }}
    .chart {{
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 14px;
      margin: 16px 0;
      overflow-x: auto;
      background: #fff;
    }}
    table {{ border-collapse: collapse; width: 100%; margin: 14px 0 24px; font-size: 13px; }}
    th, td {{ border: 1px solid var(--line); padding: 9px 10px; vertical-align: top; }}
    th {{ background: var(--band); text-align: left; }}
    @media (max-width: 900px) {{
      header {{ padding: 30px 24px; }}
      main {{ padding: 24px 18px; }}
      .grid {{ grid-template-columns: repeat(2, 1fr); }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>Doctoral Context Integration Matrix</h1>
    <p class="lede">
      Unit-level integration of broader-canon anchors, culture/history,
      textual witnesses, divine-name policy, superscription context, poetics,
      reception, and Jewish/Christian separation. The score is reviewer
      routing evidence only.
    </p>
    <p class="meta">
      Generated {esc(report["generated_on"])} from {len(SOURCE_PATHS)} source artifacts.
    </p>
  </header>
  <main>
    <section>
      <h2>Summary</h2>
      <div class="warning">{esc(summary["authority_verdict"])}</div>
      {
        metric_cards(
            [
                ("Units", f"{summary['unit_count']:,}", "All Psalm units in the base population."),
                ("Lenses", str(summary["lens_count"]), "Joined context and authority lenses."),
                (
                    "High pressure",
                    f"{summary['high_pressure_unit_count']:,}",
                    f"{summary['high_pressure_unit_pct']:.2f}% of units.",
                ),
                (
                    "Multi-lens",
                    f"{summary['multi_lens_unit_count']:,}",
                    f"{summary['multi_lens_unit_pct']:.2f}% carry six or more lenses.",
                ),
                (
                    "Doctoral collisions",
                    f"{summary['doctoral_collision_unit_count']:,}",
                    "Canon + culture + witness + reception overlap.",
                ),
                (
                    "Top unit",
                    summary["top_ref"],
                    f"Score {summary['top_integration_pressure_score']:.2f}; "
                    f"{summary['top_active_lens_count']} active lenses.",
                ),
                (
                    "J/C separation",
                    f"{summary['jewish_christian_separation_unit_count']:,}",
                    "Units requiring separated Jewish and Christian lanes.",
                ),
                (
                    "Authority blocked",
                    f"{summary['authority_blocked_dossier_unit_count']:,}",
                    "Dossier units with blocking lanes.",
                ),
            ]
        )
    }
    </section>

    <section>
      <h2>Lens Coverage</h2>
      <div class="chart">{
        svg_horizontal_bars(
            visual["lens_coverage_rows"],
            label_key="label",
            value_key="value",
            aria_label="Integrated context lens coverage by unit count",
            color="#2f6f73",
            limit=18,
        )
    }</div>
      {
        table(
            [
                "Lens",
                "Category",
                "Units",
                "Pct",
                "High-Pressure Units",
                "Top Ref",
                "Top Score",
                "Reviewer Roles",
                "Control",
            ],
            lens_rows,
        )
    }
    </section>

    <section>
      <h2>Top Units</h2>
      <div class="chart">{
        svg_horizontal_bars(
            visual["top_unit_pressure_rows"],
            label_key="label",
            value_key="value",
            aria_label="Top integrated context pressure units",
            color="#7c5b2f",
            limit=20,
        )
    }</div>
      {
        table(
            [
                "Rank",
                "Ref",
                "Score",
                "Band",
                "Lenses",
                "Lens Labels",
                "Reviewer Roles",
                "Anchor Forms",
                "Culture Domains",
                "Reception Frames",
            ],
            priority_rows,
        )
    }
    </section>

    <section>
      <h2>Psalm-Level Pressure</h2>
      <div class="chart">{
        svg_horizontal_bars(
            visual["top_psalm_pressure_rows"],
            label_key="label",
            value_key="value",
            aria_label="Top Psalms by peak integrated context pressure",
            color="#2f6f73",
            limit=20,
        )
    }</div>
      {
        table(
            [
                "Psalm",
                "Units",
                "High-Pressure Units",
                "High-Pressure Pct",
                "Mean Lens Count",
                "Top Ref",
                "Top Score",
                "Dominant Lenses",
            ],
            psalm_rows,
        )
    }
    </section>

    <section>
      <h2>Lens Co-Occurrence</h2>
      <div class="chart">{
        svg_horizontal_bars(
            visual["cooccurrence_rows"],
            label_key="label",
            value_key="value",
            aria_label="Top integrated context lens co-occurrences",
            color="#8a6426",
            limit=24,
        )
    }</div>
      {
        table(
            ["Lens A", "Lens B", "Units", "Jaccard"],
            cooccurrence_rows,
        )
    }
    </section>
  </main>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate an integrated doctoral context matrix for Psalms units."
    )
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--lens-csv-output", type=Path, default=DEFAULT_LENS_CSV_OUTPUT)
    parser.add_argument("--unit-csv-output", type=Path, default=DEFAULT_UNIT_CSV_OUTPUT)
    parser.add_argument("--psalm-csv-output", type=Path, default=DEFAULT_PSALM_CSV_OUTPUT)
    parser.add_argument(
        "--cooccurrence-csv-output",
        type=Path,
        default=DEFAULT_COOCCURRENCE_CSV_OUTPUT,
    )
    parser.add_argument("--html-output", type=Path, default=DEFAULT_HTML_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_report()
    write_json(args.json_output, report)
    write_csv(args.lens_csv_output, report["lens_rows"])
    write_csv(args.unit_csv_output, csv_unit_rows(report["unit_rows"]))
    write_csv(args.psalm_csv_output, report["psalm_rows"])
    write_csv(args.cooccurrence_csv_output, report["cooccurrence_rows"])
    args.html_output.parent.mkdir(parents=True, exist_ok=True)
    args.html_output.write_text(render_html(report), encoding="utf-8")
    print(f"Wrote {args.json_output}")
    print(f"Wrote {args.lens_csv_output}")
    print(f"Wrote {args.unit_csv_output}")
    print(f"Wrote {args.psalm_csv_output}")
    print(f"Wrote {args.cooccurrence_csv_output}")
    print(f"Wrote {args.html_output}")


if __name__ == "__main__":
    main()
