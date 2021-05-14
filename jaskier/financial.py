import logging
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
import numpy as np
import datetime
import yfinance as yf
from yaspin import yaspin
import pandas_market_calendars as mcal

from jaskier.defaults import (
    DEFAULT_BENCHMARK,
    TRADING_CALENDAR_LOCATION,
    TRADING_CALENDAR_FREQUENCY,
)

from jaskier.utils import Context


# Generate a logger
logger = logging.getLogger(__name__)


def create_market_cal(start, end):
    nyse = mcal.get_calendar(TRADING_CALENDAR_LOCATION)
    schedule = nyse.schedule(start, end)
    market_cal = mcal.date_range(schedule, frequency=TRADING_CALENDAR_FREQUENCY)
    market_cal = market_cal.tz_localize(None)
    market_cal = [i.replace(hour=0) for i in market_cal]
    return market_cal


def get_data(
    stocks: List[str], start: datetime.datetime, end: datetime.datetime
) -> pd.DataFrame:
    def data(ticker):
        df = yf.download(
            ticker, start=start, end=(end + datetime.timedelta(days=1)), progress=False
        )
        df["symbol"] = ticker
        df.index = pd.to_datetime(df.index)
        return df

    datas = map(data, stocks)
    return pd.concat(datas, keys=stocks, names=["Ticker", "Date"], sort=True)


def get_benchmark(benchmark, start, end):
    benchmark = get_data(benchmark, start, end)
    benchmark = benchmark.drop(["symbol"], axis=1)
    benchmark.reset_index(inplace=True)
    return benchmark


def position_adjust(daily_positions, sale):
    stocks_with_sales = pd.DataFrame()
    buys_before_start = daily_positions[daily_positions["Type"] == "Buy"].sort_values(
        by="Open date"
    )
    for position in buys_before_start[
        buys_before_start["Symbol"] == sale[1]["Symbol"]
    ].iterrows():
        if position[1]["Qty"] <= sale[1]["Qty"]:
            sale[1]["Qty"] -= position[1]["Qty"]
            position[1]["Qty"] = 0
        else:
            position[1]["Qty"] -= sale[1]["Qty"]
            sale[1]["Qty"] -= sale[1]["Qty"]
        stocks_with_sales = stocks_with_sales.append(position[1])
    return stocks_with_sales


def portfolio_start_balance(portfolio, start_date):
    positions_before_start = portfolio[portfolio["Open date"] <= start_date]
    future_positions = portfolio[portfolio["Open date"] >= start_date]
    sales = (
        positions_before_start[positions_before_start["Type"] == "Sell.FIFO"]
        .groupby(["Symbol"])["Qty"]
        .sum()
    )
    sales = sales.reset_index()
    positions_no_change = positions_before_start[
        ~positions_before_start["Symbol"].isin(sales["Symbol"].unique())
    ]
    adj_positions_df = pd.DataFrame()
    for sale in sales.iterrows():
        adj_positions = position_adjust(positions_before_start, sale)
        adj_positions_df = adj_positions_df.append(adj_positions)
    adj_positions_df = adj_positions_df.append(positions_no_change)
    adj_positions_df = adj_positions_df.append(future_positions)
    adj_positions_df = adj_positions_df[adj_positions_df["Qty"] > 0]
    return adj_positions_df


def fifo(daily_positions, sales, date):
    sales = sales[sales["Open date"] == date]
    daily_positions = daily_positions[daily_positions["Open date"] <= date]
    positions_no_change = daily_positions[
        ~daily_positions["Symbol"].isin(sales["Symbol"].unique())
    ]
    adj_positions = pd.DataFrame()
    for sale in sales.iterrows():
        adj_positions = adj_positions.append(position_adjust(daily_positions, sale))
    adj_positions = adj_positions.append(positions_no_change)
    adj_positions = adj_positions[adj_positions["Qty"] > 0]
    return adj_positions


