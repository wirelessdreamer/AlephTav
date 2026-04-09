import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services import report_service


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--release-id", default="v0.1.0")
    args = parser.parse_args()
    report_service.generate_audit_reports()
    report_service.generate_release_report(args.release_id)


if __name__ == "__main__":
    main()
