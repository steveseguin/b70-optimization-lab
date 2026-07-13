# Q6_K M=6 fused top-1 production-fixture gate

Date: 2026-07-13

## Outcome

The experiment-only fused Q6_K LM-head/top-1 kernel passes the required real
DFlash production-fixture gate on B70 GPU 2. For a captured native-Q8 DFlash5
width-6 decoder activation, all five useful rows matched:

- the argmax from the full production logits;
- the token ID actually emitted by the DFlash sampler; and
- the comparator's independent full-logit reference.

The three 20-iteration fused-boundary medians were `2.47448 ms`, `2.46948 ms`,
and `2.47864 ms`. All are below the pre-integration `2.5 ms` absolute gate.
The largest fused-versus-production top-1 logit delta was `1.90735e-6`; three
rows were identical at the displayed float precision.

This clears correctness and latency for runtime integration. It does not claim
an end-to-end speedup yet. Against the comparator's already optimized
full-logit reference, the measured gain was only `1.053-1.061x`; the prior
live operation timeline measured the production LM head near `3.18 ms`, but
only an integrated strict crossover can establish the actual cycle saving.

## What was captured

The guarded `common/speculative.cpp` diagnostic uses
`LLAMA_DFLASH_LMHEAD_CAPTURE=/path`. It writes exactly once and is completely
dormant without that variable.

The fixture contains an 84-byte fixed header followed by `6 x 5120` contiguous
FP32 values. The activation is DFlash decoder `result_norm`, the exact right
operand consumed by shared target `output.weight`. `llama_get_embeddings_ith`
resolves each output row before the copy, so file row `i` is batch/logit row
`i`; the file stride is exactly 5120 floats with no padding. Row 0 is the
known token and is intentionally not sampled. Rows 1 through 5 are the five
noise positions.

For each useful row the header stores the result of a complete scan of the
248,320 production FP32 logits with lowest-ID tie breaking, plus the token ID
returned by the live DFlash sampler. The fixture identity is:

- path: `/mnt/fast-ai/bench-results/qwen27-q6k-m6-top1/dflash-real-m6-v1.bin`;
- bytes: `122964`;
- SHA-256: `e2bcd65300f9fa4d7b733dd0491d3c01cf566aadbbf4e22f7587079867484e3f`;
- structured manifest:
  `data/qwen27-q6k-m6-top1-real-fixture-20260713.json`.

The binary fixture stays outside Git. The manifest is the durable tracked
identity.

## Diagnostic graph effect and the first failure

The first implementation enabled ordinary embeddings in the DFlash
constructor. That was too broad: the next DFlash encoder pass inherited the
flag, entered generic pooling, and asserted at `llama-graph.cpp:3376` because
the encoder graph does not provide `result_norm/result_embd`.

The fix is to enable embeddings immediately before the one width-6 decoder
`llama_decode`, capture the normalized rows after it returns, and disable
embeddings before any later encoder call. This deliberately changes the graph
identity only for that single diagnostic decoder pass and adds a 120 KiB
device-to-host activation copy. Therefore capture-run end-to-end timings are
not representative and were not promoted. Without the environment variable,
there is no graph or execution change.

The write uses a PID-qualified temporary file and atomic rename, so a partial
fixture is not published.

## Production run identity

The capture used:

- target: Qwen3.6-27B Q4_0, target KV Q8_0;
- draft: native Q8_0 DFlash, draft KV F16;
- FA enabled for target and draft;
- `n_max=5`, `n_min=0`, `p_min=0`;
- one B70, `ZE_AFFINITY_MASK=2`;
- Xe2 M=6 gate/up plus down, `PACK_LIMIT=187`;
- llama.cpp source commit `e3546c794`, with protected guarded experiment
  changes present;
- prompt: `Write a Python function that returns the first ten prime numbers.`;
- 24 prompt tokens, 16 output tokens, `cached_tokens=0`;
- live DFlash acceptance: 11/16 accepted, mean block length 3.75.

The capture request produced the five IDs `12305, 198, 727, 369, 36951`.

## Comparator command

```bash
set +u
source /opt/intel/oneapi/setvars.sh --force
set -u
export ZE_AFFINITY_MASK=2 ONEAPI_DEVICE_SELECTOR='level_zero:*'
/mnt/fast-ai/bench-results/qwen27-q6k-m6-top1/q6k-m6-top1 \
  /dev/shm/qwen27-b70-model-cache/20c9c45d4d25b492b82117960b5f715ef9daff75e4e14c4fb878fa3793fb379a/Qwen3.6-27B-Q4_0.gguf \
  20 0xb70d6 \
  /mnt/fast-ai/bench-results/qwen27-q6k-m6-top1/dflash-real-m6-v1.bin
```

First retained result:

```text
row=1 production_id=12305 sampled_id=12305 fused_logit_delta=1.90735e-06 production_exact=1
row=2 production_id=198 sampled_id=198 fused_logit_delta=1.90735e-06 production_exact=1
row=3 production_id=727 sampled_id=727 fused_logit_delta=0 production_exact=1
row=4 production_id=369 sampled_id=369 fused_logit_delta=0 production_exact=1
row=5 production_id=36951 sampled_id=36951 fused_logit_delta=0 production_exact=1
reference_boundary_us=2605.83 fused_boundary_us=2474.48 speedup=1.05308 exact_ids=1 production_exact_ids=1 gate=PASS
```

Two immediate repeats reported `2469.48 us` and `2478.64 us`, with exact IDs
and `gate=PASS` in both.

## Artifacts and next step

- comparator:
  `experiments/qwen27-dflash-sycl-b70/xe2-verifier/q6k-m6-top1.cpp`;
- build/run helper:
  `experiments/qwen27-dflash-sycl-b70/xe2-verifier/build-q6k-m6-top1.sh`;
- initial synthetic result:
  `experiments/qwen27-dflash-sycl-b70/notes/2026-07-13-q6k-m6-fused-top1-result.md`;
- real fixture manifest:
  `data/qwen27-q6k-m6-top1-real-fixture-20260713.json`.

The next step is guarded DFlash-only runtime integration for `M=6`, `p_min=0`:
reuse an offline-expanded/cached Q6_K pack, compute rows 1 through 5, and return
the five top-1 IDs without materializing five full logit rows. Integration must
preserve a fallback to ordinary logits and pass a same-build strict AOT
crossover before promotion.
