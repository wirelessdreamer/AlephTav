import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services import registry_service


def main() -> None:
    registry_service.bootstrap_project()


if __name__ == "__main__":
    main()
