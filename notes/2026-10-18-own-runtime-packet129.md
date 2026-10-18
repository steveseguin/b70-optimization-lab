# Packet129 — acceptance-first faithful draft experts

CPU-only preparation began at 13:06 UTC, with a 2.5-hour limit. Pull refused
unrelated dirty files; fetch confirmed main and origin/main at
`2165ebe90119526861fd4bcca760639ac683374d`. Existing packet trees, screen,
orchestration and live queues remain frozen. Root starts with about 31 GB
available; stop below 25 GB. Builds stay below 300 MB, with packet94's serial
compiler turn, nice19, CPUs 8–15/24–31, closed job stdin and 8 GiB CPU limits.

The new tree copies packet124c while preserving symlinks. Production still
uses bundle7, the unchanged `iq3-p49-split32-v1` target, BF16 KV, full target
verification and the independently selected 80,128-row draft prefix.

Source inspection confirms that all 512 routed draft experts' gate/up/down
FP8 tensors are converted to symmetric INT8 with FP32 scales per 16 values.
Draft attention, shared experts and HC projections retain publisher BF16.
Norm gains are widened and adjusted by the existing convention. The production
head shares the target's expanded Q6_K head; it is not publisher BF16.

The preregistered candidate retains publisher FP8 values and BF16 block scales,
decoding their product to FP32 before the unchanged lane reduction. For this
acceptance-only test, only ten selected experts are staged at a time. The
production draft supplies every actual proposal. The candidate replays the
expert-to-head suffix on the same inputs; production mutable state is restored
before its proposal is published. No diagnostic timing is a speed claim.

The independent set uses the first and last 128 tokens of each of packet114's
five original pinned general documents, with 128 generated target tokens per
request. The full twelve-prompt suite is secondary only. Keep the candidate
only at an independent acceptance gain of at least 1.5 percentage points;
otherwise close it. No prefix or corpus tuning from suite outcomes is allowed.

The coordinator owns the eventual lane-B load. This session launches no GPU,
service or native device process and changes no host settings. Candidate
adoption, full new-format KD gates and a timing bracket remain conditional on
the actual independent acceptance result.
