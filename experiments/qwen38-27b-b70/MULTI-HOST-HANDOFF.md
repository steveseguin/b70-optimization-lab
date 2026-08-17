# Qwen3.8 27B multi-host handoff

Last audited: 2026-08-17

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

The exact 11-bit reordered-Q8 scale-dictionary arm is closed. Its slow revision
passed only a one-token smoke and had multi-minute setup; direct lookup
revisions then failed the safety gate with a host segfault and an invalid Level
Zero memory object. See the [result](notes/2026-08-17-q8-exact-scale-dictionary-active.md).
Do not duplicate either retained patch unchanged.

The materially different compile-time encoder-map retry is also closed. It
removed the runtime-USM failure and passed prompt+decode safety, but regressed
the position-balanced screen by `5.360%`; see the
[result](notes/2026-08-17-q8-exact-scale-dictionary-static-map-active.md).
Do not duplicate the retained static-map increment unchanged.

## Accepted Q8_0 lane

- model repository: `ggml-org/Qwen3.8-27B-GGUF`
- revision: `0669b98607d47046c7c2b3f801011d54a08cfccf`
- file: `Qwen3.8-27B-Q8_0.gguf`
- bytes: `28,595,763,552`
- SHA-256: `f5c702d8820d36fb55985bb238fc83ee3a313e920f4b752a437c3a6a9e14e4c8`
- result: `36.772932 tok/s` conventional, TP2 target-only
- restore/build/run: [standalone repro](../../repro/qwen38-27b-q8-tp2-asrock-b70/README.md)
- exact full source delta: [patch packet](../../patches/qwen38-27b-q8-tp2-asrock-b70/README.md)
- accepted 2026-08-17 increment: recurrent-quad SG16, two opposite-order
  realistic pairs pooling to `+0.257%` primary median with exact quality;
  the historical headline remains unchanged

Restore the public mndodd base commit, decode and checksum the Git-resident
patch, run `git apply --check`, then apply it and the documented Qwen3.8 SG16
increment. Do not copy a dirty source tree from another machine. The
reproduction packet contains both checksums, all runtime doors, and the
accepted binary hashes.

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

Do not spend another host on mode 4 unchanged. The peer-mapped vec4 collective
cache-hint arm is also closed as performance-neutral; see the
[result note](notes/2026-08-16-q8-peer-collective-cache-hints-active.md).
The exact Q8 ESIMD SIMD16 row-body arm is now closed: it was output-exact and
the poison proof confirmed that all routed families were live, but it was
`0.699%` slower in a position-balanced screen. The direct implementation patch
and the failed `invoke_simd` AOT history are in the
[result note](notes/2026-08-16-q8-esimd-dp4a-active.md). Do not repeat either
implementation unchanged. Check `origin/main` before opening another
target-only Q8 candidate.

The exact clean oneAPI 2026.1.1 AOT compiler-refresh arm is closed. The fixed
completion was byte-exact, but its position-balanced decode result was
`36.805803` versus `36.804243 tok/s` for the 2026.1.0 image (`+0.0042%`). See
the [result note](notes/2026-08-16-q8-oneapi-2026.1.1-refresh-active.md) and
structured
[data](data/2026-08-16-q8-oneapi-2026.1.1-refresh-neutral.json). Do not repeat
the identical compiler-only rebuild.

Upstream gated-delta-net state-writeback fusion commit `3d9388535` is closed
for this stack without a build. The accepted repro already enables its older,
stricter `GGML_SYCL_FUSED_GDN_STATE_IO=1` path, which removes both the input
GET_ROWS and output CPY and previously delivered a matched `+3.132%`. The
upstream symbol names differ, which caused the initial overlap check to miss
it. See the corrected
[audit](notes/2026-08-16-q8-upstream-gdn-cache-fusion-active.md). Do not port
or benchmark upstream `3d9388535` unchanged.

