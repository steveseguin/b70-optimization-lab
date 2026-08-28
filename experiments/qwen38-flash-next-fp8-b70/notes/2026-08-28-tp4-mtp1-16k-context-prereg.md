# Qwen3.8 Flash-Next FP8 TP4 MTP1 active-16K preregistration

Date: 2026-08-28

## Question

Can the normal current-source TP4/EP4 eager-text MTP1 identity complete one
exact p16384/o128 request with positive, internally consistent speculative
counters and a clean owned teardown? The frozen current-source MTP0 active-16K
output is used only as a token-parity comparator.

This is one bounded matrix-classification arm. It cannot earn speed, curve,
semantic-quality, deployment, or headline credit. No repeat is authorized.

## Frozen identity

- model: `/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8`;
- model revision: `bcd9f01ddc9cff2316eb84281bebcd5b058bddce`;
- vLLM source: `1372c62d975c554f4b465c8299bc5f3295301ceb`;
- kernel source: `ad25aa9f69a2171612b9c6b83dfa82c69559f9e4`;
- staged runtime build: `2f829747503c77d4814834dffd0840fb1dd9f75a`;
- normal MTP1 (`MTP=1`, `MTP_EXACT=0`), with exact-recurrent flags absent;
- TP4/EP4, eager, text, automatic KV/BLHNC, prefix caching off;
- max model length 16,512, max sequences 1, max batched tokens 64;
- fixed cache 470,712,320 bytes / exactly 40 blocks;
- required reported cache capacity at least 16,512 tokens;
- selective UVA placement unchanged at 12.25 GiB per rank;
- attempt 1, port 19681, fresh run/cache/compile/RPC paths.

The separate exact-recurrent MTP1 stage is excluded because it has component
evidence but no qualified endpoint result and would change two variables. The
40-block budget uses 11,767,808 bytes per block. Existing MTP1 capacities imply
a 30-block hard admission floor at 16,512 including the reserved null block;
40 supplies bounded headroom. The live reported-capacity gate is authoritative.

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

Before the request, require exact runtime identity, four idle cards, exact
40-block / 470,712,320-byte cache admission, at least 16,512 reported capacity,
four exact selective-offload receipts, a live owned server, fresh paths, and no
pre-existing request artifacts.

The request must pass all 25 generic checks with exact 16384/128/16512 usage,
cached tokens zero, finish reason `length`, and exactly 128 token IDs. MTP1
deltas must be positive for drafts, draft tokens, accepted tokens, and accepted
position zero. Draft tokens must equal drafts, and the accepted-position sum
must equal accepted tokens.

The comparator must verify its full-file and output-token hashes, 25 generic
gates, exact usage, cache-zero state, length stop, and 128-token shape. Record
parity and, on mismatch, the first zero-based divergent generated-token index.

## Frozen interpretations

- Generic gates, counter gates, and parity pass: Grade-D quarantined capability;
  semantic and repeat qualification remain absent.
- Generic and counter gates pass but parity differs: Grade-D quarantined
  capability with the first divergence recorded; no semantic claim.
- Admission, identity, counter, evidence, request, timeout, lifecycle, or
  postflight failure: stop the tranche without retrying the request.
- Any B70-addressed reset, fatal, or timeout event: stop the tranche.
- Host events naming only another device are disclosed and do not by themselves
  rewrite the model result.

## Frozen packet hashes

- MTP1 long-context base:
  `c2a0f30eec68f30298c69dc62634308fa6177b3e4ea2101ef9b89298fd933cbf`;
- 40-block wrapper:
  `7525b0c7a809a5c75a9ff9fa93661f906c9b745d5425d6fc0de9a02b5b181861`;
- supervisor:
  `4d02ea4793d404c4e2870bf757b6c88de6cc9ed9633b9fde44f237e19c667620`;
- client:
  `ad17e9176fc6f72bf82d958cb67acccd3011dbc87f16ebeba6297a15b4c638ef`.

The arm may start only after MTP2/16K fully stops, its evidence is sealed, all
locks/listeners are clear, all four cards are idle, syntax/hash/source/path
checks pass, and an independent read-only packet audit reports no blocker.
