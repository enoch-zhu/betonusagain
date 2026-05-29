#!/usr/bin/env python3
"""
Betting Research Subagent
=========================
A Claude-powered subagent for the betting agent swarm.
Researches historical performance data across:
  - Basketball (NBA)
  - Football (NFL)
  - Esports

Usage:
    from research_subagent import BettingResearchSubagent

    agent = BettingResearchSubagent()
    result = agent.research("Analyze the Lakers' home record over 5 seasons")
"""

import json
import random
from typing import Any

import anthropic
from anthropic import beta_tool


# ─────────────────────────────────────────────────────────────────────────────
# Sample Data — seeded for reproducibility
# ─────────────────────────────────────────────────────────────────────────────

NBA_TEAMS = [
    "Los Angeles Lakers",
    "Boston Celtics",
    "Golden State Warriors",
    "Milwaukee Bucks",
    "Miami Heat",
    "Phoenix Suns",
    "Denver Nuggets",
    "Philadelphia 76ers",
    "Dallas Mavericks",
    "Memphis Grizzlies",
    "New York Knicks",
    "Cleveland Cavaliers",
    "Sacramento Kings",
    "New Orleans Pelicans",
    "Los Angeles Clippers",
]

NFL_TEAMS = [
    "Kansas City Chiefs",
    "Philadelphia Eagles",
    "San Francisco 49ers",
    "Dallas Cowboys",
    "Buffalo Bills",
    "Cincinnati Bengals",
    "Baltimore Ravens",
    "Miami Dolphins",
    "Detroit Lions",
    "Jacksonville Jaguars",
    "Seattle Seahawks",
    "Pittsburgh Steelers",
    "New England Patriots",
    "Green Bay Packers",
    "Los Angeles Rams",
]

ESPORTS_TEAMS = [
    "Team Liquid",
    "Cloud9",
    "FaZe Clan",
    "Natus Vincere",
    "G2 Esports",
    "Team Vitality",
    "Astralis",
    "FNATIC",
    "100 Thieves",
    "TSM",
]

NBA_SEASONS = ["2019-20", "2020-21", "2021-22", "2022-23", "2023-24"]
NFL_SEASONS = ["2019", "2020", "2021", "2022", "2023"]
ESPORTS_YEARS = ["2021", "2022", "2023", "2024"]


# ── NBA database ──────────────────────────────────────────────────────────────

def _build_nba_database() -> dict[str, Any]:
    db: dict[str, Any] = {}
    for team in NBA_TEAMS:
        db[team] = {"seasons": {}, "recent_games": []}

        for season in NBA_SEASONS:
            rng = random.Random(abs(hash(team + season)) % 100_000)
            wins = rng.randint(24, 62)
            losses = 82 - wins
            home_wins = int(wins * rng.uniform(0.55, 0.70))
            away_wins = wins - home_wins
            ppg = round(rng.uniform(103.0, 121.0), 1)
            opp_ppg = round(ppg + rng.uniform(-6.0, 6.0), 1)
            ats_w = rng.randint(30, 52)
            ats_l = 82 - ats_w

            db[team]["seasons"][season] = {
                "wins": wins,
                "losses": losses,
                "win_pct": round(wins / 82, 3),
                "home_record": f"{home_wins}-{41 - home_wins}",
                "away_record": f"{away_wins}-{41 - away_wins}",
                "points_per_game": ppg,
                "opponent_ppg": opp_ppg,
                "point_diff": round(ppg - opp_ppg, 1),
                "ats_record": f"{ats_w}-{ats_l}",
                "over_pct": round(rng.uniform(44.0, 56.0), 1),
                "three_point_pct": round(rng.uniform(34.0, 40.0), 1),
                "fg_pct": round(rng.uniform(44.0, 50.0), 1),
                "playoff_appearance": wins >= 44,
            }

        # Last 10 game log
        rng2 = random.Random(abs(hash(team + "recent")) % 100_000)
        opponents = [t for t in NBA_TEAMS if t != team]
        for i in range(10):
            pts = rng2.randint(96, 130)
            opp_pts = rng2.randint(96, 130)
            db[team]["recent_games"].append({
                "game_number": i + 1,
                "opponent": rng2.choice(opponents),
                "home": rng2.choice([True, False]),
                "team_points": pts,
                "opponent_points": opp_pts,
                "result": "W" if pts > opp_pts else "L",
                "total": pts + opp_pts,
            })

    return db


