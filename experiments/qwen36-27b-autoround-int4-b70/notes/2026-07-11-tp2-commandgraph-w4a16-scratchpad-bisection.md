# 2026-07-11 - TP2 command-graph replay and W4A16 scratchpad bisection

Status: **resolved and promoted with pinned public oneCCL**.

The previous strict-valid Qwen27 record was the TP1 ReplaySSM result at
`68.23626314761921 tok/s` (LocalMaxxing `cmr9atqb800msqr01u760xh0t`). The
installed oneCCL runtime made the fast TP2 target-graph lane invalid, but a
pinned public oneCCL/libccl build fixes the deterministic collective oracle and
passes the endpoint gates. The conservative promoted TP2 headline is now
`78.22635247759823 tok/s`; a separate full-quality run reached
`81.34114517681084 tok/s` and is retained as high support within the known
variance band.

## Fixed TP2 identity

- model: `webhie/Qwen3.6-27B-int4-AutoRound`, revision
  `f5750c90b3776db658594df5fe8051098226dd8e`;
- two B70 GPUs, TP2, MTP3, `max_model_len=2048`, `max_num_seqs=1`;
- target: PIECEWISE XPU graph, capture size 8, forced/no-op communicator
  capture;
- draft: eager (`VLLM_XPU_DRAFT_DISABLE_CUDAGRAPHS=1`);
- ReplaySSM cache8, commit in forward, PyTorch slot-management fallback;
- target INT8 LM head with BF16 scales and draft INT4 group128 LM head with
  BF16 scales;
- strict quality requests use deterministic request IDs and `cached_tokens=0`.

Reproduction wrapper:

`experiments/qwen36-27b-autoround-int4-b70/scripts/run-tp2-targetgraph-drafteager-candidate.sh`

The earlier frontier and initial failure are recorded in
`2026-07-11-tp2-targetgraph-drafteager-invalid-frontier.md`.

## Replay boundary established

Two controls isolate the failure to command-graph replay of the compiled
packed verifier:

1. `VLLM_XPU_SKIP_COMPILED_SPEC_DECODE=1` passed quality, but ran only about
   `20.27 tok/s`.
2. `VLLM_XPU_DISABLE_SPEC_DECODE_CUDAGRAPH_REPLAY=1` kept compiled direct
   execution and passed quality at about `38.70 tok/s`.

Fully eager TP2 also passed. Therefore raw TP2 arithmetic, the base ReplaySSM
transaction, and the sampler are not the primary defect.

## Controls that did not fix replay

- `VLLM_XPU_ZERO_FRESH_GDN_STATE=1`: repeat256 failed 8 times (indices 18,
  37, 51, 84, 98, 126, 225, and 239).
- PyTorch ReplaySSM recurrent fallback: failed repeats 18 and 51.
- PyTorch staged-convolution fallback: failed 5/128.
- synchronization after layer 0 GDN and after every GDN: still failed.
- `VLLM_XPU_DDTREE_CAPTURE_GDN_CORE=1`: compiled successfully but still
  failed repeats 18, 37, and 51.
- `--no-async-scheduling`: all exact cases passed, but repeat128 still failed
  at indices 20, 25, 38, 43, 48, and 84. Async scheduling is not the root
  cause. Evidence:
  `data/qwen36-27b-autoround-int4-b70-baselines/quality-qwen27-tp2-graph-noasync-gpu23-repeat128-ctx1024-20260711T115655Z.json`.
- TP2 graph with MTP disabled: all exact cases and repeat128 passed. Ordinary
  one-row target graph replay is clean; the defect is specific to the packed
  speculative verifier shape. Evidence:
  `data/qwen36-27b-autoround-int4-b70-baselines/quality-qwen27-tp2-graph-nospec-gpu01-repeat128-ctx1024-20260711T120153Z.json`.
- static-input copying, broad static metadata copying, strong graph outputs,
  eager collective splitting, and global replay synchronization were already
  negative or non-viable in the preceding bisection.

These controls rule out fresh-slot initialization, the native ReplaySSM
kernels, simple queue ordering, and the GDN split boundary as sufficient
explanations.

## First divergent segment

Replay microscope traces localized the first bad value to
`piecewise:1/65`:

- coarse trace:
  `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/q27-cg-coarse-trace-r0-20260711T105915Z.jsonl`;
- pieces 0-8 trace:
  `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/q27-cg-fine0-8-r0-20260711T110800Z.jsonl`;
- layer-0 GDN row trace:
  `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/q27-gdnrow-layer0-r0-20260711T111300Z.jsonl`;
