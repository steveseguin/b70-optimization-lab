# Packet 35 coordinator windows

No device ran during preparation. No speed is claimed. These commands are for
the coordinator, run explicitly one at a time in the authorized systemd user
unit. Run from `/home/steve/llm-optimizations`. The coordinator supplies
`LD_LIBRARY_PATH`; no environment workaround or driver discovery is added here.
Every output directory below must be new. Change the run suffix consistently
when repeating a campaign; retain prior receipts and evidence.

`--card N` is the physical index. The executable examples use `--card 0`:
K0/W0/W2/W2m/W2c/W2x cover cards 0+1; K1a/K1b/K2 use card 0. For another adjacent pair,
replace every card index consistently. K0 must cover every card used later.

```bash
P=experiments/own-xpu-runtime/stage2/packet35-hostpath
ORACLE=experiments/qwen38-flash-next-ud-iq3xxs-b70/packet3-runtime-oracle/runs/arithmetic-v2-detmath-20261011/incident-retrospective
```

K0 compiles every linked device kernel image on the two requested cards, without
kernel execution or explicit device allocation. It binds source/binary hashes,
boot and environment for subsequent windows.

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B "$P/window.py" --authorized-device-window --window K0 --card 0 --native-nice 19 --seconds 600 --output "$P/build/k0-r35"
```

K1a and K1b enumerate all linked non-GEMV implementations, packet 25/27
GEMVs, packet 28 GEMVs, both packet 29 expert-down kernels and small GEMV tuples against the unchanged arithmetic reference and incumbent output.
Each process owns four fixture backends sequentially, with safe teardown between
them. K1b must be a fresh process and binds K1a. Both use the same candidate map
and must match the sealed CPU fixture bytes. Every linked alternative is enumerated. K1 receipts bind the closed
`kernel-registry.json`, including each class/kernel pair. This allows a later
W2x selection assembled from those covered kernels.

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B "$P/window.py" --authorized-device-window --window K1a --card 0 --native-nice 19 --seconds 10800 --k0 "$P/build/k0-r35/window.json" --dispatch "$P/dispatch-all-new.json" --output "$P/build/k1a-r35"
```

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B "$P/window.py" --authorized-device-window --window K1b --card 0 --native-nice 19 --seconds 10800 --k0 "$P/build/k0-r35/window.json" --k1a "$P/build/k1a-r35/window.json" --dispatch "$P/dispatch-all-new.json" --output "$P/build/k1b-r35"
```

K2 times the actual packet 26 incumbent against every candidate on one card at
model decode shapes and formats. It takes 200 repetitions per comparison and
reports byte equality, kernel identity, median/p90 event times and summed-stage
microseconds. GEMV inputs and all rotation copies are uploaded before timing. Outputs of
every copy are checked outside the measured repetitions. No device copy occurs
in a measured launch. Tuple output checks also stay outside measured launches. Failed candidates are
reported, excluded and followed by the remaining candidates. Incumbent failures
still prevent admission.

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B "$P/window.py" --authorized-device-window --window K2 --card 0 --native-nice 19 --seconds 10800 --k0 "$P/build/k0-r35/window.json" --k1a "$P/build/k1a-r35/window.json" --k1b "$P/build/k1b-r35/window.json" --dispatch "$P/dispatch-all-new.json" --output "$P/build/k2-r35"
```

A candidate enters `build/k2-r35/run/dispatch-measured.json` only when exact and
its ROTATED median is strictly below 0.9 times the incumbent ROTATED median
for every class with more than 8 MB per launch group. These classes are
gdn.qkv, gdn.z, qsa.qgate, attention, logits, expsgate, expsdown and ple.key.
Each uses eight complete, distinct weight payloads: dense allocations or
disjoint ten-expert groups. Incumbent and candidate alternate with a four-copy
offset, so adjacent submissions never read the previous arm's weights. The
re-read median is also reported and cannot select a heavy-class winner. Small
classes use their re-read median under the same strict threshold. Every format in
a class must clear the threshold separately; one winning format cannot hide a
regression. Small tuples compete against the sum of their members. Compound
fusions have their own measured entries. If independently winning member GEMVs
conflict with a fusion, K2 compares the measured fusion time against the sum of
the selected member times. It records both numbers per workload and keeps the
fusion only when strictly cheaper for every workload (including both FFN
formats). Ties select members. The HC aliases represent one low and one inject
operation, not five launches. Missing comparison data fails admission; it never
silently disables a fusion. If no candidate qualified, member cost is the median
of that member's same-run incumbent comparison medians. Individual winner
records remain intact; `final_dispatch` records which compatible entries run.
Invalid timing rows and affected repetition sums are excluded and counted;
more than 1% invalid event rows, missing unexcluded coverage, source changes,
unsafe teardown or an over-budget submission prevents admission. Candidate
failures remain in the receipt even when another candidate qualifies.

