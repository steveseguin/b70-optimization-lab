# P208 — selected SYCL paired projection, compile only

P208 adds a native SYCL Q6_K paired projection and a synthetic qualification
fixture, building on [P207](../packet207-host-paired-projections/README.md).
The current scope is compilation, linking and offline artifact inspection only.
No resulting executable is invoked, no device is enumerated, and no GPU/model,
service, queue or machine-setting action is authorized by this packet.

The [compile-only receipt](evidence/build-compile-only.json) passed: 43 compiler
inputs and 33 inherited objects are bound, both native pair kernel entries are
present in extracted SYCL device bitcode, and the linked ELF retains the future
qualification function and SYCL image registration. The initial compile-lock
module-alias failure is retained; the corrected attempt compiled successfully.
No device result is claimed.

## Operation and captured bindings

[paired_sycl.hpp](paired_sycl.hpp) admits only Q6_K, K2560, variant6/split1,
expanded_sg32 stride3380, and rows10240 or6144. Seven allocation IDs are owned by
the existing Device/Arena: weights, input0, input1, output0, output1, workspace0,
workspace1. All seven are distinct. The two 4-byte workspace handles satisfy the
ABI and are not consumed by the split1 arithmetic. Matrix identity, scalar types,
extents and alignment are checked before capture/issue.

Each output row has one WG32/subgroup32. The kernel decodes each weight/scale
once in source and updates two independent FP32 chains, retaining the pinned
p33 lane*8/step256 order. Each chain uses the explicit width1/2/4/8/16 subgroup
selection/add tree and one BF16 output write. The compiler retains precise
floating-point flags, including no contraction. No measured traffic, speed or
native exactness claim follows from source equivalence or compilation.

The operation derives from the selected `ownrt::SyclOperation` and submits through
the pinned `ownrt::prepared_submit` interception hook. Stored command and kernel
captures contain pointer values, not references to a transient binding span,
Operation or local. The existing 1,024-byte device capture check remains active.
Two named kernel specializations make the compiled shape identity inspectable.

This fixture explicitly requires an in-order queue and no supplied dependency
vector. Uploads and readbacks complete before their consumers, using the same
selected Device. It does not establish cross-queue ordering or a full Engine
scratch/cache dependency contract. Raw projection outputs remain unconditional;
there is no invented active/error guard inside the arithmetic kernel.

## Future qualification body, disabled CLI

[native_fixture.cpp](native_fixture.cpp) emits the externally visible
`p208_future_qualification` function. Its body uses the existing native owner,
CopyEngine, typed capture and issue path. Both production shapes compare every
BF16 output against selected native `p33.dense.segment` variant6 and independent
CPU p33 arithmetic. Caller Matrix mutation must not redirect captured commands;
changing a live row input must affect only its output, and changing the shared
weight payload must affect both outputs. Two CPU-generated synthetic weight
matrices are used; no Weights/Engine/model payload is constructed.

The function requires an external admission/fault guard before owner creation
and between requests/transfers. It records owner teardown and retains ownership
if draining fails. These are proposed future fixture semantics, not an executed
result. The executable's `main` always refuses with exit64 and never calls this
function. No live CLI, manifest or launch integration is supplied. A future
execution path requires separate coordinator/admission review.

## Reproduction and artifact gates

Compile and inspect offline:

```sh
nice -n 19 taskset -c 8-15,24-31 env OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 python3 experiments/own-xpu-runtime/stage2/packet208-sycl-paired-projections/build_native.py --compile-only
```

The recipe reuses the pinned P198 native compiler/link flags and selected
owner/arithmetic/backend objects, omitting old application/fixture entry points.
It takes the existing compile-turn lock, enforces a 27GB root-space floor after a
256MiB write reservation, and limits this CPU compiler process to 4GiB address
space. Parent headers, actual dispatch, objects and compiler dependencies are
hash-bound; local sources and compiler logs are preserved for every attempt.
Transient binaries, LLVM device bitcode and post-link tables remain ignored.

Success requires an actual non-HOST SYCL translation unit and linked ELF,
`p208_future_qualification` still defined in that ELF, a device offload bundle,
and offline post-link symbols for both named Q6 pair kernel specializations.
Tool outputs and hashes are retained. These checks never load or run the new
artifact. Compiler/tool failures remain in their per-attempt evidence directory.

## Remaining admission

Device output equality, timing, throughput, real fault behavior and complete
production Engine integration are unqualified. The census contains35 Q6 GDN
layers and one Q8 layer; this operator excludes Q8. Per-row production FP32
conversion caching, real Engine queue/scratch ownership and the frozen-chunk
expert-cache policy remain separate gates. P207's successful mini lifecycle
cannot substitute for these native/full-model requirements.
