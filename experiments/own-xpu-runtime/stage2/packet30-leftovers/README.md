# Packet 30: exact leftover kernels, CPU preparation only

No device ran. No speed is claimed and no runtime dispatch changed. Arithmetic
identity remains `iq3-p17-detmath-v2`. The 19.63 tok/s two-card result and its
35 ms/token reference remain the recorded comparison, not a result of this packet.

## Designs and cost

The following times are historical group costs or **candidate hypotheses**, not
new measurements. Launch overhead alone is approximately 3.4–5 us; the cost of
an entire workgroup shape cannot be inferred from that floor.

| Class | Where the incumbent spends time | Candidate hypotheses, us/group |
|---|---|---:|
| Route, 69 us | Five range launches; repeated maximum/sum work; 512 squared stable comparisons | Two launches SG32, 1/16 groups: 18–65; WG64: 20–65; single SG32: 25–90 |
| QSA attention, 268 us in model | Three launches; score launch covers capacity/budget slots; value creates 6144 WG128 with selected-length local trees | Admitted-slot SG32 three launches: 100–220; score+softmax two launches: 90–220 |
| hc.a.gate / hc.f.gate, historical 30 us | 10240 rows, K320; 24 lanes idle in final tile; use packet28 wg32 incumbent | SG32 or four rows/WG: 18–28 |
| small.hc, 18.5 us | 324 WG128 split4 rows, local partials and a barrier | Single tuple, sequential original splits in each SG: 12–24 |
| small.ffn, about 31 us | Router, two shared projections and scalar; 1793 WG128 for Q6 tuple | Barrier-free compiled tuple, SG32/rows4: 20–40 |
| shexpdown, historical 16 us | 2560 Q8 rows, K640; 16 lanes idle in final tile; packet28 wg32 incumbent | SG32/rows4: 10–18 |
| attn.combine / ffn.combine + next norm, about 18.5 us | Elementwise BF16 combine, then two norm launches | Exact combined/norm outputs in one launch: 10–25 |
| hc norms, about 7.6 us | Two launches, partial square tree then upper tree and output | One SG/stream or replicated 256-output tiles: 5–15 |
| hc mixes, about 8.5 us | One WG128 elementwise launch, four ordered sigmoid products/output | WG32/WG128 direct output: 5–12 |

Read the proofs and exact launch geometries in [route](route-design.md),
[attention](attention-design.md), [small dense](small-design.md), and
[combine/norm/mix](fusion-design.md). In particular, the runtime route actually
has **five** launches: the supplied class receipt says 15120 launches / 3024
calls. The earlier three-launch design measured slower because its serial
work, local storage and barriers outweighed saved launches. This packet keeps
that negative result and times every alternative.

HC gate cannot merge with low/inject: it consumes the activated low output.
Likewise norm and mix have low/activation/gate dependencies between them.
Only combine followed immediately by norm is merged. The combined BF16 stream
and normalized BF16 output are both retained, so no rounding boundary disappears.
The sequential-split small-GEMV form is deliberately an experiment: the bounding
study found that serial splits can lose. New geometry and exact tuple workload
must pass G3; no previous negative result is described as a winner.

Packet29 owns the GEMV merge and expert down. GDN recurrence retains packet27's
qualified 34 us kernel; no new recurrence or expert kernel is claimed here.
Attention projections retain packet28's winners. No protected source was edited.

## G3 and qualification

[G3](g3.cpp) calls the runtime's actual packet27 adapter for route, attention,
combine, norm and mix; its actual small tuple submission for small.hc/ffn; and
packet28's `p28.dense.wg32` for gate/down. It uses the same baseline arithmetic
and packet27 compilation overlay in an ignored build mirror. Candidate kernels
are compile-time bodies; the host dispatches their names.

Each class compares candidate/incumbent **all semantic output bytes** on the
card and incumbent/host finite output bits. Scratch is not a model output:
attention compares output/error, and does not compare unused score suffixes
which the candidate never reads. Large payloads (>8 MiB) use eight separately
allocated full-size copies, rotated across 200 repetitions. No copy, allocation
or output readback occurs inside the timed launch loop. Every constituent GPU
event duration is retained and summed before median/p90. The sorted table uses
actual logical groups/token, retaining raw launches/token separately.

A baseline outside 15% of its in-model group duration is unrepresentative and
cannot admit a candidate. Gate/down now use packet28 winners: the supplied
in-model receipt predates those winners, so these rows remain diagnostic until
a matched post-packet28 in-model anchor exists. G2 timings are useful fixture
comparisons, not a substitute model anchor. Two fresh owners must agree exactly,
and every workload must beat its incumbent by 10% before a proposal is emitted.
Overlapping norm/fusion savings must not be counted twice.

The CPU gates exercise both host compilers with fresh processes, odd lengths,
stable route/selection ties, NaN routes, positions1/3/87/255 and full attention
budgets. Empty attention exposes an existing Core/incumbent disagreement:
Core rejects it, while incumbent and candidates leave outputs unchanged. This
is explicitly diagnostic, not a passing three-way quality claim or an admitted
runtime input. All valid finite fixtures must match three ways.

Independent reviews: [route](review-route.md), [attention](review-attention.md),
[small/fusion](review-small-fusion.md), [write races](review-races.md), and
[harness](review-harness.md). Receipts are in [build-receipt.json](build-receipt.json)
and [cpu-tests.json](cpu-tests.json). See [WINDOW](WINDOW.md),
[DEADLINES](DEADLINES.md), [INTEGRATE](INTEGRATE.md), and [closeout](CLOSEOUT.md).

## Rebuild without running a device

Run each command sequentially from the repository root. Every build runs one
compiler job; the scripts cap their own address space at8GiB. The device mode
compiles and links only. `family_gates.py` and the host modes execute CPU binaries.

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B experiments/own-xpu-runtime/stage2/packet30-leftovers/family_gates.py
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B experiments/own-xpu-runtime/stage2/packet30-leftovers/build.py host
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B experiments/own-xpu-runtime/stage2/packet30-leftovers/build.py icpx-host
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B experiments/own-xpu-runtime/stage2/packet30-leftovers/build.py device
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B experiments/own-xpu-runtime/stage2/packet30-leftovers/finalize_cpu.py
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B experiments/own-xpu-runtime/stage2/packet30-leftovers/build.py seal
```

The build mirror preserves original files and applies the recorded incumbent
packet27 overlay. Finalization runs CPU protocol tests and ELF `nm`/`ldd` only;
it never executes the native binary. [Family evidence](family-gates.json) retains
compile/link arguments and both fresh-process outputs. [Raw CPU/build logs](cpu-evidence.json.gz)
are compressed losslessly; generated objects/mirrors are scratch, not evidence.
