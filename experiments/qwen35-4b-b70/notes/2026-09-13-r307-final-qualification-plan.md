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
