# Embedded-Q8 Q8-KV TP1 MTP route 8K sentinel R1

This bounded screen changes the successful F16 serving tuple only to Q8_0
target and draft KV. It binds the successful F16 MTP1/2/4 full expansion and
the prior embedded-Q8 target-only Q8-KV seven-depth result, then runs fresh
isolated MTP0, MTP1, MTP2, MTP3, and MTP4 lifetimes at exact 8K.

Every speculative arm must reproduce the fresh Q8-KV MTP0 128-token output and
the sealed deterministic target hash, report cache zero, produce exactly one
positive conserved draft row, and shut down cleanly. Candidate failures are
route-local so later arms still run. A control or shared cleanup failure
invalidates all routes.

Passing MTP1-4 routes may receive separately preregistered
0/2/4/8/16/24/32K Q8-KV curves. This sentinel has no graph, site, record,
featured, or protected-speed authority and cannot replace the F16 parent.

Inert check:

```bash
python3 -B experiments/qwen36-27b-mtp-gguf-q4-b70/scripts/run-20260825-qwen36-mtpq8-q8kv-tp1-mtp-route-8k-sentinel-r1.py --check
```

Future create-only launch:

```bash
python3 -B experiments/qwen36-27b-mtp-gguf-q4-b70/scripts/run-20260825-qwen36-mtpq8-q8kv-tp1-mtp-route-8k-sentinel-r1.py \
  --execute \
  --ack 'RUN qwen36-mtpq8-q8kv-tp1-mtp-route-8k-sentinel-20260825-r1'
```

Output root:
`/mnt/fast-ai/bench-results/qwen36-mtpq8-q8kv-tp1-mtp-route-8k-sentinel-20260825-r1`.
