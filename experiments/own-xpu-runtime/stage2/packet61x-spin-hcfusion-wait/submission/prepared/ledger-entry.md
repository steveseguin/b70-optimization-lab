## packet61x-spin-hcfusion-wait — PREPARED ONLY; not a public submission

- Submission ID / URL: **pending coordinator submission**.
- Prior record: [cmvcf84kb06r2le0174bgk16l](https://www.localmaxxing.com/runs/cmvcf84kb06r2le0174bgk16l).
- Model: Unsloth Qwen3.8 Flash-Next UD-IQ3_XXS, quantized compressed version;
  revision `766911a6b7369840a91dbcd95f9f997acaab6cd6`, separate from FP8.
- Runtime: `packet61x-spin-hcfusion-wait`, sealed build base `4941d17afc6fe42ff28c7c6f2f600356e52e87ed`, seal `7a4f76c0261ef731a6650fa5feb4d657d4d24a3697d31837d0eaf7d51357e768`.
- Hardware: 2 × Arc Pro B70, cards 0+1, target 23/25, draft rank 1, capacity 4096,
  BF16 KV; unchanged target verification.
- Primary class-balanced rate: **51.03304090336844 tok/s**; all-prompt **51.15455926856572 tok/s**;
  p10 49.89482484038567, mean 51.06548012999681; median TTFT 1030.4302410004311 ms; median wall 36.29745277703623 tok/s.
- Scope: 12 fixed realistic cold prompts × 128 tokens, cached_tokens=0;
  99 intervals between events 1 and 100; owner-authorized 128-token exception.
  Strict 512-cap gate **false**; standard prefill **not measured**.
- Correctness: 12/12 exact against `iq3-p49-split32-v1` CPU oracle and independent device
  windows. Arithmetic changed from SPEED6; no claim of bit equality to SPEED6.
- [Result, prompt/output hashes and bound evidence](/experiments/own-xpu-runtime/stage2/packet61x-spin-hcfusion-wait/submission/prepared/result.json).
- Real submission / API response: **not performed by preparation**.

Do not paste this into the public-submission index as an accepted record until
an actual successful response supplies the ID and date. Preserve the prior record.
