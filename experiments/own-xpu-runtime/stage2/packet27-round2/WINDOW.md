# Packet 27 coordinator windows

No device ran during preparation. No speed is claimed. These commands are for
the coordinator, run explicitly one at a time in the authorized systemd user
unit. Run from `/home/steve/llm-optimizations`. The coordinator supplies
`LD_LIBRARY_PATH`; no environment workaround or driver discovery is added here.
Every output directory below must be new. Change the run suffix consistently
when repeating a campaign; retain prior receipts and evidence.

`--card N` is the physical index. The executable examples use `--card 0`:
K0/W0/W2/W2m/W2c cover cards 0+1; K1a/K1b/K2 use card 0. For another adjacent pair,
replace every card index consistently. K0 must cover every card used later.

```bash
P=experiments/own-xpu-runtime/stage2/packet27-round2
ORACLE=experiments/qwen38-flash-next-ud-iq3xxs-b70/packet3-runtime-oracle/runs/arithmetic-v2-detmath-20261011/incident-retrospective
```

K0 compiles every linked device kernel image on the two requested cards, without
kernel execution or explicit device allocation. It binds source/binary hashes,
boot and environment for subsequent windows.

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B "$P/window.py" --authorized-device-window --window K0 --card 0 --native-nice 19 --seconds 600 --output "$P/build/k0-r27"
```

K1a and K1b check each new non-GEMV, large-GEMV alternative and concrete small
GEMV tuple against the unchanged arithmetic reference and incumbent output.
Each process owns four fixture backends sequentially, with safe teardown between
them. K1b must be a fresh process and binds K1a. Both use the same candidate map
and must match the sealed CPU fixture bytes. Large-GEMV alternatives are always
enumerated; the dispatch map also enables the new non-GEMV and schedule paths.

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B "$P/window.py" --authorized-device-window --window K1a --card 0 --native-nice 19 --seconds 10800 --k0 "$P/build/k0-r27/window.json" --dispatch "$P/dispatch-all-new.json" --output "$P/build/k1a-r27"
```

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B "$P/window.py" --authorized-device-window --window K1b --card 0 --native-nice 19 --seconds 10800 --k0 "$P/build/k0-r27/window.json" --k1a "$P/build/k1a-r27/window.json" --dispatch "$P/dispatch-all-new.json" --output "$P/build/k1b-r27"
```

K2 times the actual packet 26 incumbent against every candidate on one card at
model decode shapes and formats. It takes 200 repetitions per comparison and
reports byte equality, kernel identity, median/p90 event times and summed-stage
microseconds. GEMV and tuple outputs are checked at the first and last timing
repetition rather than copied back after every launch. Failed candidates are
reported, excluded and followed by the remaining candidates. Incumbent failures
still prevent admission.

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B "$P/window.py" --authorized-device-window --window K2 --card 0 --native-nice 19 --seconds 10800 --k0 "$P/build/k0-r27/window.json" --k1a "$P/build/k1a-r27/window.json" --k1b "$P/build/k1b-r27/window.json" --dispatch "$P/dispatch-all-new.json" --output "$P/build/k2-r27"
```

A candidate enters `build/k2-r27/run/dispatch-measured.json` only when exact and
its median is strictly below 0.9 times the measured incumbent. Every format in
a class must clear the threshold separately; one winning format cannot hide a
regression. Small tuples compete against the sum of their members. Compound
fusions have their own measured entries, never inferred from individual wins.
Invalid timing rows and affected repetition sums are excluded and counted;
more than 1% invalid event rows, missing unexcluded coverage, source changes,
unsafe teardown or an over-budget submission prevents admission. Candidate
failures remain in the receipt even when another candidate qualifies.

W0 is the retained two-card canary through this packet's native model binary.
It checks 100 round trips and 1,000 chained kernels per card, output bytes,
queue ownership, tiny memory use and safe teardown.

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B "$P/window.py" --authorized-device-window --window W0 --card 0 --native-nice 19 --seconds 600 --k0 "$P/build/k0-r27/window.json" --output "$P/build/w0-r27"
```

W2 is the control using packet 26's measured selection, including its qualified
non-GEMV choices and R5 GEMVs. Its measured predecessor was about 17.85 tok/s;
that value is a reproducibility target, not an assumed result. It uses two
resident cards, 64 generated tokens, token timing without profiling, and eight
retained layer-fixture steps. No custom dispatch argument is supplied.

W2, W2m and W2c must start from a nice-0 coordinator. Launching a wrapper at nice
19 and merely requesting `--native-nice 0` cannot raise its priority. The native
binary now verifies the wrapper's stated priority rather than always requiring
19. Receipts record wrapper/native priorities; helpers remain nice 19.

```bash
nice -n 0 ionice -c 3 env OMP_NUM_THREADS=2 python -B "$P/window.py" --authorized-device-window --window W2 --card 0 --native-nice 0 --seconds 10800 --k0 "$P/build/k0-r27/window.json" --w0 "$P/build/w0-r27/window.json" --input "$P/build/input" --oracle "$ORACLE" --output "$P/build/w2-r27"
```

W2m substitutes only the hash-bound K2 measured selection. It requires the
matching K1a/K1b/K2 and W0 receipts, same boot and same binary set.

```bash
nice -n 0 ionice -c 3 env OMP_NUM_THREADS=2 python -B "$P/window.py" --authorized-device-window --window W2m --card 0 --native-nice 0 --seconds 10800 --k0 "$P/build/k0-r27/window.json" --w0 "$P/build/w0-r27/window.json" --k1a "$P/build/k1a-r27/window.json" --k1b "$P/build/k1b-r27/window.json" --k2 "$P/build/k2-r27/window.json" --dispatch "$P/build/k2-r27/run/dispatch-measured.json" --input "$P/build/input" --oracle "$ORACLE" --output "$P/build/w2m-r27"
```

W2c uses exactly W2m's selection and enables per-class profiling. Its execution
sums, issue time and waits are diagnostic; W2c is not a decode-speed result.

```bash
nice -n 0 ionice -c 3 env OMP_NUM_THREADS=2 python -B "$P/window.py" --authorized-device-window --window W2c --card 0 --native-nice 0 --seconds 10800 --k0 "$P/build/k0-r27/window.json" --w0 "$P/build/w0-r27/window.json" --k1a "$P/build/k1a-r27/window.json" --k1b "$P/build/k1b-r27/window.json" --k2 "$P/build/k2-r27/window.json" --dispatch "$P/build/k2-r27/run/dispatch-measured.json" --input "$P/build/input" --oracle "$ORACLE" --output "$P/build/w2c-r27"
```

Every model window compares retained layer bytes and generated tokens directly
against the v2 CPU oracle, with no tolerance. The decode rate uses tokens 2–64,
63 intervals over their complete wall span. This fixed-prompt development window
is not the realistic final benchmark suite and cannot become a public headline.

Before native startup, the wrapper checks source/binary/dispatch/model/oracle
hashes, environment, library resolution, input identity and memory admission.
Kernel argument guards remain enabled. Expected duration is reporting only;
[DEADLINES.md](DEADLINES.md) distinguishes watchdog, submission and drain bounds.
Native failures are written before teardown. A GPU fault latches the boot and
requests one graceful stop; there is no retry, hard kill or reset. A child that
cannot finish bounded draining is retained for the coordinator. Do not launch
another window after a fault without the coordinator's recovery process.
