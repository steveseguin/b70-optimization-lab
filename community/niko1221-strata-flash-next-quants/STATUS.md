# Strata / Flash-Next quantization intake — 2026-10-10

Evidence level: **community-reported**. Review status: bounded source and metadata review only; no contributed code executed, model payload downloaded, or B70 test performed.

Contribution: Niko1221 and Strata contributors provide the inference/packing engine and links to quantized models; ISTA-DASLab provides GSQ/RCO quantizations. Acknowledged as a model/tooling lead, with no validated boost or integration. GGUF/ggml formats originate in llama.cpp/ggml; Intel AutoRound and other publishers are credited separately in the research note.

Source: [Strata commit 61b3fb5dd3f1e8ec09cf7e4e05208bc6d3c46406](https://github.com/Niko1221/Strata/tree/61b3fb5dd3f1e8ec09cf7e4e05208bc6d3c46406). Strata code is MIT. Weight licenses are separate; ISTA card metadata conflicts with its inherited-license wording, so do not assume Apache redistribution rights.

[Research, ranking, disk request and remaining gates](../../notes/2026-10-10-strata-flash-next-quants.md).
[HF revisions, file sizes and publisher-provided LFS hashes](reported/metadata-inventory.json).
[Proposed exact download allow-lists](reported/proposed-downloads.json).
The four allocation text files in `reported/` are unchanged small publisher artifacts from the pinned ISTA model repository, not local measurements. No performance claim is submitted or promoted.

Validation: source inspection, JSON parsing and size arithmetic. API hashes have **not** been checked against model payloads. Missing calibration details, runtime qualification, quality acceptance, storage approval and the current host halt remain open. Research does not authorize any launcher, installer, cleanup, host setting or publication action.
