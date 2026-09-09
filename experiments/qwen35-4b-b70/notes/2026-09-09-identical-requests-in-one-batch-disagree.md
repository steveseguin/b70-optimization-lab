# Byte-identical requests in the same batch disagree with each other

Read out of the 9B verbatim fragile ladders already on disk. It explains why the
determinism pad does nothing, and it narrows what could.

## The observation

A verbatim ladder fills its slots with byte-identical copies of the same prompt.
Across the 9B fragile campaigns, **429 of 1920 copy-groups (22.3%) contain copies
that disagree with each other inside a single batch** — same text, same batch,
same steps, different completions.

Two further properties:

- **Always exactly two distinct outputs**, never three, from five or six copies.
  The distinct-output histogram over all 1920 copy-groups is `{1: 1491, 2: 429}`:
  a group of identical copies produces either one completion or exactly two, and
  a third was never observed. That is the strongest single statement of the
  binary-fork model in this campaign, because it is 429 independent chances for a
  third branch to appear and it never did.
- **Almost always exactly one copy in the minority.** A typical group reads
  `majority slots [2, 14, 26, 38, 62], minority slot [50]`.

## What it rules out

Batch composition is identical for every copy in a group — they are in the same
batch, in the same steps, with the same neighbours. Prompt text is identical.
So neither content nor batch shape decides which branch a request takes.

That is why the determinism pad cannot help, and the measurement agrees: padding
decode row counts to fixed tiers costs 11.7% at depth-3 c64 and leaves the site
set, the per-site counts and both divergence measures unchanged. The pad makes
the batch *shape* constant; the disagreement here happens at constant shape.

More generally, any intervention whose mechanism is "remove dependence on how
many rows are in the batch" is aimed at the wrong thing for this phenomenon.

## What it does not settle, and why

The tempting next step is to read the slot indices. Which copy lands in the
minority varies between passes — `monitoring-c020`'s minority slot is 50, then
38, then 26, then 50 again; `index-c041`'s is 49, then 1, then 13 — and no slot
dominates the frequency table.

That looks like run-to-run nondeterminism at fixed shape rather than a fixed
row-position effect. **It is not evidence for that, because the `-sNNN` index is a
client-side expansion index, not a server-side batch row.** The harness launches
all requests through a thread barrier, so their arrival order, and therefore
their row assignment, varies from pass to pass. A stable "row 7 always diverges"
effect and genuine run-to-run nondeterminism produce the same client-side
picture.

Separating them needs the server row, which the client cannot pin: the harness's
`--pin-slots` sets an `id_slot` field that vLLM's `OpenAIBaseModel` accepts under
`extra="allow"` and never reads. It is a llama.cpp parameter and is a **no-op on
this path**. The `g2` arm queued in chain 2 will therefore be a replicate of `g1`,
not a slot test, and must be read that way — it is still useful as a same-config
repeat for a noise estimate.

`g3`, which staggers arrivals by 25 ms, is a real manipulation of this variable:
it changes arrival order and step composition rather than trying to pin a row.

## Only the 9B has verbatim data so far

Scanning every lane, the 9B fragile campaigns are the only verbatim runs on disk;
the 27B and 4B have none. Chain 2's `g1`, `g2` and `g3` arms are verbatim and will
give the first 4B copy-groups, so this can be checked on a second model tonight.

## Where this leaves the mechanism

Established: the fork is between two whole continuations; the sites are stable
across days, reboots, compilation modes and the pad; the direction flips when the
arithmetic changes under TP2; and now, identical requests in one batch take
different sides.

So whatever chooses the branch is neither the prompt, nor the batch shape, nor
the batch composition. It is something that differs between two identical rows of
the same step — reduction order, work-group scheduling, or an atomics ordering
inside the kernel are the obvious candidates, and this data cannot distinguish
them.

The margin probe in chain 4 is the next useful measurement: if the logit gap at
these sites is at or near zero, then any of those candidates suffices and the
question becomes which one, not whether.
