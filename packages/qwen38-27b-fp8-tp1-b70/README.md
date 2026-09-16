# Run Qwen3.8 27B official FP8 on one B70

The official Qwen FP8 weights on **one Intel Arc Pro B70 (32 GiB)**, one user,
with the model's own MTP draft at depth 5. Every answer is checked by the full
FP8 model, and outputs are identical to running without MTP.

| Profile | Context | Writing speed | Prompt reading (2K / 12K input) |
| --- | ---: | ---: | --- |
| `recommended` | 13,824 tokens | **53.5 tok/s** | 2,025 / 1,987 tok/s |
| `no-quantization` (full-precision draft head) | 12,544 tokens | 51.6 tok/s | 2,010 / 1,981 tok/s |

Graphs and every measured point are on the
[details page](https://neural.download/models/qwen38-27b-fp8-vllm-tp1-b70.html).
How it was built and tested: [recipe](../../repro/qwen38-27b-fp8-vllm-tp1-b70/README.md).

## What you need

- Linux with working Intel GPU drivers, Docker and Python 3
- One B70 not used by anything else, 16 GiB host RAM, about 60 GiB of disk
- The model: `Qwen/Qwen3.8-27B-FP8` at revision `017b9c7af6b5689d5dd426a76e0bc077eb5ca20a`

## Start

```bash
MODEL_DIR=/path/qwen3.8-27b-fp8 packages/qwen38-27b-fp8-tp1-b70/scripts/download-model.sh
MODEL_DIR=/path/qwen3.8-27b-fp8 packages/qwen38-27b-fp8-tp1-b70/scripts/verify.sh
docker pull ghcr.io/steveseguin/vllm-openai-xpu-qwen38-int4@sha256:eb8165070409959c9ce4ba4c605ebaf2a39f82ce6b755e408241ab85b08b1e04
python3 packages/qwen38-27b-fp8-tp1-b70/scripts/serve.py start --model-dir /path/qwen3.8-27b-fp8 --state-dir /path/fp8-one-card-session
```

The download and verify steps check the pinned revision, every file size and
every SHA-256, so a pass means the exact bytes these measurements used.

Add `--profile no-quantization` for the full-precision draft head, or `--gpu 1`
to use the second card. Startup takes several minutes; wait for `Ready`.

## Use and stop

```bash
curl -s http://127.0.0.1:18130/v1/chat/completions -H 'Content-Type: application/json' \
  -d '{"model":"qwen38-27b-fp8","messages":[{"role":"user","content":"Say hello in five words."}],"max_tokens":64,"chat_template_kwargs":{"enable_thinking":false}}'
python3 packages/qwen38-27b-fp8-tp1-b70/scripts/serve.py status --state-dir /path/fp8-one-card-session
python3 packages/qwen38-27b-fp8-tp1-b70/scripts/serve.py stop --state-dir /path/fp8-one-card-session
```

Send one request at a time. The context limit covers the prompt, chat history
and the answer.

## Good to know

- The input word table (2.4 GiB) is kept in host memory so the model, its draft
  and the cache fit on one card; lookups are exact.
- The `recommended` profile scores draft guesses with a small INT4 copy of
  the output layer. The FP8 model still checks every token at full precision, so
  answers are unchanged. `no-quantization` avoids that copy at a small speed cost.
- **Replayed from a fresh download:** on September 16 the steps above were run
  from a new anonymous download of this repository on the lab host, reusing only
  the verified model files and the Docker layer cache: model verify, image pull,
  start, strict suite 12/12 identical to no-MTP at 53.497 tok/s, clean stop.
- Not yet tested: a machine without Intel drivers, Docker or the model already
  in place, and more than one user at a time.
