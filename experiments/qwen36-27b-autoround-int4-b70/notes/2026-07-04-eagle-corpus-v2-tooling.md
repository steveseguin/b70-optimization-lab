# 2026-07-04 - EAGLE Corpus v2 Tooling Groundwork

## Classification

Preparation only. This is not a throughput result and must not be submitted to
LocalMaxxing.

The prior EAGLE1 endpoint attempt is closed-negative because the local draft
looked promising offline but failed endpoint quality with repeated-token
corruption. The likely problem is that the corpus and offline evaluator were too
narrow and did not preserve enough prompt metadata to expose family-specific
failures before endpoint testing.

## Changes

Updated `scripts/collect-qwen36-eagle-hidden-corpus.py`:

- added `--suite` so collection can use JSON prompt suites instead of only the
  old filler/completions prompt generator;
- added `--api-mode chat|completions`, defaulting to the old completions mode
  for backward compatibility;
- added `--request-extra-json` for request controls such as
  `{"chat_template_kwargs":{"enable_thinking":false}}`;
- added `--request-id-prefix` and sends `X-Request-Id` so hidden dump shards can
  be joined back to request metadata;
- records `prompt_id`, `family`, `suite_index`, prompt hash, response IDs, and
  original suite metadata in the collector summary.

Updated `scripts/build-qwen36-eagle-dataset-from-dump.py`:

- added repeatable `--metadata` input for collector summaries;
- copies request metadata into each saved `.pt` sample as `request_metadata`,
  plus top-level `prompt_id`, `family`, and `prompt_sha256`;
- records metadata coverage in the dataset summary.

Updated `scripts/evaluate-qwen36-eagle-draft-offline.py`:

- propagates `family` and `prompt_id` into sample rows and first-mismatch
  examples;
- adds `family_rows` with mean accepted tokens by prompt family.

## Verification

Passed:

```bash
python3 -m py_compile \
  scripts/collect-qwen36-eagle-hidden-corpus.py \
  scripts/build-qwen36-eagle-dataset-from-dump.py \
  scripts/evaluate-qwen36-eagle-draft-offline.py

/home/steve/.venvs/vllm-xpu/bin/python \
  scripts/collect-qwen36-eagle-hidden-corpus.py --help

/home/steve/.venvs/vllm-xpu/bin/python \
  scripts/build-qwen36-eagle-dataset-from-dump.py --help

/home/steve/.venvs/vllm-xpu/bin/python \
  scripts/evaluate-qwen36-eagle-draft-offline.py --help
```

Also ran a fake hidden-dump builder smoke under the XPU venv. It saved one
sample and verified `samples_with_metadata=1`, `family=test-family`, and
`prompt_id=test-prompt`.

Suite-load sanity for `calibration-suite-v1.json` passed:

- suite ID: `qwen36-27b-autoround-int4-b70-calibration-v1`;
- rows: `24`;
- first prompt ID: `ops-runbook`.

## Next EAGLE Step

If EAGLE work resumes, do not train on the old filler corpus. Use a non-final
chat-style corpus:

```bash
/home/steve/.venvs/vllm-xpu/bin/python scripts/collect-qwen36-eagle-hidden-corpus.py \
  --base-url http://127.0.0.1:<port> \
  --model qwen36-27b-int4-autoround \
  --tokenizer /mnt/fast-ai/llm-cache/hf/hub/models--webhie--Qwen3.6-27B-int4-AutoRound/snapshots/f5750c90b3776db658594df5fe8051098226dd8e \
  --suite experiments/qwen36-27b-autoround-int4-b70/calibration-suite-v1.json \
  --api-mode chat \
  --request-extra-json '{"chat_template_kwargs":{"enable_thinking":false}}' \
  --request-id-prefix qwen27-eagle-v2 \
  --output-tokens 160 \
  --out /mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/<run>/collector-summary.json
```

Then build the dataset with `--metadata <collector-summary.json>` and require
offline acceptance summaries by `family_rows` before any endpoint test.

Do not touch the fixed final realistic suite for EAGLE tuning until a held-out
calibration endpoint pass is clean.
