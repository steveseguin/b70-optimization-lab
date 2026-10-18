# Packet113 CPU preparation — closeout

<!-- campaign-closeout -->

## Question and identity

Can a single subgroup own an entire GDN value row, remove shared preparation
barriers, and cut recurrence event time by 40% without changing any state or
output byte? Packet103/97 `rec-both-plus`, `iq3-p49-split32-v1`, copied packet110
complete synthetic layer, GNU/Intel 2026 builds; lane-B device work is proposed.

## Outcome

CPU preparation passes; device verdict is pending. Two processes per compiler
pass 572 complete-layer comparisons plus 768 recurrence cases each. Device
compilation and two temporary queue plans pass. This closes preparation only,
not the experimental arm or optimization lane. No runtime integration qualifies.

## What worked

The independent-row partition removes workgroup shared memory and barriers
without splitting a reduction or carrying FP32 state between tokens. Both
compilers preserve their production NaN/Inf bytes, including the packet107
failure family. Native micro admission includes these same exceptional cases,
full mutable-state comparisons and alternating pair order.

## What failed or remains uncertain

No device ran. More workgroups is not proof of better occupancy; per-row
normalization duplicates work and may lose. The useful-byte roofline is not a
hardware memory-traffic measurement. The historical vLLM M=2 memory note is not
this runtime's timing evidence. The native full layer measures M=1; M=2/4 are
byte tests, not performance points. One test initially omitted a temporary
output directory; its fixture was corrected, then all policy checks passed.

Initial CPU aggregation could reuse old unbound output directories. Final
validation uses fresh directories and records the binary/build hashes before
each launch; seals check those bindings. Earlier successful transcripts remain.

## Evidence and patches

- [Candidate kernel](p113_recurrence.hpp) and [copied layer harness](layer_bench.cpp).
- [Compiler exceptional checks](evidence/cpu-leaf.json).
- [Complete-layer CPU checks](evidence/cpu-layers.json).
- [Device build and immutable inputs](evidence/build-device.json).
- [Temporary queue plans](evidence/queue-plans-final.json).
- [Gate](qualification.py), [seal](seal.json), [retention](RETENTION.md).
- [Work note](../../../../notes/2026-10-18-own-runtime-packet113.md).

## When to revisit

The coordinator may run both proposed lane-B micro jobs. Require <=0.6 of
production recurrence time in both fresh processes, both contexts and both
orders, with every state byte exact. Otherwise close the candidate. Only a
qualifying result permits integration into a copy of committed packet111,
followed by GNU/Intel bytes, the exact selected startup/reference views, seals
and a v5 one-load native bracket. Keep the record runtime unchanged meanwhile.
