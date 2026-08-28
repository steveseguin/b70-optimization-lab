# Qwen3.8 Flash-Next FP8 TP4 MTP2 active-16K preregistration

Date: 2026-08-28

## Question

Can the current-source TP4/EP4 eager-text identity complete one exact
p16384/o128 request with MTP2, positive and internally consistent speculative
counters, and a clean owned teardown? The frozen current-source MTP0 active-16K
output is used only as a token-parity comparator.

This is one bounded matrix-classification arm. It cannot earn speed, curve,
semantic-quality, deployment, or headline credit. No repeat is authorized.

## Frozen identity

- model: `/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8`;
- model revision: `bcd9f01ddc9cff2316eb84281bebcd5b058bddce`;
- vLLM source: `1372c62d975c554f4b465c8299bc5f3295301ceb`;
- kernel source: `ad25aa9f69a2171612b9c6b83dfa82c69559f9e4`;
- staged runtime build: `2f829747503c77d4814834dffd0840fb1dd9f75a`;
- TP4/EP4, eager, text, MTP2, automatic KV, prefix caching off;
- max model length 16,512, max sequences 1, max batched tokens 64;
- fixed cache 470,712,320 bytes / exactly 40 blocks;
- required reported cache capacity at least 16,512 tokens;
- selective UVA placement is unchanged at 12.25 GiB per rank;
- attempt 1, port 19680, fresh run/cache/compile/RPC paths.

The 40-block budget follows the observed current-source MTP2 relationship
`ceil(max_model_len / 832) + 13`: 33 blocks are the predicted admission floor
for 16,512, while 40 supplies bounded headroom. Each block is 11,767,808 bytes;
the server-reported capacity gate remains authoritative.

## Frozen request and comparator

- fixture SHA-256:
  `c44fccbaf600cc506d8ed0cc7357161057b86abc44469b611be71db97558061d`;
- harness SHA-256:
  `8f162c1ab9fde7e0daffed2c4f0d6ff061ad6076c5de716e36f3d883ab4a1067`;
- prompt-token SHA-256:
  `b7acffcd09d9466fd8382a72248f5447c59f4ee18572aff243ef29ee889883e7`;
- request-payload SHA-256:
  `b555e47c199a9166f23ba60520e6714a11fd8a31e36053db75c12863ac01c103`;
- current-source MTP0 reference receipt SHA-256:
  `214219cb8450df670d433cc6cada53a441853b14c4122ecd2c2cb8ba25c77d56`;
- current-source MTP0 output-token SHA-256:
  `5706b3445c50abaaedacae0e5f52739856300701374126c23d610367c1dd1d39`.

Exactly one deterministic request is allowed: 16,384 prompt tokens, 128 output
tokens, temperature zero, seed one, no truncation, no prefix-cache reuse, and a
length stop. Client request timeout is 2,400 seconds, the outer bound is 2,410
seconds, and the supervisor lifecycle bound is 3,600 seconds.

## Required gates

Before the request, require the exact runtime identity, four idle cards, exact
40-block / 470,712,320-byte cache admission, at least 16,512 reported capacity,
four exact selective-offload receipts, a live owned server, fresh paths, and no
pre-existing request artifacts.

The request must pass all 25 generic exact-depth checks with exact
16384/128/16512 usage, cached tokens zero, finish reason `length`, and exactly
128 returned token IDs. MTP2 deltas must be positive for drafts, draft tokens,
accepted tokens, and accepted positions zero and one. Draft tokens must equal
two times drafts, and the sum of accepted-position deltas must equal accepted
tokens.

The comparator must still verify its full-file and output-token hashes, its 25
generic gates, exact usage, cache-zero state, length stop, and 128-token shape.
Record parity and, on mismatch, the first zero-based divergent generated-token
index.

## Frozen interpretations

- Generic gates, counter gates, and parity pass: Grade-D quarantined capability;
  semantic and repeat qualification remain absent.
- Generic and counter gates pass but parity differs: Grade-D quarantined
  capability with the first divergence recorded; no semantic claim.
- Admission, identity, counter, evidence, request, timeout, lifecycle, or
  postflight failure: stop the tranche without retrying the request.
- Any B70-addressed reset, fatal, or timeout event: stop the tranche.
- Host events that identify only another device are disclosed and do not by
  themselves rewrite the model result.

## Frozen packet hashes

- MTP2 long-context base:
  `f276f933c6949b0236e0f013596ac91f5089c0a6777ab2cb1bac012a4f652386`;
- 40-block wrapper:
  `b1f4e323ebac726b1b8965044411930008ce7b7a69fd58141c58fe91cd279003`;
- supervisor:
  `61016f5f5eea2e5de49dca4375738729decf236b71ff75887342c1a809d1b8de`;
- client:
  `5ad37e955856b1d420d46e43a0dfc5c368d06d60767e9d6accd11eecd8c4b7c9`.

The arm may start only after syntax/hash checks, an exact-source and idle-host
preflight, a fresh-path check, and an independent read-only packet audit.

## Observed result

The frozen attempt admitted exactly 40 blocks / 470,712,320 bytes and reported
20,014 cache tokens. All four ranks loaded and recorded the required selective
offload receipt. The sole p16384/o128 request then stopped after 697.697 seconds
with 3,200 computed prompt tokens, no generated token, and one runtime
`sample_tokens` response timeout after five response-wait notices. Sixteen of
25 generic checks were true, but the overall completion gate failed; MTP
counters and parity remained unavailable. Client rc was 2, not an outer
request timeout.

The runtime began shutdown, after which the sealed host window recorded eight
card engine-reset records (two per card) and 40 card fault-response records.
That fails the frozen postflight rule and stops the 16K tranche without a
request retry. Supervisor rc was 70. The current host check found no listener,
owned model process, compile path, or RPC path, and the sealed postflight
snapshots show all four cards below 43 MiB.

The same window also contains 12 corrected Source-514 local-NVMe records, 13
corrected PCIe sections, and 14 RxErr log lines naming only `0000:01:00.0`;
they are separate from the card postflight failure. Resource cleanup is
currently complete, but discovery alone is not post-reset launch
qualification: require a new treatment and a fresh four-rank collective before
another model launch.

The 46-entry raw manifest verifies and has SHA-256
`fca3af5d66368c6319afaddb651a56975ed8440a37d96b27179d44de713fbc7f`.
Classify the cell as a Grade-D quarantined bounded negative with no speed,
curve, semantic-quality, deployment, or headline credit. Receipt:
`experiments/qwen38-flash-next-fp8-b70/data/20260828-tp4-mtp2-16512-attempt1-runtime-timeout-quarantine.json`.
