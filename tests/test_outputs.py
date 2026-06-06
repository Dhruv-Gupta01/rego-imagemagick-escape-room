"""
Verifier test suite for the Rego Escape Room task.

Structure:
  1. Parametrized allow/deny cases (loaded from cases/allow_cases.json, deny_cases.json)
  2. Exact allowed_actions set assertions (loaded from cases/allowed_actions_cases.json)
  3. Win-condition cases (loaded from cases/win_cases.json)
  4. Playthrough sequences (loaded from cases/playthroughs.json)

Every case is checked against the running Flask server, which delegates to the
OPA policy. Scoring is all-or-nothing: a single wrong allow/deny, a single extra
or missing allowed_actions element, a single wrong win result, or a single wrong
playthrough step fails the whole run.
"""

import json
import time
from pathlib import Path

import pytest
import requests

BASE = "http://localhost:5000"
CASES_DIR = Path("/tests/cases")


# ── Helpers ───────────────────────────────────────────────────────────────────


def _validate(state: dict) -> bool:
    r = requests.post(f"{BASE}/validate", json=state, timeout=20)
    r.raise_for_status()
    return r.json()["allow"]


def _allowed_actions(state: dict) -> list[dict]:
    r = requests.post(f"{BASE}/allowed_actions", json=state, timeout=20)
    r.raise_for_status()
    return r.json()["actions"]


def _check_win(state: dict) -> bool:
    r = requests.post(f"{BASE}/check_win", json=state, timeout=20)
    r.raise_for_status()
    return r.json()["win"]


def _action_set(state: dict) -> set[frozenset]:
    """allowed_actions as a set of frozensets, for exact (order-free) comparison."""
    return {frozenset(a.items()) for a in _allowed_actions(state)}


def _expected_set(actions: list[dict]) -> set[frozenset]:
    return {frozenset(a.items()) for a in actions}


# ── Fixture: wait for Flask ────────────────────────────────────────────────────


@pytest.fixture(scope="session", autouse=True)
def wait_for_flask():
    for _ in range(20):
        try:
            r = requests.get(f"{BASE}/health", timeout=3)
            if r.status_code == 200:
                return
        except requests.exceptions.ConnectionError:
            pass
        time.sleep(1)
    pytest.fail("Flask server did not start within 20 seconds")


# ── 1. Parametrized allow / deny cases ───────────────────────────────────────


def _load_cases(filename: str) -> list:
    data = json.loads((CASES_DIR / filename).read_text())
    return [(c["id"], c["input"], c["expected"]) for c in data]


@pytest.mark.parametrize("case_id,state,expected", _load_cases("allow_cases.json"))
def test_allow_case(case_id, state, expected):
    assert _validate(state) is expected, f"[{case_id}] expected allow={expected}"


@pytest.mark.parametrize("case_id,state,expected", _load_cases("deny_cases.json"))
def test_deny_case(case_id, state, expected):
    assert _validate(state) is expected, f"[{case_id}] expected allow={expected}"


# ── 2. Exact allowed_actions set assertions ──────────────────────────────────
# Each case pins the COMPLETE set of legal actions for a state (no missing, no
# extra). These span every branch of the movement lattice (normal/eclipse/sealed
# x cursed_idol/master_seal), the colour-lock exit gate, and teleport reachability.


def _load_action_cases() -> list:
    data = json.loads((CASES_DIR / "allowed_actions_cases.json").read_text())
    return [(c["id"], c["state"], c["expected_actions"]) for c in data]


@pytest.mark.parametrize("case_id,state,expected_actions", _load_action_cases())
def test_allowed_actions_exact(case_id, state, expected_actions):
    got = _action_set(state)
    want = _expected_set(expected_actions)
    missing = {dict(fs) for fs in want - got}
    extra = {dict(fs) for fs in got - want}
    assert got == want, (
        f"[{case_id}] allowed_actions mismatch — "
        f"missing={missing} extra={extra}"
    )


# ── 3. Win-condition cases ────────────────────────────────────────────────────


def _load_win_cases() -> list:
    data = json.loads((CASES_DIR / "win_cases.json").read_text())
    return [(c["id"], c["state"], c["expected"]) for c in data]


@pytest.mark.parametrize("case_id,state,expected", _load_win_cases())
def test_win_case(case_id, state, expected):
    assert _check_win(state) is expected, f"[{case_id}] expected win={expected}"


# ── 4. Playthrough sequences ──────────────────────────────────────────────────


def _load_playthroughs() -> list:
    return json.loads((CASES_DIR / "playthroughs.json").read_text())


def _run_playthrough(pt_id: str):
    pt = next(p for p in _load_playthroughs() if p["id"] == pt_id)
    for step in pt["steps"]:
        state = {**step["state"], "action": step["action"]}
        result = _validate(state)
        assert result is step["expected_allow"], (
            f"{pt_id} step failed: '{step['description']}' "
            f"expected allow={step['expected_allow']}, got {result}"
        )
    return pt


def test_canonical_win_playthrough():
    """Every step of the canonical solution must be allowed; final state wins."""
    pt = _run_playthrough("canonical_win")
    assert _check_win(pt["final_state"]) is True, "win must hold after canonical path"


def test_cursed_exit_blocked_playthrough():
    """Taking cursed_idol (normal phase) then moving must be denied."""
    _run_playthrough("cursed_exit_blocked")


def test_wrong_glyph_id_blocks_door():
    """glyph_key with the wrong id must be denied at the R2->R6 door."""
    _run_playthrough("wrong_glyph_id_blocks_door")


def test_exit_missing_lit_torch():
    """Exit without lit_torch must be denied even with all colour keys present."""
    _run_playthrough("exit_missing_lit_torch")
