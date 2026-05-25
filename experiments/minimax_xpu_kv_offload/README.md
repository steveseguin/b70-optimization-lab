# MiniMax XPU CPU KV Offload Research Lane

Date started: 2026-05-24

This folder tracks the experimental path toward serving MiniMax M2.7 on Intel
Arc Pro B70 with context beyond the current high-performance `32768` token
endpoint by spilling KV cache to host RAM.

Execution plan:

`../../plans/2026-05-24-minimax-xpu-kv-offload-plan.md`

The stable production lane remains:

- Model: `Lasimeri/MiniMax-M2.7-int4-AutoRound`
- Engine: vLLM/XPU TP4
- Context: `32768`
- KV dtype: `auto` / FP16-family
- Endpoint: OpenAI-compatible vLLM on `0.0.0.0:8000`
- Warm endpoint decode: about `84-95 tok/s`, depending on warm state and the
  exact benchmark shape

Do not replace that lane with this work until correctness, stability, and
quality are proven.

## Why This Matters

MiniMax advertises `196608` max position embeddings. The current B70 endpoint
serves a reliable `32768` tokens because the FP16-family KV cache must fit in
GPU memory. CPU KV offload would let the server keep less-active KV blocks in
system RAM and page them back as needed.

Useful targets:

| Target | Purpose |
| --- | --- |
| `32768`, c1 | Current fast baseline; must remain easy to restore. |
| `65536`, c1 | First large-context milestone. |
| `131072`, c1 | Prove CPU KV offload is genuinely useful. |
| `196608`, c1 | Full MiniMax advertised context. |
| `196608`, c2-c4 | Long-context concurrency research, likely slow but valuable. |

Expected performance with CPU KV offload is much lower than full-VRAM decode.
That is acceptable for this lane if it enables otherwise impossible sessions
and does not degrade model quality.

## Quality Rules

This lane may experiment with memory movement, cache layout, TurboQuant, and
runtime scheduling. It must not silently lower answer quality.

Promotion requires:

- Same model weights unless explicitly labeled otherwise.
- No expert dropping.
- No speculative decoding unless separately labeled and quality-gated.
- Exact-token canaries for deterministic low-level changes.
- Semantic/arithmetic/sixpack checks before promoting any server recipe.
- Endpoint metrics should record prompt tokens, output tokens, TTFT, output
  tok/s, total tok/s, context length, concurrency, and peak VRAM when possible.

FP8 KV, TurboQuant, or other compressed KV modes must be labeled as compressed
KV experiments and compared against the FP16-family baseline.

## 2026-05-24 Experiment Summary

All experiments were temporary. The normal `32768` server was restored.

### Attempt 1: CPU Weight Offload

Command shape:

```bash
VLLM_MAX_MODEL_LEN=196608 /home/steve/bin/minimax-vllm-serve \
  --max-num-seqs 4 \
  --cpu-offload-gb 16
```

Result:

```text
AssertionError: CPU tensor must be pinned
```

This is model-weight offload, not KV offload. It failed during model load in
vLLM's UVA offloader before any useful long-context test could run.

Log:

`/mnt/fast-ai/bench-results/minimax-m27-b70-serve/serve-196k-c4-cpuoffload16-20260524T215219Z.log`

### Attempt 2: No CPU Offload

Command shape:

```bash
VLLM_MAX_MODEL_LEN=196608 /home/steve/bin/minimax-vllm-serve \
  --max-num-seqs 4
```

Result:

```text
To serve at least one request with max seq len 196608,
11.62 GiB KV cache is needed, larger than available KV cache memory 1.56 GiB.
Based on the available memory, the estimated maximum model length is 26368.
```

Log:

`/mnt/fast-ai/bench-results/minimax-m27-b70-serve/serve-196k-c4-nooffload-20260524T215257Z.log`

### Attempt 3: Native CPU KV Offload Flag

Command shape:

```bash
VLLM_MAX_MODEL_LEN=196608 /home/steve/bin/minimax-vllm-serve \
  --max-num-seqs 4 \
  --kv-offloading-size 64
```

Result:

