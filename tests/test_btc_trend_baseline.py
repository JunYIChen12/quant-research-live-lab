from pandas import DataFrame

from experiments.btc_trend.strategies.BtcTrendBaseline import BtcTrendBaseline


def test_ema_crosses_drive_long_entries_and_exits() -> None:
    strategy = BtcTrendBaseline(config={})
    candles = DataFrame(
        {
            "ema_fast": [1.0, 2.0, 3.0, 1.0],
            "ema_slow": [2.0, 2.0, 2.0, 2.0],
            "volume": [1.0, 1.0, 1.0, 1.0],
        }
    )

    signals = strategy.populate_entry_trend(candles.copy(), {})
    signals = strategy.populate_exit_trend(signals, {})

    assert signals["enter_long"].fillna(0).tolist() == [0, 0, 1, 0]
    assert signals["exit_long"].fillna(0).tolist() == [0, 0, 0, 1]
    assert strategy.timeframe == "4h"
    assert strategy.can_short is False
