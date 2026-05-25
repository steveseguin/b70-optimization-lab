# MiniMax XPU CPU KV Offload Plan

Date: 2026-05-24

Goal: make CPU KV movement work on Intel Arc Pro B70/XPU for MiniMax M2.7 and
determine which long-context targets are achievable without lowering quality.
The current evidence separates two tracks:

- Exact-quality session swapping for contexts that individually fit in GPU KV.
- True active-context overflow beyond GPU KV, which requires attention/runtime
  work beyond scheduler-only CPU KV offload.

Primary reference:

`experiments/minimax_xpu_kv_offload/README.md`

## Ground Rules

- Keep `/home/steve/bin/minimax-vllm-serve` defaulting to the stable `32768`
  context recipe unless explicitly testing.
- Any long-context server must run as a temporary experiment with logs under
  `/mnt/fast-ai/bench-results/minimax-m27-b70-serve/`.
- Do not promote FP8 KV, TurboQuant, speculation, or model-weight changes as
  quality-equivalent without gates.
- Start with concurrency 1. Only test c2/c4 after c1 works and can be restored
  cleanly.
- Prefer adding XPU-specific worker code beside CUDA code over weakening
  CUDA-only assumptions in place.

## Current Known State

Stable endpoint:

- `max_model_len=32768`
- `max_num_seqs=1`
- FP16-family KV via `--kv-cache-dtype auto`
- warm endpoint decode about `84-95 tok/s`, depending on warm state and
  benchmark shape

XPU CPU KV prototype:

- `49152`/c1 can start with `--kv-offloading-size 16`.
- GPU KV allocation remains about `33792` tokens (`132` blocks at block size
  `256`).
- Multi-GB GPU-to-CPU and CPU-to-GPU KV transfers work.
- A `33350` token prompt (`131` blocks) plus one output token completed with
  the connector present.
- A `33580` token prompt (`132` blocks) plus one output token timed out and
  parked at `131/132` GPU KV blocks used.
- `32768`/c2 can start with `--kv-offloading-size 16`.
- c2 session-cache smoke passed for two distinct `14000`-token prompts,
  including later CPU-to-GPU reload at about `15.0 GB/s`.

Conclusion: the current path is not true active-context overflow. Exact full
attention still requires the active request's KV blocks to fit in GPU memory.
See
`experiments/minimax_xpu_kv_offload/notes-20260525-phase4-active-context-limit.md`.
The useful near-term path is exact session caching; see
`experiments/minimax_xpu_kv_offload/notes-20260525-phase5-session-swap-smoke.md`.

Failed long-context experiments:

- CPU weight offload hit `AssertionError: CPU tensor must be pinned`.
- Native `--kv-offloading-size 64` was accepted but preflight still counted
  only GPU KV.
- Temporary preflight patch let `196608`/c4 reach `OffloadingConnector`.
- Worker-side native CPU KV offload then failed with:

```text
CPU Offloading is currently only supported on CUDA-alike GPUs
```

Reason: the current native CPU KV worker uses CUDA streams, CUDA events,
`cudaHostRegister`, and CUDA-style copy handling.

## Phase 0: Preserve Baseline

Deliverable: prove the production path still works before touching offload.

Checklist:

- Confirm `/v1/models` reports `max_model_len=32768`.
- Run a short endpoint decode check and record output tok/s.
- Save current vLLM diff for files likely to be touched.
- Keep a restore command in every experiment note:

```bash
pkill -f 'vllm serve' || true
VLLM_MAX_MODEL_LEN=32768 /home/steve/bin/minimax-vllm-serve
```

Pass condition:

- Restored server reaches `/v1/models`.
- Warm short decode is in the expected `83-86 tok/s` band.

## Phase 1: XPU Primitive Probe

Deliverable: determine whether PyTorch XPU exposes enough primitives to port
the CPU KV worker.

Status: initial small-transfer probe passed on 2026-05-24. See
`experiments/minimax_xpu_kv_offload/notes-20260524-phase1-probe.md`.

Questions:

- Does `torch.xpu.Stream` exist and support stream contexts?
- Does `torch.xpu.Event` exist and support timing/synchronization?
- Does `torch.xpu.current_stream()` exist?
- Do async CPU-to-XPU and XPU-to-CPU copies work with pinned CPU tensors?
- Can pinned CPU memory be allocated reliably at larger scales later?

Suggested artifact:

`experiments/minimax_xpu_kv_offload/probes/xpu_stream_copy_probe.py`

Minimal tests:

