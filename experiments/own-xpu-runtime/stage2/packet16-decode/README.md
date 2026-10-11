# Packet 16: chained decode preparation

CPU-only preparation for the separate Unsloth Flash-Next UD-IQ3_XXS **quantized
compressed version**. **No device ran and no decode speed is claimed.** The
coordinator's W1/W2/W3 commands are in [WINDOW.md](WINDOW.md). The completed packet13 device baseline differs from the CPU oracle in
48/48 step-1 layers (token 332 agrees); [existing-file comparison](baseline-admission.json).
W1 may compare against that device control, but W2/W3 still require exact
CPU-oracle parity. Device exactness,
resident fit, fresh-process repeat and timing are still required.

## Change from packet13

The full graph, bounded GGUF loader, 24/24 sequential placement and default
GEMV dispatch come from [packet13](../packet13-integrate/README.md). Arithmetic
identity remains `iq3-p13-r234-sg32-split4-bf16-v1`. `--nongemv core` selects the
original packet4 interpreter; `--nongemv parallel` selects packet15's parallel
kernels through [adapter.cpp](adapter.cpp). Remaining integration operations
(routing, gather, combine, PLE, sampling and controls) have direct parallel
translations. The tiny model uses dimensioned parallel equations as well;
there is no hidden interpreter fallback in parallel mode.

Non-GEMV control bridges copy position/active/sticky error to packet15's
contiguous control slot, run the kernels and merge error back. These add two
small submissions per packet15 site. Expert status checks remain device
operations and fold errors into the same sticky flag. Errors are never cleared
between sites. `--checked` additionally reads it after each completed layer.
Default execution reads it once per token, packed with the generated token ID.

Every compute and copy joins the same owner event chain. One Device/Arena owns
both queues and their shared Level Zero context. The peer transport is the
packet12 path through packet14's range-aware context implementation, adapted
to this single ledger. There are **two logical handoffs per token**: five peer
copies after layer23 (20,480-byte streams and four 4-byte controls), then two
4-byte result/error copies after the head. There is no per-layer handoff or
host bounce, and no host wait at either handoff. Capability queries happen only
when a separately authorized native process starts, never during CPU building.

The local owner raises the bounded ledger to 16,384 events and permits queued,
explicitly chained copies. It still rejects freeing busy allocations. Profiling
is collected after the terminal token event and before event retirement. A
native fault retains ownership for coordinator recovery; a 60-second drain and
one SIGTERM do not promise that a hung driver process exits. The three
independent review summaries are retained in [review.md](review.md).

## Resident storage

Context256 holds the 87-token prompt plus 63 continuation inputs. Exact calculated
bytes from [census.json](census.json), excluding unmeasured driver/JIT storage:

| Dispatch | Card2 weights | Card2 total owned | Card3 weights | Card3 total owned |
| --- | ---: | ---: | ---: | ---: |
| frozen | 26,165,134,080 | 26,480,547,388 | 26,464,055,040 | 26,779,689,364 |
| r5 | 26,904,298,240 | 27,219,711,548 | 27,534,749,440 | 27,850,383,764 |

There is also one 4,194,304-byte pinned host slab per card. The planner prints
these counts and refuses above 32,212,254,720 bytes (30 GiB) per card. The allocator
independently enforces the same cap. These are calculated allocations, **not
measured fit**. The 256 MiB interpreter scratch remains allocated in either mode.

As in packet13, “resident” covers all compute weights, not the 29,321,610,240-byte
embedding/PLE lookup tables. Only requested lookup rows are read on the host.
Their IDs are computed before each token from its known input/history; the
unchanged device PLE hash still updates its state. Two bounded uploads stage
those rows at the token boundary, avoiding device ID readbacks during the graph.
This host lookup work is included in wall timing. Routed expert IDs stay on
device in resident mode. One-card mode still reads them and streams the selected
packed expert banks; it is a correctness vehicle, not the speed target.

`--gemv frozen` is exactly packet13's dispatch. `--gemv r5` expands only qualified
quantized dense matrices, keeps the F32 router constant split4, uses expanded
SG32 for the head, and keeps experts packed SG32. Expansion uses bounded row
chunks and the repaired packet10 decoder. **R5's actual timed layer code preserves
each shape's frozen SG32/split4 choice**; its two named modes differed at the
head. Applying split4 to every dense shape would change v1. Thus this packet
implements the measured, identity-preserving winners, not that unsupported
interpretation. The complete per-tensor choices are in the census.

## Launch and wait census

Native submission counts derived from the actual plan, excluding copies:

| Work | packet13/core kernels | packet16/parallel kernels |
| --- | ---: | ---: |
| ordinary GDN layer 0 |49|73|
| GDN with PLE layer1 |59|91|
| upgraded GDN layer2 |47|71|
| QSA layer3 |53|81|
| full token, including head/control |2,421|3,635|

