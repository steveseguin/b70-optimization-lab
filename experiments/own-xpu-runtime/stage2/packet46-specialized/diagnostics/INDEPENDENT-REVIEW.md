# Packet46 independent review

Reviewer: diagnostics subagent, October 17, 2026. Kernel and CPU-expert code
were written by other agents. Diagnostic code below was self-reviewed and
separately reviewed by the coordinating agent; that portion is not presented
as independent review. The independent source review preceded compilation.
The diagnostic CPU gate below ran after the 02:55 UTC cutoff. No GPU or model
payload has been opened. Other agents own the kernel/CPU-expert execution receipts;
their source-review rows below retain the evidence boundary of that review.

## Reviewed scopes and findings

| Scope | Finding / disposition |
| --- | --- |
| `cache_budget.py`, `CACHE-BUDGET.md`, retained census | Packed bytes, 4 KiB slot alignment, metadata allowance, 9,082 slots, per-layer quotas and hypothetical uniform miss accounting agree. The PLE history correction is explicitly derived from retained allocation census. Both arena and physical reserve checks remain visible. No device-fit claim. Three Python tests passed in 0.011 s. |
| `cpu-expert/expert_avx2.hpp`, `fixtures.hpp`, `main.cpp`, `run.py`, specification | SIMD lanes map to independent SG32 logical lanes; IQ2/IQ3 scale/sign and IQ4 decode order agree with inherited helpers. K=640 leaves last-tile lanes 16–31 unchanged, preserving zero/add order. Existing byte slices, changed input rotation, split=1 and 47:1 benchmark mixture are consistent. Nonfinite oracle parity and per-layer miss latency are explicitly pending. Compiler/fresh-process/throughput evidence is still pending at this review checkpoint. |
| `specialized.hpp`: GateMix | Initial implementation published mix despite inactive/error/invalid-position controls. Reported to author; corrected to retain unconditional inherited GEMV gate stores while guarding only mix publication. Error/control fixtures were expanded. |
| `specialized.hpp`: Norm | Original 32-leaf FP32 partials and upper tree retained. Workgroup-uniform guard snapshot precedes barriers. Norm partial bytes are observed at the producing boundary. |
| QSA/GDN tuples | Dispatch table independently confirms QKV/Z/Q split=1, QSA K/V split=4, BF16 IQ/IK split=4. Tuple lane iteration and adjacent SG32 tree match p28/p33; split-four remains `(p0+p1)+(p2+p3)`. No descriptor interpreter in the fused device body. |
| `layer_bench.cpp`: intermediate/state coverage | Initial coverage omitted non-plan mutable buffers and live IK split-four FP32 workspace. Reported to author. Current code preserves native IK workspace stores, compares those bytes at the projection boundary, and compares the final complete mutable-allocation snapshot including controls, workspace, scratch and padding. CPU IK scratch intentionally matches the inherited CPU backend's no-store behavior. GPU checks remain required. |
| `fixture_bytes.hpp`, layer timing | Metadata/synthetic fixture construction avoids model payloads. Timing sums original individual completed GPU event intervals by class and verifies event/submission coverage. AB/BA pairs restore identical initial bytes outside timing. Review found timing's 210 inputs initially lacked per-arm error/state checks; author added sticky-error checks and full mutable-state paired comparison after event capture for all 420 layer pairs. These checks are outside timing. These are layer microbenchmarks, never model throughput claims. |
| `specialized_cpu_test.cpp` | Raw FP32 lane/part/final-tree comparisons now cover Q6 split=1/4, BF16 split=4 and Q8 HC gates. Norms compare BF16 outputs, FP32 partial bytes and error control; GateMix compares gate and mix bytes on active/inactive/error/invalid-position cases. Test execution was not yet available during this source review. |
| `build_layer.py`, coordinator/summarizer | Builds use only new packet46 output paths and verify parent source/binary/link identities. Parent relink-to-new-path must reproduce the existing binary before cached object reuse. Window admission restricts card 0, new output, systemd ownership, fault evidence and memory/storage; uncertain live children are retained. Summarizer checks full ordered capture manifest, six cases/layer, unique GPU-event accounting, baseline35/41 launches and hash-bound exactness companions for two fresh timing owners. Compilation and executable receipts remain pending. |
| `diagnostics/` self-review | Coordinating reviewer caught callback execution before closed/metadata checks. Corrected: validate before read/query callbacks; any collector failure is sticky and prevents a complete footer. Default off executes no callbacks; speed mode refuses flags. Schema validates slot order, route uniqueness, command identity/resolution, duplicate event accounting and clock domains. Post-cutoff C++ mock and five Python test groups passed; details below. |

## Executed diagnostic CPU gate

The [receipt](evidence/cpu-gate/receipt.json) records one GCC 13.3 compilation
and two fresh CPU processes at **02:56:21–02:56:22 UTC**, using nice 19 and
CPUs 4–15,20–31 under the shared preparation lock. Both processes emitted
identical bytes: nine JSONL records, two commands, two route layers and two
synthetic event intervals. Both traces passed strict validation. Five Python
schema/cache-report test groups passed in 0.002 seconds. No source correction
or repeated compilation was needed. Compiler output, commands, source/binary
hashes and both raw mock traces are retained in that evidence directory.

The synthetic event intervals were supplied by the CPU mock callback; **no GPU
events were collected**. No real routes, hit rate, model speed, device arithmetic
or integrated engine behavior is qualified by this gate.

## Evidence limits and remaining checks

Source-level agreement is not a quality or speed pass. The actual CPU builds,
raw comparison gates and fresh-process repeats must run after the cutoff.
Device exactness, native launch census and 80-microsecond paired timing bar
remain coordinator-owned and unrun. Local-memory/register FP32 partials need
the authored leaf tests as well as final native raw-output checks; BF16 output
agreement alone could hide FP32 changes. No scratch range should be waived
because it is inconvenient to reproduce.

CPU throughput will report processed packed bytes, not measured DRAM bandwidth.
The 144-expert batch exposes much more independent work than a real layer's
maximum ten selected experts. It can reject an optimistic throughput premise;
it cannot establish layer-tail latency or CPU/GPU overlap. Nonfinite CPU status
and output parity remains an explicit integration blocker.

Diagnostics are an adapter with documented hook sites, not a modified two-card
engine. Future integration must collect original IDs before allocation reuse,
query GPU events before retirement, preserve cancellation hooks, and compare
instrumented versus uninstrumented token/state bytes. Its copy/wait overhead
excludes all collected traces from speed claims. Cache reports model a fixed
placement and report observed coverage; mock traces are not measured hit rates.
