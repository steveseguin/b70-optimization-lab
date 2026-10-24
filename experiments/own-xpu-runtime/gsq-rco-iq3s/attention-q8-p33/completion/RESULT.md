# Remaining five prompt pairs: exact correctness complete

The separately admitted October 24 completion session passed all ten arms for
original prompt indices 7–11. Independent readback verified 27,816 artifacts /
3,057,323,570 bytes. Every output token and full target-state byte matches its
corresponding original baseline. Target-only and MTP also agree within each pair.
All ten arms reached the declared 128-token cap; no cases were dropped.

Together with the independently verified fourteen earlier arms for indices 0–6,
the same candidate binary has exact coverage of all twelve original prompt pairs.
This is a disjoint correctness join across two sessions. The original session
remains interrupted by storage exhaustion, without clean native success receipts.
Its timings are not joined with the completion as one resident benchmark.

Two disjoint excluded warmups preceded the ten arms, with full RESET before all
twelve requests. Weights, quantization, context4096, full BF16 KV, full draft
vocabulary and target verification remain unchanged. The candidate changes only
48 Q8 attention projections to existing p33 variant6/split1. Actual allocation
matches forecast:30,763,989,898 bytes on rank0 and29,719,637,908 on rank1.

The completion took273.099 seconds including loading, execution and teardown.
Ranks3595998/3596006 returned0 with zero live allocations/in-flight work; no
signals or retained owners. Passive records establish physical drain, unchanged
vision ownership and no new GPU faults. USB has about8.12GB free afterward.

The separate five-case descriptive decode rates are13.8737 target-only and
19.8980 MTP tokens/s, each across635 intervals. These subset/session rates are
not an all-corpus speed result or a causal comparison to the original baseline.
The [same-owner micro](../micro/RESULT.md) supplies the focused kernel-latency
comparison; it likewise does not establish full-model throughput improvement.

- [Independent raw audit and correctness join](evidence/device-a/review.json),
  SHA256 `068fe237589673cc7ef9545b5bcfbf65d1a51cfe9e8351a727b925bb9f6bd245`.
- [Earlier fourteen-arm audit](../operating/evidence/partial-independent-a/review.json).
- [Exact admitted plan](evidence/operating-plan.json) and [terminal](evidence/closed-terminal.json).
- Raw completion evidence: `/mnt/usb-models/own-xpu-runtime-results/gsq-attention-p33-completion-a`.
- Control evidence: `/home/steve/own-xpu-runtime-results/gsq-attention-p33-completion-a.control`.

The compressed artifact index is needed to reproduce every raw-file comparison
and to authorize any later verified archival. Retain it with the raw artifacts;
it contains hashes/metadata, not weight or state payloads. No raw candidate
artifacts were removed during this run or audit.

This supports retaining the attention change as an exact internal optimization
for these registered cases. Broad task quality, long-context behavior and the
full public performance gate remain separate work. Next is a narrow exact Q6
GDN-QKV micro, with storage record capacity restored before another full suite.