def time_fill(portfolio, market_cal):
    sales = (
        portfolio[portfolio["Type"] == "Sell.FIFO"]
        .groupby(["Symbol", "Open date"])["Qty"]
        .sum()
    )
    sales = sales.reset_index()
    per_day_balance = []
    for date in market_cal:
        if (sales["Open date"] == date).any():
            portfolio = fifo(portfolio, sales, date)
        daily_positions = portfolio[portfolio["Open date"] <= date]
        daily_positions = daily_positions[daily_positions["Type"] == "Buy"]
        daily_positions["Date Snapshot"] = date
        per_day_balance.append(daily_positions)
    return per_day_balance


# matches prices of each asset to open date, then adjusts for  cps of dates
def modified_cost_per_share(portfolio, adj_close, start_date):
    df = pd.merge(
        portfolio,
        adj_close,
        left_on=["Date Snapshot", "Symbol"],
        right_on=["Date", "Ticker"],
        how="left",
    )
    df.rename(columns={"Close": "Symbol Adj Close"}, inplace=True)
    df["Adj cost daily"] = df["Symbol Adj Close"] * df["Qty"]
    df = df.drop(["Ticker", "Date"], axis=1)
    return df


# merge portfolio data with latest benchmark data and create several calcs
def benchmark_portfolio_calcs(portfolio, benchmark):
    portfolio = pd.merge(
        portfolio, benchmark, left_on=["Date Snapshot"], right_on=["Date"], how="left"
    )
    portfolio = portfolio.drop(["Date"], axis=1)
    portfolio.rename(columns={"Close": "Benchmark Close"}, inplace=True)
    benchmark_max = benchmark[benchmark["Date"] == benchmark["Date"].max()]
    portfolio["Benchmark End Date Close"] = portfolio.apply(
        lambda x: benchmark_max["Close"], axis=1
    )
    benchmark_min = benchmark[benchmark["Date"] == benchmark["Date"].min()]
    portfolio["Benchmark Start Date Close"] = portfolio.apply(
        lambda x: benchmark_min["Close"], axis=1
    )
    return portfolio


def portfolio_end_of_year_stats(portfolio, adj_close_end):
    adj_close_end = adj_close_end[adj_close_end["Date"] == adj_close_end["Date"].max()]
    portfolio_end_data = pd.merge(
        portfolio, adj_close_end, left_on="Symbol", right_on="Ticker"
    )
    portfolio_end_data.rename(columns={"Close": "Ticker End Date Close"}, inplace=True)
    portfolio_end_data = portfolio_end_data.drop(["Ticker", "Date"], axis=1)
    return portfolio_end_data


# Merge the overall dataframe with the adj close start of year dataframe for YTD tracking of tickers.
def portfolio_start_of_year_stats(portfolio, adj_close_start):
    adj_close_start = adj_close_start[
        adj_close_start["Date"] == adj_close_start["Date"].min()
    ]
    portfolio_start = pd.merge(
        portfolio,
        adj_close_start[["Ticker", "Close", "Date"]],
        left_on="Symbol",
        right_on="Ticker",
    )
    portfolio_start.rename(columns={"Close": "Ticker Start Date Close"}, inplace=True)
    portfolio_start["Adj cost per share"] = np.where(
        portfolio_start["Open date"] <= portfolio_start["Date"],
        portfolio_start["Ticker Start Date Close"],
        portfolio_start["Adj cost per share"],
    )
    portfolio_start["Adj cost"] = (
        portfolio_start["Adj cost per share"] * portfolio_start["Qty"]
    )
    portfolio_start = portfolio_start.drop(["Ticker", "Date"], axis=1)
    portfolio_start["Equiv Benchmark Shares"] = (
        portfolio_start["Adj cost"] / portfolio_start["Benchmark Start Date Close"]
    )
    portfolio_start["Benchmark Start Date Cost"] = (
        portfolio_start["Equiv Benchmark Shares"]
        * portfolio_start["Benchmark Start Date Close"]
    )
    return portfolio_start


