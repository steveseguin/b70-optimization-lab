# Benchmark integrity audit — 2026-08-27

This audit covers recently promoted or package-featured benchmark claims from
2026-08-25 through 2026-08-27. Raw evidence is preserved. Corrections change
classification and public use; they do not erase measurements.

## Publication contract

A general single-user headline must satisfy all of these independent gates:

1. **Representative performance:** the complete fixed suite, with prose,
   code, analysis, operations, documentation, and structured-writing tasks;
   each unique prompt once; a 512-token response cap; every response long
   enough for the first-100-event/99-interval metric; median within each prompt
   type, then median across type medians, as the primary rate. This prevents a
   class with more prompts from dominating the headline.
2. **No reuse:** every request reports zero cached prompt tokens. Prompt/KV,
   response, context-checkpoint, history, n-gram, learned-draft, and repeated
   prompt reuse are disabled. Loaded weights and compiled kernels are allowed;
   a warm runtime is not permission to warm the benchmark inputs.
3. **Quality:** the optimized identity is checked against the registered
   unoptimized or unchanged-target oracle. Exact-token, semantic, arithmetic,
   coding, practical, and long-context gates are used where relevant.
4. **Determinism:** registered repeat and fresh-server checks pass. For
   speculative decoding, accepted draft tokens are verified by the unchanged
   target model.
5. **Reproducibility:** model/runtime/patch/config identities and hashes are
   bound to both performance and quality evidence. Two fresh-server attempts
   are required for a package headline.

Context curves, aggregate concurrency, raw-engine rates, synthetic shape
fixtures, and mechanism probes may still be published when clearly scoped.
They do not become general single-user headlines.

## Recent-claim verdicts

| Claim | Verdict | Public action |
| --- | --- | --- |
| Gemma 4 26B A4B Q8+MTP, `124.977141` legacy / `123.727369` all-prompt tok/s | **Valid suite, headline aggregation corrected.** The rows satisfy the varied full-512 cache-zero performance gate and the target-verification/quality record remains valid. The class-balanced 99-interval median is `122.160357 tok/s`. | Publish `122.160357`; preserve the other two values as labeled compatibility/diagnostic fields. |
| LFM2.5 2.6B Q8_0, `132.351606 tok/s` | **Measured candidate, strict headline pending.** The guide records a complete varied 512-cap pair and objective canaries, but the raw operating-point/canary JSON files are not in the repository. | Preserve the observation in the guide; import, hash-bind, and replay before promotion. |
| Ornith 1.5 35B-A3B Q4_K_M, `131.460231 tok/s` | **Scoped measurement, strict headline pending.** Complete varied-suite performance and extensive same-binary patch exactness exist, but fresh stock servers matched 0/12 complete natural-response hashes. | Preserve mechanism/context evidence; require a stable cross-server oracle before promotion. |
| Nemotron 3.5 Lightning 30B-A3B, `72.169452 tok/s` | **Measured candidate, strict headline pending.** The guide records a complete varied 512-cap pair and reasoning-off deterministic canaries, but the raw operating-point/canary JSON files are not in the repository. | Preserve the observation in the guide; import, hash-bind, and replay before promotion. |
| Ornith 1.5 9B Q8_0, `49.588381 tok/s` | **Measured candidate, strict headline pending.** The guide records a complete varied 512-cap pair and objective canaries, but the raw operating-point/canary JSON files are not in the repository. | Preserve the observation in the guide; import, hash-bind, and replay before promotion. |
| Qwen3.8 27B Q4_K_M TP1, `27.824790 tok/s` all-prompt | **Retain with class-balanced headline `27.825726`.** Complete varied 12-prompt suite with a 512 cap, cache zero, two fresh servers, and exact oracle/quality gates. One response ended naturally at 270 tokens, after the registered 100-event window; that is valid and is not a short requested cap. | Keep the exact package-scoped result; publish the class-balanced value and retain the all-prompt value as secondary. |
| Qwen3.8 27B Q8_0 TP1, `19.662501 tok/s` | **Scoped measurement, not a package headline.** Five-repeat direct `llama-bench` tg128 measurement plus a separate service-quality battery; not varied-prompt HTTP. | Keep the context/prefill curves; set featured metric to pending. |
| Qwen3.8 27B Q8_0 TP2, `36.772932 tok/s` | **Valid historical identity, mismatched package headline.** The measurement is reasoning-enabled; the package launcher defaults to reasoning off. | Preserve the historical A/B and quality evidence; set the exact packaged headline to pending. |
| Qwen3.8 27B FP8/W8A16 MTP8, `58.391033 tok/s` | **Incomplete screening only.** It used the varied suite and cache-zero requests but requested only 128 output tokens. | Removed from package, landing-page, generated-model, scoreboard, and submission headline surfaces. |
| Qwen3.8 27B FP8/W8A16 MTP8, `146.814418 tok/s` | **Selected-fixture diagnostic only.** It used one 40-token high-acceptance fixture and therefore measures that fixture, not representative model speed. | Removed from public headline graphs and package speed; historical mechanism notes carry correction banners. |
| Qwen3.8 FP8/W8A16 MTP0 c128 `1,112.570323 tok/s` and exact-32K `31.489587 tok/s` | **Retain as separately scoped capacity/context evidence.** These are output-audited target-only measurements, not substitutes for the missing varied-prompt single-user headline. | Keep explicit aggregate/context labels; never use either as the general one-user number. |

