import logging
import os
import time
from pathlib import Path

from freqtrade.strategy import IStrategy
from pandas import DataFrame

from quant_lab import GitHubApprovalVerifier, ReleaseGate

logger = logging.getLogger(__name__)


def _value(value):
    return getattr(value, "value", value)


class GovernedDryRunStrategy(IStrategy):
    """Manual-entry dry-run strategy guarded by an approved frozen release."""

    INTERFACE_VERSION = 3
    can_short = True
    timeframe = "5m"
    startup_candle_count = 0
    process_only_new_candles = True
    minimal_roi = {"0": 10.0}
    stoploss = -0.01
    use_exit_signal = False
    order_types = {
        "entry": "market",
        "exit": "market",
        "emergency_exit": "market",
        "force_entry": "market",
        "force_exit": "market",
        "stoploss": "market",
        "stoploss_on_exchange": False,
    }

    def bot_start(self, **kwargs) -> None:
        if not self._safe_dry_run_config():
            raise RuntimeError("unsafe Freqtrade dry-run configuration")

        self._release_gate = ReleaseGate(
            repository_root=Path(os.getenv("QUANT_REPOSITORY_ROOT", "/opt/quant-lab")),
            artifact_root=Path(os.getenv("QUANT_ARTIFACT_ROOT", "/opt/release")),
            manifest_path=Path(
                os.getenv("QUANT_MANIFEST_PATH", "/opt/release/release-manifest.toml")
            ),
            requested_mode="dry-run",
            expected_repository="JunYIChen12/quant-research-live-lab",
            approval_verifier=GitHubApprovalVerifier(token=os.getenv("GITHUB_TOKEN")),
            approval_ttl_seconds=300,
        )
        result = self._release_gate.refresh(now=time.monotonic())
        if not result.allowed:
            raise RuntimeError(f"release verification failed: {','.join(result.violations)}")
        self._next_release_refresh = time.monotonic() + 60

    def bot_loop_start(self, current_time, **kwargs) -> None:
        now = time.monotonic()
        if now < self._next_release_refresh:
            return
        result = self._release_gate.refresh(now=now)
        self._next_release_refresh = now + 60
        if not result.allowed:
            logger.error("Release gate closed: %s", ",".join(result.violations))

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["enter_long"] = 0
        dataframe["enter_short"] = 0
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["exit_long"] = 0
        dataframe["exit_short"] = 0
        return dataframe

    def leverage(
        self,
        pair,
        current_time,
        current_rate,
        proposed_leverage,
        max_leverage,
        entry_tag,
        side,
        **kwargs,
    ) -> float:
        return 1.0

    def confirm_trade_entry(
        self,
        pair,
        order_type,
        amount,
        rate,
        time_in_force,
        current_time,
        entry_tag,
        side,
        **kwargs,
    ) -> bool:
        if not self._safe_dry_run_config() or pair != "BTC/USDT:USDT":
            return False
        result = self._release_gate.check_before_entry(now=time.monotonic())
        if not result.allowed:
            logger.error("Entry rejected by release gate: %s", ",".join(result.violations))
        return result.allowed

    def _safe_dry_run_config(self) -> bool:
        try:
            stake_amount = float(self.config.get("stake_amount", 0))
        except (TypeError, ValueError):
            return False
        return bool(
            self.config.get("dry_run") is True
            and _value(self.config.get("runmode")) == "dry_run"
            and _value(self.config.get("trading_mode")) == "futures"
            and _value(self.config.get("margin_mode")) == "isolated"
            and self.config.get("max_open_trades") == 1
            and 0 < stake_amount <= 10
            and self.config.get("exchange", {}).get("pair_whitelist")
            == ["BTC/USDT:USDT"]
        )
