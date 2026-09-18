"""Run the offline Freqtrade checks for one frozen strategy candidate."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

Conclusion = Literal["qualified", "unqualified", "evidence_insufficient"]
CommandRunner = Callable[..., subprocess.CompletedProcess[str]]


@dataclass(frozen=True, slots=True)
class ValidationRequest:
    candidate_id: str
    strategy_name: str
    strategy_path: Path
    config_path: Path
    risk_config_path: Path
    data_dir: Path
    output_dir: Path
    repository_root: Path
    repository: str
    dataset_identity: str
    timeframe: str
    pairs: tuple[str, ...]
    development_timerange: str
    holdout_timerange: str
    hyperopt_loss: str
    hyperopt_epochs: int
    freqtrade_executable: str = "freqtrade"
    validation_rules_version: str = "1.0"
    timeout_seconds: float = 1800


@dataclass(frozen=True, slots=True)
class CheckEvidence:
    name: str
    command: tuple[str, ...]
    returncode: int | None
    stdout_path: Path
    stderr_path: Path
    error: str | None = None
    evidence_paths: tuple[Path, ...] = ()

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and self.error is None


@dataclass(frozen=True, slots=True)
class ValidationReport:
    candidate_id: str
    dataset_identity: str
    conclusion: Conclusion
    technical_checks_passed: bool
    checks: tuple[CheckEvidence, ...]
    failed_checks: tuple[str, ...]
    blockers: tuple[str, ...]
    evidence_dir: Path
    evidence_path: Path
    report_path: Path
    manifest_path: Path


def run_validation(
    request: ValidationRequest,
    *,
    runner: CommandRunner = subprocess.run,
) -> ValidationReport:
    """Run all required offline checks and write evidence plus a candidate manifest.

    The result stays ``evidence_insufficient`` until a later policy evaluator
    supplies the confirmed statistical and economic thresholds.  A successful
    CLI run is technical evidence, not a profitability or release approval.
    """
    _validate_request(request)
    request.output_dir.mkdir(parents=True, exist_ok=True)
    run_id = f"{request.candidate_id}-{uuid.uuid4().hex}"
    run_root = request.output_dir / "runs" / run_id
    run_root.mkdir(parents=True, exist_ok=False)
    evidence_dir = run_root / "evidence"
    evidence_dir.mkdir()
    userdir = run_root / "freqtrade-userdir"
    userdir.mkdir()

    checks: list[CheckEvidence] = []
    for name, args in _commands(request, userdir, evidence_dir):
        command = (request.freqtrade_executable, *args)
        stdout_path = evidence_dir / f"{name}.stdout.txt"
        stderr_path = evidence_dir / f"{name}.stderr.txt"
        evidence_paths: tuple[Path, ...] = ()
        try:
            result = runner(
                list(command),
                cwd=str(request.repository_root),
                capture_output=True,
                text=True,
                check=False,
                shell=False,
                timeout=request.timeout_seconds,
            )
            stdout = _as_text(result.stdout)
            stderr = _as_text(result.stderr)
            returncode = result.returncode
            error = None
            if returncode == 0:
                evidence_paths, error = _check_required_evidence(
                    name=name,
                    stdout=stdout,
                    stderr=stderr,
                    strategy_name=request.strategy_name,
                    evidence_dir=evidence_dir,
                    userdir=userdir,
                )
        except (OSError, subprocess.SubprocessError) as exc:
            stdout = ""
            stderr = str(exc)
            returncode = None
            error = type(exc).__name__

        stdout_path.write_text(stdout, encoding="utf-8")
        stderr_path.write_text(stderr, encoding="utf-8")
        checks.append(
            CheckEvidence(
                name=name,
                command=command,
                returncode=returncode,
                stdout_path=stdout_path,
                stderr_path=stderr_path,
                evidence_paths=evidence_paths,
                error=error,
            )
        )

    failed_checks = tuple(check.name for check in checks if not check.ok)
    technical_checks_passed = not failed_checks
    blockers = ["validation_policy_thresholds_not_configured", "release_approval_pending"]
    if not technical_checks_passed:
        blockers.insert(0, "technical_check_failed")
    head = _git_head(request.repository_root)
    if head is None:
        head = "0" * 40
        blockers.append("git_identity_unavailable")

    evidence_path = request.output_dir / "evidence.json"
    evidence_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "candidate_id": request.candidate_id,
                "run_id": run_id,
                "dataset_identity": request.dataset_identity,
                "validation_rules_version": request.validation_rules_version,
                "technical_checks_passed": technical_checks_passed,
                "failed_checks": list(failed_checks),
                "checks": [_check_payload(check, request.repository_root) for check in checks],
            },
            ensure_ascii=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    manifest_path = request.output_dir / "release-manifest.toml"
    report_path = request.output_dir / "validation-report.json"
    report_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "candidate_id": request.candidate_id,
                "run_id": run_id,
                "dataset_identity": request.dataset_identity,
                "validation_rules_version": request.validation_rules_version,
                "conclusion": "evidence_insufficient",
                "technical_checks_passed": technical_checks_passed,
                "failed_checks": list(failed_checks),
                "blockers": blockers,
                "evidence_dir": _relative(request.repository_root, evidence_dir),
                "evidence_path": _relative(request.repository_root, evidence_path),
                "evidence_sha256": _sha256(evidence_path),
                "manifest_path": _relative(request.repository_root, manifest_path),
                "checks": [_check_payload(check, request.repository_root) for check in checks],
            },
            ensure_ascii=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    manifest_path.write_text(
        _manifest_text(request, head, evidence_path, report_path),
        encoding="utf-8",
    )

    return ValidationReport(
        candidate_id=request.candidate_id,
        dataset_identity=request.dataset_identity,
        conclusion="evidence_insufficient",
        technical_checks_passed=technical_checks_passed,
        checks=tuple(checks),
        failed_checks=failed_checks,
        blockers=tuple(blockers),
        evidence_dir=evidence_dir,
        evidence_path=evidence_path,
        report_path=report_path,
        manifest_path=manifest_path,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-id", required=True)
    parser.add_argument("--strategy-name", required=True)
    parser.add_argument("--strategy-path", type=Path, required=True)
    parser.add_argument("--config", dest="config_path", type=Path, required=True)
    parser.add_argument("--risk-config", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument("--repository", required=True)
    parser.add_argument("--dataset-identity", required=True)
    parser.add_argument("--timeframe", required=True)
    parser.add_argument("--pair", action="append", required=True)
    parser.add_argument("--development-timerange", required=True)
    parser.add_argument("--holdout-timerange", required=True)
    parser.add_argument("--hyperopt-loss", default="MultiMetricHyperOptLoss")
    parser.add_argument("--hyperopt-epochs", type=int, default=100)
    parser.add_argument("--freqtrade", default="freqtrade")
    parser.add_argument("--rules-version", default="1.0")
    parser.add_argument("--timeout-seconds", type=float, default=1800)
    args = parser.parse_args(argv)

    try:
        report = run_validation(
            ValidationRequest(
                candidate_id=args.candidate_id,
                strategy_name=args.strategy_name,
                strategy_path=args.strategy_path,
                config_path=args.config_path,
                risk_config_path=args.risk_config,
                data_dir=args.data_dir,
                output_dir=args.output_dir,
                repository_root=args.repository_root,
                repository=args.repository,
                dataset_identity=args.dataset_identity,
                timeframe=args.timeframe,
                pairs=tuple(args.pair),
                development_timerange=args.development_timerange,
                holdout_timerange=args.holdout_timerange,
                hyperopt_loss=args.hyperopt_loss,
                hyperopt_epochs=args.hyperopt_epochs,
                freqtrade_executable=args.freqtrade,
                validation_rules_version=args.rules_version,
                timeout_seconds=args.timeout_seconds,
            )
        )
    except (OSError, ValueError) as exc:
        parser.error(str(exc))

    print(
        json.dumps(
            {
                "conclusion": report.conclusion,
                "report_path": str(report.report_path),
                "manifest_path": str(report.manifest_path),
            },
            ensure_ascii=True,
        )
    )
    return {"qualified": 0, "unqualified": 1, "evidence_insufficient": 2}[report.conclusion]


def _commands(
    request: ValidationRequest,
    userdir: Path,
    evidence_dir: Path,
) -> tuple[tuple[str, tuple[str, ...]], ...]:
    load = (
        "list-strategies",
        "--no-color",
        "-c",
        str(request.config_path),
        "--userdir",
        str(userdir),
        "--strategy-path",
        str(request.strategy_path.parent),
        "--one-column",
    )
    common = (
        "--no-color",
        "-c",
        str(request.config_path),
        "-d",
        str(request.data_dir),
        "--userdir",
        str(userdir),
        "-s",
        request.strategy_name,
        "--strategy-path",
        str(request.strategy_path.parent),
        "-i",
        request.timeframe,
        "-p",
        *request.pairs,
    )
    return (
        ("load", load),
        (
            "lookahead",
            (
                "lookahead-analysis",
                *common,
                "--timerange",
                request.development_timerange,
                "--lookahead-analysis-exportfilename",
                str(evidence_dir / "lookahead-analysis.csv"),
            ),
        ),
        (
            "recursive",
            ("recursive-analysis", *common, "--timerange", request.development_timerange),
        ),
        (
            "hyperopt",
            (
                "hyperopt",
                *common,
                "--timerange",
                request.development_timerange,
                "-e",
                str(request.hyperopt_epochs),
                "--hyperopt-loss",
                request.hyperopt_loss,
                "--disable-param-export",
                "-j",
                "1",
                "--print-json",
            ),
        ),
        (
            "backtest_development",
            (
                "backtesting",
                *common,
                "--timerange",
                request.development_timerange,
                "--backtest-directory",
                str(evidence_dir / "backtest_development"),
            ),
        ),
        (
            "backtest_holdout",
            (
                "backtesting",
                *common,
                "--timerange",
                request.holdout_timerange,
                "--backtest-directory",
                str(evidence_dir / "backtest_holdout"),
            ),
        ),
    )


def _validate_request(request: ValidationRequest) -> None:
    if not request.candidate_id or "/" in request.candidate_id or "\\" in request.candidate_id:
        raise ValueError("candidate_id must be a non-empty single path component")
    if not request.strategy_name or not request.repository or not request.dataset_identity:
        raise ValueError("strategy_name, repository, and dataset_identity are required")
    if not request.pairs:
        raise ValueError("at least one pair is required")
    if request.hyperopt_epochs < 1:
        raise ValueError("hyperopt_epochs must be positive")
    if request.timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")

    root = request.repository_root.resolve()
    for path, label in (
        (request.strategy_path, "strategy_path"),
        (request.config_path, "config_path"),
        (request.risk_config_path, "risk_config_path"),
    ):
        if not path.is_file():
            raise FileNotFoundError(f"{label} does not exist: {path}")
        _relative(root, path)
    if not request.data_dir.is_dir():
        raise FileNotFoundError(f"data_dir does not exist: {request.data_dir}")
    output = request.output_dir.resolve()
    if output == root:
        raise ValueError("output_dir must be below repository_root")
    _relative(root, output)


def _check_payload(check: CheckEvidence, root: Path) -> dict[str, object]:
    return {
        "name": check.name,
        "command": list(check.command),
        "returncode": check.returncode,
        "ok": check.ok,
        "error": check.error,
        "stdout_path": _relative(root, check.stdout_path),
        "stderr_path": _relative(root, check.stderr_path),
        "evidence_paths": [_relative(root, path) for path in check.evidence_paths],
    }


def _strategy_loaded(stdout: str, strategy_name: str) -> bool:
    return any(line.strip() == strategy_name for line in stdout.splitlines())


def _check_required_evidence(
    *,
    name: str,
    stdout: str,
    stderr: str,
    strategy_name: str,
    evidence_dir: Path,
    userdir: Path,
) -> tuple[tuple[Path, ...], str | None]:
    if name == "load":
        return (
            (),
            None if _strategy_loaded(stdout, strategy_name) else "strategy_not_loaded",
        )
    if name == "lookahead":
        path = evidence_dir / "lookahead-analysis.csv"
        return ((path,), None if _has_content(path) else "evidence_missing")
    if name == "recursive":
        markers = (
            "Start checking for recursive bias",
            "No variance on indicator(s) found due to recursive formula.",
        )
        output = f"{stdout}\n{stderr}"
        return (
            (),
            None if any(marker in output for marker in markers) else "evidence_missing",
        )
    if name == "hyperopt":
        paths = _non_empty_files(userdir / "hyperopt_results", "*.fthypt")
        return (paths, None if paths else "evidence_missing")
    if name in {"backtest_development", "backtest_holdout"}:
        paths = _non_empty_files(evidence_dir / name, "*.json")
        return (paths, None if paths else "evidence_missing")
    return (), "evidence_missing"


def _has_content(path: Path) -> bool:
    try:
        return path.is_file() and path.stat().st_size > 0
    except OSError:
        return False


def _non_empty_files(directory: Path, pattern: str) -> tuple[Path, ...]:
    try:
        return tuple(path for path in sorted(directory.glob(pattern)) if _has_content(path))
    except OSError:
        return ()


def _manifest_text(
    request: ValidationRequest,
    head: str,
    evidence_path: Path,
    report_path: Path,
) -> str:
    root = request.repository_root.resolve()
    lines = [
        "# Candidate evidence manifest only; approval_pr_number=0 is intentional.",
        "# This file does not authorize Dry-run or live execution.",
        "schema_version = 1",
        f"release_id = {_toml_string(request.candidate_id)}",
        'execution_mode = "dry-run"',
        f'approved_commit_sha = "{head}"',
        f"release_tag = {_toml_string(request.candidate_id)}",
        f"repository = {_toml_string(request.repository)}",
        "approval_pr_number = 0",
        'approval_label = "release-approved"',
        "",
        "[artifacts.strategy]",
        f"path = {_toml_string(_relative(root, request.strategy_path))}",
        f'sha256 = "{_sha256(request.strategy_path)}"',
        "",
        "[artifacts.runtime_config]",
        f"path = {_toml_string(_relative(root, request.config_path))}",
        f'sha256 = "{_sha256(request.config_path)}"',
        "",
        "[artifacts.risk_config]",
        f"path = {_toml_string(_relative(root, request.risk_config_path))}",
        f'sha256 = "{_sha256(request.risk_config_path)}"',
        "",
        "[artifacts.evidence_bundle]",
        f"path = {_toml_string(_relative(root, evidence_path))}",
        f'sha256 = "{_sha256(evidence_path)}"',
        "",
        "[artifacts.validation_report]",
        f"path = {_toml_string(_relative(root, report_path))}",
        f'sha256 = "{_sha256(report_path)}"',
        "",
    ]
    return "\n".join(lines)


def _git_head(root: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            shell=False,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    head = result.stdout.strip().lower()
    return head if len(head) == 40 and all(char in "0123456789abcdef" for char in head) else None


def _relative(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise ValueError(f"path must stay below repository_root: {path}") from exc


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _toml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=True)


def _as_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


if __name__ == "__main__":
    raise SystemExit(main())
