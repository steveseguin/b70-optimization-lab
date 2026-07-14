# Current Workspace State

Last reviewed: **2026-07-14**

## Authority And Update Rule

This is the sole cross-repository authority for the loaded service, active
optimization lane, protected work, and immediate next actions. Result packets
own promoted evidence; lane handoffs own detailed resume context; `notes/` owns
chronology. Do not append experiment history here.

Always verify the actual endpoint, relevant processes, and Git status before an
operational change. A runnable recipe or installed service unit does not prove
that its model is currently loaded.

## Live Service

No process was listening on the public LAN `:8000` endpoint when the Qwen lane
was closed on 2026-07-13. The last configured role was the temporary Gemma 4
26B A4B Q8 coding-agent service. Its restore, validation, and stop procedure is
in [`docs/gemma4-26b-q8-service-runbook.md`](docs/gemma4-26b-q8-service-runbook.md).
Confirm the endpoint and process state before relying on this observation.

The unauthenticated LAN front door is intentional for this private network. Do
not silently add authentication or change its exposure policy.

## Optimization Transition

The Qwen3.6 27B Q4_0/DFlash optimization lane was closed on 2026-07-13. Its
`>=100 tok/s` TP1 and `>=200 tok/s` multi-B70 single-session objectives were
not reached. The final strict one-B70 record is `47.818818 tok/s`, approved by
LocalMaxxing as `cmrjbx8bc02g8mj01yzz2v701`. The authoritative closeout is
[`notes/2026-07-13-qwen27-dflash-sycl-closure.md`](notes/2026-07-13-qwen27-dflash-sycl-closure.md).

The next active research lane is the investment-gated DeepSeek V4 Flash
vLLM/XPU bring-up for one active generation on four B70s. The frozen source is
`deepseek-ai/DeepSeek-V4-Flash` revision
`60d8d70770c6776ff598c94bb586a859a38244f1`. The first runnable candidate is
the uniform-K160 `0xSero/DeepSeek-V4-Flash-180B` smoke checkpoint at revision
`7c360e1cd4a5168099dbc54d16d929bf6df04990`. It is a 96.026 GiB standard
safetensors artifact with 160 experts in every layer, so explicit TP4 expert
parallelism assigns 40 experts per rank without heterogeneous loader surgery.
It is not yet the quality-certified final model: its hash layers are pruned,
its calibration is not reproducible, and its published ranking is not true
REAP. A later
official-source teacher and hash-preserved nested pack remain the quality path.

The controlling plan is
[`plans/2026-07-13-deepseek-v4-flash-b70-investment-gated-plan.md`](plans/2026-07-13-deepseek-v4-flash-b70-investment-gated-plan.md),
with the current handoff at
[`experiments/deepseek-v4-flash-reap-xpu-b70/HANDOFF.md`](experiments/deepseek-v4-flash-reap-xpu-b70/HANDOFF.md).
The user explicitly authorized the frozen K160 download on 2026-07-13. It is
now complete, cryptographically verified, and promoted to
`/mnt/fast-ai/llm-models/deepseek-v4-flash-xpu/current-k160`. The official-source
transfer was started, then paused without a completed weight shard so the
runnable K160 could take priority; it remains resumable later for teacher
evidence. Speculation remains prohibited until correct nonspeculative decode
approaches 40-50 tok/s. The archived Qwen detail below remains resume evidence,
not an instruction to continue experimenting.

The clean pinned runtime is now vLLM `61c87db64` plus XPU kernels `d553fd2ac`.
Persistent graph replay, native mHC, context-bounded sparse work, and direct
paged FP8 attention all pass. The current strict TP4+EP single-session record
uses split QK/LSE plus 8-by-64 tiled PV and a mutation-declared TP-only
in-place all-reduce for the 87 contiguous BF16 `[1,4096]` decode reductions.
The trustworthy W8A8 record is now **30.2390162 tok/s** median and
`29.7545702` p10 across the strict cold suite, confirmed by a second
`30.2303750` run. All 12 prompts emitted 128 token IDs cached-zero; sequential
changed-input replay and arithmetic/copy/Paris/JSON canaries pass. LocalMaxxing
approved it as `cmrl2619q06hwmj011j5rtnbt`; evidence is
`/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/tp4-w8a8-woa-corrected-n64-20260714T1940Z`.
The previous 30.295 and 33.887 rows are invalid: generic scale prepacking also
transposed DeepSeek's special `wo_a` BMM scales, while its BF16 cache interpreted
them as canonical. Correcting that layout changed 77% of the first 96 greedy
tokens versus the invalid path. Corrected W8A16 is fast (`34.015` and `33.924`
tok/s) but rejected as a quality side lane: it matches only 83.3% of early W8A8
greedy tokens and corrupts the frozen long math-invariant case that W8A8 solves
correctly. MXFP4 N32 failed exact changed-input replay; N128 reached 30.518 and
30.482 tok/s but altered outputs for a sub-1% gain and is not promoted. The
active work is exact-W8A8 producer/quantization fusion and the ordered
87-collective producer/consumer boundary. The standalone MHC/RMS fusion and
oneCCL twoshots lanes remain preserved losses.
Speculation remains disabled until nonspeculative decode approaches 40-50
tok/s. Detailed history is in the lane handoff and
[`experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-14-xpu-graph-recovery-and-tp4-profile.md`](experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-14-xpu-graph-recovery-and-tp4-profile.md).

