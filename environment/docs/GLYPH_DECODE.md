# Glyph Decode Reference

## Overview

The Archive (R2) contains a glyph terminal. When the player performs the
`decode_glyph` action there, a `glyph_key` item is granted with an integer id
derived from a glyph PNG image.

## Formula

```
glyph_key_id = (width // 8) % 16
```

`width` is the pixel width of `/app/glyphs/glyph_<glyph_index>.png`.  
`glyph_index` is an integer (0–3) injected per scenario via `game_state.glyph_index`.

## Lookup via API

```
GET /glyph/<glyph_index>
→ { "index": 0, "width": 112, "height": 112, "path": "/app/glyphs/glyph_0.png" }
```

```
POST /decode_glyph   body: { "glyph_index": 0 }
→ { "glyph_index": 0, "width": 112, "glyph_key_id": 14 }
```

## Lookup via ImageMagick

```bash
identify -format "%w %h" /app/glyphs/glyph_0.png
# → 112 112
python3 -c "print((112 // 8) % 16)"
# → 14
```

## Glyph table

| glyph_index | width (px) | glyph_key_id |
|-------------|-----------|--------------|
| 0           | 112       | 14           |
| 1           | 144       |  2           |
| 2           | 192       |  8           |
| 3           | 160       |  4           |

## Policy requirement

The Rego policy must implement this formula. Door rules for R2–R6 and the
Exit (R5→R7) validate that `input.glyph_key_id == (glyph_widths[input.glyph_index] / 8) % 16`.
A hard-coded constant will fail held-out cases that use different `glyph_index` values.
