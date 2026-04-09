import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services import ingest_service


def main() -> None:
    ingest_service.import_fixture_psalms()


if __name__ == "__main__":
    main()
