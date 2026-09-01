# D63 preregistration: TP2/MTP1 startup without projection repair

Date: 2026-08-31

D61 and the post-reboot synchronized D62 arm both lost TP rank 1's Level Zero
device during vLLM's TP2/MTP1 profile run. D62's first failing synchronization
was at entry to a dense MLP, before the dummy sampler and after an earlier
asynchronous model operation. The clean-reboot preflight and independent
per-device compute gates passed; D62 then produced 594 unsuccessful Xe fault
responses and 27 engine-memory CAT errors on `0000:e3:00.0`. Both devices
returned to normal management state and passed independent compute after the
failed container was removed.

D63 changes exactly one runtime mechanism from D62: the M=512 deterministic
projection-repair hook is mounted but disabled. TP2, MTP depth 1, eager mode,
the 256-token profile bound, image identity, model identity, local ext4 model,
stage-by-stage dummy-sampler synchronization, and device mapping remain
unchanged. This is a startup-only localization arm. It serves no benchmark
request and cannot produce or promote a decode, TTFT, acceptance, quality, or
determinism result.

Interpretation is frozen as follows:

- readiness plus exactly two receipts for every instrumented dummy-sampler
  stage, two healthy endpoint checks, clean teardown, and no new kernel fault
  classifies the projection repair as necessary to the D61/D62 startup fault;
- another device loss before readiness classifies the fault as independent of
  the projection repair and uses the last completed synchronization receipt to
  localize the earlier asynchronous operation;
- any identity, source, receipt, cleanup, or health-gate failure leaves the A/B
  inconclusive and authorizes no performance run.

No retry or relaxed stage list is permitted under this preregistration.
