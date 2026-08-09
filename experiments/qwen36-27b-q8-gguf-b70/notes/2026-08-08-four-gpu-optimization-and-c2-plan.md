# Qwen3.6 27B Q8 four-GPU optimization and c2/32K plan

Date: 2026-08-08

Status: approved working plan; the c2 configuration and optimization results
below remain unvalidated until their stated gates pass.

## Decision

Optimize the pinned target-only Q8_0 model as four independent one-B70
processes. The primary service target is two 32K slots per process with F16 KV,
for up to eight cluster-wide requests:

- model: `unsloth/Qwen3.6-27B-GGUF` at revision
  `82d411acf4a06cfb8d9b073a5211bf410bfc29bf`;
- artifact: `Qwen3.6-27B-Q8_0.gguf`, SHA-256
  `f93f517f38e696d35a1a7df2c0e3155a64f4c4dcd662107a146ae263f7fb14ce`;
- one process and one B70 per lane;
- primary KV identity: F16 K and F16 V;
- primary context identity: `-c 65536 -np 2`, or 32,768 tokens per slot;
- no prompt/response cache, MTP, projector, or reasoning parser;
- `GGML_SYCL_ENABLE_DNN=0`, `GGML_SYCL_ENABLE_OPT=1`, graph disabled;
- full `65/65` GPU layer offload is mandatory.

BF16 KV has the same two-byte capacity cost as F16 and creates a new numerical
identity. In the pinned source, the oneDNN attention fast path accepts F16 but
not BF16. BF16 therefore gets only a later, isolated A/B if profiling supplies
a concrete reason to expect a win. It is not a primary lane.

Vision is deferred until the text build and context/concurrency envelope are
settled. MTP is also deferred: ordinary c2 concurrency is simpler and addresses
the requested workload first. Q8 KV at 100K--128K remains an optional capacity
study, not an immediate optimization target.

## Why c2 comes first

The current exact runtime already contains the public Q8 reorder optimization.
The local `OPT=1` baseline measured `15.55 tok/s`, while a broader
`DNN=1,OPT=0` control measured `5.03 tok/s`. Source dispatch and that roughly
3.09x gap strongly suggest that the reorder stack is the major banked win, but
this was not a clean one-variable attribution. The same reordered Q8 MMVQ path
has explicit multi-column support for two through eight columns. Two
simultaneous slots can therefore create a useful M=2 target shape and
potentially amortize weight traffic across both requests.

The retained device model buffer is 25,972.29 MiB, or approximately 27.234
decimal GB, and includes both Q8 and non-Q8 tensors. Multiplying it by the
validated `15.550257 tok/s` gives an implied 423 GB/s byte-rate heuristic.
This is neither a physical bandwidth measurement nor a strict lower bound:
cache reuse and the bytes actually touched per step remain unmeasured. It still
makes weight reuse and Q8 load layout the first places to look. PCIe is not in
the bulk per-token model-weight read path after full model offload.

Measured-memory modeling predicts the c2/F16/32K server at approximately
30,570 MiB resident, leaving about 1,879 MiB. That is enough to attempt the
configuration but too tight to infer success from arithmetic. Both slots must
be filled and decoded concurrently before c2 is called a fit.

## Numeric objectives

These are research targets, not permission to weaken correctness gates:

1. Establish the missing isolated full-512 c1 reference and then reach at least
   `17.0 tok/s` on the conventional 99-interval primary window. The validated
   128-token reference is `15.550257 tok/s`, so this is a 9.3% first milestone.
2. Call c2 useful only if a correct two-request run reaches at least
   `24 aggregate output tok/s` per card, each request remains at or above
   `9 tok/s`, and the per-request rate fairness ratio is at least `0.90`.
   Retain the complete frontier even if it misses these provisional thresholds.
3. For the final four-service/eight-slot test, retain at least 90% of the sum
   of four isolated c2 results. Diagnose host, power, cooling, and I/O pressure
   before changing model code if the cluster misses this efficiency target.
4. A source candidate needs at least a 1% isolated paired improvement with its
   paired 95% interval above zero for promotion. Two normalized screens below
   0.5% close the idea unless new evidence changes its expected ceiling.

## Locked c2 runtime identity

