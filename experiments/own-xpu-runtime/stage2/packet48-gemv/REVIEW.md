# Independent preparation review

The requested read-only reviewer audited the candidate arithmetic, baseline
composition, M2 routing, captures, wrappers and summary, and authored
`test_validation.py`. The separate kernel-design agent reviewed the harness.
All work was CPU-only; neither reviewer accessed packet47 or model payloads.

Corrections applied before the final seal:

- Actual P39 IQ2/down controls include their status/error semantics.
- Paired gate/up uses the input-sharing helper; M2 has independently changing
  input/route rows and a shared CPU/device addressing helper.
- Existing sticky error7 survives an invalid route; the combined case is gated.
- Nonfinite weight-scale failures are retained and rejected at repack admission.
- Same-slot versus shifted-overlap weight reuse is explicitly separated.
- Exactness companions require all three raw files, complete native validation
  and matching window/native output identities; hash-only partial maps fail.
- Timing owners must be fresh and distinct from both exactness owners; final
  qualification reopens the current seal and revalidates raw event coverage.
- Physical LevelZero0 must be PCI0000:23:00.0 before context creation.

Sixteen mutation/protocol tests pass. They reject missing, duplicate, truncated
or altered captures, unchanged inputs, unsafe teardown, missing/overlapping
events, changed event sums/warmup labels, reused owner identities, changed
boot/files, incomplete companion closure, unsafe paths and source/binary/gate
seal drift. Recorded logs are linked by `python-gates.json`.

The review does not qualify device arithmetic, performance, register occupancy,
real-model finite-scale admission, capacity, or engine integration. IQ3 and
dense isolated controls use inherited arithmetic in an adapted launch wrapper;
full-runtime confirmation remains necessary.