vLLM accepted the flag but the KV preflight check still counted only GPU KV
capacity and rejected the run before the offload connector could initialize.

Log:

`/mnt/fast-ai/bench-results/minimax-m27-b70-serve/serve-196k-c4-kvoffload64-20260524T221520Z.log`

### Attempt 4: Temporary Admission-Check Patch

A local patch added the per-worker CPU KV budget to the preflight capacity
calculation. This got past the prior GPU-only KV check.

The next blocker:

```text
Exception: CPU Offloading is currently only supported on CUDA-alike GPUs
```

The native CPU KV offload path then tried to initialize
`OffloadingConnector` / `CPUOffloadingSpec`, but rejected XPU explicitly.

Log:

`/mnt/fast-ai/bench-results/minimax-m27-b70-serve/serve-196k-c4-kvoffload64-admissionpatch-20260524T223029Z.log`

Patch sketch:

`patches/kv-offload-admission-check-xpu-experiment-20260524.patch`

## Current Root Cause

vLLM's native CPU KV offload implementation is CUDA-oriented. The XPU run gets
past the scheduler-side configuration only after an admission-check patch, then
fails in the worker-side offload handler because the CPU KV path uses CUDA
concepts:

- `torch.cuda.Stream`
- `torch.cuda.current_stream`
- CUDA events
- `cudaHostRegister`
- CUDA-style async copy handling

The guard is in:

`vllm/v1/kv_offload/cpu/spec.py`

The CUDA-specific worker code is in:

`vllm/v1/kv_offload/cpu/gpu_worker.py`

## Candidate Work Plan

1. Keep `32768` FP16-family KV endpoint as the stable fallback.
2. Create an XPU implementation parallel to the CUDA CPU KV worker rather than
   weakening CUDA assumptions in place.
3. Replace CUDA streams/events with XPU stream/event equivalents if available
   in the installed PyTorch XPU stack.
4. Replace `cudaHostRegister` with a Level Zero / SYCL / PyTorch XPU pinned
   host-memory path. `torch.empty(..., pin_memory=True)` and `.pin_memory()`
   already work locally in `torch 2.11.0+xpu`.
5. Start with small context over GPU capacity, not full `196608`:
   `49152` or `65536`, c1.
6. Measure decode with long prompt plus small output first, then short prompt
   plus long output, then concurrency.
7. Only after c1 works, test c2/c4.

## Phase 1 Probe Result

Initial PyTorch XPU primitive probe passed on 2026-05-24 while the normal 32K
server was running:

- `torch.xpu.Stream`: available
- `torch.xpu.Event`: available
- pinned CPU tensors: available
- pinned CPU -> XPU -> pinned CPU round-trip: correct through `64 MiB`
- event transfer rates at 4-64 MiB: roughly `25-28 GB/s`

Artifacts:

- `probes/xpu_stream_copy_probe.py`
- `xpu_stream_copy_probe_20260524.json`
- `notes-20260524-phase1-probe.md`

Decision: proceed to an XPU CPU KV worker prototype rather than another
launch-flag experiment.

## Phase 2 Block Copy Probe Result

Initial KV-shaped block-copy probe passed on 2026-05-24:

- loop copy mode: correct but slow, about `2.1-2.4 GB/s`
- indexed scatter mode: not usable because XPU `index_copy_` requires
  same-device source/destination
- contiguous logical slice mode: correct and fast, about `28 GB/s` for 64-256
  MiB one-way timed regions

Artifacts:

- `probes/xpu_kv_block_copy_probe.py`
- `xpu_kv_block_copy_probe_20260524.json`
- `xpu_kv_block_copy_probe_20260524-indexed-fail.json`
- `xpu_kv_block_copy_probe_20260524-slice.json`
- `notes-20260524-phase2-block-copy-probe.md`

Decision: prototype an XPU CPU KV worker around range coalescing plus fast
slice copies, with the loop path as a correctness fallback for fragmented
transfers.

## Phase 3 XPU Worker Live Server Result

Status on 2026-05-25: partially working, not production-ready.

Prototype patch:

- `patches/xpu-cpu-kv-worker-prototype-20260525.patch`

Detailed notes:

