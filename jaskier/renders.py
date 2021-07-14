from plotly.subplots import make_subplots
import plotly.graph_objects as go
import pandas as pd


def make_graphs(df_global_portfolio_performances: pd.DataFrame) -> go.Figure:

    min_date = df_global_portfolio_performances.index.min().strftime("%d-%m-%Y")
    max_date = df_global_portfolio_performances.index.max().strftime("%d-%m-%Y")
    last_state_values = df_global_portfolio_performances.tail(5).dropna()

    fig = make_subplots(
        rows=3,
        cols=4,
        shared_xaxes=True,
        vertical_spacing=0.05,
        subplot_titles=(
            "",
            "",
            "",
            "",
            "Amount invested & portfolio valuation evolution",
            "Profit & Loss evolution",
            "ROI evolution",
            "Equivalent annual ROI",
        ),
        specs=[
            [
                {"type": "indicator"},
                {"type": "indicator"},
                {"type": "indicator"},
                {"type": "indicator"},
            ],
            [{"colspan": 2}, None, {"colspan": 2}, None],
            [{"colspan": 2}, None, {"colspan": 2}, None],
        ],
    )

    fig.add_trace(
        go.Indicator(
            mode="number",
            value=int(last_state_values.total_value_currently_invested.values[-1]),
            title={"text": "Amount invested"},
        ),
        row=1,
        col=1,
    )

    fig.add_trace(
        go.Indicator(
            mode="number",
            value=int(last_state_values.current_portfolio_valuation.values[-1]),
            title={"text": "Current valuation"},
            domain={"x": [0.05, 0.5], "y": [0.15, 0.35]},
        ),
        row=1,
        col=2,
    )

    fig.add_trace(
        go.Indicator(
            mode="number",
            value=round(last_state_values.current_roi.values[-1] * 100, 2),
            title={"text": "Current ROI"},
            domain={"x": [0.05, 0.5], "y": [0.15, 0.35]},
        ),
        row=1,
        col=3,
    )

    fig.add_trace(
        go.Indicator(
            mode="number",
            value=round(last_state_values.current_pl.values[-1], 2),
            title={"text": "Current P&L"},
            domain={"x": [0.05, 0.5], "y": [0.15, 0.35]},
        ),
        row=1,
        col=4,
    )

    fig.add_trace(
        go.Scatter(
            x=df_global_portfolio_performances.index,
            y=df_global_portfolio_performances["current_portfolio_valuation"].values,
            name="Portfolio valuation",
        ),
        row=2,
        col=1,
    )

    fig.add_trace(
        go.Scatter(
            x=df_global_portfolio_performances.index,
            y=df_global_portfolio_performances["total_value_currently_invested"].values,
            name="Amount invested",
        ),
        row=2,
        col=1,
    )

    fig.add_trace(
        go.Scatter(
            x=df_global_portfolio_performances.index,
            y=df_global_portfolio_performances["current_roi"].values,
            name="Current ROI",
        ),
        row=3,
        col=1,
    )

    fig.add_trace(
        go.Scatter(
            x=df_global_portfolio_performances.index,
            y=df_global_portfolio_performances["current_pl"].values,
            name="Current P&L",
        ),
        row=2,
        col=3,
    )

    fig.add_trace(
        go.Scatter(
            x=df_global_portfolio_performances.index,
            y=df_global_portfolio_performances["estimated_annual_roi"].values,
            name="Annual ROI",
        ),
        row=3,
        col=3,
    )

    fig.update_layout(
        height=1080,
        width=1920,
        title_text=f"Portfolio performances between the {min_date} and the {max_date}",
    )

    return fig
