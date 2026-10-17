# Coordinator runbook: packet46, card 0 only

Preparation runs no GPU command, discovery or health probe. These commands
are for the device coordinator after it releases the FP8 comparison and
establishes current host/device ownership and health under `docs/local-ops.md`.
The packet does not authorize a restart, reset or reboot. All four device
windows run **one card, physical card 0**. They generate synthetic fixtures;
no model-weight path is accepted.

The final CPU seal, device build and CPU gates must exist and verify before
any command below can launch. Current status and hashes are in `seal.json`
and the October 17 packet46 note. A missing or failed seal is a refusal, not
an invitation to use an unsealed override. No device correctness or speed
claim follows from a passing CPU seal.

Set `P46_LIBS` to the installed compiler/runtime library path. Set `P46_REVIEW`
to the actual UTC instant through which the coordinator has reviewed this
boot's previous faults and completed required recovery. It is not simply the
current time. Both exactness and timing runs must use the same review instant.
The wrapper preserves the full boot journal and checks every line after that
review. New faults invalidate the run and write a retained boot latch.

Run from `/home/steve/llm-optimizations`. Choose a new suffix for this campaign;
existing directories and systemd unit names must never be overwritten. This
example uses `p46-a`. Set these shell variables before the command files:

```bash
P46=/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet46-specialized
P46_LIBS="${LD_LIBRARY_PATH:?supply installed oneAPI runtime libraries}"
P46_REVIEW="${REVIEWED_THROUGH_UTC:?supply the coordinator-reviewed UTC instant}"
```

The user-unit settings are deliberate: `KillMode=process`, `SendSIGKILL=no`
and no `RuntimeMaxSec` keep systemd from hard-killing a retained GPU child.
If a wrapper returns 75, its child remains the coordinator's responsibility.
Inspect its receipt/PID and preserve evidence; do not launch the next window.
Never use a default control-group kill or an automatic restart policy here.

Each command is a separate single-attempt window. Check its passing
`window.json` and safe teardown before advancing. The next command does not
retry a failed previous one.

```bash
systemd-run --user --unit=packet46-e1-p46-a --wait \
  --property=KillMode=process --property=SendSIGKILL=no --property=TimeoutStopSec=90s \
  /usr/bin/bash "$P46/coordinator-exact.sh" "$P46_LIBS" "$P46_REVIEW" "$P46/build/p46-a-e1"

systemd-run --user --unit=packet46-e2-p46-a --wait \
  --property=KillMode=process --property=SendSIGKILL=no --property=TimeoutStopSec=90s \
  /usr/bin/bash "$P46/coordinator-exact.sh" "$P46_LIBS" "$P46_REVIEW" "$P46/build/p46-a-e2"

systemd-run --user --unit=packet46-t1-p46-a --wait \
  --property=KillMode=process --property=SendSIGKILL=no --property=TimeoutStopSec=90s \
  /usr/bin/bash "$P46/coordinator-timing.sh" "$P46_LIBS" "$P46_REVIEW" "$P46/build/p46-a-t1" \
  "$P46/build/p46-a-e1/window.json" "$P46/build/p46-a-e2/window.json"

systemd-run --user --unit=packet46-t2-p46-a --wait \
  --property=KillMode=process --property=SendSIGKILL=no --property=TimeoutStopSec=90s \
  /usr/bin/bash "$P46/coordinator-timing.sh" "$P46_LIBS" "$P46_REVIEW" "$P46/build/p46-a-t2" \
  "$P46/build/p46-a-e1/window.json" "$P46/build/p46-a-e2/window.json"

nice -n 19 taskset -c 4-15,20-31 python3 -B "$P46/summarize.py" \
  --windows "$P46/build/p46-a-t1/window.json" "$P46/build/p46-a-t2/window.json" \
  --output "$P46/build/p46-a-summary.json"
```

E1 and E2 require the same full ordered intermediate/state capture manifest,
changing expert sets and identical complete output/state identities across
fresh processes. T1 and T2 additionally require both exactness companions,
matching source/binary/environment/boot identity, 4K populated attention,
the exact 35/41 baseline launch census and complete unique per-class GPU events.
Compilation/JIT, staging, state restoration and comparison are outside GPU
timing. Both timing owners must save at least 80 microseconds per layer to
make that layer a later integration candidate.

The wrapper admits only a closed environment, 16 GiB of available host memory,
8 GB of remaining output-disk space and no visible foreign Xe clients.
The passive `/proc` check cannot inspect another user's private clients;
the coordinator remains responsible for exclusive ownership. It never opens
a DRM node, starts a health probe, changes a selector or uses XPU-SMI itself.
The native program constructs only the authorized card-0 owner.

During execution the inherited packet34 supervisor polls the journal and
process-tree anonymous memory. At a failure it saves evidence, sends at most
one cooperative SIGTERM and waits up to 60 seconds for a safe drain. A busy
owner is retained, never hard-killed. Success requires a normal native exit,
all raw checks, safe teardown and a clean five-second journal postflight.
Full host/four-card postflight ownership remains with the coordinator.

The raw results are `run/receipt.json`, `run/comparisons.jsonl`,
`run/iterations.jsonl` and the capture manifest. `window.json` binds them to
the seal; timing `summary.json` reports the measured bar separately from
whether the window completed correctly. Do not turn this synthetic per-layer
screen into tokens/s, a full engine quality pass or a public speed claim.
