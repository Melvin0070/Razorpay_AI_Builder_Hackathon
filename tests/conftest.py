import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "leakproof"
FIXTURES = ROOT / "tests" / "fixtures"


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return ROOT


@pytest.fixture(scope="session")
def demo_report_json() -> dict:
    return json.loads((FIXTURES / "batch_report.demo.json").read_text(encoding="utf-8"))
