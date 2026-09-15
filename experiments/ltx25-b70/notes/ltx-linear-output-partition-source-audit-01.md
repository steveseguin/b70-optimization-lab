# BF16 output-column partition: bounded sampler source audit

Status: **go for a future isolated exactness experiment; no-go for deployment
or a speed claim.** Native work remains halted by the recorded host OOM/xe
fault. This audit read only source and saved JSON metadata. It did not import
Torch, load weights, run compilation, query devices, or change runtime code.

The best narrow starting point is one video's FF up projection,
`transformer_blocks[24].ff.net[0].proj`. It has BF16 weight `[16384,4096]`, no
bias, and baseline stage inputs `[1,64,4096]` / `[1,256,4096]`. Partition its
**output features** by splitting weight rows into `[8192,4096]` halves. Each
output retains the full 4096-term K dimension; concatenate output halves in
original order on the owning device before the original GELU and down projection.
Block24 normally runs on XPU1, so XPU0 would compute its remote half.

This is algebraically equivalent and needs no cross-device reduction. It is
**not a proof of bitwise equality**: changing GEMM N from16384 to8192 can change
the native kernel, tiling, accumulation order, or epilogue. Preserving K's
length does not force the same floating-point reduction implementation. Even
identical deterministic settings only promise repeatability for a qualified
configuration. Native bytewise tests must decide; no tolerance waiver.

## Concrete shapes and source boundary

Let M be64 at stage1 and256 at stage2, batch1. Shapes below use PyTorch's stored
`W[N,K]`, so output-column partition means splitting dimension0 of W, not K.

| Native layer in each block | Weight N×K | Tokens M | BF16 weight bytes | Bias |
| --- | --- | --- | ---: | --- |
| Video FF `ff.net.0.proj` | 16384×4096 | 64 / 256 | 134,217,728 | absent |
| Video FF `ff.net.2` | 4096×16384 | 64 / 256 | 134,217,728 | absent |
| Video self-attention `attn1.to_q` | 4096×4096 | 64 / 256 | 33,554,432 | 4096 |
| Audio FF `audio_ff.net.0.proj` | 8192×2048 | 26 | 33,554,432 | 8192 |
| Audio FF `audio_ff.net.2` | 2048×8192 | 26 | 33,554,432 | 2048 |

These are saved checkpoint-header shapes, not newly loaded tensors. The existing
native full-block gates additionally recorded BF16 state and both stage input
shapes. All48 checkpoint blocks share these shapes. Video FF up is a focused
first choice because it is one of the largest matrices, has no bias ambiguity,
and offers a clean boundary before a nonlinear operation. No saved measurement
establishes it as the most expensive individual layer.

Frozen `av_model.py:362–373` calls this FF after the original normalization and
adaptive modulation, and applies the residual afterward. `model.py:305–330`
constructs the 4× expansion and invokes `linear_input_act` for the down projection.
For native BF16, `ops.py:958–975` takes the ordinary tanh-GELU followed by the
original Linear; it does not use the INT8 activation-quantizer fusion. Preserve
that complete sequence. Do not move GELU onto independently partitioned paths,
combine both FF matrices, split K in the down projection, or replace the residual.

Attention projection partition is also algebraically possible, but concatenate
before `q_norm`/`k_norm`. `model.py:479–484` explicitly normalizes across **all**
heads; separate per-half norms are a different operation. Leave RoPE, masks,
attention, sigmoid gating and output projection unchanged. The small audio
token count alone does not establish whether communication can be amortized.

Native Linear dispatch is `ops.py:566–576`, including its cast-weight context
and optional weight/bias functions. A future narrow adapter must reject patches,
quantization, training, nonresident state and unsupported layouts; it must retain
the qualified BF16 native operation. It must not globally replace `F.linear` or
all Comfy Linear modules. Start with an isolated operator gate; only afterward
design a per-selected-layer owner/routing adapter around the frozen block.

## Movement, ownership and execution implications

For the chosen up projection, each resident half weighs64MiB. Replicating the
remote half while retaining the full original weight and registration makes
the simplest reversible diagnostic but costs an **additional64MiB** remote
weight. A true storage partition requires moving ownership, not just taking a
slice: a view may retain the full backing allocation. Fresh contiguous halves
can also create a temporary allocation peak. Do not claim memory neutrality or
allow native model accounting to omit the retained remote state.

