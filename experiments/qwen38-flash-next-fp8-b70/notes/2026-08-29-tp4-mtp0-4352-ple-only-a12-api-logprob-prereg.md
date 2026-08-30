# Qwen3.8 Flash-Next FP8 TP4 MTP0 A12 API-logprob retry

Date: 2026-08-29
Status: frozen before retry

A12 is the single corrected retry of the A11 client-format negative. It retains
the complete A11 preregistration, including the exact A10 server identity,
exact 4K prompt, four requests, top-eight score width, no performance credit,
and all frozen interpretations.

The sole behavior correction is in the diagnostic response parser. A streamed
completion delta may contain one or more integer token IDs. A12 accepts it only
when the `tokens`, `token_logprobs`, and `top_logprobs` arrays have exactly the
same nonzero length. It then validates each generated token separately: exact
`token_id:N` placeholder, selected score, top-score list, and selected-token
equals top-one. Empty, malformed, unequal, or missing arrays still fail closed.

Attempt 12 uses port 19684 and new compile, cache, RPC, run, and supervisor
roots. No A11 path is reused. No extra model request is authorized beyond the
same four exact-4K diagnostic rows.

Frozen artifacts:

- launcher wrapper SHA-256:
  `f2d652635bef135f59f3e5700ee0320ba3c2cff3986b3787f2445b3851408f66`;
- generated launcher SHA-256:
  `1a00a6575ba33e0aae4c0491e164d3e4cfdeb80d64e7068bb4e03779ffd441e2`;
- client wrapper SHA-256:
  `5756b9eb40ef9451a20be0d66c16c7ea9cf00f74ac8936cf8242b88f196988da`;
- generated client SHA-256:
  `8892b1c72b1240dc32d8696eb3cb36d35f75f554a8333fb9af74a07480e0e816`;
- corrected helper SHA-256:
  `7608299f95fbec2067011414ad12322f0fad56a621e0e63105f8964d57ca956f`;
- five-test helper suite SHA-256:
  `a54e0cc6c1c9b9d3f90714695f3273673c30c0a842d3e1f201ac15418c9bcb48`;
- supervisor wrapper SHA-256:
  `c7dbe6737fe9328468d57fc2d5157a1660163dce226cffb8a92f47f2ea70284f`;
- generated supervisor SHA-256:
  `e2957acf73d46954ca86f01028cc759ae965f0c56b8e6d8b2ea2100fa8df0627`.

The corrected helper passes five unit tests, Python compilation, Ruff check and
format, and its unchanged inert plan. All generated Bash sources pass syntax
and identity validation.
