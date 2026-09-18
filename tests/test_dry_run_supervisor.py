from __future__ import annotations

import json
import threading
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from quant_lab.dry_run import (
    CLOSING_RECONCILIATION_SECONDS,
    GET_BACKOFF_SECONDS,
    GET_MAX_RETRIES,
    REQUEST_TIMEOUT_SECONDS,
    STARTUP_CONFIRMATION_SECONDS,
    DryRunSupervisor,
    FreqtradeRestClient,
    FreqtradeSnapshot,
    RestError,
    RiskConfig,
    RoundInputs,
    RoundState,
    SQLiteStateStore,
    StateConflict,
    create_web_server,
)
from quant_lab.release import ReleaseVerification


class FakeClock:
    def __init__(self) -> None:
        self.value = datetime(2026, 9, 17, 8, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.value

    def advance(self, seconds: int) -> None:
        self.value += timedelta(seconds=seconds)


class FakeFreqtrade(FreqtradeRestClient):
    def __init__(self, snapshot: FreqtradeSnapshot) -> None:
        self.current = snapshot
        self.calls: list[str] = []
        super().__init__(
            "http://127.0.0.1:8080",
            "runtime-user",
            "runtime-password",
            opener=self._pseudo_opener,
        )

    def _pseudo_opener(self, request, *, timeout):
        assert timeout == REQUEST_TIMEOUT_SECONDS
        path = urllib.parse.urlsplit(request.full_url).path
        if request.method == "POST":
            if path == "/api/v1/start":
                self.calls.append("start")
                payload = {"status": "starting trader ..."}
            elif path == "/api/v1/pause":
                self.calls.append("pause")
                payload = {"status": "paused"}
            elif path == "/api/v1/forceexit":
                self.calls.append("forceexit")
                payload = {"result": "Created exit orders for all open trades."}
            else:
                return self._response(404, {"error": "not found"})
            return self._response(200, payload)
        if path == "/api/v1/health":
            return self._response(200, self.current.health)
        if path == "/api/v1/show_config":
            return self._response(200, self.current.config)
        if path == "/api/v1/status":
            return self._response(200, list(self.current.open_trades))
        if path == "/api/v1/trades":
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(request.full_url).query)
            offset = int(query.get("offset", ["0"])[0])
            page = self.current.closed_trades[offset : offset + 500]
            return self._response(
                200,
                {"trades": list(page), "total_trades": len(self.current.closed_trades)},
            )
        if path == "/api/v1/balance":
            return self._response(200, {"total_bot": str(self.current.balance)})
        return self._response(404, {"error": "not found"})

    @staticmethod
    def _response(status: int, payload: object):
        class Response:
            def __init__(self, response_status: int, response_payload: object) -> None:
                self.status = response_status
                self.body = json.dumps(response_payload).encode()

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self) -> bytes:
                return self.body

        return Response(status, payload)

    def snapshot(self) -> FreqtradeSnapshot:
        self.calls.append("snapshot")
        parsed = super().snapshot()
        return FreqtradeSnapshot(
            health=parsed.health,
            config=parsed.config,
            open_trades=parsed.open_trades,
            closed_trades=parsed.closed_trades,
            balance=parsed.balance,
            observed_at=parsed.observed_at,
            market_data_reliable=self.current.market_data_reliable,
            qualifying_strategy=self.current.qualifying_strategy,
        )


class StartTimeoutFreqtrade(FakeFreqtrade):
    def _pseudo_opener(self, request, *, timeout):
        path = urllib.parse.urlsplit(request.full_url).path
        if request.method == "POST" and path == "/api/v1/start":
            self.calls.append("start")
            raise TimeoutError("start response timed out")
        return super()._pseudo_opener(request, timeout=timeout)


