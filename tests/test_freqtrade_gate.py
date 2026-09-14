from pathlib import Path

import quant_lab.freqtrade_gate as freqtrade_gate
from quant_lab.release import (
    ArtifactDigest,
    ReleaseManifest,
    ReleaseVerification,
)


def _manifest() -> ReleaseManifest:
    artifact = ArtifactDigest(path="artifact", sha256="0" * 64)
    return ReleaseManifest(
        schema_version=1,
        release_id="candidate-v0.2.0",
        execution_mode="dry-run",
        approved_commit_sha="0" * 40,
        release_tag="candidate-v0.2.0",
        repository="JunYIChen12/quant-research-live-lab",
        approval_pr_number=7,
        approval_label="release-approved",
        strategy=artifact,
        risk_config=artifact,
        evidence_bundle=artifact,
    )


def _gate() -> freqtrade_gate.ReleaseGate:
    return freqtrade_gate.ReleaseGate(
        repository_root=Path("repo"),
        artifact_root=Path("artifacts"),
        manifest_path=Path("release-manifest.toml"),
        requested_mode="dry-run",
        expected_repository="JunYIChen12/quant-research-live-lab",
        approval_verifier=lambda _: True,
        approval_ttl_seconds=60,
    )


def test_stale_full_approval_blocks_entry(monkeypatch) -> None:
    monkeypatch.setattr(
        freqtrade_gate,
        "verify_release",
        lambda **_: ReleaseVerification(True, ()),
    )
    monkeypatch.setattr(freqtrade_gate, "load_manifest", lambda _: _manifest())
    gate = _gate()

    assert gate.refresh(now=100).allowed is True

    result = gate.check_before_entry(now=161)
    assert result.allowed is False
    assert result.violations == ("approval_stale",)


def test_local_release_tampering_blocks_entry(monkeypatch) -> None:
    results = iter(
        [
            ReleaseVerification(True, ()),
            ReleaseVerification(False, ("strategy_hash_mismatch",)),
        ]
    )
    monkeypatch.setattr(freqtrade_gate, "verify_release", lambda **_: next(results))
    monkeypatch.setattr(freqtrade_gate, "load_manifest", lambda _: _manifest())
    gate = _gate()

    assert gate.refresh(now=100).allowed is True
    result = gate.check_before_entry(now=110)

    assert result.allowed is False
    assert result.violations == ("strategy_hash_mismatch",)
