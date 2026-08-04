import json
from datetime import date, datetime
from pathlib import Path

import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px

# Page setup
st.set_page_config(
    page_title="Stock Movers Dashboard",
    page_icon=":material/finance_mode:",
    layout="wide",
)
st.title("📊 Watchlist top movers")
st.caption("Track your **watchlist** and spot the biggest **gainers** and **losers** at a glance.")

# Default Watchlist
DEFAULT_TICKERS = [ "AAPL", "TSLA", "META", "GOOG" ]

# Sidebar controls
with st.sidebar:
    st.header("Settings")
    tickers_input = st.text_area(
        "Edit watchlist (comma-separated)",
        value=", ".join(DEFAULT_TICKERS),
        height=150,
    )
    watchlist = [t.strip().upper() for t in tickers_input.split(",") if t.strip()]

    top_n = st.slider("Number of top movers to show", min_value=3, max_value=10, value=5)

    if st.button("Refresh data", icon=":material/refresh:", width="stretch"):
        st.cache_data.clear()

@st.cache_data(ttl=30)
def get_stock_data(tickers):
    if not tickers:
        return pd.DataFrame()

    df = yf.download(tickers, period="1mo", interval="1d", progress=False)["Close"]

    results = []
    for ticker in tickers:
        try:
            series = (df if isinstance(df, pd.Series) else df[ticker]).dropna()

            curr_price = series.iloc[-1]
            change_1d = ((curr_price - series.iloc[-2]) / series.iloc[-2]) * 100
            change_5d = ((curr_price - series.iloc[-6]) / series.iloc[-6]) * 100 if len(series) > 5 else None
            change_30d = ((curr_price - series.iloc[0]) / series.iloc[0]) * 100

            results.append({
                "Ticker": ticker,
                "Price": round(curr_price, 2),
                "Change (%)": round(change_1d, 2),
                "Change 5D (%)": round(change_5d, 2) if change_5d is not None else None,
                "Change 30D (%)": round(change_30d, 2),
                "Trend 30D": series.tolist(),
                "Trend Dates": series.index.strftime("%Y-%m-%d").tolist(),
            })
        except Exception:
            continue

    return pd.DataFrame(results)


BASE_VALUE_STYLE = {"font-size": "1.75rem"}
TICKER_STYLE = {"font-weight": "800", "font-size": "2.75rem"}


def style_change(val):
    """Bold + green/red color for a %-change cell."""
    if pd.isna(val):
        return ""
    color = "#1a9e5c" if val > 0 else "#d1453d" if val < 0 else "inherit"
    return f"color: {color}; font-weight: 800; font-size: 1.75rem"


def style_bar(fig, color):
    fig.update_traces(
        texttemplate="%{text:.2f}%",
        textposition="outside",
        textfont=dict(size=13, family="Arial"),
        marker_color=color,
        marker_line_width=0,
    )
    fig.update_layout(
        showlegend=False,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10, t=10, b=10),
        font=dict(family="Arial", size=13),
        xaxis=dict(title=None, tickfont=dict(size=13)),
        yaxis=dict(title=None, showgrid=False, zeroline=False, showticklabels=False),
    )
    return fig


# Portfolio persistence — saved to disk so holdings survive app restarts
DATA_DIR = Path(__file__).parent
HOLDINGS_FILE = DATA_DIR / "portfolio_holdings.json"
SOLD_FILE = DATA_DIR / "portfolio_sold.json"


def load_json(path, default):
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            return default
    return default


def save_json(path, data):
    path.write_text(json.dumps(data, indent=2))


if "holdings" not in st.session_state:
    st.session_state.holdings = load_json(HOLDINGS_FILE, [])
if "sold_history" not in st.session_state:
    st.session_state.sold_history = load_json(SOLD_FILE, [])


def style_portfolio_table(df, pnl_cols):
    return (
        df.style
            .set_properties(**BASE_VALUE_STYLE)
            .set_properties(subset=["Ticker"], **TICKER_STYLE)
            .map(style_change, subset=pnl_cols)
    )


tab_market, tab_holdings = st.tabs([
    ":material/monitoring: Market movers",
    ":material/wallet: My holdings",
])

