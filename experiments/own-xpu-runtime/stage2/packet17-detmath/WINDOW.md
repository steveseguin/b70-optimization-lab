# Packet 17 prepared elementary windows

No device program was run while preparing this packet. The coordinator owns
admission, the selected card, sourcing oneAPI, and post-window idle health. These
commands are preparations for that separately admitted window.

The hash-bound `build/window-prepared.json` must be regenerated after any source,
binary, fixture, table, trace or host-hash change. `--check` verifies file hashes
and calls `ldd`; it never discovers devices. Missing shared libraries fail before
an output directory, fault latch or `device_executed` claim is created.

From the repository root, after the coordinator has sourced
`/opt/intel/oneapi/setvars.sh`:

```sh
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B experiments/own-xpu-runtime/stage2/packet17-detmath/device_window.py --check --mode W-B --card 3 --output experiments/own-xpu-runtime/stage2/packet17-detmath/build/card3-wb-b
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B experiments/own-xpu-runtime/stage2/packet17-detmath/device_window.py --authorized-device-window --mode W-B --card 3 --seconds 600 --output experiments/own-xpu-runtime/stage2/packet17-detmath/build/card3-wb-b
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B experiments/own-xpu-runtime/stage2/packet17-detmath/device_window.py --check --mode W-A --card 3 --output experiments/own-xpu-runtime/stage2/packet17-detmath/build/card3-wa-b
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B experiments/own-xpu-runtime/stage2/packet17-detmath/device_window.py --authorized-device-window --mode W-A --card 3 --seconds 900 --output experiments/own-xpu-runtime/stage2/packet17-detmath/build/card3-wa-b
```

These are diagnostic device jobs, not model servers. Launch the wrapper through
the coordinator's approved job owner if needed; do not create or modify LTX
units. Output directories must be new. An existing latch forbids another launch
until coordinator review. No retries or automatic fault recovery exist here.

## W-A coverage and interpretation

**All host reference math runs before admission.** The CPU builder pilots each
function on 2^20 stratified inputs. A projected full cost at most 550 CPU seconds
selects all 2^32 encodings; otherwise it selects the existing 2^28 stratified
domain. The three rsqrt spellings share the plain spelling's identical host
twin and selected domain. The completed receipt records the exact choices.
No coverage is reduced to shorten a device window.

The host builder writes per-chunk dual fingerprints and losslessly compressed
binary32 reference values. Explicit RoPE, triple and fixture operands are also
prepared on CPU. Each slab contains at most 262,144 values; delta byte planes
and zlib preserve every bit, including signed zeros and NaN payloads. The CPU
readback checks every fingerprint, every slab boundary and two independently
recomputed host endpoints per slab before sealing. W-A streams these slabs;
there is no host elementary-function evaluation, pilot or 600-second host
budget while a card is held. The window's `host_cpu_seconds: 0` means reference
math was moved to the build; it does not mean file decoding or launch work is free.
All 72 fixtures' distinct elementary operands remain included.

Functions: native exp, log, sqrt, reciprocal, sin, cos and three reciprocal-sqrt
spellings. Each reciprocal-sqrt spelling compares to host `sqrtf` followed by
host binary32 division. RoPE tests all 32 exponents for rotary width 64, positions
0..150, and their host-generated sin/cos arguments. Traces add fixture-specific
arguments. Each division/contraction operation receives the same 2^26 triples;
half are general bit patterns and half are cancellation or adjacent-to-exact-
cancellation constructions. For the latter probes, receipts also count direct
device differences against device separate-mul-add and device explicit FMA.

Each chunk reports raw-bit differences, differences between two NaN encodings,
two 64-bit order-sensitive-to-input-index fingerprints, and ULP histogram.
Histogram bin 0 means zero integer ULP distance; bin k>0 means a distance in
[2^(k-1), 2^k-1]. Signed zeros and NaN payloads retain their raw bits; their
integer distances are not numerical-error measurements. Native disagreement is
the W-A result, not a failed census. Missing coverage or timeout is a failure.

W-A also writes `owner0/census/summary.json` and embeds it in the window receipt.
It checks complete coverage and aggregates every function and its fixture
arguments. Only differing encodings where **both** results are NaNs are exempt
from the candidate decision; one-NaN-versus-finite/infinity is always a failure.
The summary distinguishes exhaustive equality from equality on the documented
stratified sample. It prefers the current barrier spelling when qualified and
never changes the runtime automatically.

The plain, integer-barrier and software-corrected reciprocal-sqrt candidates
remain selectable. W-A must select a candidate with **zero non-NaN differences
and the required special-case behavior** before a device identity is accepted.
The software reciprocal uses an exact integer quotient/remainder after rounded
sqrt. Its device implementation still requires the complete gate. The current compiler flags explicitly require correctly
rounded offload division and sqrt; W-A measures whether the actual lowering
obeys that requirement.

## W-B coverage and three fixture gates

Before admission, the CPU build creates `host-hashes.txt` using:

```sh
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 experiments/own-xpu-runtime/stage2/packet17-detmath/build/gnu/census-host host-hashes 32 262144 experiments/own-xpu-runtime/stage2/packet17-detmath/build/host-hashes.txt 1
```

It visits every one of the 2^32 input encodings for each of v2 exp and log in
ascending integer order. Each 262,144-input row stores operation ID, start,
count, modular 64-bit sum and 64-bit XOR of a fixed mix of input index and output
bits. The preparation receipt hashes this complete ordered file. W-B rejects
partial, reordered, extra or mismatched rows. Hash agreement has the usual finite
fingerprint collision limitation; it is not a formal bitwise proof.

