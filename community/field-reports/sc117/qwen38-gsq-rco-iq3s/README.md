# SC117 Qwen3.8 Flash-Next GSQ-RCO IQ3_S intake

Evidence level: `community-reported`. Recognition: acknowledged model lead.
Review scope: source identity, local download integrity, bounded header and
CPU compatibility checks. No B70 inference or performance reproduction.

The owner supplied [SC117's model repository](https://huggingface.co/SC117/Qwen3.8-Flash-Next-GSQ-RCO-abliterated-GGUF)
and explicitly requested IQ3_S and integration into our custom engine with
MTP. Pinned revision: `eec4e10a2c29b440a2ae85591fa11569ce752963`.
Display name: SC117. License reported by model card: Apache-2.0. Separate
right-to-submit statement: unknown; this is a public model lead, not a
submitted code patch. Original upstream revisions beyond this assembled
release are not established by this intake.

Publisher provenance: Qwen base model; ISTA-DASLab GSQ/RCO quantization;
orcarouter abliterated weights; SC117 alignment, 144-tensor transplant,
assembled release and verification data. The stock MTP is described as
unmodified. Publisher quality/performance claims have not been reproduced
here. No measured boost is credited or entered into the claims registry.

Pre-existing lab work is our model-specific runtime and MTP coordinator.
New lab follow-up is downloaded-file verification, header/type census,
independent decoder checks and the engine integration. GGML format references
are separately pinned and credited where used. None of those lab checks
establishes the publisher's transplant or model-quality claims.

[Local integration evidence](../../../../experiments/own-xpu-runtime/gsq-rco-iq3s/README.md)
records the exact files and current qualification limits. Download integrity
and CPU tests do not elevate this report to `B70-tested` or `B70-verified`.
