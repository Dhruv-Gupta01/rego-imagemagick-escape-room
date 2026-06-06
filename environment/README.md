# Rego ImageMagick Escape Room — Environment

This directory is the Docker build context for the escape-room task.

## Quick start (local)

```bash
docker build --platform linux/amd64 -t ergo ./environment
docker run --rm -p 5000:5000 ergo
curl http://localhost:5000/health
```

## Directory layout

```
environment/
├── Dockerfile          # linux/amd64 image; installs OPA, ImageMagick, Flask
├── requirements.txt    # Flask stack — hash-pinned for pip --require-hashes
├── api/app.py          # Stateless Flask server; delegates decisions to OPA
├── data/               # Game-world JSON (rooms, items, doors, scenarios)
├── glyphs/             # generate_glyphs.sh + build-time PNG output
├── schemas/            # JSON Schema for game state, actions, policy outputs
├── docs/               # Rules, API reference, glyph decode, design notes
└── policy/             # Agent writes Rego here. Ships with only .keep.
```

## Key runtime paths (inside container)

| Path | Content |
|------|---------|
| `/app/policy/` | Agent's Rego policy (empty until agent/oracle writes it) |
| `/app/glyphs/glyph_N.png` | Deterministic PNG glyphs (generated at build time) |
| `/app/glyphs/glyph_meta.json` | Width/height index (generated at build time) |
| `/logs/verifier/reward.txt` | Written by `tests/test.sh` — 1 or 0 |

## OPA policy contract

The agent must write a Rego file under `/app/policy/` in package `escape`.
See `docs/RULES.md` and `instruction.md` (task root) for the full rulebook.

```bash
# Verify the policy parses
opa check /app/policy/

# Test a single query
echo '{"current_room":"R0","inventory":[],"unlocked_rooms":["R0"],
  "glyph_key_id":null,"epoch_phase":"normal","glyph_index":0,
  "available_items":["brass_key"],"action":{"type":"look"}}' \
| opa eval -d /app/policy -I 'data.escape.allow'
```
