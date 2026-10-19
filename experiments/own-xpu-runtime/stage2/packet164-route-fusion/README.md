# Packet164: route-fusion CPU decision

The saved clocks do **not establish 0.4 ms/half of removable latency**. The
0.792448 ms route class already consists of 24 single-kernel calls, containing
normalization, top-k, descriptor publication and shared activation. It is not
four separately timed stages. No device implementation is selected today.

At the requested 20% transfer assumption, deleting the entire route class
would give a **+1.025% one-card sensitivity**; deleting both route and the
entire fused router class gives **+1.729%**. Neither is a performance forecast.
The corresponding impossible full-removal ceilings are +5.343% and +9.291%.
Because those raw ceilings exceed +2%, the requested
[conditional one-card build brief](briefs/onecard.md) is retained. It supplies
no readiness or device authorization.

[Analysis](ANALYSIS.md), [conditional synchronization design](DESIGN.md),
[prior-work audit](PRIOR.md), [CPU evidence](evidence/cpu.json),
[closeout](CLOSEOUT.md), [do not repeat](DO-NOT-REPEAT.md).

Reproduce from the repository root, stdin `/dev/null`:

```sh
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/stage2/packet164-route-fusion/analyze.py </dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/stage2/packet164-route-fusion/cpu_gate.py </dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B -m unittest discover -s experiments/own-xpu-runtime/stage2/packet164-route-fusion -p test_analyze.py </dev/null
```

`capture.py` originally retained existing receipts and searched every available
repository DO-NOT-REPEAT plus own-runtime notes. Analysis uses those retained,
hash-checked compressed inputs; rerunning capture is unnecessary and would
refresh the audit census against today's files. See [retention](RETENTION.md).
No GGUF, model payload, full-shape allocation, GPU, service, sudo, queue or
host setting was accessed. Existing packet trees, shared screen and ops are
unchanged. CURRENT.md was already dirty and was left alone: device ownership
and live state did not change. All new work is this packet and its work note.