### Archived Qwen3.6 27B lane detail

- [Controlling requirements and execution plan](plans/2026-07-12-qwen27-tp1-max-speed-requirements-and-execution.md)
- [Archived experiment workspace](experiments/qwen27-dflash-sycl-b70/README.md)
- [Initial Q4_0 and speculation diagnostic](experiments/qwen27-dflash-sycl-b70/notes/2026-07-12-initial-dflash-mtp-benchmark.md)
- [Current MMVQ dispatch-fix result](experiments/qwen27-dflash-sycl-b70/notes/2026-07-12-mmvq-dispatch-fix.md)
- [Native DFlash draft-KV correctness isolation and first >68 result](notes/2026-07-13-qwen36-native-dflash-sycl-fa-isolation.md)
- [Prior promoted vLLM result packet](results/qwen36-27b-autoround-int4-b70/README.md)

The target product is one B70. The intended route combines persistent cached
development workers, B70-native offline weight packs, full useful device
replay/fusion, true multi-row Xe2 verification, and the fastest measured
target-verified MTP/DFlash policy. The main engineering target is a strict
quality-valid result above `100 tok/s` on the fixed realistic suite, with
higher workload-specific code throughput where DFlash acceptance supports it.

Phase 0 implementation now has direct MMVQ rows 1-17 correctness at 34/34,
strict graph-off medians of `25.783 tok/s` no-spec and `47.244 tok/s` MTP3,
and four independent MTP3 calibration medians of `47.976-49.708 tok/s` with
all cold/cached-zero gates passing. Mixed-suite DFlash5 is closed as a global
policy at `11.505 tok/s`; preserve long DFlash for targeted code/adaptive work.
The guarded persistent executable-graph cache now achieves exact direct replay
(381/384 hits) and deterministic output parity, but strict no-spec throughput
was unchanged (`25.848` cache versus `25.854 tok/s` graph off), so graph remains
off by default. Native event timing locates steady M=1 work at about `37.0 ms`
(`12.2-12.5 ms` host submission) and MTP3 at roughly a `42.5-45.8 ms` target
verifier plus about `9.7 ms` of draft/state graphs. Standalone MMVQ+residual
fusion hits 128 pairs/pass and saves about `0.3 ms`, but failed the 3% MTP gate.
The first block-scaled Xe2 DPAS verifier layout is closed at only `1.11x` M=4
and `1.09x` M=8 versus vector, below its `1.5x` integration gate.

The larger guarded fusion stack now reaches `50.390 tok/s` strict MTP3 versus
`48.796 tok/s` without direct GDN cache commit (`+3.27%`) across an eight-run
four-card crossover.  RMS/Q8 sharing and repaired SwiGLU/Q8 are retained behind
flags.  Two further 48-layer boundaries are closed as losses: the matched GDN
output epilogue was neutral (`25.89` versus `25.93-25.94 tok/s` M=1), while
moving sigmoid/softplus raw-gate work into GDN regressed strict MTP3 by `6.67%`
(`46.321` versus `49.632 tok/s`).  Both remain default off.  These results show
that launch-count reduction alone is insufficient when fusion enlarges the GDN
kernel or adds transcendental work to its critical path.

Direct GDN epilogue-to-Q8 output projection, direct SSM convolution cache
commit, and fused SSM convolution/QK normalization are also implemented behind
default-off flags and confirmed to match the real graph. The output-Q8 path was
only `+1.00%` in the AOT eight-run crossover (`49.978` versus `49.486 tok/s`),
below promotion threshold. Combining it with convolution cache regressed AOT
MTP3 by `1.10%` (`49.418` versus `49.969 tok/s`), and QK normalization was
neutral. Preserve these implementations and results, but do not enable them in
the production stack. JIT had overstated these gains, so AOT crossover remains
mandatory before interpreting future fusion wins.

A second Xe2 joint-N verifier briefly appeared to clear the verifier gate, but
independent review found its repeated-vector control reread weights per row,
unlike production reordered MMVQ. The corrected exact-production comparator,
including activation quantization and joint reduction, measured only `1.407x`
and `1.374x` on two critical M=4 shapes; a `1.662x` down-projection case missed
correctness. M=8 square passed at `1.925x`, but is not the MTP3 floor. Runtime
integration is therefore closed; no verifier-v2 dispatch flag was added.

