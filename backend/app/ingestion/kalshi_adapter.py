"""
Kalshi ingestion adapter — DEFERRED
=====================================
Kalshi integration is currently on hold. This module is not imported
by any active Celery task. It will be wired in when Kalshi integration
is re-enabled.

Original plan: fetch NFL prediction market contracts (winner / spread / total)
from the Kalshi v2 REST API (https://trading-api.kalshi.com/trade-api/v2)
and compare implied win probabilities against ESPN spread-implied probabilities
to generate a Kalshi divergence edge signal.

When you're ready to re-enable Kalshi:
  1. Restore the implementation from git history (or re-generate).
  2. Add KALSHI_API_KEY to .env.
  3. Uncomment the "ingest-kalshi-every-5min" entry in celery_app.py.
  4. Re-enable the KalshiContract model and kalshi_divergence_score
     component in the edge engine.
"""