class StartTimeoutUnreadableFreqtrade(FakeFreqtrade):
    def __init__(self, snapshot: FreqtradeSnapshot) -> None:
        self.readback_unavailable = False
        super().__init__(snapshot)

    def _pseudo_opener(self, request, *, timeout):
        path = urllib.parse.urlsplit(request.full_url).path
        if self.readback_unavailable and request.method == "GET":
            raise TimeoutError("startup readback unavailable")
        if request.method == "POST" and path == "/api/v1/start":
            self.calls.append("start")
            self.readback_unavailable = True
            raise TimeoutError("start response timed out")
        return super()._pseudo_opener(request, timeout=timeout)


def inputs(*, duration_minutes: int = 120) -> RoundInputs:
    return RoundInputs.from_strings(
        capital="1000",
        target_profit="100",
        duration_minutes=str(duration_minutes),
        max_loss="200",
        stake_currency="USDT",
        dry_run_wallet="1000",
    )


def snapshot(
    clock: FakeClock,
    *,
    open_trades: tuple[dict[str, object], ...] = (),
    closed_trades: tuple[dict[str, object], ...] = (),
    balance: str = "1000",
    market_data_reliable: bool = True,
    qualifying_strategy: bool = True,
    config: dict[str, object] | None = None,
) -> FreqtradeSnapshot:
    runtime = {
        "dry_run": True,
        "dry_run_wallet": "1000",
        "stake_currency": "USDT",
        "max_open_trades": 1,
        "strategy": "FrozenStrategy",
        "trading_mode": "futures",
        "margin_mode": "isolated",
        "leverage": 1,
    }
    if config:
        runtime.update(config)
    return FreqtradeSnapshot(
        health={"last_process": clock().timestamp()},
        config=runtime,
        open_trades=open_trades,
        closed_trades=closed_trades,
        balance=Decimal(balance),
        observed_at=clock(),
        market_data_reliable=market_data_reliable,
        qualifying_strategy=qualifying_strategy,
    )


def open_trade(
    clock: FakeClock, *, profit: str = "0", with_exit_order: bool = False
) -> dict[str, object]:
    return {
        "trade_id": 1,
        "is_open": True,
        "amount": "1",
        "current_rate": "1000",
        "profit_abs": profit,
        "open_fill_timestamp": int(clock().timestamp()),
        "orders": [
            {
                "is_open": with_exit_order,
                "ft_order_side": "sell" if with_exit_order else "buy",
                "ft_is_entry": not with_exit_order,
            }
        ],
    }


def closed_trade(clock: FakeClock, profit: str) -> dict[str, object]:
    return {
        "trade_id": 1,
        "is_open": False,
        "profit_abs": profit,
        "close_profit_abs": profit,
        "open_fill_timestamp": int(clock().timestamp()),
        "open_timestamp": int(clock().timestamp()),
    }


def supervisor(
    tmp_path: Path,
    clock: FakeClock,
    client: FakeFreqtrade,
    *,
    release: ReleaseVerification | None = None,
    duration_minutes: int = 120,
) -> DryRunSupervisor:
    store = SQLiteStateStore(tmp_path / "supervision.sqlite3")
    return DryRunSupervisor(
        store,
        client,
        release_check=lambda: (
            release or ReleaseVerification(True, (), "candidate-v1.0.0", "a" * 40)
        ),
        runtime_config={
            "dry_run": True,
            "dry_run_wallet": "1000",
            "stake_currency": "USDT",
            "max_open_trades": 1,
            "strategy": "FrozenStrategy",
            "trading_mode": "futures",
            "margin_mode": "isolated",
        },
        risk_config=RiskConfig.from_mapping({"exit_cost_buffer_bps": "10"}),
        clock=clock,
    )


def start_running(sut: DryRunSupervisor, round_inputs: RoundInputs) -> str:
    record = sut.create_round(
        round_inputs, release_id="candidate-v1.0.0", approved_commit_sha="a" * 40
    )
    assert record.state is RoundState.APPROVAL_PENDING
    assert sut.approve_and_start(record.round_id).state is RoundState.RUNNING
    return record.round_id


