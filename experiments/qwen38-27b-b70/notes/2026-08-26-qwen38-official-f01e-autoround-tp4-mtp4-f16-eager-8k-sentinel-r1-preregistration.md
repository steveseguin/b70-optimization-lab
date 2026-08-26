# Qwen3.8 official AutoRound TP4 eager MTP4/F16 8K sentinel R1

Status: **preregistered and executable; not launched**.

This bounded sentinel tests the current-f01e TP4/MTP4 route without borrowing
authority from another topology or runtime. Its target is the just-passed
same-image, same-topology TP4/MTP0/eager/F16 exact-8K oracle. The frozen parent
exact receipt is `49ea5c...`, its 128-token output hash is `34e792cc...`, its
terminal receipt is `779c64...`, and its objective-quality receipt is
`201924...`. Any target-token mismatch is a quarantine, not a caveated pass.

The server keeps the proven parent identity: TP4, `ZE_AFFINITY_MASK=0,1,2,3`,
memory utilization `0.60`, F16/auto KV, eager graph-off execution, one sequence,
and no `ONEAPI_DEVICE_SELECTOR`. The only serving change is native MTP4 via
`qwen3_next_mtp` with `num_speculative_tokens=4`; startup must report method
`mtp` and `num_spec_tokens=4`. The embedded MTP config, 29 indexed MTP tensors,
and `model_extra_tensors.safetensors` hash are frozen before launch.

The exact 8K request is isolated between before/after metric snapshots.
Speculative draft and accepted counters must both exist, remain finite and
nondecreasing, and produce positive deltas with `accepted <= drafted`. Exact
depth, all 128 target IDs, four-worker topology, runtime identity, rank-cache
isolation, objective quality, all 16 explicit cache-zero quality usages, all 24
same-topology baseline comparisons, and global cleanup must all pass.

The output and compilation caches use new fresh ext4 roots, and the server uses
fresh port `19485`. Graph-off should produce no compile files; if files appear,
all must live beneath the four rank namespaces with no shared artifact.

The current-f01e TP1/MTP4 expansion hit an EngineCore speculative-token shape
fatal at exact 32K. That is profile-local risk context only: TP1 at 32K is a
different topology and depth, so it does not predict, close, or weaken this TP4
exact-8K sentinel. Any failure here preserves lower-grade evidence but cannot
publish, replace protected results, or authorize descendants automatically.

Static check:

```bash
experiments/qwen38-27b-b70/scripts/run-20260826-qwen38-official-f01e-autoround-tp4-mtp4-f16-eager-8k-sentinel-r1.sh --check
```

GPU execution (not performed during packet preparation):

```bash
experiments/qwen38-27b-b70/scripts/run-20260826-qwen38-official-f01e-autoround-tp4-mtp4-f16-eager-8k-sentinel-r1.sh \
  --execute \
  --ack 'RUN qwen38-official-f01e-autoround-tp4-mtp4-f16-eager-8k-sentinel-20260826-r1'
```
