# Qwen3.8 27B AutoRound INT4 on 2x Intel Arc Pro B70 — lane setup

> **Certification: `research-status`.** Active or unresolved work, not a
> promoted reproduction; see its entry in
> [`repro/guide-catalog.json`](../guide-catalog.json).

## Fixed-K batch-invariant profile on the R187 stack (2026-09-05, research-status)

The 2026-09-04/05 refresh runs the same AutoRound tensors on the FP8 lane's R187 stack (whole-graph compile,
deterministic Inductor, no autotune, r152 harness) with two kernel-level changes and three runtime switches. Every
number below is class-balanced median decode at concurrency 1 unless a ladder is named; the two-run identity rule and
the MTP-vs-MTP0 oracle gate are the FP8 lane's.

**What changed and why**

1. *Kernel routing.* vLLM routes `quant_method: auto-round` to INC/ARK `woqgemm`, which is nondeterministic for 32-256
   rows, never batch-shape invariant (so speculative decoding can never be lossless on it) and 6-10x slower at two rows
   than one. The identical tensors relabelled as plain `gptq` select `XPUwNa16LinearKernel -> _xpu_C.int4_gemm_w4a16`
   (oneDNN). Builder: [`scripts/make-gptq-relabel.py`](scripts/make-gptq-relabel.py) (hard links plus rewritten
   `config.json`/`quantization_config.json`; the `mtp.fc` exclusion is spelled `mt[p]\.fc` so vLLM keeps the INT4 draft
   layers quantized); manifest [`manifests/model-gptq-relabel-r212.json`](manifests/model-gptq-relabel-r212.json).
2. *Fixed-K W4A16 GEMM.* The oneDNN catalog splits K 8-way for 1-8 token rows, 2-way to 128 and not at all above, so a
   request's rows get different bits depending on batch composition. The R221 kernel library pins a two-tier strategy
   (the natural 1-8-row entry for n <= 8, the 9-24 tile with the same 8-way K split above; bitwise equal on all 14 TP1/TP2
   shapes for n = 1..1024): decode unchanged, prefill GEMMs about 2x. Patches
   `experiments/qwen38-27b-b70/patches/onednn-qwen38-w4a16-{strategy-override-dump-r220,fixed-k-two-tier-r221}-20260905.patch`,
   build `experiments/qwen38-27b-b70/docker/{build-w4a16-strategy-r220-image.sh,rebuild-w4a16-incremental-r221.sh}`
   (the R139 flow: vllm-xpu-kernels 1e90ffa6 + r35 + r50, oneDNN 0e2a5bfe + r137a + r137b). `QWEN38_W4A16_FIXED_K=0`
   restores the catalog.
3. *FP16 linears in 32-row pieces* (R224, `docker/r224-fp16-linear-rowchunk.py`, `VLLM_XPU_FP16_LINEAR_ROWCHUNK`): the
   oneDNN f16 GEMM behind `lm_head` and `mtp.fc` keeps the single-row class only to 32 rows.
4. *Runtime switches:* `VLLM_BATCH_INVARIANT=1` (single-split flash-decoding) and Inductor `"split_reductions": false`
   in `inductor_compile_config` (size-independent reduction order for the compiled RMSNorm and other reductions);
   `VLLM_XPU_GDN_SPEC_GROUP` / `VLLM_XPU_GDN_PREFILL_GROUP` (R228/R236) group the GDN launches.

Images: `neural-download/vllm-openai-xpu:qwen38-int4-w4a16-fixed-k-r221` (699e2699, `_xpu_C` 271db0d4) ->
`...:qwen38-int4-fp16-rowchunk-r224` (a23ff249) -> `...:qwen38-int4-gdn-spec-group-r228` (aaf920b0, `_xpu_ops.py`
c91d6b0d) -> `...:qwen38-int4-gdn-prefill-group-r236` (9488db61, `_xpu_ops.py` 015b4dce). Launch through the FP8 lane's
launchers with `MODEL_DIR=<relabel dir> MODEL_MANIFEST=<relabel manifest> QUANTIZATION=gptq VLLM_XPU_FP8_BLOCK_W8A16=0
VLLM_XPU_DRAFT_LM_HEAD_INT4=0 VLLM_XPU_W4A16_DETERMINISM_PAD=0 XPU_EXTENSION_SHA256_OVERRIDE=<_xpu_C sha256>
XPU_OPS_SHA256_OVERRIDE=<_xpu_ops.py sha256>` (see the R222-R239 wrappers under `experiments/qwen38-27b-b70/scripts/`).

