from __future__ import annotations

from app.schemas.research import BarRecord


def _generate_monthly_series(symbol: str, start_close: float, monthly_returns: list[float], base_volume: float) -> list[BarRecord]:
    rows: list[BarRecord] = []
    year = 2020
    month = 1
    previous_close = start_close

    for index, monthly_return in enumerate(monthly_returns):
        close = previous_close * (1 + monthly_return)
        open_price = previous_close * (1 + (monthly_return * 0.25))
        high = max(open_price, close) * 1.02
        low = min(open_price, close) * 0.98
        volume = base_volume * (1 + (((index % 6) - 2) * 0.035))
        rows.append(
            BarRecord(
                date=f"{year:04d}-{month:02d}-02",
                open=round(open_price, 4),
                high=round(high, 4),
                low=round(low, 4),
                close=round(close, 4),
                volume=round(volume),
            )
        )
        previous_close = close
        month += 1
        if month > 12:
            month = 1
            year += 1

    return rows


def _expand_with_regime(base_pattern: list[float], year_adjustments: list[float]) -> list[float]:
    series: list[float] = []
    for year_index, adjustment in enumerate(year_adjustments):
        for month_index, base_return in enumerate(base_pattern):
            seasonal_tilt = ((month_index % 4) - 1.5) * 0.0015
            regime_wave = (((year_index + month_index) % 5) - 2) * 0.0008
            series.append(round(base_return + adjustment + seasonal_tilt + regime_wave, 6))
    return series


YEAR_ADJUSTMENTS = [-0.004, -0.002, 0.0, 0.003, 0.006, 0.002, -0.001, 0.004, 0.007, 0.001]

SPY_RETURNS = _expand_with_regime([0.02, -0.03, 0.04, 0.015, -0.02, 0.03, 0.025, -0.01, 0.018, 0.012, 0.02, 0.008], YEAR_ADJUSTMENTS)
XLK_RETURNS = _expand_with_regime([0.03, -0.025, 0.05, 0.022, -0.01, 0.038, 0.03, -0.012, 0.024, 0.016, 0.028, 0.014], [adjustment + 0.002 for adjustment in YEAR_ADJUSTMENTS])
XLF_RETURNS = _expand_with_regime([0.012, -0.018, 0.026, 0.014, -0.022, 0.021, 0.018, -0.009, 0.017, 0.011, 0.016, 0.009], [adjustment - 0.001 for adjustment in YEAR_ADJUSTMENTS])
XLV_RETURNS = _expand_with_regime([0.01, -0.008, 0.018, 0.013, -0.006, 0.014, 0.012, -0.004, 0.011, 0.01, 0.012, 0.008], [adjustment - 0.0005 for adjustment in YEAR_ADJUSTMENTS])
XLE_RETURNS = _expand_with_regime([0.025, -0.04, 0.035, 0.018, -0.03, 0.028, -0.01, -0.02, 0.03, 0.022, 0.018, 0.014], [adjustment + ((index % 3) - 1) * 0.002 for index, adjustment in enumerate(YEAR_ADJUSTMENTS)])
XLI_RETURNS = _expand_with_regime([0.015, -0.02, 0.03, 0.016, -0.018, 0.024, 0.02, -0.008, 0.019, 0.013, 0.018, 0.011], YEAR_ADJUSTMENTS)
QQQ_RETURNS = _expand_with_regime([0.032, -0.028, 0.048, 0.025, -0.012, 0.04, 0.034, -0.014, 0.026, 0.017, 0.03, 0.016], [adjustment + 0.003 for adjustment in YEAR_ADJUSTMENTS])
IWM_RETURNS = _expand_with_regime([0.008, -0.026, 0.022, 0.012, -0.024, 0.019, 0.014, -0.011, 0.015, 0.009, 0.013, 0.007], [adjustment - 0.0015 for adjustment in YEAR_ADJUSTMENTS])

