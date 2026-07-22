# DeepSeek V4 Flash on 4x B70: Orchestrator Handoff

Last updated: **2026-07-18**

**Closeout override (2026-07-21):** the lane is paused at the verified
80.820052 tok/s record. This document remains the detailed build and evidence
reference, but its immediate-work sections are historical. Resume only under
the conditions in
[`notes/2026-07-21-deepseek-v4-flash-frontier-closeout.md`](notes/2026-07-21-deepseek-v4-flash-frontier-closeout.md).
The promoted entry points are the
[result packet](../../results/deepseek-v4-flash-k160-b70/README.md) and
[standalone repro](../../repro/deepseek-v4-flash-k160-b70-80tps-20260718/README.md).

This is the manager-facing resume document for handing orchestration to another
AI. It describes the objective, immutable rules, live state, source trees,
record identity, build and run workflow, quality gates, LocalMaxxing policy,
completed experiments, known dead ends, and the next decision tree. Detailed
chronology remains in `results/experiment-ledger.md` and `notes/`.

## 1. Objective

The product objective is throughput for **one active generation**, never
aggregate serving throughput:

- next milestone: **100 tok/s** for the unchanged DeepSeek V4 Flash K160
  target on four Intel Arc Pro B70 32 GB GPUs;
- stretch milestone: **200 tok/s** for that same single session;
- do not shrink, replace, sparsify further, or silently substitute the target
  model to improve the headline;
- do not count multiple concurrent requests or multiple independent replicas;
- every speculative token must be verified by the declared target;
- short and long unpredictable real-world inputs matter more than a favorable
  synthetic score.

The current qualified target-verified record is **80.820052 tok/s**. The
three independent strict-suite medians were 80.820052 / 76.900178 /
78.287226 tok/s. All 36 requests were unique and cache-zero, and 24/24 ordered
exact canaries passed around the suites. LocalMaxxing approved
`cmrquta9905w3lg013m5vxoqx`.

At the current run-of-three center, 100 tok/s still needs roughly 21.7% less
time per emitted token or a useful increase in accepted tokens per target
cycle. A 200 tok/s result is not credible from micro-fusion alone; it requires
both a substantially leaner target cycle and deeper useful speculation.

## 2. Non-negotiable validity rules

1. Report one-active-generation throughput only.
2. Keep target model/revision/quantization fixed for matching comparisons.
3. Use the complete run identity. A speed number without source commits,
   graph flags, topology, sampler flags, and runtime identity is not evidence.
4. Promotion uses fresh unique prompts, `cached_tokens=0`, no prefix cache,
   no response reuse, no n-gram/history acceleration, and no warmed repeated
   continuation.
5. The primary strict metric is median generated-token throughput for tokens
   1-100 after TTFT, using streamed token-ID timestamps.
6. Exact target verification is required. Draft acceptance alone is not a
   quality proof.
7. Freeze speculative policy before held-out evaluation. Do not route by
   prompt ID/hash, suite label, target output, future logits, or manually
   selected per-prompt policy.
8. Preserve failed patches and results. Do not erase negative experiments or
   silently relabel a failed gate.
9. A component microbenchmark does not establish endpoint speed. Require a
   same-binary service control for any promotion claim.
10. Submit to LocalMaxxing only after a real matching record, complete identity,
    exactness, and realistic-suite pass.

The detailed anti-cheating specification is
`quality/spec-eval-contract-v1.json`. It requires two frozen held-out packs,
short and 2K/4K nonrepetitive contexts, request-scoped acceptance and timing,
target-only/current-control/candidate comparisons, and no benchmark-specific
routing.

## 3. Hardware, model, and storage

- Host: four Intel Arc Pro B70 32 GB GPUs, visible as Level Zero devices
  `0,1,2,3`.
- Intended topology: TP4 + expert parallelism, one active request.
- Target model:
  `0xSero/DeepSeek-V4-Flash-180B`, revision
  `7c360e1cd4a5168099dbc54d16d929bf6df04990`.
- Hot target path:
  `/mnt/fast-ai/llm-models/deepseek-v4-flash-xpu/current-k160`.
- Target size: about 96.026 GiB standard safetensors; uniform K160 assigns 40
  experts per EP rank.
- DSpark draft pack:
  `/mnt/fast-ai/llm-models/deepseek-v4-flash-xpu/dspark-draft-pack-aa22cb0`.
