# Flash-Next TP4 eager MTP0 fixed-vision attempt 1 preregistration

Date: 2026-08-28

## Purpose and credit boundary

Run the first bounded vision-enabled screen for only the current-runtime
TP4/EP4, eager, MTP0, active-context-0, automatic-KV, fixed-vision-fixture-v1
cell. The arm can earn at most Grade-C `lab-screened` capability and bounded
quality evidence after every server, client, health, and teardown gate passes.
It grants no decode, prefill, TTFT, deployment, graph, other-topology, other-MTP,
other-context, or other-modality credit and cannot replace or lower any prior
text result or speed.

No launch is part of packet construction. In particular, the supervisor must
refuse to start while `user@1000.service` remains failed after the preceding
host OOM.

## Frozen source and runtime identity

- checkpoint `/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8`, revision
  `bcd9f01ddc9cff2316eb84281bebcd5b058bddce`;
- vLLM `1372c62d975c554f4b465c8299bc5f3295301ceb`;
- XPU kernels `ad25aa9f69a2171612b9c6b83dfa82c69559f9e4`;
- staged runtime build `2f829747503c77d4814834dffd0840fb1dd9f75a`;
- TP4/EP4, all-gather/reduce-scatter, Triton MoE, eager, MTP0, no reasoning
  parser, `MAX_MODEL_LEN=512`, `MAX_NUM_BATCHED_TOKENS=64`, one sequence;
- the accepted selective UVA placement remains exactly the PLE n-gram and
  input embedding under the 12.25-GiB per-rank budget;
- fixed 201,326,592-byte KV cache, BLHNC, automatic KV dtype, 64-token blocks,
  prefix caching disabled;
- multimodal loading enabled (`language_model_only=false`), exact
  `{"image":1,"video":0}` per-prompt limits, processor cache 0 GiB, and
  encoder tensor-parallel mode `weights`;
- port `19676`; fresh campaign, run, cache, compile, RPC, state, and supervisor
  paths containing `qwen38-flash-next-fp8-tp4-ep4-eager-mtp0-vision-512-r1-attempt1`.

## Frozen packet hashes

| Artifact | SHA-256 |
|---|---|
| `tools/launch-tp4-ep4-eager-mtp0-vision-512-base.sh` | `f3aff8be5518a9d4694df8ff4e5486a42a0a366323f5917781b2b2053bf8b716` |
| `tools/launch-tp4-mtp0-current-vision-a1.sh` | `179499c7849f427a21e8ef0093b42eb7329cda76d174cde5cc3fa38f39110dfe` |
| `tools/run-tp4-mtp0-current-vision-a1-client.sh` | `da5d13a5b5ec0acdfbd6297b8b17e685abc20702a951d9c540f146e3af8e2db7` |
| `tools/supervise-tp4-mtp0-current-vision-a1.sh` | `6b542b7329de435b047c175eb601a61d0335f0674190e26fe8eb6b65c9eedd9f` |
| `tools/run-fixed-vision-fixture-v1.py` | `f84e7f02d98c611095b2bae9582fc1056c3e042969733d1ef4290910cd40e0a1` |
| `fixtures/fixed-vision-fixture-v1.json` | `395158995f300e53d4360b844bcbb8dffb2dd551eb0106f4d91200b9c7402226` |
| `fixtures/fixed_vision_fixture_v1.py` | `82bc70952db0b00368d7142569f239763d07075aed270b8b7fa14b1062066345` |
| `scripts/qwen38-text-quality-suite.py` | `8e18afee22a0fda4b44583ca55e3a43aef5f86fe8387a1bd28c533d1534bd3de` |

The fixed fixture regenerates byte-exact PNG SHA-256
`ffbac32956e25357b1a3985a8562da7f725dc1eb6c8f7845e73028f76553e207`.

## Ordered protocol

1. Require the active user manager, at least 110 GiB available RAM, 6 GiB free
   swap, 80 GiB free root space, fresh exact paths, clean source identities,
   four idle B70s, and the launcher's exact four-rank collective.
2. Start the exact vision-enabled server and require the model, placement,
   cache, modality-limit, processor-cache, and encoder-TP receipts.
3. On the same boot, run one exact text recovery request. Require `OK`, normal
   stop, exact served identity, `17/2/19` usage, and zero cache creation/reuse.
4. Run exactly the seven established deterministic semantic cases. Accept 7/7
   or the already disclosed 6/7 outcome whose sole miss is
   `code_execution=30`; require complete usage arithmetic and zero cache
   creation/reuse on every case.
5. Only after those text gates pass, run the committed fixture client: three
   grounded cases (OCR `B7X9`, right-square color `blue`, bottom-circle count
   `3`) repeated three times, exactly nine requests. Require HTTP 200, exact
   served identity, normal stop, exact answers and prompt-token counts, zero
   cache creation/reuse, and one request/answer/usage identity per repeat group.
6. Require health after request nine, then allow the exact client stop sentinel.
   The supervisor performs descendant-aware teardown and requires no listener,
   process group, compile path, RPC path, B70 event, OOM record, or `RxErr`, plus
   four rediscovered cards below 256 MiB.

The supervisor is bounded at 15,000 seconds, and the client refuses to start
unless at least 10,500 seconds remain. This admits the frozen 300-second text
recovery, 1,500-second semantic gate, 8,400-second vision-client bound, and
bounded HTTP/journal overhead even after a late healthy boot. The supervisor
samples RAM, swap, and swap I/O throughout. It stops the owned lifecycle if
available RAM falls below 8 GiB or free swap falls below 4 GiB. Each vision
request is bounded at 900 seconds, and any first failure stops later requests.

## Stop and interpretation rules

Stop without retry on any identity/hash/path/lock/collective/placement/cache
failure, server timeout, text recovery failure, unaccepted semantic result,
vision response or repeat failure, health failure, resource-floor breach,
host OOM, storage receiver event, B70 event, or dirty teardown. Preserve all
partial artifacts. A completed client with a dirty teardown remains diagnostic
only. Do not add a family cell or measurement until a separate closeout reads
the immutable result and supervisor evidence.
