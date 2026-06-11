#!/usr/bin/env bash
# SpecForge uninstaller for Linux/macOS installs created by scripts/install.sh.

set -euo pipefail

INSTALL_DIR="${SPECFORGE_INSTALL_DIR:-$HOME/.local/share/specforge/specforge}"
SHIM_DIR="${SPECFORGE_SHIM_DIR:-$HOME/.local/bin}"
REMOVE_CODE=0
ASSUME_YES=0

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log_info() { printf "%b==>%b %s\n" "$CYAN" "$NC" "$1"; }
log_success() { printf "%bOK%b %s\n" "$GREEN" "$NC" "$1"; }
log_warn() { printf "%b!%b %s\n" "$YELLOW" "$NC" "$1"; }
log_error() { printf "%bError:%b %s\n" "$RED" "$NC" "$1" >&2; }

usage() {
  cat <<'EOF'
SpecForge uninstaller

Usage: uninstall.sh [options]

Options:
  --dir PATH       Installed checkout path.
                   Default: ~/.local/share/specforge/specforge
  --shim-dir PATH  Directory containing the specforge command shim.
                   Default: ~/.local/bin
  --remove-code    Remove the installed checkout directory after removing .venv.
  -y, --yes        Do not prompt for confirmation.
  -h, --help       Show this help.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dir)
      INSTALL_DIR="$2"
      shift 2
      ;;
    --shim-dir)
      SHIM_DIR="$2"
      shift 2
      ;;
    --remove-code)
      REMOVE_CODE=1
      shift
      ;;
    -y|--yes)
      ASSUME_YES=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      log_error "Unknown option: $1"
      usage >&2
      exit 2
      ;;
  esac
done

detect_local_repo() {
  local script_dir repo_dir
  if [[ "${BASH_SOURCE[0]}" != */* ]]; then
    return 1
  fi

  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  repo_dir="$(cd "$script_dir/.." && pwd)"
  if [[ -f "$repo_dir/pyproject.toml" && -d "$repo_dir/src/specforge" ]]; then
    printf '%s\n' "$repo_dir"
    return 0
  fi
  return 1
}

is_unsafe_path() {
  local resolved
  resolved="$(cd "$(dirname "$1")" 2>/dev/null && pwd)/$(basename "$1")"
  [[ "$resolved" == "/" || "$resolved" == "$HOME" ]]
}

local_repo="$(detect_local_repo || true)"
if [[ -n "$local_repo" && -z "${SPECFORGE_INSTALL_DIR:-}" ]]; then
  INSTALL_DIR="$local_repo"
fi

if [[ "$ASSUME_YES" -ne 1 ]]; then
  printf 'SpecForge uninstall will remove:\n'
  printf '  Virtual environment: %s/.venv\n' "$INSTALL_DIR"
  printf '  Command shim:        %s/specforge\n' "$SHIM_DIR"
  if [[ "$REMOVE_CODE" -eq 1 ]]; then
    printf '  Code directory:      %s\n' "$INSTALL_DIR"
    log_warn "remove-code deletes the installed checkout directory."
  else
    printf '  Code directory:      kept at %s\n' "$INSTALL_DIR"
  fi
  printf '\n'
  read -r -p "Type 'yes' to continue: " answer
  if [[ "$answer" != "yes" ]]; then
    printf 'Uninstall cancelled.\n'
    exit 0
  fi
fi

shim_path="$SHIM_DIR/specforge"
if [[ -f "$shim_path" ]]; then
  if grep -F "$INSTALL_DIR" "$shim_path" >/dev/null 2>&1; then
    rm -f "$shim_path"
    log_success "Removed $shim_path"
  else
    log_warn "Not removing $shim_path because it was not created for $INSTALL_DIR"
  fi
else
  log_info "Command shim not found: $shim_path"
fi

if [[ -d "$INSTALL_DIR/.venv" ]]; then
  rm -rf "$INSTALL_DIR/.venv"
  log_success "Removed $INSTALL_DIR/.venv"
else
  log_info "Virtual environment not found: $INSTALL_DIR/.venv"
fi

if [[ "$REMOVE_CODE" -eq 1 ]]; then
  if is_unsafe_path "$INSTALL_DIR"; then
    log_error "Refusing to remove unsafe install path: $INSTALL_DIR"
    exit 1
  fi
  if [[ -d "$INSTALL_DIR" ]]; then
    rm -rf "$INSTALL_DIR"
    log_success "Removed $INSTALL_DIR"
  fi
fi

log_success "SpecForge uninstall complete"