- `notes-20260525-phase3-xpu-worker-live-server.md`

What now works:

- vLLM can initialize `CPUOffloadingSpec` on XPU with a new XPU worker.
- `49152` context starts and `/v1/models` reports `max_model_len=49152`.
- GPU KV allocation remains sane: about `33792` tokens, rather than being
  accidentally inflated by CPU offload admission bytes.
- Short requests complete on the compiled server with the offload connector
  present. One short check produced `64` output tokens in `0.903 s`
  (`70.88 tok/s` wall output, `84.17 tok/s` total).
- Long requests above the GPU-only KV budget now trigger real multi-GB KV
  movement between GPU and pinned host RAM.

Measured live transfer example at about `34500` prompt tokens:

| Direction | Bytes | Time | Effective rate |
| --- | ---: | ---: | ---: |
| GPU -> CPU | `8.45152256 GB` | `0.779795848 s` | about `10.8 GB/s` |
| CPU -> GPU | `8.321499136 GB` | `0.508610908 s` | about `16.4 GB/s` |

Current blocker:

- The XPU worker can move KV to and from pinned host RAM.
- The current vLLM/XPU exact attention path still needs the active request's
  KV pages resident in GPU KV blocks.
- Scheduler-only CPU KV offload can store/reload cached blocks, but it does
  not yet make one exact full-attention sequence larger than the live GPU KV
  cache.
- A `49152` server starts, but prompts that require the last GPU KV block or
  more can park in `deferred` instead of generating.

Do not use this lane as the default server yet. The stable `32768` endpoint is
still the recommended path for real use.

## Phase 4 Active Context Limit Finding

Follow-up validation on 2026-05-25 refined the blocker:

- `49152`/c1 with `--kv-offloading-size 16` reported `33792` GPU KV tokens,
  or `132` blocks at block size `256`.
- A `33350` token prompt (`131` blocks) plus one output token completed with
  the CPU KV connector present.
- A `33580` token prompt (`132` blocks) plus one output token timed out after
  `300 s` and parked with `131/132` GPU KV blocks occupied.
- A `34500` token prompt had already shown real multi-GB CPU KV store/load,
  but still did not return a completion.

Detailed note:

`notes-20260525-phase4-active-context-limit.md`

Interpretation: this prototype is useful groundwork for XPU CPU KV movement
and may support exact-quality session swapping for contexts that individually
fit in GPU KV. It is not yet true active-context overflow. Full `196608`
active exact context needs CPU-paged attention, host-readable KV kernels, or
quality-gated KV compression.

## Phase 5 C2 Session-Swap Smoke

Follow-up validation on 2026-05-25 found the first practical RAM-backed use
case:

- `32768`/c2 with `--kv-offloading-size 16` started successfully.
- c2 reduced GPU KV capacity to `26112` tokens because of extra runtime and
  graph memory.
- Two concurrent distinct `14000`-token prompts completed even though their
  combined prompt length was `28000` tokens.
- The first pass stored about `4.29 GB` from GPU to CPU at roughly
  `10-11 GB/s`.
- Repeating the same two prompts produced CPU-to-GPU loads of about
  `7.02 GB` in `0.467 s`, roughly `15.0 GB/s`.
- vLLM reported an external prefix cache hit rate of `49.4%`.

Detailed note:

`notes-20260525-phase5-session-swap-smoke.md`

Interpretation: CPU KV offload can already act as an exact session cache for
contexts that fit individually in GPU KV. This is a useful community-facing
capability, but it is separate from full active-context overflow.

## Phase 6 Session-Cache Canaries And C4 Ladder

Follow-up validation on 2026-05-25 added a reusable OpenAI endpoint canary
script and tested longer reload decode:

- Added `scripts/session_cache_canary.py`.
- Stable c1 baseline with two `16134`-token prompts and `128` generated tokens
  measured about `74 tok/s` after TTFT for each sequential request.
- c2 with CPU KV offload repeated those two prompts concurrently. The second
  pass returned in `2.785 s` per request with about `60 tok/s` after TTFT.
