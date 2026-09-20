"""
SQLAlchemy ORM models for NFL Betting Edge.
"""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime,
    ForeignKey, Text, JSON, UniqueConstraint, Enum
)
from sqlalchemy.orm import relationship, DeclarativeBase
import enum


class Base(DeclarativeBase):
    pass


# ── Auth ──────────────────────────────────────────────────────────────────────

class InviteCode(Base):
    __tablename__ = "invite_codes"

    id = Column(Integer, primary_key=True)
    code = Column(String(32), unique=True, nullable=False, index=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    used_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    used_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(64), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_admin = Column(Boolean, default=False)
    invite_code_used = Column(String(32), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)


# ── NFL Data ──────────────────────────────────────────────────────────────────

class NFLTeam(Base):
    __tablename__ = "nfl_teams"

    id = Column(Integer, primary_key=True)
    abbreviation = Column(String(5), unique=True, nullable=False)
    name = Column(String(64), nullable=False)
    city = Column(String(64), nullable=False)
    stadium_name = Column(String(128), nullable=True)
    stadium_lat = Column(Float, nullable=True)
    stadium_lon = Column(Float, nullable=True)
    is_dome = Column(Boolean, default=False)
    turf_type = Column(String(32), nullable=True)  # grass, turf


class NFLGame(Base):
    __tablename__ = "nfl_games"
    __table_args__ = (UniqueConstraint("season", "week", "home_team_id", "away_team_id"),)

    id = Column(Integer, primary_key=True)
    external_id = Column(String(64), nullable=True, index=True)
    season = Column(Integer, nullable=False)
    week = Column(Integer, nullable=False)
    game_time = Column(DateTime, nullable=False)
    home_team_id = Column(Integer, ForeignKey("nfl_teams.id"), nullable=False)
    away_team_id = Column(Integer, ForeignKey("nfl_teams.id"), nullable=False)
    home_score = Column(Integer, nullable=True)
    away_score = Column(Integer, nullable=True)
    status = Column(String(32), default="scheduled")  # scheduled, live, final

    home_team = relationship("NFLTeam", foreign_keys=[home_team_id])
    away_team = relationship("NFLTeam", foreign_keys=[away_team_id])
    odds_snapshots = relationship("OddsSnapshot", back_populates="game")
    weather_readings = relationship("WeatherReading", back_populates="game")
    edge_scores = relationship("EdgeScore", back_populates="game")


# ── Odds ──────────────────────────────────────────────────────────────────────

class OddsSource(str, enum.Enum):
    DRAFTKINGS = "draftkings"
    KALSHI = "kalshi"
    ODDS_API = "odds_api"


class OddsSnapshot(Base):
    __tablename__ = "odds_snapshots"

    id = Column(Integer, primary_key=True)
    game_id = Column(Integer, ForeignKey("nfl_games.id"), nullable=False, index=True)
    source = Column(Enum(OddsSource), nullable=False)
    captured_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Spread
    home_spread = Column(Float, nullable=True)
    away_spread = Column(Float, nullable=True)
    home_spread_juice = Column(Integer, nullable=True)   # e.g. -110
    away_spread_juice = Column(Integer, nullable=True)

    # Moneyline
    home_ml = Column(Integer, nullable=True)
    away_ml = Column(Integer, nullable=True)

    # Total
    total = Column(Float, nullable=True)
    over_juice = Column(Integer, nullable=True)
    under_juice = Column(Integer, nullable=True)

    # Public money data (from Action Network)
    home_spread_pct = Column(Float, nullable=True)    # % of bets on home spread
    away_spread_pct = Column(Float, nullable=True)
    over_pct = Column(Float, nullable=True)           # % of bets on over
    under_pct = Column(Float, nullable=True)
    home_ml_pct = Column(Float, nullable=True)
    away_ml_pct = Column(Float, nullable=True)
    home_money_pct = Column(Float, nullable=True)     # % of money on home spread
    away_money_pct = Column(Float, nullable=True)
    total_bet_count = Column(Integer, nullable=True)

    game = relationship("NFLGame", back_populates="odds_snapshots")


class KalshiContract(Base):
    __tablename__ = "kalshi_contracts"

    id = Column(Integer, primary_key=True)
    game_id = Column(Integer, ForeignKey("nfl_games.id"), nullable=False, index=True)
    market_ticker = Column(String(64), nullable=False)
    market_title = Column(String(255), nullable=True)
    yes_price = Column(Float, nullable=True)   # cents (0-99)
    no_price = Column(Float, nullable=True)
    volume = Column(Integer, nullable=True)
    open_interest = Column(Integer, nullable=True)
    captured_at = Column(DateTime, default=datetime.utcnow)


# ── Weather ───────────────────────────────────────────────────────────────────

class WeatherReading(Base):
    __tablename__ = "weather_readings"

    id = Column(Integer, primary_key=True)
    game_id = Column(Integer, ForeignKey("nfl_games.id"), nullable=False, index=True)
    captured_at = Column(DateTime, default=datetime.utcnow)
    forecast_for = Column(DateTime, nullable=False)

    temp_f = Column(Float, nullable=True)
    wind_mph = Column(Float, nullable=True)
    wind_dir_deg = Column(Integer, nullable=True)
    precip_mm = Column(Float, nullable=True)
    snow_mm = Column(Float, nullable=True)
    humidity_pct = Column(Float, nullable=True)
    cloud_cover_pct = Column(Float, nullable=True)
    condition_code = Column(Integer, nullable=True)
    condition_desc = Column(String(64), nullable=True)

    game = relationship("NFLGame", back_populates="weather_readings")


# ── Power Rankings ────────────────────────────────────────────────────────────

class PowerRanking(Base):
    """
    Per-team power ranking snapshot — sourced from ESPN FPI with standings fallback.
    One row per team per season/week. Unique constraint prevents duplicates.
    """
    __tablename__ = "power_rankings"
    __table_args__ = (UniqueConstraint("team_id", "season", "week"),)

    id = Column(Integer, primary_key=True)
    team_id = Column(Integer, ForeignKey("nfl_teams.id"), nullable=False, index=True)
    season = Column(Integer, nullable=False)
    week = Column(Integer, nullable=False)

    # ESPN FPI fields (primary source)
    fpi_score = Column(Float, nullable=True)          # raw FPI value, higher = better
    overall_rank = Column(Integer, nullable=True)     # 1–32, lower rank = better team
    offensive_rank = Column(Integer, nullable=True)   # 1–32
    defensive_rank = Column(Integer, nullable=True)   # 1–32
    sos_rank = Column(Integer, nullable=True)         # strength of schedule rank

    # Standings-based fields (fallback / supplemental)
    wins = Column(Integer, nullable=True)
    losses = Column(Integer, nullable=True)
    win_pct = Column(Float, nullable=True)
    points_for = Column(Float, nullable=True)
    points_against = Column(Float, nullable=True)
    point_diff = Column(Float, nullable=True)         # PF - PA per game

    source = Column(String(16), default="fpi")       # "fpi" | "standings"
    captured_at = Column(DateTime, default=datetime.utcnow)

    team = relationship("NFLTeam")


# ── Injury Reports ────────────────────────────────────────────────────────────

class InjuryReport(Base):
    """
    Individual player injury record from ESPN Injuries API.
    Refreshed every 3 hours during the season.
    No game_id FK — injuries apply to all upcoming games for that team.
    """
    __tablename__ = "injury_reports"

    id = Column(Integer, primary_key=True)
    team_id = Column(Integer, ForeignKey("nfl_teams.id"), nullable=False, index=True)

    # Player info
    espn_athlete_id = Column(String(32), nullable=True, index=True)
    athlete_name = Column(String(128), nullable=False)
    position = Column(String(16), nullable=True)      # QB, WR, RB, TE, OL, LB, DB, ...
    jersey_number = Column(String(8), nullable=True)

    # Injury status
    status = Column(String(32), nullable=False)       # Out, Doubtful, Questionable, Probable
    injury_type = Column(String(64), nullable=True)   # Ankle, Knee, Hamstring, ...

    # Impact flags (set during ingestion)
    is_qb = Column(Boolean, default=False)            # True when position = QB
    is_key_player = Column(Boolean, default=False)    # QB, starting WR/RB/TE, impact DL/LB

    # Timestamps
    reported_at = Column(DateTime, nullable=True)     # date field from ESPN response
    captured_at = Column(DateTime, default=datetime.utcnow)

    team = relationship("NFLTeam")


# ── Analysis ──────────────────────────────────────────────────────────────────

class EdgeScore(Base):
    __tablename__ = "edge_scores"

    id = Column(Integer, primary_key=True)
    game_id = Column(Integer, ForeignKey("nfl_games.id"), nullable=False, index=True)
    calculated_at = Column(DateTime, default=datetime.utcnow)

    # Component scores (0–100 each)
    line_move_score = Column(Float, nullable=True)
    sharp_money_score = Column(Float, nullable=True)
    weather_impact_score = Column(Float, nullable=True)
    kalshi_divergence_score = Column(Float, nullable=True)
    public_fade_score = Column(Float, nullable=True)
    power_ranking_score = Column(Float, nullable=True)   # NEW — talent gap
    injury_impact_score = Column(Float, nullable=True)   # NEW — key injuries

    # Composite
    composite_score = Column(Float, nullable=True)
    recommendation = Column(String(32), nullable=True)  # home_spread, away_spread, over, under, none
    confidence = Column(String(16), nullable=True)       # low, medium, high
    notes = Column(Text, nullable=True)

    raw_inputs = Column(JSON, nullable=True)

    game = relationship("NFLGame", back_populates="edge_scores")
