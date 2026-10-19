# Packet153 — static speculative snapshot descriptors

Started about 00:18 UTC on steve-b70s. The requested work is CPU preparation of
a two-card lane-B experiment, not a launch. Pull refused unrelated dirty work;
fetch confirmed HEAD and origin/main at 3db45a0bd41f623bd70b09a0c3e70bfefea50fa2.
Root began at 31.44 GB free. Existing packets, queue files and orchestration
edits remain untouched. frozen_paths.py was run; its entire union is protected.

The first repository-wide search covered every DO-NOT-REPEAT.md and notes
folder for snapshot, descriptor and rotation work. Relevant exclusions:
[packet131](../experiments/own-xpu-runtime/stage2/packet131-snapshot-banks/DO-NOT-REPEAT.md),
[packet62](../experiments/own-xpu-runtime/stage2/packet62-miss-path/DO-NOT-REPEAT.md),
[packet121](../experiments/own-xpu-runtime/stage2/packet121-miss-table/DO-NOT-REPEAT.md),
[packet144](../experiments/own-xpu-runtime/stage2/packet144-miss-path/DO-NOT-REPEAT.md),
and [packet150](../experiments/own-xpu-runtime/stage2/packet150-rank0-split/DO-NOT-REPEAT.md).
No extra bank rotation, lost old-spare state, skipped QSA copies, diagnostic
speed promotion or miss-only overlap estimate is being reused.

[Packet153](../experiments/own-xpu-runtime/stage2/packet153-snapshot-host/README.md)
starts with a symlink-preserving packet136 copy. Packet150 supplies a vendored
one-load harness and the same timing scopes, with all replay modes disabled.
The new static path builds one table at load. Its nonbank sources are invariant
across all six bank pairs; QSA offsets use the captured position in the kernel.
Capture and restore both avoid the descriptor build and upload. Required copy
traffic, kernel search, host metadata and synchronization remain.

The CPU audit identified and fixed immutable-table reset handling and the
protected-active negative test. The smoke analyzer now validates the real
embedded native-trace schema and rejects missing streams/scopes. Compiler turns
wait behind the active record chain's whole-host hold. No device or service
was started; no model payload/full-shape read or privileged operation occurred.

Initial source milestone: implementation and CPU test sources prepared;
qualification and final readiness are still pending. No proposal is queued.
