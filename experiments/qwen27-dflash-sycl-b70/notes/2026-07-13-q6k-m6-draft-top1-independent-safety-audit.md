# Q6_K M=6 draft top-1 independent safety audit

Date: 2026-07-13

## Scope and outcome

This is a read-only review of the guarded native-DFlash Q6_K M=6 fused top-1
implementation in the protected dirty llama.cpp tree at base commit
`e3546c7948e3af463d0b401e6421d5a4c2faf565`. Benchmarking was stopped by the
manager so the implementation owner could address the three semantic gaps
below before promotion.

The fused kernel's five-row Q6 calculation and lowest-ID reduction are
internally coherent, its pack has a single owner, and its current event/scratch
ordering is valid on the backend's in-order queue. The current target graph
cannot accidentally match the draft pattern. Three issues nevertheless block
promotion:

1. the graph matcher does not prove that the rows-1..5 view has no second
   consumer;
2. a failed compact-result read claims to fall back to logits that the compact
   graph did not produce; and
3. the generic SYCL argmax fallback does not guarantee the fused kernel's
   lowest-token-ID tie rule.

No protected source was changed by this audit.

## Blocking findings

### 1. The matched view is not proven exclusive

`ggml/src/ggml-sycl/ggml-sycl.cpp:6841-6867` counts direct consumers of the
Q6_K `MUL_MAT` and requires the only consumer to be the exact rows-1..5 view.
It finds an `I32[5]` argmax whose input is that view, but it never counts the
view's consumers.

On successful dispatch, `ggml-sycl.cpp:7383-7388` submits a kernel that writes
only the argmax output, skips the ordinary `MUL_MAT`, and later skips the
argmax node. The view node is harmlessly skipped by the generic view handling
at lines 7377-7378. If a debug, capture, comparison, or future model graph adds
a second consumer of the matched view, however, that consumer will read the
unwritten full-logit tensor.

Required fix: make a second pass over every node source, count consumers of the
matched view, and require exactly one consumer whose node pointer is the
matched argmax. Add a negative matcher test with a second view consumer.

### 2. Compact-read failure is not a valid logits fallback

For an eligible unsplit width-six graph,
`src/models/dflash.cpp:273-285` exposes `t_dflash_top1` instead of `t_logits`.
`src/llama-context.cpp:2168-2195` copies the five IDs and deliberately skips
raw-logit extraction when that result exists.

After decode, `common/speculative.cpp:1276-1281` warns that a failed
`llama_dflash_top1_read()` will use the ordinary logits sampler. Continuing to
`common_sampler_sample()` is unsafe for the compact graph: the context has no
raw logits, and `src/llama-context.cpp:842-858` reports `no logits` and aborts
in a debug build.

Required fix: fail closed when the expected M=6 compact result cannot be read,
or rerun only after explicitly disabling compact mode and rebuilding/decoding
an ordinary-logit graph. Do not continue merely because the log message calls
it a fallback. A smaller ubatch that split M=6 can legitimately have ordinary
logits, so a generalized recovery needs an explicit “result kind/logits
available” query rather than inference from batch width.

### 3. Generic fallback and fused tie rules differ

The fused kernel correctly selects lower token IDs on exact float ties:

- group-local comparison: `ggml/src/ggml-sycl/mmvq.cpp:115-124`;
- final reduction: `mmvq.cpp:142-163`.

The generic SYCL argmax used when the fusion matcher declines does not have the
same rule. At `ggml-sycl.cpp:2873-2892`, both the per-thread scan and workgroup
reduction update only on strict `>`. Equal maxima in different lanes therefore
favor the lower lane (`token_id % 256`), not necessarily the lower token ID.
For example, an exact tie between IDs 1 and 256 can retain ID 256 from lane 0.

Required fix: compare `(value, -token_id)` consistently in both the local scan
and reduction, including a defined invalid-ID rule. Tests must include ties
that cross lane and reduction boundaries, such as 1 versus 256, 255 versus
256, and 0 versus 248319. The expected finite-logit oracle is the lowest token
ID, matching the fused reduction and the CPU temperature-zero scan.

## Additional hardening

### Scratch allocation failure

`ggml/src/ggml-sycl/mmvq.cpp:189-211` allocates 337,600 bytes of activation and
partial-reduction scratch but does not check `scratch.get()` before submitting
the three kernels. The allocation is small and failure is unlikely after the
large pack succeeds, but a null allocation should return `false` so the normal
graph can execute rather than enqueueing invalid pointers.

### Explicit draft identity

