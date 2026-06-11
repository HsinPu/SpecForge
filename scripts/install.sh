#!/usr/bin/env bash
# SpecForge installer for Linux/macOS.
#
# Usage:
#   bash scripts/install.sh
#   curl -fsSL https://raw.githubusercontent.com/HsinPu/SpecForge/main/scripts/install.sh | bash

set -euo pipefail

REPO_URL="${SPECFORGE_REPO_URL:-https://github.com/HsinPu/SpecForge.git}"
BRANCH="${SPECFORGE_BRANCH:-main}"
INSTALL_DIR="${SPECFORGE_INSTALL_DIR:-$HOME/.local/share/specforge/specforge}"
SHIM_DIR="${SPECFORGE_SHIM_DIR:-$HOME/.local/bin}"
CREATE_LINK=1

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
SpecForge installer

Usage: install.sh [options]

Options:
  --dir PATH       Install checkout path for streamed installs.
                   Default: ~/.local/share/specforge/specforge
  --branch NAME    Git branch to install. Default: main
  --repo URL       Git repository URL. Default: https://github.com/HsinPu/SpecForge.git
  --no-link        Do not create ~/.local/bin/specforge.
  -h, --help       Show this help.

Environment overrides:
  SPECFORGE_REPO_URL
  SPECFORGE_BRANCH
  SPECFORGE_INSTALL_DIR
  SPECFORGE_SHIM_DIR
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dir)
      INSTALL_DIR="$2"
      shift 2
      ;;
    --branch)
      BRANCH="$2"
      shift 2
      ;;
    --repo)
      REPO_URL="$2"
      shift 2
      ;;
    --no-link)
      CREATE_LINK=0
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

python_is_usable() {
  "$1" - <<'PY'
import sys
raise SystemExit(0 if sys.version_info >= (3, 11) else 1)
PY
}

resolve_python() {
  for candidate in python3 python; do
    if command -v "$candidate" >/dev/null 2>&1 && python_is_usable "$candidate"; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  return 1
}

install_repository() {
  log_info "Installing repository to $INSTALL_DIR"
  if ! command -v git >/dev/null 2>&1; then
    log_error "Git was not found. Install Git and re-run this installer."
    exit 1
  fi

  mkdir -p "$(dirname "$INSTALL_DIR")"
  if [[ -d "$INSTALL_DIR/.git" ]]; then
    git -C "$INSTALL_DIR" fetch origin
    git -C "$INSTALL_DIR" checkout "$BRANCH"
    git -C "$INSTALL_DIR" pull --ff-only origin "$BRANCH"
    return 0
  fi

  if [[ -e "$INSTALL_DIR" ]]; then
    log_error "Install path exists but is not a git checkout: $INSTALL_DIR"
    exit 1
  fi

  git clone --branch "$BRANCH" "$REPO_URL" "$INSTALL_DIR"
}

install_package() {
  local python_cmd="$1"
  local source_dir="$2"
  local venv_dir="$source_dir/.venv"

  if [[ ! -x "$venv_dir/bin/python" ]]; then
    log_info "Creating virtual environment"
    "$python_cmd" -m venv "$venv_dir"
  fi

  log_info "Installing SpecForge package"
  "$venv_dir/bin/python" -m pip install --upgrade pip
  "$venv_dir/bin/python" -m pip install -e "$source_dir"
}

install_link() {
  local source_dir="$1"
  if [[ "$CREATE_LINK" -ne 1 ]]; then
    return 0
  fi

  mkdir -p "$SHIM_DIR"
  cat > "$SHIM_DIR/specforge" <<EOF
#!/usr/bin/env bash
exec "$source_dir/.venv/bin/python" -m specforge "\$@"
EOF
  chmod +x "$SHIM_DIR/specforge"
  log_success "Created command shim: $SHIM_DIR/specforge"

  case ":$PATH:" in
    *":$SHIM_DIR:"*) ;;
    *)
      log_warn "$SHIM_DIR is not currently in PATH. Add it to your shell profile if specforge is not found."
      ;;
  esac
}

local_repo="$(detect_local_repo || true)"
if [[ -n "$local_repo" && -z "${SPECFORGE_INSTALL_DIR:-}" ]]; then
  INSTALL_DIR="$local_repo"
  source_dir="$local_repo"
  log_info "Using local checkout: $source_dir"
else
  install_repository
  source_dir="$INSTALL_DIR"
fi

python_cmd="$(resolve_python || true)"
if [[ -z "$python_cmd" ]]; then
  log_error "Python 3.11+ was not found."
  exit 1
fi
log_success "$python_cmd provides Python 3.11+"

install_package "$python_cmd" "$source_dir"
install_link "$source_dir"

log_info "Verifying SpecForge"
"$source_dir/.venv/bin/python" -m specforge --version

log_success "SpecForge installation complete"
printf '\nUsage:\n'
printf '  cd /path/to/project\n'
printf '  specforge init\n'
printf '\nUpdate later:\n'
printf '  specforge update\n'
