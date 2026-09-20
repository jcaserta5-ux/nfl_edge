"""Tests for the edge scoring engine."""
import pytest
from app.analysis.edge_engine import calculate_edge, GameSnapshot


def make_snap(**kwargs) -> GameSnapshot:
    defaults = dict(game_id=1, home_team="NE", away_team="BUF", is_dome=False)
    defaults.update(kwargs)
    return GameSnapshot(**defaults)


def test_no_data_scores_zero():
    snap = make_snap()
    result = calculate_edge(snap)
    assert result.composite_score == 0.0
    assert result.recommendation == "none"
    assert result.confidence == "low"


def test_line_move_increases_score():
    snap = make_snap(home_spread=-7.0, home_spread_open=-5.0)
    result = calculate_edge(snap)
    assert result.line_move_score > 0


def test_large_line_move_caps_at_100():
    snap = make_snap(home_spread=-10.0, home_spread_open=-4.0)
    result = calculate_edge(snap)
    assert result.line_move_score <= 100.0


def test_sharp_money_signal():
    # 30% bets on home but 70% of money — sharp lean home
    snap = make_snap(home_spread_pct=30.0, home_money_pct=70.0)
    result = calculate_edge(snap)
    assert result.sharp_money_score > 0


def test_dome_game_zero_weather():
    snap = make_snap(is_dome=True, wind_mph=50.0, temp_f=10.0)
    result = calculate_edge(snap)
    assert result.weather_impact_score == 0.0


def test_high_wind_raises_weather_score():
    snap = make_snap(wind_mph=30.0)
    result = calculate_edge(snap)
    assert result.weather_impact_score > 0


def test_snow_raises_weather_score():
    snap = make_snap(wind_mph=5.0, snow_mm=3.0)
    result = calculate_edge(snap)
    assert result.weather_impact_score > 0
    assert any("snow" in n.lower() or "Snow" in n for n in result.notes)


def test_public_fade_heavy_public():
    snap = make_snap(home_spread_pct=75.0)
    result = calculate_edge(snap)
    assert result.public_fade_score > 0


def test_public_fade_balanced_no_signal():
    snap = make_snap(home_spread_pct=50.0)
    result = calculate_edge(snap)
    assert result.public_fade_score == 0.0


def test_high_composite_gives_high_confidence():
    snap = make_snap(
        home_spread=-7.0, home_spread_open=-4.0,       # big line move
        home_spread_pct=72.0, home_money_pct=38.0,      # sharp fade public
        wind_mph=28.0, temp_f=22.0,                      # bad weather
    )
    result = calculate_edge(snap)
    assert result.composite_score >= 45
    assert result.confidence in ("medium", "high")


def test_under_recommendation_on_weather():
    snap = make_snap(wind_mph=30.0, temp_f=20.0, snow_mm=2.0)
    result = calculate_edge(snap)
    # Weather dominant — should lean under
    if result.recommendation != "none":
        assert result.recommendation in ("under", "investigate")


def test_notes_populated():
    snap = make_snap(
        home_spread=-7.0, home_spread_open=-4.5,
        home_spread_pct=70.0, home_money_pct=38.0,
    )
    result = calculate_edge(snap)
    assert isinstance(result.notes, list)
