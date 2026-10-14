# Packet45 fix 3: folded route descriptor writes

<!-- campaign-closeout -->

## Root cause

K2 submits the folded four-output route ABI to implementation 0 as its incumbent.
`packet18::simple`, `Op::route`, wrote the selected IDs and probabilities but
omitted the gate/down descriptors; those buffers retained their initial zeros.
The missing stores reproduce on CPU: this is not a rank32, NaN or device-math defect.

The owner reported the K2 failure on both card pairs under boot `13858eef` after
K0/K1a/K1b passed. The retained rank0 K2 events for both draft placements contain
200 one-stage incumbent submissions and 600 three-stage round2 events. They end
at repeat 199 of the round2 comparison, **before** candidate 6/rank32 is reached.
The old event label calls the incumbent `specialised`, but
`class_incumbent("route+gather")` returns 0 and its one-stage event confirms that
path. Repeated failure/teardown messages do not represent three tested versions.
No device output buffer was retained at the mismatch; the buffer-level evidence
here is the independent CPU reproduction, not invented device bytes.

## Why the previous gates missed it

`adapter_cases()` contains the K2 construction as case 8: `make_case(3)` followed
by `fold_pair`, with exactly the same buffer salt/fill and initial position zero.
Cases 9/10 change only the route scores to zeros/NaN; case 49 adds scheduled
active/error inputs. The ordinary fixture runs versions 0/1/2 but uses
`c.sites` (unfused) for version 0 and `c.new_sites` only for nonzero versions.
The six-setting HC matrix explicitly iterates only cases 51–54. Sharing a
constructor did not imply sharing its case coverage. Rank32 version 6 was not
in that loop either. CPU K2 rehearsals used `validation_only`, which checks
bindings and event structure while bypassing arithmetic and byte comparisons.

The normal score fixture contains finite BF16 values, many exact ties and no
special values. Its first selected expert is 24. Before the repair, descriptor
buffers 7 and 8 retain zero instead of 24 in case 8/49. In case 9 the expert ID
zero is correct but the row extents remain zero. Case 10 correctly sets the
error and leaves outputs untouched. All nonzero implementations agree with the
unchanged unfused reference in these cases.

## Fix and invariant

Complete the existing folded ABI in the route winner branch: for a winning
expert `j` at slot `rank`, write `[j, 0, g.mid]` and `[j, 0, g.h]` to outputs 2
and 3 when they are present. This is the same descriptor layout produced by
the unfused `expert_gather`, specialised, round2 and rank32 paths. No selected
probability expression, reduction order, tie-break rule, input, fixture, registry
choice or packet18 oracle changes. The existing two-output route is unchanged.
The ABI and number of submissions are unchanged.

`fusion_matrix.cpp` uses the real `Runner`, `packet18::submit_parallel` and the
device fixture constructors. It folds **both** arms and requires all five
outputs (error, IDs, probabilities, gate/down descriptors) to match the unfused
reference. It explicitly executes versions 0/1/2/6 and records stage counts
1/5/3/4 to catch silent fallback. Both combine-normalization modes use their
actual adapter path. The same executable calls the real p39 and small-GEMV
owner fixtures; validation-only mode is false. GNU and Intel each run O0, O2
and O3 with native targeting, precise floating point and contraction disabled.

## Fusion audit

None of the entries below was covered as a fused submission by the old six-arm
HC matrix. They are all exercised by the new six-arm matrix. “Separate” means
the corresponding shared device fixture, not an equivalent scalar substitute.

