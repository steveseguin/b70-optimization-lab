# Packet55 row-vectorized exact CPU experts

The [two fresh CPU fixture runs](evidence/test-corrected/receipt.json) pass
**54,001 checks each**, including 18 complete experts, 80,640 BF16 values and
60 raw exceptional-input cases. Their output digests match each other and
packet46. The retained build is 248 KiB. Throughput is **unmeasured**; the
coordinator runs the quiet window below.

This is an independently written AVX2 CPU kernel. A vector contains eight
different output rows. Each row still has the production 32 logical lanes,
each visiting eight consecutive values per tile in increasing order, followed
by the adjacent SG32 tree. Multiplication and addition round separately;
GEMV has no FMA contraction. Gate and up round separately to BF16, the lab's
deterministic SiLU runs, its product rounds to BF16, then down runs and rounds
to BF16. The code reads original packed expert bytes without an expanded copy.
It does not use Strata, llama.cpp, vLLM or BLAS code.

Credit Niko1221 / Strata for the hot-expert GPU cache and parallel exact CPU
miss design idea, as recorded in [the design](../../../ONE-CARD-DESIGN.md).
The implementation and measurements are the lab's own work.

The production arithmetic reference is the read-only packet49c source.
IQ2_S gate/up and IQ4_NL down use the packet49b compact-layout host arithmetic;
the candidate reads the equivalent original packed bytes. Layer 2 has IQ3_S
gate/up and is a separate case, using packet49c's unchanged p28 reference.
It costs **2,329,600 bytes/expert**, versus **1,971,200** for ordinary layers.
Neither layer-2 time nor its byte count is inferred from IQ2_S.

Build and light tests, from the repository root:

```bash
nice -n 19 taskset -c 4-15,20-31 python3 -B experiments/own-xpu-runtime/stage2/packet55-feasibility/cpu/run.py build --output experiments/own-xpu-runtime/stage2/packet55-feasibility/cpu/evidence/build-fresh
nice -n 19 taskset -c 4-15,20-31 python3 -B experiments/own-xpu-runtime/stage2/packet55-feasibility/cpu/run.py test --output experiments/own-xpu-runtime/stage2/packet55-feasibility/cpu/evidence/test-fresh
```

Allow about 15 seconds for the serial build and 15 seconds for the two fresh
test processes. Coordinate the compile slot; no other compiler should run.
New output directories are mandatory. The runner records compiler flags,
transitive local header hashes, binary hashes, commands and all output. An edit
to any source dependency requires a rebuild and another exactness gate.

The fixture gate reconstructs the existing packet46 G4 experts 0, 37 and 333
for both formats and three input variants. It compares **80,640 complete BF16
values** (gate, up, SiLU product and down) and requires the existing frozen
packet46 output digest `0ea0eeaa89bce627`. Sampled rows also compare every FP32
logical lane, the SG32 tree and final BF16 boundary to packet49c production.
Additional cases cover signed zero, BF16/half subnormals, largest finite half
scales, NaN payloads and infinities. No tolerance or NaN canonicalization is
allowed in those arithmetic comparisons.

One-time immutable weight admission refuses nonfinite scales. The standalone
transaction rejects nonfinite input/output, inactive work, sticky errors and
wrong extents without publishing partial results. Those conservative guards
are not production GPU route/status semantics. **Device exception/status
parity and actual GPU output comparison remain unqualified**; the CPU gate
establishes equality against production CPU arithmetic fixtures. This is a
benchmark prerequisite, not an admitted engine miss handler.

The initial harness failure is retained under `evidence/test`: the reference
tree helper mutates its input, so calling it twice produced a wrong BF16 test
expectation. The corrected harness stores the first reduced result. No
candidate arithmetic was changed to tolerate the failure.

## Coordinator's quiet CPU window

Run only after all GPU windows, including packet49d on cards 0+1, have ended.
This benchmark is not authorized while any GPU campaign runs. No services,
GPU probes, model loads or memory/power changes are performed by the runner.
It holds the shared packet55 `window.lock` exclusively and nonblocking for the
whole run. That lock covers only packet55; the coordinator's explicit flag
acknowledges that all other packets and GPU work are quiet too.

```bash
nice -n 19 taskset -c 4-15,20-31 python3 -B experiments/own-xpu-runtime/stage2/packet55-feasibility/cpu/run.py bench --coordinator-quiet-window --seconds 1 --samples 3 --output experiments/own-xpu-runtime/stage2/packet55-feasibility/cpu/evidence/quiet-cpu-01
```

Reserve **10–20 minutes**, conservatively, for two fresh processes at each of
1, 4, 8, 12 and 16 threads. Each process tests both formats and 96/4/6/10
experts per dispatch, with three samples of at least one second each. Small
groups directly measure a layer with 4, 6 or 10 misses; their times are not
obtained by multiplying an unrestricted bulk rate. Work distributes independent
eight-row tiles, so a four-miss layer can use 16 threads. Gate/up and down have
a barrier between them. Actual sample overruns remain in the receipt.

Workers are pinned individually in order `4..15,20..23`. The admitted affinity
has only **12 physical cores**; the 16-thread case uses those 12 plus **four
SMT siblings**, not all 16 physical cores of the processor. Affinity and the
rounding/underflow environment are checked each dispatch. The runner clears
inherited OpenMP affinity variables and records actual worker CPUs.

The synthetic bank has 96 distinct experts and rotates between calls. Maximum
packed bank size is 223,641,600 bytes, above aggregate LLC. Inputs change each
dispatch; immutable weights may remain in normal hardware caches. There is
one initialization sweep, outside timing. No model weights are read, no large
memory is pinned. Peak explicitly allocated data is below **225 MiB** and
expected peak resident host memory is **256 MiB**, including touched stack
pages and program overhead; thread stack virtual reservations are additional.
This is an estimate, not a changed host memory limit. CPU build files
are a few MiB; all evidence is compact JSON and text.

`receipt.json` reports decimal GB/s of **packed bytes processed**, microseconds
per complete expert, and measured dispatch mean/p50/p90/p99 for each sample.
It is not a DRAM bandwidth measurement. Timing includes input construction,
team dispatch, gate/up, deterministic SiLU, down, barrier, output finite checks
and hash/publication work. It excludes allocations and immutable admission.
No CPU/GPU overlap, D2H input latency, H2D output latency, route lookup, cache
policy, actual checkpoint bandwidth or end-to-end model speed is measured.

For the feasibility calculation, use the directly measured per-layer latency
at the required thread count, format and miss count. The bulk 96-expert rate
is a ceiling diagnostic. A design must sum dependent layer waits and account
for draft and target sharing the same GPU.