def test_round_inputs_are_exact_decimal_and_match_dry_run_wallet() -> None:
    parsed = inputs()
    assert parsed.capital == Decimal("1000")
    assert parsed.duration_seconds == 7200

    with pytest.raises(ValueError):
        RoundInputs.from_strings(
            capital="1e3",
            target_profit="100",
            duration_minutes="120",
            max_loss="200",
            stake_currency="USDT",
            dry_run_wallet="1000",
        )
    with pytest.raises(ValueError):
        RoundInputs.from_strings(
            capital="1000",
            target_profit="100",
            duration_minutes="120",
            max_loss="200",
            stake_currency="USDT",
            dry_run_wallet="999.99",
        )


def test_risk_config_missing_or_negative_exit_buffer_fails_closed() -> None:
    with pytest.raises(ValueError):
        RiskConfig.from_mapping({})
    with pytest.raises(ValueError):
        RiskConfig.from_mapping({"exit_cost_buffer_bps": "-1"})


def test_rest_client_uses_runtime_credentials_and_fixed_get_budget(monkeypatch) -> None:
    monkeypatch.setenv("FREQTRADE_API_URL", "http://127.0.0.1:8080")
    monkeypatch.setenv("FREQTRADE_API_USERNAME", "runtime-user")
    monkeypatch.setenv("FREQTRADE_API_PASSWORD", "runtime-password")
    attempts = 0
    delays: list[float] = []
    requests: list[tuple[str, float]] = []

    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self) -> bytes:
            return b'{"status":"pong"}'

    def opener(request, *, timeout):
        nonlocal attempts
        attempts += 1
        requests.append((request.full_url, timeout))
        if attempts <= GET_MAX_RETRIES:
            raise urllib.error.URLError("temporary")
        return Response()

    client = FreqtradeRestClient.from_environment(opener=opener, sleeper=delays.append)
    assert client.get("/api/v1/ping") == {"status": "pong"}
    assert attempts == GET_MAX_RETRIES + 1
    assert delays == list(GET_BACKOFF_SECONDS)
    assert all(timeout == REQUEST_TIMEOUT_SECONDS for _, timeout in requests)
    assert "runtime-password" not in repr(client)


def test_rest_response_audit_sink_records_each_http_response(tmp_path: Path) -> None:
    store = SQLiteStateStore(tmp_path / "audit.sqlite3")
    client_config = {
        "dry_run": True,
        "dry_run_wallet": "1000",
        "stake_currency": "USDT",
        "max_open_trades": 1,
    }
    responses = [
        (200, b'{"status":"pong"}'),
        (503, b'{"error":"unavailable"}'),
    ]

    class Response:
        def __init__(self, status: int, body: bytes) -> None:
            self.status = status
            self.body = body

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self) -> bytes:
            return self.body

    def opener(_request, *, timeout):
        assert timeout == REQUEST_TIMEOUT_SECONDS
        status, body = responses.pop(0)
        return Response(status, body)

    client = FreqtradeRestClient(
        "http://127.0.0.1:8080",
        "runtime-user",
        "runtime-password",
        opener=opener,
        max_get_retries=0,
    )
    supervisor = DryRunSupervisor(
        store,
        client,
        release_check=lambda: ReleaseVerification(True, (), "candidate-v1.0.0", "a" * 40),
        runtime_config=client_config,
        risk_config=RiskConfig.from_mapping({"exit_cost_buffer_bps": "10"}),
    )
    record = supervisor.create_round(
        inputs(), release_id="candidate-v1.0.0", approved_commit_sha="a" * 40
    )
    assert supervisor.get_round(record.round_id).state is RoundState.APPROVAL_PENDING

    assert client.get("/api/v1/health") == {"status": "pong"}
    with pytest.raises(RestError):
        client.get("/api/v1/status")

    rows = store.connection.execute(
        "SELECT endpoint, status_code, summary_sha256 FROM observations "
        "WHERE round_id = ? ORDER BY observation_id",
        (record.round_id,),
    ).fetchall()
    assert [(row[0], row[1]) for row in rows] == [
        ("/api/v1/health", 200),
        ("/api/v1/status", 503),
    ]
    assert all(len(row[2]) == 64 for row in rows)


