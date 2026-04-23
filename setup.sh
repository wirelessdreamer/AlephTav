#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_DIR="${ROOT_DIR}/.run"
VENV_DIR="${ROOT_DIR}/.venv"
LOG_PREFIX="setup"
REBUILD_STATE_SCRIPT="${ROOT_DIR}/scripts/setup_rebuild_state.py"
MANAGED_SERVICES_FILE="${RUN_DIR}/managed-services.json"

DATA_MODE="full"
SKIP_INSTALL=0
SKIP_REBUILD=0
SKIP_START=0
NONINTERACTIVE=0
API_PORT=8765
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
  --api-port PORT    Override the API port (default: 8765)
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

clear_managed_services_state() {
  rm -f "${MANAGED_SERVICES_FILE}"
}

write_managed_services_state() {
  cat >"${MANAGED_SERVICES_FILE}" <<EOF
{
  "api": {"pid": ${API_PID:-null}, "port": ${API_PORT}},
  "ui": {"pid": ${UI_PID:-null}, "port": ${UI_PORT}}
}
EOF
}

stop_pid_if_running() {
  local pid="$1"
  local label="$2"
  local signal="${3:-TERM}"

  [[ -n "${pid}" ]] || return 0
  if ! kill -0 "${pid}" 2>/dev/null; then
    return 0
  fi

  kill "-${signal}" "${pid}" 2>/dev/null || kill "${pid}" 2>/dev/null || true
  for _ in 1 2 3 4 5; do
    if ! kill -0 "${pid}" 2>/dev/null; then
      return 0
    fi
    sleep 1
  done

  if [[ "${signal}" != "KILL" ]]; then
    warn "${label} process ${pid} did not exit after SIG${signal}; forcing shutdown."
    stop_pid_if_running "${pid}" "${label}" KILL
  fi
}

get_listener_pid() {
  local port="$1"
  if have_cmd lsof; then
    lsof -nP -iTCP:"${port}" -sTCP:LISTEN -t 2>/dev/null | head -n 1
    return 0
  fi
  if have_cmd ss; then
    ss -lptn "sport = :${port}" 2>/dev/null | sed -n 's/.*pid=\([0-9][0-9]*\).*/\1/p' | head -n 1
    return 0
  fi
  return 0
}

get_process_cmdline() {
  local pid="$1"
  if [[ -r "/proc/${pid}/cmdline" ]]; then
    tr '\0' ' ' <"/proc/${pid}/cmdline" | sed 's/[[:space:]]\+$//'
    return 0
  fi
  ps -o command= -p "${pid}" 2>/dev/null || true
}

get_process_cwd() {
  local pid="$1"
  if [[ -L "/proc/${pid}/cwd" ]]; then
    readlink -f "/proc/${pid}/cwd" 2>/dev/null || true
    return 0
  fi
  if have_cmd lsof; then
    lsof -a -p "${pid}" -d cwd -Fn 2>/dev/null | sed -n 's/^n//p' | head -n 1
  fi
}

is_repo_owned_listener() {
  local pid="$1"
  local kind="$2"
  local cmdline cwd

  cmdline="$(get_process_cmdline "${pid}")"
  cwd="$(get_process_cwd "${pid}")"

  case "${kind}" in
    api)
      [[ "${cmdline}" == *"app.api.main:app"* ]] || return 1
      [[ "${cmdline}" == *"uvicorn"* ]] || return 1
      ;;
    ui)
      [[ "${cmdline}" == *"vite"* ]] || return 1
      [[ "${cmdline}" == *"app/ui/vite.config.ts"* ]] || return 1
      ;;
    *)
      return 1
      ;;
  esac

  [[ -n "${cwd}" && "${cwd}" == "${ROOT_DIR}" ]] || return 1
  return 0
}

reclaim_repo_owned_port() {
  local port="$1"
  local kind="$2"
  local pid

  pid="$(get_listener_pid "${port}")"
  [[ -n "${pid}" ]] || return 0
  if ! kill -0 "${pid}" 2>/dev/null; then
    return 0
  fi
  if is_repo_owned_listener "${pid}" "${kind}"; then
    log "Stopping existing repo-owned ${kind^^} process ${pid} on port ${port}."
    stop_pid_if_running "${pid}" "${kind^^}"
  fi
}

