from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class NewsSignal:
    sentiment: float        # -1.0 (bearish) to 1.0 (bullish)
    headline_summary: str   # Key headlines driving sentiment
    confidence: float       # 0.0 to 1.0


@dataclass
class MarketSignal:
    trend: float            # -1.0 (downtrend) to 1.0 (uptrend)
    volatility: float       # 0.0 (calm) to 1.0 (extreme)
    momentum: float         # -1.0 to 1.0
    summary: str
    confidence: float       # 0.0 to 1.0


@dataclass
class FundamentalsSignal:
    score: float            # -1.0 (weak) to 1.0 (strong)
    revenue_trend: str      # "positive", "neutral", or "negative"
    summary: str
    confidence: float       # 0.0 to 1.0


@dataclass
class SynthesisInput:
    question: str           # e.g. "Will MSFT be up in a week?"
    ticker: str             # e.g. "MSFT"
    time_horizon: str       # e.g. "1 week", "1 month"
    news_signal: NewsSignal
    market_signal: MarketSignal
    fundamentals_signal: FundamentalsSignal


@dataclass
class SynthesisOutput:
    question: str
    ticker: str
    time_horizon: str
    weighted_score: float           # -1.0 to 1.0, combined directional signal
    weights: dict                   # {"news": 0.4, "market": 0.4, "fundamentals": 0.2}
    signal_agreement: str           # "strong", "moderate", "weak", "conflicting"
    synthesis_narrative: str        # Reasoning behind the weighting
    raw_signals: dict               # Serialized input signals for downstream use


@dataclass
class ForecastOutput:
    question: str
    ticker: str
    time_horizon: str
    probability: float              # 0.0 to 100.0 — chance the prediction is TRUE
    confidence: str                 # "low", "medium", or "high"
    ci_low: float                   # Lower bound of confidence interval
    ci_high: float                  # Upper bound of confidence interval
    direction: str                  # "bullish", "bearish", or "neutral"
    reasoning: str
    caveats: list

    def to_dict(self) -> dict:
        return asdict(self)
