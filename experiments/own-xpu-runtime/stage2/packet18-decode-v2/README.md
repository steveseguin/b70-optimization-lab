# Packet 18: chained decode on arithmetic v2

CPU-only preparation of our own runtime for the Unsloth Flash-Next UD-IQ3_XXS
**quantized compressed version**. No device binary ran. No speed is claimed.
The coordinator owns the separately admitted [W0/W1/W2/W3 windows](WINDOW.md).
Packet16 and historical packets13/14/15 are unchanged.

## Packet19 fault containment, CPU only

All snapshot bytes are initialized before capture. Device-computed indices are
checked before conversion and address calculation; invalid values set sticky
error and use a safe index or return before addressing. V2 math and table-based
RoPE are preserved in both the parallel adapter and serial Core.

The owner now rejects any dependency from another queue. Native pointer/event
registries independently enforce the same rule. Queue switches and every peer
copy drain both queues on the host and retire their events first, including
begin0/begin1/broadcast, all boundary/return fields and the final card1 commit.
The shutdown marker has an empty dependency list after host drain. Local
retirement clears the event-to-queue ledger. `queue_gate.py` runs at build time;
`queue-tests` exercises pending peer-copy and foreign-dependency rejection.
The [independent source review](review-queue-isolation.md) found cross-queue
event edges **[]**. This is conservative containment, not a proven repair of
the packet16 driver fault.

[Sanitizer mini](sanitizer-mini.json), [integration](sanitizer-integration.json),
[short real](sanitizer-real-short.json), [full real](sanitizer-real-full.json),
and [checker/index tests](sanitizer-unit.json) bind the CPU gates. Mini runs cover
both card counts and both non-GEMV modes under seeds 0, 1, 17 and 73; all buffers,
tokens and fixtures must match. The short real run covers positions 0 and 1 plus
a generated-token input at position 2 on two resident CPU owners, under all four
seeds. The full 87-position run compares the first token and 48 fixtures directly
to the v2 oracle. Native kernel internals and driver backing are not simulated.

The prepared W0 is weight-free and precedes the model windows. All windows refuse
NEO debug keys; W2/W3 add explicit host-shadow RAM admission and memory samples.
No device ran, and FAULT HALT remains in force.

## Arithmetic and construction

The graph, loader, GEMV kernels, frozen `r234-sg32-split4-bf16` reduction order,
R5 dense dispatch, 24/24 sequential layer placement and event owner come from
[packet16](../packet16-decode/README.md). The arithmetic identity is
`iq3-p17-detmath-v2`, exactly [packet17's authority](../packet17-detmath/arithmetic.json).
This is a new arithmetic identity, not a losslessness claim against v1 or FP8.
Both `--nongemv core` and `--nongemv parallel` use v2 exp/log/softplus,
IEEE sqrt, and correctly rounded division. The one rsqrt switch remains
`DETMATH_RSQRT_MODE` in packet17's included `detmath.hpp` (currently 1: barrier
between sqrt and division). No implicit contraction is enabled; detmath's
explicit FMA operations are deliberate parts of v2.

The [source provenance](source-provenance.json) records the original bytes
before adaptation. Local Core and parallel kernels differ from packet17 in
pointer plumbing, direct control bindings and tiny-model rotary geometry;
the real-model equations are unchanged. The synthetic NumPy graph remains
independent for orchestration and reductions but shares v2 elementary functions
through a CPU-only library. That scope is execution parity, not independent
proof of elementary arithmetic or of the model equations.

`rope.bf16` is the 524,288-byte, 4096-position host-generated packet17 table.
It is SHA256-checked before loading and uploaded once as a process-lifetime
model constant on each card. Each queued operation binds its owner's table;
streamed layer eviction cannot free it. It adds 524,288 bytes per card and no
per-token copy or launch. Tiny rotary dimensions select the corresponding
frequencies of the same table. The generating source and original hash are
recorded in provenance; regeneration never runs on a device.

[The link incident](../packet17-detmath/evidence/20261011-wb-a-link-flags/README.md)
showed that compile flags alone are insufficient. Every device translation
unit and the final link receive `-fno-fast-math -ffp-contract=off
-fdenormal-fp-math=ieee -foffload-fp32-prec-div -foffload-fp32-prec-sqrt`.
`build.py` checks the generated `link.txt` and compile commands. The CMake
build also runs a grep over the recursive local include closure, refusing
platform exp/log/pow/sin/cos calls. Neither configuration nor tests execute the
device binary or discover devices.

## Exact CPU gates

