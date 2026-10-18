# Packet139 — bundle9, CPU preparation

Bundle9 is packet136 bundle8 with packet137 `token_input=both`. The native
engines are byte-identical to packet137's **v5** build. Banked rollback,
80128-row draft prefix, full target verification, BF16 KV and the
`iq3-p49-split32-v1` oracle remain fixed. No device result is claimed here.

[Review26 preregistration](PREREGISTRATION.md) requires packet137's lane-B
one-load five-view bracket (both candidate views at least 0.5% above every
control, at most 1% control drift, every output exact), plus this bundle's
lane-A twelve-prompt 64-token smoke. There is no lane-A timing grid. Only then
may the coordinator start the fresh `build/device-cards01-a` chain.

The [orchestration](../../ops/packet139-orchestration/README.md) contains the
CPU preparation, real-entry startup probes, readiness reader and complete
submission tool. Missing device evidence keeps `ready.json` false. The
`READY-FOR-DEVICE.json` marker means CPU preparation and the unqueued smoke
proposal are sealed; it does not bypass chain readiness.

All 184 packet137 symlinks are retained, including the packet49 oracle link.
The root native files are copied research sources; the reused executable's
actual bracket source files are bound under packet137 `v5/native-src` and
`v5/native`. The frozen CPU proofs are explicitly reused, including the legacy
K2 proof that cannot be reallocated under the 4-GiB CPU cap.

Use only the entry points documented in orchestration. Inherited preparation
scripts and copied v5 sources preserve history; they are not new launch or
rebuild instructions. [Retention and restoration](RETENTION.md),
[CPU closeout](CPU-PREPARATION-CLOSEOUT.md).