**Single-request results, TP2 (R222/R227, R224 + batch-invariant):** MTP0 36.00 / 34.92 tok/s; MTP depth 1
50.83 / 51.12; depth 4 68.62 / 68.23; G1 (MTP0 pair), G2 (MTP pair) and G3 (each MTP server vs the MTP0 oracle) 12/12 at
every depth measured; G5 probe identical at 224/250/300 prompt tokens. Old ARK routing on the same stack: 32.8 tok/s and
no lossless speculation possible.

**Concurrency identity (c1-c64 ladder, 128 tokens per request, TP2):**

| configuration | MTP0 | MTP depth 4 |
|---|---|---|
| ARK routing (R216) | exact to c2 | exact to c2 |
| fixed-K kernel (R222) | exact to c32, c64 63/64 | c4 3/4, c8-c32 exact, c64 59/64 |
| + FP16 32-row pieces (R225) | c32 31/32, c64 64/64 | c8 7/8, c32 31/32, c64 60/64 |
| + `VLLM_BATCH_INVARIANT=1` (R226) | **exact c1-c64** | exact c1-c16, c32 30/32, c64 59/64 |
| + Inductor `split_reductions=false` (R232) | exact c1-c64 | exact c1-c16, c32 31/32, c64 63/64 |

The remaining c32/c64 flips are a handful of near-tie prompts whose result depends on how the ladder's arrival timing
mixes prefills into the first steps (the MTP0 ladder with an unchanged configuration is all-exact in one run and one miss
at c32 or c64 in others). Every INT4 GEMM, FP16 linear and the attention decode are batch-invariant; the residual sits in
the GDN kernel's dependence on launch composition (grouping its launches, R229-R238, does not reproduce the
single-request arithmetic). Notes: `experiments/qwen38-27b-b70/notes/2026-09-05-qwen38-int4-{w4a16-fixed-k-two-tier-r220-r221,concurrency-identity-r222-r226}.md`;
data `experiments/qwen38-27b-b70/data/2026-09-05-qwen38-int4-*`.

**Matrix R239, TP2 (2026-09-05, final configuration: R228 image + `VLLM_BATCH_INVARIANT=1` + `split_reductions=false`,
data `experiments/qwen38-27b-b70/data/2026-09-05-qwen38-int4-r239-matrix-result.json`):**

| depth | strict pair (tok/s) | gates | identity ladder c1 / c2 / c4 / c8 / c16 / c32 / c64 (aggregate tok/s at c16) |
|---|---|---|---|
| 0 (MTP0) | 34.21 / 35.64 | G1 12/12 | exact at every level in 3 of 4 ladders (c64 998.6 tok/s); one run c32 31/32, c64 63/64 |
| 1 | 51.10 / 50.09 | G2, G3 x2 12/12, probe exact | exact to c16 (650.1), c32 30/32, c64 58/64 |
| 2 | 61.14 / 61.54 | G2, G3 x2 12/12 | exact to c16 (522.3), c32 30/32, c64 60/64 |
| 3 | 67.61 / 67.83 | G2, G3 x2 12/12 | exact to c16 (599.4), c32 30/32, c64 59/64 |
| 4 | 68.55 / 67.79 (R240 re-run; first pass 68.22 / candidate b died at engine start) | G2, G3 x2 12/12 | c8 7/8, c16 exact (516.1), c32 30/32, c64 59/64 |

Depth 4 in R222/R227 on the same tensors and kernel: 68.62 / 68.23 with all gates 12/12. Aggregate ladder rates are
identity-qualified only where the level is exact.

**Matrix R239, TP1 (one card, `TENSOR_PARALLEL_SIZE=1 XPU_DEVICE_MASK=0 GPU_MEMORY_UTILIZATION=0.96`, same
configuration):**

