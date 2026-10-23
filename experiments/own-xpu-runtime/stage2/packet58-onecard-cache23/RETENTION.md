# Retention

- **Tracked (committable):** every Python/JSON/Markdown/C++ source, `native/` (including the generated
  entry snapshot and `native-cache23-delta.patch`), `frozen-inputs/` text headers (path-rewritten tracked
  copies) and `rope.bf16` (4,194,304 B, sha256 `92a8f392…`), `selections/`, `host-admission/`, `lineage/`
  (copy record, path rewrite, harness delta, pre-delta native snapshot, parent receipts), `memory-plan.json`,
  `admission.json`, `evidence/*.json` and `screen/evidence/*.json` receipts, `screen/proposals/`,
  `screen/build-receipt.json`, `READY-FOR-DEVICE.json`.
- **Ignored, host-local, restorable:** `build/` (81 MB: the rebuilt engine `083e3853…`, host parser binary,
  preparation probe, K1 wrapper, objects). The 79 unchanged parent objects/binaries are restored by
  `restore_build.py` from `restore-inputs.json` (packet58aj kernel/host objects, packet182's
  `single_device.o` and K1 host fixture, digest-verified); the rest is rebuilt by `build_cache23.py`
  (`evidence/build.json` records every command). `*.o` payloads are never tracked.
- **Ignored device streams (future):** `screen/evidence/card0-58c23-v5-a/resident/*/run/`, `native-home/`,
  `*.jsonl` stay host-local but ignored (never untracked-and-unignored); `summary.json`, `window.json`,
  `queue.json` and `*.log` of every window are committable and must be committed right after the window.
- **Read in place, never copied:** packet182c's chain receipts (`memory-plan.json` names each file and
  digest), packet182's v5 bracket and the oracle (`analyzer-real-parent.json` provenance records);
  `plan.entry_rehearsal.timing_evidence` points at packet182's host-local `cold-start.json`.
- **Not a public release:** research packet; see README "Not claimed".
