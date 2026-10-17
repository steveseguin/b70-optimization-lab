# Coordinator screen: packet59b against packet56

No GPU command was run during preparation. Use the screen v2 crossover tool
present at handoff. X is packet59b (INT8 plus rank0 draft); Y is packet56
(expanded Q6 prefix plus rank1 draft). Both retain the same target, oracle,
23/25 target split and 4K BF16 KV. Acceptance may change.

From the repository root, this CPU-only command verifies both identities and
prints the crossover launch plan without starting a service or touching GPUs:

```bash
P=experiments/own-xpu-runtime/stage2/packet59b-int8-head
S=experiments/own-xpu-runtime/stage2/screen/v2
nice -n 19 taskset -c 8-15,24-31 env OMP_NUM_THREADS=2 python3 -B "$S/ab.py" \
  --x "$P" --x-seal "$P/screen-seal.json" \
  --y experiments/own-xpu-runtime/stage2/packet56-draft-prefix \
  --output "$S/evidence/packet59b-v56-ab-a" --plan
```

The coordinator runs the following **inside a newly admitted `screen-*`
systemd user unit**, at nice0 on supervisor cores 8–15,24–31. The unit must
set `Restart=no`, `SendSIGKILL=no`, `KillMode=process`, `ExitType=cgroup` and
`TimeoutStopSec=infinity`. Preserve the coordinator's approved library path
and closed environment. `REVIEW` must name the current boot's real, reviewed
fault receipt; it is not a waiver for new faults. The output must not exist.
Only the coordinator starts the unit and admits both pairs.

```bash
P=experiments/own-xpu-runtime/stage2/packet59b-int8-head
S=experiments/own-xpu-runtime/stage2/screen/v2
taskset -c 8-15,24-31 env OMP_NUM_THREADS=2 python3 -B "$S/ab.py" \
  --x "$P" --x-seal "$P/screen-seal.json" \
  --y experiments/own-xpu-runtime/stage2/packet56-draft-prefix \
  --output "$S/evidence/packet59b-v56-ab-a" \
  --fault-review "$REVIEW" --authorized-device-window
```

The tool runs X on cards 0+1 while Y uses 2+3, then exchanges the lanes. It
retains its own admission, all-token oracle checks, host-memory monitoring,
fault aborts, graceful drains and teardown separation. Each lane checks the
incident prefix and all twelve 128-token prompts. Its 8–10 minute estimate
is the wrapper's planning estimate, not a measurement for this candidate.
This candidate adds about 0.945 GiB total device allocations versus packet56;
its allocation table and the live census must both pass. Rank0 placement's
larger scratch is already included in that table.

Review per-class speed, every-token target equality, acceptance, draft time
and hit/miss cycles in both lane orders. Also verify each candidate's
`run/packet59b-placement.json`, native rank launch arguments and live census:
the **effective draft rank must be 0**, although the generic screen ABI's
requested rank is 1. Never reuse packet56's draft-proposal oracle for INT8.
A passing screen does not qualify a record; device deterministic repeats and
the complete lane chain are still required before promotion.
