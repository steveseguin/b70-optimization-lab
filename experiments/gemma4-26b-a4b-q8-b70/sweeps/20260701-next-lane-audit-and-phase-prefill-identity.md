# 2026-07-01 - Next-Lane Audit and Phase-Prefill Identity Hardening

Status: documentation + harness identity fix. No LocalMaxxing submission is
implied.

## Current Objective

Continue Gemma 4 26B A4B IT Q8/INT8-quality optimization on the B70 box:

- preserve the `UD-Q8_K_XL` target/verifier quality lane;
- use Q4_0 MTP draft/speculation only when accepted tokens are verified by the
  declared target model;
- promote only fixed realistic-suite cold responses with `cached_tokens=0`;
- keep service/prefill and long-context improvements separate from the
  short-decode LocalMaxxing headline unless they beat the same strict gate.

Current valid one-B70 short-decode record remains:

- `123.67689864739785 tok/s` median generated-token throughput for tokens
  1-100 after TTFT;
- evidence:
  `data/gemma4-q8-gpu0-finalpostnorm-on-full512-20260630T024027Z-finalpost-full512/summary.json`;
- LocalMaxxing ID: `cmr01nnet000mld01x2tt6qds`;
- config: llama.cpp `c926ad098`, `UD-Q8_K_XL` target, Q4_0 MTP draft, VDR2
  selected-down fused weighted-sum, FA-on, 32K/VMM, `n_max=3`, `n_min=2`,
  `p_min=0.0475`, `UBATCH_SIZE=1024`,
  `LLAMA_SYCL_F16_P021_SMALL_NCOLS=1`,
  `LLAMA_SPEC_VERIFY_BULK_SAMPLED_IDS=1`,
  `LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM_REORDER_VDR2=1`, and
  `LLAMA_GEMMA4_FUSED_FINAL_POST_NORM_RESIDUAL=1`.

## Short-Decode Audit

The easy short-decode lanes are exhausted for now:

- repeated current-record runs are valid but variance/no-new-record;
- `BATCH_SIZE=1152` / `UBATCH_SIZE=1152` did not repeat after final-postnorm;
- packed `GATEUP_GEGLU_EPILOGUE` (`1` and `all`) already closed negative;
- no-bonus row, staged MTP3, late-head bonus, prefix-tail, sampler clone/ID
  cleanup, handoff-copy lanes, DFlash PR 22105, rowpack, route-cache, and
  related MoE-ID variants are already recorded as negative or diagnostic-only;
- the `LLAMA_SPEC_VERIFY_ACCEPT_PREFIX_ARGMAX=1` prototype was semantically
  valid but slower because the row-by-row kernel/reduction design gave up the
  efficient current multi-row Q8 LM-head shape.

The credible next short-decode mechanism is still verifier cost reduction, but
it is not a quick flag tweak. A useful v2 needs a bonus-preserving accept-prefix
verifier LM-head implementation that avoids per-row launches, likely via a new
single/global row scheduler or equivalent backend boundary. It must preserve:

1. exact target top-1 on the first rejecting row;
2. the bonus row when all draft rows match;
3. existing target KV / rollback / sampler semantics;
4. strict parity mode before any performance claim.

Until that source work is being implemented, additional short-decode config
roulette is unlikely to beat the `123.6769 tok/s` headline reliably.

## Service / Prefill Audit

The practical active service lane is long-context prompt processing:

- `GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8` is a valid long-context prefill win for
  Gemma's DV512/GQA8 FlashAttention shape;
- `BATCH_SIZE=2048`, `UBATCH_SIZE=2048` is the current balanced service
  candidate;
- the default-off phase-specific prefill patch can keep decode at
  `UBATCH_SIZE=1024` while using `LLAMA_PREFILL_UBATCH_SIZE=2048` for prompt
  chunks, preserving the short-record-friendly decode shape during service
  experiments.

Best preserved phase-prefill service candidate:

```bash
BATCH_SIZE=2048
UBATCH_SIZE=1024
LLAMA_PREFILL_UBATCH_SIZE=2048
GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8
```

Known evidence:

- phase-prefill v2 long-context screen:
  `data/gemma4-long-context-service-gate-20260630Tprefill-ubatch-phase-v2-candidateA.json`;
- paired short guard:
  `data/gemma4-short-decode-guard-20260630Tprefill-ubatch-phase-v2-short-candidateA.json`;
- patch artifact:
  `patches/gemma4-26b-a4b-q8-b70/20260630-llama-phase-prefill-ubatch-memory-sized-experiment.patch`.

This remains a service/prefill recipe, not a short LocalMaxxing record. Promote
only if a future short fixed-suite gate beats the current headline.

## Identity Hardening

Gap found: phase-prefill wrappers export `LLAMA_PREFILL_UBATCH_SIZE`, but the
lower-level launcher identity did not record it durably enough for later
artifact comparison.

Fix made in this repo:

- `scripts/run-gemma4-26b-llamacpp-replica.sh` now logs
  `prefill_ubatch_size=<value-or-unset>` in the server header;
- `scripts/run-gemma4-26b-first-baseline.sh` now records
  `launcher_identity.prefill_ubatch_size` in `summary.json`, reading either the
  inherited environment or the server-log header.

This is a reproducibility-only change. It should not alter runtime behavior,
because it does not force an empty `LLAMA_PREFILL_UBATCH_SIZE` into the server
environment.

## Validation

Fresh four-GPU phase-prefill identity validation:

```bash
cd /home/steve/qwen36-results-main
STAMP=20260701T023112Z-phaseprefill-identity \
READINESS_TIMEOUT_S=900 \
repro/gemma4-26b-a4b-q8-b70/run-vdr2-gqa8-phase-prefill-service.sh
```

Aggregate:

- `data/gemma4-long-context-service-gate-20260701T023112Z-phaseprefill-identity.json`

Lane summaries:

- `data/gemma4-q8-gpu0-longctx-phase2048-ub1024-a-ctx32768-o96-20260701T023112Z-phaseprefill-identity/summary.json`
- `data/gemma4-q8-gpu1-longctx-phase2048-ub1024-b-ctx32768-o96-20260701T023112Z-phaseprefill-identity/summary.json`
- `data/gemma4-q8-gpu2-longctx-phase2048-ub1024-c-ctx32768-o96-20260701T023112Z-phaseprefill-identity/summary.json`
- `data/gemma4-q8-gpu3-longctx-phase2048-ub1024-d-ctx32768-o96-20260701T023112Z-phaseprefill-identity/summary.json`

Server logs are outside Git under:

- `/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/*20260701T023112Z-phaseprefill-identity.server.log`

Result:

- all 4 lanes passed the long-context gate;
- all aggregate rows had `cached_tokens_all_zero=true`;
- all canaries passed (`8` rows per lane);
- aggregate median prefill average: `1051.794789819953 tok/s`;
- aggregate median decode average: `119.50639487463019 tok/s`;
- per-lane median prefill: `1053.751`, `1042.833`, `1058.511`,
  `1052.084 tok/s`;
- per-lane median decode: `119.709`, `119.321`, `119.498`,
  `119.498 tok/s`;
- every lane `summary.json` recorded
  `launcher_identity.prefill_ubatch_size = "2048"`;
- every server log header recorded `prefill_ubatch_size=2048`.

This validates the identity-capture fix and preserves the phase-prefill service
recipe as a reproducible service lane. It is still not a LocalMaxxing
short-decode headline.

## Next Action

For short-decode records, stop repeat-only and small-flag sweeps unless paired
with a new source mechanism. The next serious source lane is the verifier
accept-prefix v2 design described above.
