# Preregistration: A375/A376 - the 32K context cell on the exact-serial-GDN line

## Question

The Flash-Next lines are certified at a served context of 4,352 tokens (KV `376569856` bytes,
"32 blocks", a determinism choice, not a memory limit). The front page's "32K input" cell is
empty. Does the promoted MTP1 exact-mode line stay lossless and how fast is it at 8K, 16K and
32K input depth, with the served capacity raised to 33,280 tokens?

## Arms

- A375: promoted MTP0 line (overlay `2a372e86`, served stage), `MAX_MODEL_LEN=33280`,
  `KV_CACHE_MEMORY_BYTES=1341530112` (114 pool blocks; ~33.1K tokens of KV), expert host placement
  widened to 5.0 GiB per rank (`data/20260913-q38-expert-host-placement-a315-census-5gib-mc8-per-rank.json`,
  built from this lineage's A315 routing census with pairs selected at most 8 times parked: 0.06-0.39% of
  census selections would hit the host; placement is bit-exact by construction), everything else the A336 packet; depth ladder 2K/8K/16K/32K, two rows each, port 19988.
- A376: promoted MTP1 exact-mode line (overlay `6d872457`, stage v2, the four exact-mode
  exports), same capacity and KV, same ladder, port 19989.
- Generators: the A336/A338 diag generators with the new `MAXLEN:`/`KVBYTES:` options (the
  derived script's frozen-context check and the campaign directory name follow the capacity);
  driver `tools/q38-depth-ladder-driver.sh` (bounded 1,800 s per request; 32K prefill runs in
  64-token batches).

## Why the placement widens

A VRAM probe on the served line (A369, healthy) found 0.11-0.35 GiB free per card: the
4352-token KV is not a determinism choice alone, the cards are full. A 33K KV needs ~0.97 GiB
more per rank; the A315 census shows 772-850 never-selected experts per rank (3.5-3.9 GiB) against
the 543-587 the 2026-09-06 placement parks, and parking pairs hit at most 8 times fills a 5.0 GiB
budget with under 0.4% of census selections crossing PCIe. Both arms carry the widened placement.

## Gates

- Lossless: at every depth, A376 r1 == r2 and A376 == A375 (the MTP1 line must reproduce the
  MTP0 line's output ids, the lineage's definition of lossless). At 2K and 4K the ids must equal
  the certified pins where the depth exists on the ladder (2K: `afffd211…`).
- Speed: reported per depth (99-interval tok/s after TTFT) and TTFT; no threshold.

## Predictions

Decode rate falls slowly with depth (the QSA sparse attention bounds the attention cost; the
GDN state is fixed-size), so 32K should stay within ~15% of the 2K row on both lines; TTFT at
32K is minutes (prefill in 64-token batches). If the ids hold at every depth, the line earns a
"32K input" cell and a long-context suite candidate; if a depth diverges between MTP0 and
MTP1, MTP1 is not lossless past that depth on this line and the cell is published MTP0-only.

## Stop rules

Server fails health (KV/capacity change); any depth row fails; the pair diverges.
