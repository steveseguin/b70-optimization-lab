# Compiler screen02: exactness failure source audit

This read-only audit follows the first compiled block24 call failing exact
parity: video54 and audio5923 unequal **bytes**, with finite values and matching
metadata. It does not establish which operation first diverged. No native
imports, GPU work, requests or runtime modifications were performed.

[Evidence, hashes and selected generated excerpts](../data/compiler-screen-02-rms-source-audit.json)
bind the failed call, its compiler options and source files. The full generated
wrapper remains in the evidence root under
`encoder-server-compiler-03/inductor-cache/rx/crx5gzovt3rxiijvak577nmftatyazzjjytqe2hiddhjvmitnwiu.py`.

## Confirmed source change

Native RMS normalization has been decomposed into Triton reductions. The
current `comfy/rmsnorm.py:7–11` calls `torch.nn.functional.rms_norm`; its comment
explicitly warns that manual rsqrt/reduction rounding differs from native RMS.
The installed PyTorch decomposition at
`torch/_decomp/decompositions.py:1946–1998` expands `_fused_rms_norm` into FP32
square, mean, epsilon addition, rsqrt, multiplication and final dtype conversion.

The generated wrapper's lines211–257 implement a 4096-wide RMS using `tl.sum`,
`div_rn` and `libdevice.rsqrt`. Its first invocation normalizes the video
self-attention Q projection before RoPE and SDPA. This is an early diagnostic
boundary, not a proven first mismatch. Audio's separate full-width RMS sites
at `av_model.py:299`, `315`, and `379` are also decomposed and fused with
modulation/residual operations (generated kernels9,19,26). Video AdaLN remains
an opaque `torch.ops.comfy_kitchen.rms_adaln.default` call. The much larger audio
difference is consistent with this asymmetry but cannot attribute the fault.

`emulate_precision_casts=True` and rounded division are active. The generated
code retains explicit BF16 casts, uses `div_rn`, and records
`enable_fp_fusion=False`. Those controls preserve selected operation rounding;
they do not preserve the native reduction tree or guarantee identical
transcendental implementations. Sigmoid gates use `tl.sigmoid` and GELU uses
`libdevice.tanh`; these are additional candidates if RMS passes or replacing
RMS does not restore exactness. Explicit `tl.fma` is emitted for `addcmul`, so
the fusion flag alone is not a statement that no fused multiply-add exists.
The source evidence does not establish that this `addcmul` differs from eager.

## Recommended next candidate: keep native RMS opaque inside this block

Prefer a private custom operation over globally changing PyTorch's
decomposition/lowering registries. Its implementation must call the saved
original `F.rms_norm(x, normalized_shape, weight, eps)` unchanged, with the same
input/weight tensors, shape, dtype and epsilon. Do not substitute a manual RMS
formula or change either epsilon (`1e-5` for Q/K norms and `1e-6` for unweighted
hidden-state norms). Register no decomposition for the custom operation.

A narrow adapter can rewrite only recognized RMS call-function nodes in the
selected block's Dynamo FX graph, **before AOT decomposition**, to that custom
operation, then invoke `torch._inductor.compile(gm, inputs, options=OPTIONS)`.
The installed entry point supports that options argument at
`torch/_inductor/__init__.py:42–61`. This avoids editing the original module,
its RMSNorm submodules, shared `F.rms_norm`, or process-global lowering tables.
It also covers both `comfy.ops.RMSNorm` and the plain function sites after
their forward methods have been traced.

Preregister the observed FX targets/signatures from a source dump: expected
high-level targets include `torch.rms_norm` and `F.rms_norm`. Do not assume a
particular target is present. Reject zero replacements, unknown signatures,
or a decomposed RMS pattern arriving too late. Preserve positional/keyword
arguments and record the complete replacement census. If an ATen
`_fused_rms_norm` tuple-output node is encountered, reject it until a separate
tuple-return wrapper/fake is reviewed; a tensor-return wrapper is not a
drop-in replacement for that operator.

The fake implementation must return the same shape, dtype, device and layout
as native RMS without performing native work. Start with the observed
contiguous inputs and produce a contiguous `empty_like` result; explicitly
reject unsupported layouts and training/autograd use. Validate actual output
strides before broadening the fake. Do not guess native layout for every
possible noncontiguous input. The schema needs optional weight and optional
epsilon, and should declare no mutation or output aliasing.

Simply calling `make_fallback(..., override_decomp=True)` is insufficient:
the installed `torch/_inductor/lowering.py:2903–2955` uses that flag to bypass
conflict checks, not to remove an earlier decomposition. A fallback for
`aten._fused_rms_norm` already exists at line3726, yet this compiled block
contains the reduction expansion. Removing entries from a global table
would additionally depend on which earlier AOT/core table supplied the
decomposition. The private operation makes the numerical boundary explicit.

## Qualification and first-divergence diagnostic

First census the native RMS sites using the exact captured block inputs,
parameters, strides and epsilons. Capture the first native block24 call's
small input/intermediate tensors once; retain hashes and a bounded archive,
not more video. Compare native eager RMS, the existing generated reduction,
and the opaque candidate on identical inputs with byte equality and repeats.
The required widths include4096 and2048; enumerate every actual site instead
of assuming those two widths are the whole graph. Also screen the generated
sigmoid/GELU and residual operations on their actual inputs if RMS does not
explain the failure.

For locating the first mismatch, preserve the existing compiled kernels and
inspect their materialized boundaries in dependency order: initial AdaLN,
Q projection, Q RMS, K RMS, RoPE, SDPA, gate and residual, followed by the
audio path. Capture a buffer before in-place reuse. A copied generated Python
wrapper may add bounded snapshots after existing kernel calls without
regenerating or splitting those kernels. Require that diagnostic replay
reproduces the original failed output hashes; additional copies can alter
timing and lifetimes. Recompiling an instrumented/partitioned model changes
the fusion boundaries and is not automatically observation-neutral.

After isolated operator gates, require the new generated wrapper to retain
the opaque RMS calls and contain no corresponding decomposed RMS reductions.
Then repeat the original block24 comparison, both latent stage shapes, and
the full boat/marble/bird exact tensor gates with same-process repeats. Keep
native precision, resolution, frame count, seeds and8+3 steps unchanged.
Any mismatch remains a rejection; no tolerance waiver or speed claim follows
from this source audit. Root retains ownership of the persistent endpoint,
bounded requests, fault monitoring and any necessary deployment.