The trace-driven queue-0 local-ready event-elision arm is now closed. Normal
output was exact and poison proved that the branch was live, but its
position-balanced decode result was performance-neutral (`+0.0247%`). See the
[result note](notes/2026-08-16-q8-local-ready-elision-active.md), structured
[data](data/2026-08-16-q8-local-ready-elision-neutral.json), and incremental
[patch](patches/q8-local-ready-elision-neutral-20260816.diff). Do not repeat
the exact event-elision arm unchanged.

The compile-time FFN-shape MMVQ arm (K8704/N5120 down plus fused
K5120/N8704 gate/up) is now closed. Both specializations were live on both
devices, the 128-token output was exact, and poison proved reachability, but
the position-balanced result was performance-null (`-0.0088%`). See the
[result note](notes/2026-08-16-q8-fixed-shape-mmvq-active.md), structured
[data](data/2026-08-16-q8-fixed-shape-mmvq-neutral.json), and incremental
[patch](patches/q8-fixed-shape-mmvq-neutral-20260816.diff). Do not duplicate
the exact specialization unchanged.

The compile-time recurrent GDN quad specialization is also closed. Its exact
equal-TP2 local shape (`K5120`, rows `5120+3072+24+24`) was live on both
devices and repeated at `+0.741%` in the long `p64/n512` direct benchmark.
However, the matched same-binary 12-prompt service result was `-0.0664%` by
the conventional metric. All 12 outputs, seven semantic canaries, eight
repeats and the 3,829-token needle matched the promoted oracle exactly. See
the [result note](notes/2026-08-17-q8-recurrent-quad-fixed-shape-active.md),
structured
[data](data/2026-08-17-q8-recurrent-quad-fixed-shape-service-neutral.json),
and incremental
[patch](patches/q8-recurrent-quad-fixed-shape-service-neutral-20260817.diff).
Keep it as a synthetic diagnostic and do not add it to the accepted service
repro unchanged.

The recurrent-quad SG32 follow-up to accepted SG16 is closed. An initial
eight-process order falsely showed `+1.664%`; swapping every arm position
reversed it to `-2.096%`. Across the unbiased 16-run combination, SG32 was
`-0.233%` versus SG16. See the
[result note](notes/2026-08-17-q8-recurrent-quad-sg32-active.md), structured
[data](data/2026-08-17-q8-recurrent-quad-sg32-negative.json), and incremental
[patch](patches/q8-recurrent-quad-sg32-negative-20260817.diff). Retain SG16.

The shape-scoped SG4 follow-up is also closed. It independently changed only
the dominant fused gate/up pair and/or down-projection workgroup population.
Both shapes announced on both devices and the smoke ended with
`VERIFY_MISMATCH=0`. A first four-arm screen misleadingly showed `+1.252%`
when both doors were enabled, but an eight-process confirmation balanced for
the observed odd/even run-position state measured `36.925030` versus
`37.025710 tok/s` control (`-0.272%`), with its two blocks disagreeing. See the
[result note](notes/2026-08-17-q8-ffn-shape-scoped-subgroups-active.md),
structured [data](data/2026-08-17-q8-ffn-shape-scoped-sg4-negative.json), and
incremental [patch](patches/q8-ffn-shape-scoped-sg4-negative-20260817.diff).
Retain hardware-derived SG8 and do not retry the exact SG4 admission unchanged.

The register-direct collective tail workgroup sweep is closed. This was not
the old root-reduction WG experiment: it changed the two 5,120-element
residual/RMS/multiply/Q8 tails repeated at all 128 TP boundaries. WG256 was
mechanically safe with `VERIFY_MISMATCH=0`, but a mirrored screen measured
WG1024 `37.171867`, WG512 `36.018933` (`-3.102%`) and WG256 `35.306167 tok/s`
(`-5.019%`). See the
[result note](notes/2026-08-17-q8-collective-tail-workgroup-active.md),
structured [data](data/2026-08-17-q8-collective-tail-workgroup-negative.json),
and incremental
[patch](patches/q8-collective-tail-workgroup-negative-20260817.diff). Retain
the accepted 1,024-work-item tail and do not repeat 256/512 unchanged.

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
