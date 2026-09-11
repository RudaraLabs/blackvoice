#!/bin/sh
# Launcher installed at /usr/bin/blackvoice.
#
# Black Voice runs on the system Python. Everything the distribution packages —
# numpy, cffi, PyQt6, requests, psutil — is imported from there, so those follow
# whatever interpreter the system happens to have.
#
# The handful of libraries no distribution ships (vosk above all) live in
# /opt/blackvoice/lib. Every one of them is a py3-none or abi3 wheel, meaning it
# carries no CPython ABI tag and works on any Python 3, so this directory does
# not have to be rebuilt when the system interpreter is upgraded.
#
# The previous approach — a bundled virtualenv — could not do that: a venv
# symlinks the system interpreter and pins itself to that version, so a package
# built on Python 3.11 stopped working the moment the host had 3.13.

LIB=/opt/blackvoice/lib

if [ ! -d "$LIB" ]; then
    echo "blackvoice: the bundled libraries at $LIB are missing." >&2
    echo "Reinstall the package, or report this at" >&2
    echo "https://github.com/RudaraLabs/blackvoice/issues" >&2
    exit 1
fi

PYTHON="${BLACKVOICE_PYTHON:-python3}"
if ! command -v "$PYTHON" >/dev/null 2>&1; then
    echo "blackvoice: $PYTHON was not found." >&2
    echo "Install python3, or set BLACKVOICE_PYTHON to an interpreter." >&2
    exit 1
fi

# Appended, not prepended: a distribution's own numpy or PyQt6 should win over
# anything that happens to be sitting in our directory.
if [ -n "${PYTHONPATH:-}" ]; then
    PYTHONPATH="$PYTHONPATH:$LIB"
else
    PYTHONPATH="$LIB"
fi
export PYTHONPATH

exec "$PYTHON" -m blackvoice "$@"
