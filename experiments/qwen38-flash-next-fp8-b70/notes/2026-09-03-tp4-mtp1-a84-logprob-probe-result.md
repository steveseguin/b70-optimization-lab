# Qwen3.8 Flash-Next FP8 A84 result: the MTP1 verification path is not the decode path

Date: 2026-09-03 11:19--11:46 EDT
Status: **diagnostic; closes the question of where MTP1 diverges**

## What ran

The A81 server (MTP1 in the full decode graph, deterministic identity, NVMe
copy) under the A59 logprob probe at depths 8, 256 and 2048: eight
`max_tokens=1` repeats with top-5 logprobs and three 128-token repeats per
depth. Offline comparison against the MTP0 line's A76 probe with
`tools/compare-q38-logprob-probes.py`.

## Findings

| depth | MTP1 self-repeat | first-step top-5 vs MTP0 | first token to differ (of 128) | mean / max abs top-1 logprob diff before it | gap at divergence (MTP1 / MTP0) |
| ---: | --- | --- | ---: | ---: | ---: |
| 8 | 8/8 and 3/3 identical | identical, diff 0.0 | 31 | 0.089 / 0.742 | 0.25 / 0.125 |
| 256 | identical | identical, diff 0.0 | 15 | 0.022 / 0.078 | 0.50 / 0.25 |
| 2048 | identical | identical, diff 0.0 | 7 | 0.070 / 0.234 | 0.25 / 0.75 |

- The MTP1 path is deterministic on its own (every repeat identical).
- Prefill and the first generated token are bit-identical to the MTP0 line
  at all three depths: the divergence is not in the prompt processing.
- From the second generated token on, the token logprobs differ by tens of
  millinats on average and up to 0.74 nats, and every fixture continuation
  diverges within 31 tokens at a near-tie. This is not summation-order
  noise on an otherwise identical computation; the two-row verification
  forward (M=2 GEMMs, the GDN spec-decode kernel, and whatever the MoE
  router does with a two-token batch) computes materially different
  logits from single-row decode for the same prefix.
- The A81/A83 short rows and quality cases matched the MTP0 line only
  because those prompts are peaky; the probe's depth-8 case diverges after
  31 tokens. The A81 result note's "bit-exact at short context" is
  therefore too strong and is corrected there.

## Reading

MTP1 on Flash-Next is a different function from the target model, at every
depth, by an amount that flips near-ties within a few dozen tokens. Under
the lab's lossless standard it cannot be promoted in any context length
until the verification step reproduces single-row decode. Because the
first step is exact and the difference appears only once the two-row step
runs, the next diagnostic is kernel-level and offline: feed one recurrent
state and two tokens to `gdn_attention_spec_decode` and to two sequential
`gdn_attention` steps and compare (the A1 repeat gate already drives these
ops), and compare the tuned MoE kernel and the oneDNN GEMMs at M=2 against
two M=1 calls. Whichever differs first is where the serial-exact treatment
(the 27B lane's R38/R50 pattern) goes.

Data: [`probe`](../data/20260903-tp4-mtp1-a84-logprob-probe.json),
[`comparison`](../data/20260903-tp4-mtp1-a84-vs-mtp0-a76-logprob-comparison.json).
