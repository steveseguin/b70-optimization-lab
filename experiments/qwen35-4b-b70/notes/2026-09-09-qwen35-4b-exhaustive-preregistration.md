# Qwen3.5-4B W4A16 exhaustive campaign — preregistration (2026-09-09)

Preregistered before launch per AGENTS.md "Diagnosis And Campaign Speed Rules"
rule 4. One runner owns preflight, every server stage, the comparisons, health
postflights and abort rules. Scope for this campaign is **in-repository evidence
only**: no package updates, no catalog rebuild, no LocalMaxxing submission.

## What prompted it

Re-reading the 2026-09-07 `v1`/`t1` ladders showed something the depth-sweep
write-up did not cover. The MTP0 (no-speculation) ladder is exact at every rung
through c32 in all four passes across both TP configs, while the MTP3 ladder
breaks at c32 in all four. So the c32+ identity break in the published matrix is
**speculation-driven, not a W4A16 kernel property** — the row-invariance claim
survives.

But the three MTP0 c64 flips are not benign near-ties, which is what the lane has
assumed for every previous flip:

| prompt | pass | similarity | alignment |
|---|---|---|---|
| `benchmark-c043` | TP2 c64 rep1 | 0.992 | **one phantom token inserted at index 124**, remainder identical |
| `capacity-c022` | TP2 c64 rep1 | 0.734 | **four tokens deleted at index 17**, then progressive drift |
| `rollback-c034` | TP1 c64 rep2 | 0.117 | content divergence from index 5 |

The inserted-token signature is the one AGENTS.md documents for the MTP
first-token phantom. Its appearance with **speculation off** is new and is the
central question of this campaign.

## Questions, in priority order

1. **F1 — rate and classification.** At c32/c64, how often does an MTP0 request
   diverge, and in what proportion insertion / deletion / content divergence?
   n=4 passes is not a rate. Preregistered: 20 repeats.
2. **F2 — is it the capture path?** Same rungs with `GRAPH=0` (piecewise
   Inductor, XPU graph disabled). If flips vanish, the decode-only graph capture
   is implicated; if they persist at the same rate, it is not.
3. **T3 — TP2 strict replication.** The published TP2 pair is 240.615 / 227.533
   tok/s, a 5.7% spread against this host's ~3% back-to-back drift bound. Two
   more strict passes before that number is usable.
4. **F3 — the speculation crossover.** MTP3 beats MTP0 at c1 (159 vs 102) and
   loses at c32 (1032/1147 vs 1596/1594). Locate the crossing at
   c8/12/16/20/24/32, 6 repeats. Existing c16 passes disagree 937 vs 1090, so
   that rung specifically needs samples.
5. **T4 — TP2 long context.** The 2K-32K real-content depth ladder has only ever
   run on TP1.
6. **F4 — beyond c64.** Raise `CAPTURE_SIZES`/`CAPTURE_MAX` to 128 together (an
   uncaptured decode shape falls back to eager and would confound the ladder)
   and run c64/96/128.

## Gates and abort rules

- Every stage keeps the engine's existing preflight, per-stage postflight,
  `xpu-smi` device-state check, kernel-journal fault scan and compute/XCCL
  health check. Rule 5 fast-fail is inherited from the engine.
- The wrapper stops the whole chain when an arm aborts for a **hardware** reason
  (device not normal, journal fault signature, health failure, container left
  running). It continues to the next arm when an arm aborts on a **gate**
  (G1 not 12/12), because a gate failure is a result.
- Identity is recorded, never used to stop a stage: `--require-output-identity`
  makes the ladder harness exit non-zero and the engine logs that exit code.
- No speed verdict from one server (rule 3). Speed is recorded at every rung and
  compared only across arms with matched passes.

## Fixed identity

- model `/home/steve/llm-models/qwen35-4b-w4a16`,
  `RedHatAI/Qwen3.5-4B-quantized.w4a16` rev `7a613872`
- image R276 `sha256:521eb277c0733f8c2ce47aea1bb98ed576c6f1ad63bf5baf22d38fc07abf54ad`
- depth 3 (`qwen3_5_mtp`) where speculation is on, draft-only INT4 lm_head on,
  determinism pad off (measured inert at MTP0 below 128 rows)
- ladder suite `experiments/qwen38-27b-b70/data/2026-08-25-qwen38-q4km-tp2-http-smallctx-suite.json`,
  128 tokens, seed 42, `temperature 0`, `ignore_eos`
- strict suite `repro/qwen36-27b-autoround-int4-b70/realistic-suite-v1.json`

Runner: `experiments/qwen35-4b-b70/scripts/run-20260909-qwen35-4b-exhaustive-chain.sh`
