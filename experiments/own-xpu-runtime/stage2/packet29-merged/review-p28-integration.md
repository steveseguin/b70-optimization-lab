# Independent packet28 integration review

This reviewer independently compared packet28 and the copied packet29 source,
then traced arithmetic storage, argument binding, scratch and fixture entry
paths. No device or compiler was run by this reviewer. This is source review,
not hardware qualification or a speed claim.

The initial copy changed only relative include paths and a host-only OpenMP
pragma over independent rows. `dense.hpp`, `expert.hpp` and native submit
bodies otherwise preserve packet28 arithmetic. `p28/source-proof.json` binds
the copy to its source hashes. Later integration-specific bank validation
must be recorded there and reviewed separately from the unchanged math.

Dense Q6/Q8 consume R5 expanded weights and the R5-selected split tree. Raw
F32/BF16 consume their original scalar bytes. Split4 computes the four
original partial sums and `(p0+p1)+(p2+p3)`. WG32 split4 is two events and
both count; rows4 split4 is one work-group submission. Scratch is 32 bytes
per output row/route even for paths which currently do not write it. The
runtime's 8MiB scratch exceeds the largest logits requirement7,946,240 bytes.

Routed gate/up use two independent accumulators with one shared input;
expert-down uses one slot-specific input. Native weight offsets, scale/sign
expressions, quantized level lookup, BF16 output and SG32 tree are unchanged.
The copied validators retain activation/output type, aligned live device
extent, route/cardinality, alias and output/status separation checks. New
host dispatch branches must preserve the same `r5_variant` and `row_bytes`.

Actionable findings and their resolution path:

- Runtime arithmetic selection must map p28/p29 names to R5 storage before
  loading weights. The one-card streamed model uses compact ten-expert banks;
  the copied full512-only validator now explicitly admits that exact contract.
  Both names now map to R5 in `selected_variant`.
- The first rotated paired fixture allocated distinct route IDs for its two
  projections. This was corrected to one shared route allocation per bank.
- Timing initially reused expert IDs within a launch while reporting ten
  payloads. Timing now uses ten distinct experts, rotating disjoint banks of
  ten; duplicate experts remain a correctness fixture only.
- Copy checks initially interrupted timed repetitions. The current GEMV loop
  performs eight untimed exact preflight requests,200 compute-only requests,
  and eight untimed postflight requests. Dense heavy classes use eight full
  weight allocations; routed heavy classes use eight disjoint expert sets.
- Raw F32/BF16 classes need finite raw-element fixture generation, not random
  upper bits with FP16 scale overwrite. A separate raw-element branch is present.
- Packet28 standalone diagnostics tolerate some NaN payload differences.
  They cannot stand in for this packet's strict v2 byte gates. Runtime K1
  compares every output byte; the existing nonfinite arithmetic limitation
  remains explicit in NONFINITE-GEMV.md, never an exactness pass.

The parent and implementation agent own final fixture receipts and any later
changes. Exact device gates, determinism and rotated timing remain pending
until the coordinator executes the sealed windows.

Final source verification: the bank-size validation extension and CPU-only
row pragma are the only body changes in copied `p28/submit.cpp`; no packet28
device arithmetic body changed. K1 also exercises odd9-row tails and route
status failures. Shared route-bank identity, source/output extents, all34
registered workload shapes, and eight-copy timing admission were re-read
after their fixes. No remaining finite-arithmetic defect was found in the reviewed
new-down or copied packet28 paths.

Final reviewed integration hashes:

- `p28/submit.cpp`: `10ba4dee0b311c7d0f487d11159d06d8f16304ff3f9e745e62950d5ff54aa92d`
- `p28/submit.hpp`: `6d0bddcbb38d635c9d5194b73cba7624db27a7617754af5369bfa51e731c5bbf`
- `p28/dense.hpp`: `bc6d77353fa71520e15f2b349db381ced4370d8413fae3b6687cefed56297b47`
- `p28/expert.hpp`: `fe0edeb0afedccd2b835d636c9d5e53f7725c995c192be2c6526377cdb58f63b`
- `p28/registry.hpp`: `add5690af080348ac78cbc3a19e41ac4e46fcef133cc6c2a162e3089ea377d85`
- `gemv_timing.cpp`: `15bfa0bc28582fd4487dddad8062a04c49da80059767d5a702f133da01bac918`

The five source/copy pairs in `p28/source-proof.json` were independently
rehash-verified after compact-bank validation was extended. The new-down
exceptional-value probe has a separate failed Intel-host diagnostic; see
`review-expert-down.md`. This failure is not NaN-canonicalized or counted as
an exact exceptional-value pass.

Packet29's final independent diagnostic reports 31,416 finite comparisons per
process, all exact in four processes (GNU/Intel, two each). Mixed nonfinite
inputs remain unqualified: Intel reports 1,254 candidate-versus-R5 and 1,254
candidate-versus-scalar differences; R5-versus-scalar has zero differences in
this diagnostic. GNU reports zero differences. No failure was relabeled equal
and no kernel arithmetic was changed. See `expert-down-review-gates.json`.