- DSpark source revision used for the pack:
  `aa22cb07426656189b2573b8e77a9b7333b8ae0f`.
- Benchmark outputs:
  `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/`.
- Captured decoder corpora:
  `/mnt/fast-ai/deepseek-v4-corpora/`.
- Compile caches:
  `/mnt/fast-ai/vllm-cache-exp/deepseek-v4-k160-dspark/vllm` and
  `/mnt/fast-ai/vllm-cache-exp/deepseek-v4-k160-dspark/torchinductor`.

K160 is the runnable performance target, not the final quality-certified
teacher construction. Its hash layers were pruned and its calibration is not
fully reproducible. Do not claim it is official REAP. The user nevertheless
explicitly chose to continue this K160/DSpark path and does not authorize
another model substitution.

## 4. Source trees and current state

```text
main repo    /home/steve/llm-optimizations
vLLM        /home/steve/src/deepseek-v4-vllm-xpu-dspark
             80f1ad820706103d11f095c8a97e42c624c8bad3
XPU kernels /home/steve/src/deepseek-v4-xpu-kernels-mwidth-mhc
             2cc25d0ca08d3a76de27ee50c6dda258350e93e8
oneCCL      /home/steve/src/oneccl-2021.17.2-b70-sizegate
             48fda4f0e074db005596d6899d5227d3f0316c12
runtime     /mnt/fast-ai/runtime/oneccl-2021.17.2-b70-wideepoch-48fda4f/lib
venv        /home/steve/.venvs/deepseek-v4-xpu
```

The vLLM and XPU worktrees are clean. The oneCCL tree intentionally contains
untracked local build output (`_build-b70/` and generated
`include/oneapi/ccl/config.h`); do not stage, delete, or mistake it for a
source patch.

No DeepSeek service is currently running. The final candidate was stopped
cleanly and all four GPUs are free. Verify rather than assume:

```bash
pgrep -af 'vllm|api_server|EngineCore|ray::' || true
ss -ltnp | rg ':18080|:8000' || true
```

The current source trees include later default-off experiments. The exact
public-record source identity remains:

```text
vLLM        264c7f2f7df21ddeeab32ecca0353133344f1ac9
XPU kernels 31315673737d95da0f79179c8f755260ef02c1d6
oneCCL      48fda4f0e074db005596d6899d5227d3f0316c12
```

For an exact record reproduction, use detached worktrees at those commits.
Do not call the newer experimental HEAD the same run identity merely because
all newer flags are off. The newer trees are the active development lane and
are useful for same-binary control/candidate testing.

## 5. Record recipe and launcher

The base launcher is:

```text
scripts/serve-k160-dspark-candidate.sh
  -> scripts/serve-k160-tp4-smoke.sh
```

The first script chooses eager/PIECEWISE graph modes, pins experiment flags,
the draft pack, cache paths, and speculative width. The second validates clean
source commits and model structure, loads oneAPI/oneCCL, records the full
identity, runs a four-rank preflight, and launches `vllm serve`.

The record used target PIECEWISE, private breakable draft PIECEWISE at exact
M=7, target verifier M=8, TP4+EP/DP1/PP1/concurrency1, FP8 KV, block 256,
seven DSpark proposals, persistent Markov, W1-only replication, exact M8
compressors, M8 W8A16, MXFP4 N128, native M8 router, sharded greedy target
argmax, and native rejection/commit. oneCCL preloads the wide-epoch runtime
and routes only all-reduces larger than 131,072 bytes through the safe path.

Working-control launch from a compatible clean development tree:

```bash
cd /home/steve/llm-optimizations
RUN_DIR=/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/control-$(date -u +%Y%m%dT%H%M%SZ) \
VLLM_COMMIT="$(git -C /home/steve/src/deepseek-v4-vllm-xpu-dspark rev-parse HEAD)" \
KERNEL_COMMIT="$(git -C /home/steve/src/deepseek-v4-xpu-kernels-mwidth-mhc rev-parse HEAD)" \
DSPARK_GRAPH_MODE=piecewise \
DSPARK_DRAFT_GRAPH_MODE=piecewise \
DSPARK_SPEC_TOKENS=7 \
VLLM_XPU_DSPARK_EXACT_QUERY_CAPTURE=1 \
VLLM_XPU_GREEDY_FUSED_REJECTION=1 \
VLLM_XPU_GREEDY_SHARDED_TARGET_ARGMAX=1 \
VLLM_XPU_DSPARK_FIXED_M7_TARGET_INPUTS=1 \
VLLM_XPU_DSPARK_PERSISTENT_MARKOV=1 \
VLLM_XPU_DSPARK_REPLICATED_MARKOV_W1=1 \
VLLM_XPU_V4_COMPRESSOR_BATCHED_EXACT_MAX_M=8 \
VLLM_XPU_V4_BLOCK_FP8_W8A16_MAX_M=8 \
VLLM_XPU_MXFP4_SMALL_M_N=128 \
VLLM_XPU_V4_ROUTER_NORM_MAX_M=8 \
experiments/deepseek-v4-flash-reap-xpu-b70/scripts/serve-k160-dspark-candidate.sh
```

Keep rejected flags at zero, especially event/host/sharded Markov transports,
M8 DPAS MHC, M8 pair-tile MHC, copy-elision, context-WKV fusion, and the fixed
M8 target builder.

Canonical identity dump:

```text
/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/
  dspark7-sharded-target-argmax-candidate-20260718T2100Z/identity.txt
```

Diff every field against it before interpreting speed.

## 6. Build workflow

### vLLM Python changes

Most changes need no package rebuild when the active trees lead `PYTHONPATH`:

```bash
export PYTHONPATH=/home/steve/src/deepseek-v4-vllm-xpu-dspark:\
/home/steve/src/deepseek-v4-xpu-kernels-mwidth-mhc:${PYTHONPATH:-}
/home/steve/.venvs/deepseek-v4-xpu/bin/python -m py_compile changed_file.py
```

Run relevant unit tests before model load. IPC broker example:

```bash
cd /home/steve/src/deepseek-v4-vllm-xpu-dspark
/home/steve/.venvs/deepseek-v4-xpu/bin/python -m pytest -q \
  tests/distributed/test_xpu_ipc_broker.py
```

### XPU native changes

```bash
cd /home/steve/src/deepseek-v4-xpu-kernels-mwidth-mhc
source /opt/intel/oneapi/setvars.sh >/dev/null 2>&1
ninja -C build/temp \
  csrc/xpu/mhc/xe_2/CMakeFiles/mhc_kernels_xe_2.dir/mhc_pre.cpp.o \
  CMakeFiles/_xpu_C.dir/csrc/xpu/torch_bindings.cpp.o \
  _xpu_C.abi3.so
install -m 755 build/temp/_xpu_C.abi3.so \
  vllm_xpu_kernels/_xpu_C.abi3.so
sha256sum build/temp/_xpu_C.abi3.so vllm_xpu_kernels/_xpu_C.abi3.so
```

Sampler-only edits usually need `topk_topp_sampler.cpp.o`,
`torch_bindings.cpp.o`, and the final link. SYCL device linking is expensive
and may touch generated attention objects. If the Ninja dependency database is
corrupt or causes spurious rebuilds:

```bash
ninja -C build/temp -t recompact
```

Do not copy a binary without recording source commit and binary SHA. The
package `.so` is ignored by Git; source commits are the durable identity.

### oneCCL

Do not replace the runtime casually. The wide collective epoch fixed
deterministic failures around positions 28 and 58. Generic communication flag
sweeps, recursive doubling, tiny-pair collectives, and resident polling are
already rejected.

## 7. Test and promotion workflow

Use the cheapest valid gate first:

1. source/static checks;
2. one-card changed-input arithmetic and timing;
3. all four cards independently if one card passes;
4. changed-input fixed-address graph replay;
5. real captured tensors/cycle corpus;
6. guarded service load;
7. ordered exact canaries before and after performance;
8. same-binary control/candidate crossover;
9. strict realistic suite, preferably three independent suites;
10. LocalMaxxing only for a genuine matching record.

Do not load 96 GiB for a candidate that already fails exactness or its
conservative component gate.

Exact canary capture and score:

```bash
python experiments/deepseek-v4-flash-reap-xpu-b70/scripts/capture-openai-logprob-corpus.py \
  --base-url http://127.0.0.1:18080 --model deepseek-v4-flash-k160 \
  --suite experiments/deepseek-v4-flash-reap-xpu-b70/quality/exact-canaries-v1.json \
  --out "$RUN_DIR/exact-canaries-pre.json" \
  --max-tokens 32 --top-logprobs 0 --label pre
python experiments/deepseek-v4-flash-reap-xpu-b70/scripts/score-exact-canaries.py \
  "$RUN_DIR/exact-canaries-pre.json" \
  --suite experiments/deepseek-v4-flash-reap-xpu-b70/quality/exact-canaries-v1.json \
  --out "$RUN_DIR/exact-canaries-pre-score.json"
```

The six ordered cases include `1073 -> 437 -> 1073`, exact copy, factual, and
strict JSON checks. Every row must be cache-zero.

Strict suite:

```bash
python scripts/bench-openai-realistic-suite.py \
  --base-url http://127.0.0.1:18080 --model deepseek-v4-flash-k160 \
  --suite repro/rapid-model-snapshots-b70/realistic-suite-v1.json \
  --max-tokens 128 --metric-tokens 100 --return-token-ids \
  --out "$RUN_DIR/strict-screen.json"
```

The 12-prompt public suite is a continuity screen. Deeper speculation
promotion requires the larger frozen held-out packs in
`quality/spec-eval-contract-v1.json`; public prompts alone do not prove against
overfitting.

## 8. LocalMaxxing

Instructions: `/home/steve/llm-optimizations/docs/localmaxxing.md`.

Credential: `/home/steve/.config/localmaxxing/api_key`. Never print, paste, or
commit it. Submission helper:

```bash
scripts/submit_localmaxxing_results.py \
  --payloads path/to/queue.json --label label-to-submit
```

Submit only when the result improves the matching GPU-count record, states one
active generation, includes model/revision/quantization/topology/commits/full
flags/hashes/evidence, passes exactness and `realistic_final_gate`, and uses
`primaryMetricName=median_tok_s_1_100_after_ttft`. Never submit warmed,
history-assisted, synthetic-only, or diagnostic results. The current approved
DeepSeek record is `cmrquta9905w3lg013m5vxoqx`.

## 9. Performance ladder and durable wins

- nonspeculative direct routed-MoE + wide epoch: about 43.77 tok/s;
- attached MTP and M2 target-fusion ladder: 50 -> 57 -> 60 -> 63.85 tok/s;
- official three-stage DSpark exact-M7 PIECEWISE: 64.66 tok/s;
- persistent Markov: 66.48 tok/s;
- W1-only replication: 67.50 tok/s;
- exact M8 batched compressors: 71.51 tok/s;
- M8 W8A16 + MXFP4 N128: 78.29 tok/s;
- native exact M8 router: 80.16 tok/s;
- sharded greedy target argmax + native rejection/commit: **80.82 tok/s**.

Reusable technical wins:

- fixed M4/M8 verifier MHC kernels pass genuine sequential tensors and 70
  graph replays on every B70;
- real content-addressed M2/M4/M8 corpora avoid many full model loads;
- exact identity and ordered changed-input gates caught rollover, dtype,
  graph-reuse, and stale-state bugs;
- offline-packed Xe2 BF16 DPAS makes real DSpark W2 output bit-exact and
  improves isolated W2 from 64.87 to 38.64 us;
- Level Zero IPC event handle brokering and one-shot transport were proven,
  though the endpoint architecture was rejected.

## 10. Major rejected paths: do not repeat

Read the named note before reopening a class.

### Submission-only fusions

- Fixed M8 input/block/slot builder: eager 194.3 -> 85.4 us, but captured
  33.974 -> 33.718 us; only 0.256 us survives.
- Finite oneCCL event chain: eager saves 5.6 ms, captured saves 0.110 ms.
- Lesson: graphs already amortize host submission. New work must delete
  device/collective work or an entire framework turn.

### Markov winner transport

- ordinary tiny oneCCL pair exchange regresses;
- padded pair exchange saves 6.4 us/cycle;
- raw remote-atomic IPC is unreliable;
- host barrier is fast in isolation but endpoint falls to 74.84/75.76 tok/s;
- one-shot device events cut transport to ~185 us and the local-base/DPAS M7
  bundle saves ~0.994 ms, but its eager boundary drops endpoint to
  **67.227723 tok/s**;
- event reset/reuse hangs and one-shot capacity is finite.

Do not retry transport that adds an eager/host synchronization boundary.