# ── NFL database ──────────────────────────────────────────────────────────────

def _build_nfl_database() -> dict[str, Any]:
    db: dict[str, Any] = {}
    for team in NFL_TEAMS:
        db[team] = {"seasons": {}, "recent_games": []}

        for season in NFL_SEASONS:
            rng = random.Random(abs(hash(team + season)) % 100_000)
            wins = rng.randint(4, 15)
            losses = 17 - wins
            pts_for = rng.randint(18, 32)
            pts_against = rng.randint(16, 30)
            ats_w = rng.randint(6, 11)
            ats_l = 17 - ats_w

            db[team]["seasons"][season] = {
                "wins": wins,
                "losses": losses,
                "win_pct": round(wins / 17, 3),
                "home_wins": rng.randint(2, min(wins, 8)),
                "away_wins": max(0, wins - rng.randint(2, min(wins, 8))),
                "points_per_game": pts_for,
                "points_allowed": pts_against,
                "point_diff": pts_for - pts_against,
                "ats_record": f"{ats_w}-{ats_l}",
                "over_pct": round(rng.uniform(44.0, 56.0), 1),
                "yards_per_game": rng.randint(290, 400),
                "yards_allowed": rng.randint(290, 400),
                "turnovers": rng.randint(12, 30),
                "playoff_appearance": wins >= 9,
            }

        rng2 = random.Random(abs(hash(team + "nfl_recent")) % 100_000)
        opponents = [t for t in NFL_TEAMS if t != team]
        for i in range(8):
            pts = rng2.randint(10, 38)
            opp = rng2.randint(10, 38)
            db[team]["recent_games"].append({
                "game_number": i + 1,
                "opponent": rng2.choice(opponents),
                "home": rng2.choice([True, False]),
                "team_points": pts,
                "opponent_points": opp,
                "result": "W" if pts > opp else "L",
                "total": pts + opp,
            })

    return db


# ── Esports database ──────────────────────────────────────────────────────────

def _build_esports_database() -> dict[str, Any]:
    db: dict[str, Any] = {}
    for team in ESPORTS_TEAMS:
        db[team] = {"seasons": {}}
        for year in ESPORTS_YEARS:
            rng = random.Random(abs(hash(team + year)) % 100_000)
            wins = rng.randint(30, 80)
            total = rng.randint(wins, wins + 40)
            db[team]["seasons"][year] = {
                "wins": wins,
                "losses": total - wins,
                "win_rate": round(wins / total, 3),
                "tournament_wins": rng.randint(0, 4),
                "tournament_appearances": rng.randint(4, 12),
                "prize_money_usd": rng.randint(50_000, 2_000_000),
                "avg_map_score": round(rng.uniform(1.8, 2.6), 2),
                "peak_ranking": rng.randint(1, 20),
            }
    return db


# Build all databases once at import time
NBA_DB = _build_nba_database()
NFL_DB = _build_nfl_database()
ESPORTS_DB = _build_esports_database()


# ─────────────────────────────────────────────────────────────────────────────
# Tool Definitions
# ─────────────────────────────────────────────────────────────────────────────

@beta_tool
def list_available_teams(category: str) -> str:
    """List all teams available for a given sport category.

    Args:
        category: Sport category — one of "basketball", "football", or "esports"
    """
    mapping = {
        "basketball": NBA_TEAMS,
        "football": NFL_TEAMS,
        "esports": ESPORTS_TEAMS,
    }
    key = category.lower()
    if key not in mapping:
        return json.dumps({"error": f"Unknown category '{category}'. Valid: basketball, football, esports"})
    return json.dumps({"category": key, "teams": mapping[key]}, indent=2)


