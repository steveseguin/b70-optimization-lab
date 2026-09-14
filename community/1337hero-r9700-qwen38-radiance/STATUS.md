# AMD Qwen3.8 MXFP4 / Radiance / DFlash2 review

- Evidence level: **community-reported**.
- Patch review: bounded static inspection of the relevant source, not a full runtime audit.
- Contributor: LocalMaxxing **1337Hero**, identified by the user as Mike Key / @1337hero. The social post URL was not supplied.
- Contribution: useful dual-R9700 benchmark and implementation lead. Acknowledged; no validated B70 boost or integration.
- Source: [reported run](https://www.localmaxxing.com/en/models/amd/Qwen3.8-27B-Quark-AWQ-MXFP4?run=cmtx76rb70aj0ps014d8a37v9).
- Model/runtime: AMD Quark AWQ MXFP4, FP8 KV, TP2, DFlash2 K7; reported Radiance 1.0.16. See [identity and arithmetic](validation/review-metadata.json).
- Initial review executed metadata retrieval, source reading and arithmetic only. A subsequent [local FP8 transfer study](../../experiments/qwen38-27b-b70/notes/2026-09-14-amd-transfer-results.md) measured controls and an exact-but-neutral dispatch prototype. The combined newer-runtime/V2/DFlash2 startup froze the host before readiness; no DFlash inference result exists. The user rebooted and the original service was restored. The AMD result remains community-reported.
- Quality: the run lacks output evidence; the pinned runtime documentation says strict speculative/non-spec equivalence has not passed.
- Recognition: report acknowledged; core runtime/kernels credited to StillDeadcode, MXFP4 work to Brian/ggz14, integration to magiccodingman, draft algorithm to DFlash2 authors, FP8 draft conversion to tcclaviger, checkpoint quantization to AMD. No authorship assigned to the benchmark submitter beyond the reported measurement.
- License/right-to-submit: model cards list Apache 2.0; no new source-code redistribution or adoption in this intake, and no contributor right-to-submit attestation requested/received.
- Disposition: retain research notes; no changes to model packages, homepage rates, serving defaults or LocalMaxxing submissions.

Read the [findings and transfer priorities](README.md). Reported metadata is preserved separately from [local static review](validation/review-metadata.json).

September 14 follow-up: user excludes DFlash and retains FP8/native MTP.
[MTP-only source review](validation/2026-09-14-mtp-fp8-transfer-review.md)
preserves one inactive metadata cleanup and an exact-communication design lead.
No model requests, installed changes, new speed measurements or promotion.

September 14 implementation follow-up: the [FP8/native-MTP campaign](../../experiments/qwen38-27b-b70/notes/2026-09-14-mtp-lossless-transfer-results.md)
implemented and offline-tested the metadata relocation and a native Intel
communication prototype. The operator attempt failed NaN-payload equality and
recorded GPU memory faults; native work halted before performance or model
tests. No validated boost, recipe integration or verification of the AMD run.
The query-length observation is acknowledged; the actual branch relocation
and Intel prototype are lab adaptations. All failed stages remain preserved.
