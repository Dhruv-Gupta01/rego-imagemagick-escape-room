# Rego ImageMagick Escape Room

A Flask escape-room server is running at `http://localhost:5000`. The server
delegates every game-rules decision to an OPA (Open Policy Agent) policy that
you must author. Your task is to write the Rego policy so that a scripted
playthrough of the escape room reaches the Exit and all illegal moves are
correctly rejected.

---

## Your deliverable

Write a Rego policy file at `/app/policy/escape.rego` (or multiple `.rego`
files under `/app/policy/`). The policy **must** be in package `escape` and
define the rules listed in §6. The Flask server calls OPA via:

```
opa eval -d /app/policy -I --format json '<query>'
```

with the full game state as JSON on stdin.

Validate your policy parses with: `opa check /app/policy/`

---

## §1 — Game state (OPA `input` shape)

Every OPA call receives a JSON object with these fields:

| Field | Type | Description |
|---|---|---|
| `current_room` | string | Room the player is in (R0–R7) |
| `inventory` | array of string | Items the player is holding |
| `unlocked_rooms` | array of string | Every room legally entered so far |
| `glyph_key_id` | integer or null | Integer id of the decoded glyph key; null if not yet decoded |
| `epoch_phase` | string | `"normal"`, `"eclipse"`, or `"sealed"` (see §7) |
| `glyph_index` | integer | Which glyph to decode (0–3); injected per scenario |
| `available_items` | array of string | Items in current room not yet picked up |
| `action` | object | The action being evaluated (omitted for `allowed_actions` queries) |

The `action` object always has a `"type"` field (one of the 8 values in §4)
plus type-specific fields: `"room"` for move/teleport, `"item"` for take/use,
`"item1"` + `"item2"` for combine.

---

## §2 — Rooms and door graph

Eight rooms. All door edges are **undirected** (traversal works both ways).

| ID | Name |
|---|---|
| R0 | Atrium — start room |
| R1 | Gallery |
| R2 | Archive — contains the glyph terminal |
| R3 | Workshop |
| R4 | Conservatory |
| R5 | Antechamber |
| R6 | Mirror Hall — contains the wormhole pad |
| R7 | Exit — win room |

**Door requirements** (item must be in inventory to traverse):

| Edge | Requirement |
|---|---|
| R0 ↔ R1 | none |
| R1 ↔ R2 | `brass_key` in inventory |
| R1 ↔ R3 | none |
| R3 ↔ R4 | `hammer` in inventory |
| R2 ↔ R6 | `glyph_key` in inventory **AND** `glyph_key_id` equals the computed id (§5) |
| R4 ↔ R6 | none |
| R6 ↔ R5 | none |
| R5 → R7 | `lit_torch` + `glyph_key` (correct id) + all three colour keys (§9) in inventory; not movement-blocked (§7); via `exit` action only — not `move` |

---

## §3 — Items and crafting

| Item | Obtained | Purpose |
|---|---|---|
| `brass_key` | Pick up in R0 | Opens R1–R2 door |
| `stick` | Pick up in R1 | Ingredient for `hammer` |
| `rock` | Pick up in R3 | Ingredient for `hammer` |
| `hammer` | `combine stick rock` | Opens R3–R4 door |
| `torch` | Pick up in R4 | Ingredient for `lit_torch` |
| `oil` | Pick up in R4 | Ingredient for `lit_torch` |
| `lit_torch` | `combine torch oil` | Required for Exit |
| `glyph_key` | `decode_glyph` in R2 | Required for R2–R6 door and Exit |
| `cursed_idol` | Pick up in R6 (optional) | **Trap item** — see §7 |
| `master_seal` | Pick up in R6 | Lifts the `sealed`-phase movement block (see §7) |
| `key_red` | Pick up in R1 | One of three colour keys required to Exit and win (§9) |
| `key_green` | Pick up in R3 | One of three colour keys required to Exit and win (§9) |
| `key_blue` | Pick up in R4 | One of three colour keys required to Exit and win (§9) |

`combine` ingredient order does not matter (`stick rock` = `rock stick`).

---

## §4 — Action vocabulary

The policy must handle exactly these action types:

| `type` | Extra fields | Allowed when |
|---|---|---|
| `look` | — | Always |
| `take` | `item` | `item` is in `available_items` |
| `combine` | `item1`, `item2` | Both items in inventory; a valid recipe exists |
| `use` | `item` | `item` is in inventory |
| `move` | `room` | Door requirement met (§2); not movement-blocked (§7); target ≠ R7 |
| `decode_glyph` | — | `current_room == "R2"` |
| `teleport` | `room` | In R6; not movement-blocked (§7); target is reachable (§8) |
| `exit` | — | In R5; not movement-blocked (§7); `lit_torch` + `glyph_key` (correct id) in inventory; **and all three colour keys** `key_red`, `key_green`, `key_blue` in inventory (§9) |

---

## §5 — Glyph decode (ImageMagick)

The Archive terminal uses a glyph image to derive the `glyph_key_id`. The four
glyph PNGs are at `/app/glyphs/glyph_0.png` through `glyph_3.png`. You can
inspect them with `identify` or via `GET /glyph/<index>`.