Post-audit closure: Qwen3.8 Q8_0 TP2 subsequently passed the exact missing
contract on two fresh servers. The full 12-prompt/six-class, 512-cap,
cache-zero attempts measured `36.733956` and `36.718938 tok/s`, passed both
objective-canary batteries, and matched complete token arrays 12/12. The
paired **`36.726447 tok/s`** value is now the packaged headline; the historical
row above remains the reason that number was initially withheld. See the
[R2 result](../experiments/qwen38-27b-b70/notes/2026-08-27-qwen38-q8-tp2-strict-reasoningoff-native-r2-result.md).

The LocalMaxxing submission `cmtb5n45n0021qq01n13vly2h` was built from the
incomplete FP8 evidence and is premature. Repository surfaces mark withdrawal
as recommended. The external service does not provide a trusted automated
delete/edit path in the current workflow, so human coordination is required.

## How the failure happened

The benchmark harness checked only that responses covered the first 100-token
metric window. It did not require the registered 512-token cap. After a prompt
filter, it compared completion against the filtered list rather than the full
suite. The stored “final gate” boolean was then trusted by submission tooling,
even though it described performance-workload validity and was not hash-bound
to an independent quality/determinism result. Finally, the package schema
required a featured number, which encouraged a diagnostic result to fill a
headline slot.

The 146.814 fixture was also called “promoted” inside a mechanism-selection
ladder. That internal word was later mistaken for public promotion. Those are
different decisions and now use different states.

## Durable corrections

- The realistic-suite harness fails closed unless the full fixed suite runs,
  at least five prompt classes are represented, the requested cap is exactly
  512, every response covers the 100-event metric, cache is zero, and no prompt
  subset or `ignore_eos` override is used.
- The headline aggregation is class-balanced: median within task class, then
  median across class medians. The ordinary all-prompt median remains visible
  only as a secondary diagnostic.
- The evidence qualifier re-derives those facts from raw rows and identity; it
  does not trust an old `passed` boolean.
- A performance artifact now identifies itself as a workload-performance gate,
  not complete public promotion.
- External payload builders require a hash-bound promotion attestation linking
  the exact performance file to quality/oracle evidence, deterministic and
  fresh-server repeats, unchanged target identity, and a no-quality-loss
  decision.
- Packages may explicitly have `featured_metric: null`; generators display
  **strict headline pending** instead of forcing a diagnostic number.
- Unit tests cover 128-token caps, prompt subsets, repeated prompt classes,
  early natural EOS after the metric window, insufficient completions,
  `ignore_eos`, evidence substitution, and failed quality gates.

## Remaining work

No corrected replacement FP8 single-user number is claimed yet. It requires
two fresh-server runs of the complete varied 512-cap suite and the independent
quality/determinism attestation for the exact optimized identity. Until that
exists, the honest public value is **strict headline pending**.
