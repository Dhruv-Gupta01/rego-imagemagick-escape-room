# Escape Room — Rules Reference

Human-readable copy of the complete rulebook.  
(Authoritative version: `instruction.md` at the task root.)

---

## Rooms

| ID | Name         | Notes |
|----|--------------|-------|
| R0 | Atrium       | Start room |
| R1 | Gallery      | — |
| R2 | Archive      | Contains the glyph terminal (`decode_glyph` action) |
| R3 | Workshop     | Crafting room |
| R4 | Conservatory | — |
| R5 | Antechamber  | Last room before Exit |
| R6 | Mirror Hall  | Contains the wormhole pad (`teleport` action) |
| R7 | Exit         | Win room |

---

## Doors (undirected unless noted)

| Edge  | Requirement |
|-------|-------------|
| R0–R1 | none |
| R1–R2 | `brass_key` in inventory |
| R1–R3 | none |
| R3–R4 | `hammer` in inventory |
| R2–R6 | `glyph_key` in inventory AND `glyph_key_id` equals the computed id |
| R4–R6 | none |
| R6–R5 | none |
| R5→R7 | `lit_torch` AND `glyph_key` (correct id) AND player NOT holding `cursed_idol` (unless eclipse) |

---

## Items and Recipes

| Item | Source | Use |
|------|--------|-----|
| `brass_key`   | R0 (pick up)          | Opens R1–R2 |
| `stick`       | R1 (pick up)          | Ingredient → `hammer` |
| `rock`        | R3 (pick up)          | Ingredient → `hammer` |
| `hammer`      | `combine stick rock`  | Opens R3–R4 |
| `torch`       | R4 (pick up)          | Ingredient → `lit_torch` |
| `oil`         | R4 (pick up)          | Ingredient → `lit_torch` |
| `lit_torch`   | `combine torch oil`   | Required for Exit |
| `glyph_key`   | `decode_glyph` in R2  | Required for R2–R6 and Exit |
| `cursed_idol` | R6 (optional — trap)  | Blocks all doors and exit |

---

## Glyph Decode

1. Inspect glyph image at `/app/glyphs/glyph_<glyph_index>.png` using `identify` or `GET /glyph/<glyph_index>`.
2. Compute: **`glyph_key_id = (width // 8) % 16`** (integer arithmetic).
3. Grant `glyph_key` to the player's inventory and record this integer as `glyph_key_id` in the game state.
4. Door and exit rules validate that `glyph_key_id` equals the scenario's expected value.

---

## Cursed Idol Override

- **Base:** holding `cursed_idol` → ALL `move`, `teleport`, and `exit` actions **DENIED**.
- **Exception:** if `epoch_phase == "eclipse"` → curse is lifted; doors and exit work normally.
- **Precedence:** `eclipse` exception beats the curse; curse beats normal key possession.

---

## Wormhole / Teleport

- Only available from **R6** (Mirror Hall).
- Target must be in `unlocked_rooms` (rooms the player has previously entered).
- Target must be **transitively reachable** from `current_room` through the graph of unlocked rooms and currently-passable door edges.
- Teleport to an unreachable or not-yet-unlocked room is **denied**.

---

## Win Condition

Player wins when **all** of the following hold:
1. `current_room == "R7"`
2. `hammer` in inventory
3. `lit_torch` in inventory
4. `glyph_key` in inventory
5. `glyph_key_id` equals `(glyph_width // 8) % 16` for the scenario's `glyph_index`
