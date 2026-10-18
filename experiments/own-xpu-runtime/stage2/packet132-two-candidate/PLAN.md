# Packet132: CPU-only two-candidate study plan

Recorded before new target or draft outputs, 2026-10-18. This is a bounded
follow-up to packet96, using new independent text and packet128b costs.
No runtime candidate, device job, service or queue entry is authorized here.

## Inputs and resource bound

Use the five exact source documents and source commit frozen by
[packet114](../packet114-draft-prefix/calibration/preregistration.json).
Tokenize each complete original document with its pinned tokenizer. From each,
take 16 consecutive tokens starting at `len(tokens)//2`, without a chat
template, and generate at most 24 greedy target tokens. This mechanical rule
is chosen for the 90-minute CPU budget, not after examining outputs. Keep all
five sources, natural early termination and every observed position; no
replacement or favorable prompt selection. This small excerpt study is not
the complete packet129 corpus or a performance benchmark.

Target: packet49 `iq3-p49-split32-v1` CPU oracle, unchanged arithmetic and
weights, private capture harness only. Draft: packet31 CPU INT8 semantic
reference with IQ3 shared embedding/head, restricting head candidates to the
production 91,392-row prefix. This reference is not certified device-identical;
record that limitation rather than borrowing packet129's parity claim.
Warm every shifted draft context row. Target labels are oracle predictions,
never the next source-text token. Never read benchmark prompts or outputs for
calibration, threshold choice or evaluation.

Run under `nice -n 19 taskset -c 8-15,24-31 python3 -B`, stdin `/dev/null`,
with bounded host-only children, at most 8 GB combined process RAM, no GPU API,
services, sudo or settings. Only one heavy capture/build/draft phase at a time.
Stop launching captures at the fixed deadline; incomplete evidence cannot pass.

## Fixed policies and selection

Compute the top-two logit margin and top-one probability normalized over the
91,392 admitted draft rows. The latter is a **prefix probability**, not a full
248,320-token vocabulary probability. Margin is the primary feature; the
probability sweep is secondary. Equal logits use the lowest token ID.

Flag strictly below tau. Margin grid: 0 to 16 inclusive in steps of 0.125,
then 32 and 64. Probability grid: 0 to 1 inclusive in steps of 0.025, then
1.01. Include never and always. Train on source documents 1–3; hold out 4–5.
Choose feature/threshold on training projected time, breaking ties toward
fewer flags, then fixed feature/grid order. Report all thresholds, counts,
baseline acceptance, top-two rescue among misses, flagged fraction and new
acceptance. Report pooled best as an explicitly in-sample diagnostic, too.

## Cost assumptions and decision

Snapshot the current packet128b BUDGET bytes: its overhead check **fails**,
so its class times support sensitivity calculations only. Never treat them
as qualified whole-engine timing or a sum of disjoint wall-time buckets.

Primary screening scenario deliberately favors the idea: fully exposed extra
rank0 expert-union work plus recurrence, route, activation/combine and QSA
row work; free incremental dense/HC/projection work, state selection and
top-two reduction; 15 ms saved per rescued miss from the brief. Expert union
uses independent uniform top-ten routes among 512, not measured route sharing.
Rank0 has no established spare time (packet120/127). State-bank ownership is
unproved: packet131's third bank is already used for speculation/rollback.

Also show expert-only extreme sharing, the same favorable work charged against
packet128b's restore-plus-redo compute, and duplicated whole-half work with
explicit state/control/top-two allowances. None is measured M=2 latency.

Use the brief's 17.4 ms anchor (57.471264 tok/s):
`T' = 17.4 + f*C - r*B`, where f is flagged fraction and r rescued fraction.
Every cycle emits one verified token; no two-token multiplier. Also report
finite-window accounting: interval i pays flag i+1 and receives rescue i;
never join prompts or invent edge/wraparound positions.

Advance to a design note only if the primary training-selected policy projects
at least +3% on held-out sources, with complete capture. Otherwise close this
session with a local DO-NOT-REPEAT entry. Report the best in-sample projection
and all sensitivities even when they disagree. No implementation either way.
