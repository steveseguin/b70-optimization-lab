# Packet53 independent source review

Reviewed the candidate header, independent CPU proof, native benchmark,
production fixture/control bindings, build/source closure, CPU gate, seal,
coordinator supervision and evidence parser. The reviewer performed read-only
inspection and wrote this review; no compiler, CPU test process, GPU program,
health probe, service or oracle was launched by the reviewer. Build and test
outcomes belong to the retained preparation receipts, not this source review.

## Arithmetic and scheduling

Each physical lane owns V consecutive logical lanes as separate FP32 chains.
Their indices remain `256*t + 8*logical_lane + j`, with j increasing from zero
to seven. Register reductions perform exactly the first log2(V) levels of the
production adjacent tree; subgroup reductions perform the remaining levels.
The K=640 tail skips the absent third step for logical lanes16–31. Gate and up
retain separate accumulators, share only activation reads, and use distinct
weights. Strict no-fast-math/no-contraction flags are present on new host and
device compilation; retained supporting objects are checked for those flags.

Persistent scheduling has64 groups of256 work-items, eight SG32 per group.
Each subgroup owns V adjacent output rows and advances by the complete grid
stride. The loop predicate uses the subgroup's first row. Padded row lanes
still execute its shuffles. The full2048-word IQ2 codebook is copied once per
SLM workgroup and the barrier precedes the row loop. Every work-item reaches
that barrier. Two32-bit indexed gathers preserve the production table bytes.
Actual bank conflicts, register pressure, device shuffle execution and compiler
address-space lowering remain device questions; source review establishes no
speedup.

The CPU proof separately decodes compact planes using the normative byte
tables and traverses scalar K positions. It compares raw FP32 logical chains,
full trees and BF16 results with production and shared candidate functions.
Direct paired gate/up checks cover distinct weights. The full codebook/index
and sign census, scale boundaries, cancellation/signed-zero cases, reordered-
tree negative control, real-stride routed samples, persistent padded coverage
and whole-host-kernel route/error comparisons are present. This independently
written gate is stronger than comparing candidate BF16 outputs with themselves.

## Production controls and native evidence

The unchanged controls are packet48b's paired IQ2_S K2560 and IQ4_NL K640
kernels, selected through packet51's production fixture. Both classes assert
ten routes and512 experts. Gate/up has640 rows per expert and down has2560.
The fixture uses actual compact strides and512-expert banks, with ten distinct
IDs changing across four activation/route snapshots. M2 runs two independent
serial rows. It does not share a weight-read kernel between token rows.

Before every candidate/control arm, scoped input, route, output, status,
active and error allocations are restored. Down uses the correct slot-specific
activation offset. Exact windows evaluate the unchanged CPU production lane
and tree functions, execute the production kernel, then compare every candidate
to both captures. CPU reference evaluation and readback are outside timing.
The independent standalone proof qualifies those production decoder/order
functions separately; the full harness reference does not call p53 arithmetic.

Gate/up captures both complete BF16 outputs, both ten-entry status arrays and
the sticky error word: five buffers/25684 bytes. Down captures output, status
and error: three buffers/51244 bytes. The admitted device fixtures are finite,
active and valid-route cases. Invalid/shortened/nonzero-start routes and
inactive/sticky-error cases are CPU controls; they are not represented as
additional device coverage or a complete model-quality gate.

The native loop emits60 exact comparisons per owner: ten class arms including
controls, two fixtures, and three token rows across M1/M2. Timing emits10080
records/events: eight candidate pairs, two arms,210 iterations, and three token
rows. Control/candidate order alternates by iteration. Event durations cover
the entire compute kernel, including SLM fill and persistent loops; copies,
CPU evaluation and readback are excluded. Only the first ten iterations are
warmups, leaving200 paired samples. These repeated synthetic operator fixtures
are explicitly screening evidence, not a model-throughput benchmark.

## Closure and coordinator admission

The serial build reuses hash-checked historical objects only after relinking
the original command into this packet reproduces the retained baseline binary.
The source closure covers the original and checked baseline source, p51 fixture
and controls, p48 formats/control, new header/benchmark/proof, directory and
rope inputs, and build helpers. Host artifacts include both benchmark and
proof binaries. Intel host recompiles the new source while reusing historical
GNU support objects, as documented. CPU receipts bind both compilers' proof
binaries and fresh runs, plus two complete60-case host harness runs.

The final seal checks source, binary, build receipt, CPU evidence and Python
gate hashes, and freezes packet-root source, scripts, manifest and Markdown.
Final documentation therefore must precede the seal. Cleanup is restricted to
this packet's regenerable objects/dependencies and hash-verified own scratch
copies. Preparation is serialized at nice19 on the allowed cores, with the
1GB build limit and18GB free-space admission floor.

The wrapper requires its own coordinator user unit, card0, a supplied past UTC
fault-review boundary, a closed environment, completed CPU seal and a new
output directory. The native device setup additionally verifies PCI
0000:23:00.0. Passive Xe-client admission, memory/storage checks, ongoing
specific kernel-fault detection, cooperative SIGTERM and retained undrained
owners are present. It neither resets devices nor restarts failed windows.
The packet52 PF_EXITING fix is retained exactly and the corrected memory
sensor is passed explicitly to the inherited supervisor. The2880-second
watchdog covers four times the12-minute upper timing estimate; native deadline
2820 seconds leaves time for cooperative exit.

Timing admission rehashes both exact windows and their complete native evidence,
then revalidates exact case inventories and output identities. Final combination
rehashes both timing windows, reparses their native events and rechecks the same
exact companions. Different fresh process identities, the same seal/binary,
card, boot, environment and fault boundary are mandatory.

The parser crosslinks candidate hashes to the actual production control for
the same class, fixture and serial row. A self-consistent candidate/CPU hash
claim cannot bypass this check. The common selection maximizes each class's
lesser-owner M1 saving, retaining the zero-saving control option. Both owner
sums must reach30us; M2 cannot qualify. All candidate regressions remain in the
reported owner summaries. No oracle or integration job is started.

## Corrections and remaining gates

The initial manifest's128 work-items disagreed with the header's256 and has
been corrected. A duration paragraph attributing packet52's completed windows
to packet53 was also corrected. The initial CPU proof failed because the
production `tree32(float*)` helper mutates its input array; later virtual-tree
checks inadvertently reused the mutated lanes. The corrected proof calls that
helper through a by-value array wrapper, preserving the original lanes and
removing function-argument evaluation-order dependence. The failed receipt
must remain retained; it is a proof-harness failure, not a device result.

No arithmetic, route-binding, capture or coordinator-admission blocker was
found in the reviewed implementation. Final CPU/Python receipts and the seal
must pass before handoff. Device E1/E2 and T1/T2 remain entirely pending and
coordinator-owned; this review is not permission to infer their outcome.

## Parent verification after source review

The corrected GNU/Intel proof passed8,432,381 checks in each of four fresh
processes with one identical receipt/hash. Two fresh complete-shape CPU
harnesses each passed all60 M1/M2 production comparisons. One standalone GNU
AddressSanitizer/UBSan proof passed with the same hash and no sanitizer error.
The second fixture correction sequenced two RNG draws formerly placed in one
`ldexp` call; its mismatched prior receipts and source are retained. The
strict cross-compiler gate was preserved. These results come from
`cpu-gates.json`; the review agent did not execute them.