- piece-1 live-input trace:
  `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/q27-piece1-input-r0-20260711T112000Z.jsonl`.

For adjacent good/bad requests, piece 0 and layer-0 GDN were identical. At the
first piece-1 replay, every live tensor argument had the same address, shape,
dtype, and digest, but the graph output diverged. This makes the remaining
state graph-owned or internal to an opaque operation, rather than a missing
Python-visible input.

An all-rank graph-versus-direct experiment was required because running the
direct comparison only on TP rank 0 deadlocked in the first collective. The
initial count appeared to show that all 267 piece-1 calls disagreed, but that
interpretation was wrong: output paths `$[1]` and `$[5]` are deliberately
uninitialized `empty_like` handoff buffers that eager GDN overwrites later.
Their digests are allocator noise and are not semantic model outputs.

Only three calls disagreed in the meaningful output paths `$[2]`, `$[3]`, and
`$[6]`: the JSON request at computed-token count 44, repeat 8 at count 36, and
repeat 40 at count 30. Returning direct piece-1 outputs improved repeat64 to
one failure at repeat 40, but did not fix the whole model:

- JSON exact case returned an empty `unit` instead of `widgets`;
- repeat 40 returned only `blue`;
- result:
  `data/qwen36-27b-autoround-int4-b70-baselines/quality-qwen27-tp2-piece1-return-direct-allranks-gpu23-repeat64-ctx1024-20260711T112936Z.json`;
- rank traces:
  `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/q27-piece1-directcompare-allranks-{0,1}-20260711T1130.jsonl`.

The decisive comparison is the residual output `$[6]` on the repeat-40 bad
call. Direct execution produced the same post-reduction tensor on both ranks
(`sum=50.124893`, `l2=24.160638`, `min=-0.361328`, `max=13.9375`). Graph replay
instead produced different, severely corrupted tensors after the TP reduction:

| rank | sum | l2 | min | max |
| ---: | ---: | ---: | ---: | ---: |
| 0 | `440.0545` | `468.036` | `-75.5` | `406` |
| 1 | `465.1138` | `474.683` | `-75.5` | `406` |

The adjacent good repeat-39 call had graph residuals identical to direct
execution and identical across ranks. A successful all-reduce must leave the
same reduced hidden state on both TP ranks. This establishes an intermittent
TP collective command-graph replay failure at speculative verifier row count
`M=4`; W4A16 and the preceding local compute are not the primary fault.

Compare-direct remains diagnostic only: graph replay runs before the eager
rerun and can already mutate graph-owned state.

## W4A16 scratchpad hypothesis rejected

Generated piece 1 contains four `_xpu_C::int4_gemm_w4a16` calls and two TP
collective regions. Because W4A16 uses oneDNN user scratchpad through a raw
pointer, an earlier TP1 no-win patch retaining scratchpads in a thread-local
ring was retested as a possible graph-lifetime correctness fix.

Both ring sizes failed with the same intermittent output pattern:

- ring 1: failures at repeat indices 47, 61, 80, 99, and 118;
- ring 16: failures at 47, 61, 80, 99, 113, and 125.

Artifacts:

- `data/qwen36-27b-autoround-int4-b70-baselines/quality-qwen27-tp2-w4scratch-ring1-gpu01-repeat128-ctx1024-20260711T120740Z.json`;
- `data/qwen36-27b-autoround-int4-b70-baselines/quality-qwen27-tp2-w4scratch-ring16-gpu23-repeat128-ctx1024-20260711T120748Z.json`;
- `patches/qwen36-27b-autoround-int4-b70/vllm-xpu-kernels-qwen27-int4-gemm-scratchpad-ring-no-win-20260706.patch`.

The active kernel binary and source were restored after this result.

An eager-op split was also tested by adding
`_xpu_C::int4_gemm_w4a16` to the default split list. It is not a valid
arithmetic oracle: every W4A16 call returns a newly allocated output, while the
next captured piece retains its capture-time input pointer. The run failed all
exact cases and collapsed speculative acceptance to zero, demonstrating a
new eager-to-graph handoff alias rather than resolving the original defect:

`data/qwen36-27b-autoround-int4-b70-baselines/quality-qwen27-tp2-w4a16-eager-split-gpu01-repeat64-ctx1024-20260711T115416Z.json`

## Existing custom-op all-reduce also fails

The existing out-of-place custom-op route was tested with its required inner
clone and both settings of the graph-visible clone:

```bash
VLLM_XPU_COMPILE_ALLREDUCE_CUSTOM_OP=1
VLLM_XPU_CUSTOM_ALLREDUCE_CLONE_INPUT=1
```

