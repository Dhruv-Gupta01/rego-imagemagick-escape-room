"""
Verifier test suite for the Rego ImageMagick Escape Room task.

Structure:
  1. Parametrized allow/deny cases (loaded from cases/*.json)
  2. Exact allowed_actions set assertions (Lever 1)
  3. Partial-unlock teleport coverage (Lever 2 — reachability)
  4. Canonical and must-fail playthrough sequences
  5. Win condition assertion
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
    """Return allowed_actions as a set of frozensets for exact comparison."""
    return {frozenset(a.items()) for a in _allowed_actions(state)}


def _action_in(state: dict, action: dict) -> bool:
    return frozenset(action.items()) in _action_set(state)


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


# ── 1. Parametrized allow/deny cases ─────────────────────────────────────────


def _load_cases(filename: str) -> list:
    data = json.loads((CASES_DIR / filename).read_text())
    return [(c["id"], c["input"], c["expected"]) for c in data]


@pytest.mark.parametrize("case_id,state,expected", _load_cases("allow_cases.json"))
def test_allow_case(case_id, state, expected):
    assert _validate(state) is expected, f"[{case_id}] expected allow={expected}"


@pytest.mark.parametrize("case_id,state,expected", _load_cases("deny_cases.json"))
def test_deny_case(case_id, state, expected):
    assert _validate(state) is expected, f"[{case_id}] expected allow={expected}"


# ── 2. Exact allowed_actions set assertions (Lever 1) ────────────────────────


def test_exact_actions_start_state():
    """R0 with brass_key available: exactly look + take brass_key + move R1."""
    state = {
        "current_room": "R0",
        "inventory": [],
        "unlocked_rooms": ["R0"],
        "glyph_key_id": None,
        "epoch_phase": "normal",
        "glyph_index": 0,
        "available_items": ["brass_key"],
    }
    expected = {
        frozenset({"type": "look"}.items()),
        frozenset({"type": "take", "item": "brass_key"}.items()),
        frozenset({"type": "move", "room": "R1"}.items()),
    }
    assert _action_set(state) == expected


def test_exact_actions_r2_before_decode():
    """R2 with only brass_key: look + use brass_key + move R1 + decode_glyph. NOT move R6."""
    state = {
        "current_room": "R2",
        "inventory": ["brass_key"],
        "unlocked_rooms": ["R0", "R1", "R2"],
        "glyph_key_id": None,
        "epoch_phase": "normal",
        "glyph_index": 0,
        "available_items": [],
    }
    expected = {
        frozenset({"type": "look"}.items()),
        frozenset({"type": "use", "item": "brass_key"}.items()),
        frozenset({"type": "move", "room": "R1"}.items()),
        frozenset({"type": "decode_glyph"}.items()),
    }
    assert _action_set(state) == expected, (
        "move R6 must not appear before glyph_key is decoded"
    )


def test_exact_actions_cursed_normal_epoch():
    """cursed_idol + normal epoch: curse active — only look and use cursed_idol. No move."""
    state = {
        "current_room": "R0",
        "inventory": ["cursed_idol"],
        "unlocked_rooms": ["R0"],
        "glyph_key_id": None,
        "epoch_phase": "normal",
        "glyph_index": 0,
        "available_items": [],
    }
    expected = {
        frozenset({"type": "look"}.items()),
        frozenset({"type": "use", "item": "cursed_idol"}.items()),
    }
    got = _action_set(state)
    # No move action should appear
    move_actions = {a for a in got if dict(a).get("type") == "move"}
    assert move_actions == set(), (
        f"Curse should block all move actions; got: {move_actions}"
    )
    assert got == expected


def test_exact_actions_cursed_eclipse():
    """cursed_idol + eclipse: curse lifted — move R1 must reappear."""
    state = {
        "current_room": "R0",
        "inventory": ["cursed_idol"],
        "unlocked_rooms": ["R0"],
        "glyph_key_id": None,
        "epoch_phase": "eclipse",
        "glyph_index": 0,
        "available_items": [],
    }
    expected = {
        frozenset({"type": "look"}.items()),
        frozenset({"type": "use", "item": "cursed_idol"}.items()),
        frozenset({"type": "move", "room": "R1"}.items()),
    }
    assert _action_set(state) == expected, (
        "eclipse must lift the curse — move R1 should be allowed"
    )


# ── 3. Partial-unlock teleport coverage (Lever 2) ────────────────────────────


def test_teleport_partial_unlock_allows_reachable():
    """
    Partial unlock: {R1, R3, R4, R6} with hammer in inventory.
    From R6: R6->R4->R3->R1 is traversable.
    Teleport to R4, R3, R1 must all be ALLOWED.
    """
    state = {
        "current_room": "R6",
        "inventory": ["hammer"],
        "unlocked_rooms": ["R1", "R3", "R4", "R6"],
        "glyph_key_id": None,
        "epoch_phase": "normal",
        "glyph_index": 0,
        "available_items": [],
    }
    for room in ["R4", "R3", "R1"]:
        assert _action_in(state, {"type": "teleport", "room": room}), (
            f"teleport {room} should be allowed — reachable through unlocked graph"
        )


def test_teleport_partial_unlock_denies_not_unlocked():
    """Same partial-unlock state — R0, R2, R5 not in unlocked_rooms → denied."""
    state = {
        "current_room": "R6",
        "inventory": ["hammer"],
        "unlocked_rooms": ["R1", "R3", "R4", "R6"],
        "glyph_key_id": None,
        "epoch_phase": "normal",
        "glyph_index": 0,
        "available_items": [],
    }
    for room in ["R0", "R2", "R5"]:
        assert not _action_in(state, {"type": "teleport", "room": room}), (
            f"teleport {room} should be denied — not in unlocked_rooms"
        )


def test_teleport_unlocked_but_unreachable():
    """
    R6 isolated state: unlocked_rooms = {R0, R1, R2, R6}, inventory = [brass_key].
    R6->R2 requires glyph_key (absent). R6->R4/R5 are outside unlocked_rooms.
    R6 has zero reachable neighbours -> no teleport should be allowed.
    Tests that the policy uses transitive closure, not just 'room in unlocked_rooms'.
    """
    state = {
        "current_room": "R6",
        "inventory": ["brass_key"],
        "unlocked_rooms": ["R0", "R1", "R2", "R6"],
        "glyph_key_id": None,
        "epoch_phase": "normal",
        "glyph_index": 0,
        "available_items": [],
    }
    actions = _action_set(state)
    teleport_actions = {a for a in actions if dict(a).get("type") == "teleport"}
    assert teleport_actions == set(), (
        f"R6 is isolated — no teleports should be allowed; got: {teleport_actions}"
    )


def test_teleport_reachable_via_brass_key_path():
    """
    Unlock {R0, R1, R2, R3, R4, R6} with brass_key + hammer + glyph_key (id=14).
    From R6: R6->R2 (glyph_key ✓) -> R2->R1 (brass_key ✓) -> R1->R3 -> R3->R4.
    Also R6->R4 directly.
    All of R0 (not unlocked here), R1, R2, R3, R4 should be reachable except R0 (not unlocked).
    """
    state = {
        "current_room": "R6",
        "inventory": ["brass_key", "hammer", "glyph_key", "lit_torch"],
        "unlocked_rooms": ["R1", "R2", "R3", "R4", "R6"],
        "glyph_key_id": 14,
        "epoch_phase": "normal",
        "glyph_index": 0,
        "available_items": [],
    }
    for room in ["R1", "R2", "R3", "R4"]:
        assert _action_in(state, {"type": "teleport", "room": room}), (
            f"teleport {room} should be allowed — reachable in unlocked graph"
        )
    # R0 not in unlocked_rooms
    assert not _action_in(state, {"type": "teleport", "room": "R0"}), (
        "R0 not in unlocked_rooms — teleport must be denied"
    )


# ── 4. Playthrough sequences ──────────────────────────────────────────────────


def _load_playthroughs() -> list:
    return json.loads((CASES_DIR / "playthroughs.json").read_text())


def test_canonical_win_playthrough():
    """Every step of the canonical solution must be allowed; final state must win."""
    playthroughs = _load_playthroughs()
    pt = next(p for p in playthroughs if p["id"] == "canonical_win")
    for step in pt["steps"]:
        state = {**step["state"], "action": step["action"]}
        result = _validate(state)
        assert result is step["expected_allow"], (
            f"canonical_win step failed: '{step['description']}' "
            f"expected allow={step['expected_allow']}, got {result}"
        )
    assert _check_win(pt["final_state"]) is True, (
        "win must be true after canonical path"
    )


def test_cursed_exit_blocked_playthrough():
    """Taking cursed_idol then attempting to move to R5 must be denied."""
    playthroughs = _load_playthroughs()
    pt = next(p for p in playthroughs if p["id"] == "cursed_exit_blocked")
    for step in pt["steps"]:
        state = {**step["state"], "action": step["action"]}
        result = _validate(state)
        assert result is step["expected_allow"], (
            f"cursed_exit step failed: '{step['description']}' "
            f"expected allow={step['expected_allow']}, got {result}"
        )


def test_wrong_glyph_id_blocks_door():
    """glyph_key with wrong id must be denied at the R2->R6 door."""
    playthroughs = _load_playthroughs()
    pt = next(p for p in playthroughs if p["id"] == "wrong_glyph_id_blocks_door")
    for step in pt["steps"]:
        state = {**step["state"], "action": step["action"]}
        result = _validate(state)
        assert result is step["expected_allow"], (
            f"wrong_glyph_id step failed: '{step['description']}' "
            f"expected allow={step['expected_allow']}, got {result}"
        )


def test_exit_missing_lit_torch():
    """Exit without lit_torch must be denied even with all other requirements met."""
    playthroughs = _load_playthroughs()
    pt = next(p for p in playthroughs if p["id"] == "exit_missing_lit_torch")
    for step in pt["steps"]:
        state = {**step["state"], "action": step["action"]}
        result = _validate(state)
        assert result is step["expected_allow"], (
            f"missing_lit_torch step failed: '{step['description']}' "
            f"expected allow={step['expected_allow']}, got {result}"
        )


# ── 5. Win condition ──────────────────────────────────────────────────────────


def test_win_requires_correct_glyph_id():
    """win is false when glyph_key_id is wrong even if in R7 with all items."""
    state = {
        "current_room": "R7",
        "inventory": ["hammer", "lit_torch", "glyph_key"],
        "unlocked_rooms": ["R0", "R1", "R2", "R3", "R4", "R5", "R6", "R7"],
        "glyph_key_id": 99,
        "epoch_phase": "normal",
        "glyph_index": 0,
        "available_items": [],
    }
    assert _check_win(state) is False


def test_win_false_when_missing_hammer():
    """win is false when hammer is absent from inventory."""
    state = {
        "current_room": "R7",
        "inventory": ["lit_torch", "glyph_key"],
        "unlocked_rooms": ["R0", "R1", "R2", "R3", "R4", "R5", "R6", "R7"],
        "glyph_key_id": 14,
        "epoch_phase": "normal",
        "glyph_index": 0,
        "available_items": [],
    }
    assert _check_win(state) is False


def test_win_false_when_not_in_r7():
    """win is false when player has all items but is not in R7."""
    state = {
        "current_room": "R5",
        "inventory": ["hammer", "lit_torch", "glyph_key"],
        "unlocked_rooms": ["R0", "R1", "R2", "R3", "R4", "R5", "R6"],
        "glyph_key_id": 14,
        "epoch_phase": "normal",
        "glyph_index": 0,
        "available_items": [],
    }
    assert _check_win(state) is False
