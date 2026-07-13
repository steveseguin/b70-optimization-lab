# Xe2 hot-loadable kernel module proof

Date: 2026-07-13

## Result

The hot-module boundary is viable. A standalone `bmg-g31` AOT SYCL module was
built, loaded with `dlopen`, given an already-created in-order queue and
host-owned USM pointers, and dispatched correctly on an Arc Pro B70.

- module-only incremental rebuild: `3.01 s`;
- clean module plus standalone loader build: `3.36 s` (configure: `0.40 s`);
- current monolithic `libggml-sycl.so` AOT link: `497 s`, measured from the
  link-process start at 10:26:14 to the resulting `.so` mtime at 10:34:31;
- rebuild speedup: `165.1x`;
- one-time `dlopen` plus symbol lookup: `0.108724 ms`;
- worst dynamic-module overhead across five 2,000-launch repeats:
  `0.000269 ms/call` (`0.269 us`);
- correctness: passed all repeats on `ZE_AFFINITY_MASK=3`;
- required runtime gate (`< 0.1 ms/call`): passed with over two orders of
  magnitude of margin.

The measured result is in
`data/2026-07-13-hot-kernel-module-proof.json`. The proof implementation is in
`hot-kernel-module/`.

## Stable boundary

The module exports one C symbol:

```c
const struct q27_xe2_module_v1 *q27_xe2_module_get_v1(void);
```

It returns a versioned function table. Every ABI record contains fixed-width
integers and C pointers; no C++ object is embedded in a public struct. The one
intentional toolchain dependency is the opaque borrowed queue pointer: the
module casts it to `sycl::queue *`. Loader and module therefore must match the
exact `toolchain_abi` string before the queue can be touched. This is a narrow,
honest ABI rather than pretending a C++ SYCL queue has cross-toolchain binary
stability.

The initial production tag should include at least the oneAPI compiler major
and minor, C++ standard, `_GLIBCXX_USE_CXX11_ABI`, and libsycl major. A mismatch
disables the module before dispatch. `target_arch` must be `bmg-g31`, and the
runtime must also prove that the selected device is BMG G31.

## Ownership and ordering

The runtime owns everything:

- `ggml_backend_sycl_context::stream()` owns/provides the queue;
- model loading owns persistent packed weights;
- the graph/runtime owns inputs, outputs, recurrent state, and scratch;
- the loader owns the `dlopen` handle for process lifetime.

The module borrows these objects only for a launch. It may not create another
queue/context, wait, allocate, free, retain pointers after return, or close the
module while work is in flight. The protected source confirms that
`ctx.stream()` returns DPCT's `default_queue()`, and that default is the
in-order queue. The same borrowed queue therefore preserves ordering against
ordinary ggml operations without an added event, barrier, or synchronization.

The module call is asynchronous. All pointed-to allocations and the module
handle remain valid until the runtime later completes the queue.

## Exact fallback contract

There are two status classes, and they must never be conflated:

1. `DECLINED`, `BAD_ABI`, `BAD_ARGUMENT`, `BAD_LAYOUT`, and `BAD_SHAPE`
   guarantee no work was submitted. The existing built-in kernel path may run.
2. `SUBMIT_STATE_UNKNOWN` means submission was attempted and queue state cannot
   be proven. The runtime must report a fatal device error; it must not run the
   built-in path and risk executing the operation twice.

The module validates ABI, op, layout, dimensions, pack sizes, queue property,
and scratch before its first `queue.submit`. For fused operations, validation
must still be complete before the first enqueue. Prefer one genuinely fused
kernel per ABI call. A module must never enqueue kernel one, fail on kernel
two, and return a fallback-safe status.

At graph execution, the current graph matcher remains the source of truth. It
must first prove the exact fusion boundary and exclusivity of skipped nodes.
Only after a module returns `OK` may the runtime suppress those nodes. A
fallback-safe status runs the current implementation with no skips. Load,
symbol, version, build-tag, architecture, or op-mask failures warn once and
leave the current built-in path unchanged.

## Q6 and GDN pack handoff

Packed weights remain runtime-owned persistent device allocations. The ABI
passes a host-resident array of `q27_xe2_pack_v1` descriptors. Each descriptor
contains:

- a borrowed device pointer and exact byte count;
- a globally scoped 64-bit layout ID;
- a semantic role such as draft LM head, GDN QKV, alpha/beta, or output;
- a content tag derived from the model/tensor fingerprint.

For Q6 M6 top-1, the runtime passes the existing
`extra->xe2_q6_m6_top1_pack[device]` as one `DRAFT_LM_HEAD` descriptor, using
`Q27_XE2_LAYOUT_Q6K_M6_TOP1_V1`, the existing exact packed byte count, draft
rows as `input0`, and the five-token I32 result as `output0`. The module checks
all four identity fields before submit.

For a GDN fusion, the runtime passes the persistent projection packs as
role-labelled descriptors (`GDN_QKV`, `GDN_ALPHA_BETA`, `GDN_OUTPUT`) with the
Q4/Q8 layout ID. The launch record separately carries current activation,
output, recurrent state, and fixed-address scratch pointers. This permits one
fused module to consume several packs without owning or duplicating them and
without baking model addresses into the `.so`.

The `content_tag` prevents a valid-sized pack from the wrong tensor/model from
being accepted after a hot swap. Modules do not build or load packs. The
existing RAM/disk pack cache remains responsible for that work.

## AOT build and registration point

The prototype uses the same essential target as the protected build:

```text
icpx -O3 -fPIC -shared -fsycl -fsycl-targets=spir64_gen \
  -Xs "-device bmg-g31"
```

The eventual protected-source change should be deliberately small:

1. A process-lifetime registry reads `GGML_SYCL_XE2_MODULE` once at backend
   initialization, opens it `RTLD_NOW | RTLD_LOCAL`, resolves the getter, and
   validates the ABI/toolchain/architecture/op mask.
2. The Q6 integration belongs inside `q6_m6_top1_dispatch`, after the existing
   strict matcher and before `ggml_sycl_mul_mat_q6_k_xe2_m6_top1`.
3. GDN module calls belong at the already-proven GDN dispatch plans in
   `ggml_backend_sycl_graph_compute_impl`, not inside generic tensor ops.
4. The built-in dispatch remains the exact fallback and the module is fully
   opt-in. No graph node is skipped until module `OK`.

`libggml-sycl` already links `-ldl`, so the eventual loader adds no new runtime
library dependency. This active proof did not modify the protected llama.cpp
tree.

## What this changes

This does not improve decode speed by itself. It removes the iteration
bottleneck: a Q6/GDN kernel edit can be AOT-built in about three seconds rather
than relinking the entire device image for many minutes. That makes broad
tile/subgroup/layout experiments practical while preserving the production
runtime and exact fallback. The next implementation move is to put the real Q6
M6 top-1 kernel behind this module boundary, then use the same registry for
GDN fusion candidates after Q6 correctness and economics are measured.
