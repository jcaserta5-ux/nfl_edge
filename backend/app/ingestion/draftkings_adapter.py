"""
DEPRECATED — replaced by espn_adapter.py
=========================================
DraftKings lines are now fetched via ESPN's undocumented public scoreboard
API (provider ID 1002), which requires no API key and returns the same
DraftKings spread / moneyline / total data.

See: backend/app/ingestion/espn_adapter.py

This file is kept for reference only and is no longer imported by any
Celery task or API route. It will be removed in a future cleanup.
"""
raise ImportError(
    "draftkings_adapter is deprecated. Use espn_adapter.fetch_espn_scoreboard_odds() instead."
)
