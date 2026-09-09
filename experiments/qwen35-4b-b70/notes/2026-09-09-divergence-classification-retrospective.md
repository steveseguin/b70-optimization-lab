# Half the divergences are not tie flips: one token is emitted five positions early (2026-09-09)

Read entirely out of ladder files already on disk — no cards, no new runs. This
extends `2026-09-08-the-divergences-are-a-dozen-fixed-tie-sites.md` and corrects
one of its claims.

## What the 2026-09-08 note established, and what it assumed

That note resolved the two-card divergences into a dozen fixed sites, each a
`(prompt, token position, substitution)` triple that always flips the same way,
and argued this is what an exact two-way tie looks like. Two of its observations
hold up completely: sites are highly repeatable, and nothing is a single-token
substitution with an identical remainder (once a token changes, the continuation
is conditioned on it).

The assumption underneath is that the first differing index is a **substitution**
— that `466 -> 5787` means the tie between candidates 466 and 5787 broke the
other way. `analyze-divergence-positions.py` could not test that assumption
because it only compared position by position; an inserted token makes every
later position differ and looks identical to a substitution followed by
divergence.

## What alignment shows

The analyser is now alignment-based (difflib). Censusing every divergence in
every 9B and 4B ladder on disk — 2532 divergent requests across 135 sites:

| leading edit | count | share |
| --- | ---: | ---: |
| `insert(early+5)` | 1295 | 51% |
| `replace` | 1171 | 46% |
| `delete` | 42 | 1.7% |
| `insert` (other) | 23 | 0.9% |
| `insert(novel)` | 1 | — |

**The single largest class is not a tie.** All 1295 members of the `466 -> 5787`
family — every `monitoring-c020`, `monitoring-c044`, `monitoring-c036` variant,
across both the speculative and the no-speculation ladders, in every arm — have
the same structure, with no exceptions:

- at position 90 the run emits `5787`, which is the token the **oracle emits at
  position 95**, five positions later;
- the run then emits `466`, the token the oracle emits at position 90;
- divergence follows from position 92.

That is not two candidates tying and the tie-break going the other way. Under a
tie the model picks 466 *or* 5787. Here it picks 5787 **and then still picks**
466. The correct description of the site is "a token is emitted five positions
early," and `466 -> 5787` is an artifact of reading only the first differing
index.

**The tie model does hold for the other half.** `rollback-c042` @38
(`16070 -> 24141`, 83 occurrences) and `index-c041` @77 (`10993 -> 24816`, 82)
classify as `replace` in every occurrence. For those sites the 2026-09-08
reasoning stands as written.

So the dozen sites are better described as (at least) two mechanisms, not one:
a repeatable early-emission event that accounts for just over half of all
divergences, and a set of genuine tie substitutions accounting for most of the
rest.

## The 4B, and the phantom without speculation

The 4B's three MTP0 c64 flips (2026-09-07 `v1`/`t1`) are one clean
`insertion(1)` — `benchmark-c043`, one token inserted at index 124, everything
else identical, similarity 0.992 — one four-token deletion, and one content
divergence. AGENTS.md documents that inserted-token signature for the MTP
first-token phantom. Here speculation is off. It is one event and should be
treated as one until the 2026-09-09 campaign puts a rate on it, but combined
with the 9B early-emission class it is the second insertion-shaped defect
visible on this stack with no draft model in the loop.

## Why it matters for experiment design

The interventions this lane has built and measured — the W4A16 determinism pad,
row-wise all-reduce, serialised norm — all target **row-count dependence in
tie-breaking**. That is the right instrument for the `replace` half. There is no
argument on record that it addresses an early-emission insertion, and the pad was
measured inert at MTP0 below 128 rows anyway. Splitting the divergence rate by
leading-edit class before comparing arms would make those comparisons much
sharper: the two classes may respond to different interventions, and pooling them
dilutes both.

The 2026-09-08 note's proposal to fill batches with fragile prompts is still the
right move for throughput of evidence, with one amendment: `monitoring-c*` and
`rollback-c042` should be run as **separate** fragile sets, because they are now
known to be different phenomena.

## Second-order finding: pass 1 of a ladder is warmup-contaminated

While tabulating throughput: `tp1 mtp3` pass 1 reports c2 at 134.1 tok/s, *below*
its own c1 at 158.8, against 300.8 in pass 2. TP2 shows the same shape (c2 150.9
vs 428.4; c4 400.4 vs 759.6). The low-concurrency rungs of the first pass are not
usable as throughput. Identity is unaffected — exactness does not care about
warmup — but any speed reading from a ladder should use pass 2 onward, and the
two-pass default leaves exactly one usable pass.

## Changes

- `experiments/qwen35-9b-b70/scripts/analyze-divergence-positions.py` extended
  with difflib alignment classification. Output gains a class and a similarity;
  the JSON gains `kind_counts` and `alignment_shifts`. Existing fields unchanged.
  Not pinned by any hash gate.
- No published result is invalidated: nothing in `results/`, `repro/` or
  `packages/` claims a mechanism for these flips. What changes is the mechanism
  sentence in the 2026-09-08 note and the design of the next intervention test.
