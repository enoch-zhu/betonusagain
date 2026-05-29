# betonusagain

# Forecast Specialist Swarm

A modular multi-agent forecasting project that routes a market prediction question to specialist agents, synthesizes their signals, and produces a calibrated forecast.

## Project Purpose

This project is designed to answer forecasting questions such as:

- **Will MSFT be up in one week?**
- **What is the probability that NVDA closes higher over the next 10 trading days?**
- **How confident should we be in a short-term directional view on a target asset?**

The system uses a **specialist swarm** architecture rather than a single general-purpose agent. Each specialist focuses on one narrow domain, and a downstream synthesis layer combines the signals into a final, calibrated output.

## High-Level Architecture

The current architecture follows this flow:

1. **Prediction question**  
   A user submits a forecasting question about a target asset and time horizon.

2. **Question router**  
   The router interprets the question, extracts key parameters (for example ticker and horizon), and dispatches work to specialists.

3. **Specialist agents**  
   The router sends the task to domain-specific specialists:
   - **News & events** — catalyst detection and qualitative context
   - **Market behavior** — trend, momentum, volatility, drawdown, volume, and regime analysis
   - **Fundamentals** — revenue, profitability, and business performance context

4. **Synthesis**  
   A synthesis agent or coordinator aggregates the specialist outputs, weights the signals, and resolves conflicts.

5. **Calibrated forecast**  
   The final output is a forecast with:
   - probability
   - confidence
   - supporting rationale
   - evidence from the contributing specialists

## Design Principles

This project is intentionally built around a few core principles:

- **Specialization over generality**  
  Each agent has a narrow role and should stay within scope.

- **Explainability over black-box reasoning**  
  Outputs should be interpretable, evidence-based, and easy to debug.

- **Separation of signal generation and final decisioning**  
  Specialists produce domain-specific reads; synthesis is responsible for combining them into a final forecast.

- **Calibration matters**  
  Raw signals are not enough. The final forecast should express both directional probability and confidence.

- **Composable architecture**  
  New specialists can be added without redesigning the entire system.

## Current Specialist Roles

### 1) News & Events Specialist
Focus:
- current events
- company-specific catalysts
- earnings-related narrative
- sentiment-relevant developments
- event-driven risks

Output should emphasize:
- relevant catalysts
- whether news flow is supportive or adverse
- timing sensitivity
- evidence-backed qualitative signal for synthesis

### 2) Market Behavior Specialist
Focus:
- price trend
- momentum
- realized volatility
- ATR / range expansion
- drawdown stress
- volume confirmation
- relative strength versus benchmark
- regime classification

Output should emphasize:
- technical and market-structure signal
- directionality over the forecast horizon
- confidence based only on market behavior
- structured evidence for synthesis

### 3) Fundamentals Specialist
Focus:
- revenue growth
- margins
- profitability
- earnings quality
- financial strength
- business-performance context

Output should emphasize:
- whether the underlying business context supports or weakens the forecast
- durable versus short-term drivers
- important fundamental risks

### 4) Synthesis / Coordinator
Focus:
- combining specialist outputs
- weighting signals by relevance and reliability
- resolving contradictions
- generating a final, calibrated answer

Output should include:
- final probability estimate
- confidence estimate
- concise explanation of why
- summary of the strongest supporting and opposing signals

## Managed-Agent Pattern

This project follows a managed-agent setup inspired by a specialist-creation pattern in which each specialist is created with:

- a **narrow system prompt**
- a standard **agent toolset**
- a domain-specific **skill** uploaded separately
- metadata so the coordinator can identify the role of each specialist

A typical specialist creation script:
- defines a `SPECIALISTS` list
- creates agents through the Anthropic managed-agents API
- stores resulting IDs in `.specialist_ids.json`

This keeps agent registration separate from agent behavior and makes the project easier to scale.

## Repository Structure

Below is a suggested general structure for the repository:

```text
forecast-swarm/
├── README.md
├── .specialist_ids.json
├── create_coordinator.py
├── create_market_behavior_specialist.py
├── create_news_events_specialist.py
├── create_fundamentals_specialist.py
├── upload_skills.py
├── skills/
│   ├── market_behavior/
│   ├── news_events/
│   └── fundamentals/
├── data/
│   ├── market/
│   ├── fundamentals/
│   └── news/
├── prompts/
├── utils/
└── examples/
```

You can adjust this to fit your orchestration framework and deployment style.

## Input and Output Model

### Example Input
A prediction task should usually specify:

- a natural-language question
- target ticker or asset identifier
- forecast horizon
- any optional benchmark

Example:

```python
{
    "question": "Will MSFT be up in one week?",
    "ticker": "MSFT",
    "horizon_days": 5,
    "benchmark": "SPY"
}
```

### Example Specialist Output Shape
Each specialist should return a structured, synthesis-ready object.

For example:

```python
{
    "agent_name": "market_behavior_subagent",
    "ticker": "MSFT",
    "horizon_days": 5,
    "provisional_probability_up": 0.61,
    "directional_score": 0.29,
    "confidence": 0.67,
    "summary": "...",
    "key_evidence": [...],
    "features": {...},
    "diagnostics": {...},
    "calibration_payload": {...}
}
```

The exact schema may vary by specialist, but outputs should be consistent enough for the synthesis agent to combine them predictably.

## How the Market Behavior Specialist Fits In

The Market Behavior Specialist is responsible for technical and market-structure analysis only. It should not become the final forecasting authority and should not absorb unrelated domains such as news interpretation or fundamentals.

Its role is to:
- analyze the supplied market history
- produce an explainable directional read
- quantify confidence from market behavior alone
- hand off a structured signal package for synthesis

This separation keeps the architecture clean and reduces hidden cross-domain reasoning.

## Setup

### 1) Environment
Set your API key before running specialist creation scripts:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

### 2) Create specialists
Run the specialist creation scripts to register the agents and save their IDs:

```bash
python create_market_behavior_specialist.py
```

If the project uses multiple specialists, create each one and persist the IDs in `.specialist_ids.json`.

### 3) Upload skills
If your project uses uploaded skills, run:

```bash
python upload_skills.py
```

### 4) Create the coordinator
Once specialist IDs exist, create the coordinator that will dispatch and synthesize their outputs.

## Development Guidance

### Keep specialists narrow
A specialist should do one job well. Avoid broad prompts that cause overlap between domains.

### Keep outputs structured
Structured payloads make synthesis, auditing, testing, and future calibration easier.

### Optimize for explainability
The swarm should be able to explain why it produced a given forecast, not just provide a number.

### Calibrate later, but design for it now
Even if calibration is not fully implemented yet, include raw scores, confidence values, and diagnostic metadata so calibration can be added cleanly later.

## Future Extensions

Potential next steps for the project include:

- adding a fully defined synthesis specialist
- adding historical outcome tracking for calibration
- adding benchmark and sector-relative context
- adding model evaluation and backtesting
- adding richer evidence extraction and traceability
- adding orchestration-level logging and observability
- adding versioned prompt and skill management

## Status

This project is currently structured as a **specialist swarm forecasting system** with a clearly defined architectural pattern and at least one managed specialist focused on **market behavior**.

## Notes

This README is intentionally general so it can serve as the top-level project overview while the implementation evolves. As the project matures, you may want to expand this file with:

- exact install requirements
- concrete data sources
- specialist-specific schemas
- coordinator behavior
- evaluation methodology
- examples of full end-to-end runs

---

If you add more specialists or formalize the synthesis layer, update this README so the system design and operating assumptions remain explicit.
