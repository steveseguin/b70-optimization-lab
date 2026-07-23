# Laguna shared-down native M=8 BF16 MM preregistration

Date registered: 2026-07-23 America/Toronto

Status at registration: the default-off vLLM treatment, per-card component
harness, four-card analyzer, and analyzer tamper tests are source-frozen and
statically validated. No XPU execution test, component run, counter-fixture
run, hardware-counter capture, endpoint service, model generation, payload, or
submission has occurred for this treatment.

Execution update at 2026-07-23T15:41:46Z: the focused XPU dispatch and
fail-closed-layout test passed on physical rank 0. The first full component
command then stopped during identity validation, before tensor work, because
the initial harness looked for the noncanonical substring `Arc Pro B70` while
the frozen runtime reports `Intel(R) Arc(TM) Pro B70 Graphics`. Its failed
artifact is preserved at
`/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/shared-down-m8-component-20260723T154116Z/card0.json`
and that run root will not be reused. The correction changes only the identity
predicate: the harness and analyzer now require exact equality with the
runtime's full device name. No component timing, counter fixture, hardware
counter, endpoint, model generation, payload, or submission occurred.

Execution update at 2026-07-23T15:47:40Z: a fresh retry under
`shared-down-m8-component-20260723T154717Z` passed runtime identity and all
128 changing exactness epochs on physical rank 0, including 128 unique fixture
and output hashes and raw equality at every declared boundary. It then stopped
before real-path dispatch and timing because the harness's M=8-only incumbent
helper was mistakenly reused to construct the required M=7 tail reference.
The preserved `card0.json` reports `status=error`, has no timing result, and
keeps all counter, endpoint, generation, and submission authorizations false.
That root will not be reused. The correction factors the identical
stride-zero-BMM expression into a reference helper that permits M=1..8, while
the measured incumbent wrapper remains strictly M=8; only the M=7 real-path
reference uses the generalized helper. A CPU regression test now exercises
the M=7 shape.

Static-audit update before any further XPU retry: a line-by-line review found
that the real-path fixture disabled the down-MM marker for its unmarked M=8
check but did not re-enable it for the subsequent M=7 tail. The output was
still BMM-exact, but that sequence did not prove the preregistered *marked*
M=7 fallback. The frozen gate now records and requires marker enabled for
candidate M=8, disabled for the unmarked M=8 control, and re-enabled for the
M=7 tail. The analyzer independently requires those three marker states.
Negative CPU tests also require the reference helper to reject M=0/M=9 and
the measured incumbent wrapper to reject M=7. This verifier hardening occurred
before another component command; it changes no candidate, control, or timing
operation.

## Question and treatment choice

The approved route-interleaved profile attributes `1.014246 ms` per 47-layer
target cycle to the shared-expert/router BF16 GEMM family. The shared expert
has three unquantized BF16 projections per TP4 rank:

```text
gate: [8,3072] @ [3072,256]
up:   [8,3072] @ [3072,256]
down: [8,256]  @ [256,3072]
```

Each projection reads a 1.5 MiB BF16 local weight and performs 12.583 million
FLOPs per layer. Gate/up are narrow-N=256. A prior merged gate/up geometry
screen was faster but bitwise exact only 24/64; changing the oneDNN batch,
stride, and N geometry therefore cannot be assumed exact. The down projection
is the sole wide-N=3072 shared GEMM and gives the narrowest occupancy
hypothesis: one primitive, one projection, and one rounding boundary.

The frozen treatment is consequently **down-only**, not all-three and not a
gate/up merge:

```text
control:
  shared down = stride-zero B=8, M=1, K=256, N=3072 BF16 BMM

candidate:
  shared down = native M=8, K=256, N=3072 BF16 MM
```

Gate, up, the existing exact shared SiLU/multiply, routed scale, shared+routed
add, and fixed-rank reduction stay literal and separate. There is no fusion,
auxiliary stream, weight repack, quantization change, graph, or collective
change.

## Default-off selector and exact scope

The new selector is:

```text
VLLM_XPU_LAGUNA_M8_SHARED_DOWN_MM=1
```

Only the target model's `shared_expert.down_proj` receives its marker. Dense
MLP, shared gate/up, router, attention, routed experts, and the DFlash draft do
not. Dispatch additionally requires:

- the exact target-verifier context at exactly M=8;
- XPU BF16 contiguous rows `[8,256]`;
- an unquantized contiguous BF16 weight `[3072,256]` on the same device;
- no bias and eager, noncompiled execution; and
- the complete approved exact stack, including literal routed-W1 N64.

Any matching flagged M=8 call with a dtype, device, shape, layout, method,
bias, compile, or record-stack drift raises. M=1 decode, M=2..7 verifier
tails, target prefill, draft, and every unmarked layer retain the incumbent
stride-zero BMM.