with tab_market:
    # Fetch Data
    data = get_stock_data(watchlist)

    if not data.empty:
        # Separate gainers & losers
        gainers = data[data["Change (%)"] > 0].sort_values(by="Change (%)", ascending=False).head(top_n)
        losers = data[data["Change (%)"] < 0].sort_values(by="Change (%)", ascending=True).head(top_n)

        advancers = int((data["Change (%)"] > 0).sum())
        decliners = int((data["Change (%)"] < 0).sum())
        avg_change = data["Change (%)"].mean()
        best = data.loc[data["Change (%)"].idxmax()]
        worst = data.loc[data["Change (%)"].idxmin()]

        st.caption(
            f"Last updated **{datetime.now().strftime('%H:%M:%S')}** · "
            f"tracking **{len(data)}** of **{len(watchlist)}** tickers"
        )

        # KPI summary row
        with st.container(horizontal=True):
            st.metric("Average change", f"{avg_change:+.2f}%", border=True)
            st.metric("Advancers", advancers, border=True)
            st.metric("Decliners", decliners, border=True)
            st.metric(f"Best: **{best['Ticker']}**", f"${best['Price']:.2f}", f"{best['Change (%)']:+.2f}%", border=True)
            st.metric(f"Worst: **{worst['Ticker']}**", f"${worst['Price']:.2f}", f"{worst['Change (%)']:+.2f}%", border=True)

        col1, col2 = st.columns(2)

        movers_column_config = {
            "Ticker": st.column_config.TextColumn("Ticker", pinned=True, width=150),
            "Price": st.column_config.NumberColumn("Price", format="$%.2f"),
            "Change (%)": st.column_config.NumberColumn("1-day change", format="%.2f%%"),
        }

        # Positive movers (gainers)
        with col1:
            with st.container(border=True):
                st.subheader(":material/trending_up: Top gainers")
                if not gainers.empty:
                    gainers_view = gainers[["Ticker", "Price", "Change (%)"]]
                    st.dataframe(
                        gainers_view.style
                            .set_properties(**BASE_VALUE_STYLE)
                            .set_properties(subset=["Ticker"], **TICKER_STYLE)
                            .map(style_change, subset=["Change (%)"]),
                        hide_index=True,
                        width="stretch",
                        height="content",
                        row_height=90,
                        column_config=movers_column_config,
                    )

                    fig_gainers = px.bar(gainers, x="Ticker", y="Change (%)", text="Change (%)")
                    st.plotly_chart(style_bar(fig_gainers, "#00CC96"), width="stretch")

        # Negative movers (losers)
        with col2:
            with st.container(border=True):
                st.subheader(":material/trending_down: Top losers")
                if not losers.empty:
                    losers_view = losers[["Ticker", "Price", "Change (%)"]]
                    st.dataframe(
                        losers_view.style
                            .set_properties(**BASE_VALUE_STYLE)
                            .set_properties(subset=["Ticker"], **TICKER_STYLE)
                            .map(style_change, subset=["Change (%)"]),
                        hide_index=True,
                        width="stretch",
                        height="content",
                        row_height=90,
                        column_config=movers_column_config,
                    )

                    fig_losers = px.bar(losers, x="Ticker", y="Change (%)", text="Change (%)")
                    st.plotly_chart(style_bar(fig_losers, "#EF553B"), width="stretch")

        # Full data table
        change_cols = ["Change (%)", "Change 5D (%)", "Change 30D (%)"]
        with st.container(border=True):
            st.subheader(":material/table_chart: Complete watchlist data")
            st.caption("**1-day**, **5-day**, and **30-day** % change, with a 30-day price trend.")
            sorted_data = data.sort_values(by="Change (%)", ascending=False).reset_index(drop=True)
            st.dataframe(
                sorted_data.style
                    .set_properties(**BASE_VALUE_STYLE)
                    .set_properties(subset=["Ticker"], **TICKER_STYLE)
                    .map(style_change, subset=change_cols),
                width="stretch",
                hide_index=True,
                row_height=90,
                height=938,  # header + 10 rows at row_height=90, so 10 tickers show without scrolling
                column_config={
                    "Ticker": st.column_config.TextColumn("Ticker", pinned=True, width=150),
                    "Price": st.column_config.NumberColumn("Price", format="$%.2f"),
                    "Change (%)": st.column_config.NumberColumn("1-day change", format="%.2f%%"),
                    "Change 5D (%)": st.column_config.NumberColumn("5-day change", format="%.2f%%"),
                    "Change 30D (%)": st.column_config.NumberColumn("30-day change", format="%.2f%%"),
                    "Trend 30D": st.column_config.LineChartColumn("30-day trend"),
                    "Trend Dates": None,
                },
            )

            st.write("**Look up a ticker's full trend:**")
            selected_ticker = st.selectbox(
                "Select a ticker to see its 30-day trend with exact dates and prices",
                options=sorted_data["Ticker"].tolist(),
                label_visibility="collapsed",
            )
            sel = sorted_data.loc[sorted_data["Ticker"] == selected_ticker].iloc[0]
            trend_df = pd.DataFrame({
                "Date": pd.to_datetime(sel["Trend Dates"]),
                "Price": sel["Trend 30D"],
            })
            fig_trend = px.line(trend_df, x="Date", y="Price")
            fig_trend.update_traces(
                line=dict(color="#4C78A8", width=3),
                mode="lines+markers",
                marker=dict(size=6),
                hovertemplate="%{x|%b %d, %Y}<br><b>$%{y:.2f}</b><extra></extra>",
            )
            fig_trend.update_layout(
                title=f"{sel['Ticker']} · 30-day price trend",
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                margin=dict(l=10, r=10, t=40, b=10),
                font=dict(size=14),
                xaxis=dict(title=None),
                yaxis=dict(title="Price ($)"),
                hovermode="x unified",
                hoverlabel=dict(font=dict(size=22), bgcolor="white"),
            )
            st.plotly_chart(fig_trend, width="stretch")
    else:
        st.error("Failed to fetch market data. Please verify your tickers.", icon=":material/error:")

with tab_holdings:
    st.subheader(":material/wallet: My holdings")
    st.caption("Track tickers you actually own. Add one when you buy, record the sale when you sell — profit or loss is calculated automatically.")

    with st.form("add_holding_form", clear_on_submit=True, border=True):
        st.write("**Add a ticker you own**")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            new_ticker = st.text_input("Ticker", placeholder="e.g. AAPL")
        with c2:
            new_shares = st.number_input("Shares", min_value=0.0001, value=1.0, step=1.0)
        with c3:
            new_buy_price = st.number_input("Buy price ($)", min_value=0.01, value=100.0, step=0.01)
        with c4:
            new_buy_date = st.date_input("Buy date", value=date.today())

        if st.form_submit_button("Add to holdings", icon=":material/add:", width="stretch"):
            clean_ticker = new_ticker.strip().upper()
            if clean_ticker:
                st.session_state.holdings.append({
                    "Ticker": clean_ticker,
                    "Shares": new_shares,
                    "Buy Price": new_buy_price,
                    "Buy Date": new_buy_date.isoformat(),
                })
                save_json(HOLDINGS_FILE, st.session_state.holdings)
                st.toast(f"Added {clean_ticker} to holdings", icon=":material/check_circle:")
            else:
                st.warning("Enter a ticker symbol.", icon=":material/warning:")

    if st.session_state.holdings:
        holding_tickers = sorted({h["Ticker"] for h in st.session_state.holdings})
        live_data = get_stock_data(holding_tickers)
        price_map = dict(zip(live_data["Ticker"], live_data["Price"])) if not live_data.empty else {}

        holdings_rows = []
        for h in st.session_state.holdings:
            cur_price = price_map.get(h["Ticker"])
            pnl_pct = (cur_price - h["Buy Price"]) / h["Buy Price"] * 100 if cur_price is not None else None
            pnl_amt = (cur_price - h["Buy Price"]) * h["Shares"] if cur_price is not None else None
            holdings_rows.append({
                "Ticker": h["Ticker"],
                "Shares": h["Shares"],
                "Buy Price": h["Buy Price"],
                "Current Price": cur_price,
                "P&L (%)": round(pnl_pct, 2) if pnl_pct is not None else None,
                "P&L ($)": round(pnl_amt, 2) if pnl_amt is not None else None,
                "Buy Date": h["Buy Date"],
            })
        holdings_df = pd.DataFrame(holdings_rows)

        with st.container(border=True):
            st.write("**Current holdings — unrealized profit/loss**")
            st.dataframe(
                style_portfolio_table(holdings_df, ["P&L (%)", "P&L ($)"]),
                hide_index=True,
                width="stretch",
                row_height=90,
                height="content",
                column_config={
                    "Ticker": st.column_config.TextColumn("Ticker", pinned=True, width=150),
                    "Shares": st.column_config.NumberColumn("Shares", format="%.4f"),
                    "Buy Price": st.column_config.NumberColumn("Buy price", format="$%.2f"),
                    "Current Price": st.column_config.NumberColumn("Current price", format="$%.2f"),
                    "P&L (%)": st.column_config.NumberColumn("P&L (%)", format="%.2f%%"),
                    "P&L ($)": st.column_config.NumberColumn("P&L ($)", format="$%.2f"),
                    "Buy Date": st.column_config.DateColumn("Buy date"),
                },
            )

            st.write("**Sold a position? Record it here to remove it and log the result:**")
            with st.form("sell_holding_form", clear_on_submit=True):
                sc1, sc2, sc3 = st.columns(3)
                with sc1:
                    sell_idx = st.selectbox(
                        "Holding to sell",
                        options=range(len(st.session_state.holdings)),
                        format_func=lambda i: (
                            f"{st.session_state.holdings[i]['Ticker']} — "
                            f"{st.session_state.holdings[i]['Shares']} sh @ "
                            f"${st.session_state.holdings[i]['Buy Price']:.2f} "
                            f"(bought {st.session_state.holdings[i]['Buy Date']})"
                        ),
                    )
                with sc2:
                    sell_price = st.number_input("Sell price ($)", min_value=0.01, value=100.0, step=0.01)
                with sc3:
                    sell_date = st.date_input("Sell date", value=date.today())

                if st.form_submit_button("Sell / remove", icon=":material/sell:", width="stretch"):
                    sold = st.session_state.holdings.pop(sell_idx)
                    realized_pct = (sell_price - sold["Buy Price"]) / sold["Buy Price"] * 100
                    realized_amt = (sell_price - sold["Buy Price"]) * sold["Shares"]
                    st.session_state.sold_history.append({
                        "Ticker": sold["Ticker"],
                        "Shares": sold["Shares"],
                        "Buy Price": sold["Buy Price"],
                        "Sell Price": sell_price,
                        "P&L (%)": round(realized_pct, 2),
                        "P&L ($)": round(realized_amt, 2),
                        "Buy Date": sold["Buy Date"],
                        "Sell Date": sell_date.isoformat(),
                    })
                    save_json(HOLDINGS_FILE, st.session_state.holdings)
                    save_json(SOLD_FILE, st.session_state.sold_history)
                    st.toast(f"Recorded sale of {sold['Ticker']}", icon=":material/check_circle:")
                    st.rerun()

            st.write("**Added one by mistake? Remove it (no sale recorded):**")
            with st.form("remove_holding_form", clear_on_submit=True):
                remove_idx = st.selectbox(
                    "Holding to remove",
                    options=range(len(st.session_state.holdings)),
                    format_func=lambda i: (
                        f"{st.session_state.holdings[i]['Ticker']} — "
                        f"{st.session_state.holdings[i]['Shares']} sh @ "
                        f"${st.session_state.holdings[i]['Buy Price']:.2f} "
                        f"(bought {st.session_state.holdings[i]['Buy Date']})"
                    ),
                    key="remove_idx",
                )
                if st.form_submit_button("Remove entry", icon=":material/delete:", width="stretch"):
                    removed = st.session_state.holdings.pop(remove_idx)
                    save_json(HOLDINGS_FILE, st.session_state.holdings)
                    st.toast(f"Removed {removed['Ticker']} — no sale recorded", icon=":material/delete:")
                    st.rerun()
    else:
        st.info("You don't have any holdings yet — add one above.", icon=":material/info:")

    if st.session_state.sold_history:
        with st.container(border=True):
            st.write("**Realized profit/loss by year**")
            sold_df = pd.DataFrame(st.session_state.sold_history)
            sold_df["Sell Date"] = pd.to_datetime(sold_df["Sell Date"])
            sold_df["Year"] = sold_df["Sell Date"].dt.year
            sold_df["Invested"] = sold_df["Buy Price"] * sold_df["Shares"]

            yearly = (
                sold_df.groupby("Year")
                .agg(Trades=("Ticker", "count"), Realized=("P&L ($)", "sum"), Invested=("Invested", "sum"))
                .reset_index()
            )
            yearly["Realized P&L (%)"] = (yearly["Realized"] / yearly["Invested"] * 100).round(2)
            yearly["Realized P&L ($)"] = yearly["Realized"].round(2)
            yearly = yearly.sort_values("Year", ascending=False)[["Year", "Trades", "Realized P&L ($)", "Realized P&L (%)"]]

            total_realized = sold_df["P&L ($)"].sum()
            st.metric("Total realized P&L (all years)", f"${total_realized:+.2f}", border=True)

            st.dataframe(
                yearly.style
                    .set_properties(**BASE_VALUE_STYLE)
                    .set_properties(subset=["Year"], **TICKER_STYLE)
                    .map(style_change, subset=["Realized P&L ($)", "Realized P&L (%)"]),
                hide_index=True,
                width="stretch",
                row_height=90,
                height="content",
                column_config={
                    "Year": st.column_config.NumberColumn("Year", format="%d", pinned=True, width=150),
                    "Trades": st.column_config.NumberColumn("Trades sold"),
                    "Realized P&L ($)": st.column_config.NumberColumn("Realized P&L ($)", format="$%.2f"),
                    "Realized P&L (%)": st.column_config.NumberColumn("Realized P&L (%)", format="%.2f%%"),
                },
            )

            yearly_asc = yearly.sort_values("Year")
            fig_yearly = px.bar(yearly_asc, x="Year", y="Realized P&L ($)", text="Realized P&L ($)")
            fig_yearly.update_traces(
                marker_color=["#00CC96" if v >= 0 else "#EF553B" for v in yearly_asc["Realized P&L ($)"]],
                marker_line_width=0,
                texttemplate="$%{text:.2f}",
                textposition="outside",
                textfont=dict(size=13, family="Arial"),
            )
            fig_yearly.update_layout(
                showlegend=False,
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                margin=dict(l=10, r=10, t=10, b=10),
                font=dict(family="Arial", size=13),
                xaxis=dict(title=None, tickfont=dict(size=13), type="category"),
                yaxis=dict(title=None, showgrid=False, zeroline=False, showticklabels=False),
            )
            st.plotly_chart(fig_yearly, width="stretch")

            with st.expander("Full sold history log (every trade)"):
                st.dataframe(
                    style_portfolio_table(
                        sold_df[["Ticker", "Shares", "Buy Price", "Sell Price", "P&L (%)", "P&L ($)", "Buy Date", "Sell Date"]],
                        ["P&L (%)", "P&L ($)"],
                    ),
                    hide_index=True,
                    width="stretch",
                    row_height=90,
                    height="content",
                    column_config={
                        "Ticker": st.column_config.TextColumn("Ticker", pinned=True, width=150),
                        "Shares": st.column_config.NumberColumn("Shares", format="%.4f"),
                        "Buy Price": st.column_config.NumberColumn("Buy price", format="$%.2f"),
                        "Sell Price": st.column_config.NumberColumn("Sell price", format="$%.2f"),
                        "P&L (%)": st.column_config.NumberColumn("P&L (%)", format="%.2f%%"),
                        "P&L ($)": st.column_config.NumberColumn("P&L ($)", format="$%.2f"),
                        "Buy Date": st.column_config.DateColumn("Buy date"),
                        "Sell Date": st.column_config.DateColumn("Sell date"),
                    },
                )

                st.write("**Made a mistake? Delete a sold entry:**")
                with st.form("delete_sold_form", clear_on_submit=True):
                    del_idx = st.selectbox(
                        "Entry to delete",
                        options=range(len(st.session_state.sold_history)),
                        format_func=lambda i: (
                            f"{st.session_state.sold_history[i]['Ticker']} — "
                            f"{st.session_state.sold_history[i]['Shares']} sh, bought "
                            f"${st.session_state.sold_history[i]['Buy Price']:.2f}, sold "
                            f"${st.session_state.sold_history[i]['Sell Price']:.2f} "
                            f"on {st.session_state.sold_history[i]['Sell Date']}"
                        ),
                    )
                    if st.form_submit_button("Delete entry", icon=":material/delete:", width="stretch"):
                        removed = st.session_state.sold_history.pop(del_idx)
                        save_json(SOLD_FILE, st.session_state.sold_history)
                        st.toast(f"Deleted {removed['Ticker']} sold entry", icon=":material/delete:")
                        st.rerun()
