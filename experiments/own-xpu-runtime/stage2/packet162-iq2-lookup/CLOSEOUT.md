# Packet162 — grid dependency CPU study closeout

<!-- campaign-closeout -->

## Question and identity

On October 19, 2026, can an exact gate/up decoder remove the dependent IQ2
grid stage from the bundle8 two-card quantized compressed UD-IQ3_XXS lane?
Control: selected E1 source in packet136, `iq3-p49-split32-v1`, K2560,
640 rows × ten experts × two streams, V8/WG64/SG32, full BF16 KV/state.
Research ran on steve-b70s CPU only; no weights, GPU or services were used.
The user bounded this packet to sixty minutes.

## Outcome

**Close the current Boolean and enumerative implementations; no device arm
or build brief qualifies.** Integer grid decoding is exhaustive and exact;
both native host kernels match all final output/status bytes tested, including
invalid routes. Finite raw chains also agree. Independent NaN chain/tree
comparisons differ, so the complete strict CPU gate remains false. Device
speed is unmeasured. No lossless model-speed or lossy-model-output claim follows.
No READY or ops proposal was created and nothing was queued.

## What worked

The source count establishes one dependent d32x2 grid message per eight
weights, not two serial loads per weight. Signs are inline and E1 is already
present. A new **11-bit enumerative supergrid** represents all 1,024 original
grid entries exactly, removes the indexed grid read at source level and needs
only 40 extra bytes per row. Its 629,145,600-byte per-rank growth fits the
steady-state bundle8 arena, with 157,123,878 bytes left on rank 1. This useful
encoding result is retained even though its present decoder is not qualified.

## What failed or remains uncertain

The unchanged-layout Boolean circuit requires 1,288 shared nodes. The smaller
enumerative decoder still has count selection, unranking, scatter and extra
metadata work; finite CPU timing is about 4.1–4.9× control. CPU timings are
diagnostics and do not establish a device regression. Neither design has a
supported ≤0.85 device-time forecast or measurement.

GNU's auxiliary enumerative reduction differs in 2,114 BF16 NaN words;
Intel's auxiliary chains differ in 70,383 FP32 NaN words for each candidate.
The actual native host operation's tested final bytes agree. The distinction
is preserved: the failing instrumentation/call-site context is not a proven
native output regression, and final bytes do not waive raw-chain parity.
Compiler lowering, device exactness, deterministic repeats, actual loader
peak allocation and model transfer remain untested. The final arena margin
cannot accommodate arbitrary old-plus-new complete-bank staging.

## Evidence and patches

[Analysis/source pins](evidence/analysis.json), [compiler commands, dependency
pins and all final comparisons](evidence/cpu-proof.json),
[fail-closed decision](evidence/decision.json), [audit tests](evidence/audit-tests.log).
[analyze.py](analyze.py) generates [L0](candidate.hpp), [L1](enum_candidate.hpp)
and their integer decoders from frozen production source. Earlier short logs
remain under `evidence/logic-attempt1/` and `evidence/attempt2/`; the final
receipt is the replay authority. [Retention](RETENTION.md),
[full-shape CPU harness](CPU-MICRO.md),
[conditional device micro specification](DEVICE-MICRO-PROPOSAL.md).

## When to revisit

A materially shorter exact decoder for the retained 11-bit representation,
with a pinned explanation/fix for all raw-chain and NaN-byte differences and
a real peak-allocation plan. It must pass every CPU byte gate and then the
specified lane-B single-card ≤0.85 device micro gate before a build brief.
Do not reopen the excluded relocation, compaction, prefetch, batching,
tile16, persistent/V16, E1 or N2-cell levers under a new name. This packet's
closure does not close the model lane or assert that lookup removal is impossible.
