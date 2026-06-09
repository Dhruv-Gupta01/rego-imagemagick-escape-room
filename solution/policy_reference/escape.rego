package escape

import future.keywords.contains
import future.keywords.if
import future.keywords.in

# Reference oracle for the escape-room policy. Every decision is derived from
# input.* — no answers are hardcoded. See instruction.md and docs/RULES.md.

# ─── Room graph ────────────────────────────────────────────────────────────────
# door_req[from][to] = item required to traverse; "" means no item required.
# The exit door (R5→R7) is handled by the `exit` action rule, not here.
door_req := {
	"R0": {"R1": ""},
	"R1": {"R0": "", "R2": "brass_key", "R3": ""},
	"R2": {"R1": "brass_key", "R6": "glyph_key"},
	"R3": {"R1": "", "R4": "hammer"},
	"R4": {"R3": "hammer", "R6": ""},
	"R5": {"R6": ""},
	"R6": {"R2": "glyph_key", "R4": "", "R5": ""},
	"R7": {},
}

# ─── Combine recipes ───────────────────────────────────────────────────────────
combine_result["torch"]["oil"] := "lit_torch"

combine_result["oil"]["torch"] := "lit_torch"

combine_result["stick"]["rock"] := "hammer"

combine_result["rock"]["stick"] := "hammer"

# ─── Glyph decode ─────────────────────────────────────────────────────────────
# Pixel widths of glyph_0..glyph_3 (deterministic; baked in at docker build time).
glyph_widths := {0: 112, 1: 144, 2: 192, 3: 160}

# Integer key id for the current scenario: (width // 8) % 16
# All widths are exact multiples of 8, so the division is always exact.
computed_glyph_key_id := (glyph_widths[input.glyph_index] / 8) % 16

# ─── Helpers ──────────────────────────────────────────────────────────────────

# ─── Movement-blocking precedence lattice ─────────────────────────────────────
# Blocking applies to move / teleport / exit only (look/take/combine/use/
# decode_glyph are never blocked). The epoch_phase + master_seal form a lattice:
#   normal phase  : blocked iff cursed_idol is held
#   eclipse phase : never blocked (the idol curse is lifted)
#   sealed phase  : blocked, UNLESS master_seal is held (master_seal overrides)
# phase_blocked: the per-phase block, before the global phase_anchor override.
phase_blocked if {
	input.epoch_phase == "normal"
	"cursed_idol" in input.inventory
}

phase_blocked if {
	input.epoch_phase == "eclipse"
	"eclipse_ward" in input.inventory
}

phase_blocked if {
	input.epoch_phase == "sealed"
	not has_master_seal
}

# movement_blocked: the per-phase block applies UNLESS phase_anchor overrides it.
# Holding phase_anchor lifts ALL movement blocking in every phase.
movement_blocked if {
	phase_blocked
	not has_phase_anchor
}

has_master_seal if {
	"master_seal" in input.inventory
}

has_phase_anchor if {
	"phase_anchor" in input.inventory
}

# ─── Colour-lock universal requirement ────────────────────────────────────────
# The Exit demands EVERY colour lock be satisfied: for every colour in
# required_colors, key_<colour> must be in inventory (universal => "no colour
# key is missing").
required_colors := {"red", "green", "blue"}

has_color_key(c) if {
	key := sprintf("key_%s", [c])
	key in input.inventory
}

some_color_key_missing if {
	some c in required_colors
	not has_color_key(c)
}

all_color_keys if {
	not some_color_key_missing
}

# door_passable(from, to): can the player traverse this specific door right now?

# Case 1: no item requirement.
door_passable(from, to) if {
	door_req[from][to] == ""
}

# Case 2: requires a non-glyph item — presence in inventory is sufficient.
door_passable(from, to) if {
	req := door_req[from][to]
	req != ""
	req != "glyph_key"
	req in input.inventory
}

# Case 3: requires glyph_key — must have the key AND the correct integer id.
# A hardcoded constant fails any held-out case with a different glyph_index.
door_passable(from, to) if {
	door_req[from][to] == "glyph_key"
	"glyph_key" in input.inventory
	input.glyph_key_id == computed_glyph_key_id
}

