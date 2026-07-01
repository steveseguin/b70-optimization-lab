# Qwen3.6 W8A8 Offset Path Patch Note 20260612cw

This records the local `vllm-xpu-kernels` hook used to prepare the next narrow
offset-only diagnostic. It is intentionally a patch note instead of a raw
`git diff` artifact because `/home/steve/src/vllm-xpu-kernels` already has
unrelated diagnostic changes in `vllm_xpu_kernels/fused_moe_interface.py`.

Local source file:

- `/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels/fused_moe_interface.py`

New opt-in env var:

```bash
VLLM_XPU_W8A8_USE_OFFSETS=1
```

Implementation summary:

- Add `W8A8_USE_OFFSETS_ENV = "VLLM_XPU_W8A8_USE_OFFSETS"`.
- Build an exclusive prefix-sum offset vector from `rows_per_expert`:

```python
def _make_w8a8_grouped_gemm_offsets(rows_per_expert):
    offsets = torch.empty((rows_per_expert.numel() + 1, ),
                          dtype=torch.int64,
                          device=rows_per_expert.device)
    if offsets.numel() == 0:
        return offsets
    offsets[0].zero_()
    if rows_per_expert.numel() > 0:
        offsets[1:].copy_(torch.cumsum(rows_per_expert.to(torch.int64),
                                       dim=0))
    return offsets
```

- Enable only when the extension exports the offset symbol:

```python
def _should_use_w8a8_offsets():
    return (FUSEDMOE_AVAILABLE and _is_env_enabled(W8A8_USE_OFFSETS_ENV)
            and hasattr(torch.ops._xpu_C,
                        "cutlass_grouped_gemm_w8a8_int8_offsets_interface"))
```

- In the INT8 GEMM1/GEMM2 path, call
  `torch.ops._xpu_C.cutlass_grouped_gemm_w8a8_int8_offsets_interface(...)`
  with `expert_first_token_offset=w8a8_grouped_gemm_offsets` when the offset
  vector is present.
- Otherwise fall back to the existing
  `cutlass_grouped_gemm_w8a8_int8_interface(...)` path.

ABI smoke result:

- Installed extension: base W8A8 INT8 op works, offset symbols missing.
- Stable build candidate:
  `build/lib.linux-x86_64-cpython-312/vllm_xpu_kernels/_xpu_C.abi3.so`
  executes base and offset ops with matching checksum `1452.126831`.
- Archived pre-sidecar candidate executes base, offset, and active-offset with
  matching checksum.
- Sidecar-probe candidate aborts with signal `6`; do not use it for endpoint
  testing.

Next diagnostic command shape:

```bash
VLLM_XPU_W8A8_USE_OFFSETS=1 \
PYTHONPATH=/path/to/overlay:/home/steve/src/vllm:/home/steve/src/vllm-xpu-kernels \
LD_LIBRARY_PATH=/home/steve/src/vllm-xpu-kernels/build/lib.linux-x86_64-cpython-312/vllm_xpu_kernels:$LD_LIBRARY_PATH \
  scripts/launch-qwen36-quark-int8-accepted.sh
```

Do not launch this against the sidecar-probe build. Use an isolated cache root,
run provenance sentinels, measure p512/o512 c1 speed, run quality canaries, and
restore the accepted baseline immediately if the offset lane is neutral or
slower.
