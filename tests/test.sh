#!/usr/bin/env bash
# Verifier script. Must ALWAYS write /logs/verifier/reward.txt (1 or 0).
# NOTE: no `set -e` — a non-zero pytest exit must NOT abort before we capture
# it into RC and write the reward file.

set -uo pipefail

# ── Install verifier-only deps from vendored wheels (offline; no internet) ─────
# These are NOT baked into the runtime image; they ship with the tests and are
# installed here from local wheels, so no network access is required.
pip install --no-index --find-links=/tests/wheels \
    pytest==8.4.1 pytest-json-ctrf==0.3.5 requests==2.32.3

# ── Start Flask server ────────────────────────────────────────────────────────
cd /app && python api/app.py &

# Wait up to 20 s for Flask to accept connections (pure Python — no curl)
echo "[test.sh] Waiting for Flask on :5000..."
for i in $(seq 1 20); do
    if python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/health', timeout=2)" > /dev/null 2>&1; then
        echo "[test.sh] Flask ready (attempt ${i})"
        break
    fi
    sleep 1
done

mkdir -p /logs/verifier

# ── Run pytest, then write reward ─────────────────────────────────────────────
python -m pytest -o cache_dir=/tmp/pytest_cache \
    --ctrf /logs/verifier/ctrf.json \
    /tests/test_outputs.py -rA -v

RC=$?
if [ "$RC" -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
