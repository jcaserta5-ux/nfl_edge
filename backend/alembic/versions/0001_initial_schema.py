"""initial schema

Revision ID: 0001
Revises: 
Create Date: 2026-09-19
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── invite_codes ──────────────────────────────────────────────────────────
    op.create_table(
        "invite_codes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(32), nullable=False, unique=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("used_by", sa.Integer(), nullable=True),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_invite_codes_code", "invite_codes", ["code"])

    # ── users ─────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("username", sa.String(64), nullable=False, unique=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("is_admin", sa.Boolean(), server_default="false"),
        sa.Column("invite_code_used", sa.String(32), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("last_login", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_users_email", "users", ["email"])

    # Add FK from invite_codes → users now that users table exists
    op.create_foreign_key("fk_invite_created_by", "invite_codes", "users", ["created_by"], ["id"])
    op.create_foreign_key("fk_invite_used_by",    "invite_codes", "users", ["used_by"],    ["id"])

    # ── nfl_teams ─────────────────────────────────────────────────────────────
    op.create_table(
        "nfl_teams",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("abbreviation", sa.String(5), nullable=False, unique=True),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("city", sa.String(64), nullable=False),
        sa.Column("stadium_name", sa.String(128), nullable=True),
        sa.Column("stadium_lat", sa.Float(), nullable=True),
        sa.Column("stadium_lon", sa.Float(), nullable=True),
        sa.Column("is_dome", sa.Boolean(), server_default="false"),
        sa.Column("turf_type", sa.String(32), nullable=True),
    )

    # ── nfl_games ─────────────────────────────────────────────────────────────
    op.create_table(
        "nfl_games",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("external_id", sa.String(64), nullable=True),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("week", sa.Integer(), nullable=False),
        sa.Column("game_time", sa.DateTime(), nullable=False),
        sa.Column("home_team_id", sa.Integer(), sa.ForeignKey("nfl_teams.id"), nullable=False),
        sa.Column("away_team_id", sa.Integer(), sa.ForeignKey("nfl_teams.id"), nullable=False),
        sa.Column("home_score", sa.Integer(), nullable=True),
        sa.Column("away_score", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(32), server_default="'scheduled'"),
    )
    op.create_index("ix_nfl_games_external_id", "nfl_games", ["external_id"])
    op.create_unique_constraint(
        "uq_nfl_games_season_week_teams",
        "nfl_games",
        ["season", "week", "home_team_id", "away_team_id"],
    )

    # ── odds_snapshots ────────────────────────────────────────────────────────
    op.create_table(
        "odds_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("game_id", sa.Integer(), sa.ForeignKey("nfl_games.id"), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("captured_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("home_spread", sa.Float(), nullable=True),
        sa.Column("away_spread", sa.Float(), nullable=True),
        sa.Column("home_spread_juice", sa.Integer(), nullable=True),
        sa.Column("away_spread_juice", sa.Integer(), nullable=True),
        sa.Column("home_ml", sa.Integer(), nullable=True),
        sa.Column("away_ml", sa.Integer(), nullable=True),
        sa.Column("total", sa.Float(), nullable=True),
        sa.Column("over_juice", sa.Integer(), nullable=True),
        sa.Column("under_juice", sa.Integer(), nullable=True),
        sa.Column("home_spread_pct", sa.Float(), nullable=True),
        sa.Column("away_spread_pct", sa.Float(), nullable=True),
        sa.Column("over_pct", sa.Float(), nullable=True),
        sa.Column("under_pct", sa.Float(), nullable=True),
        sa.Column("home_ml_pct", sa.Float(), nullable=True),
        sa.Column("away_ml_pct", sa.Float(), nullable=True),
        sa.Column("home_money_pct", sa.Float(), nullable=True),
        sa.Column("away_money_pct", sa.Float(), nullable=True),
        sa.Column("total_bet_count", sa.Integer(), nullable=True),
    )
    op.create_index("ix_odds_snapshots_game_id",     "odds_snapshots", ["game_id"])
    op.create_index("ix_odds_snapshots_captured_at", "odds_snapshots", ["captured_at"])

    # ── weather_readings ──────────────────────────────────────────────────────
    op.create_table(
        "weather_readings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("game_id", sa.Integer(), sa.ForeignKey("nfl_games.id"), nullable=False),
        sa.Column("captured_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("forecast_for", sa.DateTime(), nullable=False),
        sa.Column("temp_f", sa.Float(), nullable=True),
        sa.Column("wind_mph", sa.Float(), nullable=True),
        sa.Column("wind_dir_deg", sa.Integer(), nullable=True),
        sa.Column("precip_mm", sa.Float(), nullable=True),
        sa.Column("snow_mm", sa.Float(), nullable=True),
        sa.Column("humidity_pct", sa.Float(), nullable=True),
        sa.Column("cloud_cover_pct", sa.Float(), nullable=True),
        sa.Column("condition_code", sa.Integer(), nullable=True),
        sa.Column("condition_desc", sa.String(64), nullable=True),
    )
    op.create_index("ix_weather_readings_game_id", "weather_readings", ["game_id"])

    # ── edge_scores ───────────────────────────────────────────────────────────
    op.create_table(
        "edge_scores",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("game_id", sa.Integer(), sa.ForeignKey("nfl_games.id"), nullable=False),
        sa.Column("calculated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("line_move_score", sa.Float(), nullable=True),
        sa.Column("sharp_money_score", sa.Float(), nullable=True),
        sa.Column("weather_impact_score", sa.Float(), nullable=True),
        sa.Column("kalshi_divergence_score", sa.Float(), nullable=True),
        sa.Column("public_fade_score", sa.Float(), nullable=True),
        sa.Column("composite_score", sa.Float(), nullable=True),
        sa.Column("recommendation", sa.String(32), nullable=True),
        sa.Column("confidence", sa.String(16), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("raw_inputs", sa.JSON(), nullable=True),
    )
    op.create_index("ix_edge_scores_game_id", "edge_scores", ["game_id"])


def downgrade() -> None:
    op.drop_table("edge_scores")
    op.drop_table("weather_readings")
    op.drop_table("odds_snapshots")
    op.drop_table("nfl_games")
    op.drop_table("nfl_teams")
    op.drop_constraint("fk_invite_created_by", "invite_codes", type_="foreignkey")
    op.drop_constraint("fk_invite_used_by",    "invite_codes", type_="foreignkey")
    op.drop_table("users")
    op.drop_table("invite_codes")
