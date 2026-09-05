"""Hard-gate registry behind ``make verify`` (D10). Integrator-owned.

Things that are provably right or wrong fail the build here. Measured things
(recall, precision, match rate) are published by lane N and gate nothing.

Lanes implement gate callables inside their own packages. **They are registered
in ``cli.py``, not here.** This module is imported by walled packages (a lane
needs ``GateResult`` to type its own gate), so importing a lane package here
would make every walled package transitively reach it and fail the D12 wall
test — ``tests/test_anticircularity.py`` asserts this module stays wall-neutral.
``cli.py`` is imported by nothing, which is what makes it the composition root
(lane C, Wave 1).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Final

from leakproof import contract as c


@dataclass(frozen=True, slots=True)
class GateResult:
    name: str
    ok: bool
    detail: str


Gate = Callable[[], GateResult]


def contract_self_check() -> GateResult:
    """The class table and the partition function must cover every class, and
    the primary mechanism must be one the class allows."""
    problems: list[str] = []
    for cls in c.ErrorClass:
        if cls not in c.ALLOWED_MECHANISMS:
            problems.append(f"class {int(cls)} has no allowed mechanisms")
        elif c.PRIMARY_MECHANISM.get(cls) not in c.ALLOWED_MECHANISMS[cls]:
            problems.append(f"class {int(cls)} primary mechanism not in its allowed set")
        if cls not in c.CLASS_BUCKET:
            problems.append(f"class {int(cls)} has no bucket")
    for cls, mechs in c.ALLOWED_MECHANISMS.items():
        if (c.Mechanism.NONE in mechs) != (cls is c.ErrorClass.UNEXPLAINED_DEDUCTION):
            problems.append(f"class {int(cls)}: mechanism none is class 8 only")
    return GateResult(
        "contract-self-check", not problems, "; ".join(problems) or "class table consistent"
    )


#: Gates that depend on nothing but this package. ``cli.hard_gates()`` extends
#: it with the lane gates as those lanes merge.
BASE_GATES: Final[tuple[Gate, ...]] = (contract_self_check,)


def run_hard_gates(gates: Sequence[Gate] = BASE_GATES) -> list[GateResult]:
    return [gate() for gate in gates]
