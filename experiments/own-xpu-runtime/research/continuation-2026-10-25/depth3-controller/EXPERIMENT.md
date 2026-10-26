# Depth3 experiment: pending

The two-request measured32 GPU gate is running under `sc117-depth3-measured-20261026`; no correctness outcome or performance gain is claimed yet. Raw evidence remains protected at `/dev/shm/sc117-ring-20261025/persistent-depth3-measured-a`.

Configuration: [config](../depth3-measured-config.json), corrected [plan-b](../depth3-measured-plan-b.json), native build `59a4edd9` ([native evidence](../depth3-native/)). Baseline placement remains stage0 on cuts `0,8,21,34,48`; capture-ready overlap and flat-copy are enabled, with explicit speculative depth3. Every worker receives `--pipeline-ring-depth 3`; default depth2 adds no depth flag.

The existing [32-output recorded reference](../recursive-provider-reference-depth3.json) retains third guesses for comparison; it does not establish this live gate's result.

The initial CPU plan used unsupported `--pipeline-ring-depth3`. It was never launched. Root corrected the option to `--pipeline-ring-depth 3` before GPU execution and produced plan-b. This folder retains the corrected patch, source identities, focused test and CPU check receipt.