The active checkpoint config is pinned at SHA-256
`9f139560db8fd723a75ee4adc24a9fece4101df0e8e7f1cce6549f7eba5b14e6`.
It explicitly puts `shared_expert.down_proj` in the quantization ignore set.
Its Hadamard entries use only offline `weight_input` and `weight_output`
locations; they do not create an online runtime transform wrapper. The
component gate parses and verifies that metadata, constructs the actual
checkpoint-selected `RowParallelLinear`, requires
`UnquantizedLinearMethod`, proves there is no runtime Hadamard module, and
exercises its real forward at the exact local geometry. Shared down has
`reduce_results=False`; the unchanged shared+routed combination is reduced
later in the existing fixed rank order.

## Frozen source and tooling

- main repository tool commit:
  `da01170c7a6ffdc060c0da797232443938143537`;
- vLLM:
  `75d4660463407975c16bd33711499ca560bf2034`;
- XPU kernels, unchanged:
  `c59aaadbbfd350c2b5f4ad663e247c2811ae3181`;
- component harness:
  `experiments/laguna-s-2.1-xpu-b70/tools/gate_laguna_shared_down_mm.py`;
- harness SHA-256:
  `df8496f1f405e8b786dff0b96b7c320944c5d0133cce0bfcc2e36150ab1e0f12`;
- four-card analyzer:
  `experiments/laguna-s-2.1-xpu-b70/tools/analyze_laguna_shared_down_mm_component.py`;
- analyzer SHA-256:
  `945810c50eeeea99f532c3e62ee5bf289677e3706d80965f966400bfab35911b`;
- CPU-only analyzer tests:
  `experiments/laguna-s-2.1-xpu-b70/tools/test_analyze_laguna_shared_down_mm_component.py`;
- analyzer-test SHA-256:
  `b0b918da332adff73496f2c252379bfbce9cd318c4d0e3038bee193c751e4f0c`;
- shared `_C.abi3.so`:
  `126da37b23e5eff6840dd256c90164e3a282469e5fafa27830530e63ff36bce2`;
- `_xpu_C.abi3.so`:
  `f5f672130cc1b1d550646f732a6d576952c49514eba7a10db60fc1c361938fd8`;
- `_moe_C.abi3.so`:
  `0057b266d567731a9f9f592cefd9103bbf027ebb83c876d26c17ffb09994a3a0`;
  and
- `libgrouped_gemm_xe_2.so`:
  `fc74a6452b95643768889e2598df77bc4f4aa2b0925257a4c0eff371b1cf6c96`.

The vLLM commit adds the selector to the AOT runtime identity even though this
experiment requires eager execution. Ruff, focused formatting, whitespace,
30 vLLM non-XPU tests, and 14 CPU analyzer/tamper/regression tests pass. The
tamper suite
changes every candidate boundary digest and aggregate linkage and requires
rejection. Independent source reviews found the selector down-only,
default-off, transform-safe, fail-closed, and the final component tooling free
of code blockers.

## Four-card exactness and timing gate

Run the frozen harness separately on each physical B70 with one visible
device. It fails before tensor work unless the output is an absolute,
nonexisting path under
`/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1`, that root still
resolves to `/dev/nvme0n1p2` `ext4`, all three repositories are clean at the
frozen vLLM/kernel heads, every native binary hash matches, the full exact
environment matches, kernel taint is zero, and boot ID is
`0b7f98a5-e50a-46a5-81ea-15938b55317a`.

Each process must have `ZE_AFFINITY_MASK=<rank>`,
`ONEAPI_DEVICE_SELECTOR=level_zero:0`, and exactly one torch-visible XPU.
The torch-visible name must equal
`Intel(R) Arc(TM) Pro B70 Graphics`.
Filtered logical-device-0 UUID/BDF/DRM identity must equal the unfiltered
physical rank, frozen as:

```text
rank 0: 0000:23:00.0  00000000-0000-0023-0000-0000e2238086
rank 1: 0000:27:00.0  00000000-0000-0027-0000-0000e2238086
rank 2: 0000:43:00.0  00000000-0000-0043-0000-0000e2238086
rank 3: 0000:47:00.0  00000000-0000-0047-0000-0000e2238086
```

All cards receive the same rank-invariant CPU-generated BF16 corpus. Each card
must pass:

- 128 changing input/weight/routed/reduction epochs;
- separate control/candidate raw SHA-256 equality and `torch.equal` at shared
  down, candidate repeat, shared+routed add, and simulated fixed-rank sum;
- unchanged input bytes, finite results, 128 unique fixture hashes, and 128
  unique output hashes;
- a 32-epoch exact replay after sustained timing;
- execution of the actual checkpoint-selected `RowParallelLinear.forward`
  while incumbent `torch.bmm` is unavailable, with exactly one `torch.mm`;
- an actual bad-layout M=8 call that raises rather than falling back; and
- unmarked M=8 plus marked M=7 calls that issue exactly two incumbent BMMs and
  zero native MMs.

