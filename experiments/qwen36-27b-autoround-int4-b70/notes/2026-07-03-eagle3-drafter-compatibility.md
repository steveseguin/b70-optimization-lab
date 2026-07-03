# 2026-07-03: EAGLE3 compressed drafter compatibility branch

## Why

The current valid Qwen3.6 27B INT4 AutoRound record is the internal
`qwen3_next_mtp` MTP3 recipe at about `53.522 tok/s` on the strict fresh
Qwen realistic suite. Timing diagnostics show that the current path is dominated
by repeated full BF16 LM-head/logits calls:

- target `gpu_model_runner.compute_logits`: about `4.42 ms` per target step;
- draft `spec_decode.greedy_sample.compute_logits`: about `4.45 ms` per draft
  sample;
- MTP proposer forward itself: about `0.65-0.83 ms`.

Raising accepted tokens per target forward is likely higher value than more
small sampler/plumbing work. External target-verified drafters are a plausible
route, provided the result remains fresh-response valid and does not depend on
warmed continuation history.

## Candidate

Downloaded and tested:

```text
Ex0bit/Qwen3.6-27B-PRISM-EAGLE3
/mnt/fast-ai/llm-cache/hf/manual/Ex0bit--Qwen3.6-27B-PRISM-EAGLE3/compressed
```

Local compressed files:

- `compressed/config.json`
- `compressed/model.safetensors` (`~1.1 GB`)

Model-card facts to preserve:

- EAGLE3 drafter for `Qwen/Qwen3.6-27B`;
- compressed draft vocabulary (`draft_vocab_size=32768`);
- one decoder layer with aux hidden-state layers `[1, 31, 60]`;
- target-verified / lossless speculation in principle;
- upstream card reports much larger wins on stock BF16 Qwen3.6, but local target
  here is Intel AutoRound INT4 with local vLLM/XPU, so acceptance and stability
  must be validated locally.

Related future candidate:

- `z-lab/Qwen3.6-27B-DFlash` is a 2B BF16 drafter with a vLLM PR requirement
  in the model card. Keep it as a follow-up only after EAGLE3 stability is
  characterized.

## Harness Fix Found While Testing

`scripts/run-qwen36-27b-autoround-vllm-candidate.sh` had a malformed default
for `COMPILATION_CONFIG`; the parameter expansion could emit invalid JSON and
also corrupt explicit overrides. The fix is to set the JSON default with an
explicit `if [[ -z ... ]]` block. This is a general harness fix and should be
committed independently from any EAGLE3 result.

## First Run: k=3, graph on, promote-source env pair

Command shape:

```bash
cd /home/steve/llm-optimizations
DRAFTER=/mnt/fast-ai/llm-cache/hf/manual/Ex0bit--Qwen3.6-27B-PRISM-EAGLE3/compressed
GPU_INDEX=0 PORT=19410 \
LABEL=qwen27-eagle3-compressed-k3-cg8-realistic128-chat-tokenids-qwensuite \
QWEN36_27B_ENABLE_MTP=0 \
QWEN36_27B_ENABLE_XPU_GRAPH=1 \
MAX_MODEL_LEN=2048 MAX_NUM_BATCHED_TOKENS=1024 MAX_NUM_SEQS=1 \
COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE","max_cudagraph_capture_size":8}' \
VLLM_XPU_GDN_PROMOTE_ACCEPTED_SPEC_STATE=1 \
VLLM_XPU_GDN_NONSPEC_POSTPROCESS_ACCEPTED_STATE=0 \
VLLM_EXTRA_ARGS="--speculative-config {\"method\":\"eagle3\",\"model\":\"${DRAFTER}\",\"num_speculative_tokens\":3}" \
scripts/run-qwen36-27b-autoround-vllm-candidate.sh
```

