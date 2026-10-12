# Coordinator windows (prepared, not executed here)

Run from the repository root. `--card N` is the first of an adjacent pair
(N=0,1,2). All W commands must start from a nice-0 parent. A taskset prefix
is allowed; the wrapper/ranks retain that affinity. Supply only the coordinator's
LD_LIBRARY_PATH, forwarded unchanged; no runtime selector/cache/precision
variables. HOME is selected by the wrapper under packet-local build. All
commands use the sealed device binaries; CPU preparation must never run them.

Shell setup (substitute the admitted first card):

```bash
set -e
packet38=experiments/own-xpu-runtime/stage2/packet38-integrated
packet38_card=0
packet38_oracle=experiments/qwen38-flash-next-ud-iq3xxs-b70/packet3-runtime-oracle/runs/arithmetic-v2-detmath-20261011/incident-retrospective
packet38_suite=experiments/own-xpu-runtime/stage2/suite-inputs-20261012/suite-manifest.json
```

K windows, from the same coordinator library environment:

```bash
nice -n 19 ionice -c 3 env -i PATH=/usr/bin:/bin OMP_NUM_THREADS=2 LD_LIBRARY_PATH="$LD_LIBRARY_PATH" python3 -B "$packet38/window.py" --authorized-device-window --window K0 --card "$packet38_card" --output "$packet38/build/K0"
nice -n 19 ionice -c 3 env -i PATH=/usr/bin:/bin OMP_NUM_THREADS=2 LD_LIBRARY_PATH="$LD_LIBRARY_PATH" python3 -B "$packet38/window.py" --authorized-device-window --window K1a --card "$packet38_card" --output "$packet38/build/K1a" --k0 "$packet38/build/K0/window.json" --dispatch "$packet38/dispatch-p38.json"
nice -n 19 ionice -c 3 env -i PATH=/usr/bin:/bin OMP_NUM_THREADS=2 LD_LIBRARY_PATH="$LD_LIBRARY_PATH" python3 -B "$packet38/window.py" --authorized-device-window --window K1b --card "$packet38_card" --output "$packet38/build/K1b" --k0 "$packet38/build/K0/window.json" --k1a "$packet38/build/K1a/window.json" --dispatch "$packet38/dispatch-p38.json"
nice -n 19 ionice -c 3 env -i PATH=/usr/bin:/bin OMP_NUM_THREADS=2 LD_LIBRARY_PATH="$LD_LIBRARY_PATH" python3 -B "$packet38/window.py" --authorized-device-window --window K2 --card "$packet38_card" --output "$packet38/build/K2" --k0 "$packet38/build/K0/window.json" --k1a "$packet38/build/K1a/window.json" --k1b "$packet38/build/K1b/window.json" --dispatch "$packet38/dispatch-p38.json"
```

Reusable W command below forwards every prerequisite. Unused prerequisites are
ignored; a file becomes mandatory only at its required stage. Use unique output
names for every attempt. The function performs no launch until called.