- Allocate pinned CPU tensor.
- Allocate XPU tensor.
- Copy CPU -> XPU on an XPU stream.
- Copy XPU -> CPU on an XPU stream.
- Synchronize and verify bytes.
- Start with small sizes while the 32K server is running.
- Record measured GB/s if events/timers work.

Pass condition:

- Correct round-trip data.
- Stable transfers.
- No process hangs or driver resets.

## Phase 2: CPU KV Worker Design

Deliverable: design an XPU backend parallel to the CUDA CPU KV worker.

Status: initial KV-shaped block-copy probe passed on 2026-05-24, and a first
XPU worker prototype was live-tested on 2026-05-25. Contiguous logical slice
copies are byte-correct and reach about `28 GB/s`; Python row loops are
correct but slow. The live worker can move multi-GB KV payloads through vLLM,
but long prompt generation is still blocked in scheduler/accounting. See:

- `experiments/minimax_xpu_kv_offload/notes-20260524-phase2-block-copy-probe.md`
- `experiments/minimax_xpu_kv_offload/notes-20260525-phase3-xpu-worker-live-server.md`

Files to study:

- `vllm/v1/kv_offload/cpu/spec.py`
- `vllm/v1/kv_offload/cpu/gpu_worker.py`
- `vllm/v1/simple_kv_offload/worker.py`
- `vllm/v1/simple_kv_offload/copy_backend.py`
- `vllm/v1/worker/gpu_model_runner.py`

Likely design:

- Keep `CPUOffloadingSpec` as the scheduler-facing path.
- Add an XPU handler implementation, for example:
  `vllm/v1/kv_offload/cpu/xpu_worker.py`.
- In `spec.py`, route `current_platform.is_xpu()` to the XPU worker.
- Avoid CUDA host registration. Start with PyTorch pinned host tensors.
- Use XPU stream/event primitives if they pass Phase 1.
- If no XPU stream support exists, start synchronous and measure correctness
  first; optimize later.

Pass condition:

- vLLM can initialize CPU KV offload handlers on XPU without rejecting the
  platform.
- Done for startup: `49152` c1 reaches `/v1/models`.
- Not done for correctness: long prompts above GPU-only KV capacity do not yet
  return completions.

## Phase 3: Admission And Capacity

Deliverable: make vLLM count CPU KV offload capacity during startup in a way
that does not break normal GPU-only serving.

Status on 2026-05-25: startup admission is partly solved for the experiment.
The current patch adds CPU KV bytes only to the max-context preflight check and
does not inflate GPU KV allocation. At `49152` c1 with
`--kv-offloading-size 16`, vLLM reports about `33792` GPU KV tokens and starts
successfully.

Starting point:

`experiments/minimax_xpu_kv_offload/patches/kv-offload-admission-check-xpu-experiment-20260524.patch`

Improve the patch:

- Account for per-rank CPU KV offload capacity cleanly.
- Preserve GPU-only behavior exactly.
- Log GPU KV capacity and CPU KV offload capacity separately.
- Avoid overclaiming max context if CPU offload blocks are insufficient.

Initial contexts:

- `49152`, c1
- `65536`, c1
- `98304`, c1
- `131072`, c1
- `196608`, c1 only after smaller contexts work

Pass condition for this phase:

- Server reaches `/v1/models` at a context above `32768`.
- The experiment clearly distinguishes advertised max model length from the
  active GPU-resident exact context limit.

Status:

- Startup passes at `49152`.
- Active exact context beyond the GPU KV block budget is blocked by the
  attention runtime model, not by raw CPU/XPU copy mechanics.
- Do not claim `49152+` active context support from scheduler-only offload.

## Phase 4: Correctness And Quality

Deliverable: prove offloaded/reloaded KV produces the same answers as GPU KV
for cases where the active sequence still fits in GPU memory.

Status on 2026-05-25: c2 session caching passed the strongest constrained
canary so far; c4 remains experimental. Free-form longer concurrent completions
do not produce exact text-hash matches across passes, but strict-word c2 matched
the GPU-only baseline by expected first word and exact output hash. Strict-word
c4 produced the expected first word for A/B/C/D, but one c4 pass added an extra
continuation token after the correct word.

Test ladder:

- 32K GPU-only baseline canaries.
- 32K with CPU KV offload enabled but under capacity.
- Largest GPU-resident prompt with deterministic small output.
- Session-swap canary: store a session to CPU, reload it, then compare its next
  deterministic token against the GPU-only path.
- Semantic/arithmetic/sixpack at the largest working context.