Both exact suites passed, but repeat128 failed:

- graph clone off: failures at 47, 61, 73, 85, 97, 109, and 121;
- graph clone on: failures at 47, 99, and 118.

Artifacts:

- `data/qwen36-27b-autoround-int4-b70-baselines/quality-qwen27-tp2-customar-innerclone-gclone0-gpu01-repeat128-ctx1024-20260711T121811Z.json`;
- `data/qwen36-27b-autoround-int4-b70-baselines/quality-qwen27-tp2-customar-innerclone-gclone1-gpu23-repeat128-ctx1024-20260711T121811Z.json`.

The custom op returns a fresh runtime allocation, so it does not establish a
stable pointer handoff to the following captured segment. The next experiment
uses a graph-owned clone plus a split mutating `vllm::all_reduce_inplace`
boundary (`VLLM_XPU_COMPILE_ALLREDUCE_STATIC_INPLACE=1`).

## Static in-place handoff: diagnostic correctness gain, speed loss

The new path clones each local partial result into a graph-owned tensor, splits
`vllm::all_reduce_inplace` out of command-graph capture, mutates the stable
tensor eagerly, and passes the same allocation into the next captured piece.
Generated graph inspection confirmed this exact compute -> collective ->
compute partition.

It substantially improved repeat stability:

- GPUs 0,1: exact cases plus repeat128 passed with full baseline parity;
- GPUs 2,3: exact cases plus repeat256 passed with full baseline parity;
- a separate GPUs 0,1 full quality run passed exact, repeat128, and the 1K
  long-context needle.

However, it is not promotable:

- strict fresh GPUs 2,3: `44.700099 tok/s` median, `38.677788` p10,
  `cached_tokens=0` for all 12 prompts;
- strict fresh GPUs 0,1: `43.655520 tok/s` over the ten measurable prompts,
  but `sql-debugging` and `bug-report-synthesis` emitted only EOS and made the
  final gate invalid;
- all 72 target row-parallel reductions become eager graph boundaries, adding
  roughly 30 ms per verifier step and reducing speed far below the valid TP1
  `68.236263 tok/s` record.

Artifacts:

- `data/qwen36-27b-autoround-int4-b70-baselines/quality-qwen27-tp2-staticinplace-ar-gpu01-r128-repeat128-ctx1024-20260711T122737Z.json`;
- `data/qwen36-27b-autoround-int4-b70-baselines/quality-qwen27-tp2-staticinplace-ar-gpu23-r256-repeat256-ctx1024-20260711T122737Z.json`;
- `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-tp2-staticinplace-ar-bench-gpu23-candidate-summary-20260711T123613Z.json`;
- `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-tp2-staticinplace-ar-strict-gpu01-candidate-summary-20260711T123414Z.json`;
- `patches/qwen36-27b-autoround-int4-b70/vllm-qwen27-static-inplace-allreduce-diagnostic-20260711.patch`.

This establishes the direction but not a shipping implementation: a correct
collective must remain inside the captured layer instead of creating 72 eager
boundaries.

## Superseded native-kernel lane

The older MiniMax Level Zero IPC prototype proved peer-buffer import/export but
its cached volatile polling timed out because B70 peer atomics are unavailable:
`notes/2026-05-20-minimax-qk-ipc-peer-polling-negative.md`.

A 2026-07-11 B70 report describes the missing coherence technique: local
writes, uncached ESIMD remote reads, and explicit `system_acquire` fences,
avoiding unreliable PCIe peer atomics while remaining graph-capturable:
https://www.reddit.com/r/LocalLLM/comments/1u8yai1/

This was the planned next implementation before the newer public oneCCL source
was tested. The local ESIMD prototype remains useful negative evidence, but a
new native collective is no longer required to restore correctness. Do not
resume peer-polling work unless the public oneCCL lane later proves insufficient
for a measured bottleneck.

## Resolution: public oneCCL fixes graph replay

The decisive step was reducing the issue to a deterministic collective oracle
instead of continuing endpoint flag sweeps. The oracle captures the exact
packed-verifier BF16 `[4,5120]` all-reduce, changes every input before every
replay, and checks every output element against an exactly representable BF16
sum.

Results:

- installed oneCCL `Gold-2021.17.2`, `HEAD/b9deca8`: rank 0 was wrong on
  `510/512` graph replays and rank 1 on `511/512`;
- public oneCCL parent `b52f40c07f0b140e6aba87548c80720a350a9827`,
  legacy libccl `4ceafd15c03ce46f11eeaf91781a92afebd3cecf`: direct control
  passed `256/256` on both ranks and XPUGraph passed `512/512` on both ranks;