The intended initial server arguments are:

```text
-c 65536 -np 2 --no-kv-unified --cont-batching
-b 1024 -ub 128 -ctk f16 -ctv f16 -fa on -ngl 99
-t 8 --poll 50 -lv 4
--cache-ram 0 --ctx-checkpoints 0 --spec-type none --reasoning off --jinja
```

The launcher must also force and record:

```text
GGML_SYCL_ENABLE_VMM=1
GGML_SYCL_ENABLE_GRAPH=0
GGML_SYCL_ENABLE_DNN=0
GGML_SYCL_ENABLE_OPT=1
```

Keep the model, exact Jinja/chat-template behavior, seed, sampler, microbatch,
oneAPI 2026.0 toolchain, driver, and all other selectors fixed during the first
source comparisons. Every native request must set `cache_prompt:false`. Do not
upgrade the system driver or toolchain inside this lane; those are separate
maintenance A/B identities.

Before requests, require the server log to attest all of the following:

- `n_ctx = 65536` total;
- `n_ctx_seq = 32768` per slot;
- `n_seq_max = 2`;
- non-unified KV and continuous batching;
- F16 K and F16 V, with an expected 4,096 MiB KV allocation;
- approximately 299 MiB recurrent-state allocation;
- `65/65` layers offloaded to the selected B70;
- at least 1,024 MiB reported free VRAM after readiness.

Any silent context reduction, CPU layer fallback, selector drift, or lower
post-load reserve rejects the run.

## Phase 0: make the benchmark trustworthy

The current `RUN_SCOPE=full` still asks for only 128 output tokens. Do not
rename or reinterpret it as a promotion run. Add a distinct `promotion512`
scope and a native exact c2 harness before optimization timing.

The harness work must provide:

1. Explicit slot count, total context, KV type, unified-KV, and continuous-
   batching inputs in the launcher and retained identity.
2. A fixed 12-prompt, 512-token c1 suite. Stream every timed prompt once before
   running any non-streaming replay, then require complete replay/token/content
   exactness. If exact length requires ignoring EOS, preregister that request
   setting and use it unchanged in every control and treatment.
3. A c2 barrier that releases two distinct requests together and proves both
   slots overlap through server slot state, retained runtime markers, or both.
4. Separate sealed c1/F16/32K/512 and c2/F16/32K-per-slot/512 oracles. First
   capture c2 requests sequentially on the c2 server, then compare concurrent
   requests with that c2 oracle. Compare c1 and sequential-c2 hashes separately
   without weakening either identity contract. Pin the sequential oracle and
   canary requests explicitly to native `id_slot:0` and `id_slot:1`, and use the
   preregistered fresh-start/slot-clear procedure before cold comparisons.
5. A 512-token response followed immediately by the known 128-token canary on
   each slot. This catches request-boundary state contamination that a short
   smoke can miss.
6. Synthetic unit checks for timing formulas and synchronized-client failure
   handling. Client processes must be tracked and torn down before servers.
7. Unique alignment of streamed token IDs to the complete non-stream replay,
   covering the runtime's known incomplete-UTF-8 SSE suppression case. Require
   observable timing endpoints for generated positions 1, 100, and 512. If
   position 512 has no stream event, reject the full-512 timing claim rather
   than assuming 512 SSE events.

For each request, retain:

- primary decode: `99 / (timestamp(token 100) - timestamp(token 1))`;
- TTFT: `timestamp(token 1) - request_start`;
- full conventional decode: `511 / (timestamp(token 512) - timestamp(token 1))`;
- full-after-TTFT compatibility rate: `512 / (request_end - timestamp(token 1))`;
- request-wall rate: `512 / (request_end - request_start)`;
- native prompt/decode timings, prompt and output counts, cache counts, stop
  status, rendered-prompt/content/token hashes, and all event timestamps.

The generic OpenAI realistic-suite helper's existing `100 / duration` field is
not the headline metric and must not be used unmodified for this lane.

## Phase 1: establish the reference and toolchain

The archived binary and gitless restored tree remain immutable controls. The
same exact commit, `15586e2d7165570fb3aa7c26e0d442e289ef69de`, exists in the
clean clone `/home/steve/src/llama.cpp-community-pr14-20260801`; all 3,333
tracked source blobs match the archive. Create detached worktrees from that
clone and never modify the protected dirty `/home/steve/src/llama.cpp`.

