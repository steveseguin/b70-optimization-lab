# Packet49 coordinator chain: cards 0+1, 4K, split23, draft rank1

These commands are for the device coordinator. CPU preparation does not run
any of them. The coordinator supplies current device admission and an existing
approved `LD_LIBRARY_PATH`. Run inside the coordinator's admitted nice-0 user
unit, pinned to cores **0–3,16–19**, as for SPEED6. The wrappers preserve
`OMP_NUM_THREADS=2`, native controller, full BF16 caches and the memory guards.
No one-card result is established by this two-card integration.

The serial queue follows packet45 `queue-runner4.py`: one launcher at a time,
90 seconds after K windows and 305 seconds after W windows, no retries, and
stop after any failed window. It also stops on a new specific GPU fault
signature. The existing window owns its deadline and graceful teardown.
The queue changes no other process's affinity and launches no companions.
Window success requires exit zero **and** a passing, qualifying device receipt.
A `STOP` file requires coordinator review; rerunning never overwrites a window.

## Before the CPU oracle completes

The **K0 → K1a → K1b → K2 → W0p** phase needs no new full-model oracle.
K1a and K1b include the actual integrated split32 bridge's M=1/M=2 checks
against its CPU reference. K2 retains the registered old kernel-selection
comparisons; production QSA attention is explicitly overridden by split32.
W0p is the oracle-free two-owner transport canary. These windows require the
finished packet49 build/CPU seal and normal coordinator admission.

From the repository root, choose one new chain directory and retain it for
both phases:

```bash
P=experiments/own-xpu-runtime/stage2/packet49-integrate
OUT=/home/steve/own-xpu-runtime-results/packet49-integrate/device-cards01-a
bash "$P/coordinator_windows.sh" --phase early --output-root "$OUT"
```

Inspect exact per-window argv without touching a device:

```bash
nice -n 19 taskset -c 4-15,20-31 python3 -B "$P/queue_runner.py" \
  --phase early --output-root "$OUT" --plan
```

## Once the oracle is complete

The coordinator checks the status command, which validates the completed
output rather than trusting a service's exit status alone:

```bash
nice -n 19 taskset -c 4-15,20-31 python3 -B "$P/oracle/oracle_job.py" \
  status --require-complete
bash "$P/coordinator_windows.sh" --phase model --output-root "$OUT" --wait-oracle
```

This runs **KD → W2m → WS → WSs → WS128x → WS128**. KD is conservatively in
this phase because it needs the new captured target streams/draft-reference
binding. W2m uses the first prompt's new 64-token prefix and fixtures. The suite
windows use `oracle/results/suite-manifest.json`, with all twelve registered
prompts and 128 outputs each. WS128x retains steps1–8 and97–104; WS128 retains
no layer fixtures and requires that exactness companion. Every window binds
its boot, environment, source/build seal, topology, dispatch and prerequisites.

The complete unattended sequence can instead be queued once:

```bash
bash "$P/coordinator_windows.sh" --phase all --output-root "$OUT" --wait-oracle
```

Use either the combined command or the split phases, never both on the same
output. Waiting occurs before the next launcher, without holding device owners.
The queue also preserves the last stop time across the split phases. The
oracle's separate completion receipt does not change the early-window build
seal. If the boot changes, inherited prerequisite checks refuse the old chain.

## Outputs and scope

Outputs, logs, `queue-state.json`, `running.json`, failures and STOP reside
under `$OUT`. `window.json` is the authority for each completed window;
`queue-early-complete.json` and `queue-model-complete.json` summarize phases.
No timing result exists until the coordinator runs this chain. The historic
39.422 tok/s SPEED6 record remains intact. This 128-token suite is the matching
historical comparison scope, not the separate 512-token publication gate.

No packet48 GEMV is production-enabled yet. The separate packet48b matched
controls must establish its per-class choices before a new integration/reseal.