AAPL_RETURNS = _expand_with_regime([0.034, -0.031, 0.058, 0.024, -0.012, 0.042, 0.036, -0.015, 0.029, 0.019, 0.032, 0.018], [adjustment + 0.002 for adjustment in YEAR_ADJUSTMENTS])
MSFT_RETURNS = _expand_with_regime([0.031, -0.022, 0.046, 0.021, -0.009, 0.036, 0.031, -0.011, 0.024, 0.017, 0.029, 0.016], [adjustment + 0.0015 for adjustment in YEAR_ADJUSTMENTS])
NVDA_RETURNS = _expand_with_regime([0.062, -0.048, 0.094, 0.041, -0.018, 0.073, 0.058, -0.024, 0.047, 0.031, 0.053, 0.026], [adjustment + ((index % 4) * 0.002) for index, adjustment in enumerate(YEAR_ADJUSTMENTS)])
AMZN_RETURNS = _expand_with_regime([0.036, -0.029, 0.054, 0.026, -0.013, 0.043, 0.035, -0.016, 0.028, 0.019, 0.031, 0.017], [adjustment + 0.001 for adjustment in YEAR_ADJUSTMENTS])
AVGO_RETURNS = _expand_with_regime([0.038, -0.03, 0.061, 0.029, -0.011, 0.046, 0.039, -0.016, 0.031, 0.02, 0.033, 0.019], [adjustment + 0.0025 for adjustment in YEAR_ADJUSTMENTS])
JPM_RETURNS = _expand_with_regime([0.018, -0.017, 0.029, 0.016, -0.018, 0.022, 0.02, -0.009, 0.019, 0.013, 0.018, 0.01], YEAR_ADJUSTMENTS)
BAC_RETURNS = _expand_with_regime([0.017, -0.021, 0.031, 0.017, -0.024, 0.024, 0.021, -0.011, 0.02, 0.012, 0.019, 0.009], [adjustment - 0.001 for adjustment in YEAR_ADJUSTMENTS])
WFC_RETURNS = _expand_with_regime([0.015, -0.019, 0.027, 0.015, -0.023, 0.022, 0.019, -0.01, 0.018, 0.011, 0.017, 0.009], [adjustment - 0.0005 for adjustment in YEAR_ADJUSTMENTS])
GS_RETURNS = _expand_with_regime([0.02, -0.016, 0.032, 0.018, -0.02, 0.025, 0.022, -0.01, 0.02, 0.013, 0.019, 0.011], [adjustment + 0.001 for adjustment in YEAR_ADJUSTMENTS])
LLY_RETURNS = _expand_with_regime([0.024, -0.01, 0.029, 0.019, -0.005, 0.023, 0.021, -0.004, 0.018, 0.015, 0.019, 0.014], [adjustment + 0.0015 for adjustment in YEAR_ADJUSTMENTS])
UNH_RETURNS = _expand_with_regime([0.013, -0.009, 0.02, 0.014, -0.007, 0.016, 0.013, -0.004, 0.012, 0.011, 0.013, 0.009], [adjustment - 0.0005 for adjustment in YEAR_ADJUSTMENTS])
JNJ_RETURNS = _expand_with_regime([0.009, -0.007, 0.014, 0.011, -0.005, 0.012, 0.01, -0.003, 0.009, 0.008, 0.01, 0.007], [adjustment - 0.001 for adjustment in YEAR_ADJUSTMENTS])
ABBV_RETURNS = _expand_with_regime([0.012, -0.008, 0.017, 0.012, -0.006, 0.014, 0.011, -0.004, 0.011, 0.009, 0.011, 0.008], YEAR_ADJUSTMENTS)
XOM_RETURNS = _expand_with_regime([0.028, -0.038, 0.039, 0.019, -0.032, 0.03, -0.011, -0.021, 0.031, 0.023, 0.02, 0.015], [adjustment + ((index % 3) - 1) * 0.0018 for index, adjustment in enumerate(YEAR_ADJUSTMENTS)])
CVX_RETURNS = _expand_with_regime([0.024, -0.033, 0.034, 0.018, -0.029, 0.026, -0.009, -0.018, 0.027, 0.02, 0.017, 0.013], [adjustment + ((index % 4) - 1.5) * 0.0012 for index, adjustment in enumerate(YEAR_ADJUSTMENTS)])
COP_RETURNS = _expand_with_regime([0.031, -0.042, 0.043, 0.022, -0.034, 0.033, -0.012, -0.022, 0.034, 0.025, 0.021, 0.016], [adjustment + ((index % 5) - 2) * 0.0015 for index, adjustment in enumerate(YEAR_ADJUSTMENTS)])
SLB_RETURNS = _expand_with_regime([0.022, -0.036, 0.032, 0.017, -0.031, 0.027, -0.013, -0.024, 0.029, 0.021, 0.018, 0.014], [adjustment + ((index % 3) - 1) * 0.001 for index, adjustment in enumerate(YEAR_ADJUSTMENTS)])
GE_RETURNS = _expand_with_regime([0.022, -0.019, 0.034, 0.018, -0.017, 0.027, 0.022, -0.009, 0.02, 0.014, 0.019, 0.012], [adjustment + 0.001 for adjustment in YEAR_ADJUSTMENTS])
CAT_RETURNS = _expand_with_regime([0.018, -0.022, 0.031, 0.017, -0.02, 0.025, 0.021, -0.009, 0.019, 0.013, 0.018, 0.011], YEAR_ADJUSTMENTS)
HON_RETURNS = _expand_with_regime([0.014, -0.017, 0.025, 0.015, -0.016, 0.021, 0.018, -0.008, 0.017, 0.012, 0.016, 0.01], [adjustment - 0.0005 for adjustment in YEAR_ADJUSTMENTS])
UNP_RETURNS = _expand_with_regime([0.015, -0.018, 0.027, 0.016, -0.017, 0.022, 0.019, -0.008, 0.018, 0.012, 0.017, 0.01], YEAR_ADJUSTMENTS)
URI_RETURNS = _expand_with_regime([0.021, -0.028, 0.033, 0.019, -0.026, 0.028, 0.022, -0.012, 0.021, 0.014, 0.019, 0.011], [adjustment + 0.0008 for adjustment in YEAR_ADJUSTMENTS])
EME_RETURNS = _expand_with_regime([0.024, -0.026, 0.035, 0.021, -0.022, 0.03, 0.024, -0.011, 0.022, 0.015, 0.02, 0.012], [adjustment + 0.0012 for adjustment in YEAR_ADJUSTMENTS])
GDDY_RETURNS = _expand_with_regime([0.023, -0.024, 0.036, 0.022, -0.019, 0.029, 0.025, -0.012, 0.023, 0.016, 0.021, 0.013], [adjustment + 0.0015 for adjustment in YEAR_ADJUSTMENTS])
TTWO_RETURNS = _expand_with_regime([0.019, -0.027, 0.034, 0.02, -0.021, 0.027, 0.023, -0.013, 0.02, 0.014, 0.019, 0.012], [adjustment + 0.0006 for adjustment in YEAR_ADJUSTMENTS])
# Additional US sector ETFs used in strategy-lab tests
XLB_RETURNS = _expand_with_regime([0.016, -0.021, 0.028, 0.015, -0.019, 0.022, 0.018, -0.008, 0.017, 0.012, 0.016, 0.01], [adjustment - 0.0005 for adjustment in YEAR_ADJUSTMENTS])
XLP_RETURNS = _expand_with_regime([0.009, -0.007, 0.013, 0.01, -0.006, 0.011, 0.009, -0.003, 0.009, 0.008, 0.009, 0.007], [adjustment - 0.002 for adjustment in YEAR_ADJUSTMENTS])
XLU_RETURNS = _expand_with_regime([0.008, -0.009, 0.012, 0.009, -0.008, 0.01, 0.008, -0.004, 0.008, 0.007, 0.008, 0.006], [adjustment - 0.0025 for adjustment in YEAR_ADJUSTMENTS])
XLY_RETURNS = _expand_with_regime([0.022, -0.026, 0.038, 0.019, -0.021, 0.029, 0.024, -0.011, 0.021, 0.014, 0.02, 0.012], [adjustment + 0.001 for adjustment in YEAR_ADJUSTMENTS])
# UCITS ETF proxies used in strategy-lab peer group tests (European-listed instruments)
IUFS_RETURNS = _expand_with_regime([0.013, -0.016, 0.024, 0.013, -0.017, 0.019, 0.016, -0.008, 0.015, 0.01, 0.014, 0.009], [adjustment - 0.001 for adjustment in YEAR_ADJUSTMENTS])
IUHC_RETURNS = _expand_with_regime([0.011, -0.009, 0.017, 0.012, -0.007, 0.013, 0.011, -0.004, 0.01, 0.009, 0.011, 0.008], [adjustment - 0.0008 for adjustment in YEAR_ADJUSTMENTS])
VDST_RETURNS = _expand_with_regime([0.028, -0.023, 0.044, 0.02, -0.009, 0.034, 0.028, -0.011, 0.022, 0.015, 0.026, 0.013], [adjustment + 0.0018 for adjustment in YEAR_ADJUSTMENTS])
VUAA_RETURNS = _expand_with_regime([0.019, -0.027, 0.036, 0.016, -0.018, 0.028, 0.022, -0.009, 0.019, 0.013, 0.018, 0.011], [adjustment + 0.0005 for adjustment in YEAR_ADJUSTMENTS])
BTEC_RETURNS = _expand_with_regime([0.031, -0.025, 0.048, 0.023, -0.011, 0.037, 0.031, -0.013, 0.025, 0.017, 0.028, 0.015], [adjustment + 0.002 for adjustment in YEAR_ADJUSTMENTS])

