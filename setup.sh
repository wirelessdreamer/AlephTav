#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_DIR="${ROOT_DIR}/.run"
VENV_DIR="${ROOT_DIR}/.venv"
LOG_PREFIX="setup"

DATA_MODE="full"
SKIP_INSTALL=0
SKIP_REBUILD=0
SKIP_START=0
NONINTERACTIVE=0
API_PORT=8000
UI_PORT=5173

API_PID=""
UI_PID=""
API_LOG=""
UI_LOG=""

usage() {
  cat <<'EOF'
Usage: ./setup.sh [options]

Options:
  --full             Run the full rebuild pipeline (default)
  --fixture          Bootstrap fixture data instead of the full rebuild pipeline
  --skip-install     Skip Python and Node dependency installation
  --skip-rebuild     Skip data bootstrap/rebuild
  --skip-start       Verify and install only; do not start the app
  --api-port PORT    Override the API port (default: 8000)
  --ui-port PORT     Override the UI port (default: 5173)
  --yes              Non-interactive mode; auto-approve derived system package manager commands
  --help             Show this help message
EOF
}

log() {
  printf '[setup] %s\n' "$*"
}

warn() {
  printf '[setup] WARNING: %s\n' "$*" >&2
}

die() {
  printf '[setup] ERROR: %s\n' "$*" >&2
  exit 1
}

cleanup() {
  local exit_code=$?
  if [[ -n "${UI_PID}" ]] && kill -0 "${UI_PID}" 2>/dev/null; then
    kill "${UI_PID}" 2>/dev/null || true
    wait "${UI_PID}" 2>/dev/null || true
  fi
  if [[ -n "${API_PID}" ]] && kill -0 "${API_PID}" 2>/dev/null; then
    kill "${API_PID}" 2>/dev/null || true
    wait "${API_PID}" 2>/dev/null || true
  fi
  exit "${exit_code}"
}

trap cleanup EXIT INT TERM

while [[ $# -gt 0 ]]; do
  case "$1" in
    --full)
      DATA_MODE="full"
      shift
      ;;
    --fixture)
      DATA_MODE="fixture"
      shift
      ;;
    --skip-install)
      SKIP_INSTALL=1
      shift
      ;;
    --skip-rebuild)
      SKIP_REBUILD=1
      shift
      ;;
    --skip-start)
      SKIP_START=1
      shift
      ;;
    --api-port)
      [[ $# -ge 2 ]] || die "--api-port requires a value"
      API_PORT="$2"
      shift 2
      ;;
    --ui-port)
      [[ $# -ge 2 ]] || die "--ui-port requires a value"
      UI_PORT="$2"
      shift 2
      ;;
    --yes)
      NONINTERACTIVE=1
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      die "Unknown option: $1"
      ;;
  esac
done

cd "${ROOT_DIR}"
mkdir -p "${RUN_DIR}"

have_cmd() {
  command -v "$1" >/dev/null 2>&1
}

python_meets_requirement() {
  local candidate="$1"
  "${candidate}" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' >/dev/null 2>&1
}

discover_python() {
  local candidate
  for candidate in python3 python; do
    if have_cmd "${candidate}" && python_meets_requirement "${candidate}"; then
      printf '%s\n' "${candidate}"
      return 0
    fi
  done
  return 1
}

detect_platform() {
  if [[ "$(uname -s)" == "Darwin" ]]; then
    printf 'macos\n'
  else
    printf 'linux\n'
  fi
}

detect_package_manager() {
  local manager
  for manager in brew apt-get dnf yum pacman zypper; do
    if have_cmd "${manager}"; then
      printf '%s\n' "${manager}"
      return 0
    fi
  done
  return 1
}

append_command() {
  local line="$1"
  if [[ -z "${INSTALL_COMMANDS}" ]]; then
    INSTALL_COMMANDS="${line}"
  else
    INSTALL_COMMANDS="${INSTALL_COMMANDS}"$'\n'"${line}"
  fi
}

build_install_commands() {
  local manager="$1"
  local need_python="$2"
  local need_node="$3"
  INSTALL_COMMANDS=""
  case "${manager}" in
    brew)
      [[ "${need_python}" == "1" ]] && append_command "brew install python@3.11"
      [[ "${need_node}" == "1" ]] && append_command "brew install node"
      ;;
    apt-get)
      append_command "sudo apt-get update"
      if [[ "${need_python}" == "1" ]]; then
        append_command "sudo apt-get install -y python3.11 python3.11-venv"
      fi
      [[ "${need_node}" == "1" ]] && append_command "sudo apt-get install -y nodejs npm"
      ;;
    dnf)
      [[ "${need_python}" == "1" ]] && append_command "sudo dnf install -y python3.11"
      [[ "${need_node}" == "1" ]] && append_command "sudo dnf install -y nodejs npm"
      ;;
    yum)
      [[ "${need_python}" == "1" ]] && append_command "sudo yum install -y python3.11"
      [[ "${need_node}" == "1" ]] && append_command "sudo yum install -y nodejs npm"
      ;;
    pacman)
      [[ "${need_python}" == "1" ]] && append_command "sudo pacman -Sy --noconfirm python"
      [[ "${need_node}" == "1" ]] && append_command "sudo pacman -Sy --noconfirm nodejs npm"
      ;;
    zypper)
      [[ "${need_python}" == "1" ]] && append_command "sudo zypper install -y python311"
      [[ "${need_node}" == "1" ]] && append_command "sudo zypper install -y nodejs20 npm20"
      ;;
  esac
}