| depth | strict pair (tok/s) | gates | identity ladder c1 / c2 / c4 / c8 / c16 / c32 / c64 (aggregate tok/s at c8) |
|---|---|---|---|
| 0 (MTP0) | 32.96 / 32.95 | G1 12/12 | exact at every level in 3 of 4 ladders (c64 447.6 tok/s); one run c64 63/64 |
| 1 | 49.64 / 49.47 | G2, G3 x2 12/12, probe exact | exact to c8 (261.6), c16 15/16, c32 30/32, c64 60/64 |
| 2 | 56.51 / 56.45 | G2, G3 x2 12/12 | exact to c8 (283.6), c16 15/16, c32 29/32, c64 62/64 |
| 3 | 58.47 / 58.47 | G2, G3 x2 12/12 | exact to c16 (270.3 at c8), c32 31/32, c64 61/64 |
| 4 | 56.29 / 56.25 | G2, G3 x2 12/12 | exact to c8 (216.3), c16 15/16, c32 31/32, c64 61/64 |

On one card the speculative turnover is at depth 3 (58.5 tok/s); on two cards depth 4 still gains (68.2). Single-card
MTP0 is within 5% of TP2 (33.0 vs 34.2-35.6), consistent with the launch-overhead-bound profile: the second card adds
almost nothing at one request and doubles aggregate throughput at concurrency. The single-card residual has the same
shape as TP2 without any collective, so the oneCCL all-reduce is excluded as a source.


New optimization lane, opened 2026-08-18, superseding the Qwen3.6 27B INT4
speculative lane. The two checkpoints have the same tensor architecture, so the
pinned Qwen3.6 source stack is mechanically compatible. New weights still
require independent numerical, quality, determinism, and performance gates.

> **Status correction, 2026-08-20:** this lane has no promoted record. The
> published `101.922` MTP5 and `100.497` MTP4 rows used an output-changing
> greedy margin and a baseline with the same setting; withdrawal is
> recommended. The honest margin-free working anchor is `101.170 tok/s`
> all-25, but its three arms agree on only 21–22/25 prompts. A fresh
> margin-free target-only oracle now exists, yet target A/B agreed on 24/25
> and a sealed-cache TP1 MTP5 pair agreed on only 2/4 diagnostic prompts. A
> later preregistered six-arm control produced two structured variants with
> the oneDNN INT4 prefill pad off and one shared variant in three pad-on arms.
> That passes the diagnostic criterion but does not establish lane-wide or
> full-25 TP2 determinism. Pad-on TP2 subsequently remained nondeterministic,
> including a recurring 512-zero final stream. A target/verifier post-forward
> sync arm observed a third endpoint family that still split at generated
> token 469; one treated arm cannot distinguish a sync effect from the lane's
> existing run-to-run variability. It is a negative boundary diagnostic, not a
> fix. A bounded prompt-24 replay-microscope arm then produced no trace because
> its anchored public request ID omitted vLLM's worker-side eight-hex suffix;
> prompt 6 also ended at 68 tokens, invalidating the strict metric window. That
> arm is an invalid false-null, not localization or speed evidence, and must not
> be retried. A later sealed graph-replay-bypass R1/R2 pair matched on 25/25
> token arrays, but its combined treatment also changed drafter geometry and
> startup allocation history; both arms remained only 18/25 exact versus target
> A and the pair central value was 56.363 tok/s. This is bounded diagnostic
> evidence, not a localized fix or performance candidate. Do not use the
> historical command below for a new promotion run. A later target-only split
> retained drafter PIECEWISE/M6 and both startup captures while bypassing only
> request-selected uniform target/verifier replay. Its two sealed arms matched
> only 24/25, splitting at prompt 24 token 469 between two sane historical
> families, and averaged only 60.938 tok/s preferred. That treatment is also
> terminal and insufficient; no retry or T3 is authorized.

## Model

`devan-carlin/Qwen3.8-27B-int4-AutoRound`, base `Qwen/Qwen3.8-27B`, Apache-2.0.
Local copy: `/mnt/usb-models/llm-models/qwen3.8-27b-int4-autoround-devan`
(19.02 GB, 8 safetensors shards + 11 small files, all verified).

