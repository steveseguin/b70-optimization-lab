# Packet109 layout and arithmetic audit

Only `other_fusion` may change at a bracket boundary. Both views retain the same
arena descriptors, allocation IDs, expanded weight layout, target/draft choices,
KV precision, ownership and resident footprint. Both speculative command banks
are rebuilt after a full request reset; candidate captures must equal a fresh
candidate process and restored production captures must equal initial captures.
Weights are write-protected by the native wrapper after initialization.

The route epilogue is limited to the existing 512-thread single-work-group
route-fast kernel with top10 and hidden2560/shared640. It retains each route
phase. The independent shared gate/up inputs are ready before the route begins.
The last route phase completes before activation uses the shared active/error
guards. Invalid positions and inactive/error cases retain the production output
rules. Valid route indices are guaranteed by the route phase; no intervening
expert status failure can occur on an admitted production route.

Shared-down uses expanded Q8_0 K640 rows of 760 bytes and the original
`p33::dense_lane` arithmetic and SG32 tree. Each row writes its rounded down
value and ten-expert mixture before the original guarded blend. The mixture
and down writers remain unconditional, including inactive/error paths. The
blend retains +0, runtime *one, both separate BF16 rounds, and the original
sigmoid operation. No floating-point sum is reordered.

Admission checks all twelve allocation sizes, lifetimes, alignment, pairwise
non-overlap and position capacity. The activation allocations have their own
extent/alignment/non-alias checks. The registered route binder validates its
original inputs. Common BF16-writer invalidation still executes after fused
sites, including sites whose launch is now empty. Draft execution is unchanged.

The byte fixture calls the actual production operations, not a rewritten
mathematical oracle. It covers real 512/top10 and 2560×640 dimensions, all BF16
encodings at activation/tail boundaries, finite/tied routes, signed zeros,
subnormals, infinities, quiet/signaling NaNs and active/error/position guards.
GNU and Intel are each compared with their own production arithmetic; their
NaN payload choices need not match each other. The final reference compiles the
actual NgHost operation separately with runtime shapes, just as the engine
does; the early inline fixture accidentally specialized that reference. GNU's
CPU implementation retains the original complete blend loop behind a generic
runtime-shape boundary. Intel's CPU check exercises the fused row expression
that is compiled for the device. These are explicitly different CPU backend
implementations, not a claim that the GNU host executes SYCL device code.
No NaN is silently replaced or canonicalized by the new code.

Full-shape CPU gates use actual parse, initialize, bank preparation, capture,
selection switch, reset and memory admission. Numerical arena addresses and
weight payload elision avoid reading the model or allocating device memory.
Startup109 additionally traverses all eleven real chain-window entry paths for
both views, including the KD host and device argument paths and target-only KD
projection. Miniature IPC/reset tests qualify orchestration, not model quality.

Device compilation is not device correctness. The proposed in-engine bracket
must pass the fixed oracle before any speed verdict can be considered.
