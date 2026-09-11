#!/usr/bin/env bash
#
# Black Voice installer for Linux.
#
#   ./install.sh              install into ~/.local/share/blackvoice-venv
#   ./install.sh --no-models  skip the ~90 MB model download
#   ./install.sh --system     install system tools too (needs sudo)
#   ./install.sh --uninstall  remove everything this script created
#
set -euo pipefail

APP_NAME="blackvoice"
VENV_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/${APP_NAME}-venv"
BIN_DIR="$HOME/.local/bin"
DESKTOP_DIR="$HOME/.local/share/applications"
ICON_DIR="$HOME/.local/share/icons/hicolor/scalable/apps"
AUTOSTART_DIR="$HOME/.config/autostart"
SYSTEMD_DIR="$HOME/.config/systemd/user"
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

WITH_MODELS=1
WITH_SYSTEM=0

bold() { printf '\033[1m%s\033[0m\n' "$1"; }
info() { printf '  \033[38;5;244m%s\033[0m\n' "$1"; }
ok()   { printf '  \033[38;5;42m✓\033[0m %s\n' "$1"; }
warn() { printf '  \033[38;5;214m!\033[0m %s\n' "$1"; }
die()  { printf '  \033[38;5;203m✗\033[0m %s\n' "$1" >&2; exit 1; }

usage() {
  sed -n '3,9p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
  exit 0
}

uninstall() {
  bold "Removing Black Voice"
  systemctl --user disable --now "${APP_NAME}.service" 2>/dev/null || true
  rm -f  "$SYSTEMD_DIR/${APP_NAME}.service"
  rm -f  "$DESKTOP_DIR/${APP_NAME}.desktop"
  rm -f  "$AUTOSTART_DIR/${APP_NAME}.desktop"
  rm -f  "$ICON_DIR/${APP_NAME}.svg"
  rm -f  "$BIN_DIR/blackvoice"
  rm -rf "$VENV_DIR"
  ok "removed the program"
  info "Your config, models and notes were left in place:"
  info "  ${XDG_CONFIG_HOME:-$HOME/.config}/$APP_NAME"
  info "  ${XDG_DATA_HOME:-$HOME/.local/share}/$APP_NAME"
  exit 0
}

for arg in "$@"; do
  case "$arg" in
    --no-models) WITH_MODELS=0 ;;
    --system)    WITH_SYSTEM=1 ;;
    --uninstall) uninstall ;;
    -h|--help)   usage ;;
    *)           die "unknown option: $arg" ;;
  esac
done

# --------------------------------------------------------------------- checks
bold "Black Voice — installer"
[[ "$(uname -s)" == "Linux" ]] || warn "this installer targets Linux; continuing anyway"

command -v python3 >/dev/null || die "python3 is not installed"
PY_VERSION="$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)' \
  || die "Python 3.9 or newer is required (found $PY_VERSION)"
ok "python $PY_VERSION"

python3 -c 'import venv' 2>/dev/null \
  || die "the venv module is missing — install python3-venv (Debian/Ubuntu: sudo apt install python3-venv)"

# ------------------------------------------------------------- system packages
if [[ "$WITH_SYSTEM" -eq 1 ]]; then
  bold "System packages"
  if command -v apt-get >/dev/null; then
    sudo apt-get update
    sudo apt-get install -y portaudio19-dev python3-dev espeak-ng \
      libnotify-bin playerctl brightnessctl pulseaudio-utils gnome-screenshot
  elif command -v dnf >/dev/null; then
    sudo dnf install -y portaudio-devel python3-devel espeak-ng \
      libnotify playerctl brightnessctl pulseaudio-utils gnome-screenshot
  elif command -v pacman >/dev/null; then
    sudo pacman -S --needed --noconfirm portaudio espeak-ng \
      libnotify playerctl brightnessctl libpulse gnome-screenshot
  elif command -v zypper >/dev/null; then
    sudo zypper install -y portaudio-devel python3-devel espeak-ng \
      libnotify-tools playerctl brightnessctl pulseaudio-utils
  else
    warn "unknown package manager — install PortAudio and espeak-ng yourself"
  fi
  ok "system packages installed"
else
  info "skipping system packages (re-run with --system to install them)"
  command -v espeak-ng >/dev/null || warn "espeak-ng not found — there will be no speech output"
fi

# ---------------------------------------------------------------- virtualenv
bold "Python environment"
if [[ ! -d "$VENV_DIR" ]]; then
  python3 -m venv "$VENV_DIR"
  ok "created $VENV_DIR"
else
  ok "reusing $VENV_DIR"
fi

"$VENV_DIR/bin/pip" install --quiet --upgrade pip wheel
info "installing dependencies (this takes a minute)…"
if ! "$VENV_DIR/bin/pip" install --quiet -e "$SRC_DIR[all]"; then
  warn "the full install failed — retrying without the optional extras"
  "$VENV_DIR/bin/pip" install --quiet -e "$SRC_DIR" \
    || die "dependency installation failed; run '$VENV_DIR/bin/pip install -e $SRC_DIR' to see why"
fi
ok "dependencies installed"

# ----------------------------------------------------------------- launcher
mkdir -p "$BIN_DIR"
cat > "$BIN_DIR/blackvoice" <<EOF
#!/usr/bin/env bash
exec "$VENV_DIR/bin/blackvoice" "\$@"
EOF
chmod +x "$BIN_DIR/blackvoice"
ok "command installed at $BIN_DIR/blackvoice"

case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *) warn "$BIN_DIR is not on your PATH — add this to ~/.bashrc:"
     info 'export PATH="$HOME/.local/bin:$PATH"' ;;
esac

# -------------------------------------------------------- desktop integration
mkdir -p "$DESKTOP_DIR" "$ICON_DIR" "$SYSTEMD_DIR"
install -m 0644 "$SRC_DIR/assets/logo.svg" "$ICON_DIR/${APP_NAME}.svg"

sed "s|@BIN@|$BIN_DIR/blackvoice|g" "$SRC_DIR/packaging/blackvoice.desktop" \
  > "$DESKTOP_DIR/${APP_NAME}.desktop"
chmod 0644 "$DESKTOP_DIR/${APP_NAME}.desktop"

sed "s|@BIN@|$BIN_DIR/blackvoice|g" "$SRC_DIR/packaging/blackvoice.service" \
  > "$SYSTEMD_DIR/${APP_NAME}.service"

command -v update-desktop-database >/dev/null && \
  update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true
command -v gtk-update-icon-cache >/dev/null && \
  gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" 2>/dev/null || true
ok "desktop entry and icon installed"

# -------------------------------------------------------------------- models
if [[ "$WITH_MODELS" -eq 1 ]]; then
  bold "Speech models"
  "$VENV_DIR/bin/blackvoice" setup || warn "model download failed — run 'blackvoice setup' later"
else
  info "skipping models (run 'blackvoice setup' when you are ready)"
fi

# --------------------------------------------------------------------- done
bold "Done"
cat <<EOF

  Start it now:          blackvoice
  Terminal only:         blackvoice run --no-ui
  Type commands:         blackvoice text
  Check the install:     blackvoice doctor

  Start on login:        systemctl --user enable --now blackvoice
  Global hotkey:         bind '$BIN_DIR/blackvoice text' or use the tray icon

  Say "Black" to wake it up.

EOF
