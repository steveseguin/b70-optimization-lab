# Packet 26 prepared device windows

No device ran during preparation. No speed is claimed. The coordinator alone
admits and runs these commands in an approved systemd user unit. They never queue
another window. Run from `/home/steve/llm-optimizations`; the coordinator supplies
`LD_LIBRARY_PATH`. Each command sets idle CPU/I/O priority and two threads.

`--card` is a physical index. Examples below use cards 0+1; the one-card fixture
and timing windows use card 0. To use another adjacent pair, change every `--card`
consistently. K0 must cover every card used later. No wrapper discovery probe,
model server, sudo or host settings change is part of admission.

```bash
P=experiments/own-xpu-runtime/stage2/packet26-specialised
ORACLE=experiments/qwen38-flash-next-ud-iq3xxs-b70/packet3-runtime-oracle/runs/arithmetic-v2-detmath-20261011/incident-retrospective
```

K0 builds every linked kernel image on both requested cards, without queue
creation or kernel execution. It binds the complete device-binary set, source
hashes, boot and recorded environment for all following windows.

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B "$P/window.py" --authorized-device-window --window K0 --card 0 --native-nice 19 --seconds 600 --output "$P/build/k0"
```

K1a and K1b run all new kernels against packet 18 and the reference core. Each
must cover the 72 original fixtures plus odd lengths, ties and NaN routes. The
bytes must also match the sealed CPU fixture output. Current coverage is 92
non-GEMV fixtures, 44 actual adapter cases and 136 GEMV arm checks (17 workloads
x four finite modes x two implementations), across three sequential owners per process. K1b binds K1a's receipt and
must use a distinct owner process; both must have safe teardown.

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B "$P/window.py" --authorized-device-window --window K1a --card 0 --native-nice 19 --seconds 10800 --k0 "$P/build/k0/window.json" --output "$P/build/k1a"
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B "$P/window.py" --authorized-device-window --window K1b --card 0 --native-nice 19 --seconds 10800 --k0 "$P/build/k0/window.json" --k1a "$P/build/k1a/window.json" --output "$P/build/k1b"
```

K2 profiles packet 18 and specialised kernels on one card at the registered
decode shapes. Each class/arm has 200 repetitions. Its event rows retain GPU
start/end timestamps and same-run byte exactness. The summary reports median and
p90 both per event and for each class's summed stage execution time. It excludes
zero/negative/nonfinite event intervals, counts them, and excludes their whole
repetition from summed timings. More than 1% affected event rows fails the window;
exactly 1% is permitted. Missing classes/repetitions, changing stage coverage,
incorrect bytes or an over-budget submission also fail.

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B "$P/window.py" --authorized-device-window --window K2 --card 0 --native-nice 19 --seconds 10800 --k0 "$P/build/k0/window.json" --k1a "$P/build/k1a/window.json" --k1b "$P/build/k1b/window.json" --output "$P/build/k2"
```

Only a passing K2 creates `build/k2/run/dispatch-measured.json`. Each class stays
on `packet18` unless the exact specialised implementation's median execution sum
is strictly below 0.9 times packet 18's. The table and raw events are hash-bound
into the window receipt. Future named GEMV winners belong in the table's `gemv`
map, with their own implemented kernel identifier and new K1/K2 qualification;
a string naming an unsupported kernel never silently falls back. Fusion pairs
have a separate `fusions` map and their own old-pair/new-pair measurements; two
winning component flags never enable an unmeasured pair. `k2-class-registry.json`
is the complete coverage contract. The norm workload has six independent dispatch
aliases (`hc.a.norm`, `hc.f.norm`, `final.norm`, `ple.kn`, `ple.qn`, `ple.cn`): these
use the identical four-by-2560 kernel with F32 gains and unit=0. They share one
measured workload; the summary does not present six independent measurements.
Unchanged GEMV baseline arms explicitly have `candidate_available=false` and
cannot become winners through timing noise. For a class covering several formats, every registered workload must independently clear the 0.9 threshold; one format cannot hide another format's regression. Their frozen R5 identity stays in
the GEMV table. To qualify a named packet 25 candidate later, append the same
`--dispatch candidate.json` to K1a, K1b and K2 using fresh output directories.
Those three windows bind the candidate input file's hash. W2m/W2c still take
K2's generated `dispatch-measured.json`, whose hash is separately bound. K1
always includes all four registered finite GEMV modes even without a candidate, so
adding a candidate never changes the sealed expected fixture bytes.

W0 runs the retained packet 18 two-card canary through the packet 26 model binary:
100 round trips and 1,000 chained kernels per card. It verifies bytes, independent
queue ownership, tiny memory allocation, per-submission budget and safe teardown.

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B "$P/window.py" --authorized-device-window --window W0 --card 0 --native-nice 19 --seconds 600 --k0 "$P/build/k0/window.json" --output "$P/build/w0"
```

