"""
Weather ingestion adapter using Open-Meteo (free, no API key required).
Fetches hourly forecast for each stadium's GPS coordinates at game time.
"""
import logging
from datetime import datetime, timezone
from typing import Optional
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings

logger = logging.getLogger(__name__)

# NFL stadium coordinates (lat, lon) — update as needed
STADIUM_COORDS: dict[str, tuple[float, float]] = {
    "NE":  (42.0909, -71.2643),  # Gillette Stadium
    "BUF": (42.7738, -78.7870),  # Highmark Stadium
    "MIA": (25.9580, -80.2389),  # Hard Rock Stadium
    "NYJ": (40.8135, -74.0745),  # MetLife Stadium
    "NYG": (40.8135, -74.0745),  # MetLife Stadium
    "BAL": (39.2780, -76.6227),  # M&T Bank Stadium
    "PIT": (40.4468, -80.0158),  # Acrisure Stadium
    "CLE": (41.5061, -81.6995),  # Huntington Bank Field
    "CIN": (39.0954, -84.5160),  # Paycor Stadium
    "TEN": (36.1665, -86.7713),  # Nissan Stadium
    "IND": (39.7601, -86.1639),  # Lucas Oil Stadium (dome)
    "HOU": (29.6847, -95.4107),  # NRG Stadium (dome)
    "JAX": (30.3239, -81.6373),  # EverBank Stadium
    "KC":  (39.0489, -94.4839),  # Arrowhead Stadium
    "LV":  (36.0909, -115.1833), # Allegiant Stadium (dome)
    "LAC": (33.9534, -118.3391), # SoFi Stadium
    "DEN": (39.7439, -105.0201), # Empower Field
    "SEA": (47.5952, -122.3316), # Lumen Field
    "SF":  (37.4032, -121.9697), # Levi's Stadium
    "ARI": (33.5276, -112.2626), # State Farm Stadium (dome)
    "LAR": (33.9534, -118.3391), # SoFi Stadium
    "MIN": (44.9737, -93.2571),  # U.S. Bank Stadium (dome)
    "CHI": (41.8623, -87.6167),  # Soldier Field
    "GB":  (44.5013, -88.0622),  # Lambeau Field
    "DET": (42.3400, -83.0456),  # Ford Field (dome)
    "ATL": (33.7553, -84.4006),  # Mercedes-Benz Stadium (dome)
    "NO":  (29.9511, -90.0812),  # Caesars Superdome (dome)
    "CAR": (35.2258, -80.8528),  # Bank of America Stadium
    "TB":  (27.9759, -82.5033),  # Raymond James Stadium
    "DAL": (32.7473, -97.0945),  # AT&T Stadium (dome)
    "PHI": (39.9008, -75.1675),  # Lincoln Financial Field
    "NYG": (40.8135, -74.0745),  # MetLife Stadium
    "WAS": (38.9078, -76.8645),  # Northwest Stadium
}

DOME_TEAMS = {"IND", "LV", "ARI", "MIN", "DET", "ATL", "NO", "DAL", "HOU"}


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def fetch_game_weather(
    home_team: str,
    game_time: datetime,
) -> Optional[dict]:
    """
    Fetch Open-Meteo hourly forecast for the game location and time.
    Returns a normalized weather dict. Returns None for dome games.
    """
    if home_team in DOME_TEAMS:
        return {
            "is_dome": True,
            "temp_f": 72.0,
            "wind_mph": 0.0,
            "wind_dir_deg": 0,
            "precip_mm": 0.0,
            "snow_mm": 0.0,
            "humidity_pct": 45.0,
            "cloud_cover_pct": 0.0,
            "condition_desc": "Indoor",
        }

    coords = STADIUM_COORDS.get(home_team)
    if not coords:
        logger.warning("No stadium coordinates for team: %s", home_team)
        return None

    lat, lon = coords
    # Format date for Open-Meteo
    date_str = game_time.strftime("%Y-%m-%d")

    url = f"{settings.OPEN_METEO_BASE_URL}/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": ",".join([
            "temperature_2m",
            "precipitation",
            "snowfall",
            "windspeed_10m",
            "winddirection_10m",
            "relativehumidity_2m",
            "cloudcover",
            "weathercode",
        ]),
        "temperature_unit": "fahrenheit",
        "windspeed_unit": "mph",
        "precipitation_unit": "mm",
        "start_date": date_str,
        "end_date": date_str,
        "timezone": "America/New_York",
    }

    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(url, params=params)
        r.raise_for_status()
        data = r.json()

    return _extract_hour(data, game_time)


def _extract_hour(data: dict, game_time: datetime) -> Optional[dict]:
    """Pick the forecast hour closest to game_time."""
    hourly = data.get("hourly", {})
    times = hourly.get("time", [])
    if not times:
        return None

    target_str = game_time.strftime("%Y-%m-%dT%H:00")
    try:
        idx = times.index(target_str)
    except ValueError:
        # Fall back to closest hour
        from bisect import bisect_left
        idx = bisect_left(times, target_str)
        idx = min(idx, len(times) - 1)

    def val(key: str):
        values = hourly.get(key, [])
        return values[idx] if idx < len(values) else None

    weather_code = val("weathercode") or 0
    return {
        "is_dome": False,
        "temp_f": val("temperature_2m"),
        "wind_mph": val("windspeed_10m"),
        "wind_dir_deg": val("winddirection_10m"),
        "precip_mm": val("precipitation"),
        "snow_mm": val("snowfall"),
        "humidity_pct": val("relativehumidity_2m"),
        "cloud_cover_pct": val("cloudcover"),
        "condition_code": weather_code,
        "condition_desc": _wmo_description(weather_code),
    }


def _wmo_description(code: int) -> str:
    """Map WMO weather code to human-readable description."""
    mapping = {
        0: "Clear", 1: "Mainly Clear", 2: "Partly Cloudy", 3: "Overcast",
        45: "Fog", 48: "Icy Fog",
        51: "Light Drizzle", 53: "Drizzle", 55: "Heavy Drizzle",
        61: "Light Rain", 63: "Rain", 65: "Heavy Rain",
        71: "Light Snow", 73: "Snow", 75: "Heavy Snow",
        80: "Rain Showers", 81: "Rain Showers", 82: "Heavy Rain Showers",
        85: "Snow Showers", 86: "Heavy Snow Showers",
        95: "Thunderstorm", 96: "Thunderstorm w/ Hail", 99: "Thunderstorm w/ Heavy Hail",
    }
    return mapping.get(code, f"Code {code}")
