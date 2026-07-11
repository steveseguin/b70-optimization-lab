# Qwen27 TP2 public-oneCCL tuning and draft-graph promotion

Date: 2026-07-11

Status: **promoted**. Conservative strict fresh-response record
`82.89371762720036 tok/s`; integrated full-quality high
`85.39381462095321 tok/s`.

## Starting point

The pinned public oneCCL parent `b52f40c` / libccl `4ceafd1` had already
repaired the installed runtime's deterministic BF16 `[4,5120]` target graph
all-reduce corruption and promoted a conservative TP2 result of
`78.22635247759823 tok/s`. The target ran PIECEWISE graph capture, but the
intrinsic MTP draft remained eager because enabling its graph failed during
capture.

All endpoint rows below use the fixed 12-prompt realistic suite, each prompt
once, token-ID stream timing for generated tokens 1-100 after TTFT,
`cached_tokens=0`, no prefix/history/response reuse, and target-verified MTP3.

## Small-message oneCCL algorithm screen

The TP2 verifier reduces 40,960-byte BF16 messages. A batched graph diagnostic
was added to `graph_allreduce_probe.py`; it includes static-input publication
plus graph replay and performs one final synchronization. It is a comparative
kernel diagnostic, not a headline throughput benchmark.

Same-pair isolated results on GPUs 2-3, 10,000 graph replays:

| oneCCL path | Exact | ms/copy+replay |
| --- | --- | ---: |
| default LL256 ring | yes | 0.022843 |
| LL256 two-shot | yes | 0.021944 |
| generic small path | yes | 0.023198 |

`CCL_SYCL_ALLREDUCE_ARC=1` deadlocked during graph validation and is rejected.
Two-shot was only about 3.9% faster for the collective itself. Its strict
endpoint screen measured `75.090862 tok/s`, below the `78.226352` record, so it
is preserved as a no-win and not enabled in the promoted wrapper.

## Draft graph failure

With `VLLM_XPU_DRAFT_DISABLE_CUDAGRAPHS=0`, the draft compiled but failed before
readiness:

```text
RuntimeError: wait method cannot be used for an event associated with a command graph.
```

Inductor generated:

```python
buf6 = torch.ops._c10d_functional.all_gather_into_tensor.default(buf5, 2, "3")
torch.ops._c10d_functional.wait_tensor.default(buf6)
```

This occurred in the Qwen3 Next draft around BF16 rank-local hidden tensors;
it was not evidence that oneCCL all-gather arithmetic or graph recording was
invalid.

## Exact all-gather oracle

`graph_allgather_probe.py` isolates a preallocated TP2 BF16 `[4,2560]`-per-rank
all-gather, changes every input before every replay, and checks every output
element against an exactly representable oracle.

Pinned public oneCCL results on independent GPU pairs:

- blocking direct all-gather capture: `512/512` exact on both ranks;
- async all-gather plus `Work.wait()` capture: `512/512` exact on both ranks.

Therefore the incompatibility is specifically the compiled functional
`wait_tensor` lowering. Direct oneCCL all-gather capture is valid.

## Runtime fix

Patch:

`patches/qwen36-27b-autoround-int4-b70/vllm-qwen27-compiled-allgather-custom-op-draftgraph-20260711.patch`

The default-off `VLLM_XPU_COMPILE_ALLGATHER_CUSTOM_OP=1` branch mirrors the
existing XPU compiled-all-reduce strategy: while compiling, keep all-gather as
the existing opaque `vllm::all_gather` custom op. At execution/capture time its
direct preallocated implementation records into the XPU graph without the
functional event wait. Eager mode and all runs without the flag retain the old
path.

The patched generated draft code contains:

```python
buf6 = torch.ops.vllm.all_gather.default(buf5, -1, 2, "tp:0")
```

Both target and draft then compiled and captured all mixed buckets plus the
decode bucket. The server passed smoke and the complete endpoint gates.

## Performance and variance

Isolated strict rows:

| Run | Median | p10 | Mean | Quality |
| --- | ---: | ---: | ---: | --- |
| first draft-graph screen | 82.893718 | 72.751868 | 83.100685 | separate quality128 pass |
| integrated lock | 85.393815 | 79.731481 | 85.343944 | all gates pass |

The isolated spread is 3.02%, inside the established 4.4% run variance band.
Use `82.893718 tok/s` as the conservative reproducible headline and retain
`85.393815 tok/s` as a valid high.

Four GPUs were used for a two-window crossover to distinguish the change from
pair and shared-load effects:

| Window | Graph draft | Eager draft | Paired delta |
| --- | ---: | ---: | ---: |
| graph GPUs 2-3, eager GPUs 0-1 | 81.580468 | 75.663924 | +7.82% |
| graph GPUs 0-1, eager GPUs 2-3 | 79.636650 | 77.307712 | +3.01% |

The graph path won after swapping physical pairs. Average graph median was
`80.608559`; average eager median was `76.485818`, a +5.39% controlled gain.
Window 2 alone is inside the single-run band, but the same-direction crossover
and isolated rows support promotion.

## Quality and validity

The integrated lock passed:

- all 12 unique realistic prompts once, `cached_tokens=0` for every request;
- exact `OK`, copy phrase, arithmetic, and JSON-schema cases;
- 128/128 identical color-canary hashes;
- parity with the established target-model baseline;
- exact 1K needle retrieval (`987` actual context tokens);
- no prefix/KV/history/checkpoint/response reuse;
- target-verified intrinsic MTP3 only.

Diagnostic all-reduce/all-gather timings and repeated quality canaries are not
used as fresh-response throughput claims.

## Reproduce

```bash
cd /home/steve/llm-optimizations
GPU_INDEX=2,3 PORT=19445 QUALITY_REPEAT_RUNS=128 \
  experiments/qwen36-27b-autoround-int4-b70/scripts/run-tp2-oneccl-public4ce-draftgraph-candidate.sh
```

The wrapper checksum-gates the pinned oneCCL library and kernels. Rebuild them
with `oneccl_ll256/build-public-oneccl.sh` if the external runtime directory is
missing.

## Next high-value work

The draft graph is now closed as a validated win, but `82.9` remains below the
100 tok/s objective. Small collective-algorithm tuning is exhausted. The next
credible levers are:

1. reduce target PIECEWISE graph boundaries, while respecting the known XPU
   full-graph scratch-memory limitation;
2. profile the now-graph-captured exact recipe to refresh step latency and
   accepted tokens per step;
3. improve target-verified accepted tokens per step without warmed history;
4. revisit full-target/DDTree work only where its acceptance and target-row
   economics can beat intrinsic MTP3;
5. avoid returning to sampler copies, metadata copies, or two-shot oneCCL
   tuning unless a new trace moves those into a material bucket.
