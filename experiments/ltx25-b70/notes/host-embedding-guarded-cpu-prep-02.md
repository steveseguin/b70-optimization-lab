# Host embedding candidate: guarded CPU preparation v2

2026-09-14. The original prep01 source snapshot and unguarded v1 fixture remain
preserved. No Torch import, native CPU test, accelerator request, or live edit
occurred in this preparation. Root schedules native CPU work separately.

Review found two concrete problems before execution. A bare Embedding as the
host ModelPatcher root makes the generic loader form an invalid `.weight` key;
the CPU owner now contains a named `embedding` child. Also, real Comfy nodes
construct models under inference mode, where parameters may lack a version
counter. The candidate preserves those original tensors, records version
tracking as unavailable, and checks owner/storage/dtype/device identity. Normal
tensors retain version checks. Inference-tensor in-place mutation is not claimed
to be detected: qualification assumes pinned immutable loaded weights and
rejects supported patch/hook paths. No full-table copy creates artificial counters.
Failed installation restores the original module registration and size cache.

The six-group successor fixture exercises actual pinned ScaledEmbedding,
Embedding ops, ModelPatcher and extracted SDClipModel.process_tokens. It now
loads the named CPU host through its actual patcher, checks clone/detach/restore,
preserves inference-created table identity, tests install rollback, and rejects
ordinary tensor mutation/unsupported state. Embedding and restored state checks
compare actual raw bytes as well as tensor equality, dtype and strides; signed
zero is included. These are prepared tests, not executed results.

`scripts/test-host-embedding-candidate-cpu-v2.py` writes exclusive startup
PID/source receipts before Torch import. It then installs the frozen v2
accelerator-entry traps and frozen v3 CPU availability policy before native
Comfy imports. Every `torch.utils._triton.triton_backend` and `torch.compile`
call is refused with a sticky BaseException. The original backend is never
called; this driver permits no compilation. Guard identities are checked after
imports, before/after each test and at exit. The first test failure stops the
suite. Final receipts record XPU/CUDA initialized flags and guard integrity;
a final guard failure also forces a nonzero exit status.

The reused frozen availability-policy description mentions compiled arms.
The wrapper explicitly records that those arms do not apply to this fixture.
Its policy is process-local, with no installed-file, host-power, cache or swap
setting change. This is a Python entry guard, not an operating-system sandbox.

Five stdlib tests passed for actual source pins, startup ordering, unconditional
backend refusals, sticky failure, identity tampering and stopping after the first
test failure. The wrapper's `--check-only` also passed without Torch. Original
exclusive source-check evidence is at
`/mnt/fast-ai/bench-results/ltx25-baseline-20260913/host-embedding-cpu-v2-source-01`;
startup/result copies and the structured stdlib receipt are under `data/`.

Final prepared hashes:

- Candidate: `b58bf0bbfc084ea89f2673f3c10d9520b5f6ac1993517c79e346ea2c573ca7e9`
- Actual CPU fixture v2: `b1295210e04c20069bded9972bdbb29ee65589410c57dc81a410956ae7e63a32`
- Guarded driver v2: `9d8053868a7a26c6dd36ff0ae1889278effee866e93cf7e931546d06a8493bd3`
- Stdlib test: `9faa37e8038c6ed955777f6ef2082cf484e7e80cdc9382bf42b78440f4df91de`

All four sources are snapshotted in `patches/host-embedding-candidate-prep-02.patch`.
The first stdlib log is retained before the final fixture-byte-comparison pin;
`data/host-embedding-cpu-v2-stdlib-02.json` binds the final passing preparation.

This remains an ownership prototype, not deployment integration. Future work
must install before CLIP's constructor-time load, expose/load both patchers
explicitly, refuse active serialization/checkpoint reload or restore first,
and bind complete residency/unload evidence. Adding `additional_models` alone
does not make this pinned CLIP loader traverse the CPU owner. A CPU proof cannot
qualify actual XPU row transfer, final conditioning, clip parity or speed.
