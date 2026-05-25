# 2026-05-25 Phase 4: Active Context Limit Finding

Goal: determine whether the XPU CPU KV offload prototype can extend a single
active MiniMax M2.7 request beyond the GPU-resident KV block budget.

Short answer: not yet. The XPU copy path works, but vLLM's current exact
attention path still needs the active request's KV pages resident in the GPU
block table. CPU KV offload is useful for storing and reloading cached blocks,
but by itself it does not make a single exact full-attention sequence larger
than the live GPU KV cache.

## Launch Shape

Temporary server:

```bash
VLLM_MAX_MODEL_LEN=49152 /home/steve/bin/minimax-vllm-serve \
  --kv-offloading-size 16 \
  --no-scheduler-reserve-full-isl
```

Log:

`/mnt/fast-ai/bench-results/minimax-m27-b70-serve/serve-49152-c1-kvoffload16-capacity-validation-20260525T010825Z.log`

Startup reported:

- `max_model_len=49152`
- GPU KV cache size: `33792` tokens
- Block size: `256`
- Effective GPU KV blocks: `132`
- CPU KV admission budget: `4.0 GiB` per worker from
  `--kv-offloading-size 16` and TP4

## Prompt Sizes

The repeated-line validation prompt tokenized as:

| Lines | Tokens | Block-rounded need |
| ---: | ---: | ---: |
| `1450` | `33350` | `131` blocks |
| `1460` | `33580` | `132` blocks |
| `1470` | `33810` | `133` blocks |
| `1500` | `34500` | `135` blocks |

## Observed Results

`1460` lines / `33580` prompt tokens with `max_tokens=1` timed out after
`300 s`.

During the stall, `/metrics` reported:

```text
vllm:num_requests_running 0
vllm:num_requests_waiting 1
vllm:num_requests_waiting_by_reason{reason="deferred"} 1
vllm:kv_cache_usage_perc 0.9923664122137404
```

`0.9923664122137404` is `131 / 132` GPU KV blocks. The request was parked
with nearly the entire GPU KV cache occupied but no model execution running.

`1450` lines / `33350` prompt tokens with `max_tokens=1` completed:

```json
{
  "prompt_tokens": 33350,
  "completion_tokens": 1,
  "total_tokens": 33351,
  "elapsed_s": 0.550637006002944
}
```

That fast elapsed time is not a clean prefill benchmark because it ran after
the aborted `1460`-line request and could reuse CPU-offloaded blocks. It is
still useful because it shows that an active request within the effective GPU
block budget can return a valid completion with the CPU KV offload connector
present.

## Interpretation

The previous working transfers were real:

- GPU to CPU store moved multi-GB KV payloads.
- CPU to GPU load moved multi-GB KV payloads.
- The worker and pinned host memory path are not the immediate blocker.

The blocker is where the loaded KV has to be used. For exact full attention,
the next token needs to attend to the whole prior sequence. vLLM's current XPU
attention kernels consume a GPU-resident block table; they do not stream part
of the active KV from CPU RAM during attention. If the active sequence needs
more GPU KV blocks than are available, scheduler-only offload cannot make it
finish without either dropping context or changing the attention implementation.

This means the current prototype does not support:

- `49152` active exact context when only about `33792` GPU KV tokens fit
- `65536`, `131072`, or `196608` active exact context
- `196608` with c2-c4 active sessions

## What CPU KV Offload Can Still Be Useful For

The current path may still be useful for exact-quality session swapping:

- Multiple sessions whose individual active context fits in GPU KV.
- Idle sessions stored in CPU RAM.
- One session reloaded into GPU KV when it becomes active again.

That is different from active-context overflow. A `32768` session fits in the
current fast lane, so c2-c4 session swapping at up to about 32K context may be
a practical next target. It will pay a large PCIe transfer cost on session
switches, but it should preserve quality.

## Next Viable Paths

1. Keep the current `32768` high-performance endpoint as the production lane.
2. Test session swapping for multiple `<=32768` contexts using CPU KV offload.
3. Find the largest reliable pure GPU-resident exact context by varying
   `gpu_memory_utilization` and measuring real completion behavior.
4. Continue TurboQuant / KV compression only behind quality gates.
5. Treat true `196608` active exact context as a separate kernel/runtime R&D
   project:
   - CPU-paged attention that streams KV tiles into scratch GPU memory and
     accumulates exact attention.
   - Or a Level Zero / SYCL USM-backed attention path that can read host KV
     directly, if performance and correctness are acceptable.
   - Or quality-gated KV compression that makes the full active KV resident on
     GPU.

## Restore

The normal server was restored after this experiment with:

```bash
VLLM_MAX_MODEL_LEN=32768 /home/steve/bin/minimax-vllm-serve
```
