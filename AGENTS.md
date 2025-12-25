# Repository Guidelines

## Project Structure & Module Organization
- `README.md` provides the list of experiments and entry points.
- `system_monitor_dashboard/` contains the terminal system monitor (`monitor.py`) and its README.
- `world_status_dashboard/` contains the world status app (`dashboard.py`), setup helpers (`run.sh`, `setup.sh`), and docs.
- Per-project caches live under `.cache/` inside each experiment and are git-ignored.

## Build, Test, and Development Commands
- `python3 system_monitor_dashboard/monitor.py` runs the local system monitor.
- `python3 world_status_dashboard/dashboard.py` runs the world status dashboard directly.
- `./world_status_dashboard/run.sh` creates/uses a venv, installs deps, and runs the dashboard.
- `./world_status_dashboard/setup.sh` bootstraps a fresh Pi (venv, deps, launcher).

There is no unified build system; each experiment is standalone.

## Coding Style & Naming Conventions
- Language: Python 3.9+ with standard library first.
- Indentation: 4 spaces, no tabs.
- Files and functions use snake_case; constants use UPPER_SNAKE_CASE.
- Prefer ASCII-only text and concise inline comments only when logic is non-obvious.

## Testing Guidelines
- No automated test suite is defined yet.
- If you add tests, keep them per-experiment (e.g., `world_status_dashboard/tests/`) and document how to run them in that folder’s README.

## Commit & Pull Request Guidelines
- Commit messages are short, imperative, and scoped (e.g., `Add setup script for new Pi installs`).
- Keep commits focused to a single experiment or feature.
- PRs should include a brief summary, steps to run, and screenshots for UI changes (terminal screenshots are fine).

## Security & Configuration
- Do not commit secrets. `world_status_dashboard/config.json` is git-ignored.
- Prefer env vars for keys when possible (e.g., `XAI_API_KEY`).
