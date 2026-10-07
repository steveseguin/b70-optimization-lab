# Durable context revision 4

The [prospective plan](../../../notes/2026-10-07-durable-context-r4-plan.md)
defines fresh development and uncached timing after r3's inspected outcome.
All earlier source trees and failed verdicts remain preserved.

The primary pair is archive (model-maintained table) versus quoted events
(code-applied verified events). Summary remains a secondary diagnostic. Every
primary answer must be correct; every planned trial, including summary, must
complete cleanly with all question IDs. Summary accuracy is always reported
separately. This narrower claim does not retroactively qualify r3.

Development uses fresh seeds 17 and 29, both authored styles: 12 trials. The
same seed-7 extraction diagnostics live in the separate `calibration/` directory.
Only after all eight structured development trials are 24/24, the entire matrix
completes cleanly, and every request has verified zero cache usage, can held-out
seeds 401/502/603 be used (18 trials). Styles share per-seed underlying events;
this remains a synthetic pilot, not independent natural-document validation.

Model-facing behavior is unchanged from r3: ingestion and extraction thinking
off with 4096 output tokens; final answering thinking on, medium effort, 8192
combined reasoning/answer tokens. The 32768-byte input budget, 32 answer calls,
24 distinct retrieval operations, saved partial answers and explicit submission
are unchanged. Exact batch fetch and digit-bounded search remain available.
Malformed model output consumes a bounded action; transport/envelope failure or
output cutoff ends the attempt without server retries.

The separate host runner derives a prefix-cache-disabled profile from the pinned
qualified launch, preserves all arithmetic/KV precision settings, omits its warmup
request, and checks actual cold launch flags before strict qualification.
The timing check independently reads every native call log. Cache counts must
be explicit nonnegative integers within prompt counts; any missing, malformed or
positive count blocks timing. Aggregate claims cannot hide raw cache hits.

One server's paired ratio is descriptive only. `single_server_speed_signal`
is not `speed_gate_passed`; a speed verdict requires a second fresh qualified
cold-server replication. No first-server ratio is published as a headline.

CPU validation:

```bash
python3 -m unittest discover -s experiments/qwen38-27b-b70/scripts/context/durable_v4 -p 'test_*.py'
python3 -m unittest discover -s experiments/qwen38-27b-b70/scripts/context -p 'test_durable_v4_host_runner.py'
```

Freeze without requests:

```bash
D=experiments/qwen38-27b-b70/scripts/context/durable_v4
DATA=experiments/qwen38-27b-b70/data/2026-10-07-durable-context-r4
python3 "$D/campaign.py" --stage development --suite "$DATA/development/suite.json" --out /tmp/context-r4-development-plan
python3 "$D/campaign.py" --stage holdout --suite "$DATA/holdout/suite.json" --out /tmp/context-r4-holdout-plan
```

Stub runs deliberately use the hidden oracle to exercise plumbing and can never
qualify model results. Real prompts never contain it. Live work uses the separate
`../durable_v4_host_runner.py` preparation and supervised execution lifecycle.
It stops its one server on completion or failure. The experiment must not run
beside another GPU owner. Native results remain separate from legacy site rows.
