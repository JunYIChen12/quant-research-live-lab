"""Small cached release gate for Freqtrade entry callbacks."""

from dataclasses import dataclass, field
from pathlib import Path

from .release import (
    ApprovalVerifier,
    ReleaseManifest,
    ReleaseVerification,
    load_manifest,
    verify_release,
)


@dataclass(slots=True)
class ReleaseGate:
    repository_root: Path
    artifact_root: Path
    manifest_path: Path
    requested_mode: str
    expected_repository: str
    approval_verifier: ApprovalVerifier
    approval_ttl_seconds: float = 300
    _approved_manifest: ReleaseManifest | None = field(default=None, init=False)
    _approved_at: float | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        if self.approval_ttl_seconds <= 0:
            raise ValueError("approval_ttl_seconds must be positive")

    def refresh(self, *, now: float) -> ReleaseVerification:
        """Perform the full local and GitHub-backed release verification."""
        result = self._verify(self.approval_verifier)
        if result.allowed:
            self._approved_manifest = load_manifest(self.manifest_path)
            self._approved_at = now
        else:
            self._approved_manifest = None
            self._approved_at = None
        return result

    def check_before_entry(self, *, now: float) -> ReleaseVerification:
        """Recheck local frozen state without a network call before an entry order."""
        if self._approved_manifest is None or self._approved_at is None:
            return ReleaseVerification(False, ("approval_not_cached",))
        if now < self._approved_at or now - self._approved_at > self.approval_ttl_seconds:
            return ReleaseVerification(False, ("approval_stale",))

        approved_manifest = self._approved_manifest
        return self._verify(lambda manifest: manifest == approved_manifest)

    def _verify(self, approval_verifier: ApprovalVerifier) -> ReleaseVerification:
        return verify_release(
            repository_root=self.repository_root,
            artifact_root=self.artifact_root,
            manifest_path=self.manifest_path,
            requested_mode=self.requested_mode,
            expected_repository=self.expected_repository,
            approval_verifier=approval_verifier,
        )
