# Gemma Dashboard Transfer Ideas

Date: 2026-06-12

Source snapshot:

- Dashboard: `https://huggingface.co/spaces/gemma-challenge/gemma-dashboard`
- Organization page: `https://huggingface.co/gemma-challenge`
- Workspace guide:
  `https://huggingface.co/buckets/gemma-challenge/gemma-main-bucket/tree/README.md`
- Eval prompts:
  `https://huggingface.co/datasets/gemma-challenge/eval-prompts`
- Public API sampled:
  `https://gemma-challenge-gemma-bucket-sync.hf.space/v1/digest?limit=20`

This is about ideas for our Gemma lanes. It is not a Qwen3.6 speed result and
does not change the Qwen accepted endpoint.

## Useful Facts From The Challenge

- Target model is `google/gemma-4-E4B-it`, not our local Gemma 4 12B lane.
- Official hardware is single `a10g-small` with 1x NVIDIA A10G 24GB, not B70 or
  multi-GPU.
- Scoring is single-stream TPS. This matches our single-request latency focus
  better than aggregate serving benchmarks.
- Quality is enforced by PPL. The public guide says the validity cap is
  reference PPL plus 5%, around `2.42` when the reference is around `2.30`.
- The benchmark requires OpenAI-compatible serving that supports token-ID
  prompts, `prompt_logprobs`, and `add_special_tokens: false` for PPL scoring.
- Greedy decode is expected to remain token-identical to plain greedy
  autoregressive decode of the same submitted checkpoint.
- Current top public rows around `420 TPS` combine serving/runtime tricks:
  `lmhead12k`, `fa2sw`, public-prompt prefix-cache warming, one-graph/loopgraph
  decode, drafter/verifier work, fused accept/prep, and detokenization cleanup.
- Several private verification messages show that high self-reported TPS can be
  invalidated when private-set rerun TPS drifts by more than the verifier
  tolerance, even if PPL stays under the cap. Do not trust a single best draw.

## Transferable Ideas For Our Gemma

1. **Use PPL as a first-class speed gate.**
   Our Gemma quality gate should report both speed and PPL or a close proxy,
   plus exact canaries. A speed result that cannot run prompt-logprob scoring
   should be considered incomplete.

2. **Separate benchmark-safe prefix warming from production-safe prefix caching.**
   The challenge top row warmed the public prompt prefixes before readiness.
   That is useful for leaderboard mechanics but risky for production. The
   production-safe version for us is static system-prefix, tool-schema, and
   repeated-workflow prefix caching with explicit cache-hit telemetry.

3. **Investigate lm-head keep-set pruning with full-head fallback.**
   `lmhead12k` appears repeatedly in the best Gemma stack. For our Gemma, build
   a workload-specific vocabulary heatmap and test a fast restricted logits
   path only if a fallback preserves exact greedy output. Full logits remain
   mandatory for prompt-logprobs/PPL and for any token outside the keep set.

4. **Audit sliding-window/local attention execution.**
   The `fa2sw` frontier implies a real gain from serving sliding-window
   attention as sliding-window attention instead of accidentally doing full
   attention work. For our Gemma, verify each local/sliding layer's effective
   attention span and backend path on XPU.

5. **Measure drafter acceptance before changing speculative depth.**
   The public acceptance histogram shows K-depth can be exhausted; the valuable
   target is the zero-accept bucket, not blindly increasing K. For our Gemma,
   add an acceptance histogram that samples without per-step device-to-host
   synchronization.

6. **Respect exact-fidelity details in custom kernels.**
   Recent challenge messages called out partial RoPE, reading the model's live
   `cos_sin_cache`, BF16 rounding at operator boundaries, and deterministic
   tie-breaking as sources of drift. Any custom Gemma kernel or speculative
   verifier needs these details before speed matters.

7. **Avoid per-token host synchronization.**
   One public diagnostic reported instrumentation-deflated throughput around
   `364 TPS` versus the `418-420 TPS` family, attributing a large cost to
   per-step host work/sync. For us, device rings and interval dumpers are the
   right pattern; per-token CPU reads are not.

8. **Use paired multi-draw A/B, not best-draw fishing.**
   The public frontier reports wide draw bands even for byte-identical packages.
   For our Gemma, require multiple paired runs with mean/spread, then promote
   the stable improvement, not a lucky sample.

9. **Keep multimodal behavior explicit.**
   The challenge disallows disabling text/image/audio capability for speed.
   Our Gemma 4 local lane should record whether image/audio are intentionally
   supported, stubbed, disabled, or out of scope. Speed numbers should state the
   capability surface.

10. **Publish exact manifests and immutable evidence.**
    The challenge's `manifest.json` plus `serve.py` plus artifact bucket pattern
    is worth copying. Our GitHub notes already do this partially; Gemma
    experiments should include the exact command, model revision, cache state,
    PPL/quality summary, and raw benchmark JSON.

## Bigger Gemma Ideas To Try

1. **Dual logits mode.**
   Fast restricted lm-head for normal greedy decode, full lm-head for PPL,
   prompt-logprobs, and fallback. The gate is token identity versus full
   logits, not approximate PPL alone.

2. **Static prefix/service-profile lanes.**
   Make separate serving profiles for known repeated chat/system/tool prefixes
   and general unknown prompts. This is the production-clean version of public
   prompt pre-cache.

3. **Gemma-specific sliding attention microbench.**
   Build a small harness that times every Gemma attention layer by effective
   window size, backend, context length, and graph-capture state. Promote only
   changes that preserve token/PPL gates.

4. **Speculative verifier with acceptance histogram first.**
   Before training or integrating any drafter, run an exact-target verifier
   harness that records accept lengths, zero-accept cases, rollback cost, and
   per-step sync cost.

5. **Kernel fidelity checklist.**
   For each custom Gemma kernel: prove partial RoPE handling, live cache use,
   BF16 boundary behavior, tie-breaking, and full-output parity on a fixed
   prompt bank before benchmarking.

6. **Variance-aware leaderboard discipline.**
   Store every draw, including bad draws, and require private-like prompt
   reruns. A speed claim should survive both PPL and run-to-run variance.

7. **Prompt-logprob compatibility audit.**
   Confirm our current Gemma vLLM endpoint can accept integer-token prompts,
   disable special-token insertion, and return `prompt_logprobs`. If not, fix
   that before serious PPL-gated optimization.
