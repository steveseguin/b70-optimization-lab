# Qwen3.8 official FP8 TP2 MTP1 serial-exact R19 preregistration

Date: 2026-08-28

Status: R19 ABI-negative; R20/R21/R22 withheld diagnostics with a subsequently
discovered unmatched-oracle confound; no performance or correctness claim

> **Audit correction (2026-08-28):** the R18 MTP0 oracle used below did not
> receive `VLLM_BATCH_INVARIANT=1`, while the R20-R22 MTP1 candidates did.
> Moreover, Qwen3.8 uses `GemmaRMSNorm`, and the exact XPU runtime did not route
> that operator through the attempted batch-invariant treatment. The 7/12
> comparisons remain valid reasons to withhold those candidates, but they do
> **not** isolate packed GDN or prove that the remaining difference was above
> GDN. Those causal statements are withdrawn. R23-R25 use matched environments
> and a separately proven XPU Gemma RMSNorm path.

## Question

Can the existing serial-exact GDN verifier make official-FP8/W8A16 TP2 MTP1
produce exactly the same complete outputs as the same-image MTP0 target, while
retaining a useful speed improvement over the qualified compiled MTP0 result?

The preceding treatments separate repeatability from target correctness:

- graph-off compiled MTP1 R16 measured `52.736500` and `52.388598 tok/s`, but
  the two fresh servers matched only 7/12 complete token arrays;
- graph-off eager MTP1 R18 repeated 12/12 across fresh servers, but matched an
  oracle later found to have an unmatched batch-invariance environment on only
  7/12 prompts; and
- a broad asynchronous all-gather completion override deadlocked during model
  loading and is rejected.

None of those MTP1 rates is eligible for a headline. Deterministic output that
differs from the unchanged target remains unacceptable; the old evidence did
not, however, identify which packed-shape operation caused the difference.

## Frozen candidate

- Base service image:
  `neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-workwait-r16`.
- Kernel source: vLLM XPU kernels
  `2dd55f380df753a10a88fcd9e96192561066e713`.
- Kernel delta: extend the existing one-request serial-exact recurrent proof
  from exactly four verifier rows to two through four rows, deriving the state
  width and loop bound from `total_spec_tokens`. MTP1 presents two rows: the
  target position plus one publisher-MTP position.
- vLLM capability gate: advertise GDN batch-invariance support only while
  `VLLM_XPU_GDN_NATIVE_SPEC_RECURRENT_SERIAL_EXACT=1`; every other GDN path
  remains fail-closed.
- Runtime treatment: graph off, eager first,
  `VLLM_BATCH_INVARIANT=1`, serial-exact GDN on, and persistent GDN scratch on.
- Unchanged model, official FP8 quantization, lab W8A16 dispatch, FP16 KV,
  TP2 topology, seed, 1,024-token service shape, and target model.

## Decision order

1. Build the two XPU-kernel DSOs in an isolated source checkout and overlay
   only those DSOs plus the narrow vLLM capability gate on the R16 image.
2. Start a fresh eager MTP1 server with a new compile-cache path. Require the
   complete fixed 12-prompt, six-class, natural-512 suite, cache zero on every
   request, independent objective canaries, and the serial-exact branch marker.
3. Compare every complete token array with a genuinely environment-matched
   eager MTP0 oracle. The originally named R18 oracle was later found not to
   satisfy this condition. Any mismatch still closes the candidate negative;
   do not run a repeat merely to manufacture a stable but target-different
   result.
4. Only after 12/12 oracle parity, run a fresh-server eager repeat and require
   12/12 A/B equality.
5. Only after eager parity and repeatability, test graph-off compiled MTP1 with
   the same treatment. Promotion requires two fresh servers, all workload and
   canary gates, 12/12 target parity, 12/12 A/B equality, and a useful gain over
   qualified MTP0's `34.031596 tok/s`.

Diagnostic subsets, selected fixtures, warmed prompts, repeated-prompt caches,
and deterministic output that differs from the unchanged target cannot pass
this program.

## Executed results

### R19: historical kernel could not enter inference

The generalized historical `2dd55f3` serial-exact kernel built coherently, but
the current vLLM call site supplies the newer 29-argument GDN interface while
that kernel exports the older 23-argument interface. Startup failed with the
explicit schema error. This is an ABI-negative build, not benchmark evidence.

### R20: recurrent-only forward port changed the wrong answer

R20 forward-ported a narrowly gated one-request/two-to-four-row serial
recurrent transaction to ABI-compatible kernel source `1e90ffa`. It passed
direct model verification, device import, the 29-argument schema gate, the
complete cold realistic workload gate, cache-zero checks, and independent
canaries. Its diagnostic class-balanced median was `18.30436979743692 tok/s`.

It matched the eager MTP0 oracle on only 7/12 complete token arrays. The five
first divergences were architecture tradeoff token 341, bug report token 110,
code review token 251, incident retrospective token 392, and performance
hypotheses token 169. The result is withheld and the preregistered ladder
correctly stopped before an R20 repeat or compiled test.

### R21: ordinary convolution plus ordinary recurrence was identical to R20

R21 additionally replayed every speculative convolution row through the same
ordinary one-token convolution kernel used by target-only decoding, with an
explicit source-state snapshot before each cache publication. Both serial
convolution and serial recurrence markers fired on both TP ranks. The complete
cold suite passed its workload/canary gates at a diagnostic
`18.023346015609906 tok/s`.

R21 was 12/12 token-array identical to R20 and retained exactly the same five
oracle divergences at exactly the same token positions. Because the target
environment was later found to be unmatched, this result does not isolate
either special speculative convolution or recurrent arithmetic. R21 is
withheld; there is no repeat, compiled test, public decode rate, or package
promotion.

### R22: suppressing the bonus token did not change the mismatch

R22 kept the verified/replacement token in sampler column zero but suppressed
the MTP1 bonus token in column one, forcing the following step to recompute
that token as a target row. The first launcher attempt was invalid and stopped
after one prompt because the allowlist had omitted the treatment variable; its
missing marker caught the mistake. The corrected R22b launcher passed the
variable through and its marker fired.

R22b completed the fixed cold suite at a diagnostic
`10.001832223262543 tok/s`. All workload, cache-zero, and independent-canary
gates passed. It still matched the eager MTP0 oracle on only 7/12 complete
token arrays, with the same five prompt IDs and exactly the same first
divergence positions as R20 and R21. Its complete outputs were also 12/12
identical to R21 despite the deliberately different emitted-token cadence.

The unchanged output under bonus suppression shows only that this treatment
did not repair the then-observed mismatch. The unmatched target environment
prevents a stronger causal conclusion about the bonus token, the first
verifier row, or operations above GDN. R22 is withheld; there is no repeat,
compiled test, public decode rate, or package promotion.

## Current conclusion and next discriminator

R20-R22 remain useful negative treatments but do not rule out either GDN or
the sampler because their target comparison was confounded. The next executed
discriminators were a matched W8A16-off pair (R23) and explicit XPU
`GemmaRMSNorm` shape-invariance proofs. The final packed-RMS plus
deterministic-Inductor treatment qualified at R32; see the
[follow-up result](2026-08-28-qwen38-fp8-mtp1-deterministic-r32-result.md) and
[structured evidence](../data/2026-08-28-qwen38-fp8-mtp1-deterministic-r32.json)
rather than retrofitting that result into this preregistered decision.
