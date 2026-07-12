# Current Workspace State

Last reviewed: **2026-07-12**

## Authority And Update Rule

This is the sole cross-repository authority for the loaded service, active
optimization lane, protected work, and immediate next actions. Result packets
own promoted evidence; lane handoffs own detailed resume context; `notes/` owns
chronology. Do not append experiment history here.

Always verify the actual endpoint, relevant processes, and Git status before an
operational change. A runnable recipe or installed service unit does not prove
that its model is currently loaded.

## Live Service

The public LAN `:8000` endpoint was last recorded on 2026-07-08 as the temporary
Gemma 4 26B A4B Q8 coding-agent service. Its restore, validation, and stop
procedure is in [`docs/gemma4-26b-q8-service-runbook.md`](docs/gemma4-26b-q8-service-runbook.md).
Confirm the endpoint and process state before relying on this observation.

The unauthenticated LAN front door is intentional for this private network. Do
not silently add authentication or change its exposure policy.

## Active Optimization Lane

The active research lane is **maximum Qwen3.6 27B TP1 decode speed on one Intel
Arc Pro B70**. All four B70s are independent TP1 experiment workers; do not
move this lane to TP2 or TP4 unless the user explicitly changes the mandate.

- [Controlling requirements and execution plan](plans/2026-07-12-qwen27-tp1-max-speed-requirements-and-execution.md)
- [Active experiment workspace](experiments/qwen27-dflash-sycl-b70/README.md)
- [Initial Q4_0 and speculation diagnostic](experiments/qwen27-dflash-sycl-b70/notes/2026-07-12-initial-dflash-mtp-benchmark.md)
- [Current MMVQ dispatch-fix result](experiments/qwen27-dflash-sycl-b70/notes/2026-07-12-mmvq-dispatch-fix.md)
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

The separate promoted two-B70 vLLM result remains durable reference evidence:
graph-safe FlashAttention plus ReplaySSM transactions reached **95.384868
tok/s median**, passed exact/repeat128/baseline-parity/1K gates, and was
approved by LocalMaxxing as `cmrh35ct50092mj01h7jgydqj`. It is not the active
target configuration.

### Protected In-Flight Work

The following July 12 main-repository work is protected and may be untracked
until it is reviewed and committed:

- `experiments/qwen27-dflash-sycl-b70/`;
- `notes/2026-07-12-b70-qwen27-prior-art-research.md`;
- `patches/qwen36-27b-autoround-int4-b70/llamacpp-sycl-mmvq-ncols17-q4_0-20260712.patch`;
- `plans/2026-07-12-qwen27-dflash-sycl-single-b70-plan.md`;
- `plans/2026-07-12-qwen27-tp1-max-speed-requirements-and-execution.md`.

`/home/steve/src/llama.cpp` is also protected. Its Q4_0 MMVQ ncols 9-17,
MMVQ regression coverage, SYCL graph evidence, and capture-safe concat work is
dirty in `common.hpp`, `ggml-sycl.cpp`, `mmvq.cpp`, and
`tests/test-backend-ops.cpp`. Preserve it, inspect it before building, and do
not reset or clean the tree. Treat the external
vLLM, XPU-kernel, oneCCL, build, cache, and result trees as mutable research
state as well.

## Paused And Bookmarked Lanes

- [Gemma 4 26B A4B Q8](results/gemma4-26b-a4b-q8-b70/HANDOFF.md)
- [MiniMax M2.7 INT4](results/minimax-m27-int4-autoround-b70/README.md)
- [Qwen3.6 35B Quark INT8](results/qwen36-35b-quark-int8-b70/README.md)
- [Qwen3.6 27B AutoRound INT4 TP2 result](results/qwen36-27b-autoround-int4-b70/HANDOFF.md)
- [All model effort packets](docs/model-effort-index.md)

These are reproducible or resumable lanes, not claims about the currently
loaded service.

## Immediate Manager Actions

1. Follow the ordered checklist in the controlling TP1 requirements plan.
2. Use the completed MMVQ/strict baseline evidence as the Phase 0 control;
   do not repeat the graph-recreate or mixed DFlash losses.
3. Continue the combined residual/RMSNorm/Q8_1 fusion boundary and a stronger
   multi-token verifier layout; do not repeat neutral graph replay or the
   closed block-scaled DPAS mapping.
4. At promotion time—not during rapid iteration—record each external source
   tree's path, commit, dirty state, and relevant aggregate patch snapshot.
5. Update the [performance index](results/scoreboard.md) for representative
   verified expectations and the [LocalMaxxing ledger](results/localmaxxing-submissions.md)
   only for actual public submissions.

The detailed state formerly accumulated in this file remains available in Git
at commit `95b4ca413` (`git show 95b4ca413:CURRENT.md`).
