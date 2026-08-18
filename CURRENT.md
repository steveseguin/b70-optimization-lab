# Current Workspace State

Last reviewed: **2026-08-18**

## Authority And Update Rule

This is the sole cross-repository authority for the loaded service, active
optimization lane, protected work, and immediate next actions. Result packets
own promoted evidence, lane handoffs own detailed resume context, and `notes/`
owns experiment chronology. Keep this file short; do not append experiment
history here.

Always verify Git status, relevant processes, listeners, and the actual endpoint
before an operational change. A recipe or installed unit does not prove that a
model is currently loaded.

The verbose pre-consolidation workspace ledger remains available in Git at
`0dbe3ab3e:CURRENT.md`. Its durable findings are also preserved in the linked
result packets, handoffs, notes, patches, and reproduction recipes below.

## Live Service

Verified on 2026-08-15:

- `muse-glimmer-bf16-fleet.service`: inactive;
- `muse-glimmer-frontdoor.service`: inactive;
- no listeners on `8000`, `18080`-`18089`, `19470`, or `19471`;
- no `llama-server`, vLLM, or frontdoor process is running.

The preserved Muse source/build remains under
`/home/steve/src/llama.cpp-muse-100`. Do not reset, clean, rebuild, restart, or
repurpose that tree without first checking service ownership and the canonical
host GPU lock; inactive services can still be started by another operator.

Operational and result references:

- [Muse BF16 service runbook](docs/muse-glimmer-bf16-service-runbook.md)
- [Muse Q8/WOQ closed result](results/muse-glimmer-30b-q8-woq-b70/README.md)
- [Muse standalone reproduction](repro/muse-glimmer-30b-q8-woq-b70-100tps-20260813/README.md)
- [Local operations and recovery policy](docs/local-ops.md)

