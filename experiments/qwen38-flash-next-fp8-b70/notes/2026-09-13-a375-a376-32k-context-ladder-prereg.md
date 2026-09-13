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

## Amendment (07:30 UTC): host memory, not VRAM, bounds the placement

Three A375 launches failed on packet literals the context override had not moved (the launcher's
option tokens exported verbatim, the campaign literal behind the derived script's fail-closed
`--ack`, the supervisor's `--max-model-len` server-identity check; all fixed in the generators and
recorded in memory). The fourth loaded the model and was stopped by the supervisor's host-memory
guard: MemAvailable fell to 9.9 GB (floor 12 GB) while the 5.0 GiB max-count-8 placement pinned
its host copies (four ranks, ~20 GB against ~10 GB for the promoted placement). Both 32K arms and
the eight-user arm now carry the never-hit plus max-count-2 placement
(`data/20260913-q38-expert-host-placement-a315-census-5gib-mc2-per-rank.json`: 3.57 / 3.73 / 3.97 /
3.88 GiB per rank, at most 0.017% of census selections on the host), which frees 1.0-1.3 GiB of VRAM
per rank against the promoted placement and adds ~4.8 GB of pinned host memory; the guard's margin
is estimated at ~3 GB and the VRAM margin on rank 1 at ~0.2 GiB. If rank 1 cannot fit the 114-block
KV the server fails at KV allocation and the next step is a 112-block KV with a 32,640-token
capacity (a 32K prompt with a 128-token output no longer fits; the ladder would stop at 24K).

## Amendment 2 (07:55 UTC): the fifth A375 launch and the first A376 launch, re-run as A381/A382

The fifth A375 launch (07:25 UTC, max-count-2 placement) loaded the model and was stopped at 07:36:36
by the supervisor, not by memory pressure as such: the MTP0 lineage's supervisor (A336) floors
MemAvailable at 16,000,000 KiB while the MTP1 lineage's (A338, the certified exact-mode runs) floors it
at 12,000,000; the last sample before the stop read 15,947,688 KiB (the 5 GiB-per-rank placement pins
~4.8 GB more host memory than the promoted one). The MTP0 generator gains a `HOSTFLOOR:` option; the
32K MTP0 arm and the eight-user arm (A377, regenerated before its 07:46 launch) carry the 12 GB floor
that every certified MTP1 run already ran under. Nothing about the server changed.

A376 (07:41 UTC) exited within a second with an empty host log: the MTP1 generator's `MAXLEN:` option
had moved the derived script's context check to 33280 but not the launcher's own silent `grep -Fxq`
assertion on that line (still 4352), so `set -e` ended the launcher with rc 1 and no message. The
generator now rewrites that assertion too. The arms are regenerated as A381 (MTP0, port 19994) and A382
(MTP1 exact mode, port 19995), queued behind A380 with the five-minute gaps (chain-a381-a382).
