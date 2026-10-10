# Objective: Our Own Model-Specific Inference Runtimes For Intel Xe (B70)

**Owner decision, 2026-10-10.** This is a long-running objective of the lab,
alongside the two standing priorities (the Flash-Next line and the LTX live
stream). It is not a replacement for the current certified lanes; those keep
running and keep publishing while this is built.

## The owner's words

- "Lets do that then; lets put that as a long running objective for us."
- "I do NOT want to use Strata itself; we can use any optimizations around
  kernels and such to help us though, and we can use whatever official or
  unsloth or such quantizations if needed also. I do not want to use non
  official sources, other than those from unsloth lets say. Model specific
  runtimes make sense, and we have lots of models to do this for."
- "We can use optimizations from Strata and other projects, but I dont want
  to be basing our work off of theirs; I want it to be our own project.
  Mainly I'd want to accelerate any optimizations by looking for ideas of what
  works for optimizing. This only needs to be for Intel XPU/Xe hardware,
  mainly the B70, as that's what we have. We can use other models beyond
  Unsloth/official models, but I'd want to have justifications and my
  approval to do so."

## Rules that bind this objective

1. **Our own project.** The runtime is written and owned here. Other projects
   (Strata, llama.cpp/ggml, vLLM, SGLang, ik_llama.cpp, TensorRT-LLM, Intel's
   own stacks) are read for ideas: kernel layouts, scheduling tricks, memory
   placement, speculative decoding, graph capture. Their code is not the base
   of ours. Platform libraries from Intel (SYCL, Level Zero, oneDNN, oneMKL,
   oneCCL, Triton-XPU) are dependencies, not "basing our work on theirs".
   Every borrowed idea is credited in the lane notes with a link.
2. **Intel Xe only, B70 first.** One to four Arc Pro B70 cards (32 GB each,
   one compute queue per card, copy-engine overlap only). No CUDA/HIP ports,
   no portability layer for other vendors.
3. **Weights: official publisher or Unsloth.** The model author's own release
   (any precision they publish) or an Unsloth release. Any other source needs
   a written justification in the lane note and the owner's approval before a
   byte is downloaded. Quantizations we produce ourselves from an official
   release (for example AutoRound INT4 from the official FP8 or BF16) count
   as our own work from an official source and are allowed.
4. **The lab's standing rules apply unchanged:** no cheating, lossless by
   default, machine safety, no server left running, receipts for every
   number, main-only Git, plain reports. A quantized line is never presented
   as the original model; its quality evidence is published next to its speed.
5. **Evidence gates every stage.** Nothing is "the runtime" until it has beaten
   or matched the existing certified line for that model on the same test,
   with bit-identical output where the line is lossless.

## Why (the evidence from this host)

- Our wins already are runtime work carried as patches: the 41-file MiniMax
  INT4 patch, the Flash-Next sealed patch sets and rebuilt GDN extension, the
  9B dynsd overlays, the LTX graph-capture layer, the teardown overlay. Every
  upstream image or tag bump re-resolves identity and costs launches.
- General runtimes fight the exactness standard: piecewise graphs break
  tie-site identity, graph plus MTP corrupts outputs on XPU, multi-sequence
  batches are not output-identical, and the upstream exit path is what faults
  the cards.
- The remaining levers on several lanes are overhead, not bandwidth: LTX is
  CPU-dispatch-bound with GEMMs at roofline, the Flash-Next M=2 verify step
  is glue, multi-card processes shadow every GPU buffer in host RAM.
- Kernels themselves are mostly at roofline (9B draft head at copy roofline,
  537 GB/s GEMMs). The runtime does not move the bandwidth bound; it removes
  what sits between the kernels. That bounds the gain and shapes the design:
  own the step, the placement, the capture, the teardown; write a kernel only
  where the upstream one is measured off roofline.

## Design pillars

- **Whole-step graph capture.** One captured decode step per model (target
  plus MTP/draft, sampler, state updates), replayed with device-resident
  inputs. Proven here at 2.4x bit-exact on LTX; forbidden in practice by the
  general runtimes for MTP on XPU.
