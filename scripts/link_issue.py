import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services import github_link_service


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("unit_id")
    parser.add_argument("issue_number", type=int)
    args = parser.parse_args()
    print(github_link_service.link_issue(args.unit_id, args.issue_number))


if __name__ == "__main__":
    main()
