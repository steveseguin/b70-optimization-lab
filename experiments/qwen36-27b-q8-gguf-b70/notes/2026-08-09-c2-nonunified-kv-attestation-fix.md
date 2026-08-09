# c2 non-unified KV attestation fix

Date: 2026-08-09

## Failed attempt

The first formal short-band c2 launch stopped before any benchmark requests:

`/mnt/fast-ai/bench-results/qwen36-27b-q8-gguf-b70/runs/goal1-formal-c2-gpu0-short-20260809T164938.287900799Z`

The fail-closed runner exited 1 at the sequential-server attestation and sealed
the failed packet. Cleanup was clean and all four cards returned to idle. This
was a harness expectation error, not a model-fit failure.

## Evidence and diagnosis

The server successfully established the intended c2 identity:

- `n_ctx=65536`, `n_ctx_seq=32768`, `n_seq_max=2`;
- two runtime slots at 32,768 tokens with `kv_unified=false`;
- `65/65` layers fully offloaded;
- 4,096 MiB F16 KV and 299.25 MiB recurrent state;
- projected device use 30,406 MiB, leaving 1,814 MiB against the required
  1,024 MiB floor.

The only false field was `f16_kv_4096_mib`. The harness expected the KV log's
cell field to be 65,536. llama.cpp's non-unified cache instead reported:

```text
size = 4096.00 MiB (32768 cells, 16 layers, 2/2 seqs),
K (f16): 2048.00 MiB, V (f16): 2048.00 MiB
```

For `--no-kv-unified`, that field is the per-sequence capacity. Total context
is already attested independently by `n_ctx=65536`; `n_ctx_seq=32768`, the
`2/2` sequence count, and the 4,096-MiB allocation complete the proof.

## Fix and validation

The attestation now requires the observed 32,768 per-sequence cell capacity
while retaining every total-context, byte-size, sequence-count, F16, fit,
slot, and full-offload gate. No memory, quality, or performance threshold was
weakened.

Offline checks after the one-field correction:

- both shell scripts passed `bash -n`;
- 17 c1 capture tests and 24 c2 capture tests passed;
- `git diff --check` passed.

The decisive validation is a fresh formal c2 run: both independently launched
servers must pass the corrected attestation and the full exactness, semantic,
occupancy, fairness, cleanup, and sealed-completion gates. The failed packet is
retained so the original false-negative and its evidence remain auditable.
