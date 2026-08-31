# Qwen3.8 Flash-Next HC-up grouped dynamic-M source preregistration

Date: 2026-08-31

Status: frozen before source implementation

S3g authorizes a default-off source-dispatch design. The candidate extends the
existing single-storage M1 integration without changing its environment flag,
97-target census, packed-weight representation, loader behavior, graph/MTP/TP
guards, or default-off behavior.

Frozen source treatment:

1. Require `scheduler_config.max_num_seqs == 1`,
   `scheduler_config.max_num_batched_tokens == 64`, and
   `scheduler_config.max_num_scheduled_tokens is None` in the opt-in
   configuration guard. In this MTP0 lane the scheduler then derives an exact
   effective cap of 64. A different scheduler contract fails before weight
   treatment.
2. Replace the per-linear scalar `rows=[1]` buffer with one immutable,
   nonpersistent XPU int32 lookup table `arange(65)`. Its total cost is 260
   bytes per linear, about 25 KiB across all 97 targets.
3. Validate the packed allocation, logical shared-storage view, and exact rows
   table once after loading, including table shape, stride, dtype, device,
   contiguity, `requires_grad=False`, and values. Preserve the original
   Parameter, loader metadata, layerwise reload path, and single 635.7 MiB
   physical weight bank.
4. In eager `apply`, accept only contiguous XPU BF16 `[M,320]` with
   `1 <= M <= 64`. Select `rows_table[M:M+1]`; this creates Tensor metadata
   only and performs no device allocation, fill, copy, or host synchronization.
5. In the hot path, recheck table metadata and storage identity without reading
   a device value. Allocate a fresh `[M,10240]` output, call grouped E=1, bind
   the returned Tensor, and verify exact shape, stride `(10240,1)`, dtype,
   device, storage offset zero, and `data_ptr()` equality before returning it.
6. Continue to reject compilation, graphs, MTP, LoRA, other TP/PP shapes,
   broader PLE offload, non-BF16 inputs, and M outside 1--64.

Mutable per-call `rows.fill_(M)` is forbidden because different streams could
race. Lazy per-M device caches are forbidden because they add initialization,
thread, and lifecycle state. The immutable table and fresh outputs leave only
read-only shared state and support different M values on concurrent streams.

Frozen focused tests:

- default-off path performs no model inspection;
- exact scheduler guards accept only one sequence, 64 batched tokens, and an
  unset scheduled-token override;
- exact 97-target/TP4/PP1/MTP0/eager/selective-PLE guards remain intact;
- packed/logical weight shared-storage identity and official layerwise reload
  identity remain exact;
- every M from 1 through 64 matches contiguous authority byte-for-byte on XPU;
- every rows slice is `[M]`, contiguous, and shares the immutable table storage;
- sequential calls use fresh output allocations;
- two XPU streams running different M values return exact outputs and leave the
  rows table and packed weight unchanged;
- M0/M65, compilation, wrong dtype/device/shape, bias, and drifted packed/table
  metadata or storage identity fail closed; table values are validated once at
  load/reload rather than synchronously read in the decode hot path;
- the existing Qwen configuration suite passes separately.

Implementation may begin after this packet is committed. No staged serving
runtime may be built and no endpoint may launch until S4g passes, the focused
tests pass, the source commit is exported as a tracked patch, and independent
source review finds no blocker. Those later gates still authorize only a
separately preregistered endpoint arm.
