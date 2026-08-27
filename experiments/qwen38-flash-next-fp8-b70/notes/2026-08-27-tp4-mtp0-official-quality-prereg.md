# Qwen3.8 Flash-Next TP4 MTP0 official-quality preregistration

Date: 2026-08-27

## Purpose and boundary

This is a bounded model-quality arm, not a throughput benchmark. It adds no
timing rows and cannot replace or lower any existing decode result. The
published non-thinking MTP3 hero and the complete MTP0--MTP4 speed evidence
remain unchanged.

The existing deterministic `enable_thinking=false`, temperature-zero profile
is retained as the runtime-parity and context-integrity profile. This arm asks
a separate question: does the target-only model pass the prescribed short
quality set when served in its official thinking-enabled profile?

The run is fixed as TP4/EP4/eager/MTP0 with a 4,352-token model limit and a
192 MiB fixed KV-cache allocation. It uses the currently staged performance
runtime without changing model placement, graph mode, kernels, collectives, or
the known-good server flags. `--reasoning-parser qwen3` only separates
reasoning from the final response at the API layer; it does not change the
model weights or sampling implementation.

## Exact server identity

- campaign: `qwen38-flash-next-fp8-tp4-ep4-eager-mtp0-4352-r1`
- attempt: `2`
- API port: `19646`
- model: `/mnt/usb-models/llm-models/Qwen3.8-Flash-Next-FP8`
- model revision: `bcd9f01ddc9cff2316eb84281bebcd5b058bddce`
- vLLM checkout: `1372c62d975c554f4b465c8299bc5f3295301ceb`
- runtime stage:
  `/mnt/usb-models/qwen38-build/runtime-core-moe-negidguard-b70`
- TP/EP: `4/4`
- mode: eager; graph capture off
- MTP: `0`
- maximum model length: `4352`
- maximum sequences: `1`
- maximum batched tokens: `64`
- KV-cache bytes: `201326592`
- prefix caching: off
- async scheduling: off
- reasoning parser: `qwen3`
- diagnostics: none

The run and cache directories must be new and absent before launch:

```text
/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-eager-mtp0-4352-r1-attempt2
/mnt/usb-models/llm-runtime/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-eager-mtp0-4352-r1-attempt2
```

## Frozen evidence and source hashes

- sealed MTP0 exact-4K baseline:
  `/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-eager-mtp0-4352-r1-attempt1/quality-v2-short-and-4k.json`
- baseline SHA-256:
  `a458747f6c84b1adbfbf4dff77ab8c5ffabf5446a990fc6711a66ae1119389b4`
- base launcher SHA-256:
  `62b40c9268a665727ff3946a621e4fcd2db072ed0bd4595dde7a6a006083ccb7`
- fixed wrapper SHA-256:
  `c88b4ff973716d75c50ac8aa49ad5dd051b71f474b45f250a6014133e1bec912`
- deterministic quality helper SHA-256:
  `8e18afee22a0fda4b44583ca55e3a43aef5f86fe8387a1bd28c533d1534bd3de`
- official-quality helper SHA-256:
  `c3a63b8a456379e7c345a9efb8a55e6ae1db0dca94c0be3b7ba88478ce7eed95`
- model `config.json` SHA-256:
  `99c11efba4012d0f760f4e4831a8d6cafd845044e21d0aa9e6d9e70a15a90a8d`
- model weight index SHA-256:
  `0419e2c2dfbb925257d7409405433a793cf7ff7d96f3eba882a815ec6d9fe7a6`

## Door A: sealed non-thinking control

Before testing the official profile, replay the deterministic quality-v2 suite
against the sealed MTP0 baseline with:

- `chat_template_kwargs={"enable_thinking": false}`;
- 16 fixed-set repeats;
- requested long-context filler setting 4,372;
- an exact 4,096-server-token needle;
- prompt caching disabled and both reported cache counters zero.

Require all 26 baseline comparisons, 16/16 identical repeats with one hash,
the exact 4K needle, complete usage, and zero cached/created-cache tokens. The
helper exit code is expected to remain `1` because the target's known code
answer is substantively wrong. The corrected semantic interpretation is 6/7:
the target answers the logic case `Yes`, which is correct case-insensitively,
and answers the Python expression `30` rather than `14`.

Any new parity, repeat, context, usage, or cache failure stops the arm before
Door B.

## Door B: official thinking profile

Use the model's published thinking sampler without tuning:

```text
temperature=1.0
top_p=0.95
top_k=20
min_p=0.0
presence_penalty=0.0
repetition_penalty=1.0
reasoning_effort=xhigh
max_tokens=1024
enable_thinking=true
preserve_thinking=true
```

First run the frozen scout in this order:

1. code execution;
2. logic;
3. arithmetic;
4. exact phrase copy.

Use seeds `2026082701` through `2026082704`. Each response must expose
nonempty separated reasoning and final fields, end with `finish_reason=stop`,
have complete usage accounting and zero cache counters, and produce the
semantically correct final answer. Stop on the first wrong response. Treat an
output-limit finish as inconclusive rather than a quality failure.

If the scout passes, run all seven prescribed cases with the frozen seeds
`2026082711`, `2026082712`, and `2026082713`. Require 21/21 semantically correct
final answers with the same structural and cache requirements. The helper is
fail-fast and writes its state after every response.

No thinking-enabled 4K needle is authorized here because a 4,096-token prompt
under a 4,352-token limit leaves too little output room. The sealed
non-thinking needle remains the context-integrity evidence.

## Interpretation and next action

- Door A pass + Door B pass: target-only official-quality profile passes.
  Preserve the result, then preregister a deterministic MTP3-versus-MTP0
  thinking-correctness arm without timing.
- Door A pass + Door B wrong answer: preserve as a model-quality negative. Do
  not alter or retract the deterministic speed records.
- Door A pass + Door B output limit: preserve as inconclusive and design a
  separately preregistered larger-output/shorter-context quality arm.
- Door A failure: stop and classify the exact identity mismatch before making
  any code or performance change.

Any future thinking-speed result must report reasoning and final-answer tokens
and latency separately. It cannot silently replace the existing non-thinking
decode metric.