The v2 authority is the 87-token incident-retrospective prompt in
`experiments/qwen38-flash-next-ud-iq3xxs-b70/packet3-runtime-oracle/runs/arithmetic-v2-detmath-20261011/incident-retrospective/`.
Full-model frozen dispatch uses CPU one-card streaming; R5 uses two CPU owners
and resident weights (about 55.1 GB allocated, with a 70 GiB available-RAM
preflight). `cpu_gate.py --cards 1` keeps R5 bounded on smaller hosts.
Full-model frozen dispatch requires all 64 generated tokens and all 384 layer
fixtures (48 layers at each of steps 1–8). R5 requires at least eight tokens and
the same 384 fixtures. No tolerance is allowed. The first differing retained
layer boundary and BF16 value statistics are saved on failure; an unrecorded
inner site is never invented. Step1 means the final prompt position predicting
the first answer. Final CPU gates pass: **64/64 frozen tokens + 384/384 fixtures; 8/8 R5 tokens
+ 384/384 fixtures; 13/13 integration cases per non-GEMV mode; 150/150 GEMV
arithmetic comparisons; 4/4 owner-retirement checks; 7/7 deferred-chain checks;
39/39 window protocol tests; 2/2 deliberate wrong-fixture rejections**.
No device ran. CPU-only receipts and final counts are in `cpu-tests.json`,
`cpu-real-frozen.json`, `cpu-real-r5.json` and `build-receipt.json`.

Reproduction from repository root (two compilation jobs, two numeric threads):

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 \
 /home/steve/.venvs/vllm-xpu/bin/python -B \
 experiments/own-xpu-runtime/stage2/packet18-decode-v2/build.py --keep-build
```

The builder runs the sanitizer gates before the full CPU oracle gates. To run
them separately after the host build and input preparation:

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B "$P/depcheck_build.py" --source "$P" --tag sanitized
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B "$P/guard_tests.py"
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 /home/steve/.venvs/vllm-xpu/bin/python -B "$P/sanitizer_gate.py" all
```

Here `P=experiments/own-xpu-runtime/stage2/packet18-decode-v2`. The sanitized
builder is packet19's builder with an explicit packet18-local output root,
local retirement implementation and the reviewed CPU fatal-helper anchor.
It reads packet19 without writing there. Each sanitizer invocation chooses a fresh output root under build/; an explicit
`--run-root` must also be new. Existing evidence is preserved.
`build.py` refuses to seal without passing sanitizer receipts and an unchanged
instrumented binary/source manifest. Build the host prerequisites first with
`cmake -S "$P" -B "$P/build/host" -DOWN_RT_HOST_ONLY=ON` then
`cmake --build "$P/build/host" -j2`, using the same nice/ionice/OMP wrapper. If input is absent, run
`python -B "$P/prepare.py" --output "$P/build/input"` with that wrapper.
`--reuse-sanitizer-gates` is allowed only with the current instrumented binary
and its unchanged dependency manifest.
The default full CPU checks run frozen 64 and R5 eight.
The initial R5 streaming attempt was stopped cooperatively before fixtures to
avoid repeated dense-weight expansion; its interrupted receipt is retained. `--reuse-real-gates`
requires the identical host binary, prompt, oracle tokens and every fixture
hash. The builder removes completed test/model scratch; `--keep-build` retains
only compiled programs and coordinator inputs. No model server is involved.

## Launch census and byte census

Counts are calculated from the actual plan, not measured performance. Removing
the two control-copy kernels at each parallel site eliminates **1,190 native
launches per token**. The kernels now bind the existing active, position and
sticky-error allocations directly. The owner chain still orders every access;
parallel sticky-error accesses remain atomic. The reserved 12-byte compatibility
control allocation is counted even though the bridge launches are gone.

| Layer kind | Frozen core | Frozen parallel | R5 core | R5 parallel |
| --- | ---: | ---: | ---: | ---: |
| Ordinary GDN, layer0 | 49 | 49 | 44 | 44 |
| GDN with PLE, layer1 | 59 | 59 | 53 | 53 |
| Upgraded GDN, layer2 | 47 | 47 | 44 | 44 |
| QSA, layer3 | 53 | 55 | 46 | 48 |
| Whole token including head/control | 2421 | 2445 | 2157 | 2181 |

