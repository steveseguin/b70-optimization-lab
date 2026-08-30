# Qwen3.8 Flash-Next FP8 TP4 MTP0 QSA-stable A15 preregistration

Date: 2026-08-30
Status: frozen recovery replica after pre-inference A14 interruption

A15 repeats the exact A14 fresh-server reliability contract under a new,
non-overlapping lifecycle identity. A14 produced no model result, so this is not
an unchanged retry of a model failure and introduces no treatment change.

The model revision, vLLM `f68c9386f`, kernel and staged runtime, TP4/EP4 eager
MTP0 topology, 51.200-GB PLE-only host placement, input embedding in VRAM,
128-MiB cache, 4,352-token capacity, prompts, seeds, quality battery, and short
and exact-4K authority hashes remain identical. Only attempt 15, port 19687,
state/RPC/compile/cache, and evidence paths change.

Frozen wrappers and generated sources:

- launcher `a9689bef...2dfa`, intermediate `f8d01f97...1339`, final base
  `6c98434d...b753`;
- client `14c8e29c...574f`, intermediate `4ff5d6df...6d2e`, final source
  `d1edfad9...8c40`;
- supervisor `9bcfcb3e...1da8`, intermediate `86c63e1d...df70`, final source
  `613f0813...d825`.

The full A13/A14 gate and interpretation remain frozen. All three short rows
must equal `5f407446...f89f0`; both p4096/o128 rows must equal
`1d833e5f...39d5cc` with zero cached tokens. Any semantic, repeat, output,
lifecycle, or B70 postflight failure rejects promotion. Timing cannot lower or
replace any protected result. A full pass completes the bounded two-server
reliability/losslessness contract for deterministic XPU QSA plus PLE-only
placement.

No MTP, graph, cache, context, MoE, website, or submission change is authorized
inside A15. The packet must be committed and pushed before GPU launch.
