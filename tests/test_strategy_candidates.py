import importlib
import importlib.util

from pandas import DataFrame


def load_strategy(module_name: str, class_name: str):
    module_path = f"experiments.btc_trend.strategies.{module_name}"
    assert importlib.util.find_spec(module_path) is not None, f"missing {module_name}"
    return getattr(importlib.import_module(module_path), class_name)(config={})


def test_donchian_breakout_uses_prior_channel() -> None:
    strategy = load_strategy("BtcDonchian5520", "BtcDonchian5520")
    candles = DataFrame(
        {
            "close": [9.0, 11.0, 7.0],
            "donchian_high": [10.0, 10.0, 10.0],
            "donchian_low": [8.0, 8.0, 8.0],
            "volume": [1.0, 1.0, 1.0],
        }
    )

    signals = strategy.populate_entry_trend(candles.copy(), {})
    signals = strategy.populate_exit_trend(signals, {})

    assert signals["enter_long"].fillna(0).tolist() == [0, 1, 0]
    assert signals["exit_long"].fillna(0).tolist() == [0, 0, 1]

    history = DataFrame(
        {
            "high": [float(value) for value in range(1, 57)],
            "low": [float(value) for value in range(1, 57)],
        }
    )
    indicators = strategy.populate_indicators(history, {})
    assert indicators.iloc[-1]["donchian_high"] == 55.0
    assert indicators.iloc[-1]["donchian_low"] == 36.0


def test_sma_filter_holds_only_above_long_average() -> None:
    strategy = load_strategy("BtcSmaFilter200", "BtcSmaFilter200")
    candles = DataFrame(
        {
            "close": [99.0, 101.0, 99.0],
            "sma_200": [100.0, 100.0, 100.0],
            "volume": [1.0, 1.0, 1.0],
        }
    )

    signals = strategy.populate_entry_trend(candles.copy(), {})
    signals = strategy.populate_exit_trend(signals, {})

    assert signals["enter_long"].fillna(0).tolist() == [0, 1, 0]
    assert signals["exit_long"].fillna(0).tolist() == [1, 0, 1]
    assert strategy.timeframe == "4h"
    assert strategy.can_short is False
