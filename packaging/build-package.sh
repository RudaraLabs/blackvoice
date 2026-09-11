#!/usr/bin/env bash
#
# Build a .deb or .rpm containing a self-contained Black Voice.
#
#   ./packaging/build-package.sh deb
#   ./packaging/build-package.sh rpm
#
# The package ships a virtualenv at /opt/blackvoice/venv with every Python
# dependency inside it. That is deliberate: vosk is not in any distro's
# repositories and the PyQt6 package names differ across distributions, so
# depending on system Python packages would break somewhere.
#
# Because a virtualenv is tied to the interpreter that created it, this script
# must run on the distribution it targets - the release workflow runs it inside
# a Debian container for the .deb and a Fedora container for the .rpm.
#
set -euo pipefail

TYPE="${1:?usage: build-package.sh deb|rpm}"
case "$TYPE" in
    deb|rpm) ;;
    *) echo "unknown package type: $TYPE" >&2; exit 2 ;;
esac

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PREFIX=/opt/blackvoice
VENV="$PREFIX/venv"
STAGE="$ROOT/build/stage-$TYPE"
OUT="$ROOT/dist"

# ------------------------------------------------------------------ version
# A quoted heredoc keeps the shell out of the Python entirely, which matters
# because the pattern is full of quote characters.
VERSION="$(python3 - "$ROOT/blackvoice/__init__.py" <<'PY'
import pathlib
import re
import sys

src = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8")
match = re.search(r'^__version__\s*=\s*["\']([^"\']+)["\']', src, re.M)
if not match:
    sys.exit("no __version__ found")
print(match.group(1))
PY
)"
[ -n "$VERSION" ] || { echo "could not read the version" >&2; exit 1; }

echo "==> Black Voice $VERSION  ($TYPE)"

# --------------------------------------------------------------- the venv
# Built at its final absolute path so nothing has to be relocated afterwards.
echo "==> building the bundled environment"
rm -rf "$VENV" "$STAGE"
mkdir -p "$PREFIX"
python3 -m venv "$VENV"
"$VENV/bin/pip" install --quiet --upgrade pip wheel
"$VENV/bin/pip" install --quiet "$ROOT[all]"

# Trim what is only needed to install, not to run. Saves ~15 MB.
echo "==> trimming"
"$VENV/bin/pip" uninstall -y --quiet pip setuptools wheel 2>/dev/null || true
find "$VENV" -type d -name '__pycache__'   -prune -exec rm -rf {} + 2>/dev/null || true
find "$VENV" -type d -name 'tests'          -prune -exec rm -rf {} + 2>/dev/null || true
find "$VENV" -type d -name 'test'           -prune -exec rm -rf {} + 2>/dev/null || true
find "$VENV" -type f -name '*.pyc'          -delete 2>/dev/null || true
# Qt ships translations and examples we never load.
find "$VENV" -type d -name 'Qt6' -prune -exec rm -rf {}/translations \; 2>/dev/null || true

# ------------------------------------------------------------------- stage
echo "==> staging"
mkdir -p "$STAGE$PREFIX" \
         "$STAGE/usr/bin" \
         "$STAGE/usr/share/applications" \
         "$STAGE/usr/share/icons/hicolor/scalable/apps" \
         "$STAGE/usr/lib/systemd/user" \
         "$STAGE/usr/share/doc/blackvoice"

cp -a "$VENV" "$STAGE$PREFIX/venv"

install -m 0755 "$ROOT/packaging/blackvoice-launcher.sh" "$STAGE/usr/bin/blackvoice"

# The shipped .desktop and .service carry an @BIN@ placeholder so the same
# files serve the tarball installer and the distro packages.
sed 's|@BIN@|/usr/bin/blackvoice|g' "$ROOT/packaging/blackvoice.desktop" \
    > "$STAGE/usr/share/applications/blackvoice.desktop"
sed 's|@BIN@|/usr/bin/blackvoice|g' "$ROOT/packaging/blackvoice.service" \
    > "$STAGE/usr/lib/systemd/user/blackvoice.service"
