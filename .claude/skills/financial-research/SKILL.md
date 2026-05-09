---
name: financial-research
description: Use when researching factor methodology, ETF/equity universes, market data sources, or quant literature. Triggers on questions about momentum, value, quality, volatility, liquidity factors; FMP vs Alpha Vantage data availability; universe definitions (S&P 500, Russell, sector screens); cross-sectional normalization; or when needing to cite academic precedent for a methodology choice.
---

# Financial Research

Use this skill when the work shifts to quant methodology, factor design, market data sourcing, or academic precedent.

## Output format for research findings

Structure findings so they can flow directly into implementation:

```markdown
## Research: [Topic]
**Date**: [YYYY-MM-DD]
**Data sources**: [FMP, Alpha Vantage, papers]

### Summary
[2-3 sentence executive summary]

### Findings
[Tables, formulas, comparisons]

### Methodology notes
[Caveats, edge cases, data quality]

### Recommended next steps
[Concrete actions for implementation]
```

Cite every data point. Distinguish live vs cached data. Never fabricate values to fill gaps — surface trust state instead.

## Factor families — confirmed formulas

### Momentum
| Factor ID | Formula | Direction | Lookback |
|---|---|---|---|
| `momentum_1m` | trailing 21d price return | higher_is_better | 21d |
| `momentum_3m` | trailing 63d price return | higher_is_better | 63d |
| `momentum_6m` | trailing 126d price return | higher_is_better | 126d |
| `momentum_12m` | trailing 252d price return | higher_is_better | 252d |
| `momentum_12_1` | 12m return skipping last month | higher_is_better | 252d (skip 21d) |

Evidence: Jegadeesh & Titman (1993). Skip-month variant avoids 1m reversal.

### Volatility / risk
| Factor ID | Formula | Direction |
|---|---|---|
| `realized_volatility_126d` | annualized stdev of daily returns | lower_is_better |
| `downside_volatility_126d` | annualized stdev of negative daily returns | lower_is_better |
| `max_drawdown_252d` | peak-to-trough drawdown over window | lower_is_better |

### Liquidity
| Factor ID | Formula | Direction |
|---|---|---|
| `liquidity_60d` | log(1 + median(dollar_volume)) over 60d | higher_is_better |

### Quality (Novy-Marx, Sloan, AQR QMJ)
| Factor ID | Primary formula | Fallback | Direction |
|---|---|---|---|
| `quality_profitability` | (Revenue − COGS) / Total Assets | EBIT / Total Assets | higher_is_better |
| `quality_cash_generation` | OCF / Total Assets | FCF / Total Assets | higher_is_better |
| `quality_accrual` | (Net Income − OCF) / Total Assets | — | lower_is_better (Sloan ratio) |
| `quality_leverage` | (Total Debt − Cash) / Total Assets | — | lower_is_better (net leverage) |

### Value (Greenblatt, Fama-French)
| Factor ID | Formula | Direction | FMP Source |
|---|---|---|---|
| `value_earnings_yield` | EBIT / Enterprise Value | higher_is_better | `key-metrics-ttm` |
| `value_book_to_market` | 1 / P/B | higher_is_better | `ratios-ttm.priceToBookRatioTTM` |
| `value_fcf_yield` | FCF / Market Cap | higher_is_better | `ratios-ttm.priceToFreeCashFlowsRatioTTM` (invert) or `key-metrics-ttm.freeCashFlowYieldTTM` |
| `value_ev_ebitda_inverse` | 1 / (EV/EBITDA) | higher_is_better | `ratios-ttm.enterpriseValueMultipleTTM` (invert) |

EBIT/EV preferred over 1/PE because it's leverage-neutral.

## Data availability — FMP vs Alpha Vantage

| Factor family | FMP | Alpha Vantage | Primary choice |
|---|---|---|---|
| Price history | ✓ `historical-price-eod/light` | ✓ `TIME_SERIES_DAILY_ADJUSTED` | **FMP** (already integrated) |
| Volume / ADV | ✓ same | ✓ same | **FMP** |
| Income / balance / cash flow | ✓ statement endpoints | ✓ same | **FMP** (already integrated) |
| Financial ratios TTM | ✓ `ratios-ttm`, `key-metrics-ttm` | partial via `OVERVIEW` | **FMP** |
| ETF holdings | ✓ `etf-holder` | ✗ | **FMP only** |
| Stock screener | ✓ `stock-screener` | ✗ | **FMP only** |
| News sentiment | ✗ | ✓ `NEWS_SENTIMENT` | **AV only** |
| Earnings transcripts | ✗ | ✓ `EARNINGS_CALL_TRANSCRIPT` | **AV only** |
| Earnings surprise | partial | ✓ `EARNINGS` | **AV** |
| Insider transactions | partial | ✓ `INSIDER_TRANSACTIONS` | **AV** |
| Institutional holdings | ✗ | ✓ `INSTITUTIONAL_HOLDINGS` | **AV only** |

## Universe types — known sources

| Universe kind | Data source | Notes |
|---|---|---|
| `etf_peer_group` | explicit list | already shipped |
| `custom_list` | explicit list | already shipped |
| `broad_equity_screen` | FMP `/stock-screener` | filters: marketCap, volume, exchange, sector, country |
| `sector_screen` | FMP `/stock-screener` + sector filter | GICS sector names |
| `index_constituent` (S&P 500) | FMP `/stable/sp500-constituent` | current snapshot only; use historical endpoint for PIT reconstruction |
| `index_constituent` (Russell 1000) | **No FMP support** — use IWB ETF holdings CSV from BlackRock or `pyndex` package |

For Russell, recommended approach is versioned snapshot: download IWB monthly to `data/universe/russell1000_YYYYMM.csv`.

## Normalization standards

| Method | When to use |
|---|---|
| Cross-sectional z-score | Default for price-based factors (momentum, volatility) |
| Percentile rank (0–1) | Skewed distributions, fundamental factors |
| Min-max | Only for factors with bounded ranges |

Winsorize at ±3σ or 5th/95th percentile before normalizing — required to prevent outliers dominating composite.

## Composite construction

Two patterns from institutional practice:

1. **Independent factors** (current architecture): each factor has user-set weight, composite = weighted sum of normalized scores. Maximum flexibility, transparent.
2. **Two-tier composite** (S&P / AQR QMJ pattern): equal-weight sub-factors within a family (quality, value), then weight family composites at portfolio level. Reduces user-facing dials.

Phase 2 uses pattern 1 — matches existing `component_weights` architecture and avoids baking in fixed sub-weights that may need tuning per asset class.

## MCP tools available

- **alpha-vantage** — live AV API for factors not in FMP (sentiment, transcripts, surprises)
- **brave-search** — papers, methodology references, market commentary
- **fetch** — direct HTTP to any financial API
- **memory** — persist research findings across sessions
- **sequential-thinking** — for multi-step factor design problems

## Key sources

- Novy-Marx (2013) — gross profitability premium
- Sloan (1996) — accrual anomaly
- AQR QMJ (Asness, Frazzini, Pedersen 2019)
- MSCI Quality Indexes Methodology
- Fama-French (1992, 1993) — HML / SMB
- Jegadeesh & Titman (1993) — momentum
- Greenblatt (2005) — Magic Formula (EBIT/EV)
- S&P Quality, Value & Momentum Multi-Factor Index methodology
