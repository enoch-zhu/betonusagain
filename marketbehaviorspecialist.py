"""
Create the Market Behavior specialist sub-agent for the Forecast swarm.

This specialist gets:
- A narrow system prompt
- The agent toolset (file ops, web search, web fetch, bash)
- A market-behavior skill uploaded separately by upload_skills.py

Saves the resulting agent ID to .specialist_ids.json so create_coordinator.py
can reference it.

Usage:
    export ANTHROPIC_API_KEY="sk-ant-..."
    python create_market_behavior_specialist.py
"""

import json
import os
from pathlib import Path

from anthropic import Anthropic


SPECIALISTS = [
    {
        "key": "market_behavior",
        "name": "Market Behavior Specialist",
        "model": "claude-sonnet-4-6",
        "system": (
            "You are the Market Behavior Specialist in a Forecast swarm. Your job is to "
            "analyze market behavior for the target asset and produce an explainable signal "
            "package for downstream synthesis.\n\n"
            "Inputs you'll receive:\n"
            "- The prediction question (for example: Will MSFT be up in one week?)\n"
            "- The target ticker and forecast horizon\n"
            "- market-behavior skill (your authoritative technical analysis framework)\n"
            "- historical market data files for the asset and, when available, a benchmark \n"
            "  such as SPY, QQQ, or a sector ETF\n\n"
            "Your job is to evaluate market behavior only. Focus on price action, trend, \n"
            "momentum, realized volatility, ATR/range expansion, drawdown stress, volume \n"
            "confirmation, regime, and benchmark-relative strength.\n\n"
            "Your output: a structured market behavior assessment covering:\n"
            "1. Trend assessment (short, medium, and long horizon)\n"
            "2. Momentum assessment\n"
            "3. Volatility assessment and whether volatility strengthens or weakens signal reliability\n"
            "4. Volume confirmation or divergence\n"
            "5. Relative strength versus benchmark when benchmark data is available\n"
            "6. Regime classification: bull_trend_stable / bull_trend_high_vol / sideways / \n"
            "   sideways_high_vol / transition / bear_trend / bear_stress\n"
            "7. A provisional directional read for the stated horizon\n"
            "8. A confidence estimate based only on market behavior\n"
            "9. The 3-6 most important evidence points supporting that read\n\n"
            "Output requirements:\n"
            "- Be precise, concise, and explainable.\n"
            "- Do not use news, sentiment, earnings, revenue, or macro fundamentals except \n"
            "  when they are explicitly encoded in the supplied market data.\n"
            "- Do not produce the final forecast for the swarm. You are a specialist input \n"
            "  into synthesis, not the final arbiter.\n"
            "- Return a synthesis-ready payload with these fields:\n"
            "  agent_name, ticker, horizon_days, provisional_probability_up, directional_score, \n"
            "  confidence, regime, summary, key_evidence, features, diagnostics, calibration_payload\n"
            "- Keep the reasoning grounded in observable market behavior and cite the supplied \n"
            "  data artifacts when you use them."
        ),
    },
]


def main() -> None:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise SystemExit("Set ANTHROPIC_API_KEY before running.")

    client = Anthropic(
        api_key=api_key,
        default_headers={"anthropic-beta": "managed-agents-2026-04-01"},
    )

    specialist_ids: dict[str, str] = {}
    for spec in SPECIALISTS:
        agent = client.beta.agents.create(
            name=spec["name"],
            model=spec["model"],
            system=spec["system"],
            tools=[{"type": "agent_toolset_20260401"}],
            metadata={
                "hackathon": "partner-basecamp-2026",
                "track": "specialist-swarm",
                "role": spec["key"],
            },
        )
        specialist_ids[spec["key"]] = agent.id
        print(f"  Created {spec['name']:32s} -> {agent.id}")

    Path(".specialist_ids.json").write_text(json.dumps(specialist_ids, indent=2))
    print(f"\nSaved {len(specialist_ids)} specialist IDs to .specialist_ids.json")
    print("Next: python upload_skills.py")


if __name__ == "__main__":
    main()
