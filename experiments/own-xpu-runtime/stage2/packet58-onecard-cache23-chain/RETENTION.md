# Retention

- **Tracked (committable):** every Python/JSON/Markdown source at the top level, `selections/`, `frozen-inputs/`
  (text headers and `rope.bf16`, 4,194,304 B, sha256 `92a8f392…`, the inherited rotary table), `host-admission/`,
  `native/` (the parent harness entry snapshot; the bound engine's own source delta is packet58-onecard-cache23's
  `native-cache23-delta.patch`, pinned by provenance in `engine-binding.json`), `lineage/` (parent receipts, the inherited
  packet58aj README/DO-NOT-REPEAT), `screen-reader/`, `evidence/*.json` receipts (inherited parent gates byte for byte,
  the generator's chain-flags/pin-relocation receipts, the cache23 delta log, every cpu_gates receipt, final checks, the
  retired derivation READY, the two parent test fixtures), `engine-binding.json`, `restore-inputs.json`,
  `build-receipt.json`, `submission-pins.json`, `ready.json`, `derived-chain.json`, `WINDOW.md`, `READY-FOR-DEVICE.json`.
- **Ignored, host-local, restorable:** `build/` (49 MB: `device/own-rt-iq3` `083e3853…` and `gnu-host/own-rt-iq3`
  `03a2aa12…` are byte copies of `packet58-onecard-cache23/build`; `device/p58-cache-fixtures` `ba49aa81…` of packet58ag/
  182c). `restore_build.py` restores all three from `restore-inputs.json` (digest-verified) and the inherited objects;
  **never run `build_engine.py` here** (no compile belongs to this packet).
- **Ignored device streams (future chain):** `evidence/card0-cache23-a/*/run/`, `*/native-home/`, `*/*.jsonl` stay
  host-local but ignored (never untracked-and-unignored); `summary.json`, `window.json`, `queue.json` and `*.log` of every
  window are committable and must be committed right after the window. The fault-review capture
  `evidence/fault-review-cache23-a.json` + `.kernel.jsonl.gz` is committable (as in packet182c).
- **Read in place, never copied:** packet58-onecard-cache23's screen evidence (330 files, `evidence/admission-gate.json`
  provenance records), its build binaries, native delta and receipts (`engine-binding.json`), packet182c-chain's real chain
  evidence (the generator's post-native rehearsal, `ops/packet58c23chain-orchestration/postnative-rehearsal.json`) and its
  submission bundle (refused by this validator, `evidence/submission-rehearsal-cache23.json`), packet58ad's prepared
  evidence (the rehearsal replay), the packet49 oracle, the live record ledger (snapshot `record-threshold.snapshot`).
- **Orchestration** `ops/packet58c23chain-orchestration/`: tools, generator copy, receipts, `entry-proposal.jsonl`
  (entry-check descriptor; never queue it), `launch_chain.sh`, READY/ready copies. Pinned into the packet READY by
  provenance records (the `ops/packet58-*` glob is deliberately not matched; see DO-NOT-REPEAT).
- **Submission outputs (future):** `submission/prepared-a/` (evidence bundle, result, attestation, payload queue,
  result-packet, local dry run) committable after a finished chain; receipts in `data/localmaxxing-responses/`.
- **Not a public release:** research packet; see README "Not claimed".