```bash
packet38_window() {
  nice -n 0 ionice -c 3 env -i PATH=/usr/bin:/bin OMP_NUM_THREADS=2 LD_LIBRARY_PATH="$LD_LIBRARY_PATH" python3 -B "$packet38/window.py" --authorized-device-window --card "$packet38_card" --input "$packet38/build/input" --oracle "$packet38_oracle" --dispatch "$packet38/build/K2/run0/dispatch-measured.json" --k0 "$packet38/build/K0/window.json" --k1a "$packet38/build/K1a/window.json" --k1b "$packet38/build/K1b/window.json" --k2 "$packet38/build/K2/window.json" --w0p "$packet38/build/W0p/window.json" --kd "$packet38/build/KD/window.json" "$@"
}
packet38_window --window W0p --output "$packet38/build/W0p"
nice -n 19 ionice -c 3 env -i PATH=/usr/bin:/bin OMP_NUM_THREADS=2 LD_LIBRARY_PATH="$LD_LIBRARY_PATH" python3 -B "$packet38/window.py" --authorized-device-window --window KD --card "$packet38_card" --output "$packet38/build/KD" --input "$packet38/build/input" --dispatch "$packet38/build/K2/run0/dispatch-measured.json" --k0 "$packet38/build/K0/window.json" --k1a "$packet38/build/K1a/window.json" --k1b "$packet38/build/K1b/window.json" --k2 "$packet38/build/K2/window.json"
packet38_window --window W2s --controller python --output "$packet38/build/W2s-python"
packet38_window --window W2s --controller native --output "$packet38/build/W2s-native"
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B "$packet38/retain_window.py" --pair W2s
packet38_window --window W2m --controller python --output "$packet38/build/W2m-python"
packet38_window --window W2m --controller native --output "$packet38/build/W2m-native"
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B "$packet38/retain_window.py" --pair W2m
packet38_window --window W2d --controller python --output "$packet38/build/W2d-python"
packet38_window --window W2d --controller native --output "$packet38/build/W2d-native"
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B "$packet38/retain_window.py" --pair W2d
packet38_window --window W2n --controller python --output "$packet38/build/W2n-python"
packet38_window --window W2n --controller native --output "$packet38/build/W2n-native"
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B "$packet38/retain_window.py" --pair W2n
packet38_window --window W2x --controller python --output "$packet38/build/W2x-python"
packet38_window --window W2x --controller native --output "$packet38/build/W2x-native"
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B "$packet38/retain_window.py" --pair W2x
packet38_window --window W2mc --controller python --output "$packet38/build/W2mc-python"
packet38_window --window W2mc --controller native --output "$packet38/build/W2mc-native"
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B "$packet38/retain_window.py" --pair W2mc
packet38_window --window WS --controller native --suite-manifest "$packet38_suite" --repeat 2 --output "$packet38/build/WS"
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B "$packet38/retain_window.py" --suite WS
packet38_window --window WSs --controller native --suite-manifest "$packet38_suite" --repeat 2 --output "$packet38/build/WSs"
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B "$packet38/retain_window.py" --suite WSs
```

W2s/WSs use draft none; W2m/W2mc/WS use MTP. W2n uses prompt-local n-grams. W2x is an all-miss oracle-derived diagnostic.
W2d is an all-hit oracle-fed
diagnostic, never a speed claim. W2mc is profiling, including draft classes.
WS label: **official draft head, draft-only 8-bit requantisation, output identical
to sequential decode**. That label describes the verification contract, not an
unrun device pass. The sealed suite speed remains pending until every requested
oracle comparison passes; incomplete manifests are explicitly incomplete.

K0 builds device kernel bundles and has no host-only execution equivalent. CPU
receipt dryruns test its schema/refusal path only; coordinator K0 remains mandatory.
K1a/b use fresh owners; KD uses two fresh rank1 owners. Keep all receipts before
teardown and preserve retained ownership on a fault. No automatic retry.

Run the sequence with shell error checking (`set -e`) so a failed window or
comparison stops it. After each pair, `retain_window.py` compares tokens,
guesses, hit/miss events, target/draft final states and fixture hashes, then
archives and verifies all text/nested compressed evidence and every raw-file
hash before deleting that pair's scratch. Its parity/retention receipt lives
under `evidence/`. No speed verdict follows from one pair. Failed windows are
never deleted by this helper. K0/K1/K2/W0p/KD prerequisites remain intact.
Suite windows are likewise archived before the next one, keeping the ignored
build tree below 3 GB. Use unique output/retention names for a new campaign;
the listed names describe the first sealed campaign only.

`dispatch-p38.json` is the concrete unmeasured candidate map: p33 dense/expert
kernels, packet30 SG32 attention, packet30 HC gates/shared-down and small HC/FFN
fusions. K1 executes every registered alternative, including score_softmax; K2
chooses `dispatch-measured.json` only from exact qualified measurements.
