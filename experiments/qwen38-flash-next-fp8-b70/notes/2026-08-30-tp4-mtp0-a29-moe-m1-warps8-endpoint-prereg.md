# Qwen3.8 Flash-Next FP8 A29 production-M1 MoE endpoint preregistration

Date: 2026-08-30
Status: frozen before GPU launch

A29 is an additive endpoint test of the lossless production-M1 component win.
It derives from the last synchronous full-battery A27 path and changes the
isolated attempt/port/cache identities plus the tuned-config folder. The model,
runtime heads, PLE-only synchronous placement, graph/MTP/scheduler settings,
cache capacity, prompts, protected hashes, and complete client battery remain
unchanged.

The candidate map SHA-256 is
`91e5d8b692da3febbba7cb07ee4fdab319909da0c82c1fda95b92dc42d680464`.
Only key `1` uses `num_warps=8`; all other keys retain four warps.

A file-load log is insufficient. Immediately before `vllm serve`, A29 runs a
hash-bound resolver helper in the exact server environment. It must record
requested `M=1`, selected key `1`, effective `num_warps=8`, equality with
vLLM's official resolver, and the frozen fused-MoE/Triton-MoE source hashes.
The live server must then log the same M1 folder. The client and supervisor
reject a missing or inconsistent receipt, the old M4 folder, async PLE,
profiling, tracing, MTP, or source drift.

That prelaunch resolver is intentionally not live-inference evidence. A28's
trace establishes that production decode reaches M1, and the resolver proves
what the exact server environment selects for M1; engagement is therefore
strongly inferred rather than directly observed during A29 inference. Retain
that disclosure unless a later report-only arm captures a live selected-key
receipt without changing arithmetic or scheduling.

The arm is attempt `29`, port `19701`, and must be the boot's only full model
load. Promotion requires recovery canary, the inherited semantic suite,
16-repeat exactness, three protected short rows, cache-zero 4K needle, and two
exact-4K rows with the protected same-output hash. Any failure is a bounded
negative and changes no protected result. A pass is still a candidate endpoint
win. Because the projected effect is only about one percent and overlaps the
observed short-row spread, causal promotion requires a separately booted exact
config-unset control followed by a fresh candidate repeat, all using the same
client and battery. A29 alone cannot establish attribution or replace the
protected frontier.

## Prelaunch identity amendment

An independent prelaunch audit caught that the active kernel-source checkout
had advanced by one preserved, default-off component commit after A29 was
frozen. The staged runtime did not change. A29 is therefore refrozen with two
separate identities: `ad25aa9f...` remains the sealed kernel-overlay/source
identity, the loaded stage remains the hash-manifested `2f829747...` build,
and the clean source workspace must be the overlay's exact child
`359466a2...`. The child patch is hash-bound and remains disabled in A29.

The workspace parent, clean state, exported patch, 18-file staged-runtime
manifest, memory, swap, and NVMe gates are checked before the fresh-boot marker
is claimed. A hash-bound rewrite changes only the generated workspace check;
the sealed source and staged-build identities remain distinct and unchanged.
The workspace is checked again immediately before `vllm serve`. This amendment
changes no model, loaded library, selector, quality battery, performance
configuration, or interpretation.

Refrozen SHA-256 identities:

- launcher: `6a624362e1ae1d4c4522fbc6cd88c6ac9e7da0da7998390c28333927c3aec5b0`;
- client: `28e89555634fe22a06cf87d8bc15fbb69fe6230981ddaef34d9a7fe1476b6981`;
- supervisor: `bfb70ca1cdb74f5c7ec4bf462755c250cebbf71a828fd42d18b09c36e7c13bb0`;
- workspace-contract helper:
  `d16129b94e969a428f980af47b5dda952e72a960714d96dc662f90dee5aef65a`;
- generated inner launcher:
  `37791a9b20d0ce0d10e89f3930f9d0e8b7d7f743e1074691b39ed22a40e6adbb`.
