"""Verification of frozen release artifacts and their GitHub approval."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tomllib
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

SHA1_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
TAG_PATTERNS = {
    "dry-run": re.compile(r"^candidate-v\d+\.\d+\.\d+$"),
    "live": re.compile(r"^live-v\d+\.\d+\.\d+$"),
}


@dataclass(frozen=True, slots=True)
class ArtifactDigest:
    path: str
    sha256: str


@dataclass(frozen=True, slots=True)
class ReleaseManifest:
    schema_version: int
    release_id: str
    execution_mode: str
    approved_commit_sha: str
    release_tag: str
    repository: str
    approval_pr_number: int
    approval_label: str
    strategy: ArtifactDigest
    risk_config: ArtifactDigest
    evidence_bundle: ArtifactDigest


@dataclass(frozen=True, slots=True)
class ReleaseVerification:
    allowed: bool
    violations: tuple[str, ...]
    release_id: str | None = None
    approved_commit_sha: str | None = None


ApprovalVerifier = Callable[[ReleaseManifest], bool]


def load_manifest(path: Path) -> ReleaseManifest:
    """Load a strict version-1 TOML release manifest."""
    with path.open("rb") as handle:
        raw = tomllib.load(handle)

    artifacts = raw["artifacts"]
    return ReleaseManifest(
        schema_version=int(raw["schema_version"]),
        release_id=str(raw["release_id"]),
        execution_mode=str(raw["execution_mode"]),
        approved_commit_sha=str(raw["approved_commit_sha"]).lower(),
        release_tag=str(raw["release_tag"]),
        repository=str(raw["repository"]),
        approval_pr_number=int(raw["approval_pr_number"]),
        approval_label=str(raw["approval_label"]),
        strategy=_artifact(artifacts["strategy"]),
        risk_config=_artifact(artifacts["risk_config"]),
        evidence_bundle=_artifact(artifacts["evidence_bundle"]),
    )


def verify_release(
    *,
    repository_root: Path,
    artifact_root: Path,
    manifest_path: Path,
    requested_mode: str,
    approval_verifier: ApprovalVerifier | None,
) -> ReleaseVerification:
    """Fail closed unless Git state, tags, artifacts and approval all match."""
    violations: list[str] = []
    try:
        manifest = load_manifest(manifest_path)
    except (OSError, KeyError, TypeError, ValueError, tomllib.TOMLDecodeError):
        return ReleaseVerification(False, ("manifest_invalid",))

    if manifest.schema_version != 1:
        violations.append("manifest_schema_unsupported")
    if requested_mode not in TAG_PATTERNS:
        violations.append("requested_mode_invalid")
    if manifest.execution_mode != requested_mode:
        violations.append("execution_mode_mismatch")
    if not SHA1_RE.fullmatch(manifest.approved_commit_sha):
        violations.append("approved_commit_invalid")
    if manifest.approval_pr_number <= 0:
        violations.append("approval_pr_invalid")
    if manifest.approval_label != "release-approved":
        violations.append("approval_label_invalid")
    if not REPOSITORY_RE.fullmatch(manifest.repository):
        violations.append("repository_invalid")
    if manifest.release_id != manifest.release_tag:
        violations.append("release_identity_mismatch")

    tag_pattern = TAG_PATTERNS.get(requested_mode)
    if tag_pattern is None or not tag_pattern.fullmatch(manifest.release_tag):
        violations.append("release_tag_invalid")

    head = _git(repository_root, "rev-parse", "HEAD")
    if head is None or head != manifest.approved_commit_sha:
        violations.append("commit_mismatch")
    if _git(repository_root, "status", "--porcelain", "--untracked-files=no"):
        violations.append("tracked_worktree_dirty")

    tag_target = _git(repository_root, "rev-list", "-n", "1", manifest.release_tag)
    tag_type = _git(repository_root, "cat-file", "-t", f"refs/tags/{manifest.release_tag}")
    if tag_target != head:
        violations.append("tag_target_mismatch")
    if tag_type != "tag":
        violations.append("tag_not_annotated")

    for name, artifact in (
        ("strategy", manifest.strategy),
        ("risk_config", manifest.risk_config),
        ("evidence_bundle", manifest.evidence_bundle),
    ):
        if not SHA256_RE.fullmatch(artifact.sha256):
            violations.append(f"{name}_hash_invalid")
            continue
        resolved = _safe_artifact_path(artifact_root, artifact.path)
        if resolved is None:
            violations.append(f"{name}_path_invalid")
        elif not resolved.is_file():
            violations.append(f"{name}_missing")
        elif _sha256(resolved) != artifact.sha256:
            violations.append(f"{name}_hash_mismatch")

    if approval_verifier is None:
        violations.append("approval_not_verified")
    else:
        try:
            if not approval_verifier(manifest):
                violations.append("approval_not_verified")
        except Exception:
            violations.append("approval_verification_error")

    return ReleaseVerification(
        allowed=not violations,
        violations=tuple(violations),
        release_id=manifest.release_id,
        approved_commit_sha=manifest.approved_commit_sha,
    )


class GitHubApprovalVerifier:
    """Verify that the release PR is merged into main and deliberately labelled."""

    def __init__(self, *, token: str | None = None, timeout_seconds: float = 5.0) -> None:
        self._token = token
        self._timeout_seconds = timeout_seconds

    def __call__(self, manifest: ReleaseManifest) -> bool:
        url = (
            "https://api.github.com/repos/"
            f"{manifest.repository}/pulls/{manifest.approval_pr_number}"
        )
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "quant-research-live-lab",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"

        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=self._timeout_seconds) as response:
                payload = json.load(response)
        except (OSError, ValueError, urllib.error.HTTPError, urllib.error.URLError):
            return False

        labels = {label.get("name") for label in payload.get("labels", [])}
        return bool(
            payload.get("merged_at")
            and payload.get("base", {}).get("ref") == "main"
            and payload.get("merge_commit_sha") == manifest.approved_commit_sha
            and manifest.approval_label in labels
        )


def _artifact(raw: object) -> ArtifactDigest:
    if not isinstance(raw, dict):
        raise TypeError("artifact must be a table")
    return ArtifactDigest(path=str(raw["path"]), sha256=str(raw["sha256"]).lower())


def _git(root: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *args],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip()


def _safe_artifact_path(root: Path, relative_path: str) -> Path | None:
    path = Path(relative_path)
    if path.is_absolute():
        return None
    root_resolved = root.resolve()
    resolved = (root_resolved / path).resolve()
    try:
        resolved.relative_to(root_resolved)
    except ValueError:
        return None
    return resolved


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