SAMPLE_ETF_HOLDINGS: dict[str, list[dict[str, str | float]]] = {
    "SPY": [
        {"symbol": "MSFT", "name": "Microsoft", "weight": 0.27},
        {"symbol": "AAPL", "name": "Apple", "weight": 0.25},
        {"symbol": "NVDA", "name": "NVIDIA", "weight": 0.24},
        {"symbol": "AMZN", "name": "Amazon", "weight": 0.24},
    ],
    "QQQ": [
        {"symbol": "MSFT", "name": "Microsoft", "weight": 0.28},
        {"symbol": "AAPL", "name": "Apple", "weight": 0.25},
        {"symbol": "NVDA", "name": "NVIDIA", "weight": 0.24},
        {"symbol": "AMZN", "name": "Amazon", "weight": 0.23},
    ],
    "XLK": [
        {"symbol": "MSFT", "name": "Microsoft", "weight": 0.29},
        {"symbol": "AAPL", "name": "Apple", "weight": 0.27},
        {"symbol": "NVDA", "name": "NVIDIA", "weight": 0.24},
        {"symbol": "AVGO", "name": "Broadcom", "weight": 0.20},
    ],
    "XLF": [
        {"symbol": "JPM", "name": "JPMorgan Chase", "weight": 0.31},
        {"symbol": "BAC", "name": "Bank of America", "weight": 0.25},
        {"symbol": "WFC", "name": "Wells Fargo", "weight": 0.23},
        {"symbol": "GS", "name": "Goldman Sachs", "weight": 0.21},
    ],
    "XLV": [
        {"symbol": "LLY", "name": "Eli Lilly", "weight": 0.32},
        {"symbol": "UNH", "name": "UnitedHealth", "weight": 0.26},
        {"symbol": "JNJ", "name": "Johnson & Johnson", "weight": 0.22},
        {"symbol": "ABBV", "name": "AbbVie", "weight": 0.20},
    ],
    "XLE": [
        {"symbol": "XOM", "name": "Exxon Mobil", "weight": 0.34},
        {"symbol": "CVX", "name": "Chevron", "weight": 0.27},
        {"symbol": "COP", "name": "ConocoPhillips", "weight": 0.22},
        {"symbol": "SLB", "name": "SLB", "weight": 0.17},
    ],
    "XLI": [
        {"symbol": "GE", "name": "GE Aerospace", "weight": 0.29},
        {"symbol": "CAT", "name": "Caterpillar", "weight": 0.26},
        {"symbol": "HON", "name": "Honeywell", "weight": 0.24},
        {"symbol": "UNP", "name": "Union Pacific", "weight": 0.21},
    ],
    "IWM": [
        {"symbol": "URI", "name": "United Rentals", "weight": 0.28},
        {"symbol": "EME", "name": "EMCOR", "weight": 0.25},
        {"symbol": "GDDY", "name": "GoDaddy", "weight": 0.24},
        {"symbol": "TTWO", "name": "Take-Two", "weight": 0.23},
    ],
}