run_install_commands() {
  local commands="$1"
  local line
  while IFS= read -r line; do
    [[ -n "${line}" ]] || continue
    log "Running: ${line}"
    bash -lc "${line}"
  done <<< "${commands}"
}

ensure_system_runtimes() {
  local need_python=0
  local need_node=0
  local python_cmd=""
  local manager=""
  local platform

  platform="$(detect_platform)"

  if python_cmd="$(discover_python)"; then
    log "Using Python runtime: ${python_cmd}"
  else
    need_python=1
    warn "Python 3.11+ was not found."
  fi

  if have_cmd node && have_cmd npm; then
    log "Using Node runtime: $(node --version) / npm $(npm --version)"
  else
    need_node=1
    warn "Node.js and npm were not found."
  fi

  if [[ "${need_python}" -eq 0 && "${need_node}" -eq 0 ]]; then
    PYTHON_CMD="${python_cmd}"
    return 0
  fi

  if manager="$(detect_package_manager)"; then
    build_install_commands "${manager}" "${need_python}" "${need_node}"
    cat <<EOF
[setup] Missing required system runtimes on ${platform}.
[setup] Suggested install commands for ${manager}:
${INSTALL_COMMANDS}
EOF
    if [[ "${NONINTERACTIVE}" -eq 1 ]]; then
      log "Auto-approving derived install commands because --yes was supplied."
      run_install_commands "${INSTALL_COMMANDS}"
    else
      printf '[setup] Run these commands now? [y/N]: '
      read -r reply
      if [[ "${reply}" =~ ^[Yy]$ ]]; then
        run_install_commands "${INSTALL_COMMANDS}"
      else
        die "Install the missing system runtimes, then re-run ./setup.sh."
      fi
    fi
  else
    cat <<EOF
[setup] Missing required system runtimes on ${platform}.
[setup] No supported package manager was detected.
[setup] Install Python 3.11+ and Node.js/npm manually, then re-run ./setup.sh.
EOF
    exit 1
  fi

  PYTHON_CMD="$(discover_python)" || die "Python 3.11+ is still unavailable after the attempted installation."
  have_cmd node || die "Node.js is still unavailable after the attempted installation."
  have_cmd npm || die "npm is still unavailable after the attempted installation."
}

run_python_http_probe() {
  local python_bin="$1"
  local url="$2"
  "${python_bin}" - "$url" <<'PY'
import sys
import urllib.request

url = sys.argv[1]
try:
    with urllib.request.urlopen(url, timeout=2) as response:
        raise SystemExit(0 if response.status < 500 else 1)
except Exception:
    raise SystemExit(1)
PY
}

require_free_port() {
  local python_bin="$1"
  local port="$2"
  local label="$3"
  "${python_bin}" - "$port" <<'PY' || die "${label} port ${port} is already in use. Stop the conflicting process or pass an override flag."
import socket
import sys

port = int(sys.argv[1])
sock = socket.socket()
try:
    sock.bind(("127.0.0.1", port))
except OSError:
    raise SystemExit(1)
finally:
    sock.close()
PY
}

run_step() {
  local description="$1"
  shift
  log "${description}"
  "$@" || die "${description} failed."
}

