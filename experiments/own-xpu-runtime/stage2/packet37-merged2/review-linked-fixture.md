# Independent all-linked dense fixture review

Source-only review by the K2/dense reviewer. No compilation or device entry
was run during this review. This is correctness/admission review, not timing.

The fixture enumerates four formats and five K families, rejecting incomplete
Q6 blocks before dispatch. This gives 18 valid type/K pairs and both arithmetic
splits: 36 compiled dense template instantiations. Each runs six modes, giving
216 comparisons and 1,512 BF16 output rows. The modes cover varied finite
values, signed zero, subnormal values, large finite values, nine-row tails and
one-row tails. All values generated here are finite; exceptional/NaN policy is
unchanged and remains covered as unqualified diagnostics by the earlier gate.

Each expected row comes from `arithmetic::row` over the same immutable input
bytes and variant, then the same BF16 conversion. Exact `memcmp` compares the
copied output bytes, and every output is included in the aggregate hash.
Q6/Q8 variants 6/7 and scalar variants 0/4 use the intended split1/split4 path.
On the device, all 18 split4 type/K cases invoke the linked `Finish` kernel;
the fixture waits on the final event before copying any output. The host path
finishes split4 inside its host operation, so device Finish still requires K1.

Per-case scratch spans the validated eight floats per row. The maximum case
is nine rows, keeping memory small. Case cleanup retires completed events,
then releases every allocation. Final receipt emission requires safe shutdown
with exit code zero. The wrapper additionally checks zero live bytes and zero
in-flight work. Failure delegates to the existing evidence-first owner handler.
Authorization is checked before creating a device or opening output files.

K1 runs the original fixture owner followed by this additional owner on the
first card, without overlap. K1a and K1b enforce four distinct positive PIDs.
The linked admission checks schema, device execution, reference exactness,
216 comparisons, 36 split instantiations, 18 type/K families, six modes,
1,512 rows, card identity, drained ownership, and exact equality to the sealed
host output hash. The wrapper binds linked receipt/output bytes and the device
binary identity into each K1 prerequisite. Thus an old K1 receipt lacking this
new linked evidence is refused.

One seal finding was reported to the root agent: the initial `build.py`
version read the linked host gate and output digest but did not verify its
per-row binary hashes against the current host binaries. Before sealing it
must bind all six compiler/repeat rows (GNU, Intel, sanitizer; repeats 0/1) to
the corresponding current `p33-linked-fixtures` binaries, require their exact
coverage, and require the shared output hash. This prevents stale host receipts
from qualifying a rebuilt linked fixture. Resolution is recorded in the JSON
review once the root's fix is inspected.

The actual device checks remain pending coordinator K1a and K1b. CPU source
review does not establish device compilation equivalence or kernel performance.

## Seal finding resolved

Inspected the root's final `build.py` change: the compiler/repeat set is exactly
GNU, Intel and sanitizer crossed with repeats 0 and 1, with a separate six-row
cardinality check. Every row must bind the current linked-host binary hash,
216 checks, 36 split instantiations and the shared output digest. The stale-host
receipt finding is closed. No source-review findings remain open.

Final reviewed source hashes:

- `p33_linked_fixture.cpp`: `1abb466123de8a71898ade5d65cf35aee16395481331cf99836e33d6051b4fe6`
- `p33_linked_fixture_gate.py`: `aac1dac3a41c78f075d750179d76be52c4bc94f0928042b5834ab7d158aed9d2`
- `window.py`: `090206826c2f1806e628e74f30c4884c464fbbdc0a7ecd84fb7bb1974f9a0c95`
- `build.py`: `56ac6040b5a4ce5e7aaef7ea8bf7ba140b97d34d5ee0309c6b2ce79cf5b34e1e`
- `p33_submit.cpp`: `c7bcacd934e0d06639aaecf46625a0c3e1a8fea47dda799d415e5c392f21b84a`

Final metadata refresh verified that the only later build change adds the three
independent review JSON receipts to the seal. The reviewed logic is unchanged.
