# Laguna target inline prefix 48 full exactness gate

Date: 2026-08-01 America/Toronto

Status: **closed negative on request 1; no score was run or authorized.**

## Candidate

The fixed-input prefix-48 candidate captures target gather slots 0–47 and
keeps slots 48–95 plus the embedding all-reduce eager. It passed two changing
400-token q=1 requests with target `98/97`, draft `14/13`, cache-zero behavior,
normal speculation, four-rank activation, and clean teardown. Prefix 49 failed,
and skipping only slot 48 while capturing the later slots also failed.

## Gate

Extend the existing evidence-preserving smoke runner with fail-closed choices
for 13 requests and 512 tokens. Defaults remain exactly two requests and 400
tokens. The full diagnostic must:

- run all 13 frozen prompts once in order at 512 output tokens;
- persist each complete raw response before its assertion;
- require every token prefix to match the canonical q=1 teacher;
- require `cached_tokens=0` and real, normally decaying DFlash speculation on
  every request;
- require target `98/97` and draft `14/13` capture/replay on all ranks;
- require the exact prefix-48 activation marker on all ranks; and
- stop cleanly with a passing post-idle snapshot.

The diagnostic emits no promoted throughput metric and cannot authorize a
submission. Any mismatch, runtime/device error, contract drift, or dirty
teardown closes prefix 48. A complete pass authorizes a separately
preregistered first cold score whose result must be reported whether it wins or
loses.

The model, draft, BF16 KV, width 12, DFlash depth 11, sampler, teacher, prompt
set, cache policy, verification, and production score accounting remain fixed.

## Result

Request 0 was fully exact for all 512 tokens with `cached_tokens=0` and normal
speculation. Request 1 returned 512 cache-zero tokens but diverged from its q=1
teacher at token 0. Target `98/97`, draft `14/13`, and four-rank prefix-48
activation were all exact; no runtime/device error occurred and teardown was
clean.

Artifact:
`/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-target-inline-prefix48-full-exactness-20260801T172528Z`.

This exposes a length/cross-request failure that the earlier two 400-token
requests did not cover. Prefix 48 is rejected and must not be scored.
