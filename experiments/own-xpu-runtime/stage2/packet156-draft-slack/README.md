# Packet156 — bound hidden draft work in suffix slack

**This is an evidence-first rejection of the specified host insertion, not a
prepared runtime candidate.** Packet154 confirms the draft is on rank0's
critical path. It does not establish an idle suffix window large enough to
hide that work. The complete replay and disposition are in
[ANALYSIS-CLOSEOUT.md](ANALYSIS-CLOSEOUT.md).

The requested branch is target-stream copy, unchanged hidden norm and unchanged
hidden projection, after rank1's prefix completes and before the suffix is
ready. The bound is `min(branch service, suffix slack) - adoption/dispatch`.
We bound the second term first. No weights, runtime, arithmetic, canonical
state, source packet, operations tool, service or live queue was changed.

[The supplied PLAN](../packet152-segment-prep/PLAN.md#verdict-to-build-dispatch)
explicitly says to record a failed mechanism bound and move on without a
device screen. Accordingly there is no speculative candidate, binary,
selection, or runnable lane-A/lane-B proposal. The final
`READY-FOR-DEVICE.json` has `ready_for_device: false`; completed analysis must
never be mistaken for device admission. The next-design audit is in the
closeout. The two-card 58.798 tok/s record remains unchanged.

Reproduce without a model or device:

```bash
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/stage2/packet156-draft-slack/test_analyze_slack.py -v </dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/stage2/packet156-draft-slack/replay_retained.py experiments/own-xpu-runtime/stage2/packet156-draft-slack/evidence/smoke-bound.json </dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/stage2/packet156-draft-slack/replay_retained.py experiments/own-xpu-runtime/stage2/packet156-draft-slack/evidence/bracket-bound.json </dev/null
```

All entry processes cap address space at 2 GiB. There is no elapsed-wall data
deadline or subprocess timeout. The parser runs on actual first-request
output and refuses missing/empty streams. Retained replay checks compressed
and original SHA256 values, restores to a temporary CPU-only directory,
replays the unchanged packet154 analyzer, and compares the entire bound.
No tests patch out the proof.

See [prior attempts](DO-NOT-REPEAT.md), [budget](BUDGET.md),
[retention](RETENTION.md), [smoke bound](evidence/smoke-bound.json),
[complete bracket bound](evidence/bracket-bound.json), and
[source pins](evidence/source-pins.json).
