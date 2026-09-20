"""
Edge detection engine.
Combines line movement, sharp money, weather impact, Kalshi divergence,
public fade, power ranking differential, and injury impact into a
composite score (0–100) per game per market.

Weight breakdown (must sum to 1.0):
  line_move          0.20  — sharp line movement signals
  sharp_money        0.25  — money % vs bet % divergence
  weather_impact     0.12  — wind/cold/precip suppresses totals
  kalshi_divergence  0.10  — prediction market vs spread divergence (deferred)
  public_fade        0.13  — fading the public square
  power_ranking      0.12  — talent gap between teams (FPI differential)
  injury_impact      0.08  — key player availability advantage
                    ──────
  Total              1.00
"""
from __future__ import annotations
import logging
import math
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# ── Score weights (must sum to 1.0) ──────────────────────────────────────────
WEIGHTS = {
    "line_move":          0.20,
    "sharp_money":        0.25,
    "weather_impact":     0.12,
    "kalshi_divergence":  0.10,
    "public_fade":        0.13,
    "power_ranking":      0.12,
    "injury_impact":      0.08,
}
assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9, "Weights must sum to 1.0"


@dataclass
class GameSnapshot:
    game_id: int
    home_team: str
    away_team: str
    is_dome: bool = False

    # Odds
    home_spread: Optional[float] = None
    home_spread_open: Optional[float] = None   # opening line
    total: Optional[float] = None
    total_open: Optional[float] = None

    # Public money
    home_spread_pct: Optional[float] = None    # % of bets on home spread
    home_money_pct: Optional[float] = None     # % of money on home spread
    over_pct: Optional[float] = None
    total_bet_count: Optional[int] = None

    # Kalshi (deferred — scores 0 while deferred)
    kalshi_home_yes: Optional[float] = None    # implied prob (0-1)
    kalshi_total_over_yes: Optional[float] = None

    # Weather
    wind_mph: Optional[float] = None
    temp_f: Optional[float] = None
    precip_mm: Optional[float] = None
    snow_mm: Optional[float] = None

    # Power rankings (NEW)
    home_overall_rank: Optional[int] = None    # 1–32, lower = better
    away_overall_rank: Optional[int] = None
    home_fpi: Optional[float] = None           # raw FPI score
    away_fpi: Optional[float] = None
    home_point_diff: Optional[float] = None    # pts per game differential
    away_point_diff: Optional[float] = None

    # Injuries (NEW) — pre-computed impact scores from injury_adapter
    home_injury_impact: Optional[float] = None  # 0–100 from compute_injury_impact
    away_injury_impact: Optional[float] = None
    injury_notes: list[str] = field(default_factory=list)


@dataclass
class EdgeResult:
    game_id: int
    line_move_score: float = 0.0
    sharp_money_score: float = 0.0
    weather_impact_score: float = 0.0
    kalshi_divergence_score: float = 0.0
    public_fade_score: float = 0.0
    power_ranking_score: float = 0.0   # NEW
    injury_impact_score: float = 0.0   # NEW
    composite_score: float = 0.0
    recommendation: str = "none"
    confidence: str = "low"
    notes: list[str] = field(default_factory=list)


