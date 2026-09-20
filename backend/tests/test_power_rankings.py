"""
Tests for the power rankings adapter and edge engine integration.
"""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from app.ingestion.power_rankings_adapter import (
    fetch_power_rankings,
    fetch_power_rankings_v2,
    _remap,
    _fv,
    _iv,
)
from app.analysis.edge_engine import calculate_edge, GameSnapshot


# ── Unit tests: adapter helpers ───────────────────────────────────────────────

def test_remap_washington():
    assert _remap("WSH") == "WAS"

def test_remap_unknown_passthrough():
    assert _remap("KC") == "KC"

def test_fv_normal():
    assert _fv(12.5) == 12.5

def test_fv_none():
    assert _fv(None) is None

def test_fv_string_number():
    assert _fv("7.3") == 7.3

def test_iv_normal():
    assert _iv(3) == 3

def test_iv_float():
    assert _iv(3.9) == 3   # truncated to int

def test_iv_none():
    assert _iv(None) is None


# ── Adapter: FPI endpoint fallback to standings ────────────────────────────────

@pytest.mark.asyncio
async def test_fetch_power_rankings_returns_empty_on_network_error():
    with patch("app.ingestion.power_rankings_adapter.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__.return_value.get = AsyncMock(
            side_effect=Exception("Connection refused")
        )
        result = await fetch_power_rankings(season=2026, week=1)
    assert isinstance(result, list)
    # Falls back to standings which also fails → returns []
    assert result == []


@pytest.mark.asyncio
async def test_fetch_power_rankings_v2_falls_back_on_empty_response():
    """v2 falls back to v1 when ESPN returns an empty items list."""
    empty_response = MagicMock()
    empty_response.raise_for_status = MagicMock()
    empty_response.json = MagicMock(return_value={"powerIndexes": []})

    with patch("app.ingestion.power_rankings_adapter.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__.return_value.get = AsyncMock(
            return_value=empty_response
        )
        result = await fetch_power_rankings_v2(season=2026, week=1)
    # Falls back to v1 → also gets empty → []
    assert isinstance(result, list)


# ── Edge engine: power ranking component ─────────────────────────────────────

def test_power_ranking_score_zero_when_no_ranks():
    snap = GameSnapshot(
        game_id=1,
        home_team="KC",
        away_team="LV",
        home_overall_rank=None,
        away_overall_rank=None,
    )
    result = calculate_edge(snap)
    assert result.power_ranking_score == 0.0


def test_power_ranking_score_large_gap():
    """Rank 1 vs rank 32 → max power ranking score (100)."""
    snap = GameSnapshot(
        game_id=2,
        home_team="KC",
        away_team="NE",
        home_overall_rank=1,
        away_overall_rank=32,
    )
    result = calculate_edge(snap)
    assert result.power_ranking_score == 100.0


def test_power_ranking_score_small_gap():
    """Adjacent ranks → very low score."""
    snap = GameSnapshot(
        game_id=3,
        home_team="KC",
        away_team="BUF",
        home_overall_rank=5,
        away_overall_rank=7,
    )
    result = calculate_edge(snap)
    # Gap of 2 → 2/15 * 100 ≈ 13.3
    assert 10 < result.power_ranking_score < 20


def test_power_ranking_score_uses_fpi_when_ranks_unavailable():
    """FPI fallback: 10-pt gap yields max 100."""
    snap = GameSnapshot(
        game_id=4,
        home_team="KC",
        away_team="NYG",
        home_overall_rank=None,
        away_overall_rank=None,
        home_fpi=15.0,
        away_fpi=5.0,
    )
    result = calculate_edge(snap)
    assert result.power_ranking_score == 100.0


def test_power_ranking_score_uses_point_diff_fallback():
    """Point diff fallback: 14-ppg gap = max 100."""
    snap = GameSnapshot(
        game_id=5,
        home_team="KC",
        away_team="CHI",
        home_overall_rank=None,
        away_overall_rank=None,
        home_fpi=None,
        away_fpi=None,
        home_point_diff=10.0,
        away_point_diff=-4.0,
    )
    result = calculate_edge(snap)
    assert result.power_ranking_score == 100.0


def test_power_ranking_note_generated_for_large_gap():
    snap = GameSnapshot(
        game_id=6,
        home_team="KC",
        away_team="CLE",
        home_overall_rank=2,
        away_overall_rank=28,
    )
    result = calculate_edge(snap)
    assert any("Power ranking gap" in n for n in result.notes)


def test_composite_includes_power_ranking():
    """Composite score should be non-zero when only power ranking fires."""
    snap = GameSnapshot(
        game_id=7,
        home_team="KC",
        away_team="NE",
        home_overall_rank=1,
        away_overall_rank=32,
    )
    result = calculate_edge(snap)
    # Only power_ranking_score is non-zero: 100 * 0.12 = 12
    assert result.composite_score == pytest.approx(12.0, abs=0.5)
