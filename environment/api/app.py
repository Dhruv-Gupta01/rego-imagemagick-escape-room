#!/usr/bin/env python3
"""
Escape-room game server.

All policy decisions (allow/deny, legal action sets, win condition) are
delegated to the OPA policy at POLICY_DIR via `opa eval` subprocess calls.
The server is intentionally stateless: every request carries the full game
state so tests can construct arbitrary scenarios without session management.
"""

import json
import os
import subprocess
from pathlib import Path

from flask import Flask, abort, jsonify, request

app = Flask(__name__)

POLICY_DIR = Path(os.environ.get("POLICY_DIR", "/app/policy"))
OPA_BIN = os.environ.get("OPA_BIN", "opa")
GLYPHS_DIR = Path(os.environ.get("GLYPHS_DIR", "/app/glyphs"))

_glyph_meta: dict | None = None


def _load_glyph_meta() -> dict:
    global _glyph_meta
    if _glyph_meta is None:
        with open(GLYPHS_DIR / "glyph_meta.json") as f:
            _glyph_meta = json.load(f)
    return _glyph_meta


def opa_eval(query: str, input_data: dict):
    """
    Run: opa eval -d <policy_dir> -I --format json '<query>'
    with input_data serialised as JSON on stdin.
    Returns the first expression's value, or None if the query is undefined.
    """
    result = subprocess.run(
        [OPA_BIN, "eval", "-d", str(POLICY_DIR), "-I", "--format", "json", query],
        input=json.dumps(input_data).encode(),
        capture_output=True,
        timeout=15,
    )
    if result.returncode != 0:
        raise RuntimeError(f"OPA error: {result.stderr.decode()}")
    data = json.loads(result.stdout)
    if not data.get("result"):
        return None
    return data["result"][0]["expressions"][0]["value"]


def _require_state(state: dict) -> None:
    required = {
        "current_room",
        "inventory",
        "unlocked_rooms",
        "epoch_phase",
        "glyph_index",
    }
    missing = required - state.keys()
    if missing:
        abort(400, description=f"Missing game-state fields: {sorted(missing)}")


# ── Endpoints ─────────────────────────────────────────────────────────────────


@app.get("/health")
def health():
    return jsonify({"status": "ok", "policy_dir": str(POLICY_DIR)})


@app.get("/glyph/<int:index>")
def glyph_info(index: int):
    """Return pixel dimensions for glyph <index> (0-3)."""
    if index not in range(4):
        abort(404, description="glyph index must be 0, 1, 2, or 3")
    meta = _load_glyph_meta()
    entry = meta[str(index)]
    return jsonify({"index": index, **entry})


@app.post("/decode_glyph")
def decode_glyph():
    """
    Compute the glyph_key_id for a given glyph_index.
    Formula: glyph_key_id = (width // 8) % 16   (integer result)
    """
    body = request.get_json(force=True) or {}
    idx = body.get("glyph_index")
    if idx not in range(4):
        abort(400, description="glyph_index must be 0, 1, 2, or 3")
    meta = _load_glyph_meta()
    width = meta[str(idx)]["width"]
    glyph_key_id = (width // 8) % 16
    return jsonify({"glyph_index": idx, "width": width, "glyph_key_id": glyph_key_id})


@app.post("/validate")
def validate():
    """
    Ask the OPA policy whether a specific action is allowed.
    Body: full game state + "action" field.
    Returns: {"allow": true|false}
    """
    state = request.get_json(force=True) or {}
    _require_state(state)
    if "action" not in state:
        abort(400, description="Missing 'action' field in request body")
    allow = opa_eval("data.escape.allow", state)
    return jsonify({"allow": bool(allow)})


@app.post("/allowed_actions")
def allowed_actions():
    """
    Ask the OPA policy for the complete set of legal actions given the
    current game state (no 'action' field needed in the body).
    Returns: {"actions": [ {type, ...}, ... ]}
    """
    state = request.get_json(force=True) or {}
    _require_state(state)
    actions = opa_eval("data.escape.allowed_actions", state)
    return jsonify({"actions": list(actions) if actions else []})


@app.post("/check_win")
def check_win():
    """
    Ask the OPA policy whether the current game state satisfies the win
    condition (player in R7 with required inventory).
    Returns: {"win": true|false}
    """
    state = request.get_json(force=True) or {}
    _require_state(state)
    win = opa_eval("data.escape.win", state)
    return jsonify({"win": bool(win)})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
