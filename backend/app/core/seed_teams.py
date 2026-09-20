"""
Seed all 32 NFL teams with stadium coordinates, dome flags, and turf type.
Run: docker compose exec backend python -m app.core.seed_teams
"""
import asyncio
from app.db.session import AsyncSessionLocal
from app.db.models import NFLTeam
from sqlalchemy import select

TEAMS = [
    # AFC East
    dict(abbreviation="BUF", name="Bills",     city="Buffalo",       stadium_name="Highmark Stadium",         stadium_lat=42.7738,  stadium_lon=-78.7870,  is_dome=False, turf_type="grass"),
    dict(abbreviation="MIA", name="Dolphins",  city="Miami",         stadium_name="Hard Rock Stadium",         stadium_lat=25.9580,  stadium_lon=-80.2389,  is_dome=False, turf_type="grass"),
    dict(abbreviation="NE",  name="Patriots",  city="New England",   stadium_name="Gillette Stadium",          stadium_lat=42.0909,  stadium_lon=-71.2643,  is_dome=False, turf_type="grass"),
    dict(abbreviation="NYJ", name="Jets",      city="New York",      stadium_name="MetLife Stadium",           stadium_lat=40.8135,  stadium_lon=-74.0745,  is_dome=False, turf_type="turf"),
    # AFC North
    dict(abbreviation="BAL", name="Ravens",    city="Baltimore",     stadium_name="M&T Bank Stadium",          stadium_lat=39.2780,  stadium_lon=-76.6227,  is_dome=False, turf_type="turf"),
    dict(abbreviation="CIN", name="Bengals",   city="Cincinnati",    stadium_name="Paycor Stadium",            stadium_lat=39.0954,  stadium_lon=-84.5160,  is_dome=False, turf_type="turf"),
    dict(abbreviation="CLE", name="Browns",    city="Cleveland",     stadium_name="Huntington Bank Field",     stadium_lat=41.5061,  stadium_lon=-81.6995,  is_dome=False, turf_type="grass"),
    dict(abbreviation="PIT", name="Steelers",  city="Pittsburgh",    stadium_name="Acrisure Stadium",          stadium_lat=40.4468,  stadium_lon=-80.0158,  is_dome=False, turf_type="grass"),
    # AFC South
    dict(abbreviation="HOU", name="Texans",    city="Houston",       stadium_name="NRG Stadium",               stadium_lat=29.6847,  stadium_lon=-95.4107,  is_dome=True,  turf_type="grass"),
    dict(abbreviation="IND", name="Colts",     city="Indianapolis",  stadium_name="Lucas Oil Stadium",         stadium_lat=39.7601,  stadium_lon=-86.1639,  is_dome=True,  turf_type="turf"),
    dict(abbreviation="JAX", name="Jaguars",   city="Jacksonville",  stadium_name="EverBank Stadium",          stadium_lat=30.3239,  stadium_lon=-81.6373,  is_dome=False, turf_type="grass"),
    dict(abbreviation="TEN", name="Titans",    city="Tennessee",     stadium_name="Nissan Stadium",            stadium_lat=36.1665,  stadium_lon=-86.7713,  is_dome=False, turf_type="turf"),
    # AFC West
    dict(abbreviation="DEN", name="Broncos",   city="Denver",        stadium_name="Empower Field",             stadium_lat=39.7439,  stadium_lon=-105.0201, is_dome=False, turf_type="grass"),
    dict(abbreviation="KC",  name="Chiefs",    city="Kansas City",   stadium_name="Arrowhead Stadium",         stadium_lat=39.0489,  stadium_lon=-94.4839,  is_dome=False, turf_type="grass"),
    dict(abbreviation="LAC", name="Chargers",  city="Los Angeles",   stadium_name="SoFi Stadium",              stadium_lat=33.9534,  stadium_lon=-118.3391, is_dome=False, turf_type="turf"),
    dict(abbreviation="LV",  name="Raiders",   city="Las Vegas",     stadium_name="Allegiant Stadium",         stadium_lat=36.0909,  stadium_lon=-115.1833, is_dome=True,  turf_type="grass"),
    # NFC East
    dict(abbreviation="DAL", name="Cowboys",   city="Dallas",        stadium_name="AT&T Stadium",              stadium_lat=32.7473,  stadium_lon=-97.0945,  is_dome=True,  turf_type="turf"),
    dict(abbreviation="NYG", name="Giants",    city="New York",      stadium_name="MetLife Stadium",           stadium_lat=40.8135,  stadium_lon=-74.0745,  is_dome=False, turf_type="turf"),
    dict(abbreviation="PHI", name="Eagles",    city="Philadelphia",  stadium_name="Lincoln Financial Field",   stadium_lat=39.9008,  stadium_lon=-75.1675,  is_dome=False, turf_type="grass"),
    dict(abbreviation="WAS", name="Commanders",city="Washington",    stadium_name="Northwest Stadium",         stadium_lat=38.9078,  stadium_lon=-76.8645,  is_dome=False, turf_type="turf"),
    # NFC North
    dict(abbreviation="CHI", name="Bears",     city="Chicago",       stadium_name="Soldier Field",             stadium_lat=41.8623,  stadium_lon=-87.6167,  is_dome=False, turf_type="grass"),
    dict(abbreviation="DET", name="Lions",     city="Detroit",       stadium_name="Ford Field",                stadium_lat=42.3400,  stadium_lon=-83.0456,  is_dome=True,  turf_type="turf"),
    dict(abbreviation="GB",  name="Packers",   city="Green Bay",     stadium_name="Lambeau Field",             stadium_lat=44.5013,  stadium_lon=-88.0622,  is_dome=False, turf_type="grass"),
    dict(abbreviation="MIN", name="Vikings",   city="Minnesota",     stadium_name="U.S. Bank Stadium",         stadium_lat=44.9737,  stadium_lon=-93.2571,  is_dome=True,  turf_type="turf"),
    # NFC South
    dict(abbreviation="ATL", name="Falcons",   city="Atlanta",       stadium_name="Mercedes-Benz Stadium",     stadium_lat=33.7553,  stadium_lon=-84.4006,  is_dome=True,  turf_type="turf"),
    dict(abbreviation="CAR", name="Panthers",  city="Carolina",      stadium_name="Bank of America Stadium",   stadium_lat=35.2258,  stadium_lon=-80.8528,  is_dome=False, turf_type="grass"),
    dict(abbreviation="NO",  name="Saints",    city="New Orleans",   stadium_name="Caesars Superdome",         stadium_lat=29.9511,  stadium_lon=-90.0812,  is_dome=True,  turf_type="turf"),
    dict(abbreviation="TB",  name="Buccaneers",city="Tampa Bay",     stadium_name="Raymond James Stadium",     stadium_lat=27.9759,  stadium_lon=-82.5033,  is_dome=False, turf_type="grass"),
    # NFC West
    dict(abbreviation="ARI", name="Cardinals", city="Arizona",       stadium_name="State Farm Stadium",        stadium_lat=33.5276,  stadium_lon=-112.2626, is_dome=True,  turf_type="grass"),
    dict(abbreviation="LAR", name="Rams",      city="Los Angeles",   stadium_name="SoFi Stadium",              stadium_lat=33.9534,  stadium_lon=-118.3391, is_dome=False, turf_type="turf"),
    dict(abbreviation="SEA", name="Seahawks",  city="Seattle",       stadium_name="Lumen Field",               stadium_lat=47.5952,  stadium_lon=-122.3316, is_dome=False, turf_type="turf"),
    dict(abbreviation="SF",  name="49ers",     city="San Francisco", stadium_name="Levi's Stadium",            stadium_lat=37.4032,  stadium_lon=-121.9697, is_dome=False, turf_type="grass"),
]


async def seed():
    async with AsyncSessionLocal() as db:
        inserted = 0
        skipped = 0
        for team_data in TEAMS:
            existing = await db.execute(
                select(NFLTeam).where(NFLTeam.abbreviation == team_data["abbreviation"])
            )
            if existing.scalar_one_or_none():
                skipped += 1
                continue
            db.add(NFLTeam(**team_data))
            inserted += 1
        await db.commit()
        print(f"✅ Teams seeded — inserted: {inserted}, skipped (already exist): {skipped}")


if __name__ == "__main__":
    asyncio.run(seed())
