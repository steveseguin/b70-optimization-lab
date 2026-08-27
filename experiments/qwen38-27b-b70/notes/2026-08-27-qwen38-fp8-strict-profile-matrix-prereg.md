# Qwen3.8 FP8 strict single-user profile matrix preregistration

## Purpose

Close the promotion-grade single-user gaps for the official FP8 TP2 package
without reusing the invalid 40-token fixture or the insufficient 128-token-cap
screen. The bounded profiles are target-only/MTP0, publisher MTP1, and dynamic
MTP8-at-one-user. Every profile is a separate operating identity.

## Frozen performance contract

- official `Qwen/Qwen3.8-27B-FP8` revision
  `017b9c7af6b5689d5dd426a76e0bc077eb5ca20a`;
- two Intel Arc Pro B70 cards, TP2, FP16 activations/KV, block-W8A16 dispatch;
- complete fixed 12-prompt suite, with its prose, code, analysis, operations,
  documentation, and structured-writing classes;
- one request per prompt per attempt, `max_tokens=512`, natural EOS allowed,
  `ignore_eos=false`, temperature zero, and streamed token IDs;
- every row must contain the first 100 generated events and report
  `cached_tokens=0`;
- primary rate is the median of the per-class medians over the 99 intervals
  between generated events 1 and 100 after TTFT;
- two new containers and two new compile-cache paths per profile. Loaded model
  weights and compiled kernels may be warm inside an attempt; prompt, KV,
  response, history, n-gram, or learned-prompt reuse may not be warm;
- no subset, selected acceptance fixture, extrapolation, or replacement of a
  failed row is allowed.

The runner is
[`run-20260827-qwen38-fp8-strict-profile-attempt.sh`](../scripts/run-20260827-qwen38-fp8-strict-profile-attempt.sh).
It refuses an existing output/cache path, captures container identity and raw
rows, and runs objective canaries after—not before—the performance suite.

## Independent promotion gates

Passing the performance workload is insufficient. Promotion requires a
hash-bound attestation for the exact result plus:

1. objective canaries and eight-repeat stability on the optimized path;
2. exact complete token-array comparison across its two fresh servers;
3. target/verifier comparison against the MTP0 profile on the same varied
   prompts, with any legitimate runtime-order difference adjudicated rather
   than silently accepted;
4. unchanged target model and target verification for accepted speculative
   tokens;
5. an explicit no-quality-loss decision.

If any gate fails, retain the measurement as diagnostic evidence and leave the
package headline pending. MTP1 or dynamic-MTP performance may not be spliced
into the MTP0 profile. The existing scoped 32K and aggregate-concurrency curves
remain separate measurements.

## Stop rules

- Stop a profile after a server failure, cache/prompt reuse, incomplete metric
  window, missing token IDs, nonzero cached tokens, or failed objective canary.
- Preserve the failed attempt; do not rerun it under the same identity.
- Do not run the INT4 AutoRound/MTP5 full server on this 15 GiB host.
- Do not promote or submit any number until the independent attestation passes.
