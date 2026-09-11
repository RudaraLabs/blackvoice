#!/bin/sh
# Launcher installed at /usr/bin/blackvoice.
#
# The package ships a self-contained virtualenv under /opt/blackvoice. Calling
# its interpreter directly - rather than the venv's own console script - means
# nothing depends on the shebang that pip baked in at build time, so the venv
# stays correct however it was staged.

VENV=/opt/blackvoice/venv

if [ ! -x "$VENV/bin/python" ]; then
    echo "blackvoice: the bundled environment at $VENV is missing." >&2
    echo "Reinstall the package, or report this at" >&2
    echo "https://github.com/RudaraLabs/blackvoice/issues" >&2
    exit 1
fi

exec "$VENV/bin/python" -m blackvoice "$@"
