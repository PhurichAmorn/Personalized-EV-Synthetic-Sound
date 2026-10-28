#!/bin/sh
set -eu

cd "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"

if [ ! -x .venv/bin/python ]; then
    if ! command -v python3.12 >/dev/null 2>&1; then
        echo "Python 3.12 is required. Install it, then run this launcher again." >&2
        exit 1
    fi
    python3.12 -m venv .venv
fi

if ! .venv/bin/python -c 'import sys; sys.exit(sys.version_info[:2] != (3, 12))'; then
    echo "The existing .venv must use Python 3.12. Please recreate it with Python 3.12." >&2
    exit 1
fi

if ! cmp -s requirements.txt .venv/.installed-requirements.txt; then
    echo "Installing EV Lab dependencies…"
    .venv/bin/python -m pip install -r requirements.txt
    cp requirements.txt .venv/.installed-requirements.txt
fi

if ! .venv/bin/python setup.py build_ext --inplace; then
    echo "Native audio build failed; fix the compiler error before launching EV Sound Lab." >&2
    exit 1
fi

if [ ! -x desktop/node_modules/.bin/tauri ]; then
    (cd desktop && npm ci)
fi

cd desktop
exec npm run tauri -- dev "$@"
