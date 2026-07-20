from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures"


def fixture(name: str) -> Any:
    with (FIXTURE_ROOT / name).open(encoding="utf-8") as source:
        return json.load(source)


def copied_fixture(name: str) -> Any:
    return copy.deepcopy(fixture(name))