def test_start_rejects_unverified_release_without_calling_freqtrade(tmp_path: Path) -> None:
    clock = FakeClock()
    client = FakeFreqtrade(snapshot(clock))
    sut = supervisor(
        tmp_path,
        clock,
        client,
        release=ReleaseVerification(False, ("validation_report_hash_mismatch",)),
    )
    record = sut.create_round(inputs(), release_id="candidate-v1.0.0", approved_commit_sha="a" * 40)

    result = sut.approve_and_start(record.round_id)

    assert result.state is RoundState.BLOCKED
    assert "validation_report_hash_mismatch" in result.stop_reason
    assert "start" not in client.calls


def test_effective_leverage_must_be_one_even_without_runtime_expectation(tmp_path: Path) -> None:
    clock = FakeClock()
    client = FakeFreqtrade(snapshot(clock, config={"leverage": 2}))
    sut = supervisor(tmp_path, clock, client)
    record = sut.create_round(inputs(), release_id="candidate-v1.0.0", approved_commit_sha="a" * 40)

    result = sut.approve_and_start(record.round_id)

    assert result.state is RoundState.BLOCKED
    assert "leverage_must_be_one" in (result.stop_reason or "")
    assert "start" not in client.calls


def test_uncertain_start_is_reconciled_before_any_block(tmp_path: Path) -> None:
    clock = FakeClock()
    client = StartTimeoutFreqtrade(snapshot(clock))
    sut = supervisor(tmp_path, clock, client)
    record = sut.create_round(inputs(), release_id="candidate-v1.0.0", approved_commit_sha="a" * 40)

    result = sut.approve_and_start(record.round_id)

    assert result.state is RoundState.RUNNING
    assert result.terminal is False
    assert client.calls.count("start") == 1
    assert client.calls.count("snapshot") >= 2


def test_uncertain_start_waits_for_startup_deadline_when_readback_fails(tmp_path: Path) -> None:
    clock = FakeClock()
    client = StartTimeoutUnreadableFreqtrade(snapshot(clock))
    sut = supervisor(tmp_path, clock, client)
    record = sut.create_round(inputs(), release_id="candidate-v1.0.0", approved_commit_sha="a" * 40)

    pending = sut.approve_and_start(record.round_id)
    assert pending.state is RoundState.STARTING
    assert pending.terminal is False

    clock.advance(STARTUP_CONFIRMATION_SECONDS - 1)
    assert sut.tick(record.round_id).state is RoundState.STARTING

    clock.advance(1)
    blocked = sut.tick(record.round_id)
    assert blocked.state is RoundState.BLOCKED
    assert "startup_confirmation_timeout" in (blocked.stop_reason or "")


def test_release_integrity_failure_wins_over_existing_loss_lock(tmp_path: Path) -> None:
    clock = FakeClock()
    client = FakeFreqtrade(snapshot(clock))
    releases = [ReleaseVerification(True, (), "candidate-v1.0.0", "a" * 40)]
    sut = supervisor(tmp_path, clock, client, release=releases[0])
    sut.release_check = lambda: releases[0]
    round_id = start_running(sut, inputs())

    client.current = snapshot(clock, open_trades=(open_trade(clock, profit="-200"),))
    closing = sut.tick(round_id)
    assert closing.state is RoundState.CLOSING
    assert closing.loss_lock is True

    releases[0] = ReleaseVerification(
        False,
        ("artifact_hash_mismatch",),
        "candidate-v1.0.0",
        "a" * 40,
    )
    client.current = snapshot(
        clock,
        closed_trades=(closed_trade(clock, "-200"),),
        balance="800",
    )

    result = sut.tick(round_id)

    assert result.state is RoundState.BLOCKED
    assert result.loss_lock is True
    assert "release_integrity" in (result.stop_reason or "")
    assert "artifact_hash_mismatch" in (result.stop_reason or "")


