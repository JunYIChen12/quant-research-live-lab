from freqtrade.strategy import IStrategy
from pandas import DataFrame


class BtcTrendBaseline(IStrategy):
    timeframe = "4h"
    can_short = False
    startup_candle_count = 200
    process_only_new_candles = True

    minimal_roi = {"0": 100.0}
    stoploss = -0.99
    use_exit_signal = True

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema_fast"] = dataframe["close"].ewm(span=50, adjust=False).mean()
        dataframe["ema_slow"] = dataframe["close"].ewm(span=200, adjust=False).mean()
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        crossed_above = (dataframe["ema_fast"] > dataframe["ema_slow"]) & (
            dataframe["ema_fast"].shift(1) <= dataframe["ema_slow"].shift(1)
        )
        dataframe.loc[crossed_above & (dataframe["volume"] > 0), "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        crossed_below = (dataframe["ema_fast"] < dataframe["ema_slow"]) & (
            dataframe["ema_fast"].shift(1) >= dataframe["ema_slow"].shift(1)
        )
        dataframe.loc[crossed_below & (dataframe["volume"] > 0), "exit_long"] = 1
        return dataframe
