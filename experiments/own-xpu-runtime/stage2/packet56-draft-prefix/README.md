# Packet 56: draft vocabulary prefix

This separate packet uses packet49d's unchanged target and the same packet49
CPU oracle (`iq3-p49-split32-v1`). Only the MTP proposal head changes: it reads
the first **91,392 of 248,320 rows** of the existing shared expanded Q6 head.
The target still verifies against its complete head. Target arithmetic,
controller, rollback, 23/25 split, draft rank 1, 4K capacity and BF16 KV stay
unchanged. No second head allocation or weight copy is introduced.

The [preregistered rule](calibration/preregistration.json) was committed before
tokenization: choose the smallest multiple of 256 rows covering at least
99.5% of tokens in five complete, fixed local operations/design documents and
storage code. No benchmark prompts or answers selected the prefix.
[Calibration](calibration/selection.json) covers **19,382/19,477 tokens,
99.512245%**. The previous prefix, 91,136, covers 99.491708% and fails the rule.
The outside fraction is **95/19,477 = 0.487755%**. This is text frequency, not
measured generated-target frequency or draft acceptance.

[Retained timing analysis](analysis/README.md) measures D at 2.775889 ms and
finds a matched head-plus-argmax proxy of 1.438645 ms (51.83%). There is no
retained direct draft-layer/head profile. Linear head scaling projects about
0.896 ms off D, about 3% total improvement under explicit acceptance
assumptions. These are planning estimates, not speed results.

- [Coordinator windows](WINDOW.md): two fresh head microtests, then the same
  early and model chain as packet49d, against the unchanged packet49 oracle.
- [CPU preparation](CPU-BUILD.md): serial, low-priority builds and synthetic
  byte/controller checks; no model loads or device execution.
- [Offline submission tooling](SUBMISSION.md): packet56 lineage and current
  pinned submitted-record floor, with no modification of the running 49d seal.
- [CPU preparation closeout](CPU-PREPARATION-CLOSEOUT.md),
  [independent runtime review](REVIEW-INDEPENDENT.md),
  [independent submission review](REVIEW-SUBMISSION.md) and
  [task note](../../../../notes/2026-10-17-own-runtime-packet56.md).

The existing 128-token owner scope remains explicit; the strict 512-token
promotion gate is false. Full-model equality, actual acceptance and speed
remain unmeasured until the coordinator completes the device chain. The
protected 49d unit, tree and shared submission helper are untouched.

The parent source manifest and seal retain the exact base identity. Copied
historical helpers are implementation history, not alternative runbooks.
Use only the entry points linked above. The standalone prefix overlay can be
applied to a separate 49c copy if 49d fails; never patch either sealed parent.
