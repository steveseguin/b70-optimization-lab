# Qwen3.8 Flash-Next FP8 A78 fresh-server repeat preregistration

Date: 2026-09-03
Status: frozen before launch

## Question

A73 passed the whole frozen client at 4352 served tokens with exact-2K
`afffd211...` and exact-4K `c6193cc6...` rows. Does an independently started
server of the byte-identical packet reproduce every output and pass the same
gates, giving the 4352-token deterministic graph line a two-server frozen
client record (the A70/A71 pattern)?

## Design

`tools/rewrite-q38-a73-to-a78-fresh-repeat.py` renames the frozen A73 packet
to attempt 78 / port 19750 (fresh run, cache, compile, state paths) and
changes nothing else; the derived server hash is recomputed for the renamed
paths. Packet: launcher `736b5b92...`, client `38e0388c...`, supervisor
`8a2b6326...`, host wrapper `7444be0b...`. Launched behind a dropped page
cache after a read-only verification of the local NVMe model copy (which
does not touch the served USB copy).

## Reading

- Same outputs and hashes as A73 on every gate, receipt present: the
  4352-token deterministic line is promotable; its short center is the
  median of the A73/A78 short medians, exact-2K and exact-4K rows are
  reported as the four-row spans.
- Any output difference: the line is not server-independent at 4352 after
  all; investigate before promotion.
