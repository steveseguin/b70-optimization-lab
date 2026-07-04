# 2026-07-04: Verifier token trace for Qwen27 drafter calibration

## Context

The next Qwen3.6 27B INT4 AutoRound lane is accepted-token improvement, not
another endpoint/config sweep. The current best strict record remains
`65.27648650325429 tok/s` for `webhie/Qwen3.6-27B-int4-AutoRound` with runtime
INT8 LM-head BF16 scales, MTP3, cg8, one B70, and the strict cold realistic
suite (`cached_tokens=0`).

The existing scheduler spec trace is not suitable for drafter calibration on
the async XPU path: it records scheduler placeholders like `[-1, -1, -1]`, not
the actual draft proposals. This is by design. Async scheduling sets
placeholder `request.spec_token_ids`; the worker later scatters real draft IDs
into the verifier input, and `SpecDecodeMetadata.draft_token_ids` is the first
reliable worker-side location.

## Source audit

Read-only explorer audit confirmed:

- scheduler trace records placeholders from `scheduled_spec_decode_tokens`;
- real draft IDs exist in worker proposal state and are scattered into
  `input_ids.gpu` before verifier metadata construction;
- target verifier top IDs exist either as dense `target_logits.argmax(dim=-1)`
  inside `rejection_sampler.py`, or as `top_token_ids[target_logits_indices]`
  in the all-greedy top-ID path;
- scheduler trace should not be repurposed as calibration source because that
  would add worker-to-scheduler synchronization and still miss target IDs.

## Heavy replay microscope attempt

Tried the existing worker replay microscope first:

```bash
VLLM_XPU_REPLAY_MICROSCOPE_FILE=<run>/replay-microscope.jsonl
VLLM_XPU_REPLAY_MICROSCOPE_MAX_LINES=2500
VLLM_XPU_REPLAY_MICROSCOPE_TENSOR_LIMIT=8
VLLM_XPU_REPLAY_MICROSCOPE_TOPK=4
```

Run directory:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/runs/qwen27-webhie-int8lmhead-bf16scale-microscope-20260704T065828Z
```

Outcome: **no-go for full-suite collection**. The server completed the first
request, then wedged; a second manual request timed out. The trace captured only
7 microscope records. This is diagnostic-only and was stopped; no speed result
was promoted.

Conclusion: the replay microscope is too invasive for current Qwen27 async/MTP
full-suite tracing.

## Lightweight verifier trace patch

Added a default-off sampler-level trace in
`/home/steve/src/vllm/vllm/v1/sample/rejection_sampler.py`:

```bash
VLLM_XPU_SPEC_DECODE_VERIFY_TRACE_FILE=<run>/verify-trace.jsonl
VLLM_XPU_SPEC_DECODE_VERIFY_TRACE_MAX_LINES=5000
```

It records compact token IDs only:

- `draft_token_ids`;
- `target_argmax_token_ids`;
- `output_token_ids`;
- `prefix_accepted`;
- `bonus_token_id`;
- target/bonus logits row indices.

No behavior change occurs unless the env var is set. Syntax check passed:

```bash
/home/steve/.venvs/vllm-xpu/bin/python -m py_compile \
  /home/steve/src/vllm/vllm/v1/sample/rejection_sampler.py
```

Patch snapshots:

```text
patches/qwen36-27b-autoround-int4-b70/vllm-active-stack-before-qwen27-sampler-trace-20260704.patch
patches/qwen36-27b-autoround-int4-b70/vllm-active-stack-with-qwen27-sampler-trace-20260704.patch
```

`before` SHA256:

```text
f87a252e62cb8885c327666b7d8ec24d0fac6ad49c4e7a8366fa8bd800a4fd12
```

`with` SHA256:

```text
60830cfb9ada3bdb9687f61afc06672f15c96c4fab82daeb9f5772d0c99ff466
```

Added summarizers:

```text
scripts/summarize-qwen27-spec-verify-trace.py
scripts/summarize-qwen27-replay-microscope.py
```

The verify-trace summarizer skips zero-draft warmup/profile rows generated
before endpoint readiness.

## Lightweight traced strict run

Run directory:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/runs/qwen27-webhie-int8lmhead-bf16scale-verifytrace-20260704T070717Z
```

Strict result:

```text
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-int8lmhead-bf16scale-verifytrace-20260704T070717Z-20260704T070717Z.json
```

Summary:

```text
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-int8lmhead-bf16scale-verifytrace-20260704T070717Z-verify-summary.md
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-int8lmhead-bf16scale-verifytrace-20260704T070717Z-verify-summary.json
```

Strict-suite result, classification **support/diagnostic only**:

- final gate passed;
- `cached_tokens=0` on all 12 prompts;
- median `64.8999288973447 tok/s`;
- p10 `57.15735989632373 tok/s`;
- mean `63.71935288222712 tok/s`;
- TTFT median `609.6218960592523 ms`.

This is not a new record and should not be submitted to LocalMaxxing.

Verifier trace totals:

- trace rows: `563`;
- skipped zero-draft warmup rows: `2`;
- verifier steps: `561`;
- draft tokens: `1683`;
- prefix-accepted tokens: `1007`;
- prefix acceptance fraction: `0.5983363042186571`;
- mean target-verified tokens per verifier step: `2.7950089126559714`;
- full-accept rate: `0.40641711229946526`;
- accepted histogram: `{0: 113, 1: 117, 2: 103, 3: 228}`;
- per-position target-top1 match: `{0: 0.7985739750445633, 1: 0.7183600713012478, 2: 0.6149732620320856}`.

## Interpretation

The verifier trace matches prior acceptance summaries and gives real draft-vs-
target identity without the scheduler placeholder problem. MTP3 is already
getting about `2.80` generated/verified tokens per expensive verifier step.
If step cost stayed fixed, perfect MTP3 acceptance would only scale the current
`~65 tok/s` family to roughly:

```text
65 * (4.0 / 2.795) ~= 93 tok/s
```

So acceptance improvement is real and worth pursuing, but it is not enough by
itself to reliably crack `100 tok/s` unless paired with lower verifier/LM-head
cost or a deeper drafter that preserves acceptance.

Current implication:

1. Use compact verifier traces for drafter calibration analysis; do not use
   scheduler `scheduled_spec_token_ids` for this purpose.
2. Do not run full replay microscope during strict suites unless debugging a
   single failure; it can wedge the service.
3. Next credible lane is target-matched drafter calibration / training on
   held-out realistic-style data, while keeping exact target verification and
   strict final-suite anti-cheating separation.
4. The other major route remains reducing step cost: a true LM-head top-ID
   producer that helps both draft and target rows, or deeper native verifier
   reductions.