- c2 moved CPU-to-GPU KV at about `13.9 GB/s`.
- c4 with four `9234`-token prompts worked after an expensive first compile.
  The second pass returned in `1.6-2.6 s` per request, with about
  `52-79 tok/s` after TTFT.
- c4 moved CPU-to-GPU KV at about `15.8 GB/s`.
- The first c4 compile exposed an Intel `ocloc` / IGC internal compiler error
  (`error code 245`, floating point exception) before fallback compilation
  completed.

Important caveat: longer free-form concurrent completions do not produce exact
text-hash matches across passes. One-token c2 matched for A/B. One-token c4
matched for A/B/D but not C. Treat CPU KV session caching as mechanically
working and promising, but do not promote it as production quality-equivalent
until a stricter deterministic canary and semantic quality gate pass.

Strict-word follow-up:

- Added `--prompt-mode strict-word`, which buries a long context and asks the
  model to copy one target word.
- GPU-only c1 baseline with four `21073`-token prompts produced stable exact
  hashes for A/B/C/D across two passes.
- c1 with CPU KV offload enabled matched the GPU-only baseline by expected word
  and exact output hash for A/B/C/D.
- c2 with two concurrent `21073`-token prompts, about `42146` combined prompt
  tokens against `34304` GPU KV tokens, matched the GPU-only baseline by
  expected word and exact output hash for A/B.
- c2 second-pass reload returned in `0.506-0.885 s` with CPU-to-GPU KV transfer
  around `15.3 GB/s`.
- c4 with four concurrent `12073`-token prompts, about `48292` combined prompt
  tokens against `34304` GPU KV tokens, produced the expected first word for
  A/B/C/D on both passes.
- c4 exact hashes matched for A/B/C. D's second pass produced the correct first
  word plus one extra continuation token, so c4 remains experimental rather
  than production quality-equivalent.
- A one-token strict run is not a clean substitute because the first generated
  token can be whitespace-only.

Detailed note:

`notes-20260525-phase6-session-cache-canaries.md`

C2 capacity ladder follow-up:

- Tightened the strict-word prompt to `strict-word-answer-space-v2`.
- Tested two-session c2 reload at about `8K`, `16K`, `21K`, `30K`, and
  `32.5K` prompt tokens per session.
- Combined prompt pressure reached `64948` tokens against a `34304` GPU KV
  budget.
- All ladder shapes matched the GPU-only baseline by expected first word.
- A fresh cold near-max c2 run with two `32474`-token prompts had first-pass
  TTFT of `24.758-48.363 s`, then second-pass reload TTFT of `0.668-1.232 s`.
- CPU-to-GPU KV reload bandwidth measured about `14-15 GB/s`.
- vLLM reports `4.0 GiB` CPU KV budget per worker for `--kv-offloading-size 16`,
  about `16 GiB` total across four tensor-parallel workers.

Detailed note:

`notes-20260525-c2-session-cache-ladder.md`

C2 quality and sustained-decode follow-up:

- Added `fact-word` and `--logprobs` modes to
  `scripts/session_cache_canary.py`.
- Small logprob requests worked, but long-context logprob checks failed with
  NaN values in the OpenAI JSON response path, so logprobs are not yet a usable
  long-context quality gate on this stack.
- c2 strict-word checks passed at about `8K`, `21K`, and `32.5K` prompt tokens
  per session.
- c2 fact-word checks returned the expected B=`cobalt` and D=`amber` answers at
  about `6.6K`, `17.5K`, and `27K` prompt tokens per session, with one brittle
  GPU-only baseline caveat at the middle size.
- Sustained c2 reload decode at `24874` prompt tokens per session measured about
  `66 tok/s` per request after TTFT on the second pass. Total wall output for
  that two-request pass was about `53.35 tok/s`.

Detailed note:

`notes-20260525-c2-quality-and-turboquant.md`

C4/C8 session-cache ladder follow-up:

- Added `scripts/serve_session_cache.sh` as a tracked helper for c1/c2/c4/c8
  launch shapes.
- Updated the tracked 110tps repro OpenAI-server launcher with environment
  knobs for `VLLM_MAX_NUM_SEQS`, `VLLM_MAX_NUM_BATCHED_TOKENS`,
  `VLLM_KV_OFFLOADING_SIZE`, and `VLLM_NO_SCHEDULER_RESERVE_FULL_ISL`.
