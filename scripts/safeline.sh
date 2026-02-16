#!/usr/bin/env bash
# SafeLine WAF automation for Linux + WSL2.
# Default behavior is NON-INTERACTIVE and DESTRUCTIVE for the "up/reset" flow.
set -euo pipefail

SAFELINE_ROOT="/data/safeline"
DEFAULT_COMPOSE_PATH="$SAFELINE_ROOT/compose.yaml"
INSTALL_URL="https://waf.chaitin.com/release/latest/setup.sh"
ORIGINAL_ARGS=("$@")


log() {
  printf '[safeline] %s\n' "$*"
}


warn() {
  printf '[safeline][warn] %s\n' "$*" >&2
}


die() {
  printf '[safeline][error] %s\n' "$*" >&2
  exit 1
}


usage() {
  cat <<'USAGE_EOF'
Usage:
  bash scripts/safeline.sh <command> [options]

Commands:
  up                Full reset + install-or-repair + start + health check
  reset             Alias for "up"
  down              Stop SafeLine services and remove running safeline containers
  status            Show SafeLine container and port status
  patch             Patch SafeLine compose for bridge mode (port 8888)
  help              Show this help

Options (for patch):
  --compose <path>               Compose file path (default: /data/safeline/compose.yaml)

Options (for up/reset/status):
  --platform <auto|wsl|linux>    Platform mode (default: auto)

Notes:
  - "up/reset" are NON-INTERACTIVE and DESTRUCTIVE by design.
  - bridge mode patch is applied for both Linux and WSL2 (traffic port 8888).
  - auto platform mode resolves to: wsl when running in WSL2, linux otherwise.
USAGE_EOF
}


is_wsl() {
  grep -qi microsoft /proc/version 2>/dev/null || grep -qi microsoft /proc/sys/kernel/osrelease 2>/dev/null
}


resolve_platform() {
  local requested="$1"
  case "$requested" in
    auto)
      if is_wsl; then
        printf 'wsl'
      else
        printf 'linux'
      fi
      ;;
    wsl|linux)
      printf '%s' "$requested"
      ;;
    *)
      die "Unsupported --platform value: $requested"
      ;;
  esac
}


ensure_root() {
  if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
    exec sudo -E bash "$0" "${ORIGINAL_ARGS[@]}"
  fi
}


require_command() {
  local cmd="$1"
  command -v "$cmd" >/dev/null 2>&1 || die "Missing required command: $cmd"
}


remove_safeline_containers() {
  local ids
  ids="$(docker ps -aq --filter "name=safeline" | tr '\n' ' ')"
  if [[ -n "${ids// }" ]]; then
    log "Removing SafeLine containers: $ids"
    # shellcheck disable=SC2086
    docker rm -f $ids >/dev/null 2>&1 || true
  fi
}


remove_safeline_volumes() {
  local vols
  vols="$(docker volume ls --format '{{.Name}}' | grep -Ei 'safeline' || true)"
  if [[ -n "${vols// }" ]]; then
    log "Removing SafeLine volumes"
    while IFS= read -r vol; do
      [[ -n "$vol" ]] && docker volume rm -f "$vol" >/dev/null 2>&1 || true
    done <<<"$vols"
  fi
}


remove_safeline_networks() {
  local nets
  nets="$(docker network ls --format '{{.Name}}' | grep -Ei '^safeline|safeline-ce$' || true)"
  if [[ -n "${nets// }" ]]; then
    log "Removing SafeLine networks"
    while IFS= read -r net; do
      [[ -n "$net" ]] && docker network rm "$net" >/dev/null 2>&1 || true
    done <<<"$nets"
  fi
}


full_reset_safeline() {
  log "Running full SafeLine reset (containers + volumes + networks + /data/safeline)"
  remove_safeline_containers
  remove_safeline_volumes
  remove_safeline_networks
  rm -rf "$SAFELINE_ROOT"
}


install_safeline() {
  log "Installing SafeLine via official installer"
  bash -c "$(curl -fsSLk "$INSTALL_URL")"
}


