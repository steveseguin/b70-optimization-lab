# Packet129 CPU preparation closeout

Question: does removing the draft experts' INT8 requantization raise acceptance
by at least 1.5 points on independent text? Identity: packet124c bundle7 target,
unchanged `iq3-p49-split32-v1`, 24/24, rank1 draft, BF16 KV, prefix 80,128.

CPU implementation and arithmetic gates pass; device acceptance remains pending.
The useful mechanism is exact FP8 staging of selected experts, with a shadow
suffix and checked restoration of all production draft mutable state. It keeps
the production proposer and target unchanged while avoiding a second full bank.

The native diagnostic is compiled. GNU/Intel routed FP8 bytes agree twice per
compiler; miniature target/proposal/state comparisons and reset tests pass.
Both real-shape rank memory censuses pass. Final argument/queue readiness is
recorded in `evidence/final-check.json` when complete, not inferred from this note.

Preparation fixes: the first native parser replay lacked `OMP_NUM_THREADS=2`;
the CPU wrapper supplies it. The corpus cap was clarified before any device
result to respect natural EOS and require 512 independent verified proposals.
No prompt, token window, candidate or acceptance threshold was selected from
benchmark results. All ten independent requests and all twelve secondary suite
requests remain mandatory.

Retain source, preregistration, corpus, compiler commands, CPU receipts and the
new proposed queue file. Existing packet/ops/screen trees and live queues were
not edited. No GPU, service, sudo or host-setting action occurred.

Revisit: only the coordinator's complete paired diagnostic can pass or close
the candidate. At a pass, build and gate the resident format and its v5 bracket;
at a failure, retain the evidence and close this candidate without tuning it on
the suite. No speed or quality promotion follows from CPU checks alone.

The final worker rehearsal covers all 22 requests and a corrupted-production
negative control, with native execution forbidden and synthetic data discarded.
Runtime imports preserve all inherited limits; the exec guard rejects the old
finite CPU cap. The real temporary queue plan passes. All CPU preparation gates
are complete; actual device acceptance remains pending.
