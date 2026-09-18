import hashlib
import json
import subprocess
from pathlib import Path

from quant_lab.release import load_manifest
from quant_lab.validation import ValidationRequest, run_validation


def _request(tmp_path: Path) -> ValidationRequest:
    root = tmp_path / "repo"
    strategy_path = root / "strategies" / "Candidate.py"
    config_path = root / "config" / "freqtrade.json"
    risk_config_path = root / "config" / "risk.toml"
    data_dir = root / "data"
    output_dir = root / "artifacts" / "validation" / "candidate-v0.1.0"

    strategy_path.parent.mkdir(parents=True)
    config_path.parent.mkdir(parents=True)
    data_dir.mkdir(parents=True)
    output_dir.mkdir(parents=True)
    strategy_path.write_text("class Candidate: pass\n", encoding="utf-8")
    config_path.write_text('{"dry_run": true}\n', encoding="utf-8")
    risk_config_path.write_text('max_leverage = "1"\n', encoding="utf-8")

    return ValidationRequest(
        candidate_id="candidate-v0.1.0",
        strategy_name="Candidate",
        strategy_path=strategy_path,
        config_path=config_path,
        risk_config_path=risk_config_path,
        data_dir=data_dir,
        output_dir=output_dir,
        repository_root=root,
        repository="JunYIChen12/quant-research-live-lab",
        dataset_identity="fixture-dataset-v1",
        timeframe="5m",
        pairs=("BTC/USDT:USDT",),
        development_timerange="20250101-20250301",
        holdout_timerange="20250302-20250501",
        hyperopt_loss="MultiMetricHyperOptLoss",
        hyperopt_epochs=3,
        freqtrade_executable="freqtrade",
    )


def _successful_runner(
    argv: list[str],
    *,
    strategy_output: str = "Candidate\n",
) -> subprocess.CompletedProcess[str]:
    command = argv[1]
    if command == "list-strategies":
        return subprocess.CompletedProcess(argv, 0, stdout=strategy_output, stderr="")
    if command == "lookahead-analysis":
        path = Path(argv[argv.index("--lookahead-analysis-exportfilename") + 1])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("pair,lookahead\nBTC/USDT:USDT,0\n", encoding="utf-8")
        return subprocess.CompletedProcess(argv, 0, stdout="lookahead complete\n", stderr="")
    if command == "recursive-analysis":
        return subprocess.CompletedProcess(
            argv,
            0,
            stdout="Start checking for recursive bias\n",
            stderr="",
        )
    if command == "hyperopt":
        userdir = Path(argv[argv.index("--userdir") + 1])
        results = userdir / "hyperopt_results" / "strategy_Candidate.fthypt"
        results.parent.mkdir(parents=True, exist_ok=True)
        results.write_text('{"epoch": 1}\n', encoding="utf-8")
        return subprocess.CompletedProcess(argv, 0, stdout='{"best": true}\n', stderr="")
    if command == "backtesting":
        output_dir = Path(argv[argv.index("--backtest-directory") + 1])
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "backtest-result.json").write_text('{"results": []}\n', encoding="utf-8")
        return subprocess.CompletedProcess(argv, 0, stdout="backtest complete\n", stderr="")
    raise AssertionError(f"unexpected command: {command}")


