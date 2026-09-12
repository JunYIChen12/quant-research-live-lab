from dataclasses import replace
from decimal import Decimal

from quant_lab import RiskLimits, RuntimeSnapshot, evaluate_runtime_gate


def valid_snapshot() -> RuntimeSnapshot:
    return RuntimeSnapshot(
        leverage=Decimal("1"),
        open_positions=0,
        margin_mode="isolated",
        starting_equity=Decimal("1000"),
        realized_pnl=Decimal("0"),
        unrealized_pnl=Decimal("0"),
        estimated_close_cost=Decimal("0"),
        weekly_loss_pct=Decimal("0"),
        drawdown_pct=Decimal("0"),
        strategy_commit="a" * 40,
        approval_id="approval-001",
        evidence_complete=True,
        account_reconciled=True,
        stop_orders_healthy=True,
    )


def test_valid_snapshot_allows_opening() -> None:
    decision = evaluate_runtime_gate(valid_snapshot(), RiskLimits())
    assert decision.may_open_position is True
    assert decision.violations == ()


def test_missing_evidence_fails_closed() -> None:
    snapshot = replace(valid_snapshot(), evidence_complete=False)
    decision = evaluate_runtime_gate(snapshot, RiskLimits())
    assert decision.may_open_position is False
    assert "evidence_incomplete" in decision.violations


def test_leverage_must_match_exactly() -> None:
    snapshot = replace(valid_snapshot(), leverage=Decimal("5"))
    decision = evaluate_runtime_gate(snapshot, RiskLimits())
    assert decision.may_open_position is False
    assert "leverage_mismatch" in decision.violations


def test_loss_includes_float_loss_and_close_cost() -> None:
    snapshot = replace(
        valid_snapshot(),
        unrealized_pnl=Decimal("-8"),
        estimated_close_cost=Decimal("2"),
    )
    decision = evaluate_runtime_gate(snapshot, RiskLimits())
    assert snapshot.liquidation_adjusted_loss_pct == Decimal("0.01")
    assert decision.may_open_position is False
    assert "daily_loss_limit_reached" in decision.violations


def test_existing_position_blocks_another_open() -> None:
    snapshot = replace(valid_snapshot(), open_positions=1)
    decision = evaluate_runtime_gate(snapshot, RiskLimits())
    assert decision.may_open_position is False
    assert "position_limit_reached" in decision.violations
