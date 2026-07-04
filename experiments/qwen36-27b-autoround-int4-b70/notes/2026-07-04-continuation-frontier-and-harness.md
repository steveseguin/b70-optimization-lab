# 2026-07-04 - Continuation frontier and speculative-config harness fix

## Classification

Qwen27 optimization continuation note. No endpoint throughput claim and no
LocalMaxxing submission.

## Current target

Beat the current strict fresh-response Qwen27 one-B70 record,
`65.27648650325429 tok/s`, without changing the quality/validity rules:

- fixed realistic Qwen suite;
- each prompt once as a cold response;
- `cached_tokens=0` every request;
- no prompt/KV/context-checkpoint/response/ngram/history reuse;
- target-verified speculation only;
- quality gate before promotion.

## State reviewed

The repo was clean and pushed at
`fe70bfc08 Record Qwen27 post-AWQ repro support` before this continuation.
No vLLM server was occupying the Qwen27 benchmark ports.

Closed lanes confirmed from local notes/results:

- webhie current recipe remains best; post-AWQ `66.128 tok/s` is support-only /
  variance, not a new record;
- Lorbus, webhie-Code, acyildirimer, and cyankiwi AWQ variants are no-win or
  variance-class;
- EAGLE3 compressed/full loaded but k>=2 device-lost or stalled locally, and
  k=1 was only about `30 tok/s`;
- compact local EAGLE v2 training remains far below endpoint-candidate
  acceptance (`0.6953125` best heldout mean accepted, `0.44091796875` separate
  calibration);
- DFlash remains closed locally due multi-KV/SWA instability and very low
  acceptance in eager diagnostics;
- llama.cpp `unsloth/Qwen3.6-27B-MTP-GGUF` Q4 lane is valid but not
  competitive (`30.679 tok/s` best strict row);
- standalone full-vocab LM-head top-1 and candidate-max kernels were exact but
  failed the microbench promotion rule.

## Harness fix

Added `QWEN36_27B_SPECULATIVE_CONFIG` to the Qwen27 vLLM candidate launcher.
This lets future external-drafter tests pass JSON as one `--speculative-config`
argument instead of relying on whitespace splitting in `VLLM_EXTRA_ARGS`.

Touched files:

- `experiments/qwen36-27b-autoround-int4-b70/scripts/serve-vllm.sh`;
- `experiments/qwen36-27b-autoround-int4-b70/scripts/run-vllm-candidate.sh`.

The default record recipe is unchanged. If `QWEN36_27B_SPECULATIVE_CONFIG` is
unset, the launcher still uses the built-in
`{"method":"qwen3_next_mtp","num_speculative_tokens":...}` config when
`QWEN36_27B_ENABLE_MTP != 0`.

Validation:

```bash
bash -n experiments/qwen36-27b-autoround-int4-b70/scripts/serve-vllm.sh
bash -n experiments/qwen36-27b-autoround-int4-b70/scripts/run-vllm-candidate.sh
```

Both syntax checks passed.

## Active question

The only plausible non-kernel path left is true partial speculative-group
support: reduce wasted serial MTP draft LM-head calls without lowering emitted
tokens per verifier step and without breaking XPU/GDN metadata. A read-only
source audit was delegated to identify whether this is a feasible next patch or
still too large/risky for the current stack.

Audit result: **no-go as a near-term record lane**.

The audit found that the scheduler already has partial-group awareness and the
rejection sampler is mostly length-aware, but the rest of the XPU/GDN stack is
not:

- proposer is fixed-width around the global `num_speculative_tokens`;
- GPU runner has fixed CPU draft buffers, fixed `prev_index * K` scatter, fixed
  stale-row zeroing, and fixed graph-capture dummy metadata;
- GDN/Mamba graph metadata is sized around global `K + 1` rows;
- GDN native/Python loops index `query_start + spec_pos` through a global loop
  length, matching the previous XPU OOB failure;
- state commit/rollback can corrupt recurrent state if an accepted count points
  to a column never produced by a short row.

True partial groups would therefore require coordinated changes to proposer
contracts, `SpecDecodeMetadata`, GPU runner scatter/copy, graph capture
bucketization, GDN/Mamba native loops, and state postprocess. That is real
groundwork, not a small record attempt.

Smaller safe experiment, if we still want a diagnostic: keep verifier/GDN shape
fixed at MTP3, shorten only proposer LM-head work, pad the tail, and carry an
explicit effective draft length so padded tokens cannot be accepted. This can
measure proposer-side savings without ragged GDN state, but expected record
upside is low because target verifier rows remain fixed and scheduler-only
adaptive depth already lost throughput.

Do not run another strict endpoint benchmark until the candidate is one of:

1. a true partial-group implementation that avoids the old scheduler-only loss
   and the prior proposer-shortening XPU indexing assert;
2. a materially different exact LM-head producer that passes the microbench
   gate before integration;
3. a genuinely stronger target-matched drafter that first clears an offline
   held-out acceptance threshold.