Each invocation needs the entire BF16 input on the remote device:0.5MiB at
stage1 /2MiB at stage2. The returning remote output is1MiB /4MiB. These are
logical payload sizes, not measured transport or peak-allocation sizes. The
assembled output is2MiB /8MiB; concatenation can temporarily coexist with both
halves. The down-projection alternative sends2MiB /8MiB input and returns
0.25MiB /1MiB output. It should be evaluated separately, not silently coupled.

Current layer sharding executes blocks0–20 on XPU0 and21–47 on XPU1. The other
device is therefore a plausible participant for a given block, but source
ordering is not a utilization measurement. Current routing uses blocking
`.to(..., non_blocking=False)` transfers (`ltx_layer_shard.py:29–37`) and has no
intra-Linear overlap. Two sequential calls plus blocking transfers do not prove
parallel speedup. Any future explicit streams/events must preserve input
lifetime, establish readiness on both devices, and join before original consumers.
Transport topology and actual overlap remain unmeasured.

Existing `verify_placement` requires every registered tensor in each owner on
that owner's device; install also rejects overlapping tensor ownership
(`ltx_layer_shard.py:119–128,167–173`). Dropping remote weights into an ordinary
block would violate these checks. A reviewed candidate needs separately accounted
remote ownership, bounded allocation, clone/restore/load/unload guards, and full
registration identity checks. No existing guard should be relaxed merely to
permit the experiment. Extending the diagnostic to all48 up projections while
retaining originals would add3GiB of weight replicas in total, distributed across
the two devices; that is arithmetic, not proof of available headroom.

## What recorded timings support

Packet11's completed warm requests2–5 in each arm report sampler-node344+368
intervals of3.4975–3.6168s. Stage1 intervals are2.5066–2.6111s and stage2
0.9909–1.0118s. These are approximate client node-event intervals, including
dispatch and other sampler work; they are not synchronized Linear or block
kernel measurements. The campaign later failed during encoder transition and
is incomplete. The inspected single-/multi-block gate receipts do not time
individual blocks or linears. Dividing sampler time by48×11 would not establish
a layer's duration or compute share.

Earlier packet08's exact all48 compilation screen lost paired sampler time
(median+0.927s). Its saved stack samples mix Python, native calls and waits.
Neither evidence identifies the FF projection's critical-path fraction or a
communication break-even point. Output partition is a concrete opportunity to
parallelize existing sequential work, but **no numerical speed prediction** is
justified. A one-layer pass cannot establish the subsecond clip goal.

## Minimum later native proof

After independent design review and fault resolution: first compare the exact
full N native BF16 Linear with two N/2 native linears on the *same device*, using
the actual saved weight and bounded captured stage inputs. Require bytewise
output equality, repeat equality, unchanged metadata and no input/weight mutation.
A failure here rejects the intended partition even before communication. Then
compare both halves across XPU0/1, preserving concatenation order and original
device/stride; retain mismatches and stop on the first failure or device fault.

Only after those gates pass, test the chosen block at both actual stages with
all original flags/contexts, followed by all four original raw clip outputs and
repeat determinism. Measure matched original/candidate/restored requests on one
persistent application, recording isolated operation and end-to-end sampler
intervals separately, with compilation/diagnostic overhead labeled. Require
observed memory safety and no hidden weight transfer per invocation before
extending to additional layers. No such proof was run for this audit.

## Source and evidence identities

Core sources are from frozen `prepared-encoder-host-embedding-11/source` beneath
`/mnt/fast-ai/bench-results/ltx25-baseline-20260913`; lane paths below are relative.

| File | SHA256 |
| --- | --- |
| `comfy/ldm/lightricks/av_model.py` | `6582ee5c9fe1119b0dfa85a7c5e4f6d94a899f3b551b1886546fd787c3799e7d` |
| `comfy/ldm/lightricks/model.py` | `f0292be2a39491d411ad3cf4b58cebd87e62bf2568aafa35814b954828733718` |
| `comfy/ops.py` | `6058f688d936b083c49fa49a57964837476db6d95750ea70198ad60e884ffed0` |
| `scripts/ltx_layer_shard.py` | `0c836c2c19ef678360c4e5dddb09173d60e0fd011e44430370485abd63336d3b` |
| `data/native-block-header-census.json` | `f7920c26c16254268c08dc597deb0e26a9eeffe6a0e819ee52d019c50f1ccffb` |
| `data/host-embedding-screen-01/summary.json` | `4a693f4f6fb11f08b36ad2eb2ff52294cf29e8d6fc456203a477a079bc6a2f80` |
| `data/multiblock-screen-03/summary.json` | `5e7c3d367b99cc8abaf31232e1308e6c19554cb1a54d52f13842a76edb1aa4f6` |
