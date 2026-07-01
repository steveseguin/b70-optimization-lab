# Qwen3.6 INT8 GDN QKVZ+BA Fusion Rejected

Date: 2026-06-10

## Context

The accepted Qwen3.6 INT8 runtime is forward-bound during steady single-request
decode. Timing traces pointed at the Gated DeltaNet path as one of the repeated
per-layer costs. In the XPU path, each GDN layer currently projects the same
`hidden_states` twice:

- `in_proj_qkvz(hidden_states)`
- `in_proj_ba(hidden_states)`

Both projections use the Quark INT8 W8A8 path, so this costs two per-token
activation quantizations and two INT8 GEMMs. The second GEMM is small. I tested
whether packing the post-load qkvz and ba weights into one wider W8A8 GEMM could
remove the duplicate activation quantization and tiny GEMM without changing
model math.

Everything else stayed aligned with the accepted runtime:

- model: `nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8`
- TP4, 32K context
- Quark W8A8 INT8, BF16 runtime
- XPU PIECEWISE graph capture
- clone-safe custom-op all-reduce
- prefix caching disabled
- `--max-num-batched-tokens 8192`
- `--max-num-seqs 48`

## Experiment

The experiment was guarded behind:

- `VLLM_XPU_GDN_FUSE_QKVZ_BA_PROJ=1`

The temporary source patch did three things:

1. After Quark quantization post-processing, concatenate the post-processed INT8
   weights and scales from `in_proj_qkvz` and `in_proj_ba`.
2. In `GatedDeltaNetAttention.forward_xpu`, quantize `hidden_states` once.
3. Run one XPU `int8_gemm_w8a8`, then split the wider output back into qkvz and
   ba tensors before calling the native XPU GDN core.

Reproduction sketch:

```python
fused_weight = torch.cat(
    (qkvz.weight.detach(), ba.weight.detach()), dim=1
).contiguous()
fused_scale = torch.cat(
    (qkvz.weight_scale.detach().flatten(),
     ba.weight_scale.detach().flatten()),
    dim=0,
).contiguous()

x_q, x_s = torch.ops._xpu_C.per_token_quant_int8_xpu(
    hidden_states.view(-1, hidden_size).contiguous()
)
projected = torch.ops._xpu_C.int8_gemm_w8a8(
    x_q, x_s, fused_weight, fused_scale, hidden_states.dtype, None
)
projected = projected.view(*hidden_states.shape[:-1], qkvz_width + ba_width)
projected_states_qkvz, projected_states_ba = projected.split(
    [qkvz_width, ba_width], dim=-1
)
```

The local vLLM source has been restored after the screen. The code above is a
repro sketch, not accepted production code.

## Candidate 1

Runtime:

- tmux session: `qwen36-tp4-gdnfuse-32k`
- cache root:
  `/mnt/fast-ai/vllm-cache-exp/qwen36-35b-a3b-quark-int8-tp4-piecewise-graph-gdn-fuse-qkvzba-32k-noprefix`
- log:
  `/tmp/qwen36-quark-int8-tp4-gdn-fuse-qkvzba-32k-noprefix-20260610.log`

Startup succeeded:

- model loading: `8.75 GiB`, `14.613227 s`
- `torch.compile`: `54.36 s`
- initial profiling/warmup: `4.97 s`
- available KV cache memory: `20.49 GiB`
- GPU KV cache size: `2,035,438 tokens`
- reported maximum concurrency for 32K requests: `62.12x`
- graph capture: `12 s`, `-0.01 GiB`

Smoke failed on the first request:

```text
RuntimeError: projected_states_qkvz must be contiguous
```

The split qkvz tensor is a view into the wider fused GEMM output, and the native
XPU GDN attention op rejects it.

## Candidate 2

Runtime:

- tmux session: `qwen36-tp4-gdnfuse-contig-32k`
- cache root:
  `/mnt/fast-ai/vllm-cache-exp/qwen36-35b-a3b-quark-int8-tp4-piecewise-graph-gdn-fuse-qkvzba-contig-32k-noprefix`
- log:
  `/tmp/qwen36-quark-int8-tp4-gdn-fuse-qkvzba-contig-32k-noprefix-20260610.log`

This variant added explicit `.contiguous()` copies after splitting the fused
projection output.

Startup succeeded:

- model loading: `8.75 GiB`, `15.055189 s`
- `torch.compile`: `54.82 s`
- initial profiling/warmup: `4.85 s`
- available KV cache memory: `20.49 GiB`
- GPU KV cache size: `2,035,438 tokens`
- reported maximum concurrency for 32K requests: `62.12x`
- graph capture: `12 s`, `-0.01 GiB`

Smoke still failed on the first request with the same native-op precondition:

```text
RuntimeError: projected_states_qkvz must be contiguous
```

Under the compiled/AOT graph path, this source-level copy did not produce an
input layout the native XPU GDN op accepted.

## Cost Versus Accepted Runtime

Accepted restored backend:

- log:
  `/tmp/qwen36-quark-int8-tp4-accepted-32k-noprefix-restored14.log`
- model loading: `8.58 GiB`, `14.619286 s`
- `torch.compile`: `3.64 s`
- available KV cache memory: `20.67 GiB`
- GPU KV cache size: `2,052,915 tokens`
- reported maximum concurrency for 32K requests: `62.65x`
- graph capture: `12 s`, `-0.17 GiB`

The fused projection candidate costs about:

- `+0.17 GiB` model-load memory per rank
- `-0.18 GiB` available KV cache memory
- `-17,477` KV cache tokens
- `62.65x` to `62.12x` reported 32K concurrency
- about `+51 s` extra compile time because it had to build a new AOT graph

No speed or quality gate was run because the candidate failed smoke.

## Stability

After the failed fusion runs, the first accepted-backend restore hit a Level
Zero device-lost error during smoke:

```text
UR_RESULT_ERROR_DEVICE_LOST
```

That was logged in:

- `/tmp/qwen36-quark-int8-tp4-accepted-32k-noprefix-restored13.log`

After killing the failed tmux sessions, waiting for stale worker processes to
clear, and restarting the accepted backend, restore14 passed health and smoke.

## Decision

Reject this Python/source-level GDN qkvz+ba projection fusion.

The idea is still technically sound as a kernel/API optimization, but the
current native XPU GDN path requires independent contiguous qkvz and ba tensors.
Splitting a fused output does not satisfy that contract, and adding a source
level copy did not fix the compiled runtime. The failed route also reduced KV
headroom and introduced a device-lost recovery event.

If this optimization is worth pursuing later, use a lower-level route:

- extend the native XPU GDN op to consume a packed qkvz+ba projection layout and
  offsets directly, or
- add an XPU INT8 GEMM variant that writes directly into two contiguous output
  buffers, or
- add a native fused projection-plus-GDN entry point that removes the split
  boundary entirely.

Do not re-enable this source-level split fusion in the production candidate.

## Restore

The accepted backend is restored:

- tmux session: `qwen36-tp4-noprefix-32k`
- endpoint: `http://127.0.0.1:18080`
- model name: `qwen36-35b-a3b-fp8`
- prefix caching disabled
- `/health`: pass
- `/v1/completions` smoke: pass

Keep the accepted runtime on the no-prefix TP4 32K profile.
