# Qwen3.8-27B Q4_K TP2 WDC HTTP r1 — stopped at control

The r1 HTTP campaign stopped before any WDC candidate server was launched.
The fresh control passed the realistic workload gate across all 12 distinct
prompts with zero cached tokens, but its output hashes did not equal the older
promoted-binary oracle. The class-balanced 99-interval diagnostic was
49.824579 tok/s; it is not promoted by this failed campaign.

The review also found that the HTTP launcher enabled the scoped Q4_K reordered
layout only in its WDC branch, while the preceding raw mechanism screen kept
that layout enabled in both arms. That made the planned HTTP comparison more
than a one-variable A/B. Fail-closed behavior worked: the runner exited 3 at
the first control and did not launch any candidate.

The follow-up first freezes and repeats a corrected, WDC-off current control
oracle. Only after that control is deterministic will a separately
preregistered WDC comparison be allowed to run. The historical oracle remains
unchanged and the failed r1 artifacts remain retained.
