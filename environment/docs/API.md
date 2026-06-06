# Escape Room API Reference

The Flask server runs on `http://localhost:5000`.  
All `POST` bodies are JSON; all responses are JSON.

---

## GET /health

Liveness check.

```json
{ "status": "ok", "policy_dir": "/app/policy" }
```

---

## GET /glyph/<index>

Returns ImageMagick-derived pixel dimensions for glyph image `index` (0–3).

```
GET /glyph/0
```

```json
{ "index": 0, "width": 112, "height": 112, "path": "/app/glyphs/glyph_0.png" }
```

The agent can also run `identify -format "%w %h" /app/glyphs/glyph_N.png` directly.

---

## POST /decode_glyph

Computes the integer `glyph_key_id` for the given `glyph_index`.

**Formula:** `glyph_key_id = (width // 8) % 16`

```json
{ "glyph_index": 0 }
```

```json
{ "glyph_index": 0, "width": 112, "glyph_key_id": 14 }
```

---

## POST /validate

Evaluates `data.escape.allow` for the provided game state + action.

**Body:** full game state (see `schemas/state.schema.json`) with an `"action"` field.

```json
{
  "current_room": "R0",
  "inventory": [],
  "unlocked_rooms": ["R0"],
  "glyph_key_id": null,
  "epoch_phase": "normal",
  "glyph_index": 0,
  "available_items": ["brass_key"],
  "action": { "type": "take", "item": "brass_key" }
}
```

```json
{ "allow": true }
```

---

## POST /allowed_actions

Evaluates `data.escape.allowed_actions` — the full set of currently legal actions.

**Body:** game state without an `"action"` field (or with `"action": null`).

```json
{ "actions": [
    { "type": "look" },
    { "type": "take", "item": "brass_key" },
    { "type": "move", "room": "R1" }
]}
```

---

## POST /check_win

Evaluates `data.escape.win`.

**Body:** game state (no action needed).

```json
{ "win": false }
```