def calculate_edge(snap: GameSnapshot) -> EdgeResult:
    result = EdgeResult(game_id=snap.game_id)
    notes: list[str] = []

    # 1 ── Line Movement Score ─────────────────────────────────────────────────
    lm = 0.0
    if snap.home_spread is not None and snap.home_spread_open is not None:
        move = snap.home_spread - snap.home_spread_open
        lm = min(abs(move) / 3.0 * 100, 100)  # 3-pt move = max score
        if abs(move) >= 1.5:
            direction = "home" if move > 0 else "away"
            notes.append(f"Line moved {abs(move):.1f} pts toward {direction}")
    result.line_move_score = lm

    # 2 ── Sharp Money Score ───────────────────────────────────────────────────
    sm = 0.0
    if snap.home_spread_pct is not None and snap.home_money_pct is not None:
        # Sharp signal: money % diverges from bet % in opposite direction
        divergence = snap.home_money_pct - snap.home_spread_pct
        sm = min(abs(divergence) / 20.0 * 100, 100)
        if abs(divergence) >= 10:
            side = "home" if divergence > 0 else "away"
            notes.append(
                f"Sharp money on {side} ({abs(divergence):.0f}% money vs bet split)"
            )
    result.sharp_money_score = sm

    # 3 ── Weather Impact Score ────────────────────────────────────────────────
    wi = 0.0
    if not snap.is_dome:
        wind_score = 0.0
        precip_score = 0.0
        temp_score = 0.0

        if snap.wind_mph is not None:
            wind_score = min(max((snap.wind_mph - 10) / 25.0, 0) * 100, 100)
            if snap.wind_mph >= 20:
                notes.append(f"Wind {snap.wind_mph:.0f} mph — totals may be suppressed")

        if snap.precip_mm is not None:
            precip_score = min(snap.precip_mm / 10.0 * 100, 100)

        if snap.snow_mm is not None and snap.snow_mm > 0:
            precip_score = min(precip_score + snap.snow_mm / 5.0 * 100, 100)
            notes.append(f"Snow forecasted ({snap.snow_mm:.1f} mm) — strong under lean")

        if snap.temp_f is not None and snap.temp_f < 25:
            temp_score = min((25 - snap.temp_f) / 15.0 * 100, 100)
            notes.append(f"Extreme cold ({snap.temp_f:.0f}°F) — consider under")

        wi = wind_score * 0.5 + precip_score * 0.3 + temp_score * 0.2
    result.weather_impact_score = wi

    # 4 ── Kalshi Divergence Score ─────────────────────────────────────────────
    kd = 0.0
    if snap.kalshi_home_yes is not None and snap.home_spread is not None:
        spread_implied = _spread_to_win_prob(snap.home_spread)
        kalshi_implied = snap.kalshi_home_yes
        divergence = abs(kalshi_implied - spread_implied)
        kd = min(divergence / 0.10 * 100, 100)
        if divergence >= 0.05:
            direction = "overvalued" if kalshi_implied > spread_implied else "undervalued"
            notes.append(
                f"Kalshi home win prob {kalshi_implied:.0%} vs spread-implied"
                f" {spread_implied:.0%} ({direction})"
            )
    result.kalshi_divergence_score = kd

    # 5 ── Public Fade Score ───────────────────────────────────────────────────
    pf = 0.0
    if snap.home_spread_pct is not None:
        public_lean = max(snap.home_spread_pct, 100 - snap.home_spread_pct)
        if public_lean >= 65:
            pf = min((public_lean - 65) / 20.0 * 100, 100)
            faded_side = "home" if snap.home_spread_pct > 50 else "away"
            fade_side = "away" if faded_side == "home" else "home"
            notes.append(
                f"{public_lean:.0f}% public on {faded_side} spread — fade to {fade_side}"
            )
    result.public_fade_score = pf

    # 6 ── Power Ranking Score (NEW) ───────────────────────────────────────────
    pr = 0.0
    if snap.home_overall_rank is not None and snap.away_overall_rank is not None:
        # Rank differential: max gap is 31 (rank 1 vs rank 32)
        # A large talent gap = high score, helping the better team's side
        rank_gap = abs(snap.away_overall_rank - snap.home_overall_rank)
        pr = min(rank_gap / 15.0 * 100, 100)  # 15-rank gap = max
        if rank_gap >= 8:
            better_team = (
                snap.home_team if snap.home_overall_rank < snap.away_overall_rank
                else snap.away_team
            )
            worse_team = (
                snap.away_team if snap.home_overall_rank < snap.away_overall_rank
                else snap.home_team
            )
            notes.append(
                f"Power ranking gap: #{snap.home_overall_rank} {snap.home_team} vs"
                f" #{snap.away_overall_rank} {snap.away_team} — talent edge for {better_team}"
            )
    elif snap.home_fpi is not None and snap.away_fpi is not None:
        # FPI-based score if ranks unavailable
        fpi_gap = abs(snap.home_fpi - snap.away_fpi)
        pr = min(fpi_gap / 10.0 * 100, 100)  # 10-pt FPI gap = max
        if fpi_gap >= 5:
            better = snap.home_team if snap.home_fpi > snap.away_fpi else snap.away_team
            notes.append(
                f"FPI differential: {snap.home_team} {snap.home_fpi:+.1f} vs"
                f" {snap.away_team} {snap.away_fpi:+.1f} — edge to {better}"
            )
    elif snap.home_point_diff is not None and snap.away_point_diff is not None:
        # Point differential fallback
        pd_gap = abs(snap.home_point_diff - snap.away_point_diff)
        pr = min(pd_gap / 14.0 * 100, 100)  # 14 ppg gap = max
        if pd_gap >= 7:
            better = snap.home_team if snap.home_point_diff > snap.away_point_diff else snap.away_team
            notes.append(
                f"Point diff: {snap.home_team} ({snap.home_point_diff:+.1f}) vs"
                f" {snap.away_team} ({snap.away_point_diff:+.1f}) — quality edge to {better}"
            )
    result.power_ranking_score = round(pr, 1)

    # 7 ── Injury Impact Score (NEW) ───────────────────────────────────────────
    ii = 0.0
    if snap.home_injury_impact is not None and snap.away_injury_impact is not None:
        # Use the pre-computed net impact from injury_adapter.compute_injury_impact
        net = abs(snap.away_injury_impact - snap.home_injury_impact)
        ii = min(net, 100)
        for note in snap.injury_notes:
            notes.append(note)
    elif snap.home_injury_impact is not None:
        ii = min(snap.home_injury_impact, 100)
        for note in snap.injury_notes:
            notes.append(note)
    result.injury_impact_score = round(ii, 1)

    # ── Composite ─────────────────────────────────────────────────────────────
    composite = (
        WEIGHTS["line_move"]         * result.line_move_score
        + WEIGHTS["sharp_money"]     * result.sharp_money_score
        + WEIGHTS["weather_impact"]  * result.weather_impact_score
        + WEIGHTS["kalshi_divergence"] * result.kalshi_divergence_score
        + WEIGHTS["public_fade"]     * result.public_fade_score
        + WEIGHTS["power_ranking"]   * result.power_ranking_score
        + WEIGHTS["injury_impact"]   * result.injury_impact_score
    )
    result.composite_score = round(composite, 1)

    # ── Confidence tier ───────────────────────────────────────────────────────
    if composite >= 68:
        result.confidence = "high"
    elif composite >= 42:
        result.confidence = "medium"
    else:
        result.confidence = "low"

    # ── Recommendation ────────────────────────────────────────────────────────
    result.recommendation = _derive_recommendation(snap, result)
    result.notes = notes
    return result


