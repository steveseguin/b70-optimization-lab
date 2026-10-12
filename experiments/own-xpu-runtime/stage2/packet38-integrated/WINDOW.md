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

The 128-token wrapper amendment changes `build-receipt.json`. **Rerun K0,
K1a, K1b, K2, W0p and KD** with the new `d` output suffix below. Earlier
prerequisites bind the old receipt and cannot admit these suite windows. The
native binary hashes are unchanged; see
[evidence/20261012-suite128-wrapper/verification.json](evidence/20261012-suite128-wrapper/verification.json).

K windows, from the same coordinator library environment:

```bash
nice -n 19 ionice -c 3 env -i PATH=/usr/bin:/bin OMP_NUM_THREADS=2 LD_LIBRARY_PATH="$LD_LIBRARY_PATH" python3 -B "$packet38/window.py" --authorized-device-window --window K0 --card "$packet38_card" --output "$packet38/build/K0d"
nice -n 19 ionice -c 3 env -i PATH=/usr/bin:/bin OMP_NUM_THREADS=2 LD_LIBRARY_PATH="$LD_LIBRARY_PATH" python3 -B "$packet38/window.py" --authorized-device-window --window K1a --card "$packet38_card" --output "$packet38/build/K1ad" --k0 "$packet38/build/K0d/window.json" --dispatch "$packet38/dispatch-p38.json"
nice -n 19 ionice -c 3 env -i PATH=/usr/bin:/bin OMP_NUM_THREADS=2 LD_LIBRARY_PATH="$LD_LIBRARY_PATH" python3 -B "$packet38/window.py" --authorized-device-window --window K1b --card "$packet38_card" --output "$packet38/build/K1bd" --k0 "$packet38/build/K0d/window.json" --k1a "$packet38/build/K1ad/window.json" --dispatch "$packet38/dispatch-p38.json"
nice -n 19 ionice -c 3 env -i PATH=/usr/bin:/bin OMP_NUM_THREADS=2 LD_LIBRARY_PATH="$LD_LIBRARY_PATH" python3 -B "$packet38/window.py" --authorized-device-window --window K2 --card "$packet38_card" --output "$packet38/build/K2d" --k0 "$packet38/build/K0d/window.json" --k1a "$packet38/build/K1ad/window.json" --k1b "$packet38/build/K1bd/window.json" --dispatch "$packet38/dispatch-p38.json"
```

Reusable W command below forwards every prerequisite. Unused prerequisites are
ignored; a file becomes mandatory only at its required stage. Use unique output
names for every attempt. The function performs no launch until called.

```bash
packet38_window() {
  nice -n 0 ionice -c 3 env -i PATH=/usr/bin:/bin OMP_NUM_THREADS=2 LD_LIBRARY_PATH="$LD_LIBRARY_PATH" python3 -B "$packet38/window.py" --authorized-device-window --card "$packet38_card" --input "$packet38/build/input" --oracle "$packet38_oracle" --dispatch "$packet38/build/K2d/run0/dispatch-measured.json" --k0 "$packet38/build/K0d/window.json" --k1a "$packet38/build/K1ad/window.json" --k1b "$packet38/build/K1bd/window.json" --k2 "$packet38/build/K2d/window.json" --w0p "$packet38/build/W0pd/window.json" --kd "$packet38/build/KDd/window.json" "$@"
}
packet38_window --window W0p --output "$packet38/build/W0pd"
nice -n 19 ionice -c 3 env -i PATH=/usr/bin:/bin OMP_NUM_THREADS=2 LD_LIBRARY_PATH="$LD_LIBRARY_PATH" python3 -B "$packet38/window.py" --authorized-device-window --window KD --card "$packet38_card" --output "$packet38/build/KDd" --input "$packet38/build/input" --dispatch "$packet38/build/K2d/run0/dispatch-measured.json" --k0 "$packet38/build/K0d/window.json" --k1a "$packet38/build/K1ad/window.json" --k1b "$packet38/build/K1bd/window.json" --k2 "$packet38/build/K2d/window.json"
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

**Native launch blocker found by the CPU dry-run:** the sealed `main.cpp`
argument guard still requires `a.tokens <= 64` (line 193). It rejects
`--max-new 128` before execution. No native source or binary was changed here.
The following WS128 commands are prepared, but cannot run successfully until a
separate authorized native change removes that guard and qualifies new binaries.
The [wrapper closeout](evidence/20261012-suite128-wrapper/CLOSEOUT.md) records
the guard refusal and unchanged binary hashes. The 128-token end-to-end proof
below uses explicitly mocked ranks; the 64-token
path additionally runs the unchanged native host mini model.

For the 128-token suite, use these after that native qualification and new `d` prerequisites. Each prompt
runs exactly once (`--repeat 1`), as required by the fixed realistic final gate.
Use fresh output names WS128 and WS128s; these commands are for the coordinator,
and were not run on devices during this CPU-only wrapper change.

```bash
packet38_window --window WS --controller native --suite-manifest experiments/own-xpu-runtime/stage2/suite-inputs-20261012-cap128/suite-manifest.json --repeat 1 --output "$packet38/build/WS128"
packet38_window --window WSs --controller native --suite-manifest experiments/own-xpu-runtime/stage2/suite-inputs-20261012-cap128/suite-manifest.json --repeat 1 --output "$packet38/build/WS128s"
```

The manifest cap must be 64 or 128, and every prompt plus its cap must fit in
256 tokens. All emitted tokens are checked exactly against the matching oracle.
The binary retains fixture steps 1–8 only. A cap128 receipt explicitly records
`fixture_steps_checked: [1,2,3,4,5,6,7,8]` and
`fixture_steps_not_retained_by_this_binary: [97,98,99,100,101,102,103,104]`.
No check of the binary's late fixtures is claimed.

`decode_tok_s` keeps the 63 intervals ending at tokens 2–64:
`63 / (t64 - t1)`. `submission_tok_s` is the rate for the **99 inter-token
intervals between generated-token timestamps 1 and 100 after TTFT**:
`99 / (t100 - t1)`, with monotonic timestamps in seconds. It is null with fewer
than 100 events. Receipts retain every completion timestamp, TTFT from request
start (prompt processing plus first token), prompt/output counts, whole-request
wall rate, early termination and guesses/hits. Both suite figures report the
median across requests and the median of per-prompt medians; these are not
prompt-class medians or an assertion that all external promotion gates pass.
CPU runs remain explicitly unqualified for speed claims.

CPU-only verification (mini ranks, no rebuild, no real-model execution):

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B "$packet38/test_suite_cap128.py"
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