@beta_tool
def get_team_history(team_name: str, category: str, seasons: int = 5) -> str:
    """Get season-by-season historical performance for a team.

    Args:
        team_name: Full team name (e.g. "Los Angeles Lakers", "Kansas City Chiefs")
        category: Sport category — "basketball", "football", or "esports"
        seasons: Number of most recent seasons to return (default 5, max 5)
    """
    cat = category.lower()
    n = max(1, min(seasons, 5))

    if cat == "basketball":
        if team_name not in NBA_DB:
            return json.dumps({"error": f"'{team_name}' not found. Call list_available_teams('basketball')."})
        season_data = NBA_DB[team_name]["seasons"]
        keys = list(season_data.keys())[-n:]
        return json.dumps({"team": team_name, "category": cat, "seasons": {k: season_data[k] for k in keys}}, indent=2)

    if cat == "football":
        if team_name not in NFL_DB:
            return json.dumps({"error": f"'{team_name}' not found. Call list_available_teams('football')."})
        season_data = NFL_DB[team_name]["seasons"]
        keys = list(season_data.keys())[-n:]
        return json.dumps({"team": team_name, "category": cat, "seasons": {k: season_data[k] for k in keys}}, indent=2)

    if cat == "esports":
        if team_name not in ESPORTS_DB:
            return json.dumps({"error": f"'{team_name}' not found. Call list_available_teams('esports')."})
        season_data = ESPORTS_DB[team_name]["seasons"]
        keys = list(season_data.keys())[-n:]
        return json.dumps({"team": team_name, "category": cat, "seasons": {k: season_data[k] for k in keys}}, indent=2)

    return json.dumps({"error": f"Unknown category '{category}'."})


@beta_tool
def get_scoring_trends(team_name: str, category: str, last_n_games: int = 10) -> str:
    """Get recent game-by-game scoring results and trend summary for a team.

    Args:
        team_name: Full team name
        category: Sport category — "basketball" or "football"
        last_n_games: Number of recent games to analyze (default 10)
    """
    cat = category.lower()
    n = max(1, min(last_n_games, 10))

    if cat == "basketball":
        if team_name not in NBA_DB:
            return json.dumps({"error": f"'{team_name}' not found."})
        games = NBA_DB[team_name]["recent_games"][:n]
    elif cat == "football":
        if team_name not in NFL_DB:
            return json.dumps({"error": f"'{team_name}' not found."})
        games = NFL_DB[team_name]["recent_games"][:n]
    else:
        return json.dumps({"error": f"Scoring trends support basketball and football only."})

    pts = [g["team_points"] for g in games]
    opp = [g["opponent_points"] for g in games]
    totals = [g["total"] for g in games]
    wins = sum(1 for g in games if g["result"] == "W")

    summary = {
        "record": f"{wins}-{n - wins}",
        "avg_points_scored": round(sum(pts) / n, 1),
        "avg_points_allowed": round(sum(opp) / n, 1),
        "avg_total": round(sum(totals) / n, 1),
        "highest_scoring": max(totals),
        "lowest_scoring": min(totals),
    }
    if cat == "basketball":
        over_line = 220
        summary["over_line_used"] = over_line
        summary["overs"] = sum(1 for t in totals if t > over_line)
        summary["unders"] = sum(1 for t in totals if t <= over_line)

    return json.dumps({"team": team_name, "category": cat, "games": games, "summary": summary}, indent=2)