chmod 0644 "$STAGE/usr/share/applications/blackvoice.desktop" \
           "$STAGE/usr/lib/systemd/user/blackvoice.service"

install -m 0644 "$ROOT/assets/logo.svg" \
    "$STAGE/usr/share/icons/hicolor/scalable/apps/blackvoice.svg"
install -m 0644 "$ROOT/README.md" "$ROOT/LICENSE" "$STAGE/usr/share/doc/blackvoice/"

# ---------------------------------------------------------- post-install
cat > "$ROOT/build/after-install.sh" <<'HOOK'
#!/bin/sh
# Refresh the desktop caches so the launcher and icon appear without a re-login.
command -v update-desktop-database >/dev/null 2>&1 && \
    update-desktop-database -q /usr/share/applications 2>/dev/null || true
command -v gtk-update-icon-cache >/dev/null 2>&1 && \
    gtk-update-icon-cache -qtf /usr/share/icons/hicolor 2>/dev/null || true

cat <<'MSG'

  Black Voice is installed.

    blackvoice setup     download the offline speech models (~90 MB)
    blackvoice doctor    check the installation
    blackvoice           start it

  Documentation: https://github.com/RudaraLabs/blackvoice/wiki

MSG
exit 0
HOOK

cat > "$ROOT/build/after-remove.sh" <<'HOOK'
#!/bin/sh
command -v update-desktop-database >/dev/null 2>&1 && \
    update-desktop-database -q /usr/share/applications 2>/dev/null || true
command -v gtk-update-icon-cache >/dev/null 2>&1 && \
    gtk-update-icon-cache -qtf /usr/share/icons/hicolor 2>/dev/null || true
exit 0
HOOK

chmod +x "$ROOT/build/after-install.sh" "$ROOT/build/after-remove.sh"

# ------------------------------------------------------------------ build
mkdir -p "$OUT"

FPM_COMMON=(
    -s dir
    -t "$TYPE"
    -n blackvoice
    -v "$VERSION"
    --iteration 1
    --license MIT
    --vendor "Rudra Labs"
    --maintainer "Rudra Labs <connect@rudralabs.dev>"
    --url "https://github.com/RudaraLabs/blackvoice"
    --description "Offline-first voice assistant for Linux
Black Voice controls your desktop by voice in Hindi, English and Hinglish.
Speech recognition runs locally, so it works without a network connection.
Applications, volume, brightness, files, timers and guarded shell access,
plus question answering through a local or hosted language model."
    --after-install "$ROOT/build/after-install.sh"
    --after-remove "$ROOT/build/after-remove.sh"
    -C "$STAGE"
    --package "$OUT/"
)

case "$TYPE" in
    deb)
        # Runtime libraries only - every Python dependency is inside the venv.
        fpm "${FPM_COMMON[@]}" \
            --depends "python3 (>= 3.9)" \
            --depends "libportaudio2" \
            --depends "libasound2" \
            --deb-recommends "espeak-ng" \
            --deb-recommends "pulseaudio-utils" \
            --deb-recommends "libnotify-bin" \
            --deb-suggests "playerctl" \
            --deb-suggests "brightnessctl" \
            --deb-suggests "gnome-screenshot" \
            --deb-priority optional \
            --category sound \
            .
        ;;
    rpm)
        fpm "${FPM_COMMON[@]}" \
            --depends "python3 >= 3.9" \
            --depends "portaudio" \
            --depends "alsa-lib" \
            --rpm-summary "Offline-first voice assistant for Linux" \
            --category "Applications/Multimedia" \
            --rpm-tag "Recommends: espeak-ng" \
            --rpm-tag "Recommends: pulseaudio-utils" \
            --rpm-tag "Suggests: playerctl" \
            --rpm-tag "Suggests: brightnessctl" \
            .
        ;;
esac

echo
echo "==> built:"
ls -lh "$OUT"/*."$TYPE" | sed 's/^/    /'
