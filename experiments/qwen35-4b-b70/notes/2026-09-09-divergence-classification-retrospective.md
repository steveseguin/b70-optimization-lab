# Divergence classification: the tie model holds, and there is a separate rare stutter (2026-09-09)

Read entirely out of ladder files already on disk — no cards, no new runs.

**This note retracts a claim an earlier version of it made.** That version argued
that half the lab's concurrent divergences were a token emitted five positions
early rather than a tie flip, and a correction to that effect was appended to
`experiments/qwen35-9b-b70/notes/2026-09-08-the-divergences-are-a-dozen-fixed-tie-sites.md`.
That was wrong. The 2026-09-08 tie model is correct. What follows is what the
data actually supports.

## The retracted claim, and why it was wrong

Alignment analysis (difflib) of the dominant 9B site reported the run inserting
token `5787` at position 90, five positions before the oracle emits it. Decoding
the tokens settles it:

- `466` = `" or"`, `5787` = `" errors"`

The oracle continues `HTTP 500 or 503 errors)` and the run continues
`HTTP 500 errors or timeouts)`. Both are fluent, both are correct, and they fork
at position 90 on exactly two candidates — `" or"` against `" errors"`. That is a
two-way substitution: precisely what the 2026-09-08 note described.

difflib called it an insertion because the two continuations reuse the same
words in a different order, so the later `" errors"` in the oracle aligns with the
earlier `" errors"` in the run. On natural language that alignment is routine and
means nothing about mechanism.

The specific defect in the analysis was in an ad-hoc census script, not in the
committed tool: the census classified on difflib's **first** opcode without
requiring the remainder to realign. `analyze-divergence-positions.py` is stricter
— it reports `insertion(n)` only when a single edit survives after the response
cap's overhang is discounted — and it correctly reported **0** pure alignment
shifts in 183 MTP0 and 2308 speculative 9B divergences. The tool was right and
the conclusion drawn around it was not.

## What the data does support

### 1. The tie model, now with direct evidence

A substitution site that is a genuine tie should sometimes resolve the other way
even in the sequential oracle, because each campaign regenerates its own oracle.
Censusing every ladder in the 27B, 9B and 4B lanes for sites where the same
`(prompt, index)` pair appears in **both** directions across campaigns finds 39
such sites. Several are close to even:

| lane | prompt | idx | pair | seen |
| --- | --- | ---: | --- | --- |
| 27B | `capacity-c006` | 11 | `" fixed"` ↔ `" finite"` | 42 / 33 |
| 27B | `capacity-c014` | 18 | `466` ↔ `326` | 27 / 19 |
| 27B | `cache-c000` | 96 | `348` ↔ `2972` | 12 / 10 |
| 27B | `monitoring-c028` | 32 | `5222` ↔ `7695` | 5 / 5 |
| 9B | `monitoring-c036` | 90 | `" or"` ↔ `" errors"` | 27 / 4 |

A site whose own single-stream oracle is unstable is a tie by any reasonable
definition. This is stronger evidence for the 2026-09-08 reading than that note
had available, and it is the useful new result here.

### 2. A genuinely distinct stutter class — four events lab-wide

Requiring the strict definition (one edit, remainder identical after discounting
the cap overhang), the whole corpus contains **four** clean single-token
insertions:

- 4B `benchmark-c043` @124, token `42903` = `" inference"`, similarity 0.992,
  TP2 c64 **MTP0**. The oracle reads `Inference performance is highly dependent`;
  the run reads `Inference inference performance is highly`. A duplicated word.
  Both responses have 128 tokens, 128 chunks and `finish_reason=length`, so this
  is a generated token, not a streaming artifact.
- 27B `evidence-c151` @123, token `82` = `"s"`, similarity 0.992, three
  occurrences in the `qwen38-int4-graph-drafthead-tp2-mtp1` ladders.

Both sites sit at index 123-124 of a 128-token cap. With four events that is not
a pattern to build on, but it is the reason to look at the end of the response
first if anyone chases this.

The 4B event occurred with speculation **off**, which is still worth noting
because AGENTS.md documents the inserted-token signature for the MTP first-token
phantom. It has not recurred in the 1920 TP1 MTP0 requests of tonight's `f1` arm,
so it is either TP2-specific or rarer than 1/1920.

### 3. Class split by model, using the strict classifier

| leading edit | 27B (947 div.) | 9B (2491) | 4B (246) |
| --- | ---: | ---: | ---: |
| substitution / replace | 73.5% | 45.8% | 83.7% |
| insert (incl. forks) | 15.4% | 52.0% | 12.2% |
| delete | 9.8% | 1.4% | 3.7% |
| clean `insertion(1)` | 3 | 0 | 1 |

The middle row is **not** a mechanism claim — as established above, most of it is
forks between continuations that share vocabulary. It is reported so the number
is not rediscovered and misread again.

### 4. The FP8 fresh-server failure has the same structure at concurrency 1

`2026-09-07-qwen35-4b-fp8-repeat-exactness.json` recorded the 4B FP8 build
failing G1 on the strict 12-prompt suite across three independent campaigns, at
`max-num-seqs 1` — no concurrency at all, just fresh servers. Its structure is
the same as the ladder's:

- exactly 3 of 12 prompts are tie-prone; the other 9 are stable across all six
  servers;
- each tie-prone prompt has **exactly two variants**, never a third, with servers
  partitioning between them (`code-review`: q1a+q2a+q3a+q3b against q1b+q2b).

Two variants and no third is the signature of a two-way tie, and it is visible
here without any batching at all. That is the same phenomenon the ladders see;
only the perturbation differs. On FP8 the tie is broken differently by whatever
varies between fresh servers, and on W4A16 — which is repeat-exact across fresh
servers, G1 12/12 — it takes concurrency to move it.

So the row-invariant kernel does not remove the ambiguous branch points. It
removes one source of perturbation at them.

## Independent findings that stand

### Divergence is concentrated and stochastic

From tonight's 20-pass `f1` arm on one card, at c64 with depth 3: 16 prompts of
64 carry all 170 divergences, at per-pass rates from 10% to 95%, and **none**
diverges in every pass. At c32, 5 prompts of 32, and one pass in 20 is fully
clean. When a site does fire it produces a byte-identical divergence every time —
`cache-c056` fired three times in the MTP0 arm, always at token 50 with the same
pair. A prompt can carry more than one site: `index-c041` diverged at token 53 in
one pass and token 2 in another.

This is what the 2026-09-08 note predicted, and it is what `build-fragile-suite.py`
is for.

### Ladder pass 1 is warmup-contaminated

`tp1 mtp3` pass 1 reports c2 at 134.1 tok/s, *below* its own c1 at 158.8, against
300.8 in pass 2. TP2 shows the same shape. Low-concurrency rungs of the first
pass are not usable as throughput; identity is unaffected. The two-pass default
leaves exactly one usable throughput pass.

## Changes

- `analyze-divergence-positions.py` keeps the alignment classification; it was
  correct. A future reader should note that `shift-then-drift` means only that
  difflib's first opcode is a shift, and on prose that is usually a shared-word
  fork rather than a real insertion. Only `insertion(n)`/`deletion(n)`, which
  require the remainder to realign, carry mechanism.
- `analyze-site-fragility.py` and `build-fragile-suite.py` are new and unaffected
  by the retraction.
- No published result is affected in either direction.
