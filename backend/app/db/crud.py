"""
CRUD helpers — thin async wrappers around SQLAlchemy queries.
Used by Celery tasks and API routes.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, desc, and_, delete
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    NFLGame, NFLTeam, OddsSnapshot, WeatherReading, EdgeScore,
    PowerRanking, InjuryReport,
)

logger = logging.getLogger(__name__)


# ── NFLGame ────────────────────────────────────────────────────────────────────

async def get_or_create_game(
    db: AsyncSession,
    *,
    external_id: str,
    home_abbr: str,
    away_abbr: str,
    game_time: datetime,
    season: int,
    week: int,
) -> Optional[NFLGame]:
    """
    Find a game by ESPN external_id, or create it if it doesn't exist yet.
    Returns None if either team abbreviation is unknown.
    """
    if external_id:
        result = await db.execute(
            select(NFLGame).where(NFLGame.external_id == external_id)
        )
        game = result.scalar_one_or_none()
        if game:
            return game

    home = await _get_team(db, home_abbr)
    away = await _get_team(db, away_abbr)
    if not home or not away:
        logger.warning("Unknown team abbr: home=%s away=%s", home_abbr, away_abbr)
        return None

    result = await db.execute(
        select(NFLGame).where(
            and_(
                NFLGame.season == season,
                NFLGame.week == week,
                NFLGame.home_team_id == home.id,
                NFLGame.away_team_id == away.id,
            )
        )
    )
    game = result.scalar_one_or_none()
    if game:
        if not game.external_id and external_id:
            game.external_id = external_id
            await db.commit()
        return game

    game = NFLGame(
        external_id=external_id,
        season=season,
        week=week,
        game_time=game_time,
        home_team_id=home.id,
        away_team_id=away.id,
        status="scheduled",
    )
    db.add(game)
    await db.commit()
    await db.refresh(game)
    logger.info("Created NFLGame id=%d: %s @ %s", game.id, away_abbr, home_abbr)
    return game


async def _get_team(db: AsyncSession, abbreviation: str) -> Optional[NFLTeam]:
    result = await db.execute(
        select(NFLTeam).where(NFLTeam.abbreviation == abbreviation.upper())
    )
    return result.scalar_one_or_none()


async def get_games_for_week(
    db: AsyncSession, season: int, week: int
) -> list[NFLGame]:
    result = await db.execute(
        select(NFLGame)
        .options(selectinload(NFLGame.home_team), selectinload(NFLGame.away_team)).where(NFLGame.season == season, NFLGame.week == week)
        .order_by(NFLGame.game_time)
    )
    return list(result.scalars().all())


async def get_all_teams(db: AsyncSession) -> list[NFLTeam]:
    result = await db.execute(select(NFLTeam).order_by(NFLTeam.abbreviation))
    return list(result.scalars().all())


# ── OddsSnapshot ───────────────────────────────────────────────────────────────

async def save_odds_snapshot(db: AsyncSession, game_id: int, data: dict) -> OddsSnapshot:
    snap = OddsSnapshot(
        game_id=game_id,
        source=data.get("source", "draftkings"),
        captured_at=datetime.utcnow(),
        home_spread=data.get("home_spread"),
        away_spread=data.get("away_spread"),
        home_spread_juice=data.get("home_spread_juice"),
        away_spread_juice=data.get("away_spread_juice"),
        home_ml=data.get("home_ml"),
        away_ml=data.get("away_ml"),
        total=data.get("total"),
        over_juice=data.get("over_juice"),
        under_juice=data.get("under_juice"),
        home_spread_pct=data.get("home_spread_pct"),
        away_spread_pct=data.get("away_spread_pct"),
        over_pct=data.get("over_pct"),
        under_pct=data.get("under_pct"),
        home_ml_pct=data.get("home_ml_pct"),
        away_ml_pct=data.get("away_ml_pct"),
        home_money_pct=data.get("home_money_pct"),
        away_money_pct=data.get("away_money_pct"),
        total_bet_count=data.get("total_bet_count"),
    )
    db.add(snap)
    await db.commit()
    await db.refresh(snap)
    return snap


async def get_latest_snapshot(
    db: AsyncSession, game_id: int
) -> Optional[OddsSnapshot]:
    result = await db.execute(
        select(OddsSnapshot)
        .where(OddsSnapshot.game_id == game_id)
        .order_by(desc(OddsSnapshot.captured_at))
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_opening_snapshot(
    db: AsyncSession, game_id: int
) -> Optional[OddsSnapshot]:
    result = await db.execute(
        select(OddsSnapshot)
        .where(OddsSnapshot.game_id == game_id)
        .order_by(OddsSnapshot.captured_at)
        .limit(1)
    )
    return result.scalar_one_or_none()


async def merge_public_money_into_snapshot(
    db: AsyncSession,
    game_id: int,
    money_data: dict,
) -> Optional[OddsSnapshot]:
    snap = await get_latest_snapshot(db, game_id)
    if not snap:
        logger.debug("No snapshot to merge public money into for game_id=%d", game_id)
        return None

    snap.home_spread_pct = money_data.get("home_spread_pct") or snap.home_spread_pct
    snap.away_spread_pct = money_data.get("away_spread_pct") or snap.away_spread_pct
    snap.over_pct        = money_data.get("over_pct")        or snap.over_pct
    snap.under_pct       = money_data.get("under_pct")       or snap.under_pct
    snap.home_ml_pct     = money_data.get("home_ml_pct")     or snap.home_ml_pct
    snap.away_ml_pct     = money_data.get("away_ml_pct")     or snap.away_ml_pct
    snap.home_money_pct  = money_data.get("home_money_pct")  or snap.home_money_pct
    snap.away_money_pct  = money_data.get("away_money_pct")  or snap.away_money_pct
    snap.total_bet_count = money_data.get("total_bet_count") or snap.total_bet_count

    await db.commit()
    return snap


# ── WeatherReading ─────────────────────────────────────────────────────────────

async def save_weather_reading(
    db: AsyncSession, game_id: int, forecast_for: datetime, data: dict
) -> WeatherReading:
    reading = WeatherReading(
        game_id=game_id,
        forecast_for=forecast_for,
        captured_at=datetime.utcnow(),
        temp_f=data.get("temp_f"),
        wind_mph=data.get("wind_mph"),
        wind_dir_deg=data.get("wind_dir_deg"),
        precip_mm=data.get("precip_mm"),
        snow_mm=data.get("snow_mm"),
        humidity_pct=data.get("humidity_pct"),
        cloud_cover_pct=data.get("cloud_cover_pct"),
        condition_code=data.get("condition_code"),
        condition_desc=data.get("condition_desc"),
    )
    db.add(reading)
    await db.commit()
    await db.refresh(reading)
    return reading


async def get_latest_weather(
    db: AsyncSession, game_id: int
) -> Optional[WeatherReading]:
    result = await db.execute(
        select(WeatherReading)
        .where(WeatherReading.game_id == game_id)
        .order_by(desc(WeatherReading.captured_at))
        .limit(1)
    )
    return result.scalar_one_or_none()


# ── PowerRanking ───────────────────────────────────────────────────────────────

async def upsert_power_ranking(
    db: AsyncSession,
    team_id: int,
    season: int,
    week: int,
    data: dict,
) -> PowerRanking:
    """
    Insert or update a PowerRanking row for a specific team/season/week.
    The unique constraint on (team_id, season, week) makes this idempotent.
    """
    result = await db.execute(
        select(PowerRanking).where(
            and_(
                PowerRanking.team_id == team_id,
                PowerRanking.season == season,
                PowerRanking.week == week,
            )
        )
    )
    ranking = result.scalar_one_or_none()

    if ranking:
        # Update in place
        ranking.fpi_score       = data.get("fpi_score", ranking.fpi_score)
        ranking.overall_rank    = data.get("overall_rank", ranking.overall_rank)
        ranking.offensive_rank  = data.get("offensive_rank", ranking.offensive_rank)
        ranking.defensive_rank  = data.get("defensive_rank", ranking.defensive_rank)
        ranking.sos_rank        = data.get("sos_rank", ranking.sos_rank)
        ranking.wins            = data.get("wins", ranking.wins)
        ranking.losses          = data.get("losses", ranking.losses)
        ranking.win_pct         = data.get("win_pct", ranking.win_pct)
        ranking.points_for      = data.get("points_for", ranking.points_for)
        ranking.points_against  = data.get("points_against", ranking.points_against)
        ranking.point_diff      = data.get("point_diff", ranking.point_diff)
        ranking.source          = data.get("source", ranking.source)
        ranking.captured_at     = datetime.utcnow()
    else:
        ranking = PowerRanking(
            team_id=team_id,
            season=season,
            week=week,
            fpi_score=data.get("fpi_score"),
            overall_rank=data.get("overall_rank"),
            offensive_rank=data.get("offensive_rank"),
            defensive_rank=data.get("defensive_rank"),
            sos_rank=data.get("sos_rank"),
            wins=data.get("wins"),
            losses=data.get("losses"),
            win_pct=data.get("win_pct"),
            points_for=data.get("points_for"),
            points_against=data.get("points_against"),
            point_diff=data.get("point_diff"),
            source=data.get("source", "fpi"),
            captured_at=datetime.utcnow(),
        )
        db.add(ranking)

    await db.commit()
    await db.refresh(ranking)
    return ranking


async def get_power_ranking(
    db: AsyncSession,
    team_id: int,
    season: int,
    week: int,
) -> Optional[PowerRanking]:
    """Get the most recent power ranking for a team, starting from the given week and walking back."""
    for w in range(week, 0, -1):
        result = await db.execute(
            select(PowerRanking).where(
                and_(
                    PowerRanking.team_id == team_id,
                    PowerRanking.season == season,
                    PowerRanking.week == w,
                )
            )
        )
        ranking = result.scalar_one_or_none()
        if ranking:
            return ranking
    return None


async def get_all_power_rankings(
    db: AsyncSession,
    season: int,
    week: int,
) -> list[PowerRanking]:
    """Return all team rankings for a given season/week (or nearest available week)."""
    result = await db.execute(
        select(PowerRanking).where(
            and_(
                PowerRanking.season == season,
                PowerRanking.week == week,
            )
        ).order_by(PowerRanking.overall_rank)
    )
    rows = list(result.scalars().all())
    if not rows and week > 1:
        return await get_all_power_rankings(db, season, week - 1)
    return rows


# ── InjuryReport ───────────────────────────────────────────────────────────────

async def save_injury_reports(
    db: AsyncSession,
    team_id: int,
    records: list[dict],
) -> int:
    """
    Replace all injury records for a team with the freshly-fetched set.
    Returns number of rows written.
    """
    # Delete existing records for this team (full refresh each cycle)
    await db.execute(
        delete(InjuryReport).where(InjuryReport.team_id == team_id)
    )

    if not records:
        await db.commit()
        return 0

    now = datetime.utcnow()
    for rec in records:
        inj = InjuryReport(
            team_id=team_id,
            espn_athlete_id=rec.get("espn_athlete_id"),
            athlete_name=rec.get("athlete_name", "Unknown"),
            position=rec.get("position"),
            jersey_number=rec.get("jersey_number"),
            status=rec.get("status", "Questionable"),
            injury_type=rec.get("injury_type"),
            is_qb=bool(rec.get("is_qb", False)),
            is_key_player=bool(rec.get("is_key_player", False)),
            reported_at=rec.get("reported_at"),
            captured_at=now,
        )
        db.add(inj)

    await db.commit()
    return len(records)


async def get_injuries_for_team(
    db: AsyncSession, team_id: int
) -> list[InjuryReport]:
    result = await db.execute(
        select(InjuryReport)
        .where(InjuryReport.team_id == team_id)
        .order_by(InjuryReport.is_qb.desc(), InjuryReport.is_key_player.desc(), InjuryReport.status)
    )
    return list(result.scalars().all())


async def get_injuries_for_game(
    db: AsyncSession, home_team_id: int, away_team_id: int
) -> tuple[list[InjuryReport], list[InjuryReport]]:
    """Return (home_injuries, away_injuries) for a given game."""
    home = await get_injuries_for_team(db, home_team_id)
    away = await get_injuries_for_team(db, away_team_id)
    return home, away


# ── EdgeScore ──────────────────────────────────────────────────────────────────

async def save_edge_score(
    db: AsyncSession, game_id: int, result_obj, raw_inputs: dict
) -> EdgeScore:
    score = EdgeScore(
        game_id=game_id,
        calculated_at=datetime.utcnow(),
        line_move_score=result_obj.line_move_score,
        sharp_money_score=result_obj.sharp_money_score,
        weather_impact_score=result_obj.weather_impact_score,
        kalshi_divergence_score=result_obj.kalshi_divergence_score,
        public_fade_score=result_obj.public_fade_score,
        power_ranking_score=result_obj.power_ranking_score,
        injury_impact_score=result_obj.injury_impact_score,
        composite_score=result_obj.composite_score,
        recommendation=result_obj.recommendation,
        confidence=result_obj.confidence,
        notes=json.dumps(result_obj.notes),
        raw_inputs=raw_inputs,
    )
    db.add(score)
    await db.commit()
    await db.refresh(score)
    return score


async def get_latest_edge_score(
    db: AsyncSession, game_id: int
) -> Optional[EdgeScore]:
    result = await db.execute(
        select(EdgeScore)
        .where(EdgeScore.game_id == game_id)
        .order_by(desc(EdgeScore.calculated_at))
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_all_injuries(
    db: AsyncSession,
    status_filter: Optional[str] = None,
) -> list[InjuryReport]:
    """
    Return every active injury record across all 32 teams, team relationship
    eagerly loaded so routes can access inj.team.abbreviation / inj.team.name.
    Optionally filter to a specific status (Out, Doubtful, Questionable…).
    """
    from sqlalchemy.orm import selectinload

    query = (
        select(InjuryReport)
        .options(selectinload(InjuryReport.team))
        .order_by(
            InjuryReport.is_qb.desc(),
            InjuryReport.is_key_player.desc(),
            InjuryReport.status,
            InjuryReport.athlete_name,
        )
    )
    if status_filter:
        query = query.where(InjuryReport.status == status_filter)

    result = await db.execute(query)
    return list(result.scalars().all())


async def get_all_power_rankings_with_teams(
    db: AsyncSession,
    season: int,
    week: int,
) -> list[PowerRanking]:
    """
    Same as get_all_power_rankings but with team relationship eagerly loaded
    so callers can access r.team.abbreviation / r.team.name.
    Falls back to nearest prior week if no data exists for requested week.
    """
    from sqlalchemy.orm import selectinload

    for w in range(week, 0, -1):
        result = await db.execute(
            select(PowerRanking)
            .options(selectinload(PowerRanking.team))
            .where(
                and_(
                    PowerRanking.season == season,
                    PowerRanking.week == w,
                )
            )
            .order_by(PowerRanking.overall_rank)
        )
        rows = list(result.scalars().all())
        if rows:
            return rows
    return []
