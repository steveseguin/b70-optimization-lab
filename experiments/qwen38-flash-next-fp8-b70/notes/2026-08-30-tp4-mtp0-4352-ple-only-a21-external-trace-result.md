# Qwen3.8 Flash-Next FP8 A21 external-model trace result

Date: 2026-08-30
Status: external load and complete battery passed; trace comparison localized

A21 loaded the exact validated checkpoint from the external NTFS drive after
the local Samsung NVMe path had twice coincided with a host stop before shard
1. All 131 shards loaded on all four ranks in about 583 seconds, the endpoint
became healthy, the client completed, and the supervisor tore down cleanly.
The journal classifier found no blocking or fatal event. One corrected APEI
PCIe RxErr/NonFatalErr for the local Samsung NVMe endpoint did occur during
external shard loading; its uncorrected status was masked and A21 continued to
completion. This validates the external checkpoint as an operational
workaround, not proof that the NVMe endpoint alone caused the earlier resets,
and it does not change model identity.

The unchanged battery passed recovery, the inherited 6/7 semantic boundary,
16/16 repeatability, the exact 4K needle, all three protected short hashes, and
both exact-4K authority rows. The short diagnostic median was `5.496024 tok/s`.
The two 4K rows were `5.268947 / 5.234646 tok/s`, both cache-zero and both the
protected `1d833e...` output. Trace synchronization means none of these timings
receive performance credit and no protected result changes.

The A16/A21 comparison is exact: both traces contain the same 51 ordered
records, positions 3968–4031, and 149 tensor digests. Six digests match: model
positions, model input hidden/input IDs, and all three layer-0 outputs. The
remaining 143 first differ at `layer_1_output`. Zero-based layer 1 is the only
PLE-bearing decoder layer and is a linear-attention layer.

That localizes the first difference to the sole PLE-bearing layer invocation,
not yet to the PLE lookup itself. The next diagnostic must record the PLE
inputs, lookup output, post-add state, hyperconnection/attention boundary, and
MLP boundary. No arithmetic treatment or further full load is justified until
that narrower trace exists.

Structured receipt:
[`../data/20260830-tp4-mtp0-4352-ple-only-a21-external-trace-positive.json`](../data/20260830-tp4-mtp0-4352-ple-only-a21-external-trace-positive.json).
