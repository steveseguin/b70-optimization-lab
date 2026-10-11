# Packet 26: specialised exact kernels and a cheaper host issue path

CPU preparation of our own runtime for the Unsloth UD-IQ3_XXS **quantized
compressed version**. Arithmetic identity remains `iq3-p17-detmath-v2`.
No device binary ran in this preparation. No model speed is claimed. The
coordinator owns the separately admitted commands in [WINDOW.md](WINDOW.md).
The reference to beat is 28.49 tokens/s, about 35 ms/token.

The starting point is committed packet18-decode-v2, pinned in
[source-proof.json](source-proof.json). Its numerical kernels, R5 GEMV choices,
24/24 sequential layer placement and cross-card host fences form the control.
The ordered allocation lookup and token/class timing follow the coordinator's
[packet 18 scratch experiment](../packet18-decode-v2/evidence/20261011-host-bottleneck-location-scan/README.md).
That experiment measured about 12 tokens/s with unchanged output; its evidence
is not a packet 26 measurement.

Packet 23/24 contribute bounded failure reporting, K0 kernel compilation,
checked by-value captures, explicit entry returns, deadline separation and
closed environment handling. Their Batch/Chain kernels and device parameter
blocks are excluded. Packet 24's adjacent-tree decomposition is used in
dedicated per-operation template kernels. The default dispatch selects packet
18 everywhere. [dispatch-all-new.json](dispatch-all-new.json) is a test choice,
not an admitted deployment choice.

## Arithmetic and per-class design

