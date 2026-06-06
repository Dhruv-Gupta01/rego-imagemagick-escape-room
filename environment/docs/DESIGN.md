# Design Notes

## Why Rego?

Rego (Open Policy Agent) is a declarative, Datalog-style policy language. It is
genuinely unfamiliar to most developers because it inverts the usual control
flow: instead of writing code that checks conditions, you declare *what is true*
and let OPA evaluate it. Common failure modes for people new to Rego:

- Writing overlapping `complete` rules that conflict (OPA raises an error).
- Forgetting `default allow = false` and getting permissive-by-default policies.
- Using imperative loops instead of `graph.reachable` for transitive closure.
- Mis-constructing partial sets with `contains` vs `=` vs `[_]` notation.

## Three difficulty levers baked in

### Lever 1 — Partial sets (`allowed_actions`)
The policy must return the **set of all legal actions**, not a single boolean.
Rego's set-comprehension syntax is different from Python/JS and models
frequently produce "multiple complete rules" errors here.

### Lever 2 — Graph reachability (wormhole)
Teleport requires transitive reachability over *unlocked* rooms. Rego forbids
general recursion; the correct solution uses `graph.reachable`. Models that
write Python-style BFS loops get a parse error from OPA.

### Lever 3 — Deterministic precedence (cursed idol)
`cursed_idol` blocks doors; `eclipse` overrides the curse. This forces
`default allow = false` + explicit `deny`/negation + an exception-to-exception
chain — the exact pattern models hallucinate overlapping complete rules on.

## Glyph as anti-hardcode axis
The glyph decode formula (`(width // 8) % 16`) is fully stated, but the
`glyph_index` varies per test case (0, 1, 2, 3). A policy that hardcodes
`glyph_key_id = 14` passes index-0 tests and fails all others.

## Determinism guarantee
No real-time calls anywhere. `epoch_phase` is injected per scenario.
Glyph PNG dimensions are fixed at build time. OPA evaluation is pure.
The oracle is 100% deterministic across repeated runs.
