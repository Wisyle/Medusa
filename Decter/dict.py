# accumulator_config.py
"""
Deriv Accumulator Strategy – Volatility Index Reference
-------------------------------------------------------

Dictionary keyed by symbol.  Each entry supplies the minimum data
needed by an automated accumulator-trading bot.

Fields
------
name                   – Human-readable instrument name
symbol                 – Trading symbol on Deriv
volatility_pct         – Fixed annualised volatility encoded by the index
tick_interval_s        – Seconds between ticks
recommended_growth_pct – Single fixed growth rate (1 ≤ rate ≤ 5) suited to
                         the index’s volatility
risk_level             – Categorical label (“low”, “medium”, “high”, “extreme”)
description            – One-sentence behavioural summary
"""

ACCUMULATOR_INDICES: dict[str, dict] = {
    # ─────────────────────────────── Low volatility ──────────────────────────────
    "R_10": {
        "name": "Volatility 10 Index",
        "symbol": "R_10",
        "volatility_pct": 10,
        "tick_interval_s": 2,
        "recommended_growth_pct": 5,
        "risk_level": "low",
        "description": "Low-volatility synthetic market ticking every 2 s.",
    },
    "1HZ10V": {
        "name": "Volatility 10 (1s) Index",
        "symbol": "1HZ10V",
        "volatility_pct": 10,
        "tick_interval_s": 1,
        "recommended_growth_pct": 5,
        "risk_level": "low",
        "description": "Same underlying as R_10 but updates every second.",
    },
    "R_25": {
        "name": "Volatility 25 Index",
        "symbol": "R_25",
        "volatility_pct": 25,
        "tick_interval_s": 2,
        "recommended_growth_pct": 4,
        "risk_level": "low",
        "description": "Slightly wider swings than Vol 10; still stable.",
    },
    "1HZ25V": {
        "name": "Volatility 25 (1s) Index",
        "symbol": "1HZ25V",
        "volatility_pct": 25,
        "tick_interval_s": 1,
        "recommended_growth_pct": 4,
        "risk_level": "low",
        "description": "Low-volatility one-second stream of Vol 25.",
    },

    # ───────────────────────────── Medium volatility ─────────────────────────────
    "R_50": {
        "name": "Volatility 50 Index",
        "symbol": "R_50",
        "volatility_pct": 50,
        "tick_interval_s": 2,
        "recommended_growth_pct": 3,
        "risk_level": "medium",
        "description": "Balanced instrument with moderate price amplitude.",
    },
    "1HZ50V": {
        "name": "Volatility 50 (1s) Index",
        "symbol": "1HZ50V",
        "volatility_pct": 50,
        "tick_interval_s": 1,
        "recommended_growth_pct": 3,
        "risk_level": "medium",
        "description": "One-second variant of Vol 50; faster compounding.",
    },
    "R_75": {
        "name": "Volatility 75 Index",
        "symbol": "R_75",
        "volatility_pct": 75,
        "tick_interval_s": 2,
        "recommended_growth_pct": 2,
        "risk_level": "high",
        "description": "Sharp swings; suitable for conservative growth rates.",
    },
    "1HZ75V": {
        "name": "Volatility 75 (1s) Index",
        "symbol": "1HZ75V",
        "volatility_pct": 75,
        "tick_interval_s": 1,
        "recommended_growth_pct": 1.5,
        "risk_level": "high",
        "description": "High-risk, rapid-tick version of Vol 75.",
    },

    # ────────────────────────────── High volatility ──────────────────────────────
    "R_100": {
        "name": "Volatility 100 Index",
        "symbol": "R_100",
        "volatility_pct": 100,
        "tick_interval_s": 2,
        "recommended_growth_pct": 1.5,
        "risk_level": "high",
        "description": "Extremely active instrument; tight range tolerance.",
    },
    "1HZ100V": {
        "name": "Volatility 100 (1s) Index",
        "symbol": "1HZ100V",
        "volatility_pct": 100,
        "tick_interval_s": 1,
        "recommended_growth_pct": 1,
        "risk_level": "high",
        "description": "Ultra-fast stream of a 100 %-volatility market.",
    },

    # ──────────────────────────── Extreme volatility ─────────────────────────────
    "1HZ150V": {
        "name": "Volatility 150 (1s) Index",
        "symbol": "1HZ150V",
        "volatility_pct": 150,
        "tick_interval_s": 1,
        "recommended_growth_pct": 1,
        "risk_level": "extreme",
        "description": "Very large price jumps; lowest growth only.",
    },
    "1HZ250V": {
        "name": "Volatility 250 (1s) Index",
        "symbol": "1HZ250V",
        "volatility_pct": 250,
        "tick_interval_s": 1,
        "recommended_growth_pct": 1,
        "risk_level": "extreme",
        "description": "Highest available volatility; survival‐focus trading.",
    },
}

# Convenience helpers
def get_index(symbol: str) -> dict | None:
    """Return the configuration for *symbol*, or None if not found."""
    return ACCUMULATOR_INDICES.get(symbol)

def list_symbols() -> list[str]:
    """Return all available accumulator symbols in sorted order."""
    return sorted(ACCUMULATOR_INDICES.keys())


# ──────────────────────────── Usage example ────────────────────────────
if __name__ == "__main__":
    from pprint import pprint

    pprint(get_index("R_10"))
    print()
    pprint(list_symbols())
