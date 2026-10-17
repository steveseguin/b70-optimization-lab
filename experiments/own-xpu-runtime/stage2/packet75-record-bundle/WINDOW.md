# Packet75 coordinator handoff

CPU preparation only; no launch performed. Run the helper after the packet73
and packet74 A grids and best-of-A B confirmations finish:

```bash
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/ops/packet75-orchestration/orchestrate.py </dev/null
```

It emits `ready.json` with the exact command. Launch only that verified command.
All windows use the shared hash-pinned v4 lane-admission code. The chain holds
the whole host during timing windows. Every gap is90seconds.

The prepared baseline is dense=production, HC=production, experts=wide64,
with draft-HC, batched rollback, 24/24 layers, rank1 draft and full BF16 KV.
The helper chooses improvements only from both-lane exact confirmations.
No packet70/73/74 receipt can be imported into this merged binary.