The backend matcher is topology- and tensor-name-based; it has no model-arch or
context-type tag. The current target Qwen graph at `src/models/qwen35.cpp:221-227`
produces full logits and has no rows-1..5 view plus `I32[5]` argmax, so it does
not match today. The DFlash decoder creates that exact topology at
`src/models/dflash.cpp:271-282`.

Thus accidental target dispatch is not a current bug. View exclusivity is
still mandatory, and an explicit draft-only marker would make the matcher
robust if another graph later adopts the same five-row shape. The separately
designed target compact boundary uses six picks and should remain a distinct
contract.

## Verified-safe areas

### Skip-node behavior and plan lifetime

- `q6_top1_plans.reserve(cgraph->n_nodes)` precedes collection, so pointers
  installed in `q6_top1_plan_by_node` remain stable.
- The matcher requires exactly one direct `MUL_MAT` consumer and the exact
  contiguous view offset/shape.
- A failed fused dispatch does not mark any skip node, so the ordinary
  `MUL_MAT -> VIEW -> ARGMAX` graph executes.
- A successful dispatch skips the `MUL_MAT`; generic graph traversal already
  skips `VIEW`; the explicit flag skips only the replaced argmax.

These properties become complete once the view's exclusive consumer is also
validated.

### Queue ordering and scratch lifetime

The quantize, Q6 dot, and reduction submissions at `mmvq.cpp:206-211` do not
carry explicit event dependencies. This is correct in the current backend
because `ctx.stream()` is the device default in-order queue
(`ggml/src/ggml-sycl/dpct/helper.hpp:738-774`). Returning the function-local
scratch allocation to the per-context pool is also ordered: any reuse is
submitted later to the same queue.

This assumption should be documented or asserted. Converting this path to an
out-of-order queue would require explicit `depends_on` events and event-aware
scratch retirement.

The pack upload is waited before its pointer is published
(`ggml-sycl.cpp:989-1003`). The five-ID async read is synchronized by
`llama_context::dflash_top1_read()` at `src/llama-context.cpp:1395-1402`.

### Pack ownership and freeing

- Tensor extras are zero-initialized and registered with the owning SYCL
  buffer context at `ggml-sycl.cpp:593-607`.
- The pack pointer is installed only after successful allocation and a waited
  copy at lines 989-1003; exceptions free the unpublished allocation.
- The buffer context owns each extra and calls `release_extra_gpu()` once.
- `ggml/src/ggml-sycl/common.cpp:140-162` frees the Q6 pack on its device and
  then deletes the extra.

No double owner, overwrite, or normal error-path leak was found. Teardown uses
the backend's existing outer synchronization assumptions, as does freeing the
ordinary tensor allocation.

## Memory accounting

The experiment's representation comparison can be misread as runtime memory.
The live implementation retains both representations:

| Item | Bytes | GiB/MiB |
|---|---:|---:|
| Ordinary Q6_K output weight | 1,042,944,000 | 0.971 GiB |
| Expanded fused pack | 1,355,847,680 | 1.263 GiB |
| Both resident | 2,398,791,680 | 2.234 GiB |
| Per-dispatch scratch | 337,600 | 0.322 MiB |
| Allocated M=6 full-logit intermediate | 5,959,680 | 5.684 MiB |

The expanded representation is 298.4 MiB larger than the raw representation,
but that delta is **not** the implementation's incremental runtime cost. Since
the raw weight remains for fallback, enabling the pack consumes the full
additional 1.263 GiB. A transient host vector of the same size also exists
during packing. The graph still allocates the 5.684 MiB logit intermediate,
although successful fused dispatch does not write it.

Pack creation is gated by `GGML_SYCL_XE2_Q6_M6_TOP1` at model load, not by
successful semantic activation of the higher-level compact path. Graph mode
also rejects fused dispatch in the matcher. Consequently, a mismatched flag or
graph-on run can pay 1.263 GiB for a pack that never dispatches. Run identity
and memory telemetry should record pack creation and fused dispatch counts.

## Promotion tests implied by this review

Before resuming a strict AOT crossover:

1. matcher accepts the intended single-consumer graph and rejects an added
   view consumer, wrong pack/layout, split weight, wrong shape, and graph mode;
2. forced compact-read failure exits safely without querying raw logits;
3. generic and fused argmax agree on cross-lane exact ties;
4. real captured activations retain five-of-five ID parity over many cycles,
   not only one fixture;
5. logs prove pack-created, fused-dispatched, compact-read, and fallback counts;
6. device headroom includes the full additional pack, not only the format-size
   delta.