- c4 with `--kv-offloading-size 32` reported `34304` live GPU KV tokens and
  `8.0 GiB` CPU KV budget per TP worker.
- c4 fact-word at four `22540`-token sessions passed expected-word checks
  across two passes. Second-pass reload TTFT was `0.390-1.211 s`.
- c8 with `--kv-offloading-size 64` reported only `22784` live GPU KV tokens
  and `16.0 GiB` CPU KV budget per TP worker. More RAM budget reduced live GPU
  headroom.
- c8 startup was expensive: `315.97 s` engine init, including `234.78 s` of
  compile time.
- c8 fact-word at eight `12540`-token sessions passed expected-word checks.
  Second-pass reload TTFT was `0.552-3.709 s`.
- c8 fact-word at eight `17540`-token sessions also passed. This is about
  `140321` combined prompt tokens. Second-pass reload TTFT was
  `0.415-3.247 s`.
- c8 stalled above that on this stack: `750`, `800`, `850`, and `900` line
  fact-word runs left some or all requests waiting/deferred near `100%` GPU KV.
  Killing the canary client cleared the queue.

Detailed note:

`notes-20260525-c4-c8-session-cache-ladder.md`

Sustained concurrent decode follow-up:

- c4 at four `9234`-token prompts with `128` requested output tokens each
  measured `109.76 tok/s` total warmed wall output on the second pass.
- c8 at eight `9234`-token prompts with `128` requested output tokens each
  measured `110.34 tok/s` total warmed wall output on the second pass.
- c8 spreads roughly the same total decode bandwidth across more sessions; it
  does not double throughput.
- Larger c4 sustained `n128` attempts at `16134` and `22459` prompt tokens per
  session stalled after partial completion even though shorter correctness
  canaries at larger contexts can pass.

Detailed note:

`notes-20260525-sustained-concurrency-decode.md`

Additional deployment observation: after the B70s were no longer used for the
Ubuntu display, experimental c2/c4 launches could report `34304` GPU KV tokens
instead of the earlier `26112` c2 result. Display ownership and compile/cache
shape can materially affect available KV budget.

## TurboQuant Interaction

TurboQuant remains interesting because it reduces KV footprint and therefore
reduces both RAM capacity pressure and PCIe transfer volume.

Current TurboQuant status after the 2026-05-25 workspace fallback experiment:

- A local patch works around two locked-workspace crashes in
  `turboquant_attn.py`: `_decode_attention` and `_continuation_prefill`.
- Patch artifact:
  `../../patches/vllm-turboquant-xpu-workspace-fallback-20260525.patch`.
- With `turboquant_k8v4` and `max_model_len=32768`, vLLM reported `80128` GPU
  KV tokens and `2.45x` max concurrency for a 32K request.
- Strict-word copy canaries passed at about `8K` and `32.5K` prompt tokens.
- Sustained decode at `24874` prompt tokens was only about `16.5 tok/s` after
  TTFT, much slower than the normal FP16-family KV lane.
- `max_model_len=65536` failed; vLLM estimated the maximum at `60672`.
- `max_model_len=60000` started and answered a `58874` token strict-word
  canary, but TTFT was about `53-54 s` and decode was not interactive.
- With `turboquant_4bit_nc`, `max_model_len=100000`, c4, and
  `--kv-offloading-size 32`, vLLM reported `84654` GPU KV tokens and `0.85x`
  max concurrency for a 100K request.
- That 100K server answered strict-word prompts at `84074` and `84374` prompt
  tokens, but timed out or parked near `84644+` tokens because the active
  request exhausted live GPU KV blocks.
- With `turboquant_4bit_nc`, `max_model_len=196608`, c1,
  `--max-num-batched-tokens 512`, and `--gpu-memory-utilization 0.959`, vLLM
  reported `98304` GPU KV tokens and `0.50x` max concurrency for a full 196K
  request.
