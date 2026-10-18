# Coordinator cost probe: sealed and pushed

CPU seal and lane-B plan pass. Six small synthetic target rows (sequential
M=1/2/3), before/after every discarded row, and fresh repeats agree with the
frozen packet64 source. No device execution or CPU model generation occurred.
The host and device builds use packet64's unchanged numerical objects.

The coordinator may run this now, while prototype CPU work continues:

```bash
P=experiments/own-xpu-runtime/stage2/packet68-mtp-depth2
bash "$P/coordinator_probe.sh" "$FAULT_REVIEW"
```

Run inside the coordinator's admitted `screen-*` systemd unit, with its
approved `P49_LDP`. The frozen lane-B wrapper owns masks, fault checks, lease,
all thirteen exact requests, graceful teardown and shared drain spacing.
Expected active time: about five minutes, unmeasured. Watchdog: 3600 seconds.
This uses the wrapper's admitted 23/25 placement, not the design's eventual
24/24 comparison. It is a discarded extra rank0 row, not an M=3 verifier.
No live probe was started by this preparation.

The extra row consumes the latest actual input token at the next hypothetical
position and uses that request's real recurrent/KV state and actual routes.
It is deliberately discarded. Sampling is fixed at generated positions
8, 16 and 32, including incident64, with no prompt selection. Row-plus-snapshot,
device row and exact restore time are logged separately. Snapshot overhead
is included in the first field; it is not independently isolated.

After a successful screen:

```bash
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/analyze_probe.py" \
 experiments/own-xpu-runtime/stage2/screen/v3-packet64-lanes/evidence/packet68-cost-B-01 \
 > "$P/evidence/device-cost.json" </dev/null
```

The root engine/source/build/seal is now frozen within packet68. The prototype
will use separate source overrides, build outputs and seals in this packet.
The record remains 51.033041 tok/s; all new speed and device-quality claims
are pending. This probe cannot fill in the missing batched-verifier cost.
