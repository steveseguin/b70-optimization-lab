# Current Workspace State

Last reviewed: **2026-08-14**

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

Verified on 2026-08-14:

- `muse-glimmer-bf16-fleet.service`: active;
- `muse-glimmer-frontdoor.service`: active;
- frontdoor: `0.0.0.0:8000`;
- text backend: `127.0.0.1:19470`;
- vision backend: `127.0.0.1:19471`;
- served identity: `muse-glimmer-30b-bf16`;
- text lane: TP2 BF16 target with BF16 DFlash;
- vision lane: BF16 target with kquant draft and `mmproj`.

The active source/build is under `/home/steve/src/llama.cpp-muse-100`. Do not
reset, clean, rebuild, restart, or repurpose that tree while the fleet is live
without first checking service ownership and the canonical host GPU lock.

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

Qwen3.6 27B Q8_0 target-only TP2 on two ASRock B70s is active toward a
40 tok/s stretch goal. DFlash, MTP, prompt reuse, and other speculation remain
outside this objective. The current clean source adds a register-direct TP2
Q8 handoff and direct IMRoPE-to-indexed-F16-KV-cache writes to the previously
promoted exact fusion stack.

All Git work is performed directly on `main`. Do not create branches or
secondary worktrees. Use focused commits, patches, bundles, configs, and result
packets for isolation and recovery.

## Active Research: Qwen3.6 27B Q8 TP2

The promoted target-only two-B70 result remains:

- conventional 99-interval median: **`35.832213 tok/s`**;
- historical helper: `36.194155 tok/s`;
- full-512 after-TTFT median: `35.711040 tok/s`;
- quality: 12/12 cold 512-token outputs exact against the accepted control;
- cache: `cached_tokens=0` for 12/12;
- speculation: none.

The 2026-08-14 pass-2 register-direct Q8 handoff and direct IMRoPE cache-write
stack passed a clean rebuild, one-prompt oracle, and complete 12-prompt cold
suite. The output oracle remains unchanged; the new full patch, binaries,
runtime doors, raw result, and summary are preserved in the linked repro.

Resume and evidence:

- [Qwen TP2 handoff](results/qwen36-27b-q8-tp2-asrock-b70/HANDOFF.md)
- [promoted result packet](results/qwen36-27b-q8-tp2-asrock-b70/README.md)
- [standalone reproduction](repro/qwen36-27b-q8-tp2-asrock-b70/README.md)
- [complete source patch](patches/qwen36-27b-q8-tp2-asrock-b70/README.md)
- [pass-1 chronological ledger](notes/2026-08-14-qwen36-q8-tp2-40tps-pass1.md)
- [pass-2 chronological ledger](notes/2026-08-14-qwen36-q8-tp2-40tps-pass2.md)
- [Qwen family research map](docs/qwen36-research-map.md)

Do not retry the built-in TP2 SYCL profiler or the unsafe root-both remote-write
prototype. Both caused device faults/resets. Other pass-1 candidates were
rejected or neutral and should not be recycled without a materially different
hypothesis.

## Protected Work And Artifacts

Preserve these paths and inspect their status before any build, cleanup, or
service change:

- `/home/steve/src/llama.cpp-muse-100`: source/build used by the live Muse fleet;
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

1. Keep the live Muse fleet untouched while choosing the next model.
2. Treat the Qwen Q8 TP2 record as closed; start from its handoff if a genuinely
   new hypothesis justifies reopening it.
3. For the next model, create a distinct result identity and begin with hashes,
   a clean baseline, fixed prompts, cache-zero controls, and preregistered
   quality/speed gates.
4. Keep `main` synchronized before and after focused commits. Preserve failed
   experiments as patches and notes rather than branches or worktrees.
5. Archive large ignored Qwen artifacts only through the verified manifest and
   restore procedure linked from the Qwen family map.
