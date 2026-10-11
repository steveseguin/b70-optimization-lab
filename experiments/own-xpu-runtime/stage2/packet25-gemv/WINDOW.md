# Coordinator windows

CPU preparation did not execute a device binary, inspect a device node, or call
Level Zero discovery. Only the coordinator runs the following after admitting
one physical card. Supply `LD_LIBRARY_PATH` in the coordinator environment;
do not source a broad runtime environment with unregistered keys. `--card N`
uses the same unmasked Level Zero GPU index convention as earlier packets.

Rebuild on the CPU if the ignored binaries are absent (one compile job, under
8 GiB address-space limit; no device executable is invoked):

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B experiments/own-xpu-runtime/stage2/packet25-gemv/build.py
```

Replace N with the admitted card number. K0 builds every kernel in the exact
same binary's SYCL input bundle, without dispatching a GEMV. G1 requires that
K0 receipt, the same boot/card/environment/build, and launches two fresh owners.
Use new output paths; there are no retries or resident services.

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B experiments/own-xpu-runtime/stage2/packet25-gemv/window.py --authorized-device-window --window K0 --card N --output experiments/own-xpu-runtime/stage2/packet25-gemv/build/K0-b --seconds 300
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B experiments/own-xpu-runtime/stage2/packet25-gemv/window.py --authorized-device-window --window G1 --card N --k0 experiments/own-xpu-runtime/stage2/packet25-gemv/build/K0-b/window.json --output experiments/own-xpu-runtime/stage2/packet25-gemv/build/G1-b --seconds 1200
```

G1 compares current with the frozen host reference: finite values (including
signed zeros and denormals) and infinities must match exactly; host NaN requires
card NaN with any encoding. Candidates must match current-card bits everywhere.
NaN encoding differences versus host are counted separately; the model's sticky
error rejects all nonfinite values, which are not model outputs. First-eight
mismatch records include full input bits and host/current/candidate output bits.

A failure excludes the candidate across its format; a current failure excludes
the whole format. Remaining fixtures, classes, timings and both fresh owners
continue. A full sequence requiring an excluded current format is skipped and
labeled. Finite gate failures make the final exit nonzero; other numerical gate
failures still exclude arms and set all_gates_passed=false. Safety faults/budgets
still abort. Both owners must agree on exactness/exclusions. All outputs include
FP32 and BF16 gate/up/down bits; nonlinear postprocessing is outside this diagnostic.

`ranked.md` and `ranked.json` are produced automatically after both owners complete, including completed finite-gate failures;
raw execution/sequence records stay under `run/owner1` and `run/owner2`.
An excluded candidate never appears as a timing winner. The full sequence's
candidate selections are in `full-sequence-plan.jsonl`.

The runner checks closed environment keys and priorities, the source/CPU/binary
seals, and `ldd` **before** inspecting or creating a fault latch. Native work runs
in its own systemd user unit, Nice19/idle I/O, Restart=no. The journal watcher
fast-fails on specific fault signatures. It records failure before requesting
one SIGTERM; it never hard-kills or restarts an owner. A stuck drain leaves the
owner/unit for the coordinator. Native failures are saved before queue-wide
wait/free. This packet never changes machine settings or performs recovery.

A passing G1 is not production admission. The coordinator must still check the
real model against its v2 oracle and repeat on a fresh owner, with actual input
classification, memory residency, input/output epilogues and all dependencies.

The old `build/K0` and `build/G1` receipts are preserved as evidence.
K0-b must bind the rebuilt binary; the old K0 cannot authorize G1-b.
