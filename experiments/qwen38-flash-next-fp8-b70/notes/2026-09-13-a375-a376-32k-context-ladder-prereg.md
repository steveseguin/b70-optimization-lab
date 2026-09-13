# Preregistration: A375/A376 - the 32K context cell on the exact-serial-GDN line

## Question

The Flash-Next lines are certified at a served context of 4,352 tokens (KV `376569856` bytes,
"32 blocks", a determinism choice, not a memory limit). The front page's "32K input" cell is
empty. Does the promoted MTP1 exact-mode line stay lossless and how fast is it at 8K, 16K and
32K input depth, with the served capacity raised to 33,280 tokens?

## Arms

- A375: promoted MTP0 line (overlay `2a372e86`, served stage), `MAX_MODEL_LEN=33280`,
  `KV_CACHE_MEMORY_BYTES=1365065728` (116 pool blocks; ~33.6K tokens of KV), everything else the
  A336 packet; depth ladder 2K/8K/16K/32K, two rows each, port 19988.
- A376: promoted MTP1 exact-mode line (overlay `6d872457`, stage v2, the four exact-mode
  exports), same capacity and KV, same ladder, port 19989.
- Generators: the A336/A338 diag generators with the new `MAXLEN:`/`KVBYTES:` options (the
  derived script's frozen-context check and the campaign directory name follow the capacity);
  driver `tools/q38-depth-ladder-driver.sh` (bounded 1,800 s per request; 32K prefill runs in
  64-token batches).

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
