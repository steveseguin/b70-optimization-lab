# Qwen3.8 Flash-Next FP8 M1 W13-N32 config integration A1

Date: 2026-09-02
Status: default-off map and static resolver contract pass; component integration
execution not yet run

## Decision

The smallest exact integration is configuration-only. The retained
`configs/moe-warps8-m1` map is copied to `configs/moe-m1-w13-n32`, and the
candidate adds only this nested delta to key `1`:

```json
"W1_CONFIG": {"BLOCK_SIZE_N": 32}
```

This packet makes no live vLLM or kernel source change. It requires the already
applied, default-off per-phase resolver at vLLM head
`cbc3cb588a7cae8dcc489fb4dfc1a800d19980d9`, preserved as
`patches/qwen38-flash-next-fp8-b70/vllm/0021-Add-opt-in-per-phase-Triton-MoE-configs.patch`
with SHA-256
`ad820bad443bba32f15b114ea76b4deb4dade754fe1bc362faddfef07eb6c519`.
Without that exact prerequisite, nested `W1_CONFIG` is not an authorized
integration mechanism. The candidate folder itself remains default-off: it has
no effect unless an experiment explicitly selects it through
`VLLM_TUNED_CONFIG_FOLDER`.

The live modular XPU resolver enables phase-specific entries only for M1,
FP8-W8A8, block shape `[128,128]`. Under that exact path, the key-1 common
configuration remains M16/N64/K128, eight warps, and four stages. W13 alone
overrides N64 to N32; W2 retains N64. Phase deltas are removed from legacy or
phase-disabled callers, and requests with M greater than one retain the
nearest-key behavior of the base map.

## Frozen static identity

- retained map SHA-256:
  `91e5d8b692da3febbba7cb07ee4fdab319909da0c82c1fda95b92dc42d680464`;
- candidate map SHA-256:
  `a8f1f8982e3e1af80ff31b9e0a00afaacf1af1b3c401585109b4d60d3c8267be`;
- prerequisite per-phase resolver patch SHA-256:
  `ad820bad443bba32f15b114ea76b4deb4dade754fe1bc362faddfef07eb6c519`;
- verifier SHA-256:
  `a464b0f6a46e9149b33e5ccca772bf21385532693e78b691ca010a7833be2e6f`;
- verifier tests SHA-256:
  `28811aca31ed1248d3c04b300af775ca21d63babc605d65fa067e42380e37268`;
- live `fused_moe.py` SHA-256:
  `4b376eb5e22e7972a1d70e4012999650ab961719d6309cbec27a6104fa64d0a0`;
- live `triton_moe.py` SHA-256:
  `b8a461b712b88cf6ab5ba4f49029fddce3a501f7ff909b276b6de04b808da4c2`;
- live `modular_kernel.py` SHA-256:
  `1e60aca6ed0dd4fcb46d577897ff1651f27a6130b3449d22265c0c791beec5d5`.

The verifier imported the official resolver in the staged server environment
and checked every integer M from 1 through 512. It passed: M1 resolved to
W13-N32 and W2-N64, every M2--M512 result matched the retained map, and the
legacy M1 API remained flat. The deterministic static receipt SHA-256 was
`933d275e369ba3b11054587563149f94bf5f7a3a471bc8b5645ce9e58ebe6ff3`.
The receipt binds both the exact vLLM Git head and the tracked prerequisite
patch. Seven CPU tests pass, including rejection of a W2 delta and any non-M1
map change. Equality of the non-M1 entries is semantic JSON-object equality;
the verifier does not claim a byte-range comparison inside the two files. This
is selection evidence, not inference evidence.

## Evidence boundary and expected effect

The clean A2 confirmation already established the exact effective treatment
across layers 0 and 47 and EP ranks 0--3: 8/8 matched cells passed 100 changing
eager/graph inputs, with a median reduction of `22.246154%` and a worst-cell
reduction of `21.551557%`. Its median matched absolute saving was
`48.2976 us` per W13 call. A28 observed one W13 and one W2 fused-MoE call in
each of 48 target layers, so simple multiplication gives a non-promotional
component projection of about `2.3183 ms/token` (`2.2373--2.3497 ms/token`
over the eight A2 cells). This is not an endpoint speed claim.

A31 proved that the retained tuned folder could be selected during TP4 startup,
but sent no inference request. A32 fixed its client binding and is the actual
endpoint evidence for that same `moe-warps8-m1` base. A32 preserved the short
output hash but measured only `5.421586 tok/s`, `1.70777%` below the protected
`5.515783 tok/s` baseline. Its two exact-4K rows also differed from each other
and from authority. The common M1 warps-8 base is therefore a lossless
short-output performance negative and a 4K reliability negative, not an
accepted endpoint baseline.

Applying the A2 median component saving arithmetically to A32 would project
only about `5.4906 tok/s`: faster than A32, but still about `0.4566%` below the
protected result. That projection has no measurement credit and makes the
endpoint's dual performance threshold mandatory.

## Next bounded qualification

Before a full-model arm, run one config-folder-selected real-weight component
qualification using the existing A2 identity and acceptance logic:

1. Resolve the base and candidate through their actual
   `VLLM_TUNED_CONFIG_FOLDER` values in each process; do not inject an
   unbound free-form kernel configuration.
2. Use layers 0 and 47, EP ranks 0--3, seed `20260827`, and matched
   control/candidate/control ordering.
3. Require all eight cells to match their control authority for all 100
   changing eager and captured inputs, all 24 process exits to be zero, control
   drift at most 2%, median reduction at least 3%, at least 7/8 positive cells,
   and no cell worse than -2%.
4. Record an in-process resolver receipt proving W13 N32, W2 N64, selected key
   1, eight warps, and the exact map/source hashes above.
5. Preserve the A2 host-health, checkpoint, teardown, no-clobber, and clearance
   gates. Use new result, cache, lock, and derived-runner paths. No reboot or
   full-model load is part of this component step.

Only that pass authorizes an endpoint candidate. A28 is the workload-share
reference, not a serving baseline. A55 is the current-source TP4/EP4, MTP0,
`FULL_DECODE_ONLY`, synchronous-PLE endpoint identity reference, but its
`twoshots` collective was slower than A44 and is already a bounded negative.
Do not inherit that negative selector silently. Freeze a matched current-source
control/candidate pair with identical model, placement, graph, collective,
cache, prompts, and quality battery; the sole candidate delta must be the exact
tuned-folder selection above. A candidate passes performance only if it beats
both its matched current-source base-map control and the protected
`5.515783 tok/s` baseline. It must also pass the exact-4K authority and
fresh-service reliability gates; merely repairing A32's speed is insufficient.
Protected results remain unchanged until all of those gates pass.

Structured packet:
[`20260902-moe-m1-w13-n32-config-integration-a1-prereg.json`](../data/20260902-moe-m1-w13-n32-config-integration-a1-prereg.json).
