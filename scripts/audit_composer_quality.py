import argparse
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.composer_quality_support import (
    audit_composer_outputs,
    bootstrap_vendored_repo,
    build_composer_outputs,
    collect_all_unit_ids,
    write_audit_reports,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bootstrap-vendored", action="store_true", help="rebuild vendored psalm content before auditing")
    parser.add_argument(
        "--json-out",
        default=str(ROOT / "reports" / "audit" / "composer_quality_full.json"),
        help="path for the JSON audit report",
    )
    parser.add_argument(
        "--md-out",
        default=str(ROOT / "reports" / "audit" / "composer_quality_full.md"),
        help="path for the Markdown audit summary",
    )
    args = parser.parse_args()

    if args.bootstrap_vendored:
        bootstrap_vendored_repo()

    unit_ids = collect_all_unit_ids()
    with tempfile.TemporaryDirectory(prefix="composer-quality-audit-") as temp_dir:
        outputs = build_composer_outputs(unit_ids, Path(temp_dir))
    report = audit_composer_outputs(outputs)
    write_audit_reports(report, Path(args.json_out), Path(args.md_out))

    print(f"Audited {report['unit_count']} units across {report['psalm_count']} psalms.")
    print(f"Flagged {report['flagged_unit_count']} units.")
    for code, count in report["issue_counts"].items():
        print(f"- {code}: {count}")


if __name__ == "__main__":
    main()