The closed no-training Muse Q8/WOQ record remains approved by LocalMaxxing as
[`cmss8515c00n0ms01n3begqgg`](https://www.localmaxxing.com/en/runs/cmss8515c00n0ms01n3begqgg).
It is a Q8/WOQ target-verified result, not BF16/lossless or universally
token-exact evidence.

## Active Optimization Lane

Qwen3.8 27B target-only TP2 on two ASRock B70s is active. The current accepted
Q4_K_M source adds a device-local Q4_K gate/up/SwiGLU fusion to the transferred
Qwen3.6 exact-shape stack. DFlash, MTP, prompt reuse, and other speculation are
separate result classes and remain outside the target-only headline.

All Git work is performed directly on `main`. Do not create branches or
secondary worktrees. Use focused commits, patches, bundles, configs, and result
packets for isolation and recovery.

## Active Research: Qwen3.8 27B TP2

The promoted target-only two-B70 Q4_K_M result is:

- conventional 99-interval median: **`49.717503 tok/s`**;
- historical helper: `50.219700 tok/s`;
- full-output after-TTFT median: `49.734644 tok/s`;
- quality: 12/12 cold 512-token outputs exact against the accepted control;
- cache: `cached_tokens=0` for 12/12;
- speculation: none;
- LocalMaxxing: approved as
  [`cmsy530c70cpwms01bl1sjk6g`](https://www.localmaxxing.com/en/runs/cmsy530c70cpwms01bl1sjk6g).

The 2026-08-15 Q4_K fusion passed a clean build, mechanism counter, same-binary
control, and complete 12-prompt cold suite. It improved the conventional
median by `+1.701%`; all complete output hashes remained exact. The Q8_0 TP2
transfer separately reached `36.772932 tok/s` conventional with 12/12 matched
complete outputs. On 2026-08-16, Q8 and Q4_K_M also passed exact, arithmetic,
JSON, factual, logic, Python-result, repeat-stability, and 3,829-token needle
canaries. Q8 is the primary quality-conservative service identity; Q4_K_M is
the explicitly lower-precision speed lane.

A separate one-B70 SergioB GPTQ INT4 route was validated on 2026-08-16. Native
FP16 KV reached `34.160467 tok/s` target-only and `87.605425 tok/s` MTP4 at
p512/g128 and 8K; both beat the FP8-KV rows. MTP4 accepted 511/540 drafts,
matched the GPTQ target on the semantic suite, and its loaded draft parameters
were verified FP16. The GPTQ target itself failed the Python-result canary
(`30` rather than `14`) passed by Q8/Q4, so the lane is quality-rejected as the
default and remains experimental. The nightly patch is redundant at 8K; 131K,
the boundary patch, power, and broad quality remain open.

The official Qwen3.8 FP8 checkpoint now has a working TP2 vLLM/XPU baseline in
the newer pinned `0.27.2rc1.dev77` image. Eager decode measured `17.097358`
tok/s; a size-one PIECEWISE graph measured **`21.708532 tok/s`** with five
unique cache-zero p512/g128 requests. Seven exact canaries, eight-run
determinism, and a 3,829-token needle all matched the Q8 oracle. This is slower
than GGUF Q8 and remains experimental because vLLM officially limits XPU Graph
support to single GPU; it is the source-level GDN/collective control, not the
promoted fastest service.

Resume and evidence:

- [Qwen3.8 model board](README.md#qwen38-27b-model-board)
- [target-only pass-2 ledger](experiments/qwen38-27b-b70/notes/2026-08-15-target-only-pass2.md)
- [Q4_K_M standalone reproduction](repro/qwen38-27b-q4km-tp2-asrock-b70/README.md)
- [Q4_K fusion source increment](patches/qwen38-27b-q4km-tp2-asrock-b70/README.md)
- [Q4_K structured summary](experiments/qwen38-27b-b70/data/2026-08-15-q4km-tp2-q4k-glu-summary.json)
- [Q8 structured summary](experiments/qwen38-27b-b70/data/2026-08-15-q8-tp2-transfer-summary.json)
- [Q8 quality-conservative standalone reproduction](repro/qwen38-27b-q8-tp2-asrock-b70/README.md)
- [Q8 c2 cache-row fusion result](experiments/qwen38-27b-b70/notes/2026-08-16-q8-c2-cache-row-fusion-neutral.md)
- [Q8 distributed greedy argmax result](experiments/qwen38-27b-b70/notes/2026-08-16-q8-distributed-greedy-argmax-neutral.md)
- [community GPTQ/MTP vLLM idea](community/sergiiob-qwen38-27b-vllm-xpu/STATUS.md)
- [one-B70 GPTQ target-only graph validation](community/sergiiob-qwen38-27b-vllm-xpu/validation/2026-08-16-local-target-only-graph-validation.md)
- [one-B70 GPTQ native-MTP matrix](community/sergiiob-qwen38-27b-vllm-xpu/validation/2026-08-16-local-mtp-matrix-validation.md)
- [GPTQ quality/KV/runtime-dtype decision](community/sergiiob-qwen38-27b-vllm-xpu/validation/2026-08-16-quality-kv-dtype-decision.md)
- [official FP8 vLLM/XPU TP2 reproduction](repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/README.md)
- [official FP8 graph result](experiments/qwen38-27b-b70/notes/2026-08-16-official-fp8-vllm-graph-tp2.md)

Do not retry the built-in TP2 SYCL profiler or the unsafe root-both remote-write
prototype inherited from Qwen3.6 work. Both caused device faults/resets. Do not
overlap BMG AOT compilation, a model workload, or a large download on this
15 GiB host.

## Protected Work And Artifacts

Preserve these paths and inspect their status before any build, cleanup, or
service change:

- `/home/steve/src/llama.cpp-muse-100`: preserved source/build used by the inactive Muse fleet;
- `/mnt/fast-ai/src/llama.cpp-q38-q4k-glu-tp2`: accepted Qwen3.8 Q4_K_M source at
  `a4349bcee`; preserve its intentional three-file uncommitted fusion delta;
- `/mnt/fast-ai/src/llama.cpp-q38-q4k-glu-tp2/build-sycl-aot-bmg-g31-oneapi-2026.1.1`:
  accepted oneAPI 2026.1.1 BMG-G31 AOT build;
- `/mnt/fast-ai/llm-models/qwen3.8-27b-gguf/`: accepted Qwen3.8 GGUF targets and MTP sidecars;
- `/mnt/fast-ai/llm-models/qwen3.8-27b-fp8/`: official FP8 artifact retained for the separate vLLM lane;
- `/mnt/fast-ai/bench-results/qwen38-official-fp8-vllm-xpu-20260816/`:
  official FP8 eager/graph/P2P controls, final quality gate, cache-zero result,
  runtime capture, and post-run health evidence;
- `/mnt/fast-ai/llm-models/qwen3.8-27b-gptq-int4-mtp/`: hash-verified
  SergioB GPTQ INT4 target with 15 BF16 MTP tensors; community replay lane;
- `/mnt/fast-ai/bench-results/qwen38-q4km-asrock-b70-20260815-pass2/`:
  accepted Q4_K fusion A/B and cold-suite evidence;
- `/mnt/fast-ai/bench-results/qwen38-gptq-int4-asrock-b70-20260816/`:
  SergioB target-only eager/graph validation, failed conservative-U graph
  attempt, logs, inspect records, prompts, and raw SSE evidence;
- `/mnt/fast-ai/bench-results/qwen38-gptq-quality-20260816/`: native/FP8 KV,
  semantic quality, MTP runtime-dtype, Q8/Q4 controls, and reset-window evidence;
- `/mnt/fast-ai/src/llama.cpp-q8-tp2-directq8-isolated`: current accepted Qwen TP2 source;
- `/mnt/fast-ai/src/llama.cpp-q38-tp2-distributed-greedy-directq8`: closed
  exact distributed-argmax candidate; preserve for mechanism reuse only;
- `/mnt/fast-ai/bench-results/qwen38-q8-asrock-b70-20260816-distributed-greedy/`:
  position-balanced reasoning-off controls/candidates and exact output oracle;
- `/mnt/fast-ai/src/llama.cpp-mndodd-intel-sycl`: prior accepted Qwen TP2 source; preserve as control;
- `/mnt/fast-ai/llm-models/qwen3.6-27b-q8_0-gguf/`: accepted Qwen model;
- `/mnt/fast-ai/bench-results/qwen36-q8-asrock-b70-20260813-tp2-fusion/`:
  promoted Qwen evidence and bounded negatives;
- `/mnt/fast-ai/bench-results/qwen36-q8-asrock-b70-20260814-40tps/`:
  Qwen pass-1/pass-2 evidence and current clean result;
- `experiments/qwen27_graphsafe_flash_attention/`: graph-safe INT4 source and
  generated research state;
- `experiments/qwen36-27b-autoround-int4-b70/`: INT4/MTP research packet and
  diagnostic artifacts.

Large ignored Qwen artifacts may be archived only after a complete inventory,
hash verification, and a recorded restore path. Never use broad `git clean` or
delete tracked experiment material to make the tree look tidy.

## Paused And Bookmarked Lanes

- [Qwen family map](docs/qwen36-research-map.md)
- [Muse-Glimmer-30B Q8/WOQ](results/muse-glimmer-30b-q8-woq-b70/README.md)
- [Laguna S 2.1 INT4](results/laguna-s-2.1-int4-b70/README.md)
- [DeepSeek V4 Flash K160](results/deepseek-v4-flash-k160-b70/README.md)
- [Gemma 4 26B A4B Q8](results/gemma4-26b-a4b-q8-b70/HANDOFF.md)
- [MiniMax M2.7 INT4](results/minimax-m27-int4-autoround-b70/README.md)
- [all model efforts](docs/model-effort-index.md)
- [promoted performance scoreboard](results/scoreboard.md)

These are reproducible or resumable lanes, not claims about the currently
loaded service.

## Immediate Manager Actions

1. Preserve the inactive Muse fleet and its source; verify service/process state
   again before every GPU launch.
2. Continue Qwen3.8 Q8_0 target-only TP2 from the accepted source snapshot,
   with same-binary controls, the fixed cold gate, and the semantic suite. Aim
   for 40 tok/s without weakening weights, KV precision, or arithmetic gates.
   The 2026-08-16 device-local Q8 gate/up/SwiGLU experiment is closed at
   `-0.224974%` after restoring its downstream Q8 producer; retain the
   [negative packet](experiments/qwen38-27b-b70/notes/2026-08-16-q8-fused-mmvq-swiglu-negative.md)
   and do not enable its default-off door in the accepted recipe.
   The c2 cache-row state-I/O fusion is also closed: it gained `+5.355%` in
   synthetic batched-bench but converged to the same endpoint plateau and did
   not satisfy strict cross-batch output invariance. Preserve the
   [neutral packet](experiments/qwen38-27b-b70/notes/2026-08-16-q8-c2-cache-row-fusion-neutral.md)
   without adding its aggregate rate to the promoted board.
   Distributed greedy argmax is closed as exact but neutral: the
   position-balanced primary delta was `-0.057%`, full-output rate was
   `+0.342%`, and TTFT regressed `+8.311%`. Preserve its
   [packet](experiments/qwen38-27b-b70/notes/2026-08-16-q8-distributed-greedy-argmax-neutral.md)
   and only revisit if winner selection can avoid the added cross-queue sync.
3. Use the official FP8 graph repro as the vLLM control and target its Triton
   GDN/state-I/O and TP2 synchronization path; simple oneCCL P2P access is
   already closed as neutral. Preserve the 9/12 GiB host cgroup.
4. Keep SergiioB's single-card GPTQ/MTP vLLM recipe experimental: it is fast,
   but the checkpoint failed the no-quality-loss semantic gate. Never stop a
   vLLM XPU container before `/health` during graph initialization.
5. The 49.717503 tok/s Q4_K_M target-only result is submitted and approved as
   LocalMaxxing `cmsy530c70cpwms01bl1sjk6g`; do not resubmit it unchanged.
6. Keep `main` synchronized before and after focused commits. Preserve failed
   experiments as patches and notes rather than branches or worktrees.
7. Archive large ignored Qwen artifacts only through the verified manifest and
   restore procedure linked from the Qwen family map.