### MHC and communication

- generic TF32 DPAS M8 MHC is faster but changes target arithmetic and returns
  1053 instead of 1073;
- exact pair-tiled M8 MHC is slower;
- M1 and M8 MHC+RMS attempts are inexact and slower;
- in-ring/resident polling fails forward progress or repeated exactness;
- wide `[M,4096]` collectives corrupt output; retain segmented M2 collectives.

Latest closure: `notes/2026-07-18-m8-mhc-rms-fusion-closure.md`.

### Target LM head

Do not prioritize fused M8 target LM-head+argmax. The local BF16 head reads
252.5 MiB/rank and already takes about 0.452-0.454 ms near bandwidth roof. Its
local max is only ~0.009 ms and output traffic is ~517 KiB. Expected fused
saving is ~0.01-0.03 ms, with exact BF16-round-before-compare risk. The earlier
native argmax packer was itself slower (28.935 vs 25.530 us).

### Isolated wins that lost at endpoint

- width-aware split-FP8 attention looked 2.54-2.59 ms faster but endpoint fell
  to 72.46/73.40 tok/s;
- route-direct compact lost realistic route distributions;
- context-WKV fusion saved 0.611 ms locally but endpoint stayed ~64.25 tok/s;
- copy elision saved 0.076 ms and endpoint regressed;
- dual RMSNorm and several QNorm fusions did not survive full graph occupancy.

Never sum isolated savings into an endpoint claim. Use frozen same-binary B-A-B.

### Speculation

- repeating K160's one-layer MTP to M4 is rejected: third proposal acceptance
  is 0-3.2%, endpoint ~46.25 tok/s;
- DFlash/deeper speculation must not be selected from code-only/favorable
  prompts;
- TP2/TP4 aggregate throughput is irrelevant.

## 11. Current profile

The post-record eager target profile attributes roughly 27.0-27.6 ms/cycle of
noncollective work: routed MXFP4 ~7.19 ms, dense GEMM ~6.51, sparse QK/LSE
~3.54, MHC ~2.80, PV ~1.78, and pre-fusion router selection/sort ~1.06. The
eager Markov sampler was ~10.5 ms/cycle under instrumentation, but graph
wrapping did not remove its kernels or collective breaks.

The conclusion is architectural: we are not missing a flag. The remaining
large opportunity is a fixed-geometry, fixed-address target/speculative
decoder transaction—the Intel/SYCL/Level Zero analogue of HIPfire—where vLLM
remains loader/API/oracle but no longer owns every hot-loop boundary.

## 12. Immediate next work

### A. M7/M8 MoE activation portfolio (first)

This is the next untried captured-path boundary with a plausible >=0.50 ms
floor:

1. Extend existing shared-expert clamped-SwiGLU + FP8 activation quantization
   from record maximum M=2 to explicit allowed widths `{1,2,7,8}`.
2. Extend the exact routed clamp/SwiGLU selector from M=2 to explicit M=7/M=8.
3. Do not use a broad `<=8` guard; gate draft M7 and target M8 independently.
4. On every B70 require 40 changing eager and 32 changed fixed-address graph
   cases, exact FP8 values/scales, exact routed BF16 activations, and exact
   final target tokens. Preserve clamp-at-10 and BF16 rounding boundaries.
5. Existing M2 evidence gives a conservative non-overlapping floor of about
   0.514-0.546 ms/cycle; require >=0.50 ms on the slowest B70 before model load.
6. If it passes, run frozen same-binary B-A-B suites, unchanged acceptance and
   token IDs, cache-zero requests, and rollover canaries.

Source locations to inspect first:

- shared fusion selector:
  `vllm/models/deepseek_v4/xpu/model.py`;
- routed activation selector:
  `vllm_xpu_kernels/fused_moe_interface.py`.

### B. Exact DPAS W2 portfolio component (second)

Integrate exact BF16 DPAS W2 into the **incumbent captured collective Markov
path**, not the rejected event path:

- retain stable packed `local_w2.t().contiguous()` `[256,32320]` BF16/rank;
- replace only seven `torch.mm(..., out=local_bias)` calls with
  `deepseek_markov_m1_bf16_dpas_out(..., tiles_per_item=2)`;
- no graph break, event transport, or host barrier;
- require changed-input XPUGraph A-B-A, all four real shards/activations,
  bitwise BF16 outputs, gathered logits, seven IDs, and acceptance exact;
