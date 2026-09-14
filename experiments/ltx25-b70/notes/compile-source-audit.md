# Stock compiler source audit

Status: **do not submit the stock whole-model compiler graph to the current
persistent server**. This is a source-based experiment selection decision, not
an observed compiler failure. Compilation remains a candidate through a bounded,
configurable block experiment. No GPU compiler job or runtime edit was made.

## Reviewed identity

The frozen ComfyUI checkout is `/home/steve/src/ComfyUI-ltx25-baseline`, commit
`19e1058f4c445ef74047e77a23f9ca7684c1e4b6`.

| Source | SHA256 |
| --- | --- |
| `comfy_extras/nodes_torch_compile.py` | `51a36311466f5f040a784b6b075f48faee28f66889fc2169837230f98dd5a155` |
| `comfy_api/torch_helpers/torch_compile.py` | `e370434c6eeae612e50fec47207faad6c2a181d5a1b836fe7e41bfb10eb11452` |
| Installed `torch/_inductor/config.py` | `9171c2ed249e13a19a2ae22dba0db14f3c4fe11762108f87c8a4e85f96945b0a` |

The installed configuration source is
`/home/steve/.venvs/ltx25-baseline/lib/python3.12/site-packages/torch/_inductor/config.py`.
A separate CPU import of this environment reported Torch `2.14.0+xpu`,
`compile_threads=32`, `emulate_precision_casts=False`,
`eager_numerics.division_rounding=False`, and `triton.cudagraphs=False`.
A restricted read of PID 24848's initial environment found none of the four
corresponding worker/rounding/autotuning overrides. This does not introspect
arbitrary in-process Python configuration mutations.

## Reasons to reject this stock screen

1. The exposed node accepts only `model` and `backend`. It clones with
   `disable_dynamic=True`, then calls the helper with a guard filter that drops
   every guard whose name contains `transformer_options`
   (`nodes_torch_compile.py`, lines 5–6 and 27–29). The shard implementation stores
   routing callbacks and the per-forward transfer cache in this dictionary.
   Removing their guards needs explicit validation, particularly across
   changing inputs, shapes and callback configurations. PyTorch labels guard
   filtering unsafe in its [compile API documentation](https://docs.pytorch.org/docs/2.14/generated/torch.compile.html).
2. The helper compiles the entire `diffusion_model`, using `fullgraph=False`,
   `dynamic=None` and the default mode. The graph API cannot select a single
   block, cap compilation workers, retain guards, or request eager-rounding
   emulation. The Python helper itself supports `keys` and options, but these
   are not node inputs.
3. Installed config lines 3156–3166 explicitly explain that ordinary fusion
   removes intermediate low-precision downcast/upcast pairs. This changes the
   eager BF16 arithmetic even while preserving weight dtype. Lines 3133–3139
   separately describe eager division rounding. Strict deterministic mode
   establishes neither of these eager numerical equivalences.
4. Default compiler worker selection is `min(32, cpu_count)` at lines 1450–1484.
   Whole-model compilation peak memory has not been measured; host available
   memory was approximately 32.9 GiB at this audit snapshot. A graph submitted
   with this node cannot limit the compile working set, and a timed-out client
   does not cancel compilation inside the server. This is an unbounded risk,
   not a claim that compilation has already exhausted memory.

There is no immediate structural shared-weight-clone rejection: the custom
shard patcher's clone supports this operation, and standard ModelPatcher.clone
copies additional model references, callbacks and wrappers. The compile helper
temporarily installs its optimized module during APPLY_MODEL and restores the
original module in `finally`.

Nevertheless, whole-model tracing reaches custom `CompressedTimestep`
objects, `id(tensor)`-keyed routing caches, device contexts, mutable dictionaries
and both XPU devices. Graph breaks, eager fallback, recompilation and unsafe
specializations are plausible outcomes. None was tested here. `fullgraph=False`
permits graph breaks; it does not prove that this combination is safe or fast.

A source search found no alternative stock compile node in this checkout's
`comfy_extras`. The `cudagraphs` backend is unsuitable for this campaign and is
not a proposed fallback. Ordinary Inductor defaults do leave CUDA graphs off.

## Next meaningful compiler experiment

Prepare a block-scoped capability, preserving the existing block objects and
shared weight ownership. Compile one original block's numerical forward on one
device. Keep the outer routing, transfer-cache lifetime and device context
outside the compiled region. Initially retain all guards and all original
arithmetic; do not fuse independently coded approximations of LTX operations.

Proposed process-local Inductor options for that bounded screen:

```python
options = {
    "compile_threads": 1,
    "emulate_precision_casts": True,
    "eager_numerics.division_rounding": True,
    "triton.cudagraphs": False,
    "max_autotune": False,
    "max_autotune_gemm": False,
}
```

These are candidate options, not an exactness guarantee on XPU. Start with
`dynamic=False` and a single block at each actual stage shape. Use
`fullgraph=True` as a capture feasibility gate for the isolated block; retain
an unsupported result instead of silently claiming an eager fallback is a
compiled win. If graph breaks require a later `fullgraph=False` experiment,
record compiled coverage and graph breaks explicitly. Do not use the stock
guard-filter callback.

Require original eager versus compiled bitwise parity on varying inputs,
both audio/video outputs, and repeated evaluation before attaching the block
to the full model. Next require the four full-clip tensors to match original
references and repeat exactly on varied scenes. Only then measure latency.
Compiler peak host/device memory and cold compile cost are separate evidence
from warm generation time. This capability cannot be expressed through the
currently exposed stock graph node; no server restart or live source mutation
has been performed to install it.

## Bounded CPU screen

[test-inductor-bf16-rounding.py](../scripts/test-inductor-bf16-rounding.py)
compares eager and Inductor on a tiny BF16 add/multiply/divide chain at two
shapes and three fresh inputs per shape. It uses one compiler worker and one
CPU compute thread, intact guards, and process-local temporary compiler caches
that are removed afterward. It allocates no XPU tensors and changes no server
or machine settings. This tests option plumbing and representative rounding
boundaries, not an LTX block, XPU compiler correctness or performance.

Run:

```bash
/home/steve/.venvs/ltx25-baseline/bin/python \
  experiments/ltx25-b70/scripts/test-inductor-bf16-rounding.py \
  --output /tmp/ltx-inductor-bf16-rounding-new.json
```

The result path must be new; the helper refuses to overwrite evidence.
The [CPU receipt](../data/inductor-bf16-rounding-cpu-01.json) records six input
cases for each arm. Default rounding differed from eager in all six cases;
the preservation options matched eager bitwise in all six. Both arms repeated
exactly. This concretely distinguishes repeatability from baseline equivalence,
but does not qualify these options for LTX or XPU.
