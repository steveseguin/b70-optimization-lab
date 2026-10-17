# Packet47 coordinator windows: physical card 0

CPU preparation launches no device, health probe or service. These commands
belong to the coordinator, after current host/card ownership and health
admission under `docs/local-ops.md`. No model weights are required. Use only
one card, physical card 0. A passing final `seal.json` is mandatory.

Each window is single-attempt. Check `window.json` for passing, completed
teardown before the next command. No retries, automatic restart, reset or
reboot. A return of 75 means a child may remain: inspect its recorded PID and
leave the coordinator responsible for safe drain. The unit settings below
prevent an automatic group hard-kill. Do not add a unit runtime limit.

Use a new campaign suffix instead of overwriting `p47-a`. `P47_REVIEW` is the
actual UTC instant through which the coordinator reviewed this boot's known
faults and required recovery, not an arbitrary current timestamp. All four
windows use the same review instant and closed runtime environment.

```bash
P47=/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet47-qsa-attn
P47_LIBS="${LD_LIBRARY_PATH:?supply installed oneAPI runtime libraries}"
P47_REVIEW="${REVIEWED_THROUGH_UTC:?supply coordinator-reviewed UTC instant}"

systemd-run --user --unit=packet47-e1-p47-a --wait \
  --property=KillMode=process --property=SendSIGKILL=no --property=TimeoutStopSec=90s \
  /usr/bin/bash "$P47/coordinator-exact.sh" "$P47_LIBS" "$P47_REVIEW" "$P47/evidence/p47-a-e1"

systemd-run --user --unit=packet47-e2-p47-a --wait \
  --property=KillMode=process --property=SendSIGKILL=no --property=TimeoutStopSec=90s \
  /usr/bin/bash "$P47/coordinator-exact.sh" "$P47_LIBS" "$P47_REVIEW" "$P47/evidence/p47-a-e2"

systemd-run --user --unit=packet47-t1-p47-a --wait \
  --property=KillMode=process --property=SendSIGKILL=no --property=TimeoutStopSec=90s \
  /usr/bin/bash "$P47/coordinator-timing.sh" "$P47_LIBS" "$P47_REVIEW" "$P47/evidence/p47-a-t1" \
  "$P47/evidence/p47-a-e1/window.json" "$P47/evidence/p47-a-e2/window.json"

systemd-run --user --unit=packet47-t2-p47-a --wait \
  --property=KillMode=process --property=SendSIGKILL=no --property=TimeoutStopSec=90s \
  /usr/bin/bash "$P47/coordinator-timing.sh" "$P47_LIBS" "$P47_REVIEW" "$P47/evidence/p47-a-t2" \
  "$P47/evidence/p47-a-e1/window.json" "$P47/evidence/p47-a-e2/window.json"

nice -n 19 taskset -c 4-15,20-31 python3 -B "$P47/summarize.py" \
  --windows "$P47/evidence/p47-a-t1/window.json" "$P47/evidence/p47-a-t2/window.json" \
  --output "$P47/evidence/p47-a-summary.json"
```

E1/E2 require the complete 316-capture matrix: contexts 1K/2K/4K/8K/32K,
three extra tail contexts, M=1/M=2, two seeds, old/ordered/split32 paths,
immutable input/KV captures, selection/qgate exactness and five control cases.
Their complete comparison identities must match across fresh processes.
The split32 CPU oracle has a new identity. Ordered and current use the old
output oracle. New-vs-old differences are informational and retained; they
never weaken equality with each arm's declared CPU reference.

T1/T2 require both exactness receipts under the same seal, boot, card and
environment. They cover every requested context and both M values, 10 warmup
and 200 measured pairs, alternating arm order. The current M=2 control runs
two sequential row-sliced p30 calls; candidates batch two causally distinct
rows. At M=2, side selection and qgate use the unchanged arithmetic in
batched operator calls; those side timings are not the engine’s sequential
whole-layer dispatch. Every attention stage, including admission and combine, counts in GPU
time. Selection and qgate are measured alongside attention and stay unchanged.
Compilation, fixture staging, validation and copies are outside GPU events.

Both timing owners must meet 3x at 4K separately for M=1 and M=2. Prefer the
order-preserving arm if it meets 5x. A completed timing window may fail the
speed bar; that is a valid negative result. Synthetic repeated operator
fixtures never qualify a realistic-suite or tokens/s claim.

The wrapper reuses the lab's existing journal/memory supervisor read-only.
It requires at least 16 GiB available host memory, preserves an 8 GB remaining
disk floor after its allowance, checks visible foreign Xe clients passively,
and refuses a retained packet47 boot fault/uncertain-owner latch. Permission
hidden clients remain the coordinator's ownership responsibility. A fault or
failed observation saves evidence and asks the owned child to stop once. A
busy child is retained after the grace period; no hard kill occurs.
