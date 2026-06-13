# Qwen3.6 Replay-Digest Layer-20 Hotset Dry Run 20260612dv

Purpose:

- Convert the 20260612dq replay digest into the route-count JSONL schema used
  by the existing grouped-GEMM hotset harness.
- Test layer `20`, the strongest decode top64 layer in the current top128
  plan, without stopping the accepted backend or loading extra XPU weights.

Converter:

```bash
python3 scripts/qwen36-replay-digest-to-route-jsonl.py \
  'data/qwen36-replay-digest-replay-digest-hot-20260612dq-*.jsonl' \
  --layers 20 \
  --num-rows 1 \
  --local-ranks 0 \
  --out data/qwen36-replay-digest-hot-decode1-layer20-rank0-routes-20260612dv.jsonl \
  --metadata-out data/qwen36-replay-digest-hot-decode1-layer20-rank0-routes-20260612dv.json
```

Conversion result:

- Emitted `347` rank-0 decode rows for layer `20`.
- Invalid rows: `0`.
- Count mismatches: `0`.
- Output route file:
  `data/qwen36-replay-digest-hot-decode1-layer20-rank0-routes-20260612dv.jsonl`.

Dry-run artifacts:

- `data/qwen36-replay-digest-hotset-top64-layer20-rank0-dryrun-20260612dv.json`
- `data/qwen36-replay-digest-hotset-top128-layer20-rank0-dryrun-20260612dv.json`

Coverage on the full 347-row rank-0 layer-20 decode route file:

| hotset | mean coverage | median | min | fully hot rows | fully hot fraction | cold rows histogram |
|---|---:|---:|---:|---:|---:|---|
| top64 | `0.7788` | `0.7500` | `0.0000` | `84/347` | `0.2421` | `{0:84,1:89,2:74,3:52,4:31,5:10,6:4,7:1,8:2}` |
| top128 | `0.9564` | `1.0000` | `0.5000` | `251/347` | `0.7233` | `{0:251,1:77,2:15,3:2,4:2}` |

Interpretation:

- The new converter is usable for replay-digest-to-harness benchmarking.
- Top64 is meaningful but still requires cold fallback for about `75.8%` of
  layer-20 decode route rows. That is fine only if the implementation is a
  single-dispatch hot/cold kernel, not a two-launch split.
- Top128 looks much more attractive for layer 20: most route rows become
  entirely hot, and the remaining cold tail is usually one or two expert rows.
- The accepted backend currently reports about `32653 MiB` used on XPU 0, so a
  live grouped-GEMM microbench was intentionally not run in this pass. A real
  timing run should happen in an isolated window or after stopping the backend.

Next:

1. Add the same converter/dry-run pass for layers `8,9,13,16,19,21,38` to
   confirm whether top128 keeps this high fully-hot fraction across the
   threshold layer set.
2. Build or prototype a one-dispatch hotset/cold fallback layerlet. Prior
   split-launch measurements remain a warning: coverage does not help if cold
   fallback pays another full launch.
3. Use the Gemma challenge lesson here: store negative timing attempts too,
   especially when a tempting speed path loses to scheduler or launch overhead.
