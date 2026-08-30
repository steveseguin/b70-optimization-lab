# Qwen3.8 Flash-Next FP8 TP4 MTP0 A11 API-logprob preregistration

Date: 2026-08-29
Status: frozen before GPU execution

## Purpose

A10 repeated the A7 exact-4K reliability failure: two byte-identical greedy,
cache-zero p4096/o128 requests passed every transport gate but returned
different token arrays. A9 remains the preferred Grade-C placement speed
screen, but it cannot be promoted as reliable or lossless.

A8 attempted to record raw greedy decisions inside each worker. The host
stopped during worker initialization before model load. That patch remains
preserved but is not reapplied. A11 instead uses the existing completion API's
generated-token logprob response. The server source, staged binaries, worker
initialization, and all serving selectors remain the same as A10.

## Frozen server identity

- model `Qwen/Qwen3.8-Flash-Next-FP8` revision
  `bcd9f01ddc9cff2316eb84281bebcd5b058bddce` from local NVMe;
- vLLM `e5137bfd8ca2ca718c4fd93d86d54bb843e2999b`;
- XPU-kernel source `ad25aa9f69a2171612b9c6b83dfa82c69559f9e4`;
- staged runtime build `2f829747503c77d4814834dffd0840fb1dd9f75a`;
- TP4/EP4, eager graph-off, MTP0, one sequence, 64 batched tokens;
- 4,352 configured tokens and 134,217,728 cache bytes;
- PLE-only UVA placement: 12,800,061,440 host bytes/rank, input embedding on
  device, and `--cpu-offload-gb 12.0`;
- prefix caching and async scheduling disabled;
- attempt 11, port 19683, fresh compile/cache/RPC/evidence roots.

No MoE table, graph, sampler selector, scheduling selector, placement selector,
or model code changes in this arm.

## Frozen diagnostic request and order

After source, artifact, four-card, XCCL, served-identity, capacity, and bounded
journal gates pass, send exactly four requests on one fresh server. Every
request uses the retained exact 4,096-token prompt with token-array SHA-256
`aedf2eb7...c76d0`, 128 output tokens, temperature zero, top-p one, seed one,
ignored EOS, no added special token, no prompt truncation, streaming token IDs,
and zero cache reuse.

The diagnostic-only additions are `logprobs=8` and
`return_tokens_as_token_ids=true`. The latter requires every returned score key
to be an exact `token_id:N` placeholder rather than ambiguous decoded text.
The frozen diagnostic request SHA-256 is
`3fb48f788ccee7337e7fbc9924ced628c419afd31dfa281846af747b287d44c1`.

Require each request to return exact 4096/128/4224 usage, zero cached tokens,
one length stop, 128 token IDs, 128 score rows, and a selected token equal to
the reported top-one token at every position. Stop after four requests even if
all outputs match or a divergent output appears earlier. Do not run the quality
battery, short speed rows, MTP, 16K, vision, or any other model request.

No timing from A11 is performance evidence. Asking for logprobs adds work and
changes request instrumentation, so this arm can receive mechanism evidence
only.

## Frozen interpretations

- If authority and non-authority arrays both appear and every selected token is
  its own top one, compare the first different generated position. Different
  top-one IDs there classify the failure as a changed greedy ranking before
  token selection, not a post-selection sampler substitution.
- Record the earliest top-eight ordering/value difference before the first
  selected-token difference. This is localization evidence, not proof of a
  particular layer or kernel.
- If a selected token differs from the reported top one, reject trace integrity
  and make no model-path inference.
- If all four arrays match, classify only this score-reporting/timing identity
  as repeat-stable. It does not erase A7/A10 or qualify the no-logprob recipe.
- Any transport failure, missing score row, nonzero cache reuse, owned residue,
  or B70-addressed event closes A11 without unchanged retry.

The next source treatment, if required, must be chosen from this evidence. MTP0
speed tuning may continue as research, but no result can be promoted as
reliable/lossless until the unchanged no-logprob exact-4K repeat passes on a
fresh server.

## Frozen artifacts

- launcher wrapper SHA-256:
  `955505783af6ec3fbfe884c3a0134561d52d0597bc7dc65a94436013a9cbd225`;
- generated launcher SHA-256:
  `e11c18122e8d6dcee99e4e624932f24a25a07c52f7a44d7b3ca6358d3abdf16e`;
- diagnostic client SHA-256:
  `56740bfb3662ce2674a367c9b43c2474379cc664b9d80da353117e99355eea07`;
- diagnostic Python helper SHA-256:
  `95a03d9c134168a2468957d7775bcb4e14df8fccb4d14ea9f596e99196edba4f`;
- helper tests SHA-256:
  `2d83b24a844661d57dd3bc1c0ffb5cc522cab2b10daa44e4bfe3ccf5d3c1f578`;
- supervisor wrapper SHA-256:
  `44d154df0dc163b9a46257e264ea34b5291803b1d6a892398bf8856b3fe4fd70`;
- generated supervisor SHA-256:
  `c17f18c9f24e0a2ae3425434925e9540e4c40e5bf9a8748c23041cbdcb7d3135`.

The helper passes four focused unit tests, Python compilation, Ruff check and
format, an inert no-network plan, Bash syntax checks, generated-source checks,
and diff validation.