**Decode formula** (integer arithmetic):

```
glyph_key_id = (width // 8) % 16
```

where `width` is the pixel width of `glyph_<glyph_index>.png`.

**Glyph pixel widths by index:**

| `glyph_index` | width (px) |
|---|---|
| 0 | 112 |
| 1 | 144 |
| 2 | 192 |
| 3 | 160 |

The `glyph_key_id` in the game state must equal this computed integer. A
`glyph_key` with the wrong id is treated as if the key is absent — it does not
satisfy door requirements or the win condition. The held-out test cases use
all four `glyph_index` values; a hardcoded constant will fail.

**API shortcut:**
```
GET  /glyph/<index>          → {"index":0,"width":112,"height":112,"path":"..."}
POST /decode_glyph           body: {"glyph_index":0}   → {"glyph_key_id":14}
```

---

## §6 — Rules the policy must define (package `escape`)

### `default allow = false`
The policy must declare `default allow = false`. If no `allow` rule fires, the
result is `false`, not undefined.

### `allow` (complete rule)
`data.escape.allow` evaluates to `true` if and only if the action in `input.action`
is legal given the current state. Governs all action types in §4.

### `allowed_actions` (partial set)
`data.escape.allowed_actions` produces the **complete set** of all currently
legal actions as a set of objects (same shape as `input.action`). Every element
that would make `allow` true must appear; no extra elements.

### `reachable_rooms` (partial set)
`data.escape.reachable_rooms` produces the set of rooms the wormhole pad can
reach from `current_room` (see §8). Used internally by `allow` and
`allowed_actions` for teleport decisions. The current room itself is **never** a
member (you cannot teleport to where you already are).

### `win` (complete rule)
`data.escape.win` is `true` when the player has won (§9).

---

## §7 — Movement-blocking lattice (epoch phase + master_seal)

Whether **`move`, `teleport`, and `exit`** are blocked is decided by `epoch_phase`
together with two items. (`look`, `take`, `combine`, `use`, and `decode_glyph`
are **never** blocked by any of this.) `epoch_phase` is one of `"normal"`,
`"eclipse"`, or `"sealed"`:

- **`normal`** — movement is blocked **iff** `cursed_idol` is in inventory.
- **`eclipse`** — movement is **never** blocked; the eclipse lifts the
  `cursed_idol` curse entirely (even while you still hold the idol).
- **`sealed`** — movement is blocked **regardless of the idol**, **unless**
  `master_seal` is in inventory, which lifts the sealed block.

Equivalently, **movement is blocked exactly when**:

```
(epoch_phase == "normal" AND cursed_idol in inventory)
  OR
(epoch_phase == "sealed" AND master_seal NOT in inventory)
```

A blocked `move` / `teleport` / `exit` is denied no matter how well its other
requirements (doors, keys, reachability) are satisfied. In `"eclipse"`, and in
`"sealed"` while holding `master_seal`, the idol does **not** block anything.

---

## §8 — Wormhole / teleport reachability

The wormhole pad is in R6. `teleport <room>` is allowed when all of:

1. `current_room == "R6"`
2. Not movement-blocked (§7)
3. `room` is in `unlocked_rooms`
4. `room` is **transitively reachable** from `current_room` through the graph
   formed by: edges between rooms that are both in `unlocked_rooms` AND whose
   door requirement is currently satisfied (item in inventory / correct id).
5. `room != current_room` — you never teleport to the room you are already in,
   so the current room is excluded from `reachable_rooms` and from the teleport
   actions in `allowed_actions`.

Condition 4 requires a transitive-closure computation over the unlocked,
passable sub-graph — not just a membership check. A room can be in
`unlocked_rooms` but unreachable if the path to it is blocked (e.g. the door
requires a key the player does not currently hold).

---

## §9 — Win condition

`win` is `true` when **all** of the following hold simultaneously:

1. `current_room == "R7"`
2. `"hammer"` in `inventory`
3. `"lit_torch"` in `inventory`
4. `"glyph_key"` in `inventory`
5. `glyph_key_id == (glyph_width_for_glyph_index // 8) % 16`
6. **Every** colour key is in `inventory`: `key_red` **AND** `key_green` **AND** `key_blue`.

Requirement 6 is a *universal* condition — it holds only when **none** of the
three colour keys is missing. The same colour-key requirement also gates the
`exit` action (§4).

---

## §10 — Flask API reference

| Endpoint | Body | Returns |
|---|---|---|
| `GET /health` | — | `{"status":"ok"}` |
| `GET /glyph/<index>` | — | `{"index":N,"width":W,"height":H,"path":"..."}` |
| `POST /decode_glyph` | `{"glyph_index":N}` | `{"glyph_key_id":N}` |
| `POST /validate` | game state + `"action"` | `{"allow":true\|false}` |
| `POST /allowed_actions` | game state (no action) | `{"actions":[...]}` |
| `POST /check_win` | game state | `{"win":true\|false}` |

Game-world data: `/app/data/rooms.json`, `items.json`, `scenarios.json`.  
Schemas: `/app/schemas/state.schema.json`, `action.schema.json`.  
Rules reference: `/app/docs/RULES.md`, `GLYPH_DECODE.md`.
