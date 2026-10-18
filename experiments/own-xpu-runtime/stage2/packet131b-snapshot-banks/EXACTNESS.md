# Exact bank rotation argument

The arithmetic identity remains `iq3-p49-split32-v1`. The source change admits
the existing local packet62 `banks-batch` selection against packet124c bundle7.
`snapshot-banks.patch` records that admission and the CPU census helper;
`copy131.json` pins the frozen source copy. No arithmetic kernel changes.

At a committed boundary let A be the active recurrent state, B the observable
spare, and C the private reserve. The baseline snapshots B before overwriting
it. The candidate rotates only the destination binding, from B to C.

For each admitted GDN/conv writer, the source state is read-only and every
destination byte is assigned from the same inputs and arithmetic. Its output
therefore does not depend on the old contents or physical identity of B/C.
This is restricted to the banks discovered by `pipeline::banks` and covered
by `RedoBankProof`; it is not assumed for other intermediate buffers.

| Outcome | Baseline logical active/spare | Candidate logical active/spare |
| --- | --- | --- |
| Completed target step, accepted | F(A, token) / A | F(A, token) / A |
| Completed speculation, rejected | A / B after copy-back | A / B after inverse swaps |
| Partial speculation, cancelled | A / B after copy-back | A / B after destination rotation is undone |
| Corrected target after rejection | F(A, corrected token) / A | F(A, corrected token) / A |

The inverse includes the completed half's active/spare swap when one occurred.
Nonbank mutable outputs and the overwritten QSA rows still use the original
guarded flat snapshot and restoration. Existing QSA prefixes are never written
by the step. History, lookup and prepared-FP32 metadata, context extents and
rank0's shared publication slot follow the unchanged snapshot protocol.
Sticky target errors cannot be erased by rollback. Terminal/abandoned redo
retains its fallback behavior; the code does not assume a corrected half will
always follow a miss.

Each of the six ordered physical pairs has its own prepared commands. Rotation
selects a previously bound pair and updates any stale QSA context extent.
The production census fixture audits every GDN/conv source and destination ID,
each captured pointer, and the absence of the private reserve from those
commands for all six pairs and contexts 32,64,4096,32. Both banks remain
observable in the comparison: an old spare is not discarded from the oracle.

The CPU state fixture hashes every logical buffer and spare, every other live
nonweight/nonpinned allocation, and host/shared metadata. Only the private
rollback image, descriptor table and current private reserve are omitted from
the logical-state transcript. Their retirement is tested separately. The
fixture covers all positions 0–31 and later context boundaries, forced hits,
misses, cancellation cuts, four abandoned-redo paths and a 98-step mixed
sequence. Corrupting active recurrence, an older QSA row, or an omitted required
output must fail comparison. GNU and Intel fixture transcripts and repeats
must agree. Unchanged arithmetic dependencies remain the pinned GNU objects.

Separately, both compilers run the actual production-size `rec-both-plus`
kernel against differently poisoned destination buffers for every ordered
pair, including exceptional floating-point inputs. All output and recurrent
state bytes are compared directly against the unchanged kernel under each
compiler, and raw repeats must agree. GNU and Intel's unchanged host kernels
propagate NaN payloads differently in the explicit NaN fixture. A separate
diagnostic canonicalizes NaNs only after the strict raw bank comparison to
confirm that all other bytes agree. It never qualifies candidate/reference
equality, and no runtime byte is normalized. The eight full-Engine transcripts
still require raw digest equality across their GNU/Intel builds.
The reset regression retains the original failing control and repaired
21-case test. These are CPU gates, not a substitute for exact full-model device
outputs. The proposed smoke and two fresh candidate loads must still pass
the pinned device oracle before any speed conclusion.

Gate status is recorded by `evidence/ready131.json` only after all required
receipts and seals verify. The existence of this argument does not admit a
device run or turn inherited packet124c receipts into packet131 evidence.
