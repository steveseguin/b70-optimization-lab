# Qwen3.8 Flash-Next FP8 M1 W13 XPU-graph census A1

Date: 2026-09-01
Status: frozen before GPU execution

## Question

Does a phase-specific W13 Triton launch configuration reduce the exact
production M1 routed-MoE component latency under XPU graph replay while W2,
weights, routing semantics, and outputs remain unchanged?

This is a one-B70 component discovery experiment. It is not a serving result,
does not alter any protected speed claim, and does not authorize an endpoint
load. The existing audited component gate is reused unchanged.

## Frozen identity

- model: `Qwen/Qwen3.8-Flash-Next-FP8` from the checksum-identical external
  copy at `/mnt/usb-models/llm-models/Qwen3.8-Flash-Next-FP8`; this avoids
  adding load to the local NVMe after A55 reached its corrected-event bound;
- revision: `bcd9f01ddc9cff2316eb84281bebcd5b058bddce`;
- index SHA-256:
  `0419e2c2dfbb925257d7409405433a793cf7ff7d96f3eba882a815ec6d9fe7a6`;
- config SHA-256:
  `99c11efba4012d0f760f4e4831a8d6cafd845044e21d0aa9e6d9e70a15a90a8d`;
- layer-0 gate/up shard SHA-256:
  `6841fe21fa8a8a7a693c585efe65cd2732889095b696da88bda0cb287366910b`;
- layer-0 down shard SHA-256:
  `974a2a2ab551f8f1405a4955ab32a8721c68c73dd85b382491d9f0e6a34ee752`;
- vLLM head: `cbc3cb588a7cae8dcc489fb4dfc1a800d19980d9` with no
  tracked-source changes;
- vLLM XPU kernels head: `e421889999bc1e5a5f11044d14548b9afdba644d`
  with no tracked-source changes;
- staged runtime:
  `/mnt/usb-models/qwen38-build/runtime-core-moe-negidguard-b70`, checked by
  manifest SHA-256
  `9fa443fdb7a6d0042cf04f859cc6fd6a7bdc09943e16cafb4ea084573c892d2b`;
- fused-MoE source SHA-256:
  `4b376eb5e22e7972a1d70e4012999650ab961719d6309cbec27a6104fa64d0a0`;
- Triton-experts source SHA-256:
  `b8a461b712b88cf6ab5ba4f49029fddce3a501f7ff909b276b6de04b808da4c2`;
- modular-kernel source SHA-256:
  `1e60aca6ed0dd4fcb46d577897ff1651f27a6130b3449d22265c0c791beec5d5`.

Frozen experiment files:

- component gate SHA-256:
  `f8682c52b0d9df911bc84295df85be9f41f0429b17431388fea60a04a9484d6c`;
- component-gate tests SHA-256:
  `d58ebb6a0b5621d12c169cbd38ac8643a320b580954b81d03a82b2875d1a646a`;
- discovery runner SHA-256:
  `8ab0d38acaa04fed918c0a30a10bf778d400b8513774e54834bc739d52173362`;
- summarizer SHA-256:
  `3118649c294c23fa37b8d84de77b34f0b2009775129a86b47257d69c64688869`;
- summarizer tests SHA-256:
  `ac1a84c4ebf7e0bbf57477cd2e8cbb1d11befb210839e9f5c20c48075bed1b35`.

## Exact component shape

- one visible XPU selected as `level_zero:0`;
- logical EP4 rank `0`, 512 global and 128 local experts;
- M1, hidden size 2560, local intermediate size 640, top-k 10;
- dynamic block FP8 with block shape `[128,128]`;
- exact layer-0 checkpoint weights and scales;
- seed `20260827`, hidden scale `0.01`;
- modular production MoE path and a clean static `torch.xpu.XPUGraph`.

## Candidates and controls

The retained control is the common-warps-8 configuration: M16, N64, K128,
group 1, split-K 1, four stages, eight warps. Every candidate changes only a
nested `W1_CONFIG`; W2 must resolve byte-for-byte to that retained control.

1. `w13-warps4`: `{"W1_CONFIG":{"num_warps":4}}`;
2. `w13-n32`: `{"W1_CONFIG":{"BLOCK_SIZE_N":32}}`;
3. `w13-n128`: `{"W1_CONFIG":{"BLOCK_SIZE_N":128}}`;
4. `w13-n256`: `{"W1_CONFIG":{"BLOCK_SIZE_N":256}}`;
5. `w13-stage5`: `{"W1_CONFIG":{"num_stages":5}}`;
6. `w13-k64`: `{"W1_CONFIG":{"BLOCK_SIZE_K":64}}`.

Each candidate owns three fresh processes in exact order:

1. protected `control-before`;
2. candidate, bound through `--control-authority-json` to the raw one-line
   control-before result;
3. protected `control-after`, bound to the same authority.

The first `w13-warps4` control-before is also the first actual one-XPU graph
smoke. Any failure there stops the entire experiment. Every control failure
stops. A candidate process may fail closed—for example because its tiling
changes an output byte. Its stderr and exit code are retained, the matched
control-after must still pass, and that candidate cannot advance.

## Correctness and timing gates

Every passing arm requires:

- 100 changing hidden/router/route inputs;
- 100 unique eager output hashes;
- 100 unique graph output hashes;
- exact eager-versus-graph hash-list equality;
- candidate/control-after equality to all 100 control-before hashes;
- zero exit-code receipts for every qualifying arm;
- one unchanged identity across every control bracket in the whole census;
- exact model, layer, rank, seed, source, runtime, shard, and config receipts;
- unchanged protected W2;
- finite positive graph timing.

Timing excludes graph capture and input copies. Each bracket uses the same
rank-0 fixed timing fixture. Raw timings from different ranks are never pooled.
The bracket control is the mean of the before/after medians. A candidate is a
discovery positive only if it is exact, its control drift is at most `2%`, and
its matched latency reduction is at least `3%`.

## Bounded confirmation boundary

This runner does **not** dynamically execute confirmation. If at least one
candidate qualifies, the summarizer selects the largest matched reduction and
emits `confirmation-packet.json` with status `frozen_not_executed`. A separate
reviewed runner would then cover:

- layers `0` and `47`;
- EP ranks `0`, `1`, `2`, and `3`;
- seeds `20260826`, `20260827`, and `20260830`;
- one fresh C/A/C bracket for every cell: 24 cells and 72 processes.

That later confirmation must freeze the layer-47 checkpoint shard hashes,
retain exactness in all 24 cells, reject any cell above `2%` control drift,
show a median matched reduction of at least `3%`, be positive in at least 20
cells, and have no cell regress by more than `2%`. It must aggregate only
within-cell candidate/control ratios, never raw timings across ranks.

## Closed exclusions

This experiment does not retry flat/common warps 8, any W2 delta, W2 N32,
W2 K64, common stage 3, grouped-M candidates, `BLOCK_SIZE_M`, split-K,
`GROUP_SIZE_M`, M4/M>1 shapes, synthetic weights, endpoint serving, MTP, PLE,
or any full-model load. It does not require a reboot.

The evidence root is frozen as:

`/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/components/20260901-moe-m1-w13-xpu-graph-census-a1`
