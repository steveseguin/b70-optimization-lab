# Qwen3.8 AutoRound INT4 TP2 all-reduce device-sync R5 preregistration

Date: 2026-08-30

Status: **preregistered before either R5 model request**

R4 stopped during fail-closed image-file preflight. Direct verification passed
19/19, but no server started, no model loaded, and no request was sent. The
expected and actual communicator hashes were identical; only their manifest
line order differed after the checker was parameterized.

R5 repeats the exact R4 question, treatment, image, suite, order, and decision
rule under new cache/evidence roots. The sole harness correction emits the
image-side hashes in the same deterministic order as the expected manifest.

Run fresh compiled `sync-A` and `sync-B` arms on local B70 GPUs 0 and 1. A
causal positive still requires every arm-level integrity/workload/canary gate
and **12/12 complete token-array equality** between the arms. Speed remains
diagnostic and non-promotable; MTP remains unauthorized.

Frozen identities:

- image ID `sha256:aa212832d5ba6d88d2fa47d1ce9b08ce3862e90bbd4aa57156d6eaafef14f1d2`;
- communicator SHA-256
  `c9a356a5a11006206ae83da9c09fd6cee86e9cd6f65e8d8d877bfe08d0762373`;
- only treatment: `torch.xpu.synchronize()` immediately after collective
  `Work.wait()`.
