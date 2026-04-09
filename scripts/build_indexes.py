import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services import concordance_service, report_service


def main() -> None:
    concordance_service.rebuild_indexes()
    report_service.generate_audit_reports()


if __name__ == "__main__":
    main()