Each of two fresh owners recomputes all exp/log chunk fingerprints on the device
and compares them with the host rows, then runs all 72 fixtures. The independent
gates are parallel-v2 == core-v2 on device, core-v2 device == core-v2 host, and
two fresh device owners produce identical fixture bytes. NaN encodings in v2
exp/log are canonical and included in the exhaustive hashes.

The wrapper checks packet2 fault signatures throughout startup, execution and a
five-second post-exit journal window. On a fault or deadline it writes a latch
and sends one SIGTERM. It allows a 20-second graceful drain, then returns the
still-live PID to the coordinator without killing it or launching anything else.
Census and fixture device events have a two-second waiting deadline; any measured kernel duration
of 0.5 seconds or longer aborts the window. Slabs are bounded to 262,144 values,
with 64 values per work item. The first real device window must still establish
the actual duration bound; no host-only build can prove a GPU time limit.

Planning allowances, not new device measurements: W-B a few minutes
(600 seconds per census owner); W-A about 5–10 minutes (900-second ceiling),
including bounded slab decoding and the short A/B probes. W-A's exact duration
still needs a coordinator measurement. Its full reference pass runs before
card admission. Each submission retains the 0.5-second abort threshold and
two-second wait deadline; no longer submissions were introduced.

## Same-object link A/B in W-A

Before the full census, W-A runs the same 65,536 division, sqrt and each of
three rsqrt probes in two separate short processes. `plain-link` is an explicit
negative control linked from the **same census object** with plain `-fsycl`.
`precise-link` is the qualified CMake target, linked with both precision flags.
Their commands, object SHA-256 and binary SHA-256 values are in the build receipt.
The negative control is not a CMake device target or a runtime candidate.

Each probe reports “correctly rounded” or “not correctly rounded” **on its tested
inputs**. For rsqrt this means rounded sqrt followed by rounded binary32
division, not a claim about single-rounding of the mathematical inverse root.
Only two-NaN encoding differences are exempt. The receipt reports whether the
two links actually differed; it does not invent a link effect when both agree.
The full census, not these short probes, remains the rsqrt candidate gate.

## Rebuild or restore W-A references on CPU

For the existing packet build (verified host hashes and oracle retained):

```sh
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B experiments/own-xpu-runtime/stage2/packet17-detmath/build.py --native-only --jobs 2
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B experiments/own-xpu-runtime/stage2/packet17-detmath/prepare_wa.py
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B experiments/own-xpu-runtime/stage2/packet17-detmath/seal.py
```

`prepare_wa.py` verifies completed references; it never launches a device.
The build requires system zlib headers and library for lossless slab storage.
For a clean CPU reference reconstruction, build the Intel HOST_ONLY
`wa-precompute` and `wa-verify` targets with at most two jobs, then use `prepare_wa.py --precompute` with a **fresh**
`build/wa-reference` path. It refuses an existing directory. `build.py --jobs 2
--wa-references` performs this preparation when references are absent, then seals
them. Do not repeat `--hashes` or the full-model oracle when their checked inputs
are unchanged. Keep the compressed slabs in ignored build/ for the window;
their hashes, format, coverage and reconstruction inputs are recorded in
`wa-reference-receipt.json`.

## CPU reproduction and oracle

The full commands below are for a fresh reconstruction. Reuse the checked host
hashes and oracle in the existing build; the short rebuild commands above do so.

Run from the repository root. Use a Python interpreter with CPU Torch available
when regenerating the original fixture inputs. All build targets are compilation
only except the explicitly named host targets; build.py never starts native code.

```sh
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 /home/steve/.venvs/vllm-xpu/bin/python -B experiments/own-xpu-runtime/stage2/packet17-detmath/build.py --hashes --wa-references --jobs 2
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 /home/steve/.venvs/vllm-xpu/bin/python -B experiments/own-xpu-runtime/stage2/packet13-integrate/prepare.py --output experiments/own-xpu-runtime/stage2/packet17-detmath/build/oracle-input
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B experiments/own-xpu-runtime/stage2/packet17-detmath/run_oracle.py --build experiments/own-xpu-runtime/stage2/packet17-detmath/build/oracle --input experiments/own-xpu-runtime/stage2/packet17-detmath/build/oracle-input --out experiments/qwen38-flash-next-ud-iq3xxs-b70/packet3-runtime-oracle/runs/arithmetic-v2-detmath-20261011 --seconds 10800 --tokens 64
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B experiments/own-xpu-runtime/stage2/packet17-detmath/compare_oracle.py
```

The oracle output path must be fresh; the recorded run may not be overwritten.
For a later repeat choose a new explicitly authorized run directory and adapt
comparison paths. The oracle uses two threads; the exhaustive host-hash pass
supports one or two and must be scheduled to keep aggregate long computations
at four CPU threads or fewer. The measured host-hash pass in this packet used
one thread. Compile at most two jobs. Do not run build.py alongside the oracle
unless their combined CPU use remains within the same cap.

The coordinator sources `/opt/intel/oneapi/setvars.sh` before the device commands.
This packet does not source it or execute a device program. A missing `ldd`
library fails before output/latch creation; supply the required environment and
rerun the read-only `--check` before admission. Do not reset a fault latch merely
to run the next window. An existing fault needs coordinator disposition.

Run W-B first, then W-A. No device ran in this repair task.
