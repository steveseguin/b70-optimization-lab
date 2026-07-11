# Current Workspace State

Last reviewed: **2026-07-11**

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

The active research lane is **Qwen3.6 27B AutoRound INT4, TP2 on two Intel Arc
Pro B70 GPUs**.

- [Lane handoff](results/qwen36-27b-autoround-int4-b70/HANDOFF.md)
- [Result packet](results/qwen36-27b-autoround-int4-b70/README.md)
- [Current promoted TP2 evidence](results/qwen36-27b-autoround-int4-b70/tp2-fp16-capture-gdn-20260711.json)
- [Reproduction entry point](repro/qwen36-27b-autoround-int4-b70/README.md)
- [Experiment workspace](experiments/qwen36-27b-autoround-int4-b70/README.md)

The current promoted captured-GDN FP16-compute result is **91.714405 tok/s
median** on the fixed 12-prompt cold realistic gate, with a pair-swapped high
of `92.637225`. The linked packet owns the complete identity, crossover, and
quality evidence; exact cases, repeat128, baseline parity, and the 1K needle
passed. LocalMaxxing approved it as `cmrgojixq005rmj0141e9fjj2`.

### Protected In-Flight Work

No main-repository path is intentionally left uncommitted after the FP16
promotion. Recheck `git status` before starting another experiment.

Treat the Qwen lane's external vLLM, XPU-kernel, oneCCL, build, cache, and result
trees as mutable research state. Inspect them before use and do not reset,
clean, rebuild, or switch them during unrelated work.

## Paused And Bookmarked Lanes

- [Gemma 4 26B A4B Q8](results/gemma4-26b-a4b-q8-b70/HANDOFF.md)
- [MiniMax M2.7 INT4](results/minimax-m27-int4-autoround-b70/README.md)
- [Qwen3.6 35B Quark INT8](results/qwen36-35b-quark-int8-b70/README.md)
- [All model effort packets](docs/model-effort-index.md)

These are reproducible or resumable lanes, not claims about the currently
loaded service.

## Immediate Manager Actions

1. Let the active Qwen lane handoff and result packet carry its detailed next
   experiment; do not duplicate it here.
2. At promotion time—not during rapid iteration—record each external source
   tree's path, commit, dirty state, and relevant aggregate patch snapshot.
3. Update the [performance index](results/scoreboard.md) for representative
   verified expectations and the [LocalMaxxing ledger](results/localmaxxing-submissions.md)
   only for actual public submissions.

The detailed state formerly accumulated in this file remains available in Git
at commit `95b4ca413` (`git show 95b4ca413:CURRENT.md`).
