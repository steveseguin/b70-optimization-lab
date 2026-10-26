# Depth3 experiment: closed negative

Closed slower: the measured32 gate passed all 64 outputs, per-request 2,065 target buffers and 73 draft allocations, and recorded third guesses. Full12 then passed all 5,965 output IDs and final 2,065 target buffers, but measured **43.381295 tok/s**, 4.019% below flat depth2 (45.197868) and 3.528% below capture depth2 (44.967924). Four workers exited zero; no live worker PIDs remained. Depth2 remains the default; no further depth sweep. [Post-host check](../host-depth3-suite-after.json) found no fault baseline change and no holders. See [combined result](../depth3-result.json), [short gate](../depth3-measured-proof/RESULT.md) and [suite](../depth3-suite-proof/RESULT.md). Protected raw evidence stays in tmpfs; no raw archive is claimed.

Configuration: [config](../depth3-measured-config.json), corrected [plan-b](../depth3-measured-plan-b.json), native build `59a4edd9` ([native evidence](../depth3-native/)). Baseline placement remains stage0 on cuts `0,8,21,34,48`; capture-ready overlap and flat-copy are enabled, with explicit speculative depth3. Every worker receives `--pipeline-ring-depth 3`; default depth2 adds no depth flag.

The existing [32-output recorded reference](../recursive-provider-reference-depth3.json) retains third guesses for comparison; it does not establish this live gate's result.

The initial CPU plan used unsupported `--pipeline-ring-depth3`. It was never launched. Root corrected the option to `--pipeline-ring-depth 3` before GPU execution and produced plan-b. This folder retains the corrected patch, source identities, focused test and CPU check receipt.

Work breakdown (overlapping work, not wall time; denominator `sum(output_tokens-1)`): stage0 ROW rose 8.784→10.130 ms/output and provider 5.194→7.082. Recursive draft doubled 2.064→4.114 ms; canonical, capture and restore stayed nearly flat. Extra speculative target work and the extra recursive pass outweighed pipeline fill.