Metrics to record:

- Exact token hashes when deterministic.
- Generated text snippets for human inspection.
- Rejection/failure count.
- Any NUL/control token incidents.
- TTFT and e2e latency.

Pass condition:

- No quality regression at 32K with offload enabled.
- No corruption after CPU store/reload when the active context fits in GPU KV.

## Phase 5: Performance Characterization

Deliverable: map GPU-resident context length, session swapping, and offload
pressure to decode speed.

Benchmark shapes:

| Shape | Purpose |
| --- | --- |
| p512/n512 | decode sanity and warmup |
| p512/n1536 | compare to existing endpoint metrics |
| p32768/n64 | near-current-full-context prompt |
| p33350/n1 | near effective GPU block limit under the 49K/offload server |
| p32768/n64 with c2 swapping | first practical session-swap pressure |
| p32768/n512 with c2 swapping | sustained decode after reload |
| p49152/n64 | active-overflow R&D only, expected blocked today |
| p196608/n64 | future kernel/runtime R&D target |

Record:

- output tok/s
- total tok/s
- TTFT
- prefill lower bound or exact prefill if available
- peak VRAM
- CPU RAM used for KV offload
- PCIe transfer throughput if measurable

Pass condition:

- A reproducible table showing where offload becomes bandwidth-bound.

## Phase 6: Concurrency / Session Swapping

Deliverable: measure exact-quality session swapping after c1 store/reload is
stable. This is not the same as four active `196608` contexts.

Status on 2026-05-25:

- Initial c2 smoke passed with two distinct `14000`-token prompts.
- First pass stored about `4.29 GB` GPU-to-CPU.
- Second pass reloaded about `7.02 GB` CPU-to-GPU in `0.467 s`.
- A reusable canary script now exists at
  `experiments/minimax_xpu_kv_offload/scripts/session_cache_canary.py`.
- c2 longer reload decode worked with two `16134`-token prompts and `128`
  output tokens. Second-pass reload returned in `2.785 s` per request, about
  `60 tok/s` after TTFT per request.
- c2 CPU-to-GPU KV movement measured about `13.9 GB/s`.
- c4 smaller-context reload worked with four `9234`-token prompts and `64`
  output tokens. Second-pass reload returned in `1.6-2.6 s` per request, about
  `52-79 tok/s` after TTFT per request.
- c4 CPU-to-GPU KV movement measured about `15.8 GB/s`.
- c4 first compile exposed an Intel `ocloc` / IGC internal compiler error
  before fallback compilation completed; the cached rerun started normally.
- Strict-word c1 CPU-offload and c2 matched GPU-only baseline by expected word
  and exact output hash.
- Strict-word c4 matched expected first words for all labels, but one pass added
  an extra continuation token after the correct word.
- Exact c4 text hashes are not stable enough yet for production quality claims.
  See
  `experiments/minimax_xpu_kv_offload/notes-20260525-phase6-session-cache-canaries.md`.
- c2 capacity ladder passed first-word correctness at about `8K`, `16K`, `21K`,
  `30K`, and `32.5K` prompt tokens per session with two concurrent sessions.
- The largest c2 ladder shape used two `32474`-token prompts, `64948` combined
  prompt tokens against a `34304` GPU KV budget.
- A fresh cold near-max c2 run had first-pass TTFT of `24.758-48.363 s` and
  second-pass reload TTFT of `0.668-1.232 s`.
- CPU-to-GPU reload bandwidth measured about `14-15 GB/s`.
- Detailed c2 ladder note:
  `experiments/minimax_xpu_kv_offload/notes-20260525-c2-session-cache-ladder.md`.

Order:

1. c2 at `32768`, one active session at a time.
2. c4 at `32768`, one active session at a time.
3. c2 at the largest active context that still fits in GPU KV.
4. c4 at the largest active context that still fits in GPU KV.
5. `65536+` only after true CPU-paged attention or quality-gated KV
   compression exists.

Record both:

- total generated tok/s across all sessions
- per-session tok/s

Pass condition:

- No hangs, request starvation, or process crashes.
- Clear expected-use recommendation, even if throughput is low.

Current recommendation: c1 `32768` remains the production endpoint. c2
session-cache behavior is the strongest experimental lane: it now reloads two
near-32K sessions with matching first-word canaries and about `0.7-1.3 s`
near-max reload TTFT. c4 mechanically works and is fast on reload, but it needs
a tighter token-level or semantic quality gate before use.

## Phase 7: TurboQuant And Compressed KV

Deliverable: revisit compressed KV once the offload path can run.