The proof reference is [packet 24's tree derivation](../packet24-kernels/README.md#exact-reduction-decomposition)
and the frozen v2 Core. Complete aligned power-of-two subtrees retain their
original additions; their roots feed the original upper tree. Incomplete tails
execute the original missing-right `+0` at each occupied level. No associative
sum, implicit FMA or different intermediate precision substitutes for those nodes.
BF16 stores between combine and norm, value and gate, recurrent updates and
rotary stages remain explicit.

| Class | Candidate work | Expected GPU microseconds, hypothesis only |
| --- | --- | --- |
| route and gather | Stable score/index rank, original softmax tree; routed consumers can read one input row | 4–12 per stage |
| attn.combine, ffn.combine and following norm | Independent BF16 combine elements, complete squared-value subtrees, original upper norm tree | 8–24 per combined group |
| standalone gather | Independent copied elements and uniquely owned route triples | 4–8 per stage |
| streams and PLE add | Independently owned output elements, exact BF16 stores | 4–8 per stage |
| HC/final/PLE norms | Complete squared-value subtrees and private upper-tree evaluation | 8–24 per group |
| gdn.recurrence | Shared per-head preparation then disjoint recurrent state rows; original four-products-per-lane dot and 32-lane tree | 10–30 per group |
| qsa.prepare and pool | Subtree norms, independently owned coordinates, original BF16 rotary operands | 8–24 per group |
| qsa.select | Independent block scores then stable rank | 8–24 per group |
| qsa.attention | Dedicated scores, max/exp/sum stages, and value subtrees | 24–80 for all stages |
| argmax | Independent chunks then earliest winning index | 10–30 per group |
| streams, ple.add | Dedicated element copies and original nested BF16 add | 4–8 per group |
| gdn.norm | Original128-wide squared-value tree followed by gain and sigmoid | 4–12 per group |
| GEMV classes, including `attention` | Proven packet18/R5 arithmetic; host-selected formats, by-value bounded captures | No new expected gain assigned |

`attention` in the class trace is the output projection GEMV, not the QSA
softmax. Logits, expert GEMVs and other long projections remain measured
baseline work. Future packet25 kernels are linked through the by-value [packet25 bridge](p25_bridge.cpp); the supported names are `p25.rows4`, `p25.scale8`, `p25.wide8`, `p25.wg32`, `p25.private_decode` and `p25.paired_input`, restricted by type and frozen arithmetic. Table edits use the class dispatch registry and must
pass K1/K2 under their own linked identity before selection. Packet25 half-table/staged candidates are not linked and are rejected. [Nonfinite GEMV inputs](NONFINITE-GEMV.md) remain unqualified; required NaN-route exactness remains in K1.

K2 records 200 repetitions of each old/new class, each event's GPU execution
timestamps, exact byte comparisons, median and p90. Nonpositive durations are
counted and excluded; an affected multi-stage repetition is excluded as a whole.
More than 1% invalid rows fails the window. New wins only below 0.9× the old
median complete execution sum. Failed candidates are recorded and excluded while the rest of K2 continues. The complete table is always written after a completed run; only a passing K2 receipt admits it.
For a GEMV class covering multiple formats, every registered workload must clear that threshold independently. Model windows consume the hash-bound measured file. Its schema is
`packet26.dispatch.v1`, with separate `classes`, `fusions` and `gemv` maps. A
folded pair needs its own measured win. The 36-workload K2 registry includes actual
adapter pair timings; shape-equivalent diagnostic kernels cannot admit a different
production kernel. Six independent norm labels share the identical measured
four-by-2560 workload, as documented in WINDOW.md.

K1 covers 92 non-GEMV fixtures (72 original and 20 odd-width/unit cases), 44 actual
adapter cases, and 136 GEMV arm checks (17 workloads, four input/scale modes, two
implementations). These are coverage counts, not an assertion that an unfinished
run passed. Requested packet25 candidates must preserve the same sealed fixture
bytes; their input table hash binds K1a/K1b/K2 separately from K2's output table.

## Host path

The ordered pointer lookup replaces the linear allocation scan. Allocation
bindings and plan-site matrix/specification records are resolved ahead of the
steady-state submission loop. The owner uses bounded/reserved dependency and
event storage and invalidates cached bindings when an allocation is released.
The in-order native queue does not receive a redundant dependency on its own
previous event. Cross-card transitions still drain on the host and reject
foreign events. Dynamic streaming bindings retain validation.

[host-issue-benchmark.json](host-issue-benchmark.json) compares the same 2,181
submissions, 19 bindings and 3,000 allocations with packet18 and packet26 owner
code using a CPU mock. Its numbers measure our bookkeeping only. W2 must prove
`enqueue_loop_ms` on the cards; the target is at most 12 ms/token. Every token
row also reports `prepare_ms`, `wait_ms`, and transfer counts by direction.
Token timing creates queues without profiling and makes no timestamp queries.
Class timing is explicitly marked profiling and sums event execution times.

## Gates and evidence boundaries

The exact oracle is
`experiments/qwen38-flash-next-ud-iq3xxs-b70/packet3-runtime-oracle/runs/arithmetic-v2-detmath-20261011/incident-retrospective`.
The CPU gate uses one streaming owner for eight generated tokens and 384 layer
fixtures, never a resident real-model CPU pair. Unit/lifetime tests, mini models
with both card counts, core/parallel modes, three timing modes and both dispatch
choices precede it. GNU and Intel host fixture gates run in fresh processes.
Sanitized mini runs shuffle work-item order under four seeds. Device compilation
is compile-only; all native entrypoints share the same compiled image set as K0.
All captures are mechanically checked at 1,024 bytes, with a negative oversized
control. Compile and link precision flags and recursive math grep are mandatory.

Historical packet18 receipts apply only to the default control, under the
arithmetic/schedule carryover proof. They cannot qualify the new dispatch or the
new owner on a device. The coordinator must run K0/W0 then W2; W2m additionally
requires two fresh K1 owners and K2, all on the same boot and binary identity.
W1 remains available but is not a prerequisite for W2.

[Build receipt](build-receipt.json), [independent arithmetic review](bit-identity-review.md),
[independent race review](review-races.md), [final bridge review](review-bridge-addendum.md),
[closeout](CLOSEOUT.md), and [deadlines](DEADLINES.md) retain the evidence and limits.

The preserved schedule exceeds two total copies per card/token. [Copy accounting](copy-budget.json) separately verifies at most two H2D control uploads per resident card/token and zero kernel-parameter uploads per launch. Peer, local snapshot and D2H readback copies remain explicit; the literal total-copy gate is not claimed.

K1's receipt retains the configured `repetitions=200` K2 option for schema compatibility; K1 itself runs each fixture once per fresh process. Only K2 executes the 200 repetitions.

Rebuild and reproduce the CPU gates with:

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 /home/steve/.venvs/vllm-xpu/bin/python -B experiments/own-xpu-runtime/stage2/packet26-specialised/build.py all
```

`all` prepares input manifests/fixtures, builds GNU host, Intel host, ASan and
native executables, runs only host gates and seals the receipt. Each build uses
one compile job. Ordinary children have an 8 GiB address-space cap; sanitizer
runs use a separate 8 GiB RSS guard because ASan reserves a large virtual shadow.
Native executables are compiled and inspected only. Individual `prepare`, `host`,
`icpx-host`, `asan`, `device`, `cheap`, `real` and `seal` stages are available.

Final CPU results: five unit suites, 156 integration cases, four fresh
fixture processes (GNU/Intel, twice each), 32 sanitized mini runs,
61 wrapper tests and 1056 symbolic tree checks passed. Each fixture
process covered 92 non-GEMV fixtures, 44 adapter cases and 136 GEMV arm checks.
All 384 layer fixtures and all eight generated tokens matched the v2
oracle under all-new dispatch. The streaming oracle used 907872 KiB peak RSS.
The native build has 165 checked capture instantiations, maximum
744 bytes. The first device K1a cleanly refused a dense fixture geometry; see the R2 repair below. Exact identities and scope limits are in
[build-receipt.json](build-receipt.json) and [cpu-tests.json](cpu-tests.json).

## R2 CPU repair after the K1a refusal

The first dense workload, `gdn.qkv.q6`, reached packet 10 expanded GEMV through
R5 with a nonzero status allocation. Dense kernels require status=0; status
belongs only to routed expert matrices. Both old/new dense arms now leave it
zero. Packet 10 validation is unchanged. The CPU arithmetic twin previously
checked byte extents but skipped the device geometry, alignment and alias checks.

`validation_mirror.py` compiles the verbatim device validation prefixes for
packet 10 dense, packet 9 expert and packet 26 non-GEMV entries into the CPU
fixture twins. Packet 25, specialised and adapter checks already share their
entry code. The mirror asserts its extraction/injection anchors and records its
source hashes. Hardware capability queries remain device-only; no discovery is
part of a CPU gate.

`validation_gate.py` runs both fixture executables with both host compilers,
all K1 modes and actual K2 shapes, all registered classes and every linked
candidate allowed by each format. Validation-only skips arithmetic, never
claims exactness and retains the real allocation extents. Reintroducing a dense
status buffer must fail both K1 and K2 on CPU. Injected failures in three classes
must still reach logits. Ordinary fixture gates still compare all output bytes.

The wrapper records matching wrapper/native nice values, default 19. W2/W2m/W2c
are documented at nice 0; CPU helper processes run at 19. K windows remain at 19.
**The previous seal's K0 and W0 receipts are void.** Preserve the old a-/b-
receipts and use the fresh `-r2` commands in [WINDOW.md](WINDOW.md).
