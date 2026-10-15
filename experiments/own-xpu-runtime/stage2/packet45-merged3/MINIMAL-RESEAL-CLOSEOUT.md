# Packet45 owner-directed minimal reseal closeout

The diagnostic handoff is commit c726c601da06935eaad8d669bd984cecb1c8888a. Fix 5 is commit 4bd493a72. Qualifying CPU admission is now sealed; device exactness and speed remain the coordinator's job. Start a fresh qualifying prerequisite chain without the diagnostic flag. Diagnostic results can never be promoted, including after resealing.

## Root cause in three lines

P39 fixture setup copied the first 268,697,600-byte IQ2 expert bank in one operation after GEMV timing completed.
`p39_fixture.cpp:OwnerBackend::copy` exceeded CopyEngine's 134,217,728-byte transfer limit; both allocations were live and large enough.
The owner now stages at most 4 MiB, waits for completion before reuse and retires each event; the checker and ABI are unchanged.

The old rehearsals reduced tensors to four rows/ten experts and used zero timestamps, so they missed both production bank extents and winner adoption. The sparse production-size gate and 244 forced winner selections (6,757 extent checks) close those gaps. P39 full-size replay passes eight cases and 3,668 copies; CopyEngine's five negative invariants still refuse violations. Audit 6 adds 28 window/context/draft rows, 375,396 model copies and 2,000 canary copies, with no new defect. The full per-window table is in [COPY-AUDIT-6.md](COPY-AUDIT-6.md).

## Minimum qualification and explicit reuse

No new real-model CPU run, compiler matrix, or sanitizer rebuild was performed after the owner directive. The compiled-source delta is exactly `p39_fixture.cpp` and `gemv_timing.cpp`; neither is called by production decode. Both are linked through the common objects, so their changes alter executable identity. Compile/link commands and the remaining source closure are identical to the historical real-model qualification. `fixture_delta.py` refuses any additional compiled-source change. Six historical real-model cases (48 tokens, 2,304 layer fixtures) and six historical draft arms (378 valid fixtures) keep their original receipts and binary identities; the seal explicitly records reuse.

The already completed 79 miniature cases, arithmetic/compiler/sanitizer/owner gates and three 9/9 coordinator chains are retained. Wrapper receipts preserve execution source hashes alongside explicit metadata revalidation. The new diagnostic path passed one 4096/dr0 chain, 9/9, and 14 unit tests; its source-edit bookkeeping exception is recorded, not hidden or called a fresh final-source execution.

The minimal reseal revalidated audit metadata and ran only eight audit mutation tests, six fixture-delta tests, 11 retained-state comparison tests, 45 seal-binding tests, and 88 blocked-launch admission checks. Every launcher was blocked. The final seal binds 31 gate receipts. Existing arithmetic totals include 854,164 selection, 4,752 HC, 2,232 fusion, 3,369 native-controller checks and 15 mailbox gates. These are retained evidence, not newly repeated runs.

All reseal work used cores 4-15,20-31, nice19, ionice3 and OMP_NUM_THREADS=2. The final freeze verification confirms 356 sealed source files and 41 artifacts unchanged from diagnostic readiness. The prior seal/receipts are retained in `evidence/minimal-reseal/before-reseal.jsonl.gz`; raw tests, rebind records and the final freeze check are alongside it. Protected incident/device evidence remains byte-identical.

## Seal hashes

- `build-receipt.json`: `7e0317b026d15fafe0e223040a0760bc81c6cb5b4db45574448e69ff0e5f110e`
- `cpu-tests.json`: `42543e9503951169a4fbcae65f647323bfe50e40ba878c464eff3886978bbc9b`
- `window-seal-binding.json`: `96bb8fbd06538ee24ee85132365a58b60fa8d40510719ff4b5eb2142800de7ce`
- `copy-adoption-gates.json`: `a70aaedba996df47857193982384654b4a1c9964380a0b0871c6bd9ab6c912b6`
- `audit6-gates.json`: `8e5913572a71fa95ee0b63723ffca010a63dd3cd4d1c2237dc09c7cbb4fecfc9`

## Device identity

All five device executable hashes differ from the preceding qualified seal because the host-side fixture owner and GEMV timing translation units are linked into common binaries. No executable changed during diagnostic enablement or this reseal. ABI, CopyEngine guard and device arithmetic are unchanged. These are CPU provenance/size checks; no device binary was executed by this repair session. Current executable hashes are in [BINARY-HASHES.md](BINARY-HASHES.md).
