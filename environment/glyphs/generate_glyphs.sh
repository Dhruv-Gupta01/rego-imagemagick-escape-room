#!/usr/bin/env bash
# Runs at docker build time. Generates 4 deterministic glyph PNGs and a
# metadata JSON the Flask API reads at startup.
#
# Glyph decode formula (stated in instruction.md):
#   glyph_key_id = (width // 8) % 16
#
# Index | Width | Height | Colour  | Computed id
#   0   |  112  |   112  | navy    |  14
#   1   |  144  |   144  | darkgreen|   2
#   2   |  192  |   192  | maroon  |   8
#   3   |  160  |   160  | purple  |   4

set -euo pipefail

GLYPHS_DIR="/app/glyphs"
mkdir -p "$GLYPHS_DIR"

declare -a WIDTHS=(112 144 192 160)
declare -a HEIGHTS=(112 144 192 160)
declare -a COLOURS=(navy darkgreen maroon purple)

for i in 0 1 2 3; do
    # Solid-colour canvas only — no text annotation so no font dependency.
    # The decode reads pixel width via `identify`; the fill colour is cosmetic.
    convert \
        -size "${WIDTHS[$i]}x${HEIGHTS[$i]}" \
        "xc:${COLOURS[$i]}" \
        "${GLYPHS_DIR}/glyph_${i}.png"
done

# Write glyph_meta.json so the Flask API (and agents using the API) can query
# glyph dimensions without needing ImageMagick installed.
python3 - <<'PYEOF'
import json, subprocess, pathlib

glyphs_dir = pathlib.Path("/app/glyphs")
meta = {}
for i in range(4):
    out = subprocess.check_output(
        ["identify", "-format", "%w %h", str(glyphs_dir / f"glyph_{i}.png")]
    ).decode().strip()
    w, h = map(int, out.split())
    meta[str(i)] = {"width": w, "height": h, "path": f"/app/glyphs/glyph_{i}.png"}

(glyphs_dir / "glyph_meta.json").write_text(json.dumps(meta, indent=2))
print("glyph_meta.json written:", json.dumps(meta))
PYEOF