Status on 2026-05-25:

- `turboquant_k8v4` originally failed first decode with a locked-workspace
  assertion in `_decode_attention`.
- A local experiment patch added locked-workspace fallbacks in
  `_decode_attention` and `_continuation_prefill`.
- Patch artifact:
  `patches/vllm-turboquant-xpu-workspace-fallback-20260525.patch`.
- With `max_model_len=32768`, TurboQuant reported `80128` GPU KV tokens and
  `2.45x` max concurrency for a 32K request.
- Strict-word canaries passed at about `8K` and `32.5K` prompt tokens.
- Sustained decode at `24874` prompt tokens was only about `16.5 tok/s` after
  TTFT, far below the normal FP16-family KV lane.
- `max_model_len=65536` failed with vLLM estimating a maximum model length of
  `60672`.
- `max_model_len=60000` started and passed a `58874` token strict-word canary,
  but TTFT was about `53-54 s` and decode was not interactive.
- Intel `ocloc` / IGC error 245 still appears during compile fallback.
- Detailed note:
  `experiments/minimax_xpu_kv_offload/notes-20260525-c2-quality-and-turboquant.md`.
- With `turboquant_4bit_nc`, `max_model_len=100000`, c4, and
  `--kv-offloading-size 32`, vLLM reported `84654` GPU KV tokens and `0.85x`
  max concurrency for a 100K request.
- That 100K/c4 server answered strict-word prompts at `84074` and `84374`
  tokens, but timed out or parked around `84644+` tokens because live GPU KV
  blocks were exhausted.
- With `turboquant_4bit_nc`, `max_model_len=196608`, c1,
  `--max-num-batched-tokens 512`, and `--gpu-memory-utilization 0.959`, vLLM
  reported `98304` GPU KV tokens and `0.50x` max concurrency for a 196K
  request.
- The 196K/c1 server answered an `84074` token strict-word prompt, but TTFT was
  `114.342 s`. A near-limit prompt around `97800` tokens filled GPU KV
  (`kv_cache_usage=1.0`) and killed the engine with
  `TimeoutError: RPC call to sample_tokens timed out`.
- Detailed active-boundary note:
  `experiments/minimax_xpu_kv_offload/notes-20260525-turboquant-active-context-boundary.md`.

Work items:

- Keep TurboQuant bug repro current.
- Replace the temporary allocation fallbacks with a cleaner workspace
  pre-growth or capture-safe allocation strategy.
- If it runs, compare FP16-family KV, FP8 KV, TurboQuant k8v4, and TurboQuant
  4-bit variants, but keep every compressed-KV result labeled experimental
  until quality gates pass.
- Always run quality gates before accepting any compressed KV result.

Pass condition:

- Compressed KV either has a documented quality-preserving recipe or remains
  clearly labeled as blocked/experimental.

Current recommendation: keep TurboQuant as a research lane. It is useful for
proving that compressed KV can lift the live KV ceiling, but it is too slow,
too unstable near the limit, and too narrowly quality-gated for production. It
also does not solve true active-context overflow because the active request must
still fit in live GPU KV blocks.

## Phase 8: True Active-Overflow Runtime Work

Deliverable: determine whether a CPU-paged or CPU-streamed XPU attention path
can execute one active sequence larger than live GPU KV capacity without
changing model semantics.

Status on 2026-05-25:

- Scheduler admission and CPU KV transfer are no longer the main blocker.
- The runtime still needs live GPU KV blocks for the active request.
- TurboQuant 4-bit NC lifted the best observed active capacity to `98304`
  tokens, but this is still only half of one full `196608` MiniMax context.
- Four active full-context sessions would need `786432` active tokens, about
  `8x` the best observed live active capacity.

Work items:

1. Trace the XPU attention backend entry points that consume block tables and
   KV cache tensors.
2. Add instrumentation to record required layer/block ranges per prefill and
   decode step.
3. Prototype a synchronous "load required CPU block range into GPU scratch,
   run attention, evict" path for a tiny context just over the GPU limit.
4. Run strict-word canaries against the GPU-only baseline for any context that
   still fits, then a small over-limit context.
5. Only after correctness works, optimize with XPU streams, range coalescing,
   and prefetch.
6. Keep `32768` production serving separate from this R&D branch.

Expected output:

- A design note naming the exact attention/runtime files that must change.
- A minimal synchronous prototype or a concrete blocker explaining why the
  current XPU attention kernels cannot consume staged CPU KV.
- Strict-word canary results before any performance claims.
