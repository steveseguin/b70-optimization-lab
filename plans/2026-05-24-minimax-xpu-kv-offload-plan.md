# MiniMax XPU CPU KV Offload Plan

Date: 2026-05-24

Goal: make CPU KV offload work on Intel Arc Pro B70/XPU for MiniMax M2.7 so
the system can serve contexts beyond the current reliable `32768` token
endpoint, while preserving answer quality and keeping the 32K fast lane easy
to restore.

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
- warm endpoint decode about `84-85 tok/s`

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

Pass condition:

- Server reaches `/v1/models` at a context above `32768`.
- It can complete a near-full-context prompt plus small output without OOM.

Current blocker:

- The first condition passes at `49152`.
- The second condition is blocked. The transfer path works, but the scheduler
  does not yet resume/generate correctly after CPU spill reload.

## Phase 4: Correctness And Quality

Deliverable: prove offloaded KV produces the same answers as GPU KV for cases
where both can run.

Test ladder:

- 32K GPU-only baseline canaries.
- 32K with CPU KV offload enabled but under capacity.
- 49K/65K near-full prompt with deterministic small output.
- Semantic/arithmetic/sixpack at the largest working context.

Metrics to record:

- Exact token hashes when deterministic.
- Generated text snippets for human inspection.
- Rejection/failure count.
- Any NUL/control token incidents.
- TTFT and e2e latency.

Pass condition:

- No quality regression at 32K with offload enabled.
- No corruption in near-full long-context tests.

## Phase 5: Performance Characterization

Deliverable: map context length and offload pressure to decode speed.

Benchmark shapes:

| Shape | Purpose |
| --- | --- |
| p512/n512 | decode sanity and warmup |
| p512/n1536 | compare to existing endpoint metrics |
| p32768/n64 | near-current-full-context prompt |
| p49152/n64 | first offload pressure |
| p65536/n64 | practical long-context target |
| p65536/n512 | sustained decode with offload |
| p196608/n64 | full advertised context smoke |

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

## Phase 6: Concurrency

Deliverable: measure active session scaling after c1 is stable.

Order:

1. c2 at `32768`
2. c2 at first offloaded context that works
3. c4 at `32768`
4. c4 at `65536`
5. c4 at `196608` only if lower targets are stable

Record both:

- total generated tok/s across all sessions
- per-session tok/s

Pass condition:

- No hangs, request starvation, or process crashes.
- Clear expected-use recommendation, even if throughput is low.

## Phase 7: TurboQuant And Compressed KV

Deliverable: revisit compressed KV once the offload path can run.

Known TurboQuant blocker:

- `turboquant_k8v4` reports much better KV capacity but first completion fails
  with a workspace-lock assertion.

Work items:

- Keep TurboQuant bug repro current.
- Test whether workspace allocation can be pre-grown before locking.
- If it runs, compare FP16-family KV, FP8 KV, TurboQuant k8v4, and TurboQuant
  4-bit variants.
- Always run quality gates before accepting any compressed KV result.

Pass condition:

- Compressed KV either has a documented quality-preserving recipe or remains
  clearly labeled as blocked/experimental.

## Suggested Next Session

Start with Phase 1. Do not begin by modifying vLLM.

Concrete first task:

1. Create `experiments/minimax_xpu_kv_offload/probes/xpu_stream_copy_probe.py`.
2. Run it under `/home/steve/.venvs/vllm-xpu/bin/python`.
3. Record whether XPU streams/events and pinned CPU copies work.
4. If primitives work, sketch `xpu_worker.py`.
5. If primitives do not work, document the missing PyTorch/Level Zero feature
   and switch to a synchronous proof-of-correctness path.

Expected output:

- Probe script.
- Probe result JSON or Markdown note.
- A yes/no decision on whether native async XPU CPU KV offload is feasible in
  the current PyTorch XPU runtime.