SAMPLE_ETF_HOLDINGS_BY_DATE: dict[str, list[tuple[str, list[dict[str, str | float]]]]] = {
    "QQQ": [
        ("2020-01-02", [
            {"symbol": "MSFT", "name": "Microsoft", "weight": 0.29},
            {"symbol": "AAPL", "name": "Apple", "weight": 0.28},
            {"symbol": "AMZN", "name": "Amazon", "weight": 0.23},
            {"symbol": "NVDA", "name": "NVIDIA", "weight": 0.20},
        ]),
        ("2023-01-02", [
            {"symbol": "MSFT", "name": "Microsoft", "weight": 0.28},
            {"symbol": "AAPL", "name": "Apple", "weight": 0.25},
            {"symbol": "NVDA", "name": "NVIDIA", "weight": 0.24},
            {"symbol": "AMZN", "name": "Amazon", "weight": 0.23},
        ]),
    ],
    "XLK": [
        ("2020-01-02", [
            {"symbol": "AAPL", "name": "Apple", "weight": 0.31},
            {"symbol": "MSFT", "name": "Microsoft", "weight": 0.28},
            {"symbol": "NVDA", "name": "NVIDIA", "weight": 0.18},
            {"symbol": "AVGO", "name": "Broadcom", "weight": 0.23},
        ]),
        ("2023-01-02", [
            {"symbol": "MSFT", "name": "Microsoft", "weight": 0.29},
            {"symbol": "AAPL", "name": "Apple", "weight": 0.27},
            {"symbol": "NVDA", "name": "NVIDIA", "weight": 0.24},
            {"symbol": "AVGO", "name": "Broadcom", "weight": 0.20},
        ]),
    ],
    "XLF": [
        ("2020-01-02", [
            {"symbol": "JPM", "name": "JPMorgan Chase", "weight": 0.28},
            {"symbol": "BAC", "name": "Bank of America", "weight": 0.27},
            {"symbol": "WFC", "name": "Wells Fargo", "weight": 0.24},
            {"symbol": "GS", "name": "Goldman Sachs", "weight": 0.21},
        ]),
        ("2023-01-02", [
            {"symbol": "JPM", "name": "JPMorgan Chase", "weight": 0.31},
            {"symbol": "BAC", "name": "Bank of America", "weight": 0.25},
            {"symbol": "WFC", "name": "Wells Fargo", "weight": 0.23},
            {"symbol": "GS", "name": "Goldman Sachs", "weight": 0.21},
        ]),
    ],
}


