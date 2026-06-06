#!/usr/bin/env bash
# Oracle script. Copies the reference Rego policy into /app/policy/ so the
# verifier (tests/test.sh) runs against a known-correct implementation.
#
# harbor run -a oracle  →  runs this script, then runs tests/test.sh
# harbor run -a nop     →  skips this script entirely → /app/policy/ stays empty
#                          → OPA returns undefined for all queries → reward 0.0

set -euo pipefail

POLICY_DIR="/app/policy"
REFERENCE_DIR="/solution/policy_reference"

echo "[oracle] Copying reference Rego into ${POLICY_DIR}/"
cp "${REFERENCE_DIR}/escape.rego" "${POLICY_DIR}/escape.rego"

echo "[oracle] Validating policy parses cleanly..."
opa check "${POLICY_DIR}/"

echo "[oracle] Done. Policy installed at ${POLICY_DIR}/escape.rego"
