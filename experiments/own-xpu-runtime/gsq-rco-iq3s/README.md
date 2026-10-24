# SC117 IQ3_S integration into our own engine

The requested model is downloaded and verified. Integration is in progress;
there is no new-model inference or speed result yet. The owner explicitly
requested the SC117 source and our custom engine with MTP. This is a distinct
modified target, separate from the closed and published Unsloth optimization.

## Model and source

[Model identity](model-identity.json) records both shards, full SHA256 readback,
revision `eec4e10a2c29b440a2ae85591fa11569ce752963` and local paths. The
83,863,586,496-byte download is on the EX400U USB disk. The old model was already
on that disk and remains intact. The RAID with recorded I/O errors is excluded.

[SC117's pinned release](https://huggingface.co/SC117/Qwen3.8-Flash-Next-GSQ-RCO-abliterated-GGUF/tree/eec4e10a2c29b440a2ae85591fa11569ce752963)
credits Qwen for the base model, ISTA-DASLab for GSQ/RCO quantization and
orcarouter for the abliterated tensors. SC117 describes transplanting 144
residual-projection tensors while retaining learned upstream scales. These
are publisher provenance claims, not payload-transplant validation by this
lab. The model card reports Apache-2.0. See the separate
[community intake](../../../community/field-reports/sc117/qwen38-gsq-rco-iq3s/README.md).

The inference engine remains our existing model-specific code. External
GGML declarations and dequantization equations are credited format references
and CPU comparison oracles, not an imported inference runtime.

## Integration evidence

| Gate | Evidence and limits |
| --- | --- |
| Download | Both full files pass SHA256 during transfer and readback. |
| Architecture | [Header census](metadata/README.md): all 1,224 names/shapes and architecture/tokenizer/PLE metadata match; 695 tensor storage types differ. Twelve CPU tests pass. |
| MTP control | [CPU bridge](mtp/README.md): 17 tests of inherited controller and metadata compatibility pass. Proposals and target recurrence are synthetic. |
| Weight arithmetic | [Decoder proof](formats/README.md): 6,780 cases and twelve real rows pass exact CPU comparisons; bounded native kernel equivalence is recorded separately below. |
| Full graph | CPU graph construction passes eight tests: 1,873 launches and 2,065 buffers preserve topology. Raw weights plus logical buffers use 25.84/29.07 GB across ranks, excluding expansion, scratch and draft costs; no fit claim. |
| Primitive coefficients | [Upload conversion](controls/README.md) passes exhaustive half/BF16 checks; actual graph needs only F16 PLE widening, adding 81,920 bytes. |
| Two-shard loader | [Authenticated loader](loader/README.md): ten parser tests and 24 immutable-authority checks pass; real headers are bound separately from payload checks. |
| Native kernels | [Packed backend](native-formats/README.md): 15 Host cases, 60 checks and 100 refusals pass. Five native kernels pass 15 synthetic GPU cases with 45 exact kernel executions. |
| Native inference | Complete engine overlay is being built and reviewed. The [tiny native qualification runner](native-qualification/README.md) passed; full-model inference remains pending. |
| Speed | Unmeasured for this model, both target-only and MTP. |

The model label does not describe every tensor. New support includes Q2_0,
Q4_K, Q5_K and IQ4_XS. Existing IQ3_XXS and F16 scalar support must also reach
the selected runtime paths. Expert gate/up mixes four formats, expert down
includes Q2_0, HC projections and many small projection matrices are now BF16, and PLE
convolution is F16. The old Q8/F32 HC fusion and IQ4_NL-only expert-down
specialization cannot be reused unchanged. The new target has two shards; the additive authenticated loader replaces the old three-shard assumption.

## MTP policy

Start from the existing P195 two-owner coordinator, which already implements
one-token MTP and target verification. The P196 one-card record and P201
streaming front are target-only. Adding a flag to that front is insufficient.

The existing official FP8/BF16 draft tensors are present on local NVMe and
match the historical manifest's file identities. No new draft payload hash
has been performed by this intake. The draft loader verifies tensor bytes at
load and performs its existing draft-only conversion. The SC117 Q8 GGUF head
is optional and is not a drop-in input to this loader; it was not downloaded.

First qualification uses the full 248,320-token draft head, with target-only
and MTP token/state comparisons. The old restricted-head calibration is not
transferred. Only target-verified tokens may be emitted. Neural acceptance,
rollback ordering and net speed remain to be measured on the new weights.

## Qualification and operating boundary

Initial planning uses context capacity 4,096 and full BF16 KV. The 262,144
context metadata is not a demonstrated capacity. Old model token outputs are
not an oracle for this modified model; compare against the same downloaded
weights and preserve exact run identity.

[Initial passive host observation](initial-host-state.json) found daily
applications still holding devices. The idle card0 text application was subsequently stopped once, gracefully, for the bounded native kernel test. The other text and vision applications remain unchanged. No full-model owner, power/memory change or restart was performed for this lane. CPU
helpers use bounded memory, helper cores and low priority. Model payloads,
binaries and temporary row samples stay outside tracked artifacts. Existing
frozen runtime packets and failed attempts remain unchanged.

The additive loading/dispatch changes described in the [source audit](native-integration-audit.md) are under integration review. The frozen preparation receipts pass an [independent source/artifact rehash](native-preparation-review.json). The tiny native kernel qualification now passes. Full Engine build precedes target-only output, then MTP equality against that same target before measuring any speed benefit.
