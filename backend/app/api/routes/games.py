"""
Games API routes — list games, get detail, odds history, power rankings, injuries.
All GET responses are Redis-cached for performance.

Route registration order matters in FastAPI: literal path segments (/rankings/current,
/injuries/current) MUST be declared before path-parameter routes (/{game_id}) to avoid
FastAPI swallowing them as game IDs.
"""
from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.db.session import get_db
from app.db.models import NFLGame, OddsSnapshot, EdgeScore, WeatherReading, PowerRanking
from app.db.crud import (
    get_games_for_week,
    get_latest_snapshot,
    get_opening_snapshot,
    get_latest_weather,
    get_latest_edge_score,
    get_power_ranking,
    get_injuries_for_team,
    get_all_power_rankings,
    get_all_power_rankings_with_teams,
    get_all_injuries,
)
from app.core.cache import (
    cache_get, cache_set,
    games_list_key, game_detail_key, odds_history_key,
    GAMES_LIST_TTL, GAME_DETAIL_TTL, ODDS_HISTORY_TTL,
)
from app.api.deps import get_current_user

router = APIRouter(prefix="/games", tags=["games"])


# ── Power rankings leaderboard — MUST come before /{game_id} ─────────────────

@router.get("/rankings/current")
async def current_power_rankings(
    season: int = Query(2026),
    week: int = Query(1),
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """
    Return all 32 teams sorted by overall rank for the given season/week.
    Includes full team name/abbreviation and all FPI + standings fields.
    Falls back to the nearest prior week if data is not yet available.
    """
    cache_key = f"rankings:{season}:{week}"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    rankings = await get_all_power_rankings_with_teams(db, season, week)
    response = {
        "season": season,
        "week": week,
        "count": len(rankings),
        "rankings": [_serialize_ranking_full(r) for r in rankings],
    }
    await cache_set(cache_key, response, ttl=600)   # 10-min cache
    return response


# ── League-wide injury report — MUST come before /{game_id} ──────────────────

@router.get("/injuries/current")
async def current_injuries(
    status: Optional[str] = Query(None, description="Filter: Out, Doubtful, Questionable, Probable"),
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """
    Return all active injury designations across the entire league.
    Sorted by severity (QB first, key players, then by status weight).
    Optionally filter to a specific status via ?status=Out.
    """
    cache_key = f"injuries:current:{status or 'all'}"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    records = await get_all_injuries(db, status_filter=status)
    response = {
        "total": len(records),
        "status_filter": status,
        "injuries": [_serialize_injury_full(i) for i in records],
    }
    await cache_set(cache_key, response, ttl=300)   # 5-min cache
    return response


# ── List games ────────────────────────────────────────────────────────────────

@router.get("/")
async def list_games(
    season: int = Query(2026),
    week: int = Query(1),
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    cache_key = games_list_key(season, week)
    cached = await cache_get(cache_key)
    if cached:
        return cached

    games = await get_games_for_week(db, season, week)

    enriched = []
    for game in games:
        snap  = await get_latest_snapshot(db, game.id)
        edge  = await get_latest_edge_score(db, game.id)
        wx    = await get_latest_weather(db, game.id)

        # Power rankings for both teams
        home_pr = await get_power_ranking(db, game.home_team_id, season, week)
        away_pr = await get_power_ranking(db, game.away_team_id, season, week)

        # Injuries for both teams (summary counts only for list view)
        home_injuries = await get_injuries_for_team(db, game.home_team_id)
        away_injuries = await get_injuries_for_team(db, game.away_team_id)

        enriched.append({
            **_serialize_game(game),
            "odds":           _serialize_odds(snap),
            "edge":           _serialize_edge(edge),
            "weather":        _serialize_weather(wx),
            "home_ranking":   _serialize_ranking(home_pr),
            "away_ranking":   _serialize_ranking(away_pr),
            "injury_summary": _serialize_injury_summary(home_injuries, away_injuries),
        })

    response = {"games": enriched, "season": season, "week": week}
    await cache_set(cache_key, response, ttl=GAMES_LIST_TTL)
    return response


# ── Game detail ───────────────────────────────────────────────────────────────

@router.get("/{game_id}")
async def get_game(
    game_id: int,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    cache_key = game_detail_key(game_id)
    cached = await cache_get(cache_key)
    if cached:
        return cached

    result = await db.execute(select(NFLGame).where(NFLGame.id == game_id))
    game = result.scalar_one_or_none()
    if not game:
        raise HTTPException(404, "Game not found")

    snap    = await get_latest_snapshot(db, game_id)
    opening = await get_opening_snapshot(db, game_id)
    edge    = await get_latest_edge_score(db, game_id)
    wx      = await get_latest_weather(db, game_id)

    season = game.season
    week   = game.week
    home_pr = await get_power_ranking(db, game.home_team_id, season, week)
    away_pr = await get_power_ranking(db, game.away_team_id, season, week)

    home_injuries = await get_injuries_for_team(db, game.home_team_id)
    away_injuries = await get_injuries_for_team(db, game.away_team_id)

    line_move = None
    if snap and opening and snap.home_spread is not None and opening.home_spread is not None:
        line_move = round(snap.home_spread - opening.home_spread, 1)

    response = {
        "game":          _serialize_game(game),
        "odds":          _serialize_odds(snap),
        "opening_odds":  _serialize_odds(opening),
        "line_move":     line_move,
        "edge":          _serialize_edge(edge),
        "weather":       _serialize_weather(wx),
        "home_ranking":  _serialize_ranking(home_pr),
        "away_ranking":  _serialize_ranking(away_pr),
        "home_injuries": [_serialize_injury(i) for i in home_injuries],
        "away_injuries": [_serialize_injury(i) for i in away_injuries],
    }
    await cache_set(cache_key, response, ttl=GAME_DETAIL_TTL)
    return response


# ── Odds history ──────────────────────────────────────────────────────────────

@router.get("/{game_id}/odds/history")
async def odds_history(
    game_id: int,
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    cache_key = odds_history_key(game_id)
    cached = await cache_get(cache_key)
    if cached:
        return cached

    result = await db.execute(
        select(OddsSnapshot)
        .where(OddsSnapshot.game_id == game_id)
        .order_by(desc(OddsSnapshot.captured_at))
        .limit(limit)
    )
    snapshots = result.scalars().all()

    response = {
        "game_id":   game_id,
        "snapshots": [_serialize_odds(s) for s in reversed(list(snapshots))],
    }
    await cache_set(cache_key, response, ttl=ODDS_HISTORY_TTL)
    return response


# ── Serializers ───────────────────────────────────────────────────────────────

def _serialize_game(g) -> dict:
    if not g:
        return {}
    return {
        "id":          g.id,
        "season":      g.season,
        "week":        g.week,
        "game_time":   (g.game_time.isoformat() + "Z") if g.game_time else None,
        "home_team":   g.home_team.abbreviation if g.home_team else None,
        "away_team":   g.away_team.abbreviation if g.away_team else None,
        "home_score":  g.home_score,
        "away_score":  g.away_score,
        "status":      g.status,
        "external_id": g.external_id,
    }


def _serialize_odds(o) -> dict:
    if not o:
        return {}
    return {
        "id":                o.id,
        "source":            o.source,
        "captured_at":       o.captured_at.isoformat() if o.captured_at else None,
        "home_spread":       o.home_spread,
        "away_spread":       o.away_spread,
        "home_spread_juice": o.home_spread_juice,
        "away_spread_juice": o.away_spread_juice,
        "home_ml":           o.home_ml,
        "away_ml":           o.away_ml,
        "total":             o.total,
        "over_juice":        o.over_juice,
        "under_juice":       o.under_juice,
        "home_spread_pct":   o.home_spread_pct,
        "away_spread_pct":   o.away_spread_pct,
        "over_pct":          o.over_pct,
        "under_pct":         o.under_pct,
        "home_ml_pct":       o.home_ml_pct,
        "away_ml_pct":       o.away_ml_pct,
        "home_money_pct":    o.home_money_pct,
        "away_money_pct":    o.away_money_pct,
        "total_bet_count":   o.total_bet_count,
    }


def _serialize_edge(e) -> dict:
    if not e:
        return {}
    notes = e.notes
    if isinstance(notes, str):
        try:
            notes = json.loads(notes)
        except Exception:
            notes = [notes]
    return {
        "calculated_at":           e.calculated_at.isoformat() if e.calculated_at else None,
        "composite_score":         e.composite_score,
        "recommendation":          e.recommendation,
        "confidence":              e.confidence,
        "line_move_score":         e.line_move_score,
        "sharp_money_score":       e.sharp_money_score,
        "weather_impact_score":    e.weather_impact_score,
        "kalshi_divergence_score": e.kalshi_divergence_score,
        "public_fade_score":       e.public_fade_score,
        "power_ranking_score":     e.power_ranking_score,
        "injury_impact_score":     e.injury_impact_score,
        "notes":                   notes or [],
    }


def _serialize_weather(w) -> dict:
    if not w:
        return {}
    return {
        "temp_f":          w.temp_f,
        "wind_mph":        w.wind_mph,
        "wind_dir_deg":    w.wind_dir_deg,
        "precip_mm":       w.precip_mm,
        "snow_mm":         w.snow_mm,
        "humidity_pct":    w.humidity_pct,
        "cloud_cover_pct": w.cloud_cover_pct,
        "condition_desc":  w.condition_desc,
    }


def _serialize_ranking(r) -> dict:
    if not r:
        return {}
    return {
        "overall_rank":   r.overall_rank,
        "offensive_rank": r.offensive_rank,
        "defensive_rank": r.defensive_rank,
        "sos_rank":       r.sos_rank,
        "fpi_score":      r.fpi_score,
        "wins":           r.wins,
        "losses":         r.losses,
        "win_pct":        r.win_pct,
        "point_diff":     r.point_diff,
        "source":         r.source,
    }


def _serialize_ranking_full(r) -> dict:
    """Extended serializer that includes team identity fields."""
    if not r:
        return {}
    team = r.team if r.team else None
    return {
        "team_id":        r.team_id,
        "abbreviation":   team.abbreviation if team else None,
        "team_name":      team.name if team else None,
        "city":           team.city if team else None,
        "season":         r.season,
        "week":           r.week,
        "overall_rank":   r.overall_rank,
        "offensive_rank": r.offensive_rank,
        "defensive_rank": r.defensive_rank,
        "sos_rank":       r.sos_rank,
        "fpi_score":      r.fpi_score,
        "wins":           r.wins,
        "losses":         r.losses,
        "win_pct":        r.win_pct,
        "points_for":     r.points_for,
        "points_against": r.points_against,
        "point_diff":     r.point_diff,
        "source":         r.source,
        "captured_at":    r.captured_at.isoformat() if r.captured_at else None,
    }


def _serialize_injury(i) -> dict:
    if not i:
        return {}
    return {
        "athlete_name":  i.athlete_name,
        "position":      i.position,
        "jersey_number": i.jersey_number,
        "status":        i.status,
        "injury_type":   i.injury_type,
        "is_qb":         i.is_qb,
        "is_key_player": i.is_key_player,
        "reported_at":   i.reported_at.isoformat() if i.reported_at else None,
    }


def _serialize_injury_full(i) -> dict:
    """Extended serializer that includes team identity fields."""
    if not i:
        return {}
    team = i.team if i.team else None
    return {
        "id":                i.id,
        "team_id":           i.team_id,
        "team_abbreviation": team.abbreviation if team else None,
        "team_name":         team.name if team else None,
        "espn_athlete_id":   i.espn_athlete_id,
        "athlete_name":      i.athlete_name,
        "position":          i.position,
        "jersey_number":     i.jersey_number,
        "status":            i.status,
        "injury_type":       i.injury_type,
        "is_qb":             i.is_qb,
        "is_key_player":     i.is_key_player,
        "reported_at":       i.reported_at.isoformat() if i.reported_at else None,
        "captured_at":       i.captured_at.isoformat() if i.captured_at else None,
    }


def _serialize_injury_summary(home_injuries, away_injuries) -> dict:
    """Lightweight summary for the game list view."""
    def _summarise(injuries) -> dict:
        out          = sum(1 for i in injuries if i.status in ("Out", "IR"))
        doubtful     = sum(1 for i in injuries if i.status == "Doubtful")
        questionable = sum(1 for i in injuries if i.status == "Questionable")
        qb_status    = next(
            (i.status for i in injuries if i.is_qb),
            None,
        )
        return {
            "out":          out,
            "doubtful":     doubtful,
            "questionable": questionable,
            "qb_status":    qb_status,
        }
    return {
        "home": _summarise(home_injuries),
        "away": _summarise(away_injuries),
    }