def test_validation_records_all_checks_and_freezes_artifacts(tmp_path: Path) -> None:
    request = _request(tmp_path)
    calls: list[tuple[list[str], dict[str, object]]] = []

    def runner(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append((argv, kwargs))
        return _successful_runner(argv)

    report = run_validation(request, runner=runner)

    assert report.conclusion == "evidence_insufficient"
    assert [check.name for check in report.checks] == [
        "load",
        "lookahead",
        "recursive",
        "hyperopt",
        "backtest_development",
        "backtest_holdout",
    ]
    assert len(calls) == 6
    assert all(call[1]["check"] is False for call in calls)
    assert all(call[1]["shell"] is False for call in calls)
    assert all("--userdir" in call[0] for call in calls)
    hyperopt_command = calls[3][0]
    assert "--disable-param-export" in hyperopt_command
    assert "--print-json" in hyperopt_command
    assert hyperopt_command[hyperopt_command.index("-e") + 1] == "3"
    assert all(check.stdout_path.is_file() for check in report.checks)
    assert all(check.stderr_path.is_file() for check in report.checks)

    payload = json.loads(report.report_path.read_text(encoding="utf-8"))
    assert payload["conclusion"] == "evidence_insufficient"
    assert payload["candidate_id"] == "candidate-v0.1.0"
    assert payload["dataset_identity"] == "fixture-dataset-v1"
    assert payload["evidence_sha256"] == hashlib.sha256(
        report.evidence_path.read_bytes()
    ).hexdigest()
    assert payload["technical_checks_passed"] is True

    manifest = load_manifest(report.manifest_path)
    assert manifest.release_id == "candidate-v0.1.0"
    assert manifest.approval_pr_number == 0
    assert manifest.strategy.path == "strategies/Candidate.py"
    assert manifest.runtime_config is not None
    assert manifest.runtime_config.path == "config/freqtrade.json"
    assert manifest.evidence_bundle.path.endswith("evidence.json")


def test_validation_binds_report_in_manifest(tmp_path: Path) -> None:
    request = _request(tmp_path)

    def runner(argv: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        return _successful_runner(argv)

    report = run_validation(request, runner=runner)

    manifest = load_manifest(report.manifest_path)
    assert manifest.validation_report is not None
    assert manifest.validation_report.path == (
        "artifacts/validation/candidate-v0.1.0/validation-report.json"
    )
    assert manifest.validation_report.sha256 == hashlib.sha256(
        report.report_path.read_bytes()
    ).hexdigest()


def test_zero_exit_with_empty_required_evidence_fails_closed(tmp_path: Path) -> None:
    request = _request(tmp_path)

    def runner(argv: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        stdout = "Candidate\n" if argv[1] == "list-strategies" else ""
        return subprocess.CompletedProcess(argv, 0, stdout=stdout, stderr="")

    report = run_validation(request, runner=runner)

    assert report.technical_checks_passed is False
    assert report.failed_checks
    assert set(report.failed_checks) == {
        "lookahead",
        "recursive",
        "hyperopt",
        "backtest_development",
        "backtest_holdout",
    }


def test_preexisting_evidence_is_not_accepted_as_current_run_output(tmp_path: Path) -> None:
    request = _request(tmp_path)
    old_evidence = request.output_dir / "evidence"
    old_evidence.mkdir(parents=True, exist_ok=True)
    (old_evidence / "lookahead-analysis.csv").write_text("old\n", encoding="utf-8")
    for name in ("backtest_development", "backtest_holdout"):
        directory = old_evidence / name
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "old-result.json").write_text('{"old": true}\n', encoding="utf-8")
    old_hyperopt = request.output_dir / "freqtrade-userdir" / "hyperopt_results"
    old_hyperopt.mkdir(parents=True, exist_ok=True)
    (old_hyperopt / "old-result.fthypt").write_text('{"old": true}\n', encoding="utf-8")

    def runner(argv: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        if argv[1] == "list-strategies":
            return subprocess.CompletedProcess(argv, 0, stdout="Candidate\n", stderr="")
        if argv[1] == "recursive-analysis":
            return subprocess.CompletedProcess(
                argv,
                0,
                stdout="Start checking for recursive bias\n",
                stderr="",
            )
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    report = run_validation(request, runner=runner)

    assert report.technical_checks_passed is False
    assert set(report.failed_checks) == {
        "lookahead",
        "hyperopt",
        "backtest_development",
        "backtest_holdout",
    }


def test_validation_keeps_failure_evidence_and_does_not_claim_qualification(
    tmp_path: Path,
) -> None:
    request = _request(tmp_path)

    def runner(argv: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        if argv[1] == "lookahead-analysis":
            return subprocess.CompletedProcess(argv, 2, stdout="", stderr="bias found\n")
        return _successful_runner(argv)

    report = run_validation(request, runner=runner)

    assert report.conclusion == "evidence_insufficient"
    failed = report.checks[1]
    assert failed.returncode == 2
    assert failed.ok is False
    assert failed.stderr_path.read_text(encoding="utf-8") == "bias found\n"
    payload = json.loads(report.report_path.read_text(encoding="utf-8"))
    assert payload["technical_checks_passed"] is False
    assert "lookahead" in payload["failed_checks"]


def test_validation_rejects_successful_load_without_the_requested_strategy(
    tmp_path: Path,
) -> None:
    request = _request(tmp_path)

    def runner(argv: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        return _successful_runner(argv, strategy_output="OtherStrategy\n")

    report = run_validation(request, runner=runner)

    assert report.conclusion == "evidence_insufficient"
    assert report.checks[0].returncode == 0
    assert report.checks[0].ok is False
    assert report.checks[0].error == "strategy_not_loaded"
    assert report.failed_checks == ("load",)