def test_frozen_release_drift_blocks_without_a_second_start(tmp_path: Path) -> None:
    clock = FakeClock()
    client = FakeFreqtrade(snapshot(clock))
    sut = supervisor(tmp_path, clock, client)
    releases = [ReleaseVerification(True, (), "candidate-v1.0.0", "a" * 40)]
    sut.release_check = lambda: releases[0]
    round_id = start_running(sut, inputs())

    releases[0] = ReleaseVerification(
        False,
        ("artifact_hash_mismatch",),
        "candidate-v1.0.0",
        "a" * 40,
    )
    result = sut.tick(round_id)

    assert result.state is RoundState.BLOCKED
    assert "artifact_hash_mismatch" in (result.stop_reason or "")
    assert client.calls.count("start") == 1


def test_estimated_target_that_settles_below_target_resumes_same_round(tmp_path: Path) -> None:
    clock = FakeClock()
    client = FakeFreqtrade(snapshot(clock))
    sut = supervisor(tmp_path, clock, client)
    round_id = start_running(sut, inputs())
    client.current = snapshot(clock, open_trades=(open_trade(clock, profit="105"),))

    closing = sut.tick()
    assert closing.state is RoundState.CLOSING
    assert client.calls.count("forceexit") == 1

    clock.advance(2)
    client.current = snapshot(
        clock,
        closed_trades=(closed_trade(clock, "98"),),
        balance="1098",
    )
    resumed = sut.tick()

    assert resumed.state is RoundState.RUNNING
    assert resumed.round_id == round_id
    assert resumed.elapsed_seconds > 0
    assert resumed.last_realized_net == Decimal("98")
    assert client.calls.count("forceexit") == 1


def test_normal_target_finishes_only_after_empty_status_and_orders(tmp_path: Path) -> None:
    clock = FakeClock()
    client = FakeFreqtrade(snapshot(clock))
    sut = supervisor(tmp_path, clock, client)
    round_id = start_running(sut, inputs())
    client.current = snapshot(clock, open_trades=(open_trade(clock, profit="105"),))
    assert sut.tick().state is RoundState.CLOSING

    client.current = snapshot(clock, closed_trades=(closed_trade(clock, "103"),), balance="1103")
    result = sut.tick()

    assert result.state is RoundState.COMPLETED_TARGET
    assert result.round_id == round_id
    assert result.loss_lock is False
    assert result.pending_action_id is None


def test_timeout_wins_over_same_snapshot_entry_signal(tmp_path: Path) -> None:
    clock = FakeClock()
    client = FakeFreqtrade(snapshot(clock))
    sut = supervisor(tmp_path, clock, client)
    start_running(sut, inputs(duration_minutes=1))
    client.current = snapshot(clock, open_trades=(open_trade(clock),))
    sut.tick()
    clock.advance(60)

    result = sut.tick()

    assert result.state is RoundState.CLOSING
    assert result.stop_reason == "timeout"
    assert "forceentry" not in client.calls


def test_loss_lock_is_persistent_across_restart(tmp_path: Path) -> None:
    clock = FakeClock()
    client = FakeFreqtrade(snapshot(clock))
    sut = supervisor(tmp_path, clock, client)
    round_id = start_running(sut, inputs())
    client.current = snapshot(clock, open_trades=(open_trade(clock, profit="-200"),))
    assert sut.tick().state is RoundState.CLOSING

    client.current = snapshot(clock, closed_trades=(closed_trade(clock, "-200"),), balance="800")
    result = sut.tick()
    assert result.state is RoundState.STOPPED_LOSS_LOCK
    assert result.loss_lock is True

    restarted = DryRunSupervisor(
        sut.store,
        client,
        release_check=sut.release_check,
        runtime_config=sut.runtime_config,
        risk_config=sut.risk_config,
        clock=clock,
    )
    recovered = restarted.recover(round_id)
    assert recovered.state is RoundState.STOPPED_LOSS_LOCK
    assert recovered.loss_lock is True
    assert client.calls.count("start") == 1