# ─── Wormhole reachability (Lever 2) ──────────────────────────────────────────
# Build a traversable sub-graph over rooms the player has already unlocked,
# then use graph.reachable for transitive closure.
# Rego forbids recursive rules — graph.reachable is the required approach.

unlocked_graph[from] := neighbors if {
	some from in input.unlocked_rooms
	neighbors := {to |
		some to in input.unlocked_rooms
		door_passable(from, to)
	}
}

reachable_rooms contains room if {
	reachable := graph.reachable(unlocked_graph, {input.current_room})
	some room in reachable
	room != input.current_room
}

# ─── Win condition ─────────────────────────────────────────────────────────────
win if {
	input.current_room == "R7"
	"hammer" in input.inventory
	"lit_torch" in input.inventory
	"glyph_key" in input.inventory
	input.glyph_key_id == computed_glyph_key_id
	all_color_keys
}

# ─── allow (Lever 3: default deny + curse precedence) ─────────────────────────
default allow = false

# look: always allowed.
allow if {
	input.action.type == "look"
}

# take: item must be present in the current room.
allow if {
	input.action.type == "take"
	input.action.item in input.available_items
}

# combine: both ingredients in inventory and a valid recipe must exist.
allow if {
	input.action.type == "combine"
	input.action.item1 in input.inventory
	input.action.item2 in input.inventory
	combine_result[input.action.item1][input.action.item2] # resolves to result name; undefined = no recipe
}

# use: item must be in inventory.
allow if {
	input.action.type == "use"
	input.action.item in input.inventory
}

# move: door passable AND curse not active. R7 is only reachable via `exit`.
allow if {
	input.action.type == "move"
	input.action.room != "R7"
	not movement_blocked
	door_passable(input.current_room, input.action.room)
}

# decode_glyph: only valid at R2 (the Archive terminal).
allow if {
	input.action.type == "decode_glyph"
	input.current_room == "R2"
}

# teleport: from R6 only; target must be reachable through unlocked graph; curse blocks.
allow if {
	input.action.type == "teleport"
	input.current_room == "R6"
	not movement_blocked
	input.action.room in reachable_rooms
}

# exit: from R5 only; lit_torch + glyph_key (correct id) required; curse blocks.
# Eclipse exception: cursed_blocked is false when epoch_phase == "eclipse",
# so `not cursed_blocked` passes and exit is allowed even with the idol.
allow if {
	input.action.type == "exit"
	input.current_room == "R5"
	not movement_blocked
	"lit_torch" in input.inventory
	"glyph_key" in input.inventory
	input.glyph_key_id == computed_glyph_key_id
	all_color_keys
}

# ─── allowed_actions set (Lever 1) ────────────────────────────────────────────
# `contains` is Rego's partial-set syntax: each clause adds one element to the
# set when its condition holds. `some x` declares x as a local variable that
# OPA enumerates — required for variables that appear in the set element value.

allowed_actions contains {"type": "look"}

allowed_actions contains {"type": "take", "item": item} if {
	some item in input.available_items
}

allowed_actions contains {"type": "combine", "item1": i1, "item2": i2} if {
	some i1 in input.inventory
	some i2 in input.inventory
	combine_result[i1][i2]
}

allowed_actions contains {"type": "use", "item": item} if {
	some item in input.inventory
}

# Enumerate room from door_req keys so `room` is grounded for the head value.
allowed_actions contains {"type": "move", "room": room} if {
	some room
	door_req[input.current_room][room] # binds room to each adjacent room key
	room != "R7"
	not movement_blocked
	door_passable(input.current_room, room)
}

allowed_actions contains {"type": "decode_glyph"} if {
	input.current_room == "R2"
}

allowed_actions contains {"type": "teleport", "room": room} if {
	input.current_room == "R6"
	not movement_blocked
	some room in reachable_rooms
}

allowed_actions contains {"type": "exit"} if {
	input.current_room == "R5"
	not movement_blocked
	"lit_torch" in input.inventory
	"glyph_key" in input.inventory
	input.glyph_key_id == computed_glyph_key_id
	all_color_keys
}
