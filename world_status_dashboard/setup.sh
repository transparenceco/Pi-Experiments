#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${ROOT_DIR}/venv"
REQ_FILE="${ROOT_DIR}/requirements.txt"
CONFIG_FILE="${ROOT_DIR}/config.json"

mkdir -p "${ROOT_DIR}/.cache"

if [[ ! -d "${VENV_DIR}" ]]; then
  python3 -m venv "${VENV_DIR}"
fi

source "${VENV_DIR}/bin/activate"
pip install -r "${REQ_FILE}" >/dev/null

read -r -p "Enter XAI API key (leave blank to skip): " XAI_KEY
CONFIG_FILE="${CONFIG_FILE}" XAI_KEY="${XAI_KEY}" python3 - <<'PY'
import json, os
path = os.environ["CONFIG_FILE"]
key = os.environ.get("XAI_KEY", "").strip()
config = {}
if os.path.exists(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            config = json.load(f)
    except Exception:
        config = {}
if key and not config.get("xai_api_key"):
    config["xai_api_key"] = key
with open(path, "w", encoding="utf-8") as f:
    json.dump(config, f)
PY

mkdir -p "${HOME}/bin"
cat <<'SH' > "${HOME}/bin/worldstatus"
#!/usr/bin/env bash
set -euo pipefail
exec ~/Documents/Pi-Experiments/world_status_dashboard/run.sh
SH
chmod +x "${HOME}/bin/worldstatus"

if ! echo "${PATH}" | grep -q "${HOME}/bin"; then
  if ! grep -q 'export PATH="$HOME/bin:$PATH"' "${HOME}/.bashrc" 2>/dev/null; then
    echo 'export PATH="$HOME/bin:$PATH"' >> "${HOME}/.bashrc"
  fi
  if ! grep -q 'export PATH="$HOME/bin:$PATH"' "${HOME}/.profile" 2>/dev/null; then
    echo 'export PATH="$HOME/bin:$PATH"' >> "${HOME}/.profile"
  fi
fi

echo "Setup complete. Restart your terminal or run: source ~/.bashrc"
