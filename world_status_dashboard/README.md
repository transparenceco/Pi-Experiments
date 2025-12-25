# World Status Dashboard

At-a-glance terminal dashboard with date/time, Toronto weather, and a news summary from X search.

## Requirements

- Python 3.9+ (for `zoneinfo`)
- Network access
- `xai-sdk==1.3.1`

## Run

```bash
pip install -r requirements.txt
python3 dashboard.py
```

On first launch you will be prompted for your xAI API key, which is saved to `config.json`.
You can also provide it via `XAI_API_KEY` to skip onboarding.

Optional overrides:

```bash
export XAI_API_KEY="your_xai_api_key"
export XAI_MODEL="grok-4-1-fast"
export X_SEARCH_QUERY="Toronto news OR Canada news"
export X_MAX_RESULTS=6
```

Press `q` to quit.

## Notes

- Weather is fetched from Open-Meteo (no API key required).
- News uses xAI agentic X search tools and caches results for 30 minutes in `.cache/`.
- Location is set to Toronto (lat/lon) and timezone `America/Toronto`.
