# SC117 IQ3_S integration into our own engine

**Precision correction in progress.** A [compiled-source and allocation audit](reference-cpu/RECURRENT-DTYPE.md)
confirms that this engine rounds GDN recurrent matrix state toBF16 each token,
while the compatible reference retainsF32. The earlier exactness and speed
results compare paths within that BF16-state contract. They do not establish
no added quality loss relative to the reference. Further speed changes are held
while recurrent storage is corrected and an independent same-weight CPU path
is prepared. BF16 attention KV remains separate from this recurrent-state issue.

The requested model is downloaded and verified. Our engine now passes exact target-only/MTP comparison on all twelve fixed short prompts. The independently audited [resident baseline](baseline/RESULT.md) measures 12.63 tokens/s target-only and 17.98 with MTP, with full target state preserved. This is a short-prompt baseline, not broad quality certification. The owner explicitly
requested the SC117 source and our custom engine with MTP. This is a distinct
modified target, separate from the closed and published Unsloth optimization.

The [exact expert-block engine](expert-iq3xxs-block/engine/operating/RESULT.md) now
passes all24 baseline arms and independent54-bundle readback, measuring15.73 target-only
/23.30 MTP tokens/s. Both ranks and safe closure are verified. This remains an internal
cap128 resident screen; publication quality/context gaps are explicitly retained.

The [116-site dense decoder](dense-packed-block/engine/operating/launch-b/RESULT.md)
now passes all24 original arms and54 bundles, measuring19.61 /28.14 tokens/s
with unchanged memory and acceptance. It is the current short-screen engine;
[expanded task readback](quality-expanded/RESULT.md) also passes exact prefixes
and all12 full target/MTP pairs on this binary. Eleven answers are capped and
incomplete; one reaches EOS. Technical/unsupported-claim cautions remain, and
broad task quality is not qualified.

The [19-site Q6 extension](dense-q6-p33/operating/RESULT.md) also passes all24
original arms and54 bundles, measuring16.17 /23.44 with188.7MB extra device memory.
The small MTP difference is descriptive, not a causal or public speed claim.
The broader coverage below remains bound to the preceding973489 binary.

The [broader coverage screen](coverage/RESULT.md) also passes exact target/MTP
comparison through512 outputs and a2084-token input. All six requested document
facts are correct; two capped outputs remain incomplete. Independent14-bundle
readback and safe closure pass. This is limited coverage, not broad certification.

The combined attention/Q6 candidate now matches all twelve original prompt pairs,
measuring14.85 target-only /22.13 MTP tokens/s in its separately audited resident run
([full result and scope](qkv-q6-p33/engine/operating/RESULT.md)). This is a cap128
internal screen, with no matched cross-binary causal or public record claim.

The attention projection candidate now matches baseline on all twelve prompt pairs
([separate-session correctness completion](attention-q8-p33/completion/RESULT.md)).
Its [same-owner kernel comparison](attention-q8-p33/micro/RESULT.md) reduces measured
isolated event latency with exact bytes; no full-model speed improvement is claimed.
The Q6 combination has now passed the full gate linked above.
[Lossless evidence bundling](state-bundle/RESULT.md) also passes exact full-state
qualification. The [current expert candidate](expert-iq3xxs-block/STATUS.md) follows measured
class and format attribution. Its CPU proof, incomplete micro qualification and completed full-engine result are retained.

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
| Native inference | The [complete native build](integration/README.md) passes. The [tiny native qualification runner](native-qualification/README.md) passed; the [first real-model comparison](serving/evidence/real-model-a/README.md) passes with 25 accepted and six rejected proposals. |
| Speed | [Resident twelve-prompt baseline](baseline/RESULT.md): 12.63 target-only / 17.98 MTP tokens/s; exact paired tokens/state, both order groups retained. |

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
match the historical manifest's file identities. The real-model loader verified all 3,101 draft tensor payload hashes and performs its existing draft-only conversion. The SC117 Q8 GGUF head
is optional and is not a drop-in input to this loader; it was not downloaded.

First qualification uses the full 248,320-token draft head, with target-only
and MTP token/state comparisons. The old restricted-head calibration is not
transferred. Only target-verified tokens may be emitted. The resident baseline verifies 1,160 accepted and 364 rejected proposals with exact target state; delivered decode speed improves on both order groups.

## Qualification and operating boundary

Initial planning uses context capacity 4,096 and full BF16 KV. The 262,144
context metadata is not a demonstrated capacity. Old model token outputs are
not an oracle for this modified model; compare against the same downloaded
weights and preserve exact run identity.

[Initial passive host observation](initial-host-state.json) found daily
applications still holding devices. The idle card0 text application was subsequently stopped once, gracefully, for the bounded native kernel test. The second idle text application was then stopped once for the planned two-card model comparison. The vision application remains unchanged. A real two-owner model comparison subsequently completed with both owners safely closed, target cards empty and the exact fault baseline unchanged. No power/memory change, reboot or automatic restart was performed. CPU
helpers use bounded memory, helper cores and low priority. Model payloads,
binaries and temporary row samples stay outside tracked artifacts. Existing
frozen runtime packets and failed attempts remain unchanged.

The additive loading/dispatch changes described in the [source audit](native-integration-audit.md) pass native integration and real-model execution. The frozen preparation receipts pass an [independent source/artifact rehash](native-preparation-review.json); subsequent full-engine and target/MTP results are linked above.

The owner requested [continuous lossless acceleration work](WORK-PLAN.md) after correctness, with a dedicated progress and fairness reviewer every 30 minutes. The complete [same-pair Host lifecycle](serving/HOST-RESULT.md) passes; it remains synthetic evidence.

The first real-model output is coherent but capped at 32 tokens. The independent review rehashed all retained target-state files and verified exact target/MTP equality, the full-vocabulary draft head and safe ownership closure. It does not establish general task quality, cross-process determinism or a speed improvement.
