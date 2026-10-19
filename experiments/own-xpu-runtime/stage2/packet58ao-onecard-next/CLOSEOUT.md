# Packet58ao one-card next compute lever — closeout

<!-- campaign-closeout -->

## Question and identity

October 19, 2026, CPU-only, 60-minute budget. Find a supported ≥2% exact
compute-tail lever behind packet58am on the one-card packet58aj record:
31.9668197878 tok/s, quantized compressed Unsloth UD-IQ3_XXS,
`iq3-p49-split32-v1`, target-only, BF16 KV, context4096, max expert cache and
resident lookup copies. Twelve cold 128-token prompts; strict512 false.

## Outcome

Closed without implementation. All applicable accepted two-card target
mechanisms are present except rec-both-plus, whose earlier one-card combined
route/recurrence test was inconclusive and closed. No new ≥2% support was found.
No packet58ap, build, device proposal or readiness marker was created.

## What worked

The source/selection inventory distinguishes adopted adaptations from absent
selection strings: route-fast is inside p109, and E1 uses an exact half table
instead of expanded rows. Replaying actual 58ah-b and 58aj-a WS128 streams
reproduces both record rates. The current 2% threshold is 0.612738 ms/token
under a uniform-saving sensitivity with the correct prompt-class aggregation.

## What failed or remains uncertain

No lever qualified. Device-class times are unavailable in the current one-card
traces; the 20.77 ms wait cannot be divided into exact per-op costs. The ranked
two-card diagnostic proxy is explicitly not a one-card timing result. Broad
scale multicast still needs unsupported transfer to pass. Tests initially
exposed two reader schema assumptions (unequal class sizes, aggregate stored as
an object); the final reader uses the actual schema and passes the retained
real-data and refusal checks. No GPU/software fault occurred.

## Evidence and patches

- [Inventory](INVENTORY.md), [ranked analysis](README.md), [negative search](negative-search.txt).
- [CPU replay](analyze.py), [results and input hashes](analysis.json),
  [failure controls](test_analyze.py), [verification](verification.json).
- [Negative index](DO-NOT-REPEAT.md),
  [work note](../../../../notes/2026-10-19-own-runtime-packet58ao.md).

No runtime patch or binary exists. Input receipts remain at their original
paths with byte hashes retained. No model payload or full-shape read was needed.

## When to revisit

New low-overhead matched class/critical-path evidence, or a distinct exact
mechanism with at least 0.612738 ms/token net support under current aggregation,
including new overhead. Consume packet58am's separate miss-path result before
revisiting overlapping expert traffic. Any qualifying packet must pass the
full requested source, shape, binary-help, real environment, queue/report,
memory/disk, exactness and READY-last gates before coordinator device admission.