def test_partial_close_recovery_does_not_repeat_existing_exit_order(tmp_path: Path) -> None:
    clock = FakeClock()
    client = FakeFreqtrade(snapshot(clock))
    sut = supervisor(tmp_path, clock, client)
    round_id = start_running(sut, inputs())
    client.current = snapshot(clock, open_trades=(open_trade(clock, profit="-10"),))
    assert sut.request_stop(round_id).state is RoundState.CLOSING
    assert client.calls.count("forceexit") == 1

    client.current = snapshot(clock, open_trades=(open_trade(clock, with_exit_order=True),))
    restarted = DryRunSupervisor(
        sut.store,
        client,
        release_check=sut.release_check,
        runtime_config=sut.runtime_config,
        risk_config=sut.risk_config,
        clock=clock,
    )
    assert restarted.recover(round_id).state in {RoundState.CLOSING, RoundState.RECONCILING}
    assert client.calls.count("forceexit") == 1

    client.current = snapshot(clock, closed_trades=(closed_trade(clock, "-10"),), balance="990")
    assert restarted.tick().state is RoundState.STOPPED_USER


def test_user_stop_does_not_chase_unmet_target(tmp_path: Path) -> None:
    clock = FakeClock()
    client = FakeFreqtrade(snapshot(clock))
    sut = supervisor(tmp_path, clock, client)
    round_id = start_running(sut, inputs())
    client.current = snapshot(clock, open_trades=(open_trade(clock, profit="10"),))
    assert sut.request_stop(round_id).state is RoundState.CLOSING
    client.current = snapshot(clock, closed_trades=(closed_trade(clock, "10"),), balance="1010")

    result = sut.tick()

    assert result.state is RoundState.STOPPED_USER
    assert result.stop_reason == "user_stop"


def test_balance_conflict_fails_closed_during_reconciliation(tmp_path: Path) -> None:
    clock = FakeClock()
    client = FakeFreqtrade(snapshot(clock))
    sut = supervisor(tmp_path, clock, client)
    round_id = start_running(sut, inputs())
    client.current = snapshot(clock, open_trades=(open_trade(clock, profit="10"),))
    assert sut.request_stop(round_id).state is RoundState.CLOSING

    client.current = snapshot(clock, closed_trades=(closed_trade(clock, "10"),))
    result = sut.tick()

    assert result.state is RoundState.BLOCKED
    assert result.stop_reason == "reconciliation_error:balance_trade_conflict"


def test_codex_unavailable_only_records_research_event(tmp_path: Path) -> None:
    clock = FakeClock()
    client = FakeFreqtrade(snapshot(clock))
    sut = supervisor(tmp_path, clock, client)
    round_id = start_running(sut, inputs())

    before = sut.get_round(round_id)
    sut.record_research_unavailable(round_id, "quota_exhausted")
    after = sut.get_round(round_id)

    assert after.state is before.state is RoundState.RUNNING
    assert after.loss_lock is before.loss_lock is False
    assert sut.store.events(round_id)[-1]["reason"] == "codex_unavailable"


def test_running_parameters_can_be_changed_once_atomically(tmp_path: Path) -> None:
    clock = FakeClock()
    client = FakeFreqtrade(snapshot(clock))
    sut = supervisor(tmp_path, clock, client)
    round_id = start_running(sut, inputs())

    result = sut.update_parameters(
        round_id,
        target_profit="120",
        duration_minutes="90",
        snapshot=snapshot(clock),
    )

    assert result.state is RoundState.RUNNING
    assert result.target_profit == Decimal("120")
    assert result.duration_seconds == 5400
    with pytest.raises(StateConflict):
        sut.update_parameters(
            round_id,
            target_profit="130",
            duration_minutes="80",
            snapshot=snapshot(clock),
        )


