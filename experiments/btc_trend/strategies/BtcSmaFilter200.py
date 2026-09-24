from freqtrade.strategy import IStrategy
from pandas import DataFrame


class BtcSmaFilter200(IStrategy):
    timeframe = "4h"
    can_short = False
    startup_candle_count = 200
    process_only_new_candles = True

    minimal_roi = {"0": 100.0}
    stoploss = -0.99
    use_exit_signal = True

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["sma_200"] = dataframe["close"].rolling(200).mean()
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (dataframe["close"] > dataframe["sma_200"])
            & (dataframe["volume"] > 0),
            "enter_long",
        ] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (dataframe["close"] < dataframe["sma_200"])
            & (dataframe["volume"] > 0),
            "exit_long",
        ] = 1
        return dataframe