cleanup_stale_managed_services() {
  [[ -f "${MANAGED_SERVICES_FILE}" ]] || return 0

  local stale_entries
  stale_entries="$(python3 - "${MANAGED_SERVICES_FILE}" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
try:
    payload = json.loads(path.read_text(encoding="utf-8"))
except Exception:
    raise SystemExit(1)

for label in ("api", "ui"):
    item = payload.get(label) or {}
    pid = item.get("pid")
    port = item.get("port")
    if pid:
        print(f"{label}:{pid}:{port}")
PY
)" || {
    warn "Unable to parse ${MANAGED_SERVICES_FILE}; clearing stale setup state."
    clear_managed_services_state
    return 0
  }

  local entry label pid port
  while IFS= read -r entry; do
    [[ -n "${entry}" ]] || continue
    IFS=':' read -r label pid port <<<"${entry}"
    if kill -0 "${pid}" 2>/dev/null; then
      log "Stopping stale setup-managed ${label^^} process ${pid} on port ${port}."
      stop_pid_if_running "${pid}" "${label^^}"
    fi
  done <<<"${stale_entries}"

  clear_managed_services_state
}

cleanup() {
  local exit_code=$?
  stop_pid_if_running "${UI_PID}" "UI"
  stop_pid_if_running "${API_PID}" "API"
  clear_managed_services_state
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
cleanup_stale_managed_services

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

is_port_free() {
  local python_bin="$1"
  local port="$2"
  "${python_bin}" - "$port" <<'PY'
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

resolve_port_conflict() {
  local python_bin="$1"
  local requested_port="$2"
  local label="$3"
  local candidate

  if is_port_free "${python_bin}" "${requested_port}"; then
    printf '%s\n' "${requested_port}"
    return 0
  fi

  for ((candidate=requested_port + 1; candidate<=requested_port + 25; candidate++)); do
    if is_port_free "${python_bin}" "${candidate}"; then
      warn "${label} port ${requested_port} is already in use by another process. Falling back to ${candidate}."
      printf '%s\n' "${candidate}"
      return 0
    fi
  done

  die "${label} port ${requested_port} is already in use and no fallback port was available in the next 25 ports. Pass an override flag."
}

require_free_port() {
  local python_bin="$1"
  local port="$2"
  local label="$3"
  is_port_free "${python_bin}" "${port}" || die "${label} port ${port} is already in use. Stop the conflicting process or pass an override flag."
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

sync_rebuild_state() {
  local action="$1"
  local output
  if ! output="$("${VENV_PYTHON}" "${REBUILD_STATE_SCRIPT}" "${action}" --mode "${DATA_MODE}" 2>&1)"; then
    printf '%s\n' "${output}" >&2
    return 1
  fi
  [[ -n "${output}" ]] && log "${output}"
}

maybe_run_data_pipeline() {
  local output
  if output="$("${VENV_PYTHON}" "${REBUILD_STATE_SCRIPT}" check --mode "${DATA_MODE}" 2>&1)"; then
    [[ -n "${output}" ]] && log "${output}"
    sync_rebuild_state mark
    log "Skipping data bootstrap/rebuild because tracked outputs are current."
    return 0
  fi

  [[ -n "${output}" ]] && log "${output}"
  run_data_pipeline
  sync_rebuild_state mark
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
  local requested_api_port="${API_PORT}"
  local requested_ui_port="${UI_PORT}"
  timestamp="$(date +%Y%m%d-%H%M%S)"
  API_LOG="${RUN_DIR}/${LOG_PREFIX}-api-${timestamp}.log"
  UI_LOG="${RUN_DIR}/${LOG_PREFIX}-ui-${timestamp}.log"

  reclaim_repo_owned_port "${API_PORT}" api
  reclaim_repo_owned_port "${UI_PORT}" ui

  API_PORT="$(resolve_port_conflict "${VENV_PYTHON}" "${requested_api_port}" "API")"
  UI_PORT="$(resolve_port_conflict "${VENV_PYTHON}" "${requested_ui_port}" "UI")"

  require_free_port "${VENV_PYTHON}" "${API_PORT}" "API"
  require_free_port "${VENV_PYTHON}" "${UI_PORT}" "UI"

  log "Starting API on http://127.0.0.1:${API_PORT}"
  "${VENV_PYTHON}" -m uvicorn app.api.main:app --host 127.0.0.1 --port "${API_PORT}" >"${API_LOG}" 2>&1 &
  API_PID=$!
  write_managed_services_state

  if ! wait_for_url "${VENV_PYTHON}" "http://127.0.0.1:${API_PORT}/health" "API" 60; then
    warn "API failed to report healthy startup. See ${API_LOG}"
    return 1
  fi

  log "Starting UI on http://127.0.0.1:${UI_PORT}"
  npm run dev -- --host 127.0.0.1 --port "${UI_PORT}" >"${UI_LOG}" 2>&1 &
  UI_PID=$!
  write_managed_services_state

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
  maybe_run_data_pipeline
else
  log "Skipping data bootstrap/rebuild."
fi

if [[ "${SKIP_START}" -eq 0 ]]; then
  start_services
else
  log "Verification and setup complete. Startup was skipped."
fi
