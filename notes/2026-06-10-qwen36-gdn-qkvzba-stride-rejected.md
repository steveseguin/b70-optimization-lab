# Qwen3.6 INT8 GDN QKVZ+BA Stride Fusion Rejected

Date: 2026-06-10

## Context

The accepted Qwen3.6 INT8 runtime is still forward-bound during single-request
decode. A previous source-level qkvz+ba projection fusion failed because the
native XPU GDN op required independent contiguous qkvz and ba projection
tensors. I tested the lower-level follow-up: allow row-strided qkvz/ba views in
the native GDN kernels, then re-enable one packed qkvz+ba INT8 projection.

Accepted control to beat:

- `data/qwen36-quark-int8-tp4-noprefix-current-control-continue-20260610.json`
- corrected after-first output: `99.630056 tok/s`
- e2e output: `98.390754 tok/s`
- total client throughput: `196.781509 tok/s`
- client TTFT: `74.773814 ms`

## Candidate

Runtime:

- tmux session: `qwen36-tp4-gdn-fusedqkvzba-stride-32k`
- cache root:
  `/mnt/fast-ai/vllm-cache-exp/qwen36-35b-a3b-quark-int8-tp4-piecewise-graph-gdn-fusedqkvzba-stride-32k-noprefix`
- log:
  `/tmp/qwen36-quark-int8-tp4-gdn-fusedqkvzba-stride-32k-noprefix-20260610.log`
- flag: `VLLM_XPU_GDN_FUSE_QKVZ_BA_PROJ=1`

Patch artifacts:

- `patches/vllm-qwen36-gdn-qkvzba-stride-candidate-20260610.patch`
- `patches/vllm-xpu-kernels-qwen36-gdn-projection-strides-candidate-20260610.patch`

The native XPU kernel patch changed the GDN qkvz/ba precondition from fully
contiguous tensors to last-dimension contiguous row-strided views, and threaded
row strides through the causal-conv/reorder kernels.

The vLLM-side patch packed the qkvz and ba INT8 weights/scales, quantized
`hidden_states` once, ran one wider `int8_gemm_w8a8`, and split the output view
before calling GDN.

## Build Notes

The first broad rebuild used the `build/temp` tree, which is configured for
oneAPI 2026. It produced artifacts linked against `libsycl.so.9`, but the
rebuilt package import segfaulted even when `/opt/intel/oneapi/compiler/2026.0/lib`
was added to `LD_LIBRARY_PATH`.

That artifact path was rejected and the previously installed package artifacts
were restored.

The candidate was then rebuilt with the existing oneAPI 2025 tree:

```bash
cmake --build build/xpu-c-only-2025 --target gdn_attn_kernels_xe_2 _xpu_C -j$(nproc)
```

The 2025 artifacts imported cleanly and were used for the actual runtime test.

## Startup

Startup succeeded:

- model loading: `8.58 GiB`, `14.245382 s`
- torch.compile: `57.95 s`
- initial profiling/warmup: `4.99 s`
- no first-request contiguous-view error

Smoke request passed.

## Speed Result

Speed gate:

```bash
/home/steve/.venvs/vllm-xpu/bin/python scripts/measure-openai-endpoint-metrics.py \
  --base-url http://127.0.0.1:18080 \
  --out data/qwen36-quark-int8-tp4-noprefix-gdn-fusedqkvzba-stride-single-r8-20260610.json \
  --prompt-tokens 512 --output-tokens 512 --repeats 8 \
  --warmup-output-tokens 64 --mode stream --skip-vram
```

Result:

- corrected after-first output: `95.049251 tok/s`
- e2e output: `93.939216 tok/s`
- total client throughput: `187.878431 tok/s`
- client TTFT: `74.173914 ms`
- vLLM TTFT: `72.972924 ms`
- vLLM e2e: `5449.253649 ms`

Against the accepted control, this is a regression:

- corrected after-first output: `-4.58 tok/s`, about `-4.6%`
- e2e output: `-4.45 tok/s`, about `-4.5%`
- total client throughput: `-8.90 tok/s`, about `-4.5%`

## Decision

Reject.

The lower-level stride support fixed the correctness blocker from the previous
fusion attempt, but the packed qkvz+ba projection is slower than two separate
accepted projections with reused activation quantization. This likely means the
larger combined GEMM shape is less favorable than the current two-GEMM schedule,
or the split/stride view causes enough downstream cost to erase the saved launch
and quantization work.

No quality gate was run because the speed gate failed.

## Restore

Restored the previous package artifacts:

- `vllm_xpu_kernels/_xpu_C.abi3.so`
- `vllm_xpu_kernels/libgdn_attn_kernels_xe_2.so`

Restored accepted backend:

- tmux session: `qwen36-tp4-gdn-reusequant-clone-envclean-32k`
- endpoint: `http://127.0.0.1:18080`
- `/health`: pass
- `/v1/completions` smoke: pass
- restore log:
  `/tmp/qwen36-quark-int8-tp4-gdn-reuseqkvzbaquant-clone-envclean-32k-noprefix-20260610-restored-after-fusedqkvzba-stride.log`
