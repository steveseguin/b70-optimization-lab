# Packet160 critical-path mechanism study — closeout

<!-- campaign-closeout -->

## Question and identity

Can a dependency change shorten B → draft → next-A enough for ≥3% over
packet136's 58.798108759 tok/s? CPU study, October19, 2026, two B70,
24/24 layers, fixed80,128 draft prefix, BF16 state/KV, unchanged
`iq3-p49-split32-v1`. Record first99 intervals/prompt and separately labeled
packet150/154 scopes and packet122/158 historical operator diagnostics.

## Outcome

No new build admitted. Head-only designs are too small; advancing only A has
zero record-model benefit; perfect equal-cost B-to-A balancing gives1.889%.
Perfect all-draft halving leaves only62.44µs for the entire new protocol to
reach3%, unsupported by the available transport evidence. No measured speed,
quality promotion, proposal or READY marker was created. The lane stays open.

## What worked

The [record replay](evidence/report.json) exactly reconstructs1,188 intervals
and the class-balanced headline. The [scope replay](evidence/scope-report.json)
joins3,780 real intervals to both host streams, verifies original output and
draft sequences, and preserves exclusive clock accounting. The direct p149
correction delta is a better input than dividing its throughput change by a
miss fraction. Eighteen tests cover actual parents and corrupted copies.

## What failed or remains uncertain

No known early signal has measured lead/accuracy/B exposure. A new small
exchange has not been measured;80µs is amortized historical pricing. Rank0
concurrent expert service is unmeasured and must not be declared free.
P106b's measured loss does not identify one isolated transport culprit.
Historical draft kernel sums are not tonight's per-interval device timings.
The first scope join included out-of-window termination waits; it refused.
Restricting decode command joins to the actual measured window fixes that
scope error, retaining the complete original streams and all decode intervals.

## Evidence and patches

[Plan and exclusions](PLAN.md), [record CSV](evidence/record-intervals.csv),
[exclusive scope CSV](evidence/scoped-intervals.csv.gz),
[negative-result audit](evidence/prior-audit.json),
[real-parent tests](test_analyze.py). Only new CPU analysis sources were written.
Reproduce with the three commands in PLAN.md. Existing p136/p156 archived
inputs remain hash-bound dependencies; the otherwise untracked149 summary is
retained here compressed with original byte hashes. No old evidence removed.

## When to revisit

A new concrete schedule with net measured exposure supporting0.628451 ms/hit
or0.495744 ms/interval, including busy-peer compute, transport and recovery;
or an exact early-target-winner certificate with useful measured occurrence.
No small-message latency inferred from byte scaling, no cheap-sibling assumption,
no learned/cache-based proposal. Follow both-lane smoke/bracket, fresh-process,
exactness,25GB device/27GB CPU, freeze-safe proof and READY-last contract in PLAN.
