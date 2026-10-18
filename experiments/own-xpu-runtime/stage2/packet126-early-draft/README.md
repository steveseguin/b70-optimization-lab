# Packet126: guessed-token draft before target verification

**Decision: not admitted; the gain is not identifiable from the retained
timings.** The zero-recovered-wait scenario predicts a 1.95–1.96% loss. An
unmeasured head decomposition consistent with the same traces can predict a
gain above 0.5%. Neither is a measured runtime result. This is inconclusive,
not a proved sub-0.5% lever. [Numbers and reproduction](RESULTS.md),
[closeout](ANALYSIS-CLOSEOUT.md), [boundaries](DO-NOT-REPEAT.md).

CPU dependency study of packet124 bundle8 BASE, whose native source is
packet118 bundle7. No runtime source is changed or executed. Target arithmetic
is `iq3-p49-split32-v1`, BF16 KV, 24/24 layers, rank1 draft, packet114's fixed
80,128 draft rows, and packet105b's unchanged full target head split.

## Exact current dependencies

Use source positions, not ambiguous generation indices: `B[p]` consumes the
target streams from `A[p]`, produces hidden `h[p]`, and verifies token
`t[p+1]`. `D[p+1]` consumes **h[p] plus t[p+1]**, advances the draft cache once,
and guesses `g[p+2]`. The earlier `D[p]` supplied `g[p+1]`. The brief's hidden
state after position p+1 corresponds to `h[p]` under this source convention.

```text
                      prior verified emission t[p]
                                    |
rank1:                   D[p](h[p-1], t[p])
                          |                  |
rank0 hit: accept A[p] ---+                  +--> g[p+1]
rank0 miss: rollback A[p]; corrected A[p]     |
                          |                  |
                 handover A[p]              |
                          |                  |
rank1:                 B-body[p]        rank0: speculative A[p+1]
                          |                           |
                     final norm                       |
                          |                           |
                  export final.mix                    |
                          |                           |
                  enqueue prefix head                 |
                     /           \                    |
          publish hidden         prefix/argmax         |
                     \           |                    |
                      +------ suffix service <--------+
                                |                     
                        suffix best reply             
                                |                     
                       target head merge <--- prefix best
                                |
                verified t[p+1]; emit; accept rank1
                                |
              D[p+1](h[p], verified t[p+1])
                                |
          accept A[p+1] on hit; restore/correct it on miss
```

The drawing's last accept/correction runs concurrently with the next DRAFT.
The rank0 command executes synchronously in `Backend::start`; only after it
finishes does `Backend::wait(1)` call `p105::Runtime::service`. That suffix
service has private scratch and writes no target state. Its work is **outside**
`rank_trace`; rank1 waits for its result **inside** B. Prefix means two
different things here: the target's split-head row partition and the draft's
fixed80,128-row vocabulary restriction. Only the latter affects D.

The packet108 position-join accounting is unchanged:

```text
current hit  = D + max(B_hit, A_next + offset) + G
current miss = max(D, R + C) + max(B_miss, A_next + offset) + G
```

G is the measured signed remainder, not a measured removable overhead.
B includes body, target head, merge wait and retirement. It cannot be split
into measured GPU durations from these command traces.

## Proposed dependencies and ownership

```text
B-body[p] -> h[p] -> speculative D*[p+1](h[p], g[p+1]) -> g*[p+2]
               \                         |
                final norm/head ---------+--> verified t[p+1]
                                               |
              hit: commit D* and A[p+1]; use g*[p+2]
              miss: discard D*, restore draft state; recompute D with t[p+1]
                    restore/correct A[p+1] concurrently with corrected D
```

D* and the rank1 head remain serialized on its single CCS. Two concrete
orders must be distinguished:

1. **Move D before the existing head-export/prefix/publish sequence.**
   Both head branches become eligible later by D. A hit gets its next draft
   early relative to the new emission, but that emission can move later.
   Without an exposed dependency wait there is no steady-state rank1 saving;
   a miss adds a wasted draft before correction. If the old suffix was waiting
   for A, some of that delay could be absorbed. Its duration is unobserved.
2. **Publish the ready hidden vector before D, or run D after prefix compute
   but before merge.** The suffix can then run concurrently with D. This can
   fill rank1's wait for the suffix. It is a distinct head-publication/progress
   change, whose useful wait is not separately measured in the saved traces.
   Variant1 also needs a draft transaction; none is a safe one-line move.

Rank0 cannot simply start a second speculative target half while its previous
candidate is unresolved: the current controller has one candidate/snapshot.
The first design keeps that ownership and starts A[p+2] only after t[p+1]
verification and suffix service. Speculating two unresolved target halves
would need a separate depth-two state design; it is not a free scheduling
edge. No unverified token may enter the output, PLE history, canonical draft
cache or request-final state.

The current `DraftRuntime::compute` advances private QSA/cache/control state;
discarding its token alone is insufficient. A future implementation needs a
transaction over every mutable allocation and host position/extent, disabled
flag, async publication and progress state. On a miss restore the exact
pre-D* state before recomputing. Provider errors remain sticky/fail closed.
Do not roll back errors to fabricate a successful candidate.

Known prompt positions can use the known token; the first unknown token has
no guess and takes the current path. At EOS and the final response-cap token,
the old path does not advance the next draft: any speculative work must be
discarded and its complete state restored. Extent transitions (31/32,63/64,
etc.), first/last generation, first/last prompt, all-hit/all-miss/alternating
patterns, no-guess and provider-error paths need controller tests if admitted.

## Evidence and reproduction

`inputs.tar.gz` retains original-byte candidate summaries for both complete
packet118 composite lanes, the selected runtime sources, head-transfer logs,
empty site/timing files, and every existing DO-NOT-REPEAT index. The archive
is intentionally over1 MiB: the raw trace inputs were not all tracked, and
hashes alone would not preserve reproducibility. No originals were removed.
Its member paths are repo-relative; read with `tarfile` or extract into a new
scratch directory. `capture_inputs.py` verifies every member against its
original before writing, and refuses to overwrite a snapshot.

The `method/` copies preserve packet108's extractor and packet85's join helper
byte for byte. The simulator executes only their accounting function ASTs,
never their old import-time resource caps. No model or device code is imported.

[Work note](../../../../notes/2026-10-18-own-runtime-packet126.md).