Frozen parallel was 3,635 in packet16; R5 parallel was 3,371. The three QSA
attention kernels remain separate, accounting for parallel's 24 extra launches
across 12 QSA layers. CPU mocks collapse multi-pass GEMVs into one host
operation, so their submission counts differ from this native census.
All GEMV kernels and trees are unchanged. Resident tokens now have **16 counted
host event waits**, or **18 while steps 1–8 snapshots are captured**. Four waits
upload the two token controls and embedding/PLE inputs. Twelve are schedule waits:
begin0 to begin1; begin1 to card0; card0 to the layer-23 boundary; four waits
between that boundary's five peer copies; card1 to the return; one wait between
the two return copies; commit0 to commit1; commit1 to card0 readback; and readback
completion. Snapshot readbacks add two. After each counted wait, event retirement
also calls `wait_and_throw` on both queues: 32 or 36 more native queue waits,
usually already complete. Total explicit native wait calls are therefore 48 or
54 per resident token, excluding load and shutdown. One-card streaming has
many weight-copy waits and is a correctness vehicle.

Context 256 includes the full prompt plus 63 continuation inputs. Calculated
bytes from [census.json](census.json), excluding unmeasured driver/JIT memory:

| Dispatch | First card GGUF weights | First card owned total | Second card GGUF weights | Second card owned total |
| --- | ---: | ---: | ---: | ---: |
| Frozen | 26,165,134,080 | 26,481,071,676 | 26,464,055,040 | 26,780,213,652 |
| R5 | 26,904,298,240 | 27,220,235,836 | 27,534,749,440 | 27,850,908,052 |

Add one 4,194,304-byte pinned host slab per card. The independent planner and
allocator both enforce 30 GiB per card. These totals establish no device fit.
The 256 MiB interpreter scratch remains in both modes. The 29,321,610,240-byte
embedding/PLE tables stay on the host; only requested rows are read and copied,
with that work included in wall time. Attention/recurrent storage stays BF16.

## Next launch reductions, ranked using packet15 timing evidence

These [planning weights](fusion-planning-weights.json) are from packet15, not packet18 measurements or speed
claims. Its measured route+gather was 0.230 ms/layer, GDN recurrence 0.109 ms,
QSA attention 0.144 ms, and elementwise kernels 3–7 us at roughly 30 us launch
overhead. The selected historical fixtures are route-varied, gdn-packed-1,
and qsa-attention-1; each has ten measured repetitions across two fresh owners.
Arithmetic v2 and different integration may change those costs.

1. Fuse HC combine with the following norm while preserving the intermediate
   BF16 store; up to two applicable boundaries/layer save roughly 96 launches
   per token (about 2.9 ms of launch overhead under the supplied 30 us assumption).
   The exact plan must establish eligible sites before implementation.
2. Fuse GEMV epilogues with their immediately following activation, and fuse
   adjacent elementwise stages. Several such boundaries per layer offer larger
   launch savings than tuning a 3–7 us elementwise kernel alone. Keep every BF16
   round and reduction tree explicit; re-gate every fixture.
3. Route+gather has a roughly 11.04 ms/token weight across 48 layers. A single
   work-group copies the 2560-wide input top-k times in packet15's fused site.
   Packet18 retains separate route and gather integration sites. Removing the
   redundant repeated input or distributing gather can matter more than saving
   its one launch; changing the expert-input ABI is deferred until exact gates.
4. GDN recurrence has a roughly 3.924 ms/token weight across 36 layers. Sharing
   Q/K normalization and decay across the 128 value rows could cut repeated work,
   but adds scratch/ordering and is not a trivial fusion. Preserve dot128 trees.
5. QSA attention has a roughly 1.728 ms/token weight across 12 layers. Fusing
   score/softmax/value removes at most 24 launches (about 0.72 ms assumed overhead),
   but requires a correct cross-work-group schedule or per-head work-group.
   Preserve score maximum, adjacent softmax sum and selected-order PV tree.

The 1,190 removed control bridges would correspond to 35.7 ms at the assumed
30 us overhead; that multiplication is not a predicted measured speedup.
Within-layer tensor parallelism, graph capture, timing and further merges are
not implemented here. Two cards still compute their half-models sequentially.

## Remaining device gates

W1 is this lane's first direct device-v2 exactness gate: eight tokens and 384
layer fixtures. W2/W3 require W0 and W1 on the same boot and binary, then 64 tokens
and 384 fixtures on two resident cards, with per-token timing and whole-wall-clock
decode over tokens 2–64. `--repeat-of` binds a fresh-process repeat; none is
queued automatically. Fixture overhead remains in timing. `ldd` checks loader
dependencies before any latch write. Compiler success and CPU parity do not
prove device math, peer transfers, resident fit, fresh-process determinism or
speed. See [independent review](review.md) and [closeout](CLOSEOUT.md).

Watchdog correction: [deadline audit](DEADLINES.md). The long CPU model/sanitizer gates are retained under the [explicit reuse proof](deadline-reuse.json); rebuilt canary, unit/mini and wrapper tests are fresh. No device ran.