- The 196K/c1 server answered an `84074` token strict-word prompt, but TTFT was
  `114.342 s`. A near-limit prompt around `97800` tokens filled GPU KV
  (`kv_cache_usage=1.0`) and killed the engine with
  `TimeoutError: RPC call to sample_tokens timed out`.
- Intel `ocloc` / IGC error 245 still appears during compile fallback.

Interpretation: TurboQuant is now mechanically past the first XPU workspace
blockers and can raise the live GPU KV ceiling, but it is not a production
replacement. Capacity improved substantially; decode speed, stability, and
quality still need work. Most importantly, TurboQuant plus CPU KV offload still
does not provide true active-context overflow: the active request must fit in
live GPU KV blocks.

Relevant repro:

`scripts/repro-minimax-turboquant-xpu-workspace-bug.sh`

Detailed note:

`notes-20260525-c2-quality-and-turboquant.md`

Active-boundary note:

`notes-20260525-turboquant-active-context-boundary.md`

## CPU-Paged Attention Path

The next full-context path is CPU-paged attention, not a larger
`--kv-offloading-size` setting. Current CPU KV offload can park/reload sessions,
but XPU FlashAttention still needs the active request's KV blocks in live GPU
memory.

The proposed exact path is:

1. Keep recent/current KV in normal GPU KV blocks.
2. Keep older logical KV blocks in CPU offload storage.
3. Stage old CPU-resident KV chunks into a small GPU scratch workspace.
4. Run FlashAttention over each staged chunk with softmax LSE returned.
5. Merge partial attention outputs using vLLM's existing
   `merge_attn_states()` log-sum-exp merge.
6. Merge that old-context result with normal attention over the live GPU suffix.

This mirrors two existing vLLM patterns:

- XPU `cascade_attention()` already splits prefix/suffix attention and merges
  LSE-backed partial outputs.
- ROCm AITER `extend_forward()` already gathers KV chunks into a workspace,
  runs attention by chunk, and merges the results.

New artifacts:

- `notes-20260525-cpu-paged-attention-design.md`
- `notes-20260525-stagea-gpu-split-attention.md`
- `probes/split_attention_merge_probe.py`
- `probes/xpu_flash_attn_split_probe.py`
- `split_attention_merge_probe_20260525.json`
- `split_attention_merge_probe_20260525-uneven.json`
- `xpu_flash_attn_split_probe_20260525.json`

Standalone split-attention math probe results:

| Shape | Chunks | Max output abs error | Max LSE abs error | Result |
| --- | ---: | ---: | ---: | --- |
| `4096` KV tokens, `4` queries, `8` heads | `8` | `6.71e-08` | `9.54e-07` | pass |
| `5000` KV tokens, `7` queries, `8` heads | `7` | `8.94e-08` | `1.91e-06` | pass |

Interpretation: the core split-and-merge softmax math is sound. The remaining
work is vLLM integration: logical-vs-physical KV accounting, CPU block range
queries, GPU staging workspace, temporary block tables, and XPU
FlashAttention calls that return LSE for merging.

Stage A vLLM integration attempt:

- A disabled-by-default patch tried to force GPU-resident split decode through
  the existing `cascade_attention()` path.
- First attempt crashed because XPU FA2 does not support `q_descale` in the
  prefix cascade call.
- After matching the normal non-cascade q-descale guard, the path ran but did
  not match the normal baseline.
- A direct XPU FlashAttention probe showed decode suffix `causal=True` produced
  a large output mismatch (`0.128` max abs error), while suffix
  `causal=False` was close (`0.0015` max abs error) but had an LSE offset.
- A third forced-cascade attempt with non-causal decode suffix improved speed
  to `60.75 tok/s` after TTFT but still did not match the baseline hash.
- Baseline checklist canary: `3714` prompt tokens, `64` output tokens,
  `91.44 tok/s` after TTFT, hash `5afda1f4fa37f3d3`.
- Forced split canary: `3714` prompt tokens, `64` output tokens,
  `13.29 tok/s` after TTFT, hash `2fb45f78a286e529`, text diverged.
- Conclusion: do not use the cascade shortcut for quality-preserving overflow.
  The next prototype needs an explicit staged-attention path with carefully
  constructed block tables and LSE comparison.

