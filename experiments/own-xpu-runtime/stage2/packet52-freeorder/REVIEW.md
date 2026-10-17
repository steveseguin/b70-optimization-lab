# Packet52 independent review

This review covers the source diagnosis, proposed arithmetic, production
controls, native harness, admission wrapper and evidence parser. The reviewer
ran the CPU-only mocked Python tests at nice19 on cores4–15,20–31, with
`python3 -B`. No compiler, device program, health probe, service or model
oracle was launched by the reviewer. Compilation and arithmetic-test outcomes
belong to the packet's build and CPU receipts.

## Scope and arithmetic

The production census selects **ten** experts. The brief's eight-expert
wording cannot reduce the fixture. QKV/Z control remains packet45's accepted
dispatch: the faster packet48b candidate numbers were not accepted controls.
Expert gate/up and down use accepted packet48b kernels; HC low/gate and output
projection/combine use packet51 winners. The small FFN control includes its
F32 router, both Q6 projections and scalar F32 gate in the production tuple.
HC includes low and gate on both sides, preserving rounded activation before
gate. Attention includes projection, BF16 rounding and all four stream updates.

The five fixed orders have explicit lane counts, tile-to-accumulator mapping,
adjacent reductions and split-part ordering. The split arm's second device
stage and partial writes count in timing. Subgroup collectives retain padded
lanes; local table initialization reaches a uniform workgroup barrier. IQ2
local-table staging is enabled only for IQ2. The other formats do not claim a
table-placement effect. No floating-point atomic or unordered reduction
implements these orders.

The attention candidate shares the same four injection factors per workgroup
as the accepted control. Its unsplit kernel and split finishing kernel compute
`2*sigmoid(widen(inject)/4)` before a uniform barrier, then combine the rounded
BF16 projection with each stream. Padded work items reach that barrier before
exiting. The factor-sharing change preserves the original arithmetic expression;
device E still qualifies the local-memory and barrier implementation.

The scalar mirror materializes a decoded row, then assigns scalar products
to their prescribed chains. It does not invoke the device lane traversal.
Shared format decoding is an existing lab dependency; it is not a new
independent weight-format implementation. A later full-model oracle must
continue to decode original packed bytes and qualify the selected orders
against that independent source. Different old-order answers are information,
not candidate failures. New-order CPU/device byte equality remains mandatory.

The bounded host proof now calls the same format/K-specialized decode helpers
as the device path. Four bounded processes compare all35 format/order cases:
two GNU and two Intel host builds. The Intel host build compiles the new packet
with `OWN_RT_HOST_ONLY`; the pinned supporting baseline objects are reused,
so this is cross-compiler coverage of the new arithmetic, not an independent
Intel rebuild of every historical dependency. Two separate GNU full-shape
processes cover42 control/candidate cases each on one M1 fixture. M2 and the
second full-shape fixture remain required device E cases.

The probe uses valid, active finite fixtures. It does not establish the full
engine's inactive/error/invalid-route/nonfinite policy. Those controls, full
model state, continuous recurrence and model quality remain packet53 gates.
M2 is two changing serial rows, not batching or measured weight reuse.

## Corrections incorporated during review

- Replace a mirror that called the device's lane helper with a separately
  traversed scalar reference; compare the distinct traversals in CPU gates.
- Exercise the four-member small FFN candidate as the same fused operation in
  E and T. Four isolated E launches would not qualify the T binding/index path.
- Compare every split4 partial to its CPU mirror, including concatenated
  partial ranges for the four-member tuple.
- Include controls in E and bind every repeated T control to its candidate
  with `pair_variant`; otherwise four control rows would share one key.
- Pass the zombie-tolerant memory sensor explicitly to the inherited
  supervisor. Replacing its module attribute alone does not replace Python's
  already-bound default argument.
- Revalidate exact companion hashes and native outputs before timing and
  before combining two owners. A stored `passed` value is insufficient.
- Require all seven classes, all five variants, both M2 rows, every measured
  iteration, the expected event counts and event-duration sums.
- Bind final capture byte extents as well as buffer counts. A present buffer
  name alone cannot establish that its complete output was checked.
- Copy the sealed case manifest into each native run before launch. The mock
  coordinator now checks this handoff instead of supplying the missing file.

## Safety and decision checks

The script wrappers set nice19, the approved affinity and a closed environment.
The device window requires coordinator authorization, its own user unit,
physical card0/PCI0000:23:00.0, storage/memory admission, no visible Xe owners
and an admitted kernel-fault boundary. It uses cooperative SIGTERM and retains
a child that does not drain; it never hard-kills or retries. Existing oracle
and packet49c units are not addressed by this packet.

The decision uses one common variant per class, chosen by its minimum saving
across both owners, with the unchanged control as a zero-saving alternative.
Both M1 class-budget sums must reach120us. M2 cannot qualify the decision.
This sum is an operator budget, not a measured integrated layer or model rate.
Device results are pending; neither a positive nor a negative speed conclusion
can be drawn from CPU preparation.

The mocked Python suite checks authorization/watchdog/priority/affinity
refusal before launch; storage/build limits; specific fault signatures;
closed environment; changed/missing/failed seals; zombie versus live missing
RSS; complete native captures and events; fresh-owner identity; companion
rehashing; command assembly; and cooperative retention. Parser mutations
remove controls, M2 rows and individual cases, duplicate records, corrupt
hashes/counts/durations, and supply invalid distances. Selection checks cover
the exact120us boundary, one owner below the threshold, incompatible owner
winners, zero-saving control selection and misleading M2 improvements.

Final build/CPU receipts and the source seal bind the actual tested bytes.
E1/E2 still must establish device parity and fresh-process identity. T1/T2
still must measure the registered production shapes and select the outcome.
The sealed inventory requires252 comparisons per E owner and44,100 timing
records containing72,450 compute events per T owner, including warmups and
both serial M2 rows.