Content manifest: [`manifests/model.json`](manifests/model.json). The upstream
revision is pinned at
[`bce40cacab0a4535b92fb3d57615c2bea9adf3d1`](https://huggingface.co/devan-carlin/Qwen3.8-27B-int4-AutoRound/tree/bce40cacab0a4535b92fb3d57615c2bea9adf3d1).
An independent download at
`/mnt/fast-ai/llm-models/qwen3.8-27b-int4-autoround` matched all recorded
file identities and the exact `19,016,930,167`-byte payload.

## Why the existing stack transfers

| Property | Qwen3.6 (old lane) | Qwen3.8 (this lane) |
| --- | --- | --- |
| architecture class | `Qwen3_5ForConditionalGeneration` | same |
| text `model_type` | `qwen3_5_text` | same |
| layers / hidden | 64 / 5120 | same |
| **vocab size** | 248320 | **same** |
| attention heads / KV heads | 24 / 4 | same |
| linear key / value heads | 16 / 48 | same |
| `full_attention_interval` | 4 | same |
| `mtp_num_hidden_layers` | 1 | same |
| `quant_method` | `auto-round` | same |
| bits / group size / packing | 4 / 128 / `auto_round:auto_gptq` | same |

Consequences:

- vLLM routes `auto-round` to `INCConfig`
  (`vllm/model_executor/layers/quantization/__init__.py:164`), so the whole INT4
  W4A16 path applies: `int4_gemm_w4a16`, the oneDNN completion barriers and
  input-dependency controls, and the INT8 LM head.
- `Qwen3_5ForConditionalGeneration` and `Qwen3_5MTP` are both registered
  (`registry.py:564`, `:634`), and the checkpoint ships **29 MTP tensors**
  (`mtp.fc.weight`, `mtp.layers.0.*`, `mtp.norm.weight`), so MTP speculative
  decoding is available.
- The vocabulary is byte-for-byte the same size, so the masked-max greedy
  sampler fix carries its full benefit.
- The upstream README warns that mixed symmetric/asymmetric INT4 checkpoints
  need devan-carlin's empty/shape-compatible qzeros guard on the newer XPU/ARK
  path ([vLLM PR #52428](https://github.com/vllm-project/vllm/pull/52428)).
  The pinned older vLLM tree has only a present/non-null check at
  `inc.py:822-825`, not that newer guard. This exact checkpoint nevertheless
  loaded successfully in the recorded baseline. Do not generalize that success
  to a different AutoRound export or claim PR #52428 is already present.

## Reference point

The model author measured **47.8 tok/s** on 4x B70 at TP=4, no speculation,
`max_tokens=16384` (versus 30.2 for BF16). That is not comparable to this lane's
TP=2 + MTP3 configuration, and it is far below what the identical Qwen3.6
architecture reaches here (~95 tok/s), so it should be treated as a floor, not a
target.

## Running an arm

Run the read-only [`scripts/preflight.sh`](scripts/preflight.sh) first. It
checks the pinned sources, Python package family, retained graph-safe
FlashAttention and oneCCL identities, complete model manifest, host memory, and
two-card inventory without importing torch or opening a GPU. The outstanding
reference-host portability and low-RAM evidence is tracked in
[`REFERENCE-HOST-HANDOFF.md`](REFERENCE-HOST-HANDOFF.md).

The Qwen3.6 harness is reused directly. Two environment variables retarget it:

```bash
MODEL_DIR=/mnt/usb-models/llm-models/qwen3.8-27b-int4-autoround-devan \
VALIDATION_MODEL_MANIFEST=$repo/repro/qwen38-27b-autoround-int4-b70/manifests/model.json \
VALIDATION_EXPECT_XPU_COUNT=2 \
VALIDATION_EXPECT_VLLM_VERSION=0.21.1rc1.dev289+g44fc8fde0 \
VALIDATION_HF_HOME=/mnt/fast-ai/llm-cache/hf \
VALIDATION_XPU_RUNTIME_MANIFEST=/path/to/xpu-runtime.sha256 \
VALIDATION_ONECCL_MANIFEST=/path/to/oneccl-runtime.sha256 \
VALIDATION_GRAPH_STAGE_MANIFEST=/path/to/graph-stage.sha256 \
  ...run-arm.sh spec-native-partition-exact-native 0,1 "$root" "$baseline"
```

`VALIDATION_MODEL_MANIFEST` was added for this lane and defaults to the Qwen3.6
manifest, so every existing Qwen3.6 arm is unaffected. The device-count
override keeps the recorded four-B70 default fail-closed while permitting this
explicitly identified two-B70 host; the runner still requires the requested
TP2 pair and logs the expected count in the run identity.
The version override is the metadata emitted by a fresh editable build of
source `44fc8fde09` on 2026-08-18. The historical environment retained an older
distribution label even after its editable source moved to that commit; source
head and diff remain the authoritative code identity in either case.
This two-card host's pinned low-memory XPU rebuild, package manifest, peak-RSS
warning, and import-path check are recorded in
[`RUNTIME-BUILD-20260818.md`](RUNTIME-BUILD-20260818.md).
The matching public oneCCL build, checksum manifest, and passing two-rank graph
oracles are recorded in
[`ONECCL-BUILD-20260818.md`](ONECCL-BUILD-20260818.md).
The matching model-specific graph-safe attention stage passed 12,000 replay
oracles across both B70s. Its complete loadable-package manifest is
[`manifests/graph-stage-qwen38-head256-oneapi2025.3.3-20260818.sha256`](manifests/graph-stage-qwen38-head256-oneapi2025.3.3-20260818.sha256),
and the replay summary is
[`evidence/graph-stage-oracles-20260818.json`](evidence/graph-stage-oracles-20260818.json).

The three optional runtime manifests make a rebuilt host identity explicit
without weakening the retained reference-host defaults. Entries are
`SHA256 relative/path` pairs rooted at, respectively,
`BASE_STAGE/vllm_xpu_kernels`, `ONECCL_INSTALL_DIR`, and `STAGE`. Absolute or
parent-traversing paths, missing files, malformed hashes, and empty manifests
all fail closed. Omit these variables only when reproducing the historical
binary hashes embedded in the validator.
`VALIDATION_HF_HOME` prevents the historical `/mnt/usb-models` cache path from
being recreated on hosts that keep their model and transient Hugging Face
metadata elsewhere; it does not change model identity verification.
The runner also places the verified `BASE_STAGE` first on `PYTHONPATH`; this is
required to keep a rebuilt `_xpu_C` paired with its matching device libraries
instead of silently importing `_xpu_C` from an installed wheel.

The known-good deterministic configuration and its flag set are documented in
[`../qwen36-27b-autoround-int4-b70-determinism-20260818/README.md`](../qwen36-27b-autoround-int4-b70-determinism-20260818/README.md)
section 7a; start from that rather than re-deriving it.

The 2026-08-18 transition pull was independently audited on the two-card,
15 GiB host. Its Qwen3.6 closeout bundle and flat patch are complete and
reconstruct the recorded vLLM tree, while the Qwen3.8 runtime and raw-evidence
handoff remains incomplete. See the
[transition audit](../../experiments/qwen38-27b-b70/notes/2026-08-18-autoround-int4-transition-handoff-audit.md).

## Open items

- A valid fresh margin-free target-only quality oracle now exists at
  `qwen38-marginfree-targetoracle-25-a-20260820`. Its A/B throughput was
  `49.759` / `50.016 tok/s`, but the pair agreed on only 24/25 prompts: long
  rollover diverged at token 469. Use A for the semantic baseline while
  retaining that target-only determinism caveat.
- The vision tower (333 tensors) is unused for text benchmarking; the config
  carries `language_model_only`.
- The current margin-free MTP5 anchor is `101.170 tok/s` all-25 and `92.851`
  selection-12, the median of three arms. Pairwise token parity is 21/25,
  21/25, and 22/25, so it is a research baseline rather than a result.
- Post-recovery dual-view-verified MTP5 arms reached `102.132` and
  `102.176 tok/s`, but agreed on 21/25 and each matched target oracle A on only
  15/25. A byte-identical sealed-cache TP1 pair agreed on only 2/4. This proves
  runtime nondeterminism without TP2 collectives. A preregistered six-arm TP1
  control then produced structured variants `G/F2/G` with the global oneDNN
  INT4 prefill pad off and `G/G/G` with it on, under the same binary and sealed
  cache. The follow-up pad-on composite TP2 full-25 pair passed the new
  fail-closed engagement/direct-load/cache/freshness/quality gates but agreed
  on only 22/25 token arrays. A2's long-rollover response was all-zero from the
  first token, while B2 was sane. The exact C1 recurrence arm repeated A2's
  512-zero stream and formed third SQL/factual output families under the same
  sealed identity. Its preferred median was `101.059 tok/s`; all three arms are
  nonpromotable. A sealed graph-replay-bypass R1/R2 pair subsequently matched
  all 25 arrays and emitted the sane S1/target-A prompt-24 family, but only
  under a combined target-verifier replay, drafter graph/geometry, and startup
  allocation treatment. Both arms were 18/25 exact versus target A and their
  preferred central value was `56.363 tok/s`, 44.263% below B2. Preserve the
  pair as bounded diagnostic evidence, run no further arm under its
  preregistration, and do not promote it. The draft-fallback-margin path is
  also closed: its real 598-call TP2 qualification exceeded the required error
  bound on every call and left 9 repaired argmax mismatches versus full FP16.
  Do not retry it or run a full-25 throughput A/B; see the
  [terminal result](../../experiments/qwen38-27b-b70/notes/2026-08-20-draft-margin-tp2-qualification-result.md).
- Do not use stock `intel/llm-scaler-vllm:0.21.0-b3.1` as a substitute for the
  pinned source stack on a 16 GB host. An independent eager TP2 smoke first hit
  its FP8-only GDN output-projection probe on an INT4 `qweight`; disabling that
  optional probe allowed all weights to load, but a 9 GiB cgroup then killed a
  worker during warmup and triggered one BCS reset. See the
  [safety note](../../experiments/qwen38-27b-b70/notes/2026-08-18-autoround-int4-stock-image-lowram-unsafe.md).

## Invalidated historical measurement — 101.922 tok/s, MTP5 (2026-08-18)

LocalMaxxing `cmszbkxco0e11ms01l2rixxbt`; withdrawal recommended. Median of three cold arms
(`100.896` / `102.042` / `101.922`) on the 25-prompt suite; all three pairwise
comparisons were 25/25 only because a `0.03125` greedy margin masked runtime
flips and changed output on 18/25 prompts. Its quality baseline used the same
margin, so the quality pass is invalid. **Selection-12 was `95.167`** — lower than the MTP4 row's `96.627`,
because depth helps the newer holdout prompts and hurts the historical ones.

Identical to the MTP4 command below except:

```bash
VALIDATION_NUM_SPECULATIVE_TOKENS=5 \
VALIDATION_COMPILATION_CONFIG_OVERRIDE='{"use_inductor_graph_partition":true,"pass_config":{"fuse_rope_kvcache_cat_mla":false},"cudagraph_mode":"PIECEWISE","cudagraph_capture_sizes":[6],"max_cudagraph_capture_size":6}' \
```

The historical depth sweep measured MTP3 `96.616`, MTP4 `100.497`, MTP5
`101.922`, and MTP6 `99.464`, all under the invalid margin-assisted identity.
It does not establish a valid optimum for the margin-free lane.

### What a third party cannot reproduce exactly

Two things are honestly out of reach without host access:

1. **The staged graph-safe FlashAttention binaries.** These are a 3.1 GB AOT
   SYCL package that is not published and cannot be rebuilt bit-identically
   across toolchains. Build your own from
   `experiments/qwen27_graphsafe_flash_attention/` (`build.sh` plus the four
   patches) and run with:

   ```bash
   VALIDATION_ALLOW_UNPINNED_BINARIES=1 ...run-arm.sh ...
   ```

   That downgrades every binary-hash mismatch to a loud warning and writes the
   actual hashes to `binary-identity.txt` in the arm root, so your run stays
   auditable against what was really loaded. **It relaxes no correctness gate** —
   freshness, cache-zero, determinism and quality all still apply. Runs made
   this way are reproductions, not record-identity runs, and should not be used
   to promote a submission.
2. **The torch.compile cache.** The historical margin-on artifact was evaluated
   against a pinned compile cache, but that does not establish determinism for
   the current margin-free lane. Even three arms sharing one cache agreed on
   only 21/25, 21/25, and 22/25 prompts. The later TP1 F2/G pair began and
   ended on a byte-identical cache tree but still agreed on only 2/4 prompts,
   so exact token repeatability is a confirmed runtime problem rather than an
   untested cache hypothesis.

Everything else — model manifest, both source trees on the public forks and
the harness — is published. The historical quality baseline is published for
audit only and is not a valid margin-free oracle.

## Invalidated historical measurement — 100.497 tok/s (2026-08-18)

This three-arm MTP4 measurement is invalid for the same reason as MTP5: the
greedy margin changed emitted tokens and the quality baseline shared it. The
historical numbers remain below for audit, not promotion. Full original analysis:
[`../../notes/2026-08-18-qwen38-int4-100tps-uninitialized-gdn-scratch.md`](../../notes/2026-08-18-qwen38-int4-100tps-uninitialized-gdn-scratch.md).

| Arm | all-25 | selection-12 |
| --- | ---: | ---: |
| A | `101.653` | `96.499` |
| B | `100.497` | `96.627` |
| C | `99.905` | `96.895` |
| **median** | **`100.497`** | **`96.627`** |

Carry these caveats with the number: arm C is below 100 so the arms are not
unanimously over the line, the median is; **selection-12 at `96.627` has not
crossed 100**, and that is the subset any record comparison rests on; and this
is the pinned-compile-cache gate, with a fresh-compile arm still outstanding.

### Historical command identity — do not use for a new measurement

This command intentionally preserves the invalid margin-assisted identity so
the old artifact can be audited. It must not be copied into a new run. A new
run requires margin `0`, persistent scratch `1`, and a fresh target-only
quality oracle; those gates are not yet represented by a promoted command.

```bash
repo=$(git -C . rev-parse --show-toplevel)
LABEL=qwen38-mtp4-noscratch-repro-a
root=${BENCH_ROOT:-/mnt/usb-models/bench-results/qwen38-27b-autoround-int4-b70}/$LABEL
cache=${CACHE_ROOT:-/mnt/usb-models/llm-runtime/vllm-cache}/qwen38-mtp4-noscratch
qbase="$repo/data/qwen38-27b-autoround-int4-b70-baselines/quality-qwen38-int4-mtp3-fast-20260818.json"

VALIDATION_GDN_SPEC_PERSISTENT_SCRATCH=0 \
MODEL_DIR=/mnt/usb-models/llm-models/qwen3.8-27b-int4-autoround-devan \
VALIDATION_MODEL_MANIFEST="$repo/repro/qwen38-27b-autoround-int4-b70/manifests/model.json" \
VALIDATION_VLLM_CACHE_ROOT="$cache" \
VALIDATION_RUN_SMOKE=1 VALIDATION_RUN_BENCH=1 VALIDATION_RUN_QUALITY=1 \
VALIDATION_BENCH_MAX_TOKENS=512 VALIDATION_BENCH_METRIC_TOKENS=100 \
VALIDATION_NUM_SPECULATIVE_TOKENS=4 \
VALIDATION_COMPILATION_CONFIG_OVERRIDE='{"use_inductor_graph_partition":true,"pass_config":{"fuse_rope_kvcache_cat_mla":false},"cudagraph_mode":"PIECEWISE","cudagraph_capture_sizes":[5],"max_cudagraph_capture_size":5}' \
VALIDATION_ENABLE_XPU_GRAPH=1 \
VALIDATION_GDN_NATIVE_SPEC_RECURRENT_SERIAL_EXACT=0 \
VALIDATION_GDN_CAPTURE_NATIVE_SPEC=1 VALIDATION_GDN_NATIVE_SPEC_COMPLETION_BARRIER=0 \
VALIDATION_ONEDNN_INT4_COMPLETION_BARRIER=1 VALIDATION_ONEDNN_INT4_INPUT_DEPENDENCY=1 \
VALIDATION_ONEDNN_INT4_INPUT_DEPENDENCY_SCOPE=all_target \
VALIDATION_ONEDNN_INT8_COMPLETION_BARRIER=1 VALIDATION_ONEDNN_INT8_INPUT_DEPENDENCY=1 \
VALIDATION_LM_HEAD_INT8=1 VALIDATION_DETERMINISTIC_GREEDY_MARGIN=0.03125 \
VALIDATION_VLLM_EXTRA_ARGS='--dtype float16' \
LABEL=$LABEL \
"$repo/experiments/qwen36-27b-autoround-int4-b70/validation-20260815/run-arm.sh" \
spec-native-partition-exact-native 0,1 "$root" "$qbase"
```

Historically, all three arms shared one `VALIDATION_VLLM_CACHE_ROOT`. Fresh
compilations produce different-but-internally-deterministic code, so a
fresh-cache rerun will not reproduce token-for-token. The compile cache is part
of the run identity.

The published command's `VALIDATION_GDN_SPEC_PERSISTENT_SCRATCH=0` attribution
was also wrong: the old harness scrubbed that value and hard-exported `1`, as
proved by 96 scratch-allocation messages in each record arm. The harness now
propagates the validation variable and records the effective flag.