def _derive_recommendation(snap: GameSnapshot, result: EdgeResult) -> str:
    """Pick the specific market to flag based on which signals fired."""
    if result.composite_score < 28:
        return "none"

    weather_dominant = result.weather_impact_score >= 60
    sharp_on_under = (
        snap.over_pct is not None and snap.over_pct >= 65
        and result.sharp_money_score >= 50
    )
    if weather_dominant or sharp_on_under:
        return "under"

    # Power ranking + injury combined suggest side bet
    pr_and_injury_favor_home = (
        snap.home_overall_rank is not None
        and snap.away_overall_rank is not None
        and snap.home_overall_rank < snap.away_overall_rank   # home is better team
        and (snap.away_injury_impact or 0) > (snap.home_injury_impact or 0) + 2
    )
    pr_and_injury_favor_away = (
        snap.home_overall_rank is not None
        and snap.away_overall_rank is not None
        and snap.away_overall_rank < snap.home_overall_rank   # away is better team
        and (snap.home_injury_impact or 0) > (snap.away_injury_impact or 0) + 2
    )
    if pr_and_injury_favor_home and result.power_ranking_score >= 50:
        return "home_spread"
    if pr_and_injury_favor_away and result.power_ranking_score >= 50:
        return "away_spread"

    # Sharp money + line move alignment
    if result.sharp_money_score >= 50 and result.line_move_score >= 40:
        if snap.home_money_pct is not None and snap.home_money_pct > 55:
            return "home_spread"
        return "away_spread"

    # Public fade
    if result.public_fade_score >= 50 and snap.home_spread_pct is not None:
        return "away_spread" if snap.home_spread_pct > 60 else "home_spread"

    return "investigate"


def _spread_to_win_prob(spread: float) -> float:
    """Convert a point spread to an approximate win probability."""
    return 1 / (1 + math.exp(spread * 0.15))