Fresh strict MTP3 cycle accounting measures `2.788` emitted tokens per cycle
at `59.64%` proposal acceptance. The M=4 target verifier is `45.646 ms`
(`80.3%`), aggregate draft preparation `9.700 ms` (`17.1%`), and everything
else only `1.566 ms`, for `56.848 ms` accounted. At current acceptance, 68
tok/s requires a `41.00 ms` cycle and 100 tok/s a `27.88 ms` cycle; even
deleting all draft cost reaches only about `59.1 tok/s`. Per-op device timing
attributes `5.43 ms` of the M=4 penalty to projections, but an explicit Xe2
SIMD4 DP4A variant was only `1.004-1.012x` versus the exact compiler-optimized
production kernel. Crossing 68 now requires materially higher accepted tokens
per cycle (roughly `>=3.1`) as well as device-resident MTP staging; generic
launch fusion and another multi-column loop rewrite are closed.

Focused policy validation (`p_min 0.025-0.80` plus MTP2) produced no rescue:
best strict throughput was `50.895 tok/s`, and even a hindsight per-prompt
oracle across policies was only `52.245 tok/s` median. Existing intrinsic-MTP
adapter experiments are tied to a different HF/vLLM checkpoint, lack a safe
GGUF merge path, and their best offline acceptance gain is far below what is
required. Under the fixed single-B70 Q4_0 model and mixed strict suite, the
`>68 tok/s` objective is now blocked by the combination of Q4 weight bandwidth,
M=4 verifier time, and MTP3's four-token ceiling. Meaningful continuation
requires at least one scope change: a compatible substantially better draft,
lower-bit/reduced-weight target, or a context-owned device-unrolled MTP engine
plus verifier below `29.8 ms`; current safe optimizations cannot meet 68.

The context-owned device-resident MTP3 phase-one path is now implemented and
correct: persistent candidate/`h_nextn` staging, ordered same-device input
copies, a fixed three-step submission loop, and a poisoned-host parity/lifetime
test all pass. A SYCL top-k leading scratch entry initially collapsed
acceptance; selecting the exact production-equivalent candidate restored normal
acceptance. The strict cold suite nevertheless measured only `50.164 tok/s`
median with all gates passing, so host-boundary removal alone is closed as a
speed lane. The serialized draft graphs still execute and the `45.646 ms` M=4
target verifier remains the dominant blocker.

Native DFlash is no longer rejected based on the earlier near-zero-acceptance
result. The failure was caused by using Q8_0 for the native DFlash draft KV
cache, not by DFlash weights, Q4 quantization, or flash attention itself. The
missing controlled run—FA enabled with F16 draft KV—restored `100/106`
acceptance (`94.3%`) and `73.47 tok/s`. The earlier Q8_0 draft-KV run managed
only `7/470`, so quantized draft KV is prohibited until its numerical/backend
failure is fixed. A focused 12-case D=128/GQA4/iSWA/sparse-mask backend test
found Q8-K SYCL/CPU parity (NMSE below `6.6e-6`, no argmax mismatches over 960
rows), so current evidence favors DFlash model sensitivity to Q8 K-cache
quantization rather than a generic FA kernel error. The existing Q4_K_M draft likewise recovered to
`104/115` acceptance and `74.01 tok/s`, proving that the original Q4 result was
not ordinary quantization damage. This is the first valid local lane above the
68 tok/s milestone, but it is workload-specific rather than a production
promotion: native Q8 DFlash5 reached only `40.203 tok/s` median on the strict
12-prompt mixed suite.

Complete native DFlash timing now accounts for the mixed-workload cycle. At
`n_max=5`, steady state is about `58.7 ms` target width-6 verification,
`10.0 ms` DFlash block decode/sampling, `1.0 ms` feature injection, and
`0.3-1.2 ms` acceptance/commit: roughly `70-71 ms` total. The measured primary
blocker is therefore the generic small-M target verifier. The next decisive
work is an offline-packed Xe2 DPAS/XMX verifier plus projection fusion; generic
configuration sweeps and another global DFlash rejection are closed.

