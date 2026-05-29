import os
from dataclasses import asdict
import anthropic
from schemas import SynthesisInput, SynthesisOutput


# Weighting guidelines by time horizon:
#   Short  (< 1 week):  news 50%, market 40%, fundamentals 10%
#   Medium (1w – 1mo):  news 30%, market 40%, fundamentals 30%
#   Long   (> 1 month): news 10%, market 30%, fundamentals 60%
SYNTHESIS_SYSTEM_PROMPT = """\
You are a financial signal synthesis engine. You receive three independent research signals:

1. News & Events — catalysts and market sentiment from recent headlines
2. Market Behavior — price trends, momentum, and volatility
3. Fundamentals — revenue, profit, and balance-sheet health

Your responsibilities:
- Weight each signal appropriately for the stated time horizon
- Detect whether signals agree or conflict
- Produce a single weighted_score from -1.0 (strongly bearish) to 1.0 (strongly bullish)
- Explain your synthesis reasoning concisely

Weighting guidelines:
- Short-term  (< 1 week):  news 50%, market 40%, fundamentals 10%
- Medium-term (1 week – 1 month): news 30%, market 40%, fundamentals 30%
- Long-term   (> 1 month): news 10%, market 30%, fundamentals 60%

signal_agreement values:
- "strong"      — all three signals point the same direction
- "moderate"    — two of three signals agree
- "weak"        — signals are mixed but not directly contradictory
- "conflicting" — signals point in opposite directions
"""

SYNTHESIS_TOOL = {
    "name": "synthesize_signals",
    "description": "Combine three research signals into a single weighted directional score.",
    "input_schema": {
        "type": "object",
        "properties": {
            "weighted_score": {
                "type": "number",
                "description": "Combined directional score from -1.0 (strongly bearish) to 1.0 (strongly bullish)."
            },
            "weights": {
                "type": "object",
                "description": "Weights actually applied, e.g. {\"news\": 0.4, \"market\": 0.4, \"fundamentals\": 0.2}.",
                "properties": {
                    "news":          {"type": "number"},
                    "market":        {"type": "number"},
                    "fundamentals":  {"type": "number"}
                },
                "required": ["news", "market", "fundamentals"]
            },
            "signal_agreement": {
                "type": "string",
                "enum": ["strong", "moderate", "weak", "conflicting"],
                "description": "How well the three signals agree with each other."
            },
            "synthesis_narrative": {
                "type": "string",
                "description": "2-4 sentence explanation of the synthesis reasoning and any notable conflicts."
            }
        },
        "required": ["weighted_score", "weights", "signal_agreement", "synthesis_narrative"]
    }
}


class SynthesisAgent:
    def __init__(self, api_key: str | None = None, model: str = "claude-sonnet-4-6"):
        self.client = anthropic.Anthropic(api_key=api_key or os.environ["ANTHROPIC_API_KEY"])
        self.model = model

    def run(self, synthesis_input: SynthesisInput) -> SynthesisOutput:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=SYNTHESIS_SYSTEM_PROMPT,
            tools=[SYNTHESIS_TOOL],
            tool_choice={"type": "tool", "name": "synthesize_signals"},
            messages=[{"role": "user", "content": self._build_prompt(synthesis_input)}],
        )

        tool_block = next(b for b in response.content if b.type == "tool_use")
        result = tool_block.input

        return SynthesisOutput(
            question=synthesis_input.question,
            ticker=synthesis_input.ticker,
            time_horizon=synthesis_input.time_horizon,
            weighted_score=result["weighted_score"],
            weights=result["weights"],
            signal_agreement=result["signal_agreement"],
            synthesis_narrative=result["synthesis_narrative"],
            raw_signals={
                "news":          asdict(synthesis_input.news_signal),
                "market":        asdict(synthesis_input.market_signal),
                "fundamentals":  asdict(synthesis_input.fundamentals_signal),
            },
        )

    def _build_prompt(self, inp: SynthesisInput) -> str:
        n = inp.news_signal
        m = inp.market_signal
        f = inp.fundamentals_signal
        return f"""\
Synthesize the following signals for this prediction question:

Question:      {inp.question}
Ticker:        {inp.ticker}
Time horizon:  {inp.time_horizon}

--- News & Events Signal ---
Sentiment:  {n.sentiment:+.2f}  (-1 = bearish, +1 = bullish)
Summary:    {n.headline_summary}
Confidence: {n.confidence:.0%}

--- Market Behavior Signal ---
Trend:      {m.trend:+.2f}
Volatility: {m.volatility:.2f}  (0 = calm, 1 = extreme)
Momentum:   {m.momentum:+.2f}
Summary:    {m.summary}
Confidence: {m.confidence:.0%}

--- Fundamentals Signal ---
Score:          {f.score:+.2f}
Revenue trend:  {f.revenue_trend}
Summary:        {f.summary}
Confidence:     {f.confidence:.0%}

Apply weights appropriate for a {inp.time_horizon} horizon and call synthesize_signals."""


if __name__ == "__main__":
    from schemas import NewsSignal, MarketSignal, FundamentalsSignal

    sample_input = SynthesisInput(
        question="Will MSFT be up in a week?",
        ticker="MSFT",
        time_horizon="1 week",
        news_signal=NewsSignal(
            sentiment=0.6,
            headline_summary="Microsoft beat earnings estimates; Azure growth accelerated to 31%.",
            confidence=0.8,
        ),
        market_signal=MarketSignal(
            trend=0.4,
            volatility=0.3,
            momentum=0.5,
            summary="Price broke above 50-day MA on elevated volume; RSI at 62.",
            confidence=0.75,
        ),
        fundamentals_signal=FundamentalsSignal(
            score=0.7,
            revenue_trend="positive",
            summary="Q3 revenue up 17% YoY; operating margins expanded 200bps.",
            confidence=0.9,
        ),
    )

    agent = SynthesisAgent()
    output = agent.run(sample_input)
    print(f"Weighted score:    {output.weighted_score:+.3f}")
    print(f"Weights:           {output.weights}")
    print(f"Signal agreement:  {output.signal_agreement}")
    print(f"Narrative:\n{output.synthesis_narrative}")
