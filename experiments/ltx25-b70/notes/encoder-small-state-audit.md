# Encoder small-state residency candidate

Status: **inactive, CPU lifecycle tests passed; GPU correctness and speed unmeasured.**
Prepared against ComfyUI `19e1058f4c445ef74047e77a23f9ca7684c1e4b6`.
The running source and server were not changed, and no GPU request was issued
for this candidate.

The live py-spy sample reported by the root agent places many encoder-worker
samples in `model_management.cast_to` below `llama.RMSNorm.forward` and
`gemma4.TransformerBlockGemma4.forward`'s scalar cast. This establishes a useful
source target. Sample occupancy includes waiting for earlier asynchronous GPU
work: it is **not** a measurement of copy kernel duration, PCIe bandwidth, or
an equal amount of recoverable latency. The root's stack-profile packet owns
sample counts and the profiled request's exactness result.

## Exact source mechanism and size

Static `ModelPatcher._load_list()` includes RMSNorm parameter leaves but loads
in descending byte-size order. Tiny norms can be omitted when the remaining
budget is too small; they have no `comfy_cast_weights` member. A CPU norm weight
therefore reaches the ordinary `rms_norm` weight cast each forward. Partial
unload does the inverse ascending-size ordering, removing tiny norms early.

Every Gemma4 transformer block also owns a direct registered BF16
`layer_scalar` buffer. Its child parameters make the block non-leaf, and
`_load_list()` omits that block. No leaf entry then owns this buffer for partial
loading. Stock whole-model `.to()` does move it during full load or detach.

A [header-only tensor census](../data/encoder-small-state-census.json), without
loading tensor data, found:

| Native text state | Tensors | Bytes |
| --- | ---: | ---: |
| RMSNorm weights | 289 | 1,539,584 |
| Per-block scalar buffers | 48 | 96 |
| Combined | 337 | 1,539,680 |

The total is approximately **1.47 MiB**. Vision position-normalization tensors
are excluded from this text-path estimate. This is stored tensor size, not an
allocator peak estimate.

## Candidate and ownership

[The candidate patch](../patches/encoder-small-state-residency.patch) is enabled
only by `clip.patcher.model_options['ltx_small_state_residency'] = True` before
loading, on the static patcher. The helper rejects dynamic mode, changed norm
state/dtype, unexpected scalar state, weight/wrapper/hook/object patches, and
insufficient model budget. The budget guard includes the small tensors and a
conservative ordinary cast-buffer allowance. It changes no global reserve,
pinning, power or memory settings. It is not a total activation/allocator peak
bound. Integration must keep dynamic VRAM disabled; its independent dynamic
loader is outside this candidate.

The patch prioritizes RMSNorm leaves without altering any byte-size field.
It moves the direct scalars on their existing registered owners, retaining
all original state-dict keys and BF16 data. Their bytes enter
`model_loaded_weight_memory` once per load, never as an extra copy hidden from
accounting. Partial unload prefers ordinary weights, then norms, then the
scalar buffers. Complete detach uses the stock whole-model move and clears the
buffer accounting marker; shared clones share the model-owned marker. The option
cannot be disabled while its buffers are marked loaded: detach first.

The earlier resident-accounting correction is included **only when this option
is enabled**. Do not stack the separate `encoder-resident-accounting.patch` on
this patch. The default load/unload ordering and accounting remain upstream.
No arithmetic, precision, operator ordering, weights, noise, frame count,
resolution or denoising steps change. Prioritizing small state may choose a
different large matrix for ordinary offload, so exact full-model GPU comparison
and matched fresh-prompt latency checks are still mandatory.

## CPU checks and next gate

[The CPU harness](../scripts/test-encoder-small-state.py) imports real tiny BF16
Gemma4 blocks and the actual pinned ModelPatcher. It applies the patch only in
memory to a subclass. **12/12 tests passed**, including complete real block
outputs, state hashes, norm loading, registered-buffer byte accounting,
repeated partial loads, pressure unload, complete unload/reload, shared clone
and detach, option-off placement, and unsupported-budget/patch/mode guards.
The [receipt](../data/encoder-small-state-cpu.json) binds the patch hash;
[full output](../data/encoder-small-state-cpu.log) lists the tests. An initial
CPU fixture used the wrong RoPE matrix shape; correcting it to the pinned
implementation's rotation-matrix layout enabled the real-block checks. No
candidate GPU result exists.

```bash
/home/steve/.venvs/ltx25-baseline/bin/python \
  experiments/ltx25-b70/scripts/test-encoder-small-state.py
```

CPU load and offload use the same actual device. Those tests verify ownership,
bookkeeping and arithmetic preservation, **not** actual XPU placement, transfer
removal or speed. The next runtime gate must inspect per-tensor placement,
accounting and post-unload ownership, then compare full captured samples across
fresh varied prompts against protected references. Profile warm encoding again
only after exactness passes. This candidate is at least as worthwhile to screen
as the separate unused-hidden-state crop: it directly addresses repeated
synchronous boundaries with only 1.47 MiB of permanent state, but the relative
speed benefit remains unknown. Preserve the current persistent server; do not
create a restart chain to screen it.
