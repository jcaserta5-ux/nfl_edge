"""add power_rankings, injury_reports, and new edge_scores columns

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-19
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── power_rankings ────────────────────────────────────────────────────────
    op.create_table(
        "power_rankings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("team_id", sa.Integer(), sa.ForeignKey("nfl_teams.id"), nullable=False),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("week", sa.Integer(), nullable=False),
        # ESPN FPI fields
        sa.Column("fpi_score", sa.Float(), nullable=True),
        sa.Column("overall_rank", sa.Integer(), nullable=True),
        sa.Column("offensive_rank", sa.Integer(), nullable=True),
        sa.Column("defensive_rank", sa.Integer(), nullable=True),
        sa.Column("sos_rank", sa.Integer(), nullable=True),
        # Standings fallback fields
        sa.Column("wins", sa.Integer(), nullable=True),
        sa.Column("losses", sa.Integer(), nullable=True),
        sa.Column("win_pct", sa.Float(), nullable=True),
        sa.Column("points_for", sa.Float(), nullable=True),
        sa.Column("points_against", sa.Float(), nullable=True),
        sa.Column("point_diff", sa.Float(), nullable=True),
        # Meta
        sa.Column("source", sa.String(16), server_default="'fpi'"),
        sa.Column("captured_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_power_rankings_team_id", "power_rankings", ["team_id"])
    op.create_unique_constraint(
        "uq_power_rankings_team_season_week",
        "power_rankings",
        ["team_id", "season", "week"],
    )

    # ── injury_reports ────────────────────────────────────────────────────────
    op.create_table(
        "injury_reports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("team_id", sa.Integer(), sa.ForeignKey("nfl_teams.id"), nullable=False),
        # Player info
        sa.Column("espn_athlete_id", sa.String(32), nullable=True),
        sa.Column("athlete_name", sa.String(128), nullable=False),
        sa.Column("position", sa.String(16), nullable=True),
        sa.Column("jersey_number", sa.String(8), nullable=True),
        # Injury fields
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("injury_type", sa.String(64), nullable=True),
        # Impact flags
        sa.Column("is_qb", sa.Boolean(), server_default="false"),
        sa.Column("is_key_player", sa.Boolean(), server_default="false"),
        # Timestamps
        sa.Column("reported_at", sa.DateTime(), nullable=True),
        sa.Column("captured_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_injury_reports_team_id", "injury_reports", ["team_id"])
    op.create_index("ix_injury_reports_espn_athlete_id", "injury_reports", ["espn_athlete_id"])

    # ── edge_scores — add two new component columns ───────────────────────────
    op.add_column("edge_scores", sa.Column("power_ranking_score", sa.Float(), nullable=True))
    op.add_column("edge_scores", sa.Column("injury_impact_score", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("edge_scores", "injury_impact_score")
    op.drop_column("edge_scores", "power_ranking_score")
    op.drop_index("ix_injury_reports_espn_athlete_id", "injury_reports")
    op.drop_index("ix_injury_reports_team_id", "injury_reports")
    op.drop_table("injury_reports")
    op.drop_constraint("uq_power_rankings_team_season_week", "power_rankings", type_="unique")
    op.drop_index("ix_power_rankings_team_id", "power_rankings")
    op.drop_table("power_rankings")