| Registry fusion | Actual matrix fixture/path | Coverage and finding |
|---|---|---|
| `route+gather` | Adapter cases 8/9/10/49, folded versions 0/1/2/6 | Missing version-0 descriptor stores; repaired; rank32 passes |
| `attn.combine+norm` | Adapter cases 6/7, folded 0/1 | Both unit-offset modes, same concrete body for both class names; passes |
| `ffn.combine+norm` | Adapter cases 6/7, folded 0/1 | Same fused body and all outputs; passes |
| `expert-checks-iq2` | Separate p39 owner fixture; p28 paired producer | Seven scenarios; passes |
| `expert-checks-iq3` | Separate p39 owner fixture; p28 paired producer | Seven scenarios; passes |
| `down-status` | Separate p39 owner fixture; p33/p28 producer | Seven scenarios; passes |
| `hc-low-act` | Separate p39 owner fixture; p28 dense producer | Seven scenarios including NaN; passes |
| `shared-up-act-q6` | Separate p39 owner fixture; p28 dense producer | Seven scenarios; passes |
| `shared-up-act-q8` | Separate p39 owner fixture; p28 dense producer | Seven scenarios; passes |
| `attention-combine` | Separate p39 owner fixture; p28 dense producer | Seven scenarios, complete streams; passes |
| `shared-down-combine` | Separate p39 owner fixture; p28 dense producer | Seven scenarios, both blend and streams; passes |
| `small.hc` | Separate small-GEMV owner fixture, round2/p30 | All tuple members, four input modes and malformed binding checks; passes |
| `small.gdn.ab` | Separate small-GEMV owner fixture, round2 | Both tuple members, four input modes and malformed binding checks; passes |
| `small.ffn` | Separate small-GEMV owner fixture, Q6/Q8 round2/p30 | All tuple members, four input modes and malformed binding checks; passes |

The registry requires a fused route implementation to match the route class and
the gather class to be specialised. Those rules match the merged table and do
not cause this defect. The removed repeated input row is intentionally absent
from the folded ABI; its consumer reads the original row. The complete CPU
model gates independently check that integration. No packet28-only entry is
misrepresented as a `known_fusions` entry: packet28 producers are exercised by
the p39 comparisons above.

## Evidence, qualification and limits

| Compiler setting | Before | After |
|---|---:|---:|
| GNU O0 | 6 failures / 372 checks | 372/372 |
| GNU O2 | 6 failures / 372 checks | 372/372 |
| GNU O3 native | 6 failures / 372 checks | 372/372 |
| Intel O0 | 6 failures / 372 checks | 372/372 |
| Intel O2 | 6 failures / 372 checks | 372/372 |
| Intel O3 native | 6 failures / 372 checks | 372/372 |

All 36 pre-fix failures are exactly buffers 7/8 in cases 8/9/49, implementation
0. After the fix all **2,232 checks** pass. Each arm includes 96 adapter-output
comparisons, 56 p39 scenarios and 220 small-fusion checks. The original HC matrix
remains a separate required gate; these counts are not substituted for it.

The final counts, hashes and verdict are in
[`evidence/route-gather-fix/qualification-summary.json`](evidence/route-gather-fix/qualification-summary.json).
The exact pre-fix and post-fix compiler outputs, compilation commands/source
hashes and retained fixture scratch manifests are in that directory. The new
seal requires the matrix, all versions and stage counts, exact sibling counts,
source hashes, binaries, raw logs and retained evidence. Eight mutation tests
check missing arms/versions, fallback, missing sibling families and stale bytes.

Reproduce with the priority/thread prefix in [CPU-REPRO.md](CPU-REPRO.md):
`fusion_matrix.py --label before` at the original adapter revision, then
`route_gather_campaign.py all` after applying the repair, followed by
`route_gather_summary.py`. Device mode in this campaign **only compiles and
links**. No accelerator executable, discovery call, `/dev/dri` access or sudo
is part of this work. Device qualification remains the coordinator's fresh
chain under the new binary/seal identity.

The initial gate bootstrap omitted `expert_down.cpp` from its link inputs; the
failed linker log is retained. It was a harness link failure, not arithmetic
evidence. Source fix and fixture evidence remain in this packet; the incident
trees and all device-produced directories are read-only throughout.