def test_reauthorization_creates_new_round_after_terminal_state(tmp_path: Path) -> None:
    clock = FakeClock()
    client = FakeFreqtrade(snapshot(clock))
    sut = supervisor(tmp_path, clock, client)
    old_id = start_running(sut, inputs())
    client.current = snapshot(clock, open_trades=(open_trade(clock, profit="105"),))
    sut.tick()
    client.current = snapshot(clock, closed_trades=(closed_trade(clock, "103"),), balance="1103")
    assert sut.tick().state is RoundState.COMPLETED_TARGET

    new_record = sut.reauthorize(
        inputs(), release_id="candidate-v2.0.0", approved_commit_sha="b" * 40
    )

    assert new_record.round_id != old_id
    assert new_record.state is RoundState.APPROVAL_PENDING
    assert sut.get_round(old_id).state is RoundState.COMPLETED_TARGET


def test_web_is_single_page_loopback_and_never_returns_credentials(tmp_path: Path) -> None:
    clock = FakeClock()
    client = FakeFreqtrade(snapshot(clock))
    sut = supervisor(tmp_path, clock, client)
    server = create_web_server(sut, host="127.0.0.1", port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_address[1]}"
        page = urllib.request.urlopen(base + "/", timeout=2).read().decode()
        assert "模拟本金" in page
        assert "目标净盈利" in page
        assert 'aria-live="polite"' in page

        response = urllib.request.urlopen(base + "/api/state", timeout=2)
        state = json.loads(response.read())
        assert state["state"] is None
        assert "runtime-password" not in json.dumps(state)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_state_store_does_not_have_trade_or_credential_columns(tmp_path: Path) -> None:
    store = SQLiteStateStore(tmp_path / "state.sqlite3")
    columns = {row[1] for row in store.connection.execute("PRAGMA table_info(rounds)").fetchall()}
    assert {"state", "start_trade_id_max", "starting_balance", "loss_lock"} <= columns
    assert not columns.intersection({"orders", "fills", "fees", "password", "token"})


def test_fixed_close_budget_is_exposed_for_auditable_reconciliation() -> None:
    assert CLOSING_RECONCILIATION_SECONDS == 300


def test_pseudo_rest_snapshot_reads_runtime_state_and_paginates_history() -> None:
    responses = {
        "/api/v1/health": {"last_process": 1},
        "/api/v1/show_config": {
            "dry_run": True,
            "dry_run_wallet": "1000",
            "stake_currency": "USDT",
            "max_open_trades": 1,
        },
        "/api/v1/status": [],
        "/api/v1/balance": {"total_bot": "1000"},
    }
    requests: list[str] = []

    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self) -> bytes:
            path = urllib.parse.urlsplit(requests[-1]).path
            if path == "/api/v1/trades":
                offset = urllib.parse.parse_qs(urllib.parse.urlsplit(requests[-1]).query)["offset"][
                    0
                ]
                return json.dumps(
                    {
                        "trades": [{"trade_id": 10, "is_open": False}]
                        if offset == "1"
                        else [{"trade_id": 9, "is_open": False}],
                        "total_trades": 2,
                    }
                ).encode()
            return json.dumps(responses[path]).encode()

    def opener(request, *, timeout):
        assert timeout == REQUEST_TIMEOUT_SECONDS
        requests.append(request.full_url)
        return Response()

    client = FreqtradeRestClient(
        "http://127.0.0.1:8080",
        "runtime-user",
        "runtime-password",
        opener=opener,
    )
    result = client.snapshot()

    assert result.balance == Decimal("1000")
    assert [trade["trade_id"] for trade in result.closed_trades] == [9, 10]
    assert any("offset=1" in request for request in requests)
    assert "runtime-password" not in repr(client)
