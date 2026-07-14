# DeepSeek V4 REAP/XPU B70 Stage Gates

A stage is incomplete until its evidence and decision are linked from
`../results/experiment-ledger.md`.

## Stage 0: Clean Runtime, Hardware, And Storage Identity

Record:

- clean DeepSeek worktree paths, commits, and diffs;
- vLLM, `vllm-xpu-kernels`, PyTorch XPU, oneAPI, Level Zero, oneCCL, driver,
  kernel, and OS versions;
- XPU inventory, PCIe topology, total memory, and usable memory per B70;
- cold build/import result;
- free space on `/mnt/usb-models`, `/mnt/fast-ai`, and the root filesystem.

The reviewed 2026-07-13 archive action moved about 170 GiB of inactive models
and cache data to external storage with compatibility symlinks. Internal free
space increased from about 11 GiB to about 180 GiB; the external archive still
has more than 2 TiB free.

Pass: clean runtime imports, all four cards enumerate, protected Qwen trees are
untouched, and storage blockers are explicitly recorded.

## Stage 1A: Exact-Shape Low-Level Correctness

Test:

- hidden size 4096;
- intermediate size 2048;
- top-k 6;
- BF16 activation/output;
- M=1, 4, and 8;
- local experts 40, 42, 44, 45, and 64 as supported;
- native MXFP4 and symmetric group-128 INT4 against explicit dequantized
  references using the same stored weights/scales.

Correctness requires:

- no NaN/Inf;
- normalized RMSE at most 0.02 and cosine similarity at least 0.999 against the
  explicit dequantized reference;
- identical routed expert IDs and finite routing weights;
- deterministic repeat output within the selected accumulation tolerance.

`scripts/run-exact-shape-gates.sh` is an initial scaffold: it checks the
existing low-level reference tolerance on one `XpuFusedMoe` process per
physical B70. It does not yet emit explicit RMSE/cosine, repeat determinism,
routing, or allocation evidence, so even a pass does not clear Stage 1A. It is
also not a TP4/EP model test and does not prove loader selection or end-to-end
native dispatch.

## Stage 1B: Native Dispatch And Performance

Performance evidence requires a separate benchmark/trace artifact with:

- median and p10 latency after at least 32 warmups and 200 measured iterations;
- allocation/scratch bytes;
- native backend/class trace;
- 128 direct graph replays without update or rerecord;
- a hard failure if full BF16 expert tensors are materialized.

Stage 1 passes only when at least one low-bit candidate is correct, native, replayable, and at
least 1.5x faster than the explicit BF16 expert path at M=1 and M=4. Record M=8
but do not let it hide a weak single-session path.

Stop: neither low-bit candidate enters the native kernel/replay path or clears
the M=1/M=4 threshold.

## Stage 2: Expert Construction

For the frozen public K160 smoke checkpoint, first assert the uniform layout:
all 43 layers have 160 global experts. The 40-local-experts shape applies only
to explicit TP4 expert parallelism (`--enable-expert-parallel`), including its
all-to-all collective. Plain MoE tensor parallelism is a different topology and
must not be described as 40 experts per rank. Do not apply the heterogeneous
patch to this artifact.

The later quality-controlled nested pack retains the original heterogeneous
contract:

Dummy model contract:

| Layers | Global experts | TP4 local experts |
| --- | ---: | ---: |
| 0-2 | 256 | 64 |
| 3-42 K160 | 160 | 40 |
| 3-42 K168 | 168 | 42 |
| 3-42 K176 | 176 | 44 |
| 3-42 K180 | 180 | 45 |

Assert per-layer router width, valid `tid2eid`, old-ID/new-ID maps, correction
metadata, rank ownership, native quantization selector, and no
Marlin/CUDA/BF16 fallback. Construct the 43-layer dummy TP4 model at context
256 and route synthetic tokens across every rank.

Smoke pass: the unchanged public K160 constructs with 160 global/40 EP-local
experts on every layer, all expert tensor sets are complete, each hash-layer
`tid2eid` tensor has the expected shape and range, selectors are native, the
EP collective succeeds, and synthetic forward passes. Exact semantic
equivalence of the uploader's remap to the unpruned source remains a later
official-source check.

Quality-pack pass: heterogeneous construction, mappings, selectors, and
synthetic forward all pass.

## Stage 3: Architecture Fixtures And Frozen Test Identity