Rebuilding also exposed a pre-seal rehearsal defect: `coordinator_cpu_gate.py`
copied host binary hashes from the **old final seal** into its private receipt.
Earlier host-only repairs had kept binaries unchanged, hiding that assumption.
The rehearsal now obtains every host artifact from the current mode-build
receipt, checks its source provenance and exact bytes, and rejects missing
fixtures or any device path. Seven new wrapper tests cover the live build and
those rejection cases. Production window admission is unchanged. The refused
CPU chain is retained as `stale-preseal-scratch.json` and its referenced archive;
the refusal logs are retained with the same prefix. Qualification resumed at
the wrapper after this host-only correction; the already-passed arithmetic,
selection, sanitizer and owner receipts are unchanged and revalidated by the
final seal. `route_gather_campaign.py all` reproduces the complete corrected
workflow; `gates-tail` is the explicit resume point used for this recorded run.

Revisit if any fused ABI, dispatch mapping or fixture case changes: a same-build
scalar check or validate-only rehearsal cannot replace actual folded owner
submissions. This closes the omitted-store defect, not the runtime lane.

## Final qualification

All required CPU gates passed. Counts overlap where a helper belongs to a larger
fixture; they are not summed into a single headline.

| Gate | Passed count |
|---|---:|
| Fusion matrix, six compiler settings | 2,232 |
| HC matrix, six compiler settings | 4,752 |
| Selection | 854,164 |
| Arithmetic fixtures | 22,326 |
| Dispatch validation | 6,899 |
| ASAN/UBSAN fixtures | 3,657 |
| Fresh miniature pipeline cases | 79 |
| Real-model cases / token matches / layer matches | 6 / 48 / 2,304 |
| Cross-placement pairs / semantic draft buffers | 3 / 17 |
| Captured draft arms / reference matches | 6 / 378 |
| Owner suites / kernel tests / memory checks | 18 / 72 / 65 |
| Controller cases / mailbox gates | 3,369 / 15 |
| Wrapper tests | 131 |
| Existing seal mutation tests / new fusion seal tests | 45 / 8 |
| Blocked-launch admission | 88 |

The unchanged coordinator shell passed **9/9** CPU rehearsal windows at each
of `4096/dr0`, `4096/dr1` and `32768/dr0`: **27/27** total. K0 uses a host
structural shim and K1/K2 use validation-only fixtures in these rehearsals; the
new matrix separately executes the real arithmetic. The real-model gate is a
first-eight-token correctness subset, not a performance or publication gate.

All 150 protected files and the original fixture hashes are unchanged.
The seal binds 25 gate receipts and 41 primary build artifacts.

| Seal | SHA256 |
|---|---|
| `build-receipt.json` | `95c76ac330f90cb9005457ff8ec0e51c715fa311e79b27c42ab9ad07108dd5d9` |
| `cpu-tests.json` | `d779a25007b680b1fe50abf0b6dce082876fe18efe413b5dd43e9a5365dd1f94` |
| `window-seal-binding.json` | `825f463daa02ba04a354ede4ae8d1ab1634f5160dca72eb5115d1dda4f447e2b` |

All five device binary hashes changed. The ABI and unfused packet18 reference
are unchanged. These are compile/link identities only: **no device binary was
executed**, and fresh coordinator device chains must qualify the new identity.

| Device artifact | New SHA256 |
|---|---|
| `device/jit-smoke` | `9d9e59863bb3cd6913389d8c330e43e0fb86d2204fcb3e4eadcd7324771b0058` |
| `device/k2-fixtures` | `70fd03c89874ff43671c49df5072201734c05e5a7eb013a258b17d42f41f3e2d` |
| `device/p33-linked-fixtures` | `16eb01ade5e0d908e253abd8a5faa2f23392c55640917a2346caab3081422b6c` |
| `device/own-rt-iq3` | `1b72982676c9d4839e1500564d13e8263ec10f92cae2150af325c9e3686d9fdc` |
| `device/nongemv-fixtures` | `39f22d9a9d9d212cdaae4f0686fbb8101644711096eff8822afafa7198f4a80e` |
