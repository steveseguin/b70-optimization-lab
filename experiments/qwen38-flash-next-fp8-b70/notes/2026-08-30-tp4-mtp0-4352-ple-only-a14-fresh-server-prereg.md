# Qwen3.8 Flash-Next FP8 TP4 MTP0 QSA-stable A14 preregistration

Date: 2026-08-30
Status: frozen fresh-server reliability replica; no GPU work yet

## Objective

Start one independent server with the exact passing A13 model, source treatment,
staged native runtime, PLE-only placement, cache, prompts, and complete gate.
A14 is the required second-server reliability/losslessness check. It introduces
no new optimization and does not tune against A13 timing.

## Frozen identity and only changes

A14 retains model revision `bcd9f01d...ddce`, vLLM
`f68c9386fe5af54055bdf20684b269b9c1340e44`, kernel source `ad25aa9f69`,
staged build `2f82974750`, TP4/EP4, graph-off eager MTP0, one sequence, 4,352
maximum tokens, 64 scheduled tokens, and the 128-MiB cache. The exact
51.200-GB PLE table is the sole host/UVA parameter; input embedding remains in
VRAM. Prefix caching and async scheduling remain disabled.

Only lifecycle identity changes: attempt 14, port 19686, A14 state/RPC/compile
paths, and new raw-evidence roots. The frozen wrappers and their generated
sources are checksum-bound:

- launcher `de10733d...c5ee`, intermediate `2020d843...db3b`, final base
  `0c6e4c11...e4cb`;
- client `2ea92230...b8b6`, intermediate `772a0fbf...3939`, final source
  `5fcdde53...c24b`;
- supervisor `f67349ed...fadd`, intermediate `ee4c46d4...1559`, final source
  `769ea881...98d2`.

## Required gates and frozen interpretation

Repeat recovery, the seven-case semantic battery, 16 fixed short repeats,
exact cache-zero 4K needle, three p146/o256 timing rows, two byte-identical
p4096/o128 rows, and owned four-card teardown. All short rows must equal
`5f407446...f89f0`; both exact-4K rows must equal
`1d833e5f...39d5cc`; cached tokens must remain zero.

- A full pass establishes the deterministic QSA treatment plus PLE-only
  placement as the reliable/lossless TP4 eager MTP0 optimization base under the
  bounded two-server contract. Preserve A13 and A14 as separate runs and report
  both rather than overwriting either.
- Any output, semantic, repeat, lifecycle, or B70 postflight failure rejects
  promotion. A timing regression never lowers A9, A13, or an older captured
  result and must be interpreted before further tuning.
- Corrected events limited to local NVMe remain a disclosed host caveat. Any
  B70-addressed event fails postflight.

No MTP, graph, alternate cache, deeper context, MoE tuning, website update, or
LocalMaxxing action is authorized inside A14. The packet must be committed and
pushed on `main` before launch.
