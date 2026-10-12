# Coordinator KD host references

The resumed plan needs GNU references only at 4,096 and 32,768. Run the
following once after the Intel composite has ended:

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B experiments/own-xpu-runtime/stage2/packet44-context/resume_draft_references.py
```

The final observed outcome is in capacity-draft-gates.json and the CPU seal.
The original six-arm capacity_draft_gate.py is retained as a reproduction
helper; its full matrix was not run during resume. The helper supplies input
preparation, host-only ELF checks, per-arm admission, memory monitoring,
SHA256 fixture maps, and verified log compression to the reduced runner.

The input preparation verifies the packet38 captured stream provenance and
copies 94 confirmed rows (87 prompt positions plus seven generated positions).
Each row's token comes from the following confirmed target row. This runs only
the draft head; it does not rerun the target-model CPU matrix. Nine draft head
outputs and the valid-prefix state produce 63 files per capacity. All must
match the frozen packet38 reference verified by draft_baseline.py. The final
full-capacity draft cache is also retained for KD comparison.

Retain build/draft-reference-c4096, build/draft-reference-c32768, the captured
streams and capture table. These are coordinator inputs, not disposable
scratch. capture-run-incident-retrospective-c{capacity}.json binds the binary,
table, context, dispatch and every reference file. build-receipt.json exposes
them through draft_capture_fixture_sha256_by_context. Logs are hashed,
compressed and round-trip checked. No Intel reference arm or 256 KD reference
is claimed. At most one draft process runs at a time, two OMP threads, nice19,
idle I/O and inherited affinity; root floor 8 GB, build cap 4 GB, anonymous
memory guard 8 GB. No device runs on this preparation path.