The production Xe2 width-6 verifier now covers 130 Q4_0 gate/up tensors plus 57
Q4_0 down tensors. Same-layer gate/up shares one activation quantization and
one dual-matrix ESIMD submission; down consumes canonical Q8_1 metadata, which
reduced its real shadow error to `1.01e-7`. The guarded BMG-native mirrors
preserve target-verifier semantics while materially reducing small-M cost. The
initial integrated kernel returned all zeros because the host packer
numerically converted a half-precision scale object into the raw
`ggml_fp16_t` storage type; copying the two representation bytes fixed the
scales and reduced the real one-tensor shadow error to `0.00036323` maximum.
The first corrected BMG-AOT strict suite passed at `39.249 tok/s`, versus the
matching FA-on, target-KV8, draft-KV-F16 baseline of `37.967 tok/s` (`+3.38%`), and was
approved by LocalMaxxing as `cmriq995z0210mj01fl13xmuc`. The joint gate/up plus
down BMG-AOT successor passed at `42.641 tok/s` (`+8.64%` over that row),
with JIT support at `45.484 tok/s`. Stacking the exact GDN snapshot-cache
commit fusion then raised the strict BMG-AOT record to `44.255 tok/s`, another
`3.79%`, approved as `cmrj8s2sy02a4mj01f18hanvc`. The next independent
boundary fused the Q6_K draft vocabulary head and exact top-1 into one M=6
device operation. Its strict confirmation reached **`47.819 tok/s`**, versus
an exact AOT control of `44.221 tok/s` (`+8.14%`), and LocalMaxxing approved it
as `cmrjbx8bc02g8mj01yzz2v701`. The compact path has guarded graph identity,
lowest-ID tie semantics, and an ordinary-logit rollback/redecode path after a
read failure. Do not compare these
identities with the older `40.203 tok/s` row, which used FA off and F16 target
and draft KV. An experimental 65-tensor QKV/Q expansion was rejected after its
paired strict result failed to improve throughput and introduced larger
summation drift. The next high-value measured boundary is target-side M=6
vocabulary verification: return six exact masked greedy IDs without copying
the full `6 x 248320` logits tensor to the host, then replace its vector head
with the offline-packed Xe2 verifier if the compact boundary clears its gate.

The separate promoted two-B70 vLLM result remains durable reference evidence:
graph-safe FlashAttention plus ReplaySSM transactions reached **95.384868
tok/s median**, passed exact/repeat128/baseline-parity/1K gates, and was
approved by LocalMaxxing as `cmrh35ct50092mj01h7jgydqj`. It is not the active
target configuration.

### Protected Qwen research state

The following main-repository paths contain the committed Qwen experiment
packet and must remain discoverable even though the lane is closed:

- `experiments/qwen27-dflash-sycl-b70/`;
- `notes/2026-07-12-b70-qwen27-prior-art-research.md`;
- `patches/qwen36-27b-autoround-int4-b70/llamacpp-sycl-mmvq-ncols17-q4_0-20260712.patch`;
- `plans/2026-07-12-qwen27-dflash-sycl-single-b70-plan.md`;
- `plans/2026-07-12-qwen27-tp1-max-speed-requirements-and-execution.md`.

`/home/steve/src/llama.cpp` is also protected at base `e3546c794`. It contains
the broader Qwen verifier/fusion/speculation stack plus uncommitted trace and
QKVZAB integration work across multiple files. Its closure-time tracked binary
diff SHA-256 and scoped snapshots are recorded in the
[closure note](notes/2026-07-13-qwen27-dflash-sycl-closure.md). Preserve it,
inspect Git status before building, and do not reset or clean the tree for a
new model lane. Treat the external vLLM, XPU-kernel, oneCCL, build, cache, and
result trees as mutable research state as well.

## Paused And Bookmarked Lanes

- [Gemma 4 26B A4B Q8](results/gemma4-26b-a4b-q8-b70/HANDOFF.md)
- [MiniMax M2.7 INT4](results/minimax-m27-int4-autoround-b70/README.md)
- [Qwen3.6 35B Quark INT8](results/qwen36-35b-quark-int8-b70/README.md)
- [Qwen3.6 27B AutoRound INT4 TP2 result](results/qwen36-27b-autoround-int4-b70/HANDOFF.md)
- [All model effort packets](docs/model-effort-index.md)

These are reproducible or resumable lanes, not claims about the currently
loaded service.

## Immediate Manager Actions

1. Keep the Qwen lane closed. Do not resume unfinished QKVZAB, Q5_K GDN-output,
   or exact-Q4 adaptation work without satisfying the reopening gate in the
   closure note.
2. Finish and cryptographically verify the active K160 download, promote the
   verified copy to internal NVMe, and run the unchanged TP4+EP/8K graph-off
   construction smoke with no speculation.
3. Add native-selector/fallback trace and a real 32-warmup/200-iteration
   M=1/4/8 kernel benchmark before treating the low-level scaffold as a Stage-1
   result. Then establish the correct nonspeculative decode baseline and cycle
   profile before optimization.
4. Preserve `/home/steve/src/llama.cpp` as dirty Qwen research state until its
   patch snapshots are independently reviewed. Do not reset or clean it for a
   DeepSeek bring-up.
5. Continue to publish only verified new matching LocalMaxxing records after
   the cold realistic gate, complete identity capture, and correctness pass.

The detailed state formerly accumulated in this file remains available in Git
at commit `95b4ca413` (`git show 95b4ca413:CURRENT.md`).
