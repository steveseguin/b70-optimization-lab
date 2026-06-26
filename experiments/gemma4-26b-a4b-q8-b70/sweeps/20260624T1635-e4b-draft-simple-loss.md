# 2026-06-24T1635 - E4B Draft-Simple Rejection

## Question

Can the local Gemma 4 E4B Q4_0 model act as a smaller external draft model for
fresh-response speculative decoding against the Gemma 4 26B A4B Q8 target?

This was worth screening because the project goal is fresh-response headline
throughput. Draft-model speculation is valid only if the draft can operate on a
new request without having seen the target response. This lane does not rely on
benchmark history or repeated-output continuation reuse.

## Tested Shape

- target: `unsloth/gemma-4-26B-A4B-it-GGUF`, `UD-Q8_K_XL`
- target path:
  `/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`
- draft: local Gemma 4 E4B Q4_0
- draft path:
  `/mnt/fast-ai/llm-models/gemma4-e4b-it-gguf/gemma-4-E4B-it-Q4_0.gguf`
- engine: llama.cpp SYCL/B70 build from
  `/home/steve/src/llama.cpp-gemma-record-stack/build-sycl-b70-aot-bmg-g31/bin/llama-server`
- speculation mode: `--spec-type draft-simple`
- fresh benchmark prompt: `filled-long`, p512/o512, `cached_tokens=0`

Common server args:

```bash
--parallel 1 --cache-ram 0 \
--spec-type draft-simple \
--spec-draft-model /mnt/fast-ai/llm-models/gemma4-e4b-it-gguf/gemma-4-E4B-it-Q4_0.gguf \
--spec-draft-device SYCL<gpu> --spec-draft-ngl all \
--spec-draft-type-k f16 --spec-draft-type-v f16 \
--no-spec-draft-backend-sampling \
--spec-draft-threads 32 --spec-draft-threads-batch 32 \
--ctx-checkpoints 0
```

Depth screen:

- GPU0: `--spec-draft-n-max 4`
- GPU1: `--spec-draft-n-max 8`
- GPU2: `--spec-draft-n-max 12`
- GPU3: `--spec-draft-n-max 16`

## Results

Completed result:

- label:
  `gemma4-q8-gpu0-draftsimple-e4bq40-n4-screen-20260624T162023Z`
- data:
  `data/gemma4-q8-gpu0-draftsimple-e4bq40-n4-screen-20260624T162023Z/`
- canary: `32/32` pass
- fresh row0 throughput after TTFT: `10.581 tok/s`
- fresh row0 wall throughput: `10.193 tok/s`
- TTFT: `1.841 s`
- prompt/completion: `588 / 512`

Interrupted lanes were clearly non-competitive before benchmark completion:

- GPU1 n8:
  `/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/gemma4-q8-gpu1-draftsimple-e4bq40-n8-screen-20260624T162025Z.server.log`
  showed short canary eval at roughly `0.19-0.71 tok/s`, with acceptance ranging
  from zero to partial.
- GPU2 n12:
  `/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/gemma4-q8-gpu2-draftsimple-e4bq40-n12-screen-20260624T162027Z.server.log`
  showed short canary eval at roughly `0.18-1.23 tok/s`, with unstable
  acceptance.
- GPU3 n16:
  `/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/gemma4-q8-gpu3-draftsimple-e4bq40-n16-screen-20260624T162029Z.server.log`
  showed short canary eval at roughly `0.18-1.39 tok/s`, with zero or partial
  acceptance.

## Decision

Reject E4B draft-simple for this target.

The draft model is far too slow in this server shape and acceptance is not good
enough to offset the extra draft execution. The completed n4 run is about
`9.3x` slower than the current valid Q8 MTP record (`98.617 tok/s` fresh row0),
and the deeper draft-simple lanes were worse during canary validation.

## Implication

Do not spend more sweeps on external E4B draft-simple without a materially
different engine implementation. The next useful work is source-level reduction
of the current MTP path's target/verifier or assistant-block cost, not changing
`n_max` or substituting this E4B draft in the existing draft-simple path.
