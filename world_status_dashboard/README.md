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

Or run the launcher (creates/uses a venv and installs deps):

```bash
./run.sh
```

## One-Command Setup (New Pi)

After cloning this repo on another Pi:

```bash
cd ~/Documents/Pi-Experiments/world_status_dashboard
./setup.sh
```

This creates the venv, installs dependencies, prompts for your xAI API key, and creates a `worldstatus` launcher in `~/bin`.

## Launcher Command

You can create a global launcher so you can run `worldstatus` from anywhere:

```bash
mkdir -p ~/bin
cat <<'SH' > ~/bin/worldstatus
#!/usr/bin/env bash
set -euo pipefail
exec ~/Documents/Pi-Experiments/world_status_dashboard/run.sh
SH
chmod +x ~/bin/worldstatus
```

If `worldstatus` is not found on the Pi’s local terminal, add `~/bin` to PATH:

```bash
echo 'export PATH="$HOME/bin:$PATH"' >> ~/.bashrc
echo 'export PATH="$HOME/bin:$PATH"' >> ~/.profile
source ~/.bashrc
hash -r
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

Press `q` to quit. Press `s` for settings, `r` to refresh news.

## Notes

- Weather is fetched from Open-Meteo (no API key required).
- News uses xAI agentic X search tools and caches results in `.cache/`.
- Location is set to Toronto (lat/lon) and timezone `America/Toronto`.
- Settings lets you toggle whether in-post links are shown.
- Stocks are fetched from Stooq (free, no key) using symbols like `TSLA.US`.
- Settings includes max results and the summary prompt for news.
- Settings includes filters: allowed/excluded handles, include/exclude keywords, and lookback hours.
- Allowed handles supports presets: `world`, `mexico`, `canada`, `toronto`, or `all`.
- Settings includes “Allowed handle limit” (max 10) for X search tool constraints.

## Feed Structure

Each post is rendered in this order:

1. Post content (wrapped to terminal width)
2. Poster handle + time
3. Optional URL line(s) (if enabled)
4. Blank line between posts

## X Search Query Flow

News fetch uses xAI agentic tool calling:

1. Build a prompt that asks the model to search X for `X_SEARCH_QUERY`.
2. The model uses `x_search` tool server-side.
3. The model returns a JSON array with `text`, `author_handle`, `created_at`, `url`.
4. Results are cached to `.cache/news.json` with `fetched_at` for schedule checks.

## Quick Wins / Optimizations

- Add `allowed_x_handles` filter to focus on trusted local sources.
- Add date range filters (e.g., last 24h) for fresher results.
- Add per-topic query presets (Toronto, Canada, Tech) via settings.
- Post-process results: de-duplicate similar headlines and remove spammy posts.
- Add relevance boosting by requiring keywords (e.g., "Toronto" AND "weather").
- Add change/% change for stocks and basic price alerts.