@beta_tool
def get_head_to_head(team1: str, team2: str, category: str) -> str:
    """Get the all-time and recent head-to-head matchup history between two teams.

    Args:
        team1: Name of the first team
        team2: Name of the second team
        category: Sport category — "basketball", "football", or "esports"
    """
    rng = random.Random(abs(hash(team1 + "|" + team2 + "|" + category)) % 100_000)
    total = rng.randint(10, 40)
    t1_wins = rng.randint(3, total - 3)
    t2_wins = total - t1_wins

    last_5 = []
    for i in range(5):
        winner = rng.choice([team1, team2])
        margin = rng.randint(1, 20)
        season = rng.choice(NBA_SEASONS if category.lower() == "basketball" else NFL_SEASONS)
        last_5.append({
            "game": i + 1,
            "season": season,
            "winner": winner,
            "margin": margin,
        })

    return json.dumps({
        "team1": team1,
        "team2": team2,
        "category": category,
        "all_time": {
            "total_games": total,
            f"{team1}_wins": t1_wins,
            f"{team2}_wins": t2_wins,
            "series_leader": team1 if t1_wins > t2_wins else team2,
        },
        "last_5_meetings": last_5,
    }, indent=2)


@beta_tool
def get_betting_indicators(team_name: str, category: str) -> str:
    """Get key betting indicators: ATS record, over/under rate, and home/away splits.

    Args:
        team_name: Full team name
        category: Sport category — "basketball" or "football"
    """
    cat = category.lower()

    if cat == "basketball":
        if team_name not in NBA_DB:
            return json.dumps({"error": f"'{team_name}' not found."})
        seasons = NBA_DB[team_name]["seasons"]
        current = list(seasons.values())[-1]
        prev = list(seasons.values())[-2]

        notes = []
        if current["point_diff"] > 5:
            notes.append(f"Strong positive point diff (+{current['point_diff']}) — likely favored often")
        elif current["point_diff"] < -5:
            notes.append(f"Negative point diff ({current['point_diff']}) — often underdog")
        if current["over_pct"] > 52:
            notes.append(f"Games going OVER {current['over_pct']}% — high-scoring tendency")
        elif current["over_pct"] < 48:
            notes.append(f"Games going UNDER {current['over_pct']}% — defensive/slow-paced")

        return json.dumps({
            "team": team_name,
            "category": cat,
            "current_season": {
                "ats_record": current["ats_record"],
                "over_pct": current["over_pct"],
                "home_record": current["home_record"],
                "away_record": current["away_record"],
                "point_diff": current["point_diff"],
            },
            "previous_season": {
                "ats_record": prev["ats_record"],
                "over_pct": prev["over_pct"],
            },
            "analyst_notes": notes,
        }, indent=2)

    if cat == "football":
        if team_name not in NFL_DB:
            return json.dumps({"error": f"'{team_name}' not found."})
        seasons = NFL_DB[team_name]["seasons"]
        current = list(seasons.values())[-1]

        notes = []
        if current["point_diff"] > 6:
            notes.append(f"Dominant point diff (+{current['point_diff']}) — strong against the spread candidate")
        if current["over_pct"] > 52:
            notes.append(f"Over hitting {current['over_pct']}% — high-scoring games")

        return json.dumps({
            "team": team_name,
            "category": cat,
            "current_season": {
                "ats_record": current["ats_record"],
                "over_pct": current["over_pct"],
                "home_wins": current["home_wins"],
                "away_wins": current["away_wins"],
                "point_diff": current["point_diff"],
            },
            "analyst_notes": notes,
        }, indent=2)

    return json.dumps({"error": f"Betting indicators support basketball and football only."})


@beta_tool
def get_league_standings(category: str, season: str = "2023-24") -> str:
    """Get full league standings sorted by win percentage for a given season.

    Args:
        category: Sport category — "basketball" or "football"
        season: Season identifier (e.g. "2023-24" for NBA, "2023" for NFL)
    """
    cat = category.lower()

    if cat == "basketball":
        rows = []
        for team in NBA_TEAMS:
            s = NBA_DB[team]["seasons"].get(season, list(NBA_DB[team]["seasons"].values())[-1])
            rows.append({
                "team": team,
                "wins": s["wins"],
                "losses": s["losses"],
                "win_pct": s["win_pct"],
                "ppg": s["points_per_game"],
                "opp_ppg": s["opponent_ppg"],
                "point_diff": s["point_diff"],
                "playoff": s["playoff_appearance"],
            })
        rows.sort(key=lambda x: x["win_pct"], reverse=True)
        return json.dumps({"category": cat, "season": season, "standings": rows}, indent=2)

    if cat == "football":
        rows = []
        for team in NFL_TEAMS:
            s = NFL_DB[team]["seasons"].get(season, list(NFL_DB[team]["seasons"].values())[-1])
            rows.append({
                "team": team,
                "wins": s["wins"],
                "losses": s["losses"],
                "win_pct": s["win_pct"],
                "pts_for": s["points_per_game"],
                "pts_against": s["points_allowed"],
                "point_diff": s["point_diff"],
                "playoff": s["playoff_appearance"],
            })
        rows.sort(key=lambda x: x["win_pct"], reverse=True)
        return json.dumps({"category": cat, "season": season, "standings": rows}, indent=2)

    return json.dumps({"error": f"Unknown category '{category}'. Use: basketball, football"})


