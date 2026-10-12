# Packet 29: merged exact runtime

This packet targets the Unsloth UD-IQ3_XXS quantized compressed version of
Qwen3.8 Flash-Next, with its own arithmetic oracle.

CPU preparation only. No device ran and no speed is claimed. Arithmetic remains
`iq3-p17-detmath-v2`; output bytes must match the v2 CPU oracle without tolerance.
The source starts from committed packet27-round2; `source-proof.json` records every
copied byte and commit. `p28/source-proof.json` records the imported kernel bytes.

This runtime links R5, packet26's selected non-GEMV paths, packet27's alternatives,
packet28's dense/private/shared/paired GEMVs and two new expert-down kernels.
`kernel-registry.json` is the complete per-class list. `dispatch-default.json` is
packet26's measured selection. The all-new map exercises packet28 and packet29;
it is a test map, not a claim that every entry is faster.

## Expert down

`p29.down.wg32` uses one subgroup per row; `p29.down.rows4` uses four independent
subgroups per work-group. Both compile the actual 2560 by 640 per-expert shape.
Each lane processes eight adjacent weights in each 256-weight tile in precisely
the R5 order. It reads the 32-weight block's FP16 scale once, converts it once,
loads each nibble byte, reads the signed byte level from the 16-entry IQ4_NL table,
and evaluates `(scale * float(level)) * input` before the unchanged sequential
lane addition. The 32-lane reduction and BF16 rounding stay unchanged.

The actual R5 IQ4 kernel already uses byte code and level-table loads and
converts a scale once per eight-weight decode, with subgroup sharing between
scale owners. The new candidates remove that sharing, generic format/control
work and native-width numerical loop indices. They do not claim that R5 converts
the half scale per weight. They have no 64-bit integer weight decoding,
subgroup broadcast, barrier or local memory in the kernel body. Pointer
addresses retain the platform's normal pointer width. See `expert-down.md`.
There is no paired down candidate: the routed down matrices consume distinct
expert activation vectors, not one shared input. Existing packet28 private/shared
down alternatives remain available for direct comparison.

## Dispatch and measurements

`python -B merge_dispatch.py A.json B.json -o merged.json` merges all three
sections in order. Later entries win. Unknown kernels/classes and conflicts in
one input are rejected; later per-class entries disable earlier containing
fusions and later fusions remove earlier incompatible member choices, with a
reported resolution. `dispatch-merged-example.json` demonstrates packet27
non-GEMV selections plus packet28's measured GEMV table.

K2 tests all registered GEMV alternatives against actual R5, the packet26
GEMV incumbent, with exact bytes and all production type/shape fixtures. Large
payloads rotate eight distinct full-size weight regions. Routed expert banks
use ten different experts per repetition and eight nonoverlapping regions.
Control and candidate offsets differ so adjacent launches do not reread the same
weights. Both rotated and repeated-buffer medians are retained. A new entry is
selected only if exact and below 0.9 times the incumbent for every class workload;
large classes use the rotated median. Full logits copies require about 6.4 GB of
device weights during K2; this is explicit fixture storage, not model residency.
There are no device copies inside the repeated GEMV submission loop.

Non-GEMV K2 state fixtures are uploaded before the timing batch and read back
afterwards. Each stateful invocation receives its own initial state. Adapter
fixtures retain allocations across their overwrite-only repetitions. Per-class
profiling is diagnostic. Only the coordinator's subsequent model windows can
measure the combined speed. Packet26's prior 17.85 tok/s is the control target;
28.49 tok/s remains the reference to beat, not a packet29 result.

## Gates and handoff

`cpu-tests.json` and `build-receipt.json` describe only freshly executed gates and
binary hashes. Gates include both host compilers and fresh fixture processes,
unit/mini/integration dispatch combinations, native argument validation on CPU,
ASan/UBSan with four randomized orders, explicit exit behavior, and eight-token
one-card streaming inference against all 384 v2 layer fixtures. Independent
reviews are retained in `review-expert-down.md` and `review-p28-integration.md`.
The independent scalar review additionally checks exceptional IQ4 values with
bit comparisons; it never equates two different NaN payloads.

[WINDOW.md](WINDOW.md) contains every coordinator command, including explicit
W2x dispatch. [DEADLINES.md](DEADLINES.md) records bounds. CPU preparation always
uses nice19, idle I/O, two OpenMP threads and no more than two compile jobs.
W2-type commands are provided for the coordinator's nice0 parent. No device
executable, discovery API, privileged operation or host setting change was used
in preparation. Prior packets and coordinator receipts remain read-only.

Packet29's final independent diagnostic reports 31,416 finite comparisons per
process, all exact in four processes (GNU/Intel, two each). Mixed nonfinite
inputs remain unqualified: Intel reports 1,254 candidate-versus-R5 and 1,254
candidate-versus-scalar differences; R5-versus-scalar has zero differences in
this diagnostic. GNU reports zero differences. No failure was relabeled equal
and no kernel arithmetic was changed. See `expert-down-review-gates.json`.

Sealed CPU results: five unit suites, 234 integration cases, four fresh fixture
processes (each 111 non-GEMV, 2,604 GEMV, 196 tuple and 51 adapter checks), 32 sanitizer
runs with four random seeds, 93 protocol tests, 1,056 symbolic tree checks,
ten host argument-validation process checks and 307 compiler-inspected kernel
captures. The all-new one-card streaming run matches all 8 generated tokens and
all 384 layer fixtures. Binary hashes are in `BINARY-HASHES.md`; available kernels
are in `KERNELS.md`. No device executable ran and no speed is claimed.
