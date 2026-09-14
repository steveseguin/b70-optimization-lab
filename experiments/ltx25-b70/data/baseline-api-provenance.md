# LTX 2.5 baseline API graph provenance

Prepared 2026-09-13; execution and quality qualification are pending.

Derived from Comfy-Org's official [LTX 2.5 T2V template](https://raw.githubusercontent.com/Comfy-Org/workflow_templates/main/templates/video_ltx2_5_t2v.json), saved locally as `upstream-t2v-workflow.json`.
Upstream snapshot SHA256: `0040f7d44a57bbaaddff78a2fbe6a9bc9631897f034f8c0fa179f94a4c8e6b84`.
Node input names inspected against ComfyUI commit `19e1058f4c445ef74047e77a23f9ca7684c1e4b6`.

`baseline-api.json` is the prompt object; submit it inside the API request's `prompt` field. Preserves the template's node IDs and AV links, both ancestral samplers, full 8-step first-stage and 3-step refinement sigma schedules, CFG 1 for each modality, and x2 latent upscaler. Changes: BF16 distilled transformer and BF16 projected Gemma4 encoder; explicit CPU text encoding; fixed boat prompt with no enhancer; seed 42 at both stages; batch 1; first stage 128x128, final 256x256; 25 frames at 24 fps; ordinary VAEDecode instead of tiled decode; PNG frame output plus stock MP4 preview. This is a small execution baseline, not a quality-preserving replacement for a higher-resolution run.

The MP4 is a lossy viewing preview. SaveImage PNGs preserve their 8-bit pixel values, but stock SaveImage quantizes the floating-point decoded tensors to 8-bit. Root will attach native tensor capture before claiming lossless output preservation or exact repeat parity. The supplied BF16 checkpoints are used without additional weight quantization; BF16 precision and the distilled checkpoint identity remain explicit parts of the baseline. Preserve decoded tensors and compare genuine recomputations with caching disabled. In this ComfyUI revision the diffusion VAE resets its RNG to seed 0 internally; both sampler seeds are 42. `--deterministic` is advisory (`warn_only=True`) and does not establish repeatability by itself.
