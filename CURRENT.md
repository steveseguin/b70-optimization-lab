# Current Workspace State

Last reviewed: **2026-08-15**

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
- speculation: none.

The 2026-08-15 Q4_K fusion passed a clean build, mechanism counter, same-binary
control, and complete 12-prompt cold suite. It improved the conventional
median by `+1.701%`; all complete output hashes remained exact. The Q8_0 TP2
transfer separately reached `36.772932 tok/s` conventional with 12/12 matched
complete outputs.

A separate one-B70 SergioB GPTQ INT4 route was validated on 2026-08-16. XPU
graph reached `33.690260 tok/s` target-only versus `25.418419` eager; MTP1/2/4
reached `54.175761`, `68.232180`, and `83.701925 tok/s` at p512/g128, 8K
context and FP8 KV. MTP4 accepted 510/544 drafts and all modes retained 5/5
target-only visible-output hashes. This is a distinct engine/quantization/KV
class and does not replace the active two-B70 GGUF target-only lane. 131K,
runtime draft dtype, and broad semantic quality remain unresolved. An MTP4
patch-off A/B reached `83.697153 tok/s` with identical acceptance/output,
confirming the nightly patch is redundant for this exact 8K route; the 131K
boundary patch remains untested.

Resume and evidence:

- [Qwen3.8 model board](README.md#qwen38-27b-model-board)
- [target-only pass-2 ledger](experiments/qwen38-27b-b70/notes/2026-08-15-target-only-pass2.md)
- [Q4_K_M standalone reproduction](repro/qwen38-27b-q4km-tp2-asrock-b70/README.md)
- [Q4_K fusion source increment](patches/qwen38-27b-q4km-tp2-asrock-b70/README.md)
- [Q4_K structured summary](experiments/qwen38-27b-b70/data/2026-08-15-q4km-tp2-q4k-glu-summary.json)
- [Q8 structured summary](experiments/qwen38-27b-b70/data/2026-08-15-q8-tp2-transfer-summary.json)
- [community GPTQ/MTP vLLM idea](community/sergiiob-qwen38-27b-vllm-xpu/STATUS.md)
- [one-B70 GPTQ target-only graph validation](community/sergiiob-qwen38-27b-vllm-xpu/validation/2026-08-16-local-target-only-graph-validation.md)
- [one-B70 GPTQ native-MTP matrix](community/sergiiob-qwen38-27b-vllm-xpu/validation/2026-08-16-local-mtp-matrix-validation.md)

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
- `/mnt/fast-ai/llm-models/qwen3.8-27b-gptq-int4-mtp/`: hash-verified
  SergioB GPTQ INT4 target with 15 BF16 MTP tensors; community replay lane;
- `/mnt/fast-ai/bench-results/qwen38-q4km-asrock-b70-20260815-pass2/`:
  accepted Q4_K fusion A/B and cold-suite evidence;
- `/mnt/fast-ai/bench-results/qwen38-gptq-int4-asrock-b70-20260816/`:
  SergioB target-only eager/graph validation, failed conservative-U graph
  attempt, logs, inspect records, prompts, and raw SSE evidence;
- `/mnt/fast-ai/src/llama.cpp-q8-tp2-directq8-isolated`: current accepted Qwen TP2 source;
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
2. Continue Qwen3.8 target-only TP2 only from the accepted Q4_K source or its
   standalone reproduction, with same-binary controls and the fixed cold gate.
3. Treat SergiioB's single-card GPTQ/MTP vLLM recipe as a separate
   community-reported lane. Resolve its patch hash, dynamic-exclusion, and MTP
   dtype questions before a bounded replay.
4. Restore the LocalMaxxing credential outside Git, then submit the already
   queued 49.717503 tok/s target-only result after authenticated dry-run.
5. Keep `main` synchronized before and after focused commits. Preserve failed
   experiments as patches and notes rather than branches or worktrees.
6. Archive large ignored Qwen artifacts only through the verified manifest and
   restore procedure linked from the Qwen family map.