Run directory:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/runs/qwen27-eagle3-compressed-k3-cg8-realistic128-chat-tokenids-qwensuite-20260703T114339Z
```

Observed:

- target and drafter loaded successfully;
- vLLM accepted `method='eagle3'`, compressed drafter path, and
  `num_speculative_tokens=3`;
- graph capture completed with capture sizes `[1, 2, 4, 8]`;
- early server metrics showed the drafter can accept well on some prompts:
  the first request reported about `94.1%` per-draft acceptance and mean
  acceptance length `3.82`;
- later prompts had lower acceptance (`~27-38%`), then one interval reported
  `0%`;
- the strict suite did not finish and no result JSON was produced.

Failure:

```text
RuntimeError: level_zero backend failed with error: 20 (UR_RESULT_ERROR_DEVICE_LOST)
```

Crash point:

```text
gpu_model_runner.py:_prepare_inputs
self.num_accepted_tokens_event.synchronize()
```

The dumped scheduler output at crash included:

```text
scheduled_spec_decode_tokens={...: [-1, -1, -1]}
num_scheduled_tokens=4
num_computed_tokens=[75]
num_output_tokens=[5]
```

Interpretation:

- invalid result; do not use for throughput or quality claims;
- promising enough to keep investigating because loading works and at least one
  prompt had high EAGLE3 acceptance;
- instability may be from k=3, XPU graph interaction, the promote-source
  accepted-state env pair, or a local vLLM/XPU EAGLE3 edge around accepted-token
  bookkeeping.

## Next Isolation Runs

Run only strict fresh-response checks or clearly labeled diagnostics. Do not
promote anything unless every request has `cached_tokens=0` and the fixed
realistic suite passes.

Planned isolation order:

1. EAGLE3 k=2, graph on, current promote-source env pair.
2. EAGLE3 k=1, graph on, current promote-source env pair.
3. EAGLE3 k=3, graph on, default accepted-state env (`PROMOTE=0`,
   `NONSPEC_POSTPROCESS_ACCEPTED_STATE=1`) to check whether the current MTP
   env pair is incompatible with EAGLE3.
4. EAGLE3 k=3, graph off / eager diagnostic, if needed, to separate graph
   capture from drafter logic.

Variance handling:

- treat any sub-1% Qwen27 delta as inconclusive without same-window or
  crossover repeats;
- crashes, quality failures, and large deltas do not need variance repeats
  before classification;
- if an EAGLE3 variant survives and appears within a few percent of the current
  best, rerun it against a same-window MTP3 promote-source control before
  deciding.

## Four-GPU Isolation Results

All variants used the fixed Qwen realistic suite in chat mode with token IDs
unless noted. These are not LocalMaxxing or headline candidates.

### k=1, graph on, promote-source env pair

Result file:

```text
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-eagle3-compressed-k1-cg8-realistic128-chat-tokenids-qwensuite-20260703T115224Z.json
```

Outcome:

- strict gate passed;
- `cached_tokens=0` on all 12 prompts;
- median tokens 1-100 after TTFT: `30.063 tok/s`;
- p10: `26.806 tok/s`;
- mean: `29.552 tok/s`;
- median TTFT: `8734.193 ms`.

Interpretation: stable enough to prove EAGLE3 compressed can run at k=1, but
far below both the current MTP3 promote-source record (`53.522 tok/s`) and the
no-spec control family. Not a viable optimization route.

### k=2, graph on, promote-source env pair

Run directory:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/runs/qwen27-eagle3-compressed-k2-cg8-realistic128-chat-tokenids-qwensuite-20260703T115224Z
```

Outcome:

- loaded target + drafter;
- graph capture completed;
- crashed during the strict suite with HTTP 500 from the benchmark;
- no result JSON produced;
- fatal error:

```text
RuntimeError: level_zero backend failed with error: 20 (UR_RESULT_ERROR_DEVICE_LOST)
gpu_model_runner.py:get_output
self.async_copy_ready_event.synchronize()
```

Interpretation: instability is not limited to k=3. It can also surface at k=2
and at a different synchronization point from the first k=3 failure.

### k=3, graph on, default accepted-state env

Run directory:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/runs/qwen27-eagle3-compressed-k3-cg8-defaultstate-realistic128-chat-tokenids-qwensuite-20260703T115225Z
```

Outcome:

- loaded target + drafter;
- graph capture completed;
- completed 8 HTTP requests, then stalled with no benchmark output after more
  than 15 minutes;
- no result JSON produced;
- manually terminated;
- acceptance collapsed on later prompts, including a `0%` interval:

```text
Mean acceptance length: 1.00
Accepted: 0
Drafted: 315
Per-position acceptance rate: 0.000, 0.000, 0.000
```

Interpretation: the current promote-source env pair is not the sole problem.
Default accepted-state handling avoids an immediate crash in this run, but the
branch still becomes operationally unusable.

### k=3, graph off / eager, promote-source env pair

Run directory:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/runs/qwen27-eagle3-compressed-k3-eager-realistic128-chat-tokenids-qwensuite-20260703T115225Z
```

Outcome:

- loaded target + drafter;
- graph capture was disabled (`cudagraph_mode=NONE`);
- crashed during the strict suite with HTTP 500;
- no result JSON produced;
- fatal error:

```text
RuntimeError: level_zero backend failed with error: 20 (UR_RESULT_ERROR_DEVICE_LOST)
gpu_model_runner.py:_prepare_inputs
self.num_accepted_tokens_event.synchronize()
scheduled_spec_decode_tokens={...: [-1, -1, -1]}
```

Interpretation: the instability is not purely an XPU graph replay/capture
issue. EAGLE3 compressed k=3 can still device-loss in eager mode.

## Decision

Close `Ex0bit/Qwen3.6-27B-PRISM-EAGLE3` compressed as a near-term optimization
lane for this Intel AutoRound INT4 target:

- it can be target-verified/fresh-valid at k=1, but that path is too slow;
- k>=2 is unstable or stalls in local vLLM/XPU;
- acceptance varies dramatically by prompt, with some prompts collapsing to
  near-zero or zero, so even a stability fix may not beat the current internal
  MTP3 recipe without additional drafter/target matching work.

Future revisit conditions:

1. test against stock BF16 `Qwen/Qwen3.6-27B` to separate AutoRound target
   mismatch from vLLM/XPU instability;
2. retry after upstream vLLM EAGLE3/XPU fixes;
3. inspect whether the compressed-draft-vocab EAGLE head has an XPU-specific
   bug around `-1` placeholders / accepted-token event handling.

The next external-drafter candidate is DFlash, but it carries higher bring-up
risk because the model card references a vLLM PR requirement. Keep it as an
explicitly labeled compatibility attempt, not as a known-good route.