- **Deterministic by construction.** Fixed reduction orders, no
  data-dependent host reads in the captured region, one replay per step,
  bit-identical replay as a test that runs every launch.
- **Census-based placement.** Weights, KV, graph pools and workspace placed
  from a measured per-card census with explicit floors; multi-card by layer or
  by tensor chosen per model from measured collective cost, never assumed.
- **Expert streaming and UVA offload** as first-class, with host-RAM shadow
  accounted (the multi-card shadow and the deferred-backing fix are known).
- **Orderly teardown.** Quiesce queues, free in order, exit only when the
  device is idle; the abrupt-exit fault class is a design input.
- **Loaders for safetensors (FP8/INT4 compressed-tensors, AutoRound) and
  GGUF** so official and Unsloth releases load without conversion.
- **Measurement built in:** the same fixed cold suites, receipts, and
  identity fields the lanes use today; the runtime emits its own run identity.

## Model lanes this applies to (priority order, from the site ranking)

1. Qwen3.8 Flash-Next: FP8 four-card (beat 46.854250 tok/s, lossless) and a
   two-card quantized line from an allowed source (Unsloth UD-IQ4_XS 93.7 GB,
   UD-IQ3_XXS 82.0 GB, UD-Q3_K_XL 90.0 GB, or our own AutoRound INT4 from the
   official FP8). The ISTA GSQ IQ3_S trial proposed in the Strata note is
   withdrawn under rule 3 unless the owner approves it with a justification.
2. Qwen3.8 27B: FP8 and AutoRound INT4 one-card, FP8 two-card multi-user.
3. MiniMax M2.7 INT4, Qwen3.6 35B, Gemma 4 26B-A4B, Muse Glimmer 30B,
   DeepSeek V4 Flash, Laguna S 2.1, Ornith 1.5 35B-A3B, Nemotron 3.5 Lightning.
4. Video: LTX 2.5 and MiniMax-H3 share the capture, placement and teardown
   layers; their samplers stay model-specific.

## Staged plan and gates

**Stage 0 (now; CPU-only while the GPU halt stands).** Written design spec;
inventory of runtime pieces we already own (graph-capture layer, rebuilt GDN
extension, Triton MoE tiles and tuned configs, placement census tools,
teardown overlay, certified replay harnesses); idea-mining survey of other
projects with each idea rated by expected gain on B70 and credited; storage
plan for allowed weights (root NVMe has 66 GB free; the 3.6 TB external disk
is unmounted and is an owner decision). Gate: the owner reads the spec.

**Stage 1. Single-card decode core on Qwen3.8 27B.** Own loader, own SYCL
or Triton-XPU GEMV/MoE/attention kernels (oneDNN where it is already at
roofline), one captured decode step, deterministic sampler, run identity and
receipts. Gate: bit-identical to the certified 27B outputs on the fixed suite
and at least the certified decode tok/s.

**Stage 2. Flash-Next.** GDN plus MoE plus MTP; four-card FP8 tensor-parallel
with the verify step inside the captured graph; two-card quantized line with
expert streaming. Gate: beat 46.854250 tok/s lossless on four cards; the
two-card line publishes its quality deltas versus FP8 with the owner's
approved tolerances.

**Stage 3. Serving.** Prefill, multi-user batching with its own certified
authority, long context, an OpenAI-compatible endpoint, a single-binary
package and a neural.download recipe per model.

**Stage 4. Video.** Move LTX 2.5 and MiniMax-H3 onto the shared layers.

Each stage is run as packets with receipts, notes under `notes/`, results
under `results/`, and promotion through the existing publication standards.

## Owner decisions still open for this objective

- Storage destination for allowed weights (cleanup of 83 GB, or mounting the
  external disk as a download cache).
- Quality tolerances for quantized lines (they are not lossless versus FP8).
- The project's name.
- Any weight source outside official/Unsloth, case by case.
