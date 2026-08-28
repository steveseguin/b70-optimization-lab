# TP4 MTP2 active-16K scheduler-32 attempt 2 preregistration

Date: 2026-08-28

## Purpose and boundary

Attempt 1 used the current source/model identity, 40 exact KV blocks, MTP2,
`max_num_batched_tokens=64`, and the default 300-second execute-model response
deadline. It booted cleanly and admitted the exact request, then ended at 3,200
computed prompt tokens with zero output after the response deadline. Its teardown
also failed the card-event postflight. It remains a Grade-D bounded negative with
no capability, speed, quality, parity, or deployment credit.

This is the sole material-treatment follow-up. It halves the scheduler work
quantum from 64 to 32 tokens, which also makes the derived
`max_num_scheduled_tokens` 32. It does not raise the runtime response deadline:
the source assertion and run identity freeze it at the default 300 seconds. The
model, model revision, runtime and kernel commits, stage, TP4/EP4 topology,
MTP2 configuration, exact 40-block cache budget, request, harness, comparator,
and all gates are unchanged.

This diagnostic is Grade D only. It cannot replace, reduce, or qualify the
protected <=8K quality-certified rows or the protected TP4 MTP0 20.72717637199404
tok/s result. It cannot create speed, quality, deployment, curve, headline, or
LocalMaxxing credit.

## Frozen identity

- Model: `/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8`
- Model revision: `bcd9f01ddc9cff2316eb84281bebcd5b058bddce`
- vLLM: `1372c62d975c554f4b465c8299bc5f3295301ceb`
- vLLM XPU kernels: `ad25aa9f69a2171612b9c6b83dfa82c69559f9e4`
- Runtime stage build: `2f829747503c77d4814834dffd0840fb1dd9f75a`
- TP/EP: 4/4, eager, one sequence, no async scheduling, no prefix cache
- MTP: 2 draft positions; `MTP_EXACT=0`
- Capacity: 16,512 tokens, exact request p16,384/o128, cached tokens must be 0
- Cache: 470,712,320 bytes, exactly 40 GPU blocks
- Scheduler treatment: max batched 32, derived max scheduled 32
- Runtime execute-model response deadline: default 300 seconds
- Supervisor lifecycle: 4,200 seconds
- Client request/outer bounds: 2,400/2,410 seconds
- Pre-request lifecycle gate: at least 2,900 seconds must remain
- Port: 19683
- Attempt: 2 under the unchanged `qwen38-flash-next-fp8-tp4-ep4-eager-mtp2-16512-r1` campaign
- Comparator: the current-runtime TP4 MTP0 p16,384/o128 attempt-2 receipt,
  full-file SHA-256 `214219cb8450df670d433cc6cada53a441853b14c4122ecd2c2cb8ba25c77d56`,
  output-token SHA-256 `5706b3445c50abaaedacae0e5f52739856300701374126c23d610367c1dd1d39`

## Mandatory preconditions

The launcher must pass its fresh four-rank XCCL collective preflight after the
attempt-1 reset events. A preflight failure means no request and no new matrix
credit. Before launch, the packet must also prove clean unique paths, an unused
port, idle cards, exact source heads, exact model/stage inputs, frozen script
hashes, and a clean repository state containing the committed preregistration.

## Frozen outcome interpretation

1. If the request completes, all 25 exact-depth checks pass, usage is exactly
   p16,384/o128/cache0, all MTP2 counter identities pass, comparator parity is
   recorded, and postflight is clean: record one Grade-D scheduler-32 capability
   cell and stop. Do not repeat.
2. If the generic and counter gates pass but output differs from the frozen MTP0
   comparator: record Grade-D quarantine with the first divergence and stop.
3. If completion occurs but a counter, evidence, postflight, or card gate fails:
   grant no capability credit and hard-stop the tranche.
4. If the unchanged 300-second runtime deadline recurs, or any request/lifecycle
   bound ends with zero output: record a bounded negative and the computed-token
   boundary relative to attempt 1's 3,200. Stop; do not try scheduler 16.
5. If the 2,400-second client deadline ends: record a bounded negative and stop.
6. If the fresh collective preflight fails: do not send the request and grant no
   matrix credit.
7. Any B70-addressed reset/fault event fails postflight and hard-stops the tranche.

There is no timeout-only retry, no response-deadline increase, no scheduler-16
follow-up, no MTP1 launch, and no second scheduler-32 repetition in this tranche.

## Frozen scripts

- scheduler-32 base launcher:
  `66530afb827d0129b85ebec89e21d5ce7361b315ab7bbda0238043ed0fb730c7`
- attempt-2 wrapper:
  `499966258244a4724c7e70572a4bbb00a586f5fe2a525890b580f5452b1636fc`
- attempt-2 supervisor:
  `8f3f778f1005daf03d83515d0b7931bf3c365da638a578d08469490e7a48d953`
- attempt-2 client:
  `e7715a6797a469f5ab53ef3ca5af9dd0b32bb4a4ce96018325a54f9c81def5d9`

The dependency order is base -> wrapper -> supervisor -> client. Any edit changes
the applicable hash and requires updating every downstream binding and this note
before execution.
