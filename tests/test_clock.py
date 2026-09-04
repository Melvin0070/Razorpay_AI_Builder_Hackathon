"""D18: nothing but cli.py reads the system clock. Every date computation takes as_of."""

import re

from tests.conftest import SRC

BANNED = re.compile(
    r"\b(date\.today|datetime\.now|datetime\.utcnow|datetime\.today|time\.time)\s*\("
)


def test_no_system_clock_outside_cli():
    offenders = []
    for path in SRC.rglob("*.py"):
        if path.name == "cli.py":
            continue
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if BANNED.search(line):
                offenders.append(f"{path.relative_to(SRC.parent)}:{n}: {line.strip()}")
    assert not offenders, "system clock read outside cli.py:\n" + "\n".join(offenders)
