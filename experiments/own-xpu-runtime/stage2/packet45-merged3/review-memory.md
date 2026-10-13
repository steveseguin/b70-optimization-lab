# Independent packet45 memory review

CPU-only source and historical receipt review. No device discovery, driver
query, device binary, or allocation ran. Both placements at 32,768 retain
full BF16 cache and exceed the 1.5 GB free allocation floor. Driver overhead,
actual residency, and new half times remain unmeasured.

## Evidence and formulas

`memory_plan.py` retains packet44's byte-exact compressed packet38 source
censuses and verifies their SHA256, launch identity, and safe teardown. The
historical C256 target allocations are 27,253,499,452 bytes on rank0 and
27,854,569,876 on rank1. Its historical draft allocation is 3,345,271,094:
3,326,953,472 weights + 606,208 cache + 17,711,414 fixed scratch/control/buffers.
Inherited explicit reserves are 46,500,548 and 1,228,800 bytes. These are
planning reserves, not measured allocations.

C32768 growth over C256 is 76,988,416 bytes/QSA layer. Every rank also adds
packet44's 3,670,016-byte RoPE growth; the draft borrows that table.
Moving layers22–23 transfers one GDN layer and one QSA layer. Historical
layer22 uses 1,117,597,962 bytes on rank0, including its 1,634,304-byte
alternate bank; rank1 receives 1,115,963,658 bytes because it does not
speculate. Layer23 uses 1,106,681,302 bytes at C256 plus QSA cache growth.
Thus C32768 removes 2,301,267,680 bytes from rank0 and adds 2,299,633,376 to
rank1. Remaining alternate-bank allocation on rank0 is 27,967,488 bytes,
versus 29,601,792 with 24 layers. These banks are already counted in the
historical baseline and transfer formula.

Rank0 draft additionally requires the unchanged output head: 839,321,600
bytes in the admitted head storage. Both placements require a
3,422,259,510-byte draft at C32768. Private draft logits, final activation,
head workspace and FP32 input already belong to its fixed scratch inventory.

## Findings fixed

The old plan omitted packet40's strict rollback image. Reproducing
`SpeculativeImage` selection against the hash-bound C256 census and retained
packet40 launch plan yields 316,271,288 bytes for 22 layers and 319,074,840
for 24 layers. It excludes alternate banks, weights, immutable metadata,
active, and next_token, while retaining selected mutable target buffers and
standalone scratch. Adding respectively five or six QSA cache-growth terms
produces 701,213,368 and 781,005,336 bytes at 32768. The private image reserves
complete invalid cache tails; each capture copies only the suffix beyond the
committed position. Active recurrent banks and committed QSA prefixes remain
independently checked protected state.

The generator recomputes this selection and asserts both constants. Snapshot
evidence records the source-plan hash and included allocation-inventory hash.
The ledger conservatively retains pre-fusion buffers: removing unused fusion
temporaries cannot increase these ceilings. Every new allocation must be
added explicitly.

The image must construct before the draft provider. Otherwise its scan can
include draft state or reject pinned memory as a device snapshot source.
The merged rank lifecycle keeps this order.

Packet40 publication and half staging are pinned host memory:
8 + 4 + 4*2560*2 = 20,492 bytes, separate from each rank's 4 MiB slab.
The reverse handoff extends shared IPC to 3*65536+4096 = 200,704 host bytes.
Final streams arrive in existing private draft merge.hidden; no extra device
handoff buffer is required.

Using the rank0 placement for rank1 draft would overfill its intended margin.
The rank1 path retains 24/24; rank0 uses 22/26. Admission keys both capacity
and draft rank. `CAPACITY.md` records every ceiling and free margin, against
34,242,297,856 bytes per card.

## CPU gates and limits

`memory-plan-gates.json` records 24 admission successes (both placements,
three capacities, two ranks, draft on/off), 24 one-byte-over-plan rejections,
three unsupported-context rejections, two invalid-placement rejections,
and 12 allocation-margin checks: 65 total. These check admission arithmetic,
not device behavior. The current census remains required before first HALF.

