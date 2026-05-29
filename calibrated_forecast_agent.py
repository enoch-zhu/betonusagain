import os
import anthropic
from schemas import SynthesisOutput, ForecastOutput


# Calibration principles baked into the system prompt so Claude reasons like
# a superforecaster rather than a naive classifier.
FORECAST_SYSTEM_PROMPT = """\
You are a calibrated probabilistic forecaster for financial markets.
You receive a synthesized directional signal and must translate it into a
well-calibrated probability that the stated prediction question is TRUE.

Calibration principles:
- Base rate: most stocks in any given week move up ~50% of the time. Anchor there.
- A neutral weighted_score near 0.0 should produce a probability near 50%.
- Strong signals (|score| > 0.7) with strong agreement can justify 65–80%.
- Probabilities below 15% or above 85% require exceptional, unanimous evidence.
- Higher volatility widens the confidence interval.
- "Conflicting" signal_agreement lowers confidence and pushes probability toward 50%.
- Never conflate direction confidence with magnitude confidence.

Confidence levels:
- "low":    < 60% evidence quality (conflicting signals, low-confidence inputs)
- "medium": 60–80% evidence quality
- "high":   > 80% evidence quality (strong agreement, high-confidence inputs)
"""

FORECAST_TOOL = {
    "name": "produce_forecast",
    "description": "Produce a calibrated probability forecast for a binary prediction question.",
    "input_schema": {
        "type": "object",
        "properties": {
            "probability": {
                "type": "number",
                "description": "Probability (0.0–100.0) that the prediction question is TRUE."
            },
            "confidence": {
                "type": "string",
                "enum": ["low", "medium", "high"],
                "description": "Quality of evidence behind this forecast."
            },
            "ci_low": {
                "type": "number",
                "description": "Lower bound of the 80% confidence interval (0.0–100.0)."
            },
            "ci_high": {
                "type": "number",
                "description": "Upper bound of the 80% confidence interval (0.0–100.0)."
            },
            "direction": {
                "type": "string",
                "enum": ["bullish", "bearish", "neutral"],
                "description": "Overall directional lean of the forecast."
            },
            "reasoning": {
                "type": "string",
                "description": "2-4 sentences explaining how the synthesis was translated into this probability."
            },
            "caveats": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Up to 3 important risks or limitations the user should consider."
            }
        },
        "required": ["probability", "confidence", "ci_low", "ci_high", "direction", "reasoning", "caveats"]
    }
}


class CalibratedForecastAgent:
    def __init__(self, api_key: str | None = None, model: str = "claude-sonnet-4-6"):
        self.client = anthropic.Anthropic(api_key=api_key or os.environ["ANTHROPIC_API_KEY"])
        self.model = model

    def run(self, synthesis_output: SynthesisOutput) -> ForecastOutput:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=FORECAST_SYSTEM_PROMPT,
            tools=[FORECAST_TOOL],
            tool_choice={"type": "tool", "name": "produce_forecast"},
            messages=[{"role": "user", "content": self._build_prompt(synthesis_output)}],
        )

        tool_block = next(b for b in response.content if b.type == "tool_use")
        result = tool_block.input

        return ForecastOutput(
            question=synthesis_output.question,
            ticker=synthesis_output.ticker,
            time_horizon=synthesis_output.time_horizon,
            probability=result["probability"],
            confidence=result["confidence"],
            ci_low=result["ci_low"],
            ci_high=result["ci_high"],
            direction=result["direction"],
            reasoning=result["reasoning"],
            caveats=result["caveats"],
        )

    def _build_prompt(self, syn: SynthesisOutput) -> str:
        return f"""\
Produce a calibrated forecast for the following prediction question:

Question:      {syn.question}
Ticker:        {syn.ticker}
Time horizon:  {syn.time_horizon}

--- Synthesis Result ---
Weighted score:    {syn.weighted_score:+.3f}  (-1 = strong bear, +1 = strong bull)
Weights applied:   {syn.weights}
Signal agreement:  {syn.signal_agreement}
Narrative:         {syn.synthesis_narrative}

--- Raw Signal Confidence ---
News confidence:         {syn.raw_signals["news"]["confidence"]:.0%}
Market confidence:       {syn.raw_signals["market"]["confidence"]:.0%}
Fundamentals confidence: {syn.raw_signals["fundamentals"]["confidence"]:.0%}

Translate this synthesis into a calibrated probability that the question is TRUE,
then call produce_forecast."""


if __name__ == "__main__":
    from schemas import NewsSignal, MarketSignal, FundamentalsSignal, SynthesisInput
    from synthesis_agent import SynthesisAgent

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

    synthesis = SynthesisAgent().run(sample_input)
    forecast = CalibratedForecastAgent().run(synthesis)

    print(f"Question:   {forecast.question}")
    print(f"Probability: {forecast.probability:.1f}%  [{forecast.ci_low:.1f}% – {forecast.ci_high:.1f}%]")
    print(f"Confidence:  {forecast.confidence}  |  Direction: {forecast.direction}")
    print(f"\nReasoning:\n{forecast.reasoning}")
    print(f"\nCaveats:")
    for c in forecast.caveats:
        print(f"  • {c}")