SAMPLE_BAR_SERIES: dict[str, list[BarRecord]] = {
    "ES": [
        BarRecord(date="2024-01-02", open=4800.0, high=4825.0, low=4790.0, close=4810.0, volume=120000),
        BarRecord(date="2024-02-01", open=4810.0, high=4860.0, low=4805.0, close=4850.0, volume=118000),
        BarRecord(date="2024-03-01", open=4850.0, high=4910.0, low=4848.0, close=4905.0, volume=124000),
        BarRecord(date="2024-04-01", open=4905.0, high=4920.0, low=4865.0, close=4878.0, volume=122000),
        BarRecord(date="2024-05-01", open=4878.0, high=4950.0, low=4875.0, close=4940.0, volume=126000),
        BarRecord(date="2024-06-03", open=4940.0, high=5005.0, low=4930.0, close=4998.0, volume=132000),
    ],
    "NQ": [
        BarRecord(date="2024-01-02", open=16700.0, high=16860.0, low=16650.0, close=16820.0, volume=95000),
        BarRecord(date="2024-02-01", open=16820.0, high=17140.0, low=16790.0, close=17080.0, volume=98000),
        BarRecord(date="2024-03-01", open=17080.0, high=17610.0, low=17050.0, close=17540.0, volume=99000),
        BarRecord(date="2024-04-01", open=17540.0, high=17620.0, low=17160.0, close=17210.0, volume=101000),
        BarRecord(date="2024-05-01", open=17210.0, high=17880.0, low=17190.0, close=17770.0, volume=103000),
        BarRecord(date="2024-06-03", open=17770.0, high=18200.0, low=17720.0, close=18140.0, volume=107000),
    ],
    "CL": [
        BarRecord(date="2024-01-02", open=71.2, high=73.1, low=70.9, close=72.8, volume=410000),
        BarRecord(date="2024-02-01", open=72.8, high=75.6, low=72.1, close=74.9, volume=422000),
        BarRecord(date="2024-03-01", open=74.9, high=79.0, low=74.3, close=78.4, volume=430000),
        BarRecord(date="2024-04-01", open=78.4, high=84.2, low=77.9, close=83.7, volume=441000),
        BarRecord(date="2024-05-01", open=83.7, high=84.0, low=79.8, close=80.5, volume=428000),
        BarRecord(date="2024-06-03", open=80.5, high=82.1, low=78.4, close=79.3, volume=419000),
    ],
    "GC": [
        BarRecord(date="2024-01-02", open=2060.0, high=2079.0, low=2050.0, close=2071.0, volume=210000),
        BarRecord(date="2024-02-01", open=2071.0, high=2098.0, low=2062.0, close=2091.0, volume=214000),
        BarRecord(date="2024-03-01", open=2091.0, high=2170.0, low=2087.0, close=2161.0, volume=226000),
        BarRecord(date="2024-04-01", open=2161.0, high=2350.0, low=2158.0, close=2322.0, volume=240000),
        BarRecord(date="2024-05-01", open=2322.0, high=2405.0, low=2288.0, close=2380.0, volume=247000),
        BarRecord(date="2024-06-03", open=2380.0, high=2394.0, low=2312.0, close=2330.0, volume=238000),
    ],
    "SPY": _generate_monthly_series("SPY", 320.0, SPY_RETURNS, 76000000),
    "XLK": _generate_monthly_series("XLK", 110.0, XLK_RETURNS, 11200000),
    "XLF": _generate_monthly_series("XLF", 24.0, XLF_RETURNS, 43500000),
    "XLV": _generate_monthly_series("XLV", 95.0, XLV_RETURNS, 8100000),
    "XLE": _generate_monthly_series("XLE", 52.0, XLE_RETURNS, 18300000),
    "XLI": _generate_monthly_series("XLI", 70.0, XLI_RETURNS, 10100000),
    "QQQ": _generate_monthly_series("QQQ", 220.0, QQQ_RETURNS, 51000000),
    "IWM": _generate_monthly_series("IWM", 150.0, IWM_RETURNS, 32200000),
    "AAPL": _generate_monthly_series("AAPL", 80.0, AAPL_RETURNS, 99000000),
    "MSFT": _generate_monthly_series("MSFT", 115.0, MSFT_RETURNS, 74000000),
    "NVDA": _generate_monthly_series("NVDA", 55.0, NVDA_RETURNS, 82000000),
    "AMZN": _generate_monthly_series("AMZN", 95.0, AMZN_RETURNS, 68000000),
    "AVGO": _generate_monthly_series("AVGO", 140.0, AVGO_RETURNS, 18000000),
    "JPM": _generate_monthly_series("JPM", 82.0, JPM_RETURNS, 21000000),
    "BAC": _generate_monthly_series("BAC", 21.0, BAC_RETURNS, 44000000),
    "WFC": _generate_monthly_series("WFC", 26.0, WFC_RETURNS, 29000000),
    "GS": _generate_monthly_series("GS", 180.0, GS_RETURNS, 4600000),
    "LLY": _generate_monthly_series("LLY", 135.0, LLY_RETURNS, 7600000),
    "UNH": _generate_monthly_series("UNH", 220.0, UNH_RETURNS, 4900000),
    "JNJ": _generate_monthly_series("JNJ", 120.0, JNJ_RETURNS, 9800000),
    "ABBV": _generate_monthly_series("ABBV", 88.0, ABBV_RETURNS, 6300000),
    "XOM": _generate_monthly_series("XOM", 48.0, XOM_RETURNS, 31000000),
    "CVX": _generate_monthly_series("CVX", 92.0, CVX_RETURNS, 14000000),
    "COP": _generate_monthly_series("COP", 44.0, COP_RETURNS, 9500000),
    "SLB": _generate_monthly_series("SLB", 23.0, SLB_RETURNS, 17000000),
    "GE": _generate_monthly_series("GE", 54.0, GE_RETURNS, 7200000),
    "CAT": _generate_monthly_series("CAT", 105.0, CAT_RETURNS, 3400000),
    "HON": _generate_monthly_series("HON", 130.0, HON_RETURNS, 2800000),
    "UNP": _generate_monthly_series("UNP", 118.0, UNP_RETURNS, 2600000),
    "URI": _generate_monthly_series("URI", 120.0, URI_RETURNS, 1500000),
    "EME": _generate_monthly_series("EME", 95.0, EME_RETURNS, 1200000),
    "GDDY": _generate_monthly_series("GDDY", 70.0, GDDY_RETURNS, 1100000),
    "TTWO": _generate_monthly_series("TTWO", 82.0, TTWO_RETURNS, 1300000),
    # Additional US sector ETFs
    "XLB": _generate_monthly_series("XLB", 60.0, XLB_RETURNS, 5200000),
    "XLP": _generate_monthly_series("XLP", 68.0, XLP_RETURNS, 9800000),
    "XLU": _generate_monthly_series("XLU", 58.0, XLU_RETURNS, 7100000),
    "XLY": _generate_monthly_series("XLY", 140.0, XLY_RETURNS, 6400000),
    # UCITS ETF proxies for peer-group strategy-lab tests
    "IUFS": _generate_monthly_series("IUFS", 34.0, IUFS_RETURNS, 1800000),
    "IUHC": _generate_monthly_series("IUHC", 42.0, IUHC_RETURNS, 1500000),
    "VDST": _generate_monthly_series("VDST", 55.0, VDST_RETURNS, 2100000),
    "VUAA": _generate_monthly_series("VUAA", 72.0, VUAA_RETURNS, 3400000),
    "BTEC": _generate_monthly_series("BTEC", 48.0, BTEC_RETURNS, 1600000),
}

SAMPLE_FUTURES_BARS = SAMPLE_BAR_SERIES
