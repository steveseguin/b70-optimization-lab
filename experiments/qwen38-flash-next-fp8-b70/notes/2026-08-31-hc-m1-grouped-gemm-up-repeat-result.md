# Qwen3.8 Flash-Next FP8 HC grouped-GEMM up-repeat result

Date: 2026-08-31
Status: frozen replication gate failed on control drift

All four new brackets retained exact output and showed large grouped-kernel
reductions: 69.25% and 66.13% at layer 0, and 70.10% and 62.76% at layer 47.
The first repeat passed the complete gate for both layers. The second repeat's
candidate remained much faster, but its two controls drifted 5.26% and 7.04%,
above the frozen 3% cap.

The preregistered family gate therefore fails. This result does not authorize
the 48-layer screen, integration, or an endpoint claim. The evidence instead
shows that fresh-process control drift—not output parity or the direction of
the candidate effect—is the unresolved discriminator. A separately frozen
same-process alternating control/candidate test is the appropriate next step.

The host remained healthy with about 120 GiB available and swap unused. No
server, full model load, reboot, or protected result changed. Exact metrics and
pair-file hashes are in the
[structured result](../data/20260831-hc-m1-grouped-gemm-up-repeat-result.json).
