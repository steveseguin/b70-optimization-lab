# Packet 49b: packet 49 plus exact expert GEMV kernels

Separate candidate derived from sealed packet49 at `5cda094d2`; predecessor
source, evidence and running oracle are unchanged. Build and CPU qualification
are recorded in [the task note](../../../../notes/2026-10-17-own-runtime-packet49b.md).
No device result or speed claim exists for this integration yet.

The engine uses packet48b's order-preserving IQ2_S expert gate/up and IQ4_NL
expert down kernels. Both ordinary decode and each M=2 verification row use
them wherever the existing P39 engine path calls those formats. The exceptional
IQ3_S gate stays unchanged. GDN QKV/Z stay unchanged: packet48b's matched
production experiment covers M=1, not M=2, and its M=1 dense screen was not
worthwhile. See [integration and layout evidence](INTEGRATION.md).

Packet48b's 16-byte final row padding would exceed the existing 30 GiB arena
limit. Packet49b preserves its plane offsets and arithmetic, using 4-byte row
strides of 820 bytes for IQ2_S gate and 360 bytes for IQ4_NL down. Those strides
satisfy every actual weight load and keep bank sizes unchanged. This layout
adjustment needs fresh device gates; packet48b speed is not a packet49b result.

Arithmetic remains `iq3-p49-split32-v1`: split32 QSA, BF16 KV, unchanged weights,
23/25 target split, draft rank1, capacity4096, snapshot and memory limits.
[The oracle binding](oracle-binding.json) pins the existing packet49 oracle.
The `oracle` symlink is read-only reuse, not a new job. Model windows validate
its completion and bind the completion, manifest, determinism and KD hashes.

- [Coordinator runbook](WINDOW.md): early and model phases, same new chain.
- [CPU build and gate commands](CPU-BUILD.md).
- [Storage budget and retention](ARTIFACT-RETENTION.md).
- [Independent review](REVIEW-INDEPENDENT.md).
- [CPU preparation closeout](CPU-PREPARATION-CLOSEOUT.md).

The inherited packet45/49 helper scripts are implementation history, not
additional approved entry points. Use the build, seal, queue and shared-oracle
entry points linked above. Historical copied reviews are explicitly labeled.
The final WS128 is the matching 128-token record comparison. Its primary rate
is the median of class medians for 99/(t100-t1), with the all-prompt median
reported separately. It does not satisfy the separate 512-token publication
gate or authorize a submission without exactness and promotion evidence.