## Dense-Scratch CPU-Staged Attention

Follow-up probes on 2026-05-25 narrowed the active-overflow path:

- Added `probes/xpu_cpu_staged_attention_probe.py` to test paged XPU scratch.
  It is a useful negative diagnostic: paged scratch output can be close, but
  returned LSE is unstable enough to break exact chunk merging.
- Added `probes/xpu_cpu_dense_staged_attention_probe.py` to test dense XPU
  scratch. This is the promising route.
- Dense full attention matched normal paged full attention output to about
  `3e-05` to `6e-05`, despite paged LSE being unreliable.
- A MiniMax-shaped synthetic dense-staged run passed at `32768` tokens with
  `8` KV heads, `128` head size, `16384` CPU-staged prefix tokens, and
  `8192` token dense scratch chunks.
- That run matched normal paged output within `3.0517578125e-05` and matched
  dense full LSE within `9.5367431640625e-07`.

Decision: stop pursuing paged scratch merging for true active overflow. The
next vLLM prototype should use dense scratch chunks for both CPU-resident old
KV and GPU-resident suffix KV, then merge dense attention states.

Detailed note:

`notes-20260525-dense-staged-cpu-attention.md`

## Current 196K / Multi-Session Conclusion

The requested end goal is useful: four or more concurrent sessions, ideally
with the full `196608` token MiniMax context, backed by system RAM when needed.

The current stack cannot do that yet.

The best active capacity observed in the TurboQuant 4-bit NC lane was `98304`
tokens. One full MiniMax context is `196608` tokens, so a single full active
context is about `2x` beyond the best live GPU KV capacity observed. Four full
active contexts are `786432` tokens, about `8x` beyond that live capacity.

CPU KV offload is still useful, but today it is session caching: it stores and
reloads KV for sessions whose active working set fits in GPU KV. It does not
make XPU attention read arbitrary old KV blocks directly from host RAM.

Production should stay on the `32768` FP16-family KV endpoint. The next R&D
step is dense-scratch CPU-staged attention, not just larger
`--kv-offloading-size` values or higher `max_model_len`. Paged scratch merging
is currently blocked by unreliable XPU paged-attention LSE values.

Restore note: a fatal near-limit 196K TurboQuant run left orphan
`VLLM::Worker_TP*` processes holding XPU memory. If the normal server fails on
restart with near-zero free XPU memory, kill the orphan workers and stale
`multiprocessing.resource_tracker`, then remove stale `/dev/shm/psm_*` and
`/dev/shm/sem.mp-*` files. Details are in the active-boundary note.

## Open Questions

- Does PyTorch XPU expose enough stream/event behavior to mirror the CUDA CPU
  KV worker cleanly?
- Can Level Zero host allocation or SYCL USM host memory replace
  `cudaHostRegister` for pinned CPU KV pages?
- Will XPU FlashAttention accept blocks that were copied back from host without
  hidden synchronization stalls?
- What is the lowest useful context above 32K once offload works?
- Is TurboQuant k8v4 quality-equivalent enough for long-context practical use,
  assuming the workspace allocation bug is fixed?
- How much decode throughput is lost per offloaded KV block ratio on PCIe4?
- Why does c4 occasionally add one extra continuation token under strict-word
  concurrent reload, and is that normal XPU/MoE nondeterminism or a
  cache-specific issue?
- Can a logprob/token-id canary prove c2 exactness more cleanly than text hashes
  when generated continuation text varies?
- Can a synchronous dense-scratch CPU-staged attention prototype load
  just-in-time KV ranges into XPU scratch space and still produce exact
  strict-word canaries?
- Can TurboQuant or another compressed KV format be quality-gated strongly
  enough to serve as a production option, or should it stay research-only?

## Stable Restore Command

If an experiment leaves the server down, restore the stable endpoint with:

```bash
pkill -f 'vllm serve' || true
VLLM_MAX_MODEL_LEN=32768 /home/steve/bin/minimax-vllm-serve
```

Expected `/v1/models`:

```json
{
  "id": "/mnt/fast-ai/llm-models/minimax-m2.7-int4-autoround",
  "max_model_len": 32768
}
```