W2 is the control: two cards resident, 64 tokens, R5 GEMV, original packet 18
non-GEMV kernels and the new host issue path. It requires K0 and W0 on this boot
and binary. It does not require K1/K2 or W1. Its target is to reproduce at least
the scratch result of roughly 12 tok/s; this is a target, never an assumed result.
Every token row includes `prepare_ms`, `enqueue_loop_ms` and `wait_ms`, so the
host issue target of at most 12 ms/token can be tested on the cards.

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B "$P/window.py" --authorized-device-window --window W2 --card 0 --native-nice 19 --seconds 10800 --k0 "$P/build/k0/window.json" --w0 "$P/build/w0/window.json" --input "$P/build/input" --oracle "$ORACLE" --output "$P/build/w2"
```

W2m changes only the per-class dispatch admitted by K1a/K1b/K2. The wrapper binds
all gates to the same boot and binary set and verifies the measured table hash.

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B "$P/window.py" --authorized-device-window --window W2m --card 0 --native-nice 19 --seconds 10800 --k0 "$P/build/k0/window.json" --w0 "$P/build/w0/window.json" --k1a "$P/build/k1a/window.json" --k1b "$P/build/k1b/window.json" --k2 "$P/build/k2/window.json" --dispatch "$P/build/k2/run/dispatch-measured.json" --input "$P/build/input" --oracle "$ORACLE" --output "$P/build/w2m"
```

W2c uses the same table with `--timing class` in the native command. Its queues
have profiling enabled and it writes per-class GPU execution sums. It is labelled
profiling and is never a decode speed claim. W2/W2m use `--timing token`: queues
without profiling and no timestamp queries.

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B "$P/window.py" --authorized-device-window --window W2c --card 0 --native-nice 19 --seconds 10800 --k0 "$P/build/k0/window.json" --w0 "$P/build/w0/window.json" --k1a "$P/build/k1a/window.json" --k1b "$P/build/k1b/window.json" --k2 "$P/build/k2/window.json" --dispatch "$P/build/k2/run/dispatch-measured.json" --input "$P/build/input" --oracle "$ORACLE" --output "$P/build/w2c"
```

Optional W1 streams one layer at a time on one card for eight generated tokens.
If supplied to a model window with `--w1`, its identity and exactness are checked.
Its omission never blocks W2.

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B "$P/window.py" --authorized-device-window --window W1 --card 0 --native-nice 19 --seconds 10800 --k0 "$P/build/k0/window.json" --input "$P/build/input" --oracle "$ORACLE" --output "$P/build/w1"
```

Every model window compares all retained 384 layer fixtures and all requested
tokens directly against the v2 CPU oracle. There is no tolerance. Decode tok/s
uses the whole wall span of tokens 2 through 64, with numerator 63. It is a
fixed-prompt correctness/timing window, not the realistic final quality suite.
Per-class profiling, preparation, waiting and host enqueue work are recorded
separately and are not substituted for that denominator.

All prerequisites, source files, binaries, model input manifests and oracle bytes
are checked before admission and after execution. `ldd` only inspects shared
library resolution; missing dependencies fail before the native binary starts.
The environment policy is closed: unknown variables and unregistered driver
settings are rejected, including empty debug variables. Only the recorded native
allowlist reaches the child. `--native-nice` records the requested native priority
and refuses a priority lower than the wrapper inherited; this packet's commands
use 19 and do not seek privileges to change that.

Output directories must be new and beneath ignored `build/`. Preserve receipts,
fixtures, raw timestamps, stdout and kernel logs before cleaning measured output.
A fault writes a boot latch and sends one SIGTERM. A still-running child after a
bounded drain is retained for the coordinator; it is never hard-killed or retried.
The coordinator remains responsible for idle/health checks and any recovery.
See [deadline separation](DEADLINES.md) for expected duration, submission budget,
wait bound and watchdog for each window.