- an experimental LL256 counter-kernel sequence dependency also passed, but a
  source-matched public build without that line passed identically. Preserve
  the patch as inconclusive; attribute the fix to the public revision as a
  whole.

Oracle artifacts:

- `data/qwen36-27b-autoround-int4-b70-baselines/oneccl-installed-ll256-graph-baseline-20260711.json`;
- `data/qwen36-27b-autoround-int4-b70-baselines/oneccl-public-unpatched-ll256-direct-control-20260711.json`;
- `data/qwen36-27b-autoround-int4-b70-baselines/oneccl-public-unpatched-ll256-graph-control-20260711.json`;
- `data/qwen36-27b-autoround-int4-b70-baselines/oneccl-ll256-seqdep-direct-20260711.json`;
- `data/qwen36-27b-autoround-int4-b70-baselines/oneccl-ll256-seqdep-graph-20260711.json`.

The 2025.3 Intel compiler needed only two ESIMD `barrier()` namespace
disambiguations to build this pinned source. That compatibility-only delta is
preserved separately from the inconclusive dependency patch. The tested binary
is outside Git at `/mnt/usb-models/llm-runtime/oneccl-4ceafd1-b70`; its library
SHA-256 is `43d94d43506e30096dd099b9d53b54f932be964751e92ff0cbb8d3a37fad6700`
and its `kernels.spv` SHA-256 is
`0d549c35a558f1b216cb7d1efeaa9f86d7596ffc47b383644e075290d314f0c9`.
Rebuild and validate it through
`experiments/qwen36-27b-autoround-int4-b70/oneccl_ll256/`.

## Endpoint validation and variance

The public build was injected only into the vLLM server subprocess with
`LD_PRELOAD`; helper Python processes retained the normal environment. This
avoids contaminating artifact generation or benchmark clients with an
experimental communication runtime.

Full-quality support run on GPUs 2,3:

- strict fresh median `81.34114517681084 tok/s`, p10 `75.44721241444648`,
  mean `81.42812719182129`;
- all 12 prompts unique and run once, `cached_tokens=0` throughout, no
  prefix/KV/history/response reuse;
- exact canaries passed, repeat128 passed, baseline matched, and the 987-token
  prompt / 1K needle passed;
- summary:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-tp2-oneccl-public4ce-lock-candidate-summary-20260711T142306Z.json`.

Isolated confirmation on GPUs 2,3:

- strict fresh median `78.22635247759823 tok/s`, p10
  `69.9633890122676`, mean `78.59814141426254`;
- full-output after-TTFT median `80.15814896781353 tok/s`, wall median
  `69.87919249825262 tok/s`, TTFT median `750.0304995337501 ms`;
- strict gate passed with all 12 `cached_tokens=0`;
- summary:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-tp2-oneccl-public4ce-solo-confirm-gpu23-candidate-summary-20260711T143410Z.json`.

The high and isolated rows differ by `3.98%`, inside the established `4.4%`
endpoint variance band. Use `78.22635247759823 tok/s` as the conservative
headline and `81.34114517681084 tok/s` as valid high support. Concurrent TP2
pairs measured `71.81599530053151` on GPUs 0,1 and `76.27441961099224` on
GPUs 2,3, confirming that simultaneous pair testing is useful for screening
but adds measurable contention and is not the promotion condition.

One harness lesson is also worth retaining: two confirmation shells failed
before server launch when `run-vllm-candidate.sh` was edited while they were
reading it. Those attempts produced no benchmark result and cleaned up
normally. Freeze or copy the launcher before parallel runs; do not edit a live
entrypoint.

## Promoted artifacts and next work

- result packet:
  `results/qwen36-27b-autoround-int4-b70/tp2-public-oneccl-4ceafd1-20260711.json`;
- checksum-gated record wrapper:
  `experiments/qwen36-27b-autoround-int4-b70/scripts/run-tp2-oneccl-public4ce-candidate.sh`;
- LocalMaxxing queue:
  `experiments/qwen36-27b-autoround-int4-b70/localmaxxing/qwen36-27b-webhie-int4-tp2-public-oneccl-20260711.queue.json`.

This is a real mechanism win over the prior `68.236263` TP1 record, not a
sub-percent endpoint fluctuation. The next optimization lane should keep this
public runtime fixed and screen its graph-safe all-reduce algorithms and
temporary-buffer modes with the deterministic oracle first, then endpoint
throughput and full quality. The goal remains `100+ tok/s`; do not fall back to
config sweeps against the known-broken installed collective.
