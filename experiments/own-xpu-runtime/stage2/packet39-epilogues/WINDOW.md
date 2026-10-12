# Coordinator K0 / G4 window

Prepared on CPU. **No device program was run for this packet.** These commands
are for the coordinator after assigning one card. Keep the coordinator's
`LD_LIBRARY_PATH` unchanged; the wrapper passes the complete environment to the
native process. `ldd` accepts libraries resolved through ordinary system paths.
The receipt records only runtime-related environment keys, not secret variables.

From `/home/steve/llm-optimizations`, with card 3 assigned (replace both card values
and all matching output names together for another card):

```sh
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B experiments/own-xpu-runtime/stage2/packet39-epilogues/window.py --authorized-device-window --window K0 --card 3 --output experiments/own-xpu-runtime/stage2/packet39-epilogues/build/k0-card3
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B experiments/own-xpu-runtime/stage2/packet39-epilogues/window.py --authorized-device-window --window G4 --card 3 --k0 experiments/own-xpu-runtime/stage2/packet39-epilogues/build/k0-card3/window.json --output experiments/own-xpu-runtime/stage2/packet39-epilogues/build/g4-card3
```

K0 creates executable bundles without submitting kernels. K0 and G4 use
byte-identical copies of one compiled executable; the wrapper passes
`--compile-smoke` for K0. This guarantees that K0 builds the actual G4 device
images, rather than a separately compiled approximation. G4 requires the successful K0 receipt to match this boot, card, binaries
and runtime environment. Both native binary hashes and all sealed source hashes
must match `build-receipt.json`. Output directories must be new, under this
packet's ignored `build/` directory.

G4 compares twelve format/shape cases: paired IQ2_S and IQ3_S expert activation; paired IQ2_S and IQ3_S status-only
checks (activation retained separately);
IQ4_NL expert-down status; Q8_0 HC low activation; Q6_K and Q8_0 shared activation;
Q8_0 shared down/combine; Q6_K split-four attention output/combine; and Q6_K/Q8_0 GDN QKV/convolution. It keeps
the unfused split-four reduction where the runtime uses it. Every case compares
raw GEMV outputs, activation/mixture outputs, all residual streams, both status
buffers and sticky error bytes. Seven scenarios cover finite inputs, invalid
routes, inactive execution, a preexisting sticky error, NaN input, and context
positions at capacity or negative. Convolution history bytes are also compared. The NaN
case checks only fused/unfused byte identity; it is not a new qualification of
the model's nonfinite GEMV policy.

After those checks, each arm receives 200 measurements. Each sample sums the
execution time of every GPU event in its chain. Input restoration and copies
are outside those event intervals. Arms alternate order. Above 8 MB, eight
complete weight banks rotate, with different banks for the control and fused
arm in a pair; no reduced toy bank is timed. Expert banks have 512 experts and
ten routed outputs. Dense Q6/Q8 fixtures use the runtime's expanded byte/scales
layout, not the on-disk packed layout.

`run/summary.json` is sorted by measured milliseconds saved per token. The
format frequencies are from packet29's pinned token plan: IQ2_S 47 / IQ3_S 1;
shared Q8_0 1 / Q6_K 47; GDN Q6_K 35 / Q8_0 1; down, attention and shared combine 48 each; HC low 97
including the final layer. `dispatch-measured.json` keeps packet26's `classes`,
`gemv` and `fusions` vocabulary and adds packet39 fusion keys. It is a one-card
screening recommendation, not an adopted runtime default or a speed verdict.
The wrapper retains the native proposal as `dispatch-provisional.json`, then
filters it using the sealed `assembly-review.json`. Expert activation and
status-only fusion are mutually exclusive for each format: when activation
passes assembly and timing, it takes precedence; otherwise accepted, faster
status-only fusion may be selected. Their timings cover different tails, so
raw chain durations are not compared to each other or added as two savings. Offline-rejected, unknown
or slower classes are absent from the final `fusions` mapping.
`dispatch-selection.json` records every selection or rejection reason. These
new keys require the integration described in `INTEGRATE.md`; the current
packet29 runtime does not understand them automatically. Raw 200-sample arrays
remain in each class JSON. A second fresh window is needed
before any performance verdict.

The wrapper captures its own journal cursor before native contact and ignores
historical fault lines. Only new lines can create `FAULT.json`. A missing library
or other refusal before native contact records failure without a fault latch.
Failures are persisted before graceful stop/teardown. There is no retry and no
hard kill. If SIGTERM does not complete in six minutes, the wrapper records the
live child PID and returns control to the coordinator for recovery.

CPU-only wrapper validation (does not select or open a device):

```sh
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B experiments/own-xpu-runtime/stage2/packet39-epilogues/test_window.py
```

The mock suite covers JSON persistence, preserved `LD_LIBRARY_PATH`, ordinary
system-library resolution, missing-library refusal, historical/new fault lines,
native failure, K0 identity refusal, offline assembly rejection and slower
candidate omission, expert-fusion conflict and status-only fallback (twelve
checks). Temporary mocks are removed afterwards.
