"""
Tests for the injury report adapter and edge engine injury integration.
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import patch, AsyncMock, MagicMock

from app.ingestion.injury_adapter import (
    fetch_injuries,
    compute_injury_impact,
    _normalise_status,
    _parse_date,
    _team_injury_impact,
    _remap,
)
from app.analysis.edge_engine import calculate_edge, GameSnapshot


# ── Unit tests: normalise_status ──────────────────────────────────────────────

def test_normalise_out():
    assert _normalise_status("out") == "Out"

def test_normalise_doubtful():
    assert _normalise_status("Doubtful") == "Doubtful"

def test_normalise_questionable():
    assert _normalise_status("questionable") == "Questionable"

def test_normalise_ir():
    assert _normalise_status("injured reserve") == "IR"
    assert _normalise_status("ir") == "IR"

def test_normalise_unknown_passthrough():
    assert _normalise_status("Active") == "Active"


# ── Unit tests: _parse_date ───────────────────────────────────────────────────

def test_parse_date_iso_utc():
    dt = _parse_date("2026-09-18T00:00:00Z")
    assert dt is not None
    assert dt.year == 2026
    assert dt.month == 9

def test_parse_date_none():
    assert _parse_date(None) is None

def test_parse_date_empty():
    assert _parse_date("") is None

def test_parse_date_bad_format():
    assert _parse_date("not-a-date") is None


# ── Unit tests: remap ─────────────────────────────────────────────────────────

def test_remap_jax_to_jac():
    # No default remap — JAX passes through; remaps are WSH→WAS
    assert _remap("WSH") == "WAS"

def test_remap_passthrough():
    assert _remap("KC") == "KC"
    assert _remap("BUF") == "BUF"


# ── Unit tests: _team_injury_impact ──────────────────────────────────────────

def test_team_impact_qb_out():
    injuries = [
        {"is_qb": True, "is_key_player": True, "status": "Out"},
    ]
    score = _team_injury_impact(injuries)
    assert score == 3.0 * 5.0    # weight 3.0 × QB multiplier 5.0 = 15.0

def test_team_impact_qb_questionable():
    injuries = [
        {"is_qb": True, "is_key_player": True, "status": "Questionable"},
    ]
    score = _team_injury_impact(injuries)
    assert score == 1.0 * 5.0    # weight 1.0 × 5.0 = 5.0

def test_team_impact_non_qb_key_out():
    injuries = [
        {"is_qb": False, "is_key_player": True, "status": "Out"},
    ]
    score = _team_injury_impact(injuries)
    assert score == 3.0           # weight 3.0 × 1.0

def test_team_impact_empty():
    assert _team_injury_impact([]) == 0.0

def test_team_impact_non_key_ignored():
    injuries = [
        {"is_qb": False, "is_key_player": False, "status": "Out"},
    ]
    # Non-key players don't contribute to score
    assert _team_injury_impact(injuries) == 0.0


# ── compute_injury_impact ─────────────────────────────────────────────────────

def test_compute_impact_balanced():
    """When both teams have the same injuries, net score is 0."""
    inj = [{"is_qb": False, "is_key_player": True, "status": "Questionable"}]
    score, notes = compute_injury_impact(inj, inj)
    assert score == 0.0

def test_compute_impact_qb_out_home():
    home_injuries = [
        {"is_qb": True, "is_key_player": True, "status": "Out", "athlete_name": "T. Brady"},
    ]
    away_injuries = []
    score, notes = compute_injury_impact(home_injuries, away_injuries)
    # home more injured → net is away_impact(0) - home_impact(15) = 15
    # abs(15) / 8 * 100 = 100 (capped)
    assert score == 100.0
    assert any("QB" in n or "T. Brady" in n for n in notes)

def test_compute_impact_qb_questionable_generates_note():
    home_injuries = [
        {"is_qb": True, "is_key_player": True, "status": "Questionable", "athlete_name": "J. Burrow"},
    ]
    _, notes = compute_injury_impact(home_injuries, [])
    assert any("Questionable" in n for n in notes)

def test_compute_impact_multiple_key_away():
    home_injuries = []
    away_injuries = [
        {"is_qb": False, "is_key_player": True, "status": "Out"},
        {"is_qb": False, "is_key_player": True, "status": "Doubtful"},
        {"is_qb": False, "is_key_player": True, "status": "Out"},
    ]
    score, notes = compute_injury_impact(home_injuries, away_injuries)
    assert score > 0
    assert any("away" in n.lower() for n in notes)

def test_compute_impact_returns_float_and_list():
    score, notes = compute_injury_impact([], [])
    assert isinstance(score, float)
    assert isinstance(notes, list)


# ── Adapter: network fetch ────────────────────────────────────────────────────

ESPN_INJURY_SAMPLE = {
    "injuries": [
        {
            "team": {"abbreviation": "KC", "id": "12", "displayName": "Kansas City Chiefs"},
            "injuries": [
                {
                    "athlete": {
                        "id": "3139477",
                        "fullName": "Patrick Mahomes",
                        "position": {"abbreviation": "QB"},
                        "jersey": "15",
                    },
                    "status": "Questionable",
                    "type": {"description": "Ankle"},
                    "date": "2026-09-18T00:00:00Z",
                },
                {
                    "athlete": {
                        "id": "1111111",
                        "fullName": "Travis Kelce",
                        "position": {"abbreviation": "TE"},
                        "jersey": "87",
                    },
                    "status": "Out",
                    "type": {"description": "Knee"},
                    "date": "2026-09-17T00:00:00Z",
                },
            ],
        }
    ]
}


@pytest.mark.asyncio
async def test_fetch_injuries_parses_response():
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json = MagicMock(return_value=ESPN_INJURY_SAMPLE)

    with patch("app.ingestion.injury_adapter.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_resp)
        records = await fetch_injuries()

    assert len(records) == 2

    mahomes = next(r for r in records if r["athlete_name"] == "Patrick Mahomes")
    assert mahomes["team_abbreviation"] == "KC"
    assert mahomes["position"] == "QB"
    assert mahomes["status"] == "Questionable"
    assert mahomes["is_qb"] is True
    assert mahomes["is_key_player"] is True

    kelce = next(r for r in records if r["athlete_name"] == "Travis Kelce")
    assert kelce["status"] == "Out"
    assert kelce["is_qb"] is False
    assert kelce["is_key_player"] is True     # TE is in _KEY_POSITIONS


@pytest.mark.asyncio
async def test_fetch_injuries_returns_empty_on_error():
    with patch("app.ingestion.injury_adapter.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__.return_value.get = AsyncMock(
            side_effect=Exception("Timeout")
        )
        records = await fetch_injuries()
    assert records == []


# ── Edge engine: injury component ─────────────────────────────────────────────

def test_injury_score_zero_when_no_data():
    snap = GameSnapshot(
        game_id=10,
        home_team="KC",
        away_team="LV",
        home_injury_impact=None,
        away_injury_impact=None,
    )
    result = calculate_edge(snap)
    assert result.injury_impact_score == 0.0

def test_injury_score_nonzero_when_imbalanced():
    snap = GameSnapshot(
        game_id=11,
        home_team="KC",
        away_team="LV",
        home_injury_impact=15.0,   # home has big QB injury
        away_injury_impact=0.0,
        injury_notes=["🚨 Mahomes (Out) — home QB concern"],
    )
    result = calculate_edge(snap)
    assert result.injury_impact_score > 0
    assert any("Mahomes" in n for n in result.notes)

def test_composite_includes_injury_impact():
    snap = GameSnapshot(
        game_id=12,
        home_team="DAL",
        away_team="NYG",
        home_injury_impact=15.0,
        away_injury_impact=0.0,
        injury_notes=["QB out"],
    )
    result = calculate_edge(snap)
    # injury weight 0.08 × 15 = 1.2 minimum contribution
    assert result.composite_score >= 0.08 * 15 - 0.5
