from freqtrade.strategy import IStrategy
from pandas import DataFrame


class CliCandidate(IStrategy):
    timeframe = "5m"
    minimal_roi = {"0": 0.1}
    stoploss = -0.1

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return dataframe
