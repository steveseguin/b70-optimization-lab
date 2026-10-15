# SPEED2 closeout: save the speculative write set

The repair saves a conservative union of bytes that a speculative target half
can write. It preserves the full-state rollback contract. It does not discard
old bytes merely because a later launch overwrites them.

## Receipt attribution

SPEED1's qualifying pair-A result was 35.480887 tok/s, with every token exact.
Its reported hit/miss medians were 24.74/43.05 ms versus packet44's 23.19/39.33.
The retained receipts do not time capture submission, capture completion and
controller work separately. The following attribution distinguishes measured
command envelopes from paired estimates; the whole hit regression cannot be
assigned to snapshot copies.

| Steady positions >=100 | SPEED1 dr0 | Packet44 record |
|---|---:|---:|
| Rank0 speculative forward median | 16.923 ms | 19.159 ms |
| Rank0 non-speculative forward median | 15.020 ms | 19.207 ms |
| Rank0 speculative command envelope median | 18.095 ms | 19.426 ms |
| Rank1 forward median | 21.181 ms | 18.845 ms |
| Rollback command median | 2.767 ms | 0.020 ms |
| Draft command median | 2.769 ms, rank0 | 3.648 ms, rank1 |

At 255 matched miss/replay positions, speculative minus non-speculative rank0
costs **0.925 ms outside the inner half timer**, plus **1.918 ms forward**
(**1.911 ms waits**): **2.851 ms per command**. These are capture-submit and
capture-drain proxies, not measured GPU copy-event durations. `rank.hpp:113`
starts capture before the inner timer at line117; the history readback at
line120 drains the queued capture. Restore submits and drains before bank and
host metadata restoration (`strict_snapshot.hpp`, `SpeculativeImage::restore`).

The busy accounting matters: `pipeline.py:503-513` counts complete HALF and
DRAFT command envelopes, so capture submission *is* in reported rank busy.
Rollback is omitted there. Comparing only the inner forward to reported busy
would misclassify capture submission as unaccounted time.

An exact additive partition of pooled steady-cycle **means** follows. These are
not the headline median of per-request means.

| Run/cycle | Before next rank1 HALF | Rank1 HALF | Completion observation | Total |
|---|---:|---:|---:|---:|
| p44 hit | 3.685649 | 19.079473 | 0.391374 | 23.156496 ms |
| SPEED1 hit | 3.296715 | 21.573928 | 0.011794 | 24.882436 ms |
| p44 miss | 19.682200 | 19.568150 | 0.098154 | 39.348504 ms |
| SPEED1 miss | 21.359062 | 21.973847 | 0.011840 | 43.344749 ms |

SPEED1's miss pre-HALF gap contains 2.772624 ms draft, 2.760506 ms rollback,
15.294809 ms target redo, and 0.531123 ms other coordination. In p44, rank1 draft
overlaps rank0 redo; adding their envelopes would double-count about3.63 ms.
The ordering is in `native_controller.hpp:92-96` and synchronous rank0 calls at
line34. After steady drafts, completion to the next command's send is about
0.49 ms. `Backend::start` calls `cancel()` before recording sent (line33), which
runs the progress callback (`rank.hpp:251,281`) and draft result publication
(`mtp.hpp:232-247`). Event timing queries at line238 occur after the draft wall
timestamp at line236. Their individual contribution is not independently timed.

`speed2_attribution.py` reads the original receipts and writes hash-bound
[evidence/speed2/cycle-attribution.json](evidence/speed2/cycle-attribution.json).
SPEED1 receipts were moved by the coordinator to `build/results-65c5eb22b/`
during this analysis; they were only read. Pair-B status is recorded in that
artifact. Same-boot p44 controls remain 37.940267/37.917139 tok/s.

## Write coverage and full-state proof

`SnapshotWriteSet` in `strict_snapshot.hpp` derives an allocation-relative
prefix from every launch's operator, shape and input element count. It takes
the maximum across the half and every selectable parallel implementation,
including candidates not chosen by the current dispatch. The 48-plan sweep
executes that exact extracted derivation without weights or model arithmetic,
checks it against the actual `specialised::scratch_floats` and
`round2::scratch_floats` functions, and records each site's bound. Unknown
operators, unsupported geometry and nonparallel scratch use full coverage;
a bound exceeding its allocation is rejected, never clamped.

The largest production scratch writer is attention value:
`6144 * ceil(min(context,budget+3)/32) * 4 = 1,597,440 bytes` at budget2048,
for both contexts4096/32768. Other bounds cover norms, gated norms, GDN,
QSA preparation/pooling/selection, route, gather and argmax. Pool scratch uses
absolute block indexing, so its bound covers the full capacity prefix rather
than just one small block. Mini GDN/QSA uses local scratch; simple mini route,
gather and argmax remain covered by their global bounds.

QSA append writes K/V/raw row `position` and, when a four-token pool completes,
pooled row `position/4`. That pooled row is saved unconditionally as a safe
superset. The parallel implementations agree (`kernels.hpp:176-182`,
`specialised.hpp:147-158`, `p42_cooperative.hpp:67-74`, `adapter.cpp:84-88`).
Only allocations whose sole scheduled writers are QSA append receive this
narrowing. A different writer retains full allocation coverage. The QSA IDs
output, including its sentinel suffix, is still captured in full.