Cover sparse MLA decode, FP8 cache insertion/readback, compressor, indexer,
inverse/scaled RoPE, hash routing, mHC pre/post/head, TP/EP collectives, logits,
and sampling in eager and graph modes.

Before running, commit an oracle/tolerance manifest. Default thresholds are:

- non-quantized BF16 paths: normalized RMSE at most 0.01 and cosine at least
  0.9999;
- FP8/cache paths: compare with explicit quantize/dequantize using normalized
  RMSE at most 0.02 and cosine at least 0.999;
- routing IDs, cache slots, token IDs, and tensor shapes: exact;
- graph/eager final token IDs: exact over at least 128 deterministic cases.

Also freeze `quality/suite-v1.json` before Stage 4. It must contain prompt
text/hashes, categories, scoring, generation settings, tokenizer revision, and
critical-case labels. Do not tune the suite after seeing K-candidate results.

Pass: fixtures meet the committed tolerances using only XPU-compatible paths.

## Stage 3.5: Ranking And Mapping Provenance

Before the source download, record one of:

1. a complete public old-ID ranking/map whose calibration prompts, scoring
   method, layer coverage, and hashes can be reproduced; or
2. `calibration-v1` with frozen prompt hashes/domain weights, REAP metric,
   tokenizer/source revision, seeds, runner revision, and a plan to compute one
   full ranking after the source is downloaded.

The calibration mix must cover code, tools, research/knowledge, math/science,
planning, and general QA. K160/K168/K176/K180 must be nested prefixes of one
ranking so calibration is performed once. Hash layers 0-2 remain unpruned.

Stop: no complete mapping provenance and no reproducible calibration plan.

## Stage 4: Download And Packing Authorization

Explicit execution exception: on 2026-07-13 the user authorized the frozen
public uniform-K160 snapshot while Stages 0-3.5 continue. This exception applies
only to `0xSero/DeepSeek-V4-Flash-180B` revision
`7c360e1cd4a5168099dbc54d16d929bf6df04990` as a smoke/performance candidate.
It does not authorize promotion, IQ3, or speculation. The official-source
download remains the teacher and final-pack gate.

Authorize the source download only after Stages 0-3.5 pass. Record:

- source revision `60d8d70770c6776ff598c94bb586a859a38244f1`;
- exact shard inventory and expected 148.648 GiB tensor payload;
- at least 800 GiB free in the archive workspace for source, retained K packs,
  temporary packing output, and later IQ3 control;
- a reviewed internal-NVMe decision. Prefer at least 140 GiB free for the hot
  pack and compile/runtime cache; otherwise explicitly accept slower external
  loading without presenting it as the intended fast iteration loop;
- content-addressed cache keys and temporary-output cleanup rules;
- chosen first pack format and K160 as the first full artifact.

Do not download the 144.905 GiB Intel AutoRound artifact for this lane.

After downloading the official source, capture primary teacher logits/results
for a fixed, tractable subset of `suite-v1` using the official weights before
pruning. This may be a slow streamed/offloaded correctness job; it is not a
performance result.

## Stage 5+: Full-Model Minimum Gates

Every K candidate requires:

- no CPU/SSD expert offload during measured decode;
- at least 3 GiB free per GPU after warm graph capture at 8K;
- deterministic p64/n16 canary pass and no control-character degeneration;
- backend trace for every quantized layer family;
- fixed quality gate against official-source teacher evidence and the IQ3
  secondary control;
- cold realistic suite with `cached_tokens=0`;
- exact model/manifest/runtime/kernel identity;
- a profile reconciling host, kernels, collectives, memory operations, and
  waits.

The IQ3 control download is authorized only after K160 runs correctly and the
four-B70 llama.cpp allocation path is either fixed or a reviewed slow control
method is available. If neither official teacher evidence nor IQ3 control can
be produced, the “smartest fitting variant” claim remains blocked.

## Stage 8: MTP Capacity Re-entry

Speculation requires a new memory decision. The base projections omit MTP.
Restoring a same-K MTP adds about 1.99-2.24 GiB across K160-K180; preserving
all 256 MTP experts adds 3.188 GiB. Re-measure warm free memory, and step down K
if necessary to retain the 3 GiB-per-rank reserve.

Do not add MTP, DFlash, EAGLE, or another speculator before correct
nonspeculative decode approaches 40-50 tok/s.
