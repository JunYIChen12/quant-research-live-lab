from freqtrade.strategy import IStrategy
from pandas import DataFrame


class BtcDonchian5520(IStrategy):
    timeframe = "4h"
    can_short = False
    startup_candle_count = 55
    process_only_new_candles = True

    minimal_roi = {"0": 100.0}
    stoploss = -0.99
    use_exit_signal = True

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["donchian_high"] = dataframe["high"].rolling(55).max().shift(1)
        dataframe["donchian_low"] = dataframe["low"].rolling(20).min().shift(1)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (dataframe["close"] > dataframe["donchian_high"])
            & (dataframe["volume"] > 0),
            "enter_long",
        ] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (dataframe["close"] < dataframe["donchian_low"])
            & (dataframe["volume"] > 0),
            "exit_long",
        ] = 1
        return dataframe
