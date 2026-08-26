# Official f01e AutoRound TP4 eager MTP0/F16 8K oracle sentinel R1

Status: **preregistered and executable; not launched**.

This bounded control establishes the current-f01e TP4/MTP0 target-only parent
needed before TP4 MTP1-4 can be interpreted. It uses all four B70s, eager
graph-off execution, F16/auto KV, one exact 8K request, and the full frozen
quality battery in one server lifetime. It neither launches spec decode nor
changes any protected result.

The immutable identity is the official f01e image (`f01e24f6...`), vLLM source
`ac7509e2...`, XPU kernels `0.1.12.3`, and AutoRound revision `bce40ca...`.
The server uses TP4, `ZE_AFFINITY_MASK=0,1,2,3`, memory utilization `0.60`,
`max-num-seqs=1`, and `max-model-len=32896`. `ONEAPI_DEVICE_SELECTOR` is not
set. Both XPU graph environment switches are explicitly zero, `--enforce-eager`
is required, the F16 cache is selected by omitting `--kv-cache-dtype`, and no
speculative configuration is passed. Startup must prove all four rank/local-rank
pairs and world size four.

The exact 8K response is compared with all 128 token IDs from the frozen
current-f01e TP1/MTP0/eager/F16 receipt (token hash `34e792cc...`). This is a
conservative same-image cross-topology comparison, not an assumption that TP1
and TP4 must be numerically identical. The older TP1 quality baseline is also a
comparison grade. Neither comparison is a prerequisite for a same-topology TP4
oracle. Exact 8K, objective `quality.json` `pass_all`, exact runtime identity,
four-worker topology, cache isolation, and cleanup are the native requirements.
If those pass while TP1 token parity or `baseline_match_all` differs, the output
is frozen as a lower-grade TP4 oracle with the precise caveat recorded.

The compilation and XDG caches are fresh ext4 paths. Graph-off should create no
compile artifacts. If the runtime creates any, every artifact must be contained
in vLLM's proven per-rank `rank_0_0` through `rank_3_0` namespaces, with all four
namespaces represented and no shared file. Writable NTFS is forbidden. Startup
is bounded to 20 minutes, requests are bounded, and EXIT/INT/TERM cleanup plus a
strict all-render-node postflight are mandatory. Infrastructure failures remain
failures and their raw logs are preserved.

There is no speed floor. The result is additive, fills at most this one
profile-specific cell, cannot replace a historical speed, and does not
automatically launch descendants. A full pass authorizes separately
preregistered TP4 MTP sentinels; it does not authorize them to execute.

Static check:

```bash
experiments/qwen38-27b-b70/scripts/run-20260826-qwen38-official-f01e-autoround-tp4-mtp0-f16-eager-8k-oracle-sentinel-r1.sh --check
```

GPU execution (not performed during packet preparation):

```bash
experiments/qwen38-27b-b70/scripts/run-20260826-qwen38-official-f01e-autoround-tp4-mtp0-f16-eager-8k-oracle-sentinel-r1.sh \
  --execute \
  --ack 'RUN qwen38-official-f01e-autoround-tp4-mtp0-f16-eager-8k-oracle-sentinel-20260826-r1'
```
