import datetime
from typing import List

import pandas as pd
import requests


class AlphaVantageDataRetriever():

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self.ALPHA_VANTAGE_URL = "https://www.alphavantage.co/query"
        self.DAILY_ENDPOINT = "?function=TIME_SERIES_DAILY&symbol={symbol}&apikey={api_key}&outputsize=full"

    def get_ticker_daily(self,
                         symbols: List[str],
                         start: datetime.datetime,
                         end: datetime.datetime) -> pd.DataFrame:

        def data(symbol):
            parametrized_endpoint = self.DAILY_ENDPOINT.format(symbol=symbol, api_key=self.api_key)
            query_url = self.ALPHA_VANTAGE_URL + parametrized_endpoint
            response = requests.get(url=query_url).json()
            df_symbol = pd.DataFrame(response.get("Time Series (Daily)")).transpose()
            df_symbol["symbol"] = symbol
            df_symbol.index = pd.to_datetime(df_symbol.index)
            return df_symbol

        datas = map(data, symbols)
        df_symbols = pd.concat(datas, keys=symbols, names=["Ticker", "Date"], sort=True)

        df_symbols = df_symbols.rename(columns={"1. open": "Open",
                                                "2. high": "High",
                                                "3. low": "Low",
                                                "4. close": "Close",
                                                "5. volume": "Volume"})

        df_symbols = df_symbols.astype({"Open": float,
                                        "High": float,
                                        "Low": float,
                                        "Close": float,
                                        "Volume": int})

        df_symbols = df_symbols[df_symbols.index.get_level_values('Date').date >= start]
        df_symbols = df_symbols[df_symbols.index.get_level_values('Date').date <= end]
        return df_symbols