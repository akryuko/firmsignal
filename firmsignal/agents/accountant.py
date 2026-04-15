import os
from datetime import datetime

import pandas as pd
import yfinance as yf
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from firmsignal.models import AccountantOutput, PricePoint
from firmsignal.state import FirmState


# ─── Helpers ───────────────────────────────────────────────────────────────────

def _format_number(n: float | None, prefix: str = "$") -> str | None:
    if n is None:
        return None
    if n >= 1e12:
        return f"{prefix}{n/1e12:.2f}T"
    if n >= 1e9:
        return f"{prefix}{n/1e9:.2f}B"
    if n >= 1e6:
        return f"{prefix}{n/1e6:.1f}M"
    return f"{prefix}{n:,.0f}"


def _llm(max_tokens: int = 50):
    # Haiku for everything here — ticker lookup and summary are both lightweight
    return ChatAnthropic(
        model="claude-haiku-4-5-20251001",
        temperature=0,
        max_tokens=max_tokens,
    )


# ─── Step 1: Ticker resolution ─────────────────────────────────────────────────

def _find_ticker(company: str) -> str | None:
    """
    Use Claude Haiku to turn a company name into a ticker symbol.
    Returns None for private companies.

    This is a good example of using an LLM for a task where structured
    knowledge beats web search — Claude knows most public company tickers.
    """
    response = _llm(max_tokens=20).invoke([
        SystemMessage(content=(
            "You are a financial data assistant. "
            "Given a company name, respond with ONLY its primary stock ticker symbol. "
            "Examples: 'Apple' → AAPL, 'Nvidia' → NVDA, 'HSBC' → HSBC. "
            "If the company is private or you are not confident, respond with exactly: UNKNOWN"
        )),
        HumanMessage(content=company),
    ])
    result = response.content.strip().upper().split()[0]
    return None if result == "UNKNOWN" else result


# ─── Step 2: yfinance data pull ────────────────────────────────────────────────

def _pull_data(ticker_str: str) -> tuple[dict, list[PricePoint]] | None:
    """
    Pulls fundamentals + 5-year monthly price history from yfinance.

    Returns None if the ticker resolves to an empty dataset — this happens
    when Claude returns a plausible-sounding but wrong ticker. The node
    handles this by treating the company as private and continuing cleanly.
    """
    t = yf.Ticker(ticker_str)
    info = t.info

    # yfinance returns a nearly-empty dict for invalid tickers
    # checking three fields gives us enough confidence it's real
    has_price = info.get("currentPrice") or info.get("regularMarketPrice")
    has_cap = info.get("marketCap")
    if not has_price and not has_cap:
        return None

    # 5-year monthly history (≈60 data points)
    hist = t.history(period="5y", interval="1mo")
    price_history = [
        PricePoint(
            date=idx.strftime("%Y-%m"),
            close=round(float(row["Close"]), 2),
        )
        for idx, row in hist.iterrows()
        if not pd.isna(row["Close"])
    ]

    current = has_price

    # Price change calculations
    change_1y = change_5y = None
    if price_history and current:
        if len(price_history) >= 12:
            p1y = price_history[-12].close
            if p1y:
                change_1y = round(((current - p1y) / p1y) * 100, 1)
        p5y = price_history[0].close
        if p5y:
            change_5y = round(((current - p5y) / p5y) * 100, 1)

    gross_margins = info.get("grossMargins")

    fundamentals = {
        "market_cap":       info.get("marketCap"),
        "pe_ratio":         info.get("trailingPE"),
        "revenue_ttm":      info.get("totalRevenue"),
        "gross_margin_pct": round(gross_margins * 100, 1) if gross_margins else None,
        "debt_to_equity":   info.get("debtToEquity"),
        "employee_count":   info.get("fullTimeEmployees"),
        "current_price":    current,
        "currency":         info.get("currency", "USD"),
        "sector":           info.get("sector", ""),
        "industry":         info.get("industry", ""),
        "change_1y":        change_1y,
        "change_5y":        change_5y,
        "analyst_recommendation": info.get("recommendationKey"),
        "analyst_count":          info.get("numberOfAnalystOpinions"),
        "target_price_mean":      info.get("targetMeanPrice"),
        "target_price_high":      info.get("targetHighPrice"),
        "target_price_low":       info.get("targetLowPrice"),
    }

    return fundamentals, price_history


# ─── Step 3: Financial summary ─────────────────────────────────────────────────

def _generate_summary(company: str, ticker: str, f: dict) -> str:
    """
    Claude Haiku writes a 3-sentence analyst-style summary from raw numbers.
    Much better than template strings — it handles edge cases naturally
    (e.g. negative P/E, no revenue data, massive debt).
    """
    metrics_text = (
        f"Ticker: {ticker}\n"
        f"Market cap: {_format_number(f['market_cap'])}\n"
        f"Current price: ${f['current_price']}\n"
        f"P/E ratio: {f['pe_ratio']}\n"
        f"Revenue (TTM): {_format_number(f['revenue_ttm'])}\n"
        f"Gross margin: {f['gross_margin_pct']}%\n"
        f"Debt/Equity: {f['debt_to_equity']}\n"
        f"Employees: {f['employee_count']:,}\n" if f["employee_count"] else ""
        f"1Y price change: {f['change_1y']}%\n"
        f"5Y price change: {f['change_5y']}%\n"
        f"Sector: {f['sector']} / {f['industry']}"
    )

    response = _llm(max_tokens=250).invoke([
        SystemMessage(content=(
            "You are a senior equity research analyst. "
            "Write a concise 3-sentence financial summary of the company based on the metrics below. "
            "Be specific — mention actual numbers. "
            "Highlight one strength and one risk visible in the data. "
            "Do not use bullet points or headers."
        )),
        HumanMessage(content=f"Company: {company}\n\n{metrics_text}"),
    ])
    return response.content.strip()


# ─── The node ─────────────────────────────────────────────────────────────────

def accountant_node(state: FirmState) -> dict:
    """
    LangGraph node — The Accountant.

    Sequence:
    1. Ask Claude Haiku to identify the stock ticker
    2. Pull 5Y monthly price history + fundamentals from yfinance (free)
    3. Ask Claude Haiku to write a 3-sentence financial summary
    4. Return structured AccountantOutput to FirmState

    Private companies get a graceful empty output — the Synthesizer
    handles missing financial data cleanly.
    """
    company = state["company_name"]
    print(f"\n[Accountant] Starting financial research on '{company}'...")

    try:
        # Step 1: Ticker
        ticker = _find_ticker(company)
        if not ticker:
            print(f"[Accountant] '{company}' appears to be private — skipping market data")
            output = AccountantOutput(
                company_name=company,
                is_public=False,
                financial_summary=f"{company} is a private company. No public market data is available.",
            )
            return {"accountant_output": output.model_dump(), "error": None}

        print(f"[Accountant] Ticker resolved: {ticker}")

        # Step 2: yfinance pull
        result = _pull_data(ticker)
        if result is None:
            # Claude returned a wrong ticker — treat as private
            print(f"[Accountant] Ticker {ticker} returned no data — treating as private")
            output = AccountantOutput(
                company_name=company,
                ticker=ticker,
                is_public=False,
                financial_summary="No reliable market data found. The company may be private or delisted.",
            )
            return {"accountant_output": output.model_dump(), "error": None}

        f, price_history = result
        currency = f["currency"]

        print(
            f"[Accountant] {ticker} — "
            f"cap: {_format_number(f['market_cap'])} · "
            f"{len(price_history)} months of price history · "
            f"1Y: {f['change_1y']}%"
        )

        # Step 3: Summary
        summary = _generate_summary(company, ticker, f)

        output = AccountantOutput(
            company_name=company,
            ticker=ticker,
            is_public=True,
            sector=f["sector"],
            industry=f["industry"],
            market_cap=f["market_cap"],
            market_cap_formatted=_format_number(f["market_cap"], prefix="$"),
            pe_ratio=round(f["pe_ratio"], 1) if f["pe_ratio"] else None,
            revenue_ttm=f["revenue_ttm"],
            revenue_formatted=_format_number(f["revenue_ttm"], prefix="$"),
            gross_margin_pct=f["gross_margin_pct"],
            debt_to_equity=round(f["debt_to_equity"], 2) if f["debt_to_equity"] else None,
            employee_count=f["employee_count"],
            current_price=f["current_price"],
            currency=currency,
            price_history=price_history,
            price_change_1y=f["change_1y"],
            price_change_5y=f["change_5y"],
            analyst_recommendation=f.get("analyst_recommendation"),
            analyst_count=f.get("analyst_count"),
            target_price_mean=round(f["target_price_mean"], 2) if f.get("target_price_mean") else None,
            target_price_high=round(f["target_price_high"], 2) if f.get("target_price_high") else None,
            target_price_low=round(f["target_price_low"], 2) if f.get("target_price_low") else None,
            financial_summary=summary,
        )

        return {"accountant_output": output.model_dump(), "error": None}

    except Exception as e:
        print(f"[Accountant] Error: {e}")
        return {"error": f"Accountant failed: {type(e).__name__}: {e}"}