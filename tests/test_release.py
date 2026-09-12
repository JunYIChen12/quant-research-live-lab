import hashlib
import io
import json
import subprocess
import urllib.request
from pathlib import Path

from quant_lab import GitHubApprovalVerifier, load_manifest, verify_release


def _run(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _release_fixture(tmp_path: Path) -> tuple[Path, Path, Path, str]:
    repository = tmp_path / "repo"
    artifacts = tmp_path / "bundle"
    repository.mkdir()
    artifacts.mkdir()

    _run(repository, "init", "-b", "main")
    _run(repository, "config", "user.name", "Test")
    _run(repository, "config", "user.email", "test@example.invalid")
    (repository / "tracked.txt").write_text("frozen\n", encoding="utf-8")
    _run(repository, "add", "tracked.txt")
    _run(repository, "commit", "-m", "frozen release")
    commit_sha = _run(repository, "rev-parse", "HEAD")

    strategy = artifacts / "strategy.py"
    risk_config = artifacts / "risk.toml"
    evidence = artifacts / "evidence.json"
    strategy.write_text("class Strategy: pass\n", encoding="utf-8")
    risk_config.write_text('max_leverage = "1"\n', encoding="utf-8")
    evidence.write_text('{"lookahead": "passed"}\n', encoding="utf-8")

    manifest = artifacts / "release-manifest.toml"
    manifest.write_text(
        "\n".join(
            [
                "schema_version = 1",
                'release_id = "candidate-v0.1.0"',
                'execution_mode = "dry-run"',
                f'approved_commit_sha = "{commit_sha}"',
                'release_tag = "candidate-v0.1.0"',
                'repository = "JunYIChen12/quant-research-live-lab"',
                "approval_pr_number = 7",
                'approval_label = "release-approved"',
                "",
                "[artifacts.strategy]",
                'path = "strategy.py"',
                f'sha256 = "{_sha256(strategy)}"',
                "",
                "[artifacts.risk_config]",
                'path = "risk.toml"',
                f'sha256 = "{_sha256(risk_config)}"',
                "",
                "[artifacts.evidence_bundle]",
                'path = "evidence.json"',
                f'sha256 = "{_sha256(evidence)}"',
                "",
            ]
        ),
        encoding="utf-8",
    )
    _run(
        repository,
        "tag",
        "-a",
        "candidate-v0.1.0",
        "-m",
        f"release-manifest-sha256={_sha256(manifest)}",
    )
    return repository, artifacts, manifest, commit_sha


def test_matching_frozen_release_is_allowed(tmp_path: Path) -> None:
    repository, artifacts, manifest, commit_sha = _release_fixture(tmp_path)

    result = verify_release(
        repository_root=repository,
        artifact_root=artifacts,
        manifest_path=manifest,
        requested_mode="dry-run",
        expected_repository="JunYIChen12/quant-research-live-lab",
        approval_verifier=lambda release: release.approved_commit_sha == commit_sha,
    )

    assert result.allowed is True
    assert result.violations == ()


def test_modified_strategy_is_rejected(tmp_path: Path) -> None:
    repository, artifacts, manifest, _ = _release_fixture(tmp_path)
    (artifacts / "strategy.py").write_text("tampered\n", encoding="utf-8")

    result = verify_release(
        repository_root=repository,
        artifact_root=artifacts,
        manifest_path=manifest,
        requested_mode="dry-run",
        expected_repository="JunYIChen12/quant-research-live-lab",
        approval_verifier=lambda _: True,
    )

    assert result.allowed is False
    assert "strategy_hash_mismatch" in result.violations


def test_manifest_and_artifact_tampering_after_tag_is_rejected(tmp_path: Path) -> None:
    repository, artifacts, manifest, _ = _release_fixture(tmp_path)
    strategy = artifacts / "strategy.py"
    approved_hash = _sha256(strategy)
    strategy.write_text("tampered\n", encoding="utf-8")
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace(approved_hash, _sha256(strategy)),
        encoding="utf-8",
    )

    result = verify_release(
        repository_root=repository,
        artifact_root=artifacts,
        manifest_path=manifest,
        requested_mode="dry-run",
        expected_repository="JunYIChen12/quant-research-live-lab",
        approval_verifier=lambda _: True,
    )

    assert result.allowed is False
    assert "manifest_hash_mismatch" in result.violations


def test_missing_real_approval_verifier_is_rejected(tmp_path: Path) -> None:
    repository, artifacts, manifest, _ = _release_fixture(tmp_path)

    result = verify_release(
        repository_root=repository,
        artifact_root=artifacts,
        manifest_path=manifest,
        requested_mode="dry-run",
        expected_repository="JunYIChen12/quant-research-live-lab",
        approval_verifier=None,
    )

    assert result.allowed is False
    assert "approval_not_verified" in result.violations


def test_wrong_execution_mode_is_rejected(tmp_path: Path) -> None:
    repository, artifacts, manifest, _ = _release_fixture(tmp_path)

    result = verify_release(
        repository_root=repository,
        artifact_root=artifacts,
        manifest_path=manifest,
        requested_mode="live",
        expected_repository="JunYIChen12/quant-research-live-lab",
        approval_verifier=lambda _: True,
    )

    assert result.allowed is False
    assert "execution_mode_mismatch" in result.violations
    assert "release_tag_invalid" in result.violations


def test_commit_mismatch_is_rejected(tmp_path: Path) -> None:
    repository, artifacts, manifest, _ = _release_fixture(tmp_path)
    (repository / "tracked.txt").write_text("next\n", encoding="utf-8")
    _run(repository, "add", "tracked.txt")
    _run(repository, "commit", "-m", "unapproved change")

    result = verify_release(
        repository_root=repository,
        artifact_root=artifacts,
        manifest_path=manifest,
        requested_mode="dry-run",
        expected_repository="JunYIChen12/quant-research-live-lab",
        approval_verifier=lambda _: True,
    )

    assert result.allowed is False
    assert "commit_mismatch" in result.violations
    assert "tag_target_mismatch" in result.violations


def test_manifest_cannot_redirect_approval_to_another_repository(tmp_path: Path) -> None:
    repository, artifacts, manifest, _ = _release_fixture(tmp_path)

    result = verify_release(
        repository_root=repository,
        artifact_root=artifacts,
        manifest_path=manifest,
        requested_mode="dry-run",
        expected_repository="trusted-owner/trusted-repository",
        approval_verifier=lambda _: True,
    )

    assert result.allowed is False
    assert "repository_mismatch" in result.violations


def test_github_approval_requires_merged_main_commit_and_label(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _, _, manifest_path, commit_sha = _release_fixture(tmp_path)
    payload = {
        "merged_at": "2026-09-12T00:00:00Z",
        "merge_commit_sha": commit_sha,
        "base": {"ref": "main"},
        "labels": [{"name": "release-approved"}],
    }

    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        lambda request, timeout: io.BytesIO(json.dumps(payload).encode()),
    )

    assert GitHubApprovalVerifier()(load_manifest(manifest_path)) is True


def test_github_approval_rejects_missing_release_label(tmp_path: Path, monkeypatch) -> None:
    _, _, manifest_path, commit_sha = _release_fixture(tmp_path)
    payload = {
        "merged_at": "2026-09-12T00:00:00Z",
        "merge_commit_sha": commit_sha,
        "base": {"ref": "main"},
        "labels": [],
    }

    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        lambda request, timeout: io.BytesIO(json.dumps(payload).encode()),
    )

    assert GitHubApprovalVerifier()(load_manifest(manifest_path)) is False
