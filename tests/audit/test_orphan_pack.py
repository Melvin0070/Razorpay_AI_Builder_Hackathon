"""D8 orphan-pack detection: an audit entry naming an artifact_path whose
file does not exist under artifacts_root must fail verification naming the
path; one whose pack was actually written must pass."""

from __future__ import annotations

from leakproof.audit import AuditLog, verify_chain
from leakproof.contract import AuditAction, State
from tests.audit.conftest import append_sample


def test_orphan_pack_fails_naming_the_missing_path(tmp_path):
    artifacts_root = tmp_path / "artifacts"
    artifacts_root.mkdir()
    path = tmp_path / "audit.jsonl"
    log = AuditLog(path)

    append_sample(
        log,
        "2026-08-21T10:00:00Z",
        action=AuditAction.APPROVE,
        exception_id="e1",
        state_before=State.CLAIM_READY,
        state_after=State.CLAIM_READY,
        artifact_path="packs/e1.json",  # never written
    )

    result = verify_chain(path, artifacts_root=artifacts_root)
    assert not result.ok
    assert result.first_bad_seq == 1
    assert "packs/e1.json" in result.detail


def test_existing_pack_verifies_ok(tmp_path):
    artifacts_root = tmp_path / "artifacts"
    pack_dir = artifacts_root / "packs"
    pack_dir.mkdir(parents=True)
    (pack_dir / "e2.json").write_text("{}", encoding="utf-8")

    path = tmp_path / "audit.jsonl"
    log = AuditLog(path)
    append_sample(
        log,
        "2026-08-21T10:00:00Z",
        action=AuditAction.APPROVE,
        exception_id="e2",
        state_before=State.CLAIM_READY,
        state_after=State.CLAIM_READY,
        artifact_path="packs/e2.json",
    )

    result = verify_chain(path, artifacts_root=artifacts_root)
    assert result.ok
    assert result.entries == 1


def test_artifact_check_is_skipped_without_artifacts_root(tmp_path):
    """Without artifacts_root, an entry naming a nonexistent pack still
    verifies on hash/chain grounds alone — the orphan-pack check is opt-in,
    matching the D8 wording ("when artifacts_root is given")."""
    path = tmp_path / "audit.jsonl"
    log = AuditLog(path)
    append_sample(
        log,
        "2026-08-21T10:00:00Z",
        action=AuditAction.APPROVE,
        exception_id="e3",
        artifact_path="packs/does-not-exist.json",
    )

    assert verify_chain(path).ok
    assert not verify_chain(path, artifacts_root=path.parent).ok