Run this initial bring-up sequence:

| Initial card | Work | Evidence class |
| --- | --- | --- |
| GPU 0 | Archived binary, isolated c1/F16 full-512 control and sealed oracle | Official baseline only while GPUs 1--3 are idle |
| GPU 1 | Clean rebuild of the exact pinned commit with matching flags and toolchain | Rebuild reproducibility; parallel timing diagnostic |
| GPU 2 | Exact-commit profiling build with bounded SYCL operation/cycle markers | Attribution only; never a headline score |
| GPU 3 | Archived binary c2/F16/32K fit and two-live-slot correctness | Functional and aggregate-service evidence |

The isolated GPU-0 timing happens in a quiet window. The other three cards can
then run their functional work concurrently. After the first wave, card roles
rotate so no physical card is permanently the control or treatment.

Also freeze and build the current upstream llama.cpp HEAD under the same
oneAPI and selector identity. If it wins, isolate the responsible commits
instead of crediting the complete upstream delta. Two immediately relevant
upstream changes are the SSM-convolution coalescing path and the flat split-GLU
path, but their endpoint effect on this Q8 model remains unmeasured.

## Phase 2: four parallel optimization lanes

Use one detached source worktree, build directory, port, run directory, and
binary manifest per lane. The starting assignments rotate between waves:

| Lane | Primary question | First candidates |
| --- | --- | --- |
| A | Can two live slots amortize Q8 weight reads? | Prove M=2 reordered-Q8 entry counts; tune multi-column MMVQ and scheduler batching |
| B | Do newer recurrent/elementwise paths help? | Current upstream, then isolate SSM-convolution and split-GLU changes |
| C | What limits single-request Q8 decode? | Profile actual M=1 Q8 shapes; test narrowly gated load/coalescing, DP4A, and workgroup changes |
| D | What limits long prefill and attention? | Verify oneDNN/MKL/TILE FA dispatch; test only exact, narrow prefill treatments |

Do not build or load a model during a timed comparison. Worktrees and builds
may live under `/dev/shm` for speed, but that storage is volatile: preserve each
meaningful patch, build identity, and result in this experiment lane immediately.
Archive any winning source/build needed for replay to the USB model store.

Every candidate goes through the same funnel:

1. Static/build/unit tests and a runtime entry marker proving treatment.
2. One-prompt 128-token exact smoke.
3. Full 12-prompt 128-token exact gate.
4. One 512-token canary plus the following-request canary.
5. Full 12-prompt 512 screen for survivors.
6. c2 paired-request screen for any batching, Q8, recurrent, attention, graph,
   allocation, or scheduler change.

Four candidates may be screened simultaneously, but those rates are labeled
`parallel-screening` and are not promotion scores. Compare each candidate with
the pinned control on the same physical GPU using control--candidate--control
bracketing. Reverse assignment and start order in the next wave. A survivor
must reproduce on a second card.

## Phase 3: c2/F16/32K validation

The first c2 gate uses the pinned control before any c2-specific optimization:

1. Start the locked c2 server and validate fit/log identity.
2. Capture two distinct requests sequentially on that same c2 server.
3. Release the same two 512-token requests behind one barrier, prove slot
   overlap, require zero cache reuse and no truncation, and compare each output
   exactly with its sequential c2 oracle.
4. Reverse request order and repeat.
5. Run the fixed 12-prompt suite as six synchronized two-request waves, with
   each prompt measured once per fresh run.
6. Fill both slots with distinct near-31.8K retrieval prompts and generate 128
   or 512 tokens within the declared per-slot limit. Both needles and exact
   structured answers must pass.
7. Test slot turnover, a 512-token response followed by the known canary on
   each slot, and long-prefill-plus-concurrent-decode scheduling.

Report aggregate throughput as total generated tokens divided by barrier-to-
last-completion time. Also report each request's TTFT and three decode rates,
queue delay, overlap duration, makespan, min/max fairness ratio, c2/c1 aggregate
gain, and per-request latency cost. Functional fit and useful performance are
separate verdicts.

## Phase 4: isolated promotion and final four-service test

