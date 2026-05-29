"""
Run the News & Events Analyst against a prediction question and stream its output.
Parses the NewsSignal JSON from the agent response for use with synthesis_agent.py.

Usage:
    python run_news_events.py "Will MSFT be up in a week?"
    python run_news_events.py "Who wins the NBA championship this year?"
    python run_news_events.py "Will the Fed cut rates in Q3 2026?"

    # Chain into synthesis (requires market and fundamentals signals):
    python run_news_events.py "Will MSFT be up in a week?" --synthesize
"""

import json
import os
import re
import sys
from pathlib import Path

from anthropic import Anthropic

from schemas import NewsSignal


def extract_news_signal(text: str) -> NewsSignal | None:
    """Parse the NewsSignal JSON block from the agent's response."""
    match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    if not match:
        # Fallback: look for a bare JSON object with the required fields
        match = re.search(r'\{\s*"sentiment".*?"confidence".*?\}', text, re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(1) if "```" in match.group(0) else match.group(0))
        return NewsSignal(
            sentiment=float(data["sentiment"]),
            headline_summary=str(data["headline_summary"]),
            confidence=float(data["confidence"]),
        )
    except (KeyError, ValueError, json.JSONDecodeError):
        return None


def main() -> None:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit("Set ANTHROPIC_API_KEY before running.")

    args = sys.argv[1:]
    synthesize = "--synthesize" in args
    question_args = [a for a in args if not a.startswith("--")]

    if not question_args:
        raise SystemExit('Usage: python run_news_events.py "<prediction question>" [--synthesize]')

    question = question_args[0]

    specialist_ids_path = Path(".specialist_ids.json")
    if not specialist_ids_path.exists():
        raise SystemExit("Run create_specialists.py and upload_skills.py first.")
    specialist_ids = json.loads(specialist_ids_path.read_text())

    news_events_id = specialist_ids.get("news_events")
    if not news_events_id:
        raise SystemExit("news_events specialist not found in .specialist_ids.json")

    env_path = Path(".environment_id")
    if not env_path.exists():
        raise SystemExit("Run setup_environment.py first.")
    environment_id = env_path.read_text().strip()

    client = Anthropic(
        default_headers={"anthropic-beta": "managed-agents-2026-04-01"},
    )

    print(f"Question: {question}")
    print(f"Agent:    {news_events_id}")
    print("-" * 60)

    response_text = ""

    with client.beta.sessions.events.stream(
        agent_id=news_events_id,
        environment_id=environment_id,
        messages=[{"role": "user", "content": question}],
    ) as stream:
        for event in stream:
            event_type = getattr(event, "type", None)
            if event_type == "session.thread_created":
                print(f"[thread created: {event.thread_id}]")
            elif event_type == "session.thread_running":
                print(f"[thread running: {event.thread_id}]")
            elif event_type == "message_delta" and hasattr(event, "delta"):
                text = getattr(event.delta, "text", None)
                if text:
                    print(text, end="", flush=True)
                    response_text += text

        final_message = stream.get_final_message()
        if final_message and final_message.content:
            for block in final_message.content:
                if hasattr(block, "text"):
                    response_text = block.text
                    break

    print("\n" + "-" * 60)

    news_signal = extract_news_signal(response_text)
    if news_signal:
        print(f"\nNewsSignal parsed:")
        print(f"  sentiment:        {news_signal.sentiment:+.2f}")
        print(f"  confidence:       {news_signal.confidence:.0%}")
        print(f"  headline_summary: {news_signal.headline_summary}")
    else:
        print("\nWarning: could not parse NewsSignal from response.")

    output_dir = Path("outputs")
    output_dir.mkdir(exist_ok=True)
    slug = question[:40].replace(" ", "_").replace("?", "").lower()
    (output_dir / f"news_events_{slug}.txt").write_text(response_text)
    print(f"\nFull output saved to outputs/news_events_{slug}.txt")

    if news_signal and synthesize:
        _run_synthesis(question, news_signal)


def _run_synthesis(question: str, news_signal: NewsSignal) -> None:
    """Chain the NewsSignal into the SynthesisAgent (requires all three signals)."""
    print("\n" + "=" * 60)
    print("Synthesis requires market and fundamentals signals.")
    print("Stub those in here or integrate with the full swarm runner.")
    print("=" * 60)

    # Example stub — replace with real Market Behavior + Fundamentals agent calls
    from schemas import MarketSignal, FundamentalsSignal, SynthesisInput
    from synthesis_agent import SynthesisAgent

    market_stub = MarketSignal(
        trend=0.0, volatility=0.5, momentum=0.0,
        summary="[stub — run market behavior specialist for real data]",
        confidence=0.0,
    )
    fundamentals_stub = FundamentalsSignal(
        score=0.0, revenue_trend="neutral",
        summary="[stub — run fundamentals specialist for real data]",
        confidence=0.0,
    )

    ticker = question.split()[1] if len(question.split()) > 1 else "UNKNOWN"
    synthesis_input = SynthesisInput(
        question=question,
        ticker=ticker,
        time_horizon="1 week",
        news_signal=news_signal,
        market_signal=market_stub,
        fundamentals_signal=fundamentals_stub,
    )

    output = SynthesisAgent().run(synthesis_input)
    print(f"\nSynthesis weighted_score: {output.weighted_score:+.3f}")
    print(f"Signal agreement:         {output.signal_agreement}")
    print(f"Narrative:\n{output.synthesis_narrative}")


if __name__ == "__main__":
    main()
