# Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│  Docker container (linux/amd64)                             │
│                                                             │
│  ┌──────────────┐   POST /validate    ┌──────────────────┐ │
│  │  Test suite  │ ──────────────────► │  Flask API       │ │
│  │  (pytest)    │   POST /allowed_    │  /app/api/app.py │ │
│  │  /tests/     │   actions etc.      │  :5000           │ │
│  └──────────────┘                     └────────┬─────────┘ │
│                                                │            │
│                                    opa eval -d /app/policy  │
│                                                │            │
│                                       ┌────────▼─────────┐ │
│                                       │  OPA evaluates   │ │
│                                       │  agent's Rego    │ │
│                                       │  /app/policy/    │ │
│                                       └──────────────────┘ │
│                                                             │
│  /app/glyphs/glyph_{0..3}.png  ← generated at build time   │
│  /app/glyphs/glyph_meta.json   ← width/height index        │
└─────────────────────────────────────────────────────────────┘
```

## Key paths

| Path | Content |
|------|---------|
| `/app/policy/` | Agent writes Rego here. Starts empty (`.keep` only). |
| `/app/api/app.py` | Flask server. Calls OPA for every decision. |
| `/app/data/` | Game world JSON (rooms, items, scenarios). |
| `/app/glyphs/` | Generated PNG glyphs + metadata JSON. |
| `/app/schemas/` | JSON Schema for game state and policy outputs. |
| `/app/docs/` | Human-readable rules and API reference. |
| `/logs/verifier/` | `reward.txt` and `ctrf.json` written by `test.sh`. |

## OPA call pattern

```bash
echo '<game_state_json>' | opa eval -d /app/policy -I --format json 'data.escape.allow'
```

The policy package must be `escape`. Required rules: `allow`, `allowed_actions`,
`reachable_rooms`, `win`. See `instruction.md` for the full specification.
