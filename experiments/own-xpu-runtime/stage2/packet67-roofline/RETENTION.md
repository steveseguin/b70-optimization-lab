# Retention and local rebuild

This is a local, sealed CPU-prepared experiment, not a publicly reproducible model package. It inherits packet64's verified local build objects, model census and packet49 oracle. No model weights, secrets, large binaries or generated caches are committed. `parent-source-manifest.json` identifies the copied source set; `build-device-receipt.json` binds the complete source and object closure. Only entry-main, p49d_submit and p60_submit objects are rebuilt. Expert arithmetic objects retain their parent hashes in `evidence/object-identity.json`.

The ignored build tree is below 1 GiB; repeated views use hardlinks. The retained synthetic expected/candidate buffers support the local seals. Small compiler receipts, per-case hashes and logs are committed under `evidence/cpu-{gnu,intel}`. The exact initial failing HC source and failing prefix evidence are retained under `evidence/failed-hc-*`; no failed output is treated as a passing fixture. Pre-epilogue build/compiler receipts are historical evidence only.

Offline assembly is gzip-compressed with deterministic timestamps under `evidence/registers/`. `register-report.json` records tool hashes, exact commands, source hashes and compressed artifact hashes. Offline temporary bitcode/SPIR-V/AOT trees were deleted after retaining assembly. The older report `evidence/registers-before-shared-epilogue.json` records the original paths; its artifacts now live under `evidence/registers-before-shared-epilogue/` with the same final path components and bytes. `evidence/register-history-retention.json` verifies that relocation. These reports are compiler observations, not measured occupancy or zero-spill claims.

All inspected kernels use 128 configured GRFs in this offline build. HC candidate spill metadata changes from 256 to 128 bytes after sharing sigmoid terms; flag store/load metadata remains 51/60. Production HC has 64 bytes. Original rows4 recurrence has 256 bytes and 10/14 flag stores/loads; head prepass has 256 bytes; the update has flag metadata 2/4 without a spill-size line. The final device JIT and real composition decide the effect.

To restore on this host, retain packet64's sealed build objects and compiler installation. Start with a new unsealed build directory; never overwrite a sealed view or its evidence. Copy `../packet64-record-bundle/rope.bf16` to this packet's ignored `rope.bf16`, and create `build/`. Every command below is CPU-only and serial, with stdin `/dev/null`:

```bash
P=/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet67-roofline
nice -n 19 taskset -c 8-15,24-31 env OMP_NUM_THREADS=2 python3 -B "$P/audit.py" </dev/null
nice -n 19 taskset -c 8-15,24-31 env OMP_NUM_THREADS=2 python3 -B "$P/build_engine.py" </dev/null
nice -n 19 taskset -c 8-15,24-31 env OMP_NUM_THREADS=2 python3 -B "$P/cpu_fixture.py" --compiler g++ --output "$P/build/fixture-gnu-b" </dev/null
nice -n 19 taskset -c 8-15,24-31 env OMP_NUM_THREADS=2 python3 -B "$P/cpu_fixture.py" --compiler /opt/intel/oneapi/compiler/2026.0/bin/icpx --output "$P/build/fixture-intel" </dev/null
nice -n 19 taskset -c 8-15,24-31 env OMP_NUM_THREADS=2 python3 -B "$P/fixture_receipts.py" </dev/null
nice -n 19 taskset -c 8-15,24-31 env OMP_NUM_THREADS=2 python3 -B "$P/selection_tests.py" </dev/null
nice -n 19 taskset -c 8-15,24-31 env OMP_NUM_THREADS=2 python3 -B "$P/inspect_registers.py" </dev/null
```

These are reconstruction steps, not permission to overwrite existing receipts. Build and sealing scripts intentionally reject an existing final receipt/seal. A reconstructed binary must receive new seals and qualification if its hashes differ. The original fixture generator and command lines reproduce synthetic buffers without running a CPU model. Use `verify_packet.py` for the current artifacts. Screen evidence stays in the ignored `screen/evidence/` directory; coordinator closeout must retain its result receipts before any later cleanup.
