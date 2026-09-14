# AMD Qwen3.8 MXFP4 / Radiance / DFlash2 review

- Evidence level: **community-reported**.
- Patch review: bounded static inspection of the relevant source, not a full runtime audit.
- Contributor: LocalMaxxing **1337Hero**, identified by the user as Mike Key / @1337hero. The social post URL was not supplied.
- Contribution: useful dual-R9700 benchmark and implementation lead. Acknowledged; no validated B70 boost or integration.
- Source: [reported run](https://www.localmaxxing.com/en/models/amd/Qwen3.8-27B-Quark-AWQ-MXFP4?run=cmtx76rb70aj0ps014d8a37v9).
- Model/runtime: AMD Quark AWQ MXFP4, FP8 KV, TP2, DFlash2 K7; reported Radiance 1.0.16. See [identity and arithmetic](validation/review-metadata.json).
- Executed here: metadata retrieval, source reading and arithmetic only. No external source code, container, model request or GPU benchmark executed. Healthy local FP8 service preserved.
- Quality: the run lacks output evidence; the pinned runtime documentation says strict speculative/non-spec equivalence has not passed.
- Recognition: report acknowledged; core runtime/kernels credited to StillDeadcode, MXFP4 work to Brian/ggz14, integration to magiccodingman, draft algorithm to DFlash2 authors, FP8 draft conversion to tcclaviger, checkpoint quantization to AMD. No authorship assigned to the benchmark submitter beyond the reported measurement.
- License/right-to-submit: model cards list Apache 2.0; no new source-code redistribution or adoption in this intake, and no contributor right-to-submit attestation requested/received.
- Disposition: retain research notes; no changes to model packages, homepage rates, serving defaults or LocalMaxxing submissions.

Read the [findings and transfer priorities](README.md). Reported metadata is preserved separately from [local static review](validation/review-metadata.json).
