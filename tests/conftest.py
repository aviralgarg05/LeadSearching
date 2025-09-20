import sys
from pathlib import Path


def pytest_sessionstart(session):  # pragma: no cover
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
