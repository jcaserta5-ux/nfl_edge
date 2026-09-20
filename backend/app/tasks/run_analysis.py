"""
Celery task: run the edge engine for all active games and persist EdgeScore rows.

Pulls the latest OddsSnapshot + WeatherReading + PowerRanking + InjuryReport
per game, detects line movement vs opening line, then writes an EdgeScore.

New in v2: power ranking differential and injury impact are now scored
and included in the composite formula.
"""
import asyncio
import logging
from datetime import datetime, timezone

from app.tasks.celery_app import celery_app
from app.analysis.edge_engine import calculate_edge, GameSnapshot
from app.ingestion.injury_adapter import compute_injury_impact
from app.db.session import AsyncSessionLocal
from app.db.crud import (
    get_games_for_week,
    get_latest_snapshot,
    get_opening_snapshot,
    get_latest_weather,
    get_latest_edge_score,
    save_edge_score,
    get_power_ranking,
    get_injuries_for_game,
)

logger = logging.getLogger(__name__)
NFL_SEASON = 2026


@celery_app.task(
    name="app.tasks.run_analysis.run_edge_analysis",
    bind=True,
    max_retries=3,
)
def run_edge_analysis(self, season: int = None, week: int = None):
    loop = asyncio.new_event_loop()
    try:
        scored = loop.run_until_complete(
            _analyze_week(season or NFL_SEASON, week or _current_week())
        )
        logger.info("Edge analysis: scored %d games", scored)
        return {"status": "ok", "scored": scored}
    except Exception as exc:
        logger.error("Edge analysis failed: %s", exc)
        raise self.retry(exc=exc, countdown=60)
    finally:
        loop.close()


async def _analyze_week(season: int, week: int) -> int:
    scored = 0
    async with AsyncSessionLocal() as db:
        games = await get_games_for_week(db, season, week)
        for game in games:
            if game.status == "final":
                continue
            try:
                result = await _score_game(db, game, season, week)
                if result:
                    scored += 1
            except Exception as exc:
                logger.warning("Failed scoring game_id=%d: %s", game.id, exc)
    return scored


async def _score_game(db, game, season: int, week: int) -> bool:
    latest  = await get_latest_snapshot(db, game.id)
    opening = await get_opening_snapshot(db, game.id)
    weather = await get_latest_weather(db, game.id)

    if not latest:
        return False  # no odds data yet

    is_dome = getattr(game.home_team, "is_dome", False)

    # ── Power rankings ────────────────────────────────────────────────────────
    home_ranking = await get_power_ranking(db, game.home_team_id, season, week)
    away_ranking = await get_power_ranking(db, game.away_team_id, season, week)

    home_overall_rank = getattr(home_ranking, "overall_rank", None)
    away_overall_rank = getattr(away_ranking, "overall_rank", None)
    home_fpi          = getattr(home_ranking, "fpi_score", None)
    away_fpi          = getattr(away_ranking, "fpi_score", None)
    home_point_diff   = getattr(home_ranking, "point_diff", None)
    away_point_diff   = getattr(away_ranking, "point_diff", None)

    # ── Injuries ──────────────────────────────────────────────────────────────
    home_injuries, away_injuries = await get_injuries_for_game(
        db, game.home_team_id, game.away_team_id
    )

    # Convert ORM objects to plain dicts for injury_adapter
    home_inj_dicts = _injury_to_dicts(home_injuries)
    away_inj_dicts = _injury_to_dicts(away_injuries)

    injury_score, injury_notes = compute_injury_impact(home_inj_dicts, away_inj_dicts)
    home_impact = sum(
        _inj_weight(i["status"]) * (5 if i["is_qb"] else 1)
        for i in home_inj_dicts if i.get("is_key_player")
    )
    away_impact = sum(
        _inj_weight(i["status"]) * (5 if i["is_qb"] else 1)
        for i in away_inj_dicts if i.get("is_key_player")
    )

    # ── Build GameSnapshot ────────────────────────────────────────────────────
    snap = GameSnapshot(
        game_id=game.id,
        home_team=game.home_team.abbreviation if game.home_team else "",
        away_team=game.away_team.abbreviation if game.away_team else "",
        is_dome=is_dome,
        # Spread / total
        home_spread=latest.home_spread,
        total=latest.total,
        home_spread_open=opening.home_spread if opening else None,
        total_open=opening.total if opening else None,
        # Public money
        home_spread_pct=latest.home_spread_pct,
        home_money_pct=latest.home_money_pct,
        over_pct=latest.over_pct,
        total_bet_count=latest.total_bet_count,
        # Weather
        wind_mph=weather.wind_mph if weather else None,
        temp_f=weather.temp_f if weather else None,
        precip_mm=weather.precip_mm if weather else None,
        snow_mm=weather.snow_mm if weather else None,
        # Power rankings
        home_overall_rank=home_overall_rank,
        away_overall_rank=away_overall_rank,
        home_fpi=home_fpi,
        away_fpi=away_fpi,
        home_point_diff=home_point_diff,
        away_point_diff=away_point_diff,
        # Injuries
        home_injury_impact=home_impact,
        away_injury_impact=away_impact,
        injury_notes=injury_notes,
    )

    result = calculate_edge(snap)

    raw_inputs = {
        "snapshot_id": latest.id,
        "opening_snapshot_id": opening.id if opening else None,
        "weather_reading_id": weather.id if weather else None,
        "home_spread": snap.home_spread,
        "home_spread_open": snap.home_spread_open,
        "home_spread_pct": snap.home_spread_pct,
        "home_money_pct": snap.home_money_pct,
        "wind_mph": snap.wind_mph,
        "temp_f": snap.temp_f,
        "home_overall_rank": home_overall_rank,
        "away_overall_rank": away_overall_rank,
        "home_fpi": home_fpi,
        "away_fpi": away_fpi,
        "home_injury_impact": home_impact,
        "away_injury_impact": away_impact,
        "injury_count_home": len(home_inj_dicts),
        "injury_count_away": len(away_inj_dicts),
    }

    await save_edge_score(db, game.id, result, raw_inputs)
    return True


# ── Helpers ───────────────────────────────────────────────────────────────────

def _injury_to_dicts(records) -> list[dict]:
    return [
        {
            "team_abbreviation": getattr(r, "team", {}) and getattr(r.team, "abbreviation", ""),
            "espn_athlete_id": r.espn_athlete_id,
            "athlete_name": r.athlete_name,
            "position": r.position,
            "status": r.status,
            "is_qb": r.is_qb,
            "is_key_player": r.is_key_player,
        }
        for r in records
    ]


_STATUS_WEIGHTS = {
    "Out": 3.0, "Doubtful": 2.0, "Questionable": 1.0,
    "Probable": 0.25, "IR": 3.0, "PUP": 2.5, "NFI": 1.5,
}


def _inj_weight(status: str) -> float:
    return _STATUS_WEIGHTS.get(status, 0.0)


def _current_week() -> int:
    import math
    now = datetime.now(timezone.utc)
    season_start = datetime(now.year, 9, 7, tzinfo=timezone.utc)
    delta = (now - season_start).days
    return max(1, min(22, math.ceil((delta + 1) / 7)))