ensure_venv() {
  if [[ ! -e "${VENV_DIR}" ]]; then
    run_step "Creating virtual environment" "${PYTHON_CMD}" -m venv "${VENV_DIR}"
  else
    log "Using existing virtual environment at ${VENV_DIR}"
  fi
  VENV_PYTHON="${VENV_DIR}/bin/python"
  [[ -x "${VENV_PYTHON}" ]] || die "Expected virtual environment interpreter at ${VENV_PYTHON}"
}

install_project_deps() {
  run_step "Upgrading pip" "${VENV_PYTHON}" -m pip install --upgrade pip
  run_step "Installing Python dependencies" "${VENV_PYTHON}" -m pip install -e '.[dev]'
  run_step "Installing Node dependencies" npm install
}

run_data_pipeline() {
  if [[ "${DATA_MODE}" == "fixture" ]]; then
    run_step "Bootstrapping fixture data" "${VENV_PYTHON}" scripts/bootstrap_fixture_repo.py
    return
  fi
  run_step "Seeding project metadata" "${VENV_PYTHON}" scripts/seed_project.py
  run_step "Importing Psalms data" "${VENV_PYTHON}" scripts/import_psalms.py
  run_step "Building indexes" "${VENV_PYTHON}" scripts/build_indexes.py
  run_step "Validating content" "${VENV_PYTHON}" scripts/validate_content.py
}

wait_for_url() {
  local python_bin="$1"
  local url="$2"
  local label="$3"
  local timeout="$4"
  local elapsed=0
  while (( elapsed < timeout )); do
    if run_python_http_probe "${python_bin}" "${url}"; then
      log "${label} is ready at ${url}"
      return 0
    fi
    sleep 1
    elapsed=$((elapsed + 1))
  done
  return 1
}

start_services() {
  local timestamp
  timestamp="$(date +%Y%m%d-%H%M%S)"
  API_LOG="${RUN_DIR}/${LOG_PREFIX}-api-${timestamp}.log"
  UI_LOG="${RUN_DIR}/${LOG_PREFIX}-ui-${timestamp}.log"

  require_free_port "${VENV_PYTHON}" "${API_PORT}" "API"
  require_free_port "${VENV_PYTHON}" "${UI_PORT}" "UI"

  log "Starting API on http://127.0.0.1:${API_PORT}"
  "${VENV_PYTHON}" -m uvicorn app.api.main:app --host 127.0.0.1 --port "${API_PORT}" >"${API_LOG}" 2>&1 &
  API_PID=$!

  if ! wait_for_url "${VENV_PYTHON}" "http://127.0.0.1:${API_PORT}/health" "API" 60; then
    warn "API failed to report healthy startup. See ${API_LOG}"
    return 1
  fi

  log "Starting UI on http://127.0.0.1:${UI_PORT}"
  npm run dev -- --host 127.0.0.1 --port "${UI_PORT}" >"${UI_LOG}" 2>&1 &
  UI_PID=$!

  if ! wait_for_url "${VENV_PYTHON}" "http://127.0.0.1:${UI_PORT}" "UI" 60; then
    warn "UI failed to report ready startup. See ${UI_LOG}"
    return 1
  fi

  cat <<EOF

[setup] Setup complete.
[setup] API: http://127.0.0.1:${API_PORT}
[setup] UI:  http://127.0.0.1:${UI_PORT}
[setup] Logs:
[setup]   API: ${API_LOG}
[setup]   UI:  ${UI_LOG}
[setup] Press Ctrl+C to stop both services.
EOF

  while true; do
    if ! kill -0 "${API_PID}" 2>/dev/null; then
      die "API exited unexpectedly. See ${API_LOG}"
    fi
    if ! kill -0 "${UI_PID}" 2>/dev/null; then
      die "UI exited unexpectedly. See ${UI_LOG}"
    fi
    sleep 1
  done
}

PYTHON_CMD=""
VENV_PYTHON=""

ensure_system_runtimes
ensure_venv

if [[ "${SKIP_INSTALL}" -eq 0 ]]; then
  install_project_deps
else
  log "Skipping dependency installation."
fi

if [[ "${SKIP_REBUILD}" -eq 0 ]]; then
  run_data_pipeline
else
  log "Skipping data bootstrap/rebuild."
fi

if [[ "${SKIP_START}" -eq 0 ]]; then
  start_services
else
  log "Verification and setup complete. Startup was skipped."
fi
