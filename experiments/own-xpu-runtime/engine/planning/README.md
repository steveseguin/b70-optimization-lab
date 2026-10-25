# Pipeline placement proposals

This CPU-only tool reads the engine loader's existing `placement.tsv` and
proposes contiguous layer ranges for 1, 2, 4, 6, or another positive number of
GPUs. It opens no model weights, discovers no devices, and launches nothing.
The layer count, per-layer tensor sizes, and quantization IDs come from the
input, so another quant or model does not require a copied planner.

From the repository root:

```bash
python3 -B experiments/own-xpu-runtime/engine/planning/placement.py \
  --placement experiments/own-xpu-runtime/gsq-rco-iq3s/loader/placement.tsv \
  --model-id SC117-Qwen3.8-Flash-Next-GSQ-RCO-abliterated-IQ3_S \
  --gpus 1 2 4 6 --output /tmp/sc117-partitions.json
python3 -B -m unittest discover -s experiments/own-xpu-runtime/engine/planning -v
```

The output path must be new. The checked-in [SC117 example](examples/sc117-partitions.json)
contains metadata and proposals only. Its placement and planner SHA256 values
identify the exact inputs and code. These hashes do not authenticate the model
payloads. The existing loader remains responsible for weight authentication.

The default objective minimizes the largest stage's **packed layer weight
bytes**. It is not a RAM/VRAM fit result or a prediction of pipeline speed.
All layer tensors are counted once; the old two-card placement masks do not
authorize or constrain a new topology. The head and other global tensors are
listed separately, as are the embedding and PLE lookups. In particular, SC117's
28.8 GB PLE lookup has layer number 1 in its metadata but resides in host RAM;
assigning that table to GPU 0 would make the weight partition misleading.

Before executing a proposed layout, a runtime plan must add the global/head
placement, draft, expanded weights, controls, KV/recurrent state, scratch,
runtime reserves, and host shadows. It must also prove the controller and state
transactions support the topology. The current engine's accepted two-stage
path and experimental rank-1 TP path are unchanged. Four/six-stage proposals
are **not** claims that four/six-stage execution already works. Whole-layer
partitioning is the only topology this tool proposes; TP and replicas have
different placement and memory semantics.

For compute balancing, supply `--cost-profile FILE` with this schema:

```json
{
  "schema": "ownrt.pipeline.layer-costs.v1",
  "placement_sha256": "<SHA256 of exact placement TSV>",
  "runtime_sha256": "<SHA256 of measured engine>",
  "measurement_sha256": "<SHA256 of retained measurement artifact>",
  "run_identity": {
    "activations": "f32",
    "context": 4096,
    "workload": "<exact measurement workload and flags>"
  },
  "layer_ns": [100, 120, 90, 110],
  "stage_overhead_ns": {"2": [20, 0], "4": [20, 0, 0, 0]}
}
```

The numbers above illustrate the format; they are not measurements. Supply one
nonnegative integer nanosecond cost per layer and, optionally, one overhead per
stage for each requested GPU count (for example, measured draft work). Omitted
overheads are explicitly labeled excluded. The profile is embedded and hashed
in the output. Its placement hash and coverage are checked, but the planner
does not verify the measurement artifact or infer whether the timing identity
matches a future run. Measured stage work still excludes pipeline bubbles and
does not predict single-conversation throughput.

Tests compare the partition optimizer with exhaustive search, including
unequal stage overheads; verify all tensor bytes are accounted for; reject
malformed or overlapping metadata and mismatched profiles; and exercise the
real SC117 metadata without reading its model files. Quant IDs are inventoried
as integers. Format-specific encoded byte sizes and decoder support are the
loader's responsibility, not inferred from an ID here.