Promote only from a quiet one-card window with the other three cards idle:

- fresh-start B--A--B or A--B--A on the same card;
- paired prompt-level analysis and a 95% interval;
- confirmation on a second isolated card;
- exact 128- and 512-token gates, next-request canary, 32K retrieval, c2 gates
  when applicable, full offload, and clean teardown;
- no material regression in p10, TTFT, full-512 rate, request-wall rate,
  prefill, long-context decode, c2 aggregate rate, or fairness.

After selecting a final build, stagger-load four independent c2 servers and
release eight distinct requests together. This is a
`four-service/eight-slot aggregate` result, not a single-GPU speed record.
Require all eight outputs exact, all cache counts zero, all slots live, clean
turnover, no faults, and at least 90% cluster efficiency relative to the sum of
four isolated c2 measurements.

## Resource and evidence controls

- Resolve and record each GPU ordinal to a distinct BDF and UUID before launch;
  force one visible device per process and retain the mapping.
- Require selected GPUs below 256 MiB before load. For four-process work,
  require at least 96 GiB host `MemAvailable`, no growing swap, and no material
  memory-pressure stalls; use at least 32 GiB as the isolated-run floor.
- Stagger the four USB-backed model loads and wait for storage activity to
  settle before requests.
- Discover the CPU topology, then pin server and load-generator work to
  disjoint physical cores. Do not hardcode an unverified topology.
- Record model/source/binary hashes, dirty patch hash, toolchain and dynamic
  libraries, driver/runtime packages, full argv/environment, context/slot/KV
  identity, GPU identity, loaded/peak/final VRAM, and raw logs.
- Keep official timed runs free of unvalidated polling overhead. Existing
  XPU-SMI PCIe counters have returned zero on this host, and polling can perturb
  tight workloads. Use pre/post health samples and a separate 1 Hz shadow
  telemetry run; accept in-run telemetry only after a same-state control shows
  at most 2% observer effect.
- Seal every packet with `artifacts.sha256` and explicit boolean gates. Keep
  negative and inconclusive patches instead of overwriting them.
- Submit a result to LocalMaxxing only after it beats the matching GPU-count,
  model, quantization, mode, and concurrency record and the complete promotion
  packet passes.

Stop the complete four-card wave on OOM, device loss, reset, hang, xe fault,
PCIe AER, RAS increment, forced teardown, unexpected process/GPU activity,
sustained throttling, cache reuse, truncation, output/replay mismatch,
retrieval failure, or failure to prove two-slot overlap. Do not automatically
reload the driver and continue the remaining lanes after a device wedge.

## Explicitly deferred or closed work

- Global DNN remains rejected: it preserved decode speed but produced
  deterministic greedy-replay failures. A narrow localization experiment may
  be useful later, but DNN is not an optimization lane until the faulty
  boundary is identified.
- BF16 KV is deferred because it saves no memory and appears to lose the F16
  attention route.
- Generic graph replay is low priority; historical Qwen GGUF graph work was
  neutral or slightly slower. Allow one bounded exact c1 screen only after
  profiling supplies a plausible ceiling.
- Forced DMMV, row splitting, the old ESIMD float prototype, Q4 subgroup/VDR
  sweeps, and TP/all-reduce work are closed for this target.
- Do not port Q4 flags whose `Q8` name referred to Q8_1 activations feeding Q4
  weights; they are not Q8_0 target-weight optimizations.
- Vision, integrated MTP, and Q8-KV 100K--128K capacity remain separate future
  identities after the text c2 frontier is established.

## Immediate execution order

1. Extend the launcher and exact harness for `promotion512` and c2.
2. Seal the isolated c1/F16/32K full-512 baseline.
3. Rebuild the pinned commit exactly and freeze a current-upstream comparison.
4. Validate pinned-runtime c2/F16/32K fit, correctness, retrieval, turnover,
   and aggregate usefulness on one card.
5. Build the profiling lane and prove which Q8/attention/recurrent paths run.
6. Start the four parallel source screens, rotate assignments, and promote only
   isolated survivors.
7. Validate the final build as four c2 services/eight slots.

No optional artifact download, driver change, MTP experiment, vision test, or
Q8-KV capacity climb is on the critical path above.