These are frozen-dispatch counts. R5 core/parallel counts are 44/68 for an
ordinary GDN layer, 53/85 for PLE GDN, 44/68 for upgraded GDN, 46/74
for QSA, and **2,157/3,371 per full token**. Expanded split4 reduces
inside one launch, saving 264 launches relative to frozen dispatch. CPU mocks execute a split GEMV in one
host operation, so their `kernel_submissions` are mock counts, not native counts.
The parallel path has more launches but removes serial one-work-item execution
of large non-GEMV sites. Kernel speed is still unmeasured here.

Packet13's resident path has 1,869 finish waits and 1,825 error readbacks per
position: 3,694 before lookup/input/output and fixture transfers. With its
48 layer readbacks, two token uploads, two lookup readbacks/uploads, seven bounced
copies and final token readback, the full generated-position count is 3,763
explicit waits. Packet16 resident has **five explicit waits per token**: two
token uploads, two pre-staged lookups, and one terminal error/token readback.
The first eight generated positions additionally read two snapshot slabs,
so those positions have **seven**. `--checked` adds 48 layer error waits and
48 layer drains when work is pending. Copy-engine retirement invokes queue
synchronization only after its tracked event has already completed; the counter
means explicit bounded event-completion waits, not every already-idle API call.

First-eight fixture capture submits 48 asynchronous D2D layer snapshots. There
are also seven peer copies and two terminal D2H copies per token. The snapshots
are read, hashed and written after the token fence. Their overhead is honestly
included in measured rows and in the whole decode span; it is not hidden warmup.
After step 8, snapshots and their two host waits disappear. Prefill head/mixer
predictions that are never consumed are omitted; all prompt layers still run.

## Timing and gates

`--stage decode --prompt-tokens FILE --max-new N` emits greedy tokens without
warmup or reuse. `timings.jsonl` has exactly one generated-token row per output;
`prefill-timings.jsonl` contains prompt rows and `sites.jsonl` diagnostic site
submission rows. CPU device times are null. Native rows record wall time,
GEMV/non-GEMV device duration, transfer wall time, kernel submissions and waits.
`transfer_wall_ms` includes synchronous transfer waits and the final queued
readback's completion wait, which can overlap remaining compute; it is not an
additive decomposition of wall time. Device kernel intervals stay within one
card's clock, even though the global event chain crosses cards.

The receipt's `prefill_ms` covers the full prompt, including the last position
that emits token 1. `first_generated_token_ms` separately identifies that final
position's time (it overlaps prefill). `decode_wall_ms` is a steady-clock span
around tokens 2..N, including required host work; `(N-1)*1000/decode_wall_ms` is
reported as `decode_tok_s`. No summed kernel durations determine that rate.
Early EOS is retained and fails a window requiring 64-token coverage.

The CPU result files are [cpu-tests.json](cpu-tests.json),
[cpu-real-frozen.json](cpu-real-frozen.json) and [cpu-real-r5.json](cpu-real-r5.json).
Final CPU gates pass: **13/13 original integration cases per non-GEMV mode**,
**75/75 frozen + 75/75 R5 arithmetic comparisons**, **4/4 owner retirement**
and **7/7 deferred-chain checks** (5,000 queued copies), and **21/21 window
protocol tests**. Each full real-model dispatch matches **384/384 layer hashes
and 8/8 tokens**: `332, 37947, 1653, 10082, 3508, 8812, 25, 23288`.
First-step coverage is 48/48 layers and token 332. All 64 CPU output tokens
were not tested. Additional [R5 mini cases](cpu-r5-mini.json) pass 12/12
(46,476 exact values); [wrong-fixture rejection](cpu-mismatch-rejection.json)
passes in both modes. IntelLLVM 2026.0 compiled and linked the native binary;
it was never executed.

They bind the actual host binary, unchanged prompt, token sequence and each
retained oracle fixture hash. The mini-model tests use the original independent
NumPy equations. The full oracle shares frozen arithmetic; this is execution
parity, not independent proof of the model equations. Host GNU scalar libm and
SYCL device elementary functions still require the exact device gates.

CPU reproduction, from repository root:

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 \
  /home/steve/.venvs/vllm-xpu/bin/python -B \
  experiments/own-xpu-runtime/stage2/packet16-decode/build.py --keep-build
```

The builder uses at most two compile jobs and two numeric CPU threads. It never
executes the device target, even for version/help. Default real CPU coverage is
eight generated tokens per dispatch; `--max-new 64` expands it. Existing exact
real gates can be reused only with the matching host binary and oracle through
`--reuse-real-gates`. Default cleanup removes scratch; `--keep-build` retains
only reconstruction artifacts and coordinator inputs, never completed CPU runs.

## What limits speed next

Device parity comes first. The existing packet13-vs-CPU discrepancy already
shows that matching eight output IDs is insufficient; first differing layer 0,
element 2 is retained in baseline-admission.json. If it passes, this sequential split keeps only one
card computing at a time. Thousands of submissions and control bridges remain;
fusing compatible parallel sites or capturing a complete token is the next
host-overhead lever. Dense/packed-expert bandwidth, the full output head and
bounded host lookup work remain. Within-layer TP belongs to packet14 and is
not implemented here. The 28.49 tok/s llama.cpp two-card reference has different
arithmetic authority; no speed or quality equivalence is inferred from it.
