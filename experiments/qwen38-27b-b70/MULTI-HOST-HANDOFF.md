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

## Official FP8 vLLM/XPU baseline

- model: `Qwen/Qwen3.8-27B-FP8`
- revision: `017b9c7af6b5689d5dd426a76e0bc077eb5ca20a`
- aggregate 66-file weight manifest SHA-256:
  `82fb8f84fa117c81c3e8639c4675709dfb667d70ddaa2fd097d35fc37d95453a`
- runtime: pinned vLLM/XPU container with vLLM `0.27.2rc1.dev77`
- result: `21.708532 tok/s`, TP2 target-only, native FP16 KV, graph c1
- restore/run: [standalone repro](../../repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/README.md)

This lane is slower than GGUF Q8 but provides the clean vLLM source-level
control. Its semantic/repeat/long-context hashes matched the Q8 oracle. Keep
the TP2 graph experimental, preserve the 9/12 GiB host bounds, and do not claim
arbitrary-prompt token-exactness.

## Latest closed candidates

Three newer, low-risk compiler/kernel arms are also closed:

- reordered-Q8 loop unroll by two was neutral (`+0.076%` overall);
- fused gate/up Q8 row-chunk interleaving appeared `+1.331%` when all
  treatments occupied middle process positions, then reversed to `-1.669%`
  in the position-balanced `B-A-A-B` confirmation; it was a run-position
  artifact, not a kernel win;
- selective per-kernel 256-GRF was safe but `2.789%` slower.

Use the [do-not-repeat index](DO-NOT-REPEAT.md) for their exact source patches,
hashes, measurements, and local evidence paths. Neither belongs in the
accepted reproduction.

The earlier root-fused per-owner handoff is likewise closed:

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

Do not spend another host on mode 4 unchanged. The reference host currently
claims the peer-mapped vec4 collective cache-hint arm; see the
[active note](notes/2026-08-16-q8-peer-collective-cache-hints-active.md).
Check `origin/main` before opening another target-only Q8 candidate.

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
