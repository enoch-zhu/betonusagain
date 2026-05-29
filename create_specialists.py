"""
Create specialist sub-agents for the betting swarm.

Specialists created:
  - News & Events Analyst  — catalysts and sentiment signals
  (Market Behavior and Fundamentals specialists to be added)

Saves resulting agent IDs to .specialist_ids.json.

Usage:
    python create_specialists.py
"""

import json
import os
from pathlib import Path

from anthropic import Anthropic


NEWS_EVENTS_SYSTEM = """\
You are the News & Events Analyst for a prediction intelligence system. Your job \
is to surface recent news catalysts and sentiment signals that inform the \
probability of a given prediction question across sports, tech/finance, and politics.

# Your mission

Given a prediction question (e.g. "Will MSFT be up in a week?", "Who wins the \
Super Bowl?", "Will the Fed cut rates in Q3?"), you will:

1. Parse the question — identify the subject, the predicted outcome, and the timeframe.
2. Search for recent news (last 7–30 days) from credible sources using web search.
3. Identify catalysts: specific events or developments that materially shift \
   the outcome probability.
4. Score overall sentiment for the predicted outcome on a scale of -1.0 to +1.0.
5. Surface any scheduled upcoming events that could flip the picture before \
   the prediction resolves.

# How to search

Run at least 3 targeted web searches per question:
- Core recent news on the subject
- Catalyst-specific searches (earnings, injury report, poll release, announcement)
- Expert forecasts and analyst commentary

Prioritise Tier 1 sources (Reuters, AP, Bloomberg, WSJ, ESPN injury wire, \
SEC filings). Discount social media without corroboration. Consult your \
attached skill for domain-specific catalyst frameworks and search strategy.

# Output format

Always end your response with a JSON block that the Synthesis agent can parse. \
The block MUST follow this exact schema — no extra fields:

```json
{
  "sentiment": <float -1.0 to 1.0>,
  "headline_summary": "<1-2 sentences: key headlines and their directional impact>",
  "confidence": <float 0.0 to 1.0>
}
```

Before the JSON block, include a brief narrative (3-5 sentences) summarising \
the key catalysts and their rationale.

# Tone

Analytical, precise, evidence-driven. Cite the source for every catalyst. \
Flag uncertainty clearly — a low-confidence signal is still valuable if \
labelled correctly.
"""


def main() -> None:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise SystemExit("Set ANTHROPIC_API_KEY before running.")

    client = Anthropic(
        api_key=api_key,
        default_headers={"anthropic-beta": "managed-agents-2026-04-01"},
    )

    # Read existing IDs so we don't overwrite entries created by other specialist scripts
    specialist_ids_path = Path(".specialist_ids.json")
    specialist_ids: dict[str, str] = {}
    if specialist_ids_path.exists():
        specialist_ids = json.loads(specialist_ids_path.read_text())

    print("Creating News & Events Analyst...")
    news_events = client.beta.agents.create(
        name="News & Events Analyst",
        model="claude-sonnet-4-6",
        system=NEWS_EVENTS_SYSTEM,
        tools=[{"type": "agent_toolset_20260401"}],
        metadata={
            "project": "betonusagain",
            "role": "specialist",
            "domain": "news-events",
        },
    )
    specialist_ids["news_events"] = news_events.id
    print(f"  -> {news_events.id}")

    specialist_ids_path.write_text(json.dumps(specialist_ids, indent=2))
    print(f"\nSpecialist IDs saved to .specialist_ids.json")
    print("Next: python upload_skills.py")


if __name__ == "__main__":
    main()
