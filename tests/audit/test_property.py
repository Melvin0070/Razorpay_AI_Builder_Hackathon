"""Property test (hypothesis): any sequence of appended entries verifies.

Uses tmp_path_factory.mktemp() rather than the function-scoped tmp_path
fixture, since hypothesis re-invokes the test body per example and a
function-scoped fixture would be shared (and its directory reused/dirtied)
across examples.
"""

from __future__ import annotations

from datetime import date

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from leakproof.audit import AuditLog, verify_chain
from leakproof.contract import AuditAction, State

_ACTORS = st.text(
    alphabet=st.characters(blacklist_categories=("Cs",), max_codepoint=0x2FFF),
    min_size=1,
    max_size=20,
)
_ACTIONS = st.sampled_from(list(AuditAction))
_STATES = st.none() | st.sampled_from(list(State))
_AMOUNTS = st.none() | st.integers(min_value=-10_000_000, max_value=10_000_000)
_EXCEPTION_IDS = st.none() | st.text(min_size=1, max_size=12)

_ENTRY_KWARGS = st.fixed_dictionaries(
    {
        "actor": _ACTORS,
        "action": _ACTIONS,
        "state_before": _STATES,
        "state_after": _STATES,
        "amount_paise": _AMOUNTS,
        "exception_id": _EXCEPTION_IDS,
    }
)


@settings(
    max_examples=30,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(st.lists(_ENTRY_KWARGS, min_size=1, max_size=8))
def test_any_appended_sequence_verifies(tmp_path_factory, entry_kwargs_list):
    log_dir = tmp_path_factory.mktemp("audit-prop")
    path = log_dir / "audit.jsonl"
    log = AuditLog(path)

    for i, kwargs in enumerate(entry_kwargs_list):
        log.append(
            ts=f"2026-08-21T{i:02d}:00:00Z",
            as_of=date(2026, 8, 21),
            artifact_path=None,
            **kwargs,
        )

    result = verify_chain(path)
    assert result.ok, result.detail
    assert result.entries == len(entry_kwargs_list)
    assert result.first_bad_seq is None
