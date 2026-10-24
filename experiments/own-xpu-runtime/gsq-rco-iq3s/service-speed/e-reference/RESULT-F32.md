# F32 exact engine against the exact reference: 99.90% agreement (2026-10-24)

## What was compared

- **Engine.** Binary `32654dfb2fde` in `--activations f32` mode: F32 activations, F32 KV and the F32 recurrent state. This is
  the service's running mode.
- **Output.** The 12-prompt realistic suite ([../d-mtp-fp8/suite/](../d-mtp-fp8/suite/), F32 run in
  [runs/f32-suite.json](runs/f32-suite.json)), greedy with MTP. That is 11 × 512 tokens plus 333 tokens for
  customer-email (natural EOS).
- **Reference.** The exact CPU reference ([RESULT.md](RESULT.md)) was teacher-forced on each prompt followed by the
  engine's own output. It uses canonical dequantization, F64 matmul sums, F32 everything else, and an F32 KV cache.
- **Test.** At every output position, the reference's argmax must equal the token the engine emitted.
- **Inputs and rows.** In [runs/f32suite/](runs/f32suite/): the runner, `inputs/in-<prompt>.json` and
  `<prompt>.rows.jsonl`.

## Result

| | Positions | Reference argmax ≠ engine token |
|---|---:|---:|
| BF16 engine (5926), incident sequence ([RESULT.md](RESULT.md)) | 512 | 9 (1.76%), gaps 0.04–0.23 |
| **F32 engine, 12-prompt suite** | **5,965** | **6 (0.10%)** |

The 6 positions (output index, reference top-1 logit minus the engine token's logit):
- bug-report-synthesis 456: 0.0003;
- technical-guide 175: 0.100;
- technical-guide 261: 0.015;
- technical-guide 420: 0.019;
- technical-guide 462: 0.004;
- technical-guide 472: 0.009.

The other 10 prompts agree at every position. Every disagreement is a near-tie, and in each the engine's token is the
reference's runner-up.

## What the residual is not (controls run on the two prompts with disagreements)

- **Matmul summation order.** A diagnostic reference that sums in F32 in the engine's exact lane order (32 lane-strided
  partial sums, then the subgroup tree) changes the reference logits by at most 4e-5 and changes no argmax. The engine's
  disagreements are 100–2,500 times larger, so they are not F32 summation-order noise. Patch:
  [ggml-cpu-exact-acc-diagnostic.patch](ggml-cpu-exact-acc-diagnostic.patch) (`GGML_CPU_EXACT_ACC=f32lane`).
- **RoPE angle formula.**
  - The reference builds angles by repeated multiplication (`theta *= theta_scale`). The engine computes each angle
    directly, as `f32(pos*powf(1e7,-2j/64))`.
  - A reference using the engine's formula (`GGML_CPU_EXACT_ROPE=powf`) gives the same 5 technical-guide disagreements,
    with gaps identical to 4 decimals.
  - Patch: [ggml-cpu-exact-rope-diagnostic.patch](ggml-cpu-exact-rope-diagnostic.patch). It also has an `f64` mode and
    handles the model's interleaved multi-section RoPE (type 40, sections 11/11/10/0).
- **Chunked recurrence algebra.** The reference resolves the fused gated-delta-net op, which is sequential per token
  like the engine. It does not use the chunked matrix form.

## Open

The source of the residual is not localized. Candidates:
- discrete MoE top-10-of-512 near-ties: the engine ranks normalized F32 probabilities, with ties broken by lower expert
  id;
- implementation differences in exp, sigmoid and rsqrt;
- some remaining difference in an engine op.

Localizing needs a per-layer comparison of the hidden streams at one disagreement position: the engine's
`--retain-steps` layer snapshots against the reference's graph callbacks. That is the next fidelity step. Until it is
done, the claim is "agrees with the exact reference at 99.90% of positions, differing only at near-ties of at most 0.1
logit". It is not "bit-faithful".

## Cost of F32 mode

The suite's median decode is 23.2 tok/s, against 24.0 for the BF16 engine on the same suite (−3.3%). MTP acceptance is
76.7% against 77.6%.
