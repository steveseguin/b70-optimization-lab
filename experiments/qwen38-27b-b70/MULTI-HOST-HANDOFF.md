# Qwen3.8 27B multi-host handoff

Last audited: 2026-08-16

This packet lets another B70 system reproduce the accepted lanes or take an
unclaimed optimization arm without relying on paths or uncommitted source from
the reference host.

## Synchronize first

From an existing clean clone:

```bash
experiments/qwen38-27b-b70/scripts/sync-worker.sh
```

The script refuses dirty worktrees and non-`main` branches. If an agent has
local work, it must commit that work on an intentional branch or stash it
manually before synchronizing; the script never discards changes.

Before starting an experiment, read the
[do-not-repeat index](DO-NOT-REPEAT.md). It maps both Qwen3.8-specific work and
the inherited Qwen3.6 search history.

## Accepted Q8_0 lane

- model repository: `ggml-org/Qwen3.8-27B-GGUF`
- revision: `0669b98607d47046c7c2b3f801011d54a08cfccf`
- file: `Qwen3.8-27B-Q8_0.gguf`
- bytes: `28,595,763,552`
- SHA-256: `f5c702d8820d36fb55985bb238fc83ee3a313e920f4b752a437c3a6a9e14e4c8`
- result: `36.772932 tok/s` conventional, TP2 target-only
- restore/build/run: [standalone repro](../../repro/qwen38-27b-q8-tp2-asrock-b70/README.md)
- exact full source delta: [patch packet](../../patches/qwen38-27b-q8-tp2-asrock-b70/README.md)

Restore the public mndodd base commit, decode and checksum the Git-resident
patch, run `git apply --check`, then apply it. Do not copy a dirty source tree
from another machine. The reproduction packet contains all runtime doors and
the accepted binary hashes.

## Accepted Q4_K_M lane

- model repository and revision: same as Q8_0 above
- file: `Qwen3.8-27B-Q4_K_M.gguf`
- bytes: `18,973,870,432`
- SHA-256: `31629f53165ab6a7dad8c9847dcfd1fdf55829dac1e6e748f4a68581b0033d34`
- result: `49.717503 tok/s` conventional, TP2 target-only
- restore/build/run: [standalone repro](../../repro/qwen38-27b-q4km-tp2-asrock-b70/README.md)
- exact incremental source delta and required base stack:
  [patch packet](../../patches/qwen38-27b-q4km-tp2-asrock-b70/README.md)

The Q4_K_M increment is not standalone. Apply its documented full lab base
stack first, then its incremental patch, checking both decoded SHA-256 values.

## Latest closed candidate

The root-fused per-owner handoff has been tested and closed:

- status: safe and exact at the benchmark gate, but `-3.388%` slower than the
  position-balanced mode-2 control;
- accepted Q8 full patch must be applied first;
- incremental patch:
  [`q8-root-fused-collective-untested-20260816.diff.gz.b64`](patches/q8-root-fused-collective-untested-20260816.diff.gz.b64);
- decoded patch SHA-256:
  `e864bf0dafcd323df330761b9048edc46875b020cf38f707175b3c53e019899c`;
- runtime door: `GGML_SYCL_COMM_DIRECT_Q8=4`;
- complete result:
  [negative-result note](notes/2026-08-16-q8-root-fused-candidate-negative.md).

Do not spend another host on mode 4 unchanged. There is currently no claimed
active target-only Q8 candidate; check `origin/main` before opening one.

Mode `3` is not an alternative candidate. Its peer-writing design caused a
device-lost/reset storm and is permanently quarantined. Never enable or port
it without a fundamentally different ownership/synchronization proof.

## Quality and benchmark contract

A machine may publish a candidate only after all of these hold:

1. target-only result unless explicitly labeled otherwise—no MTP, DFlash,
   draft model, or hidden speculation;
2. F16 KV for the promoted Q8/Q4 service lanes;
3. each fixed-suite prompt sent once with every `cached_tokens` count zero;
4. conventional 99-interval metric, not the historical 100-event helper;
5. exact complete-output hashes against the matching reasoning/API-mode oracle;
6. Qwen3.8 semantic canaries and the long-context needle pass;
7. exact model revision/SHA, source base, decoded patch SHA, binary hashes,
   compiler, runtime flags, GPU count/topology, and reasoning mode recorded;
8. no current-boot Xe/GuC fault, reset, timeout, or hang.

Run [the post-reboot gate](scripts/post-reboot-gpu-gate.sh) before an unsafe or
new collective experiment. Device enumeration can differ across hosts; verify
the physical BDF mapping before copying the reference selector
`level_zero:1,0`.

## Multi-agent coordination

- Fetch `origin/main` and check this handoff immediately before choosing work.
- Use a new source/build directory for every candidate.
- Add the hypothesis to the do-not-repeat index or a new note before a risky
  run, so another system can see that the arm is claimed.
- Commit and push a small checkpoint after source/patch staging and again after
  a measured result. Fetch before each commit; never force-push shared `main`.
- Record neutral, negative, quality-failed, and unsafe outcomes—not only wins.
- Preserve an exact incremental patch and decoded checksum for every source
  experiment that reaches execution.
- Do not promote a result from a dirty source tree without reconstructing it
  from the public base plus Git-resident patches.

## What Git does not contain

Git contains source patches, recipes, decisions, structured summaries,
quality policy, and small evidence. It intentionally does not contain model
weights, compiled binaries, or all large raw logs. Download models by the
revision and SHA above, rebuild binaries from the patches, and keep new raw
logs locally while committing their paths, hashes, and summarized metrics.