- optimistic ceiling is ~0.184 ms/cycle. Require >=0.15 ms across the complete
  captured seven-stage component before bundling into a service portfolio.

This may compound with A but is not a standalone path to 100 tok/s.

### C. Specialized decoder transaction

Continue Option 4 in
`../../plans/2026-07-16-deepseek-v4-flash-b70-100-200-tps-roadmap.md`:

- vLLM handles loading/API/prefill and remains exact oracle;
- content-addressed offline-packed per-rank weights;
- fixed persistent addresses and state-reset snapshots;
- hot-loadable modules keyed by source hash/ABI;
- fixed M1/2/4/8 primitives with real-tensor parity;
- producer/reduction/consumer communication ownership;
- device-resident DSpark prepare/sample/verify/accept/commit;
- no eager synchronization boundary;
- executable command cache keyed by addresses, shapes, verifier width,
  runtime identity, and model revision.

Reusable no-model assets:

- M2 corpus: 688 manifests, 1,030 deduplicated blobs, ~150 MiB, 70/70 replay;
- genuine sequential M4/M8 corpora in `/mnt/fast-ai/deepseek-v4-corpora/`;
- `scripts/replay-m2-cycle-corpus.py`;
- `scripts/benchmark-mwidth-cycle-corpus.py`;
- `scripts/run-mwidth-cycle-gate.sh`.

### D. Deeper speculation only after target economics

For 200 tok/s, compare emitted tokens per complete wall cycle under the frozen
anti-cheating evaluator. Candidate families may include DSpark extension,
DFlash/DEAGLE, or external draft, but do not invest until target verifier and
draft cycle costs are measured on the same frozen workload.

## 13. Agent orchestration rules

Parallelize bounded independent tasks: source audit, arithmetic/tie/NaN/alias
review, profile/result classification, harness construction, and doc/patch
review. The primary agent owns final edits, build, GPU/process safety, service
launch, exactness, classification, commits, and LocalMaxxing.

Do not let agents edit the same files concurrently. Inspect `git status`
before every edit/build; unexplained changes belong to another agent or user
and must be preserved. Report to the user only on a genuine record, major
architectural result, real blocker, or requested status; otherwise continue
through the ordered gate.

## 14. Documentation map

Read in order:

1. `/home/steve/AGENTS.md`
2. `/home/steve/llm-optimizations/AGENTS.md`
3. `/home/steve/llm-optimizations/CURRENT.md`
4. this file
5. `HANDOFF.md`
6. `results/experiment-ledger.md`
7. `../../plans/2026-07-16-deepseek-v4-flash-b70-100-200-tps-roadmap.md`
8. `quality/spec-eval-contract-v1.json`
9. note/data pair for any reopened boundary
10. `docs/localmaxxing.md` and `docs/local-ops.md` before submission or
    privileged/runtime work.

Key current notes:

- record: `notes/2026-07-18-sharded-target-argmax-record.md`;
- target profile/router closures:
  `notes/2026-07-18-m8-router-fusion-record-and-postrecord-closures.md`;
- event/DPAS closure:
  `notes/2026-07-18-dspark-m7-ipc-dpas-bundle-closure.md`;
- fixed builder closure:
  `notes/2026-07-18-fixed-m8-target-builder-closure.md`;
- latest MHC/RMS closure:
  `notes/2026-07-18-m8-mhc-rms-fusion-closure.md`;
- complete chronology: `results/experiment-ledger.md`.

Mistake audits live under `/home/steve/identified-mistakes/`. Secrets live
outside Git. Never print the Hugging Face token, LocalMaxxing key, or sudo
password.

## 15. Final current status

- Service stopped; GPUs free.
- Public record 80.820052 tok/s, LocalMaxxing
  `cmrquta9905w3lg013m5vxoqx`.
- Latest attempted M8 MHC+RMS rejected on card 0 as inexact and slower; no
  model load/submission.
- vLLM/XPU development experiments committed and clean; oneCCL retains only
  the expected untracked local build artifacts described above.
- Immediate next: M7/M8 shared+routed MoE activation portfolio.
- Then: exact DPAS W2 in the incumbent captured collective path.
- Strategic program: fixed-address Intel decoder plus frozen target-verified
  deeper-speculation evaluation.