Head storage cannot silently change: a candidate needing more bytes requires
an updated ledger. Snapshot capacity from pre-fusion outputs is a conservative
ceiling until a live census confirms the merged inventory. Driver residency
and performance remain coordinator GPU checks.

## Merged allocation implementation follow-up

Reviewed stabilized `rank.hpp`, `mtp.hpp`, and `main.cpp` after placement
integration. The owner constructs the strict image before creating a provider.
The draft constructor shares an existing output.weight only when present;
otherwise it allocates its own head with the selected unchanged arithmetic.
That is the required rank0 duplicate, and no second target-head scratch bank
is added. Reverse handoff uses the preallocated draft merge.hidden buffer.
The three IPC slots occupy 200,704 host bytes. Publication/half staging stay
pinned host allocations. No additional device allocation beyond this ledger
was found in these handoff changes. A misleading head_weight_shared receipt
was identified and corrected to reflect whether target output.weight exists.

`cpu_merged_gate.py` is a separately executable CPU harness. Writing and syntax
checking it is not an execution receipt; its future receipt must bind a fresh
host-only build and every compiled source hash. No new timing or residency
claim follows from this implementation review.

## Final allocation re-review after rollback and epilogue integration

The rollback fix now saves both launch extents, restores both prepared-command
banks through the existing QSA admission path, then restores FP32 lookup
metadata. The new fields and command vectors are host metadata; this change
introduces no device allocation and does not enlarge the strict rollback image.
Active and alternate recurrent allocations remain the same banks.

The packet39 plan rewrite absorbs the original inputs and outputs into surviving
GEMVs, keeps the layer-end identity, and dispatches epilogues against already
allocated buffers. It adds no weights, KV storage, scratch allocation, or
private device arena. The device ceilings above remain conservative because
they retain the historical pre-fusion buffer inventory. Main initialization's
new zero-fill uses one bounded 4 MiB host temporary and existing device storage.
These observations do not claim device exactness or new measured performance.

The 65 admission tests were rerun successfully after this review. The test now
binds its exact source snapshot and generated ledger, checks that the stored
ledger equals the generator, and refuses a source change during the run.
[The receipt](memory-plan-gates.json) is the machine-readable source authority.
When a listed source changes after this snapshot, rerun
`python -B test_memory_plan.py` under the required nice/ionice/OMP wrapper;
refresh the final seal from the new receipt. No compiled binary was executed
for this memory review.

Reviewed snapshot source SHA256:

| Source | SHA256 |
| --- | --- |
| `memory_plan.py` | `ec9e50a4ba33b1b935dfd0fd57dd348c4c7417c367df3ad9b649b46fbd8f304c` |
| `memory_gate.py` | `463105fb7fe10c598d318c6169df263be7d26b35c7fd2e4bb05196191046630d` |
| `test_memory_plan.py` | `4fc530ff49aca9aad302e967fb51520d93c926a59f19704e7a77c746feccebca` |
| `strict_snapshot.hpp` | `b0eeff72dff303bd8186b2c36b6362c1bcf62c8a85ba74a5c8eddb5a85a7118b` |
| `rank.hpp` | `3e87bd512f69019499fc50bdb75a333d6d3018817eb759fc4c4472b7677cddd0` |
| `mtp.hpp` | `ab81b1640de3cfdd2407762cc05d3efec1f08381dafb44b0bc0ac57c41bb8b82` |
| `main.cpp` | `7e8bb826de6463ca5cb48fa62be891f78cbcf71eba9011a2d5a79ab3f6a47296` |
| `p39_plan.hpp` | `b87b0cfc5dd0f9883e40bdf6154a0218511874897b064f7bccee23cabcc86689` |
| `p39_submit.hpp` | `f4ac85a5e48b3cf5990b1948fcf75629601b18af6373eedbf4bcc0058a9f697b` |
| `memory-plan.json` | `2b21331812f4a88b001ba2acc410c7cc883acac51ed466962fcc39c80c66c9ae` |

The separate runtime correctness campaign has expanded since its initial
harness draft. Its planned 79-case mini campaign and six-case real subset
are separate evidence; these 65 memory checks neither substitute for them nor
assert that they ran. Their own completed, source-bound receipts govern scope.
