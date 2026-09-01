# Qwen3.8 repaired TP2/MTP1 D62 post-reboot startup failure

Date: 2026-08-31

D62 reproduced D61's device-loss class after a full host reboot. Before the
model launch, both B70s reported normal device and firmware state, and each
passed an independent deterministic matrix-compute oracle. The local model
also passed direct-I/O and ordinary SHA verification for all 19 files.

The target and MTP1 drafter loaded on both ranks. During vLLM's bounded
256-token profile run, TP rank 1 raised `UR_RESULT_ERROR_DEVICE_LOST` at the
first synchronization inside the deterministic dense-MLP wrapper. That
synchronization occurs at MLP entry, before the wrapper submits its own
gate/up, activation, padding, or down-projection work. It therefore exposes a
failure from an earlier asynchronous model operation; it does not establish
that `torch.xpu.synchronize()` or the dense down-projection caused the fault.
The instrumented dummy sampler was never reached.

At the same timestamp, Xe recorded on `0000:e3:00.0`:

- 594 unsuccessful fault responses;
- 27 CCS engine-memory CAT errors for GuC ID 20;
- one CCS engine reset for the same GuC ID.

No HTTP request was served. The wrapper was stopped after the dead engine had
preserved its logs, so exit 130 is cleanup provenance rather than the fault's
cause. No decode, TTFT, acceptance, output, quality, or determinism value may
be inferred. After container removal, both B70s again reported normal and
passed the same independent compute oracle; unlike D61, this attempt did not
leave the card wedged.

The next permitted arm is the preregistered startup-only D63 A/B with the
projection repair disabled and every other TP2/MTP1/profile/stage-sync identity
held fixed. Do not run a performance suite until startup is clean and the
device-loss mechanism is removed.

Raw evidence remains under
`/mnt/fast-ai/bench-results/qwen38-prefill-projection-repair-tp2-mtp1-sync-20260831-d62/`.
The retained hashes and classification are in the adjacent structured result.