W0 is the retained two-card canary through this packet's native model binary.
It checks 100 round trips and 1,000 chained kernels per card, output bytes,
queue ownership, tiny memory use and safe teardown.

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B "$P/window.py" --authorized-device-window --window W0 --card 0 --native-nice 19 --seconds 600 --k0 "$P/build/k0-r35/window.json" --output "$P/build/w0-r35"
```

W2 is the control using packet 29's unchanged default dispatch, including its
qualified non-GEMV choices and R5 GEMVs. It uses two
resident cards, 64 generated tokens, token timing without profiling, and eight
retained layer-fixture steps. No custom dispatch argument is supplied.

W2, W2m, W2c and W2x must start from a nice-0 coordinator. Launching a wrapper at nice
19 and merely requesting `--native-nice 0` cannot raise its priority. The native
binary now verifies the wrapper's stated priority rather than always requiring
19. Receipts record wrapper/native priorities, CPU affinity and start load average;
helpers remain nice 19. The wrapper and child inherit `taskset` affinity without
changing it. A coordinator may prefix a model command with `taskset -c 4-15,20-31`
only if those cores match its allocated GPU window. Do not change affinity from
this CPU preparation session. No runtime submission starts from the preparation agent.

```bash
nice -n 0 ionice -c 3 env OMP_NUM_THREADS=2 python -B "$P/window.py" --authorized-device-window --window W2 --card 0 --native-nice 0 --seconds 10800 --k0 "$P/build/k0-r35/window.json" --w0 "$P/build/w0-r35/window.json" --input "$P/build/input" --oracle "$ORACLE" --output "$P/build/w2-r35"
```

W2m substitutes only the hash-bound K2 measured selection. It requires the
matching K1a/K1b/K2 and W0 receipts, same boot and same binary set.

```bash
nice -n 0 ionice -c 3 env OMP_NUM_THREADS=2 python -B "$P/window.py" --authorized-device-window --window W2m --card 0 --native-nice 0 --seconds 10800 --k0 "$P/build/k0-r35/window.json" --w0 "$P/build/w0-r35/window.json" --k1a "$P/build/k1a-r35/window.json" --k1b "$P/build/k1b-r35/window.json" --k2 "$P/build/k2-r35/window.json" --dispatch "$P/build/k2-r35/run/dispatch-measured.json" --input "$P/build/input" --oracle "$ORACLE" --output "$P/build/w2m-r35"
```

W2c uses exactly W2m's selection and enables per-class profiling. Its execution
sums, issue time and waits are diagnostic; W2c is not a decode-speed result.

```bash
nice -n 0 ionice -c 3 env OMP_NUM_THREADS=2 python -B "$P/window.py" --authorized-device-window --window W2c --card 0 --native-nice 0 --seconds 10800 --k0 "$P/build/k0-r35/window.json" --w0 "$P/build/w0-r35/window.json" --k1a "$P/build/k1a-r35/window.json" --k1b "$P/build/k1b-r35/window.json" --k2 "$P/build/k2-r35/window.json" --dispatch "$P/build/k2-r35/run/dispatch-measured.json" --input "$P/build/input" --oracle "$ORACLE" --output "$P/build/w2c-r35"
```

W2x accepts an explicit dispatch assembled by the coordinator. Every class/kernel
pair must exist in this sealed binary and be covered by both fresh K1 owners.
It does not require a K2 winner, and records the exact supplied map hash.
The optional `--dispatch-override` file is admitted only for W2x and is mutually
exclusive with `--dispatch`. Supply a closed-registry, conflict-free map at
`$P/build/dispatch-override.json`; all entries must be covered by K1a and K1b.
This file is a coordinator decision, not a measured winner. The inherited merge
utility remains an explicit precedence tool; K2 alone makes measured comparisons.

```bash
nice -n 0 ionice -c 3 env OMP_NUM_THREADS=2 python -B "$P/window.py" --authorized-device-window --window W2x --card 0 --native-nice 0 --seconds 10800 --k0 "$P/build/k0-r35/window.json" --w0 "$P/build/w0-r35/window.json" --k1a "$P/build/k1a-r35/window.json" --k1b "$P/build/k1b-r35/window.json" --dispatch-override "$P/build/dispatch-override.json" --input "$P/build/input" --oracle "$ORACLE" --output "$P/build/w2x-r35"
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

The device issue benchmark is the real token plan in W2/W2m/W2x. No no-op kernel
substitutions are used. `enqueue_loop_ms` times the complete normal host issue
loop once per token. W2c additionally records `enqueue_family_ms` with clock reads
around actual submissions. Token mode writes null per-family entries so it does
not add per-launch clock cost; use W2c's family split only as a profiling
diagnostic, not as token-mode throughput. Startup prepares all resident launch
bindings after dispatch selection. One-card W1 retains the legacy streaming
path and is optional; it is not evidence for the prepared two-card issue path.

After device uploads, startup requests embedding/PLE pages with MADV_WILLNEED
and reads every page. This is process-local read-ahead, not a cache drop or a
system setting. It is best effort and cannot guarantee later residency. Every
token records process major/minor faults, issuing-thread voluntary/involuntary
context switches and prepare_ms. The summary explicitly marks decode windows
with major faults as PAGE-FAULT CONTAMINATED, even if token equality passes.
The native receipt records the residency pass's duration and byte count. Warm
and cold estimates belong in README; never manufacture a cold measurement by
clearing the page cache. All windows here are prepared, not run.