All other existing extents remain covered: inactive recurrent banks, plan
outputs, full standalone workspaces, layer snapshots (which have a full-buffer
clear), bank/launch metadata, shared-slot ownership and sticky-error handling.
Already committed recurrent banks and valid QSA prefixes retain their existing
illegal-write detection. Invalid tails and unused scratch bytes are protected
by being untouched, and their complete raw bytes remain in state comparisons.
The private backup allocation size is unchanged, preserving memory admission;
request boundaries still clear only that private backup.

Let W contain every byte any launch prefix can write. Capture stores old[W].
A completed or cancelled speculative half leaves old[not W] unchanged. Restore
writes old[W], so the entire resulting allocation equals old. This applies to
every cancellation prefix, including a capacity transition and terminal EOS.
The full byte comparator is unchanged and does not mask scratch or cache tails.
The CopyEngine guard remains128 MiB; batching and copy ordering are unchanged.

## Qualification and expected effect

The metadata sweep passed48/48 plan/dispatch rows. The mini gate passed42
executions and36 full-state checks, including four deliberately omitted required
streams extents rejected by the unchanged comparator. Both native and Python
controllers and both draft placements are covered, including cancellation before,
midway through and after the half, terminal EOS, request boundary and32-to-64
launch admission. The fresh mini receipts also verify that copied bytes actually
fell while private-backup capacity stayed identical to SPEED1.

| Context | Draft placement | Capture / restore bytes, each | MiB, each | Submissions, each | SPEED1 bytes / submissions at position100 |
|---|---:|---:|---:|---:|---:|
| 4096 | 0 | 46,415,032 | 44.264824 | 30 | 360,552,888 / 32 |
| 4096 | 1 | 48,614,936 | 46.362816 | 32 | 372,212,760 / 34 |
| 32768 | 0 | 46,415,032 | 44.264824 | 30 | 700,029,368 / 34 |
| 32768 | 1 | 48,614,936 | 46.362816 | 32 | 779,584,536 / 37 |

There are935/1021 individually validated component extents. At32 descriptors per
batch,30/32 submissions are the minimum for this transport. The current payload
fits below128 MiB per batch and each original CopyEngine component is checked.
The 4K byte reductions are87.13%/86.94%. The checked production numbers derive
from tensor/allocation metadata, not a device timing or real-model CPU execution.
See [speed2-snapshot-inventory.json](speed2-snapshot-inventory.json) and
[evidence/speed2/plan-writer-sites.json.gz](evidence/speed2/plan-writer-sites.json.gz).

No build started before05:15 UTC. Only GNU, device-link and mechanically required
ASAN targets are rebuilt; `seal_context.py:83` requires ASAN's compiled source
identity to match. There is no real-model CPU suite or compiler matrix.
The explicit SPEED2 extension of seal6 retains historical executions under their
original hashes. Passing coordinator device windows W2m, WS, WSs and WS128x are
the new artifact's real-model exactness authority and mandatory publication
citations. Every other admission and runtime safety check remains enabled.

Before device measurement, the predicted direct pair-A hit saving is **0 ms**:
rank0's approximately18 ms command already finishes before rank1's21 ms command.
Any reduced resource contention is unmeasured. The predicted miss saving is
**1.5-2.2 ms**, chiefly restore. Removing about87% of copied bytes suggests roughly
**1.6-1.7 ms less capture-drain burden per attempt**, largely overlapped on pair-A
hits. The approximately0.925 ms CPU descriptor/submission cost does not scale
with bytes, and the approximately0.49 ms controller gap is unchanged. These are
estimates, not a speed claim. The cheapest confirmation is the coordinator's
same-placement WS128 chain with the unchanged immutable token oracle.

## Final seal and handoff

All39 seal gate receipts bind41 artifact hashes. Fresh short tests passed9
fixture-reuse checks,13 amendment checks,8 audit checks and45 seal-binding
checks. Final admission passed88 blocked-launch checks with the real fault latch
unchanged. No real-model CPU suite, compiler matrix or device binary ran.
GNU/device/ASAN incremental rebuilds took33.60/40.75/104.95 seconds.

All five device binaries changed, as did the five GNU and five ASAN binaries
that link the model entry. The other26 recorded artifacts are unchanged. Only
`strict_snapshot.hpp` changed in the compiled source closure; the repair selects
copy extents on the host. Arithmetic, kernel-selection rules, public/protocol ABI
and exactness comparisons are unchanged. Linked binaries postdate the last
compiled-source change. Passing device windows are still required for new speed
and real-model correctness claims.

Seal SHA-256 values:

- `build-receipt.json`: `9e0b3ce4ff13f20c2ec55e2580ae2716bdf6c8ab09aec1297534f9a9cb2aa29e`
- `cpu-tests.json`: `78ba95f5a74e7b64f0b67863ad55f0bf145c07010c0fea130a383f5b3e1ea503`
- `seal6-amendment.json`: `be707c77d929e554e8620614b83ed5d4c2ac216573e39e69f431c9f32882f64d`
- `window-seal-admission-gates.json`: `a4e334932866028077abc58212174cba373a7b5502ddef12b4b0f8cbc13608bf`
- `window-seal-binding.json`: `56936cf198437555d2c16243f30660299ca2447421a629690367aec2864e1171`

Pair-B SPEED1 WS128 was still absent at the final read-only check; its existing
partial directory was not changed. No pair-B cycle saving is claimed from missing
evidence. The allocation/write-set counts above cover both draft placements.