Timing is explicitly a **steady component screen**, not a cold measurement.
It uses 47 distinct 1.5 MiB weights per target cycle, totaling 73,924,608
weight bytes, so one repeated L3-hot tensor cannot determine the result. Each
arm gets 20 untimed cycles. The frozen measured order is 31 A-B-B-A blocks
with 64 complete 47-layer cycles per arm and a 128 MiB eviction touch once
before every arm.

On **every** physical card, not merely in a four-card average, the candidate
must:

- win at least 28/31 paired blocks; and
- save at least `0.15 ms` at the median complete 47-layer cycle.

The analyzer requires exactly ranks 0-3, four distinct UUIDs and BDFs, one
boot/source/binary identity, and identical cross-card fixture/output
aggregates. It independently regenerates all 128 expected CPU fixture hashes,
checks every reported control/candidate boundary digest pair, verifies the
32 replay entries, and recomputes every A-B-B-A average, win, median, and
threshold from the recorded arm times. It does not claim to rerun tensor
execution from JSON.

Every card command must pass harness SHA
`df8496f1f405e8b786dff0b96b7c320944c5d0133cce0bfcc2e36150ab1e0f12`;
the aggregate command must pass analyzer SHA
`945810c50eeeea99f532c3e62ee5bf289677e3706d80965f966400bfab35911b`.
One mismatch, nondeterministic replay, source-path failure, failed card, or
missed timing threshold classifies the treatment
`component_failed_stop_before_counters`. No current component output
authorizes counter execution or an endpoint.

## Future cold hardware-counter contract

The current harness modes named `counter-fixture-control` and
`counter-fixture-candidate` are explicitly direct-call fixture generators.
They do not launch `unitrace`, implement A-B-B-A pairing, analyze metrics,
evaluate a counter gate, or authorize counter execution.

Only a passing four-card aggregate authorizes construction of a dedicated
counter runner and analyzer. Those tools must then be source-frozen,
hash-pinned, statically validated, and independently audited before any
counter capture. The following acceptance contract is frozen now to prevent
hindsight changes: collect two independent matched A-B-B-A counter pairs on
every card with the pinned local `unitrace` ComputeBasic metric-query tool.
Each arm uses a 128 MiB eviction touch before each of 13 completion-bounded
selected calls and the same rank-invariant fixture; discard the first two
selected queries and analyze the remaining 11.

The pinned profiler identity is:

```text
/home/steve/src/pti-gpu/build-unitrace/unitrace
source commit: a5bab309f4ffdd78bd127035c46f5f75371160f8
binary SHA-256: 5aaca1f418a212a1d298cac27afb6c471bf1fcf47a1622e0c20d1a2cf43fc85a
```

Every card must satisfy all of:

- candidate GPU time is lower in both matched counter pairs;
- aggregate candidate GPU time is lower;
- GPU and load/store-cache read bytes regress by no more than 2%;
- XVE stall rises by no more than 0.5 percentage point;
- XVE active and thread occupancy each fall by no more than 0.5 point;
- result-validity, query-split, overrun, lost/inconsistent-report, spill, SLM,
  and partial-write proxies remain zero; and
- control/candidate outputs remain raw exact with the component result.

Failure is `counter_failed_stop_before_endpoint`. Steady component timing
cannot override a cold-counter failure: the prior native-M8 attention MM
experiment looked faster in hot timing, slowed three of four cold query
families, and regressed 3.79% at the endpoint.

## Endpoint boundary

Passing the later dedicated counter gate authorizes only construction and
audit of a separate frozen endpoint preregistration. It does not itself
authorize model generation. That later protocol must retain the current
record's local-NVMe model and artifact paths, exact shared-elementwise +
QKNorm/RoPE stack, DFlash depth 7, canonical q=1 teacher, 13 unique cold
prompts, one request each, cache-zero, no warmup/history/reuse, long-next,
rollover, one active generation, new service per leg, fixed idle gaps, and
A-B-B-A early-stop rules.

At minimum, its A1/B1 continuation gate must still require candidate headline
greater than control, at least 9/13 row wins, positive paired median, at least
`0.15 ms` target-cycle saving, and absolute acceptance-rate delta at most
`0.001`. Any miss forbids B2/A2, a payload, and submission. A record additionally
requires the conservative lower candidate to exceed the approved
`33.89498511171744 tok/s` row `cmrx6p5dv001bo4017hb7sixz`.

## Storage and exclusions

All live model, cache, temporary, log, counter, and result I/O must remain
under `/mnt/fast-ai` on internal NVMe/ext4. The external Corsair volume is
backup-only and must not be read or written by this experiment.

Do not enable the rejected shared auxiliary stream, known-negative attention
MM, failed BF16 router, N128 routed-W1, remote-route zero, fused transaction,
or graph candidates. Do not expand this treatment to gate/up or all-three
shared projections after observing component performance; that would require
a distinct preregistered experiment.
