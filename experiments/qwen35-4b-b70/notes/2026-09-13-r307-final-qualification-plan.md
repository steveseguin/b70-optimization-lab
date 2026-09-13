# R307 final qualification plan

Authorized by the user on 2026-09-13: finish the fault investigation, failure
propagation corrections, non-debug token-ID boundary repeats, isolated 9B
qualification, and conditional narrow promotion.

## Fault finding

The old 9B attempt aborted at 16:18:18 because the journal included
`Xe device coredump has been deleted.` at 16:17:41. Its saved postflight journal
contains no new fault, reset, or coredump creation. This is an expired earlier
dump, not evidence that this 9B run faulted. Preserve the failed attempt;
exclude only that deletion message from future matching. A fresh bounded
single-device test on both cards and two-rank XCCL passed at 17:28 EDT.

## Registered campaign

Runner: `../scripts/run-20260913-r307-qualification.py`.
Candidate is immutable local image
`sha256:9be49c62baabf4611ecf08419d836a2e2f171adba5d2a28509b6fd796e7d28c3`;
this validates the existing R307 candidate rather than starting a new upstream
optimization search. One server at a time, card 0, no competing GPU workload.

For each of the 4B and 9B W4A16 models, run a same-image target-only boundary
oracle and two fresh depth-3 servers with separate caches. Max model length
256, max sequences 4, fixed-depth FULL_DECODE_ONLY recipe, cache off. Probe
uses integer token-ID prompts and completion IDs. Cover prompt lengths 8–27,
sequential and four-request concurrency, repeated outputs, and short oracle
prefix tails that reach the model-length boundary. Reject errors, incomplete
outputs, missing IDs, wrong prefix lengths, and oracle mismatches. Do not count
skipped cases as requests.

Then run the isolated 9B strict campaign: two fresh target-only servers and
two fresh MTP3 servers, all full 12-prompt suites, natural completion cap 512,
cache-zero checks and canaries. Require G1/G2/G3 12/12. Existing 4B strict
pairs, 4B real-content depth, and short-prompt results are supporting evidence;
retain exact runtime/config identities.

New faults abort the chain. Every stage must propagate failures, stop its
owned server, and record health postflight. DONE means all mandatory stages
passed, never merely that the wrapper reached its last line. Existing roots
are never overwritten. Capture candidate contract without bypass before
promotion; a bypassed experiment cannot establish recipe-contract closure.

## Decision boundary

Only fixed-depth TP1 4B/9B boundary behavior is a promotion candidate. Preserve
TP2, dynamic-depth R306, and 27B recipes. c64 speculative identity is already
known to fail and is not part of this fix; no universal concurrency-exact
claim. Do not publish a new speed record from these diagnostic boundary tests.
If exact boundary or strict gates fail, preserve the negative evidence and
resolve the concrete cause before promotion. Public image/source closure,
recipe checks, documentation integrity, and deployment verification remain
required if the candidate is promoted.

## Failed expanded gate and narrower follow-up, 17:40 EDT

The first campaign is **failed**, not qualified: 4B target-only passed 100/100;
first MTP3 passed c1 full40/40 and tails12/12, but c4 full33/40 (tails12/12).
First differences occur at output indices36,153,164,193,197, before the final
boundary step. This does not establish the numerical cause, and no c4
oracle-exact claim may be promoted. The runner stopped and failure postflight
passed. Original evidence remains in its original root.

The follow-up is explicitly restricted to one active request (`max_num_seqs=1`,
`--concurrency 1`), root `r307-single-request-qualification-20260913`. It runs
the same complete L8–27 and L14-tail fixture on both models, same-image oracle,
two fresh MTP3 servers, then the unchanged isolated 9B strict pairs. No failing
case is removed from the c1 fixture. Only a **single-request profile** may be
promoted if these gates pass; multi-request serving remains outside that
qualification. The original c1/c4 gate remains failed permanently.

## 9B single-request blocker and acceptance diagnostic, 18:02 EDT

The single-request follow-up also **failed**: 4B60/60 oracle and52/52 on both
fresh MTP3 servers pass. 9B oracle60/60 passes; first9B MTP3 has repeated final
output-token differences at L13/14/16/17 and L14-tail238. No9B strict pair was
started after this failure, and no R307 profile has been promoted.

The next bounded diagnostic compares the exact same L14/L16 and tail238
integer prefixes on target-only R307, then an instrumented R307 depth3 image.
The target-only tail control distinguishes changed prefill arithmetic from a
speculative transition defect. Instrumentation records CPU valid sampled
counts and the GPU acceptance counts actually used for the GDN handoff.
Source shows these travel through different paths: GPU counts default1 and
are corrected only when previous draft bookkeeping is present. Any mismatch
must be observed before calling that the cause. Diagnostic prints can alter
synchronization; final qualification must use a non-debug image.

### Acceptance diagnostic follow-up

The matched MTP0 control passed all six cases; the logging-only MTP3 image
reproduced all six final-token failures. Final CPU and GPU accepted counts both
read one, with an empty previous-row mapping. This does not demonstrate a
CPU/GPU disagreement. A source audit identified acceptance metadata reset on
batch removal/re-addition as a possible cause, but the first trace did not
observe that lifecycle directly. One additional logging-only 9B server will
capture scheduling flags, removals, additions, and post-execute acceptance at
the same six cases. It uses the prior matched MTP0 control, preserves original
receipts, and is diagnostic only. No functional patch is qualified by these
observations. The same cleanup and GPU fault abort rules apply.
