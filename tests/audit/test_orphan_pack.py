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


def test_absolute_artifact_path_fails_even_if_the_file_exists(tmp_path):
    """F3: an absolute artifact_path used to be accepted outright (treated
    as already resolved) instead of being confined to artifacts_root."""
    artifacts_root = tmp_path / "artifacts"
    artifacts_root.mkdir()
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")

    path = tmp_path / "audit.jsonl"
    log = AuditLog(path)
    append_sample(
        log,
        "2026-08-21T10:00:00Z",
        action=AuditAction.APPROVE,
        exception_id="e4",
        state_before=State.CLAIM_READY,
        state_after=State.CLAIM_READY,
        artifact_path=str(outside),
    )

    result = verify_chain(path, artifacts_root=artifacts_root)
    assert not result.ok
    assert result.first_bad_seq == 1
    assert "relative to artifacts_root" in result.detail


def test_traversal_artifact_path_fails_even_if_it_resolves_to_a_real_file(tmp_path):
    """F3: "../elsewhere/pack.json" used to resolve outside artifacts_root
    and verify ok as long as a file happened to be there."""
    artifacts_root = tmp_path / "artifacts"
    artifacts_root.mkdir()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / "pack.json").write_text("{}", encoding="utf-8")

    path = tmp_path / "audit.jsonl"
    log = AuditLog(path)
    append_sample(
        log,
        "2026-08-21T10:00:00Z",
        action=AuditAction.APPROVE,
        exception_id="e5",
        state_before=State.CLAIM_READY,
        state_after=State.CLAIM_READY,
        artifact_path="../elsewhere/pack.json",
    )

    result = verify_chain(path, artifacts_root=artifacts_root)
    assert not result.ok
    assert result.first_bad_seq == 1
    assert "escapes artifacts_root" in result.detail


def test_directory_artifact_path_is_an_orphan(tmp_path):
    """F3: artifact_path pointing at a directory (no pack file actually
    written there) used to pass Path.exists() and verify ok."""
    artifacts_root = tmp_path / "artifacts"
    (artifacts_root / "packs").mkdir(parents=True)

    path = tmp_path / "audit.jsonl"
    log = AuditLog(path)
    append_sample(
        log,
        "2026-08-21T10:00:00Z",
        action=AuditAction.APPROVE,
        exception_id="e6",
        state_before=State.CLAIM_READY,
        state_after=State.CLAIM_READY,
        artifact_path="packs",
    )

    result = verify_chain(path, artifacts_root=artifacts_root)
    assert not result.ok
    assert result.first_bad_seq == 1
    assert "orphan pack" in result.detail


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
