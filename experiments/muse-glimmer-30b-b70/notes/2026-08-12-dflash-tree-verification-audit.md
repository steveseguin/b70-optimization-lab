# DFlash compact-tree verification audit

Date: 2026-08-12

## Why this lane exists

The exact kernel stack plus pretrained DSpark and device maxloc reaches an
honest `62.073 t/s`, leaving too large a gap for launch cleanup alone. A valid
way to amortize the target's BF16 weight pass is to verify more than one draft
path in the same target batch. This is inference-path work and requires no
drafter training.

## Source facts

DFlash generates its complete block in one non-causal draft decode. The input
is one anchor token followed by masks, and CPU sampling reads every row only
after that decode; sampled row tokens are never fed back into the DFlash graph.
Consequently, a path assembled from each row's top-k candidates is a valid
proposal even when it differs from the row-wise top-1 path. It remains exact
because the target model verifies every emitted token.

DSpark needs separate treatment. Its graph contains an internal greedy Markov
chain between block rows. Alternative row tokens are still valid target
proposals, but later DSpark row scores describe the internal top-1 path rather
than the alternative branch unless the inexpensive Markov component is
recomputed.

The tree mechanism itself is already demonstrated in
`examples/speculative/speculative.cpp`: it copies target KV sequence state,
shares common-prefix tokens across sequence IDs, decodes all unique tree nodes
in one target batch, and retains the surviving sequence. The production server
currently supports only a linear draft vector and linear batch-index vector,
so this is real server-loop engineering, not an environment switch.

## Honest ceiling from the existing measurements

The fixed DFlash rows imply approximately 84 / 59 / 49 target rounds for
prose/code/JSON, or `3.05 / 4.34 / 5.22` emitted tokens per roughly
`65--67 ms` round. Reaching 100 t/s at unchanged round cost needs about `6.6`
emitted tokens per round; if tree width raises the target-pass cost by 10--20%,
the requirement rises to about `7.2--7.9`.

A first-position top-2 split creates two 15-token paths: 31 unique target rows
with a shared anchor, or 32 rows in the simplest fully isolated proof. Fitting
a stationary suffix-match hazard to the measured emitted lengths gives a
generous perfect-top-2 ceiling of only about `75 t/s` if batch-31 costs just 5%
more than batch-16, and less as realistic coverage/cost are applied. Splitting
more positions explodes unique rows (roughly 31 / 59 / 111 / 207 for binary
depth 1--4). Therefore compact trees are a possible supporting gain, not the
primary 62-to-100 route.

## Important accounting correction

Seeing the first target mismatch at DFlash rank 2 or 3 is not itself a speed
win. The linear verifier already emits that target mismatch token. A useful
tree must also evaluate the alternative token as a target input. Its output
then guarantees the next target token, and a deeper branch can additionally
verify the old block's remaining top-1 suffix.

`scripts/analyze-muse-dflash-topk-coverage.py` measures exactly this opportunity
without changing inference. With server verbosity 4 and `LLAMA_TRACE=1`, it
joins the existing per-position DFlash top-3 logs to the server's accepted
prefix and sampled mismatch. It reconstructs the canonical emitted token
stream, checks how long the stale top-1 suffix would match after a rank-2/3
repair, and reports oracle emitted-token ratios for suffix depths 0--4. Those
ratios are feasibility ceilings, not throughput claims, because a wider target
batch has a nonzero cost.

## Preregistered post-reboot order

1. Complete the documented four-device recovery gates and restore incumbent
   production health.
2. Run the fresh isolated parallel-submit A/B in
   `sweeps/20260812-meta-parallel-submit-ab-v3.json`.
3. Restore production and health before interpreting that A/B.
4. In a separate window, run
   `sweeps/20260812-dflash-topk-tree-oracle.json` and parse its server log into
   a tracked summary. Debug logging makes this a coverage diagnostic only.
5. Implement a server tree only if the measured oracle, combined with a
   batch-width target timing screen, has a plausible ceiling above 100 t/s.

The smallest correctness proof, if justified, should use two fully duplicated
16-row paths with separate target and draft sequence IDs. Existing
`common_speculative_process` may inject both isolated paths before selection;
then retain/copy the winning target+draft sequence and prune the loser. Do not
slice a winning sub-batch after decode without remapping embedding row indices,
and do not use shared-prefix rows until DFlash's one-sequence-per-row assertion
is deliberately redesigned.

Do not implement a naive second DFlash block in the same target pass: the next
block needs target-layer features produced by the first verification pass.
