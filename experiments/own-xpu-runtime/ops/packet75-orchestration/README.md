# Packet75 preparation — never launches

Run with nice19, CPUs8-15,24-31, Python-B and closed stdin:

```bash
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/ops/packet75-orchestration/orchestrate.py </dev/null
```

The helper imports each packet's own compare and winner logic in a separate
process. All A screens and all three B confirmation screens must be13/13 exact.
Packet73 compares against the two-control mean; packet74 requires beating both
controls. Only the A winner has a B confirmation. Other A arms do not inherit
that confirmation. Packet74 combined means packed head+dense; packet73 combined
means HC-wide+experts2-b. Independently confirmed packet winners compose;
either packet can win alone. Missing or invalid evidence leaves readiness false.

After evidence selection, the helper fast-reseals, checks the chain seal,
inputs, storage, every real window plan and queue plan. `ready.json` includes
the exact systemd command for the coordinator. `device-entry.sh` rejects stale,
changed or incomplete readiness; existing runtime admission owns GPU checks.
No unit or background waiter is started by this helper.