# ─────────────────────────────────────────────────────────────────────────────
# Subagent Class
# ─────────────────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are a specialized sports betting research analyst subagent.

Your responsibilities:
- Retrieve and synthesize historical team performance data using your tools
- Identify meaningful patterns relevant to betting: ATS records, over/under tendencies,
  home/away splits, point differentials, win streaks, and multi-season trends
- Provide concise, data-backed analysis — cite exact numbers from tool results
- Avoid fabricating data; always use the retrieval tools first

Supported categories: basketball (NBA), football (NFL), esports.
When listing available teams, call list_available_teams first.
Always compare at least 2–3 seasons before drawing trend conclusions.
"""


class BettingResearchSubagent:
    """
    A Claude-powered subagent that researches historical betting data.

    Designed to be used as one node in a larger agent swarm, but also
    runnable standalone via the `research()` method.

    Example:
        agent = BettingResearchSubagent()
        report = agent.research(
            "How have the Warriors performed ATS over the last 3 seasons?"
        )
        print(report)
    """

    def __init__(self, model: str = "claude-opus-4-8"):
        self.client = anthropic.Anthropic()
        self.model = model
        self._tools = [
            list_available_teams,
            get_team_history,
            get_scoring_trends,
            get_head_to_head,
            get_betting_indicators,
            get_league_standings,
        ]

    def research(self, query: str, verbose: bool = False) -> str:
        """
        Research historical data for a given betting query.

        Args:
            query: Natural language research request.
            verbose: If True, print tool calls and intermediate messages.

        Returns:
            Final analysis text from the agent.
        """
        runner = self.client.beta.messages.tool_runner(
            model=self.model,
            max_tokens=4096,
            thinking={"type": "adaptive"},
            output_config={"effort": "medium"},
            system=_SYSTEM_PROMPT,
            tools=self._tools,
            messages=[{"role": "user", "content": query}],
        )

        full_text = []
        for message in runner:
            for block in message.content:
                if getattr(block, "type", None) == "text":
                    if verbose:
                        print(block.text, end="", flush=True)
                    full_text.append(block.text)
                elif getattr(block, "type", None) == "tool_use" and verbose:
                    print(f"\n[tool → {block.name}({json.dumps(block.input, separators=(',',':'))})]")

        if verbose:
            print()  # trailing newline
        return "".join(full_text)


# ─────────────────────────────────────────────────────────────────────────────
# Demo / CLI
# ─────────────────────────────────────────────────────────────────────────────

DEMO_QUERIES = [
    "Analyze the Los Angeles Lakers' wins, losses, and home vs. away record over the last 5 seasons. What are their ATS and over/under trends?",
    "Compare the Kansas City Chiefs and the Dallas Cowboys head-to-head. Who has the better recent ATS record?",
    "Which NBA teams have the highest over percentage in the 2023-24 season? Give me the top 5.",
]


def main() -> None:
    agent = BettingResearchSubagent()

    for i, query in enumerate(DEMO_QUERIES, 1):
        separator = "=" * 70
        print(f"\n{separator}")
        print(f"Query {i}: {query}")
        print(separator)
        result = agent.research(query, verbose=True)
        print(f"\n[Research complete — {len(result)} chars]")


if __name__ == "__main__":
    main()
