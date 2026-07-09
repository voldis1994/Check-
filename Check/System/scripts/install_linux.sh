#!/usr/bin/env bash
# Lejupielādē un uzstāda SYSTEM projektu (Linux/macOS izstrādei).
#
# Lietošana:
#   bash install_linux.sh
#   bash install_linux.sh --install-path "$HOME/SYSTEM"
#   bash install_linux.sh --skip-tests
#
set -euo pipefail

INSTALL_PATH="${HOME}/SYSTEM"
REPO_URL="https://github.com/voldis1994/Check-.git"
BRANCH="main"
SKIP_TESTS=0

usage() {
    cat <<'EOF'
SYSTEM instalators (Linux/macOS)

Opcijas:
  --install-path PATH   Mērķa mape (noklusējums: ~/SYSTEM)
  --branch NAME         Git zars (noklusējums: main)
  --skip-tests          Neizpildīt pytest
  -h, --help            Palīdzība
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --install-path)
            INSTALL_PATH="$2"
            shift 2
            ;;
        --branch)
            BRANCH="$2"
            shift 2
            ;;
        --skip-tests)
            SKIP_TESTS=1
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Nezināma opcija: $1" >&2
            usage
            exit 1
            ;;
    esac
done

step() {
    echo ""
    echo "==> $1"
}

require_python() {
    if ! command -v python3 >/dev/null 2>&1; then
        echo "Kluda: python3 nav atrasts. Instalējiet Python 3.11+." >&2
        exit 1
    fi
    python3 - <<'PY'
import sys
if sys.version_info < (3, 11):
    raise SystemExit(f"Python 3.11+ nepieciešams, atrasts {sys.version}")
print(f"Python {sys.version_info.major}.{sys.version_info.minor}")
PY
}

REPO_SYSTEM_PATH=""
REPO_TEMP_DIR=""

download_repo() {
    local temp_dir repo_system
    temp_dir="$(mktemp -d)"

    if command -v git >/dev/null 2>&1; then
        step "Lejupielādē ar git clone (zars: $BRANCH)"
        git clone --branch "$BRANCH" --single-branch --depth 1 "$REPO_URL" "$temp_dir/repo"
        repo_system="$temp_dir/repo/SYSTEM"
    else
        step "git nav atrasts — lejupielādē ZIP"
        local zip_url encoded_branch extracted_root
        encoded_branch="$(python3 -c "import urllib.parse; print(urllib.parse.quote('''$BRANCH''', safe=''))")"
        zip_url="https://github.com/voldis1994/Check-/archive/refs/heads/${encoded_branch}.zip"
        curl -fsSL "$zip_url" -o "$temp_dir/repo.zip"
        unzip -q "$temp_dir/repo.zip" -d "$temp_dir"
        extracted_root="$(find "$temp_dir" -mindepth 1 -maxdepth 1 -type d ! -name '__MACOSX' | head -n 1)"
        repo_system="$extracted_root/SYSTEM"
    fi

    if [[ ! -d "$repo_system" ]]; then
        rm -rf "$temp_dir"
        echo "Kluda: repozitorijā nav SYSTEM/ mapes" >&2
        exit 1
    fi

    REPO_SYSTEM_PATH="$repo_system"
    REPO_TEMP_DIR="$temp_dir"
}

update_root_path() {
    local config_file="$1"
    local root_path="$2"
    python3 - "$config_file" "$root_path" <<'PY'
import json
import sys

config_file, root_path = sys.argv[1], sys.argv[2]
with open(config_file, encoding="utf-8") as handle:
    payload = json.load(handle)
payload["system"]["root_path"] = root_path.replace("\\", "\\\\")
with open(config_file, "w", encoding="utf-8") as handle:
    json.dump(payload, handle, indent=2)
    handle.write("\n")
PY
}

echo "========================================"
echo " SYSTEM — automātiskā uzstādīšana"
echo "========================================"
echo "Mērķa mape: $INSTALL_PATH"
echo "Zars:       $BRANCH"

step "Pārbauda Python"
require_python

download_repo
if [[ ! -d "$REPO_SYSTEM_PATH" ]]; then
    echo "Kluda: SOURCE mapē nav SYSTEM/" >&2
    exit 1
fi

step "Kopē failus uz $INSTALL_PATH"
rm -rf "$INSTALL_PATH"
mkdir -p "$INSTALL_PATH"
cp -a "$REPO_SYSTEM_PATH/." "$INSTALL_PATH/"
rm -rf "$REPO_TEMP_DIR"

step "Izveido datu mapes un atjaunina config"
mkdir -p "$INSTALL_PATH/data"/{clients,logs,cache,history,universe}
mkdir -p "$INSTALL_PATH/config"
update_root_path "$INSTALL_PATH/config/system.json" "$INSTALL_PATH"

step "Izveido venv un instalē atkarības"
python3 -m venv "$INSTALL_PATH/.venv"
"$INSTALL_PATH/.venv/bin/python" -m pip install --upgrade pip
"$INSTALL_PATH/.venv/bin/python" -m pip install -r "$INSTALL_PATH/requirements.txt"

if [[ "$SKIP_TESTS" -eq 0 ]]; then
    step "Palaid testus"
    (cd "$INSTALL_PATH" && "$INSTALL_PATH/.venv/bin/python" -m pytest -q)
fi

echo ""
echo "========================================"
echo " UZSTĀDĪŠANA PABEIGTA"
echo "========================================"
echo "Projekta mape: $INSTALL_PATH"
echo "Aktivizēt vidi: source $INSTALL_PATH/.venv/bin/activate"
echo "Tests:          cd $INSTALL_PATH && pytest"
echo ""
echo "Piezīme: MT4 darbojas tikai Windows. Linux versija ir izstrādei/testiem."