patch_compose_file() {
  local compose_path="$1"
  [[ -f "$compose_path" ]] || die "Compose file not found: $compose_path"

  log "Patching compose for bridge mode: $compose_path"
  cp "$compose_path" "${compose_path}.bak"

  python3 - "$compose_path" <<'PYEOF'
import re
import sys
from pathlib import Path

compose_path = Path(sys.argv[1])
lines = compose_path.read_text(encoding="utf-8").splitlines()

# Find service blocks (2-space indent service names).
service_bounds = {}
start_idx = None
start_name = None
for i, line in enumerate(lines):
    m = re.match(r"^  ([A-Za-z0-9_.-]+):\s*$", line)
    if m:
        if start_name is not None:
            service_bounds[start_name] = (start_idx, i)
        start_name = m.group(1)
        start_idx = i
if start_name is not None:
    service_bounds[start_name] = (start_idx, len(lines))

target = None
for candidate in ("tengine", "safeline-tengine"):
    if candidate in service_bounds:
        target = candidate
        break
if target is None:
    raise SystemExit("Could not find tengine service block in compose file")

start, end = service_bounds[target]
block = lines[start:end]

patched = []
has_8888 = False
for line in block:
    if re.match(r"^\s*network_mode:\s*host\s*$", line):
        continue
    m = re.match(r'^(\s*-\s*)(["\']?)80:80\2\s*$', line)
    if m:
        line = f'{m.group(1)}"8888:8888"'
        has_8888 = True
    elif "8888:8888" in line:
        has_8888 = True
    patched.append(line)

if not has_8888:
    insert_at = len(patched)
    patched[insert_at:insert_at] = [
        "    ports:",
        '      - "8888:8888"',
    ]

new_lines = lines[:start] + patched + lines[end:]
compose_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
print(f"Patched tengine service: {target}")
PYEOF
}


wait_for_port() {
  local host="$1"
  local port="$2"
  local timeout="${3:-60}"
  local i=0
  while (( i < timeout )); do
    if (echo >/dev/tcp/"$host"/"$port") >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
    ((i+=1))
  done
  return 1
}


start_safeline_stack() {
  local compose_path="$1"
  [[ -f "$compose_path" ]] || die "Compose file not found: $compose_path"
  log "Starting SafeLine stack"
  docker compose -f "$compose_path" up -d
}


show_status() {
  local requested_platform="auto"
  local effective_platform

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --platform)
        [[ $# -ge 2 ]] || die "Missing value for --platform"
        requested_platform="$2"
        shift 2
        ;;
      *)
        die "Unknown status option: $1"
        ;;
    esac
  done

  effective_platform="$(resolve_platform "$requested_platform")"
  log "Platform mode: $effective_platform (requested: $requested_platform)"

  log "Container status (name contains 'safeline'):"
  docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' --filter "name=safeline" || true

  if wait_for_port "127.0.0.1" "9443" 1; then
    log "Port 9443 is reachable"
  else
    warn "Port 9443 is not reachable"
  fi

  if wait_for_port "127.0.0.1" "8888" 1; then
    log "Port 8888 is reachable"
  else
    warn "Port 8888 is not reachable"
  fi
}


cmd_up() {
  local requested_platform="auto"
  local effective_platform

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --platform)
        [[ $# -ge 2 ]] || die "Missing value for --platform"
        requested_platform="$2"
        shift 2
        ;;
      *)
        die "Unknown up/reset option: $1"
        ;;
    esac
  done

  ensure_root "$@"
  require_command docker
  require_command curl
  require_command python3

  effective_platform="$(resolve_platform "$requested_platform")"
  log "Platform mode: $effective_platform (requested: $requested_platform)"

  full_reset_safeline
  install_safeline

  log "Applying bridge mode patch (traffic port 8888)"
  patch_compose_file "$DEFAULT_COMPOSE_PATH"

  start_safeline_stack "$DEFAULT_COMPOSE_PATH"

  log "Waiting for SafeLine management API (9443)"
  wait_for_port "127.0.0.1" "9443" 120 || die "SafeLine port 9443 did not become ready in time"

  log "Waiting for SafeLine traffic port (8888)"
  wait_for_port "127.0.0.1" "8888" 120 || die "SafeLine port 8888 did not become ready in time"

  log "SafeLine is ready"
  cat <<EOF_MSG
Next steps:
  1) Reset admin password:
     sudo docker exec safeline-mgt resetadmin
  2) Open https://localhost:9443 and generate API token
  3) Save token in .env as SAFELINE_API_TOKEN
Traffic entrypoint:
  http://localhost:8888
EOF_MSG
}


cmd_down() {
  ensure_root "$@"
  if [[ -f "$DEFAULT_COMPOSE_PATH" ]]; then
    log "Stopping SafeLine compose stack"
    docker compose -f "$DEFAULT_COMPOSE_PATH" down || true
  fi
  remove_safeline_containers
}


cmd_patch() {
  local compose_path="$DEFAULT_COMPOSE_PATH"
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --compose)
        [[ $# -ge 2 ]] || die "Missing value for --compose"
        compose_path="$2"
        shift 2
        ;;
      *)
        die "Unknown patch option: $1"
        ;;
    esac
  done
  patch_compose_file "$compose_path"
}


main() {
  local cmd="${1:-help}"
  shift || true
  case "$cmd" in
    up|reset)
      cmd_up "$@"
      ;;
    down)
      cmd_down "$@"
      ;;
    status)
      show_status "$@"
      ;;
    patch)
      cmd_patch "$@"
      ;;
    help|-h|--help)
      usage
      ;;
    *)
      usage
      die "Unknown command: $cmd"
      ;;
  esac
}


main "$@"