def calc_returns(portfolio):
    portfolio["Benchmark Return"] = (
        portfolio["Benchmark Close"] / portfolio["Benchmark Start Date Close"] - 1
    )
    portfolio["Ticker Return"] = (
        portfolio["Symbol Adj Close"] / portfolio["Adj cost per share"] - 1
    )
    portfolio["Ticker Share Value"] = portfolio["Qty"] * portfolio["Symbol Adj Close"]
    portfolio["Benchmark Share Value"] = (
        portfolio["Equiv Benchmark Shares"] * portfolio["Benchmark Close"]
    )
    portfolio["Stock Gain / (Loss)"] = (
        portfolio["Ticker Share Value"] - portfolio["Adj cost"]
    )
    portfolio["Benchmark Gain / (Loss)"] = (
        portfolio["Benchmark Share Value"] - portfolio["Adj cost"]
    )
    portfolio["Abs Value Compare"] = (
        portfolio["Ticker Share Value"] - portfolio["Benchmark Start Date Cost"]
    )
    portfolio["Abs Value Return"] = (
        portfolio["Abs Value Compare"] / portfolio["Benchmark Start Date Cost"]
    )
    portfolio["Abs. Return Compare"] = (
        portfolio["Ticker Return"] - portfolio["Benchmark Return"]
    )
    return portfolio


def per_day_portfolio_calcs(
    per_day_holdings, daily_benchmark, daily_adj_close, stocks_start
):
    df = pd.concat(per_day_holdings, sort=True)
    mcps = modified_cost_per_share(df, daily_adj_close, stocks_start)
    bpc = benchmark_portfolio_calcs(mcps, daily_benchmark)
    pes = portfolio_end_of_year_stats(bpc, daily_adj_close)
    pss = portfolio_start_of_year_stats(pes, daily_adj_close)
    returns = calc_returns(pss)
    return returns


def run_date_to_date_performances_analysis(
    positions_tracking_file: Path,
    start_analysis_at: datetime.datetime = None,
    end_analysis_at: datetime.datetime = None,
    ctx: Context = None,
    benchmark: str = DEFAULT_BENCHMARK,
) -> pd.DataFrame:

    # Read positions data
    portfolio_df = pd.read_csv(positions_tracking_file)
    portfolio_df["Open date"] = pd.to_datetime(portfolio_df["Open date"], dayfirst=True)
    portfolio_df["Adj cost per share"] = portfolio_df["Adj cost"] / portfolio_df["Qty"]
    portfolio_df["Type"] = portfolio_df["Type"].str.strip()

    # if start_analysis_at or end_analysis_at are None, resolve values
    # based on positions mins and today's date
    if start_analysis_at is None:
        start_analysis_at = portfolio_df["Open date"].min() - datetime.timedelta(days=1)

    if end_analysis_at is None:
        end_analysis_at = datetime.datetime.now().date()

    if ctx and ctx.verbose:
        logger.log(
            level=logging.INFO, msg=f"Using start_analysis_at as: {start_analysis_at}"
        )
        logger.log(
            level=logging.INFO, msg=f"Using end_analysis_at as: {end_analysis_at}"
        )

    # Extract Symbols
    symbols = portfolio_df.Symbol.unique()

    with yaspin(text="Downloading portfolio tickers data..."):
        daily_adj_close = get_data(symbols, start_analysis_at, end_analysis_at)
    daily_adj_close = daily_adj_close[["Close"]].reset_index()

    with yaspin(text=f"Downloading benchmark ({benchmark}) data..."):
        daily_benchmark = get_benchmark([benchmark], start_analysis_at, end_analysis_at)
    daily_benchmark = daily_benchmark[["Date", "Close"]]

    with yaspin(text=f"Generating stock market trading calendar..."):
        market_cal = create_market_cal(start_analysis_at, end_analysis_at)

    with yaspin(text=f"Computing portfolio's state over time..."):
        # Compute portfolio state at start_analysis_at
        active_portfolio = portfolio_start_balance(portfolio_df, start_analysis_at)

        # Compute the states of positions for each day in the calendar
        positions_per_day = time_fill(active_portfolio, market_cal)

    with yaspin(text=f"Computing portfolio's performances..."):
        # Combine all results and compute performances metrics
        combined_df = per_day_portfolio_calcs(
            positions_per_day, daily_benchmark, daily_adj_close, start_analysis_at
        )

    return combined_df


