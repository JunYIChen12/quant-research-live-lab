"""Fail-closed runtime gates.

This module has no exchange integration. It only expresses invariants that any
future adapter must satisfy before opening a position.
"""

from dataclasses import dataclass
from decimal import Decimal

from .release import ReleaseVerification


@dataclass(frozen=True, slots=True)
class RiskLimits:
    max_leverage: Decimal = Decimal("1")
    max_open_positions: int = 1
    required_margin_mode: str = "isolated"
    max_daily_loss_pct: Decimal = Decimal("0.01")
    max_weekly_loss_pct: Decimal = Decimal("0.03")
    max_drawdown_pct: Decimal = Decimal("0.05")


@dataclass(frozen=True, slots=True)
class RuntimeSnapshot:
    leverage: Decimal
    open_positions: int
    margin_mode: str
    starting_equity: Decimal
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    estimated_close_cost: Decimal
    weekly_loss_pct: Decimal
    drawdown_pct: Decimal
    account_reconciled: bool
    stop_orders_healthy: bool

    @property
    def liquidation_adjusted_loss_pct(self) -> Decimal:
        """Loss after unrealized PnL and conservative close costs."""
        if self.starting_equity <= 0:
            return Decimal("Infinity")
        adjusted_pnl = self.realized_pnl + self.unrealized_pnl - self.estimated_close_cost
        return max(Decimal("0"), -adjusted_pnl / self.starting_equity)


@dataclass(frozen=True, slots=True)
class GateDecision:
    may_open_position: bool
    violations: tuple[str, ...]


def evaluate_runtime_gate(
    snapshot: RuntimeSnapshot,
    limits: RiskLimits,
    release: ReleaseVerification,
) -> GateDecision:
    """Evaluate all known constraints; any missing or invalid state blocks opening."""
    violations: list[str] = []

    if snapshot.leverage != limits.max_leverage:
        violations.append("leverage_mismatch")
    if snapshot.open_positions >= limits.max_open_positions:
        violations.append("position_limit_reached")
    if snapshot.margin_mode != limits.required_margin_mode:
        violations.append("margin_mode_mismatch")
    if snapshot.liquidation_adjusted_loss_pct >= limits.max_daily_loss_pct:
        violations.append("daily_loss_limit_reached")
    if snapshot.weekly_loss_pct >= limits.max_weekly_loss_pct:
        violations.append("weekly_loss_limit_reached")
    if snapshot.drawdown_pct >= limits.max_drawdown_pct:
        violations.append("drawdown_limit_reached")
    if not release.allowed:
        violations.extend(f"release:{violation}" for violation in release.violations)
    if not snapshot.account_reconciled:
        violations.append("account_not_reconciled")
    if not snapshot.stop_orders_healthy:
        violations.append("stop_order_unhealthy")

    return GateDecision(may_open_position=not violations, violations=tuple(violations))
