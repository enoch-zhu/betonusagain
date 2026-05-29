---
name: news-events-analyst
description: Domain knowledge for surfacing news catalysts and sentiment signals for prediction questions across sports, tech/finance, and politics.
---

# News & Events Analyst — Domain Knowledge

## Catalyst Taxonomy

### Tech / Finance
**High-impact catalysts:**
- Earnings releases (beat/miss vs consensus, EPS and revenue)
- Guidance revisions (raised/lowered forward outlook)
- Regulatory decisions (approvals, investigations, fines, antitrust)
- M&A announcements (acquirer typically drops, target spikes)
- Fed/central bank rate decisions and commentary
- Major product launches, recalls, or safety issues
- Executive departures (CEO/CFO sudden departure = high uncertainty)

**Medium-impact catalysts:**
- Analyst upgrades/downgrades and price target changes
- Sector rotation signals (ETF flow data)
- Macro data releases (CPI, jobs report, GDP, PMI)
- Competitor earnings (read-across signals to sector)
- Large institutional block trades or insider filings (Form 4)

**Noise (low signal):**
- Social media chatter without institutional backing
- Repeat coverage recycling old news
- Generic sector sentiment pieces with no new data

### Sports
**High-impact catalysts:**
- Injury reports: starter ruled out = major; "limited" or "questionable" = moderate
- Suspensions or disciplinary actions
- Weather conditions (outdoor sports): wind > 15 mph, heavy rain, or extreme temperatures
- Coaching changes mid-season or before a key matchup
- Back-to-back game fatigue or cross-timezone travel (especially relevant in NBA)

**Medium-impact catalysts:**
- Streak data: teams on 5+ game win/loss runs
- Head-to-head historical records (especially in similar conditions)
- Motivation factors: playoff positioning, rivalry games, revenge games
- Lineup rotation announcements or confirmed absences

**Noise:**
- Pre-game bulletin board quotes and trash talk
- Fan sentiment on social media
- Betting line movements that precede visible news (check if news follows)

### Politics
**High-impact catalysts:**
- New poll releases from credible pollsters (FiveThirtyEight A/B-rated)
- Major endorsements: party leadership, high-profile surrogates
- Fundraising disclosures (cash on hand is a viability proxy)
- Major gaffes or scandals — weight by novelty, not repetition of known issues
- Debate performance measured by post-debate polling shifts

**Medium-impact catalysts:**
- Early vote and absentee ballot return data
- State/local newspaper endorsements in competitive areas
- Prediction market movements (Polymarket, Manifold, PredictIt)
- Ground game activity signals (canvassing reports, volunteer surge)

**Noise:**
- Partisan media framing without polling corroboration
- Unverified social media claims
- Internal campaign spin or "sources say" stories from partisan outlets

---

## Sentiment Scoring

Score from -1.0 (strongly negative for the outcome) to +1.0 (strongly positive):

| Score Range | Interpretation |
|-------------|----------------|
| 0.7 to 1.0  | Strong tailwind — multiple high-impact bullish catalysts |
| 0.3 to 0.7  | Mild tailwind — positive outweighs negative |
| -0.3 to 0.3 | Neutral/mixed — no dominant direction |
| -0.3 to -0.7 | Mild headwind — negative outweighs positive |
| -0.7 to -1.0 | Strong headwind — multiple high-impact negative catalysts |

**Source credibility weighting:**
- Tier 1 (weight 1.0): Reuters, AP, Bloomberg, WSJ, Financial Times, ESPN injury reports, SEC filings, official government sources
- Tier 2 (weight 0.7): CNBC, NYT, Washington Post, major sports beat reporters with verified accounts
- Tier 3 (weight 0.4): Aggregators, blogs, opinion pieces, social media sentiment

---

## Output Schema

After your narrative analysis, always end with this exact JSON block. This is the
`NewsSignal` that the Synthesis agent consumes — no extra fields, no missing fields:

```json
{
  "sentiment": <float -1.0 to 1.0>,
  "headline_summary": "<1-2 sentences: key headlines and their directional impact>",
  "confidence": <float 0.0 to 1.0>
}
```

Field guidance:
- `sentiment`: aggregate directional score for the predicted outcome (-1 = strongly bearish, +1 = strongly bullish)
- `headline_summary`: distil the 2-3 most impactful recent headlines into 1-2 sentences; this is what downstream agents read
- `confidence`: how reliable this signal is (lower when few sources, conflicting signals, or a major scheduled event is imminent that could flip the picture)

You may include richer catalyst analysis in your narrative, but the JSON block must
contain exactly these three fields for downstream parsing.

---

## Search Strategy

Execute searches in this order for any prediction question:

1. **Core news**: `"[subject]" news site:reuters.com OR site:apnews.com OR site:bloomberg.com`
2. **Recent headlines**: `"[subject]" [current month year]`
3. **Catalyst-specific**: `"[subject]" [earnings|injury|poll|announcement|decision] [month year]`
4. **Expert analysis**: `"[subject]" analyst forecast prediction [month year]`
5. **Scheduled events**: `"[subject]" upcoming schedule events [month year]`

Prioritize last 7 days; extend to 30 days for context.

---

## Recency Weighting

| Age | Weight |
|-----|--------|
| 0–2 days | 100% |
| 3–7 days | 80% |
| 8–14 days | 50% |
| 15–30 days | 25% |
| 30+ days | Background context only (unless it's a scheduled future event) |

---

## Common Pitfalls

- **Overweighting social media**: Reddit/Twitter noise rarely predicts without Tier 1 corroboration
- **Missing the calendar**: A known earnings date or game schedule in 3 days dominates short-term signals — always surface upcoming scheduled events
- **Recency bias**: One dramatic headline can mask a contrary long-term trend; compare to the base rate
- **Reverse causality**: Price movements often precede news by hours; don't count post-hoc reporting as a new catalyst
- **Recycled stories**: Check publication dates — aggregators often re-date old articles