def get_last_fully_defined_day(performances_analysis: pd.DataFrame) -> pd.DataFrame:
    backward_counter = 1
    while True:
        df_yesterday = performances_analysis[
            performances_analysis["Date Snapshot"]
            == performances_analysis["Date Snapshot"].unique()[-backward_counter]
        ]
        if df_yesterday[["Ticker Return"]].isna().values.any():
            backward_counter += 1
        else:
            break
    return df_yesterday


def get_portfolio_level_performances(
    df_performances_d_day: pd.DataFrame,
) -> Dict[str, Any]:
    evaluation_date = df_performances_d_day["Date Snapshot"].values[0]
    if not df_performances_d_day[["Ticker Return"]].isna().values.any():
        total_value_currently_invested = df_performances_d_day["Adj cost"].sum()
        current_portfolio_valuation = df_performances_d_day["Adj cost daily"].sum()
        current_roi = (
            df_performances_d_day["Adj cost daily"].sum()
            / df_performances_d_day["Adj cost"].sum()
        ) - 1
        current_pl = current_portfolio_valuation - total_value_currently_invested
        first_investment_date = df_performances_d_day["Open date"].min()
        timedelta_between_first_date_and_now = evaluation_date - first_investment_date

        if timedelta_between_first_date_and_now.days != 0:
            estimated_daily_roi = (
                (current_roi + 1) ** (1 / timedelta_between_first_date_and_now.days)
            ) - 1
            estimated_annual_roi = ((estimated_daily_roi + 1) ** (365)) - 1
        else:
            estimated_daily_roi = None
            estimated_annual_roi = None

        return {
            "Date Snapshot": evaluation_date,
            "total_value_currently_invested": total_value_currently_invested,
            "current_portfolio_valuation": current_portfolio_valuation,
            "current_roi": current_roi,
            "current_pl": current_pl,
            "estimated_annual_roi": estimated_annual_roi,
        }
    else:
        return {
            "Date Snapshot": evaluation_date,
            "total_value_currently_invested": None,
            "current_portfolio_valuation": None,
            "current_roi": None,
            "current_pl": None,
            "estimated_annual_roi": None,
        }


def get_global_portfolio_level_performances(
    performances_analysis: pd.DataFrame,
) -> pd.DataFrame:
    results = []
    for date in performances_analysis["Date Snapshot"].unique():
        df_day = performances_analysis[performances_analysis["Date Snapshot"] == date]
        results.append(get_portfolio_level_performances(df_performances_d_day=df_day))
    return pd.DataFrame(results).set_index("Date Snapshot")


def compute_portfolio_performances(
    positions_tracking_file: Path,
    start_analysis_at: datetime.datetime = None,
    end_analysis_at: datetime.datetime = None,
    ctx: Context = None,
    benchmark: str = DEFAULT_BENCHMARK,
) -> pd.DataFrame:

    performances_analysis = run_date_to_date_performances_analysis(
        ctx=ctx,
        positions_tracking_file=Path(positions_tracking_file),
        start_analysis_at=start_analysis_at,
        end_analysis_at=end_analysis_at,
        benchmark=benchmark,
    )

    return get_global_portfolio_level_performances(
        performances_analysis=performances_analysis
    )
