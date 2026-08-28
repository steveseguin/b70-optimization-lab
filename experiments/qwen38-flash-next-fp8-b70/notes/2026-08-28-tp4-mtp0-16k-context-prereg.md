# Qwen3.8 Flash-Next FP8 TP4 MTP0 active-16K preregistration

Date: 2026-08-28

Status: preregistered; no server or request has been started under this packet.

## Purpose and scope

This is one bounded coverage arm for the first missing deeper-context cell in
the TP4 eager-text tranche. It must not alter, replace, or reinterpret any
retained speed, quality, curve, packet, or matrix result. The measured rate, if
one is produced, is diagnostic only. A successful generic exact-depth request
is still quarantined at Grade D because no semantic 16K oracle or repeat gate
exists.

The existing hash-pinned launcher is not edited. A new long-context base is an
exact clone except for its fail-closed defaults and allowlist: MTP0,
`MAX_MODEL_LEN=16512`, and `KV_CACHE_MEMORY_BYTES=358465536` only.

## Frozen identity

- model: `/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8`
- model revision: `bcd9f01ddc9cff2316eb84281bebcd5b058bddce`
- vLLM source: `1372c62d975c554f4b465c8299bc5f3295301ceb`
- kernel source: `ad25aa9f69a2171612b9c6b83dfa82c69559f9e4`
- staged runtime build: `2f829747503c77d4814834dffd0840fb1dd9f75a`
- TP4, EP4, eager/graph-off, MTP0, BLHNC auto-KV
- BF16 activation; Triton MoE; allgather/reducescatter
- selective UVA offload: 12.25 GiB per rank for PLE n-gram embedding and token
  embedding, with exact four-rank `12.22` log receipts required
- max model length: 16,512 tokens
- max batched tokens: 64; max sequences: 1
- prefix caching off; async scheduling off; reasoning parser absent
- port: 19673; attempt: 1; fresh run/cache/compile/RPC/state paths only

## Frozen cache geometry

The current runtime's attention page is 832 tokens. The request needs
`ceil(16512 / 832) + 5 = 25` request blocks. One pool block is reserved as the
null block. The frozen pool uses 33 total blocks, 32 usable blocks, and
10,862,592 bytes per block:

`33 * 10,862,592 = 358,465,536 bytes` (341.859 MiB).

The client must observe exactly 33 blocks, exactly 358,465,536 configured cache
bytes, prefix caching false, and reported capacity at least 16,512 before it can
send the request. Any mismatch is a no-request stop; there is no adaptive
resize.

## Frozen request and gates

Exactly one `/v1/completions` request:

- fixture depth: 16,384 prompt token IDs
- output: exactly 128 tokens
- context capacity: 16,512
- temperature 0, top-p 1, seed 1, `ignore_eos=true`
- streaming token IDs; special-token insertion off; truncation absent
- prompt caching absent; cached token count must be zero
- exact usage must be 16,384 / 128 / 16,512
- finish reason must be `length`; exactly 128 returned token IDs
- all 25 generic exact-depth harness checks must pass
- inner request timeout: 1,800 seconds
- outer request timeout: 1,810 seconds
- full supervised lifecycle timeout: 3,000 seconds
- no repeat in this arm

Frozen inputs:

- harness SHA-256: `8f162c1ab9fde7e0daffed2c4f0d6ff061ad6076c5de716e36f3d883ab4a1067`
- fixture SHA-256: `c44fccbaf600cc506d8ed0cc7357161057b86abc44469b611be71db97558061d`
- prompt-token SHA-256: `b7acffcd09d9466fd8382a72248f5447c59f4ee18572aff243ef29ee889883e7`
- request-payload SHA-256: `b555e47c199a9166f23ba60520e6714a11fd8a31e36053db75c12863ac01c103`

## Frozen packet

- long-context base SHA-256: `d5ccc4d52220f7ef46f19202436edf56e0c40f125b1b807c84125df18093b5c1`
- wrapper SHA-256: `cfb9fbf83eca6f93eea1b4ff8142a2d34d3cd2ab44f3b9bc7445935a18088798`
- supervisor SHA-256: `85181bc89f55c67e70a0eff8b74485d05d9182fa4ab93ff1ef739e317ad79ee5`
- client SHA-256: `2133ab3033cbec5cc8af173bf61fedbced8f28d1677f838656e5f6b55158f7f1`

## Frozen interpretation and stop policy

If the single request passes every structural gate, freeze its output-token and
text hashes as the prospective same-runtime/current-source MTP0 16K comparator.
Classify the cell `quarantined-generic-exact-depth-only`, Grade D, with no speed,
quality, or deployment credit. Do not add its diagnostic rate to a headline,
featured result, or estimated curve.

An admission mismatch, request timeout, nonzero client exit, malformed or
incomplete receipt, dirty owned teardown, or B70-addressed reset/fatal event
stops this arm and all further GPU work pending classification/recovery. Corrected
PCIe events addressed only to the local NVMe endpoint are disclosed separately;
they are not relabeled as B70 events. No second request or 24K/32K launch is
authorized by this preregistration.
