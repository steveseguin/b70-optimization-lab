# Run Qwen3.8 27B official FP8 on one B70

The official Qwen FP8 weights on **one Intel Arc Pro B70 (32 GiB)**, one user,
with the model's own MTP draft at depth 5. Every answer is checked by the full
FP8 model, and outputs are identical to running without MTP. Since September 17 the
launcher keeps one copy of the model's recurrent state per request instead of six,
which is what makes 32K of context fit on the card.

| Profile | Context | Writing speed | Prompt reading (2K / 8K / 16K input) |
| --- | ---: | ---: | --- |
| `recommended` | 32,768 tokens | **54.3 tok/s** | 2,031 / 2,019 / 1,935 tok/s |
| `max-context` (0.983 of GPU memory) | 40,960 tokens | 54.3 tok/s | 2,024 / 2,011 / 1,930 tok/s |
| `no-quantization` (full-precision draft head) | 28,672 tokens | 52.4 tok/s | 2,014 / 2,008 / 1,927 tok/s |

Graphs and every measured point are on the
[details page](https://neural.download/models/qwen38-27b-fp8-vllm-tp1-b70.html). LocalMaxxing:
[`cmu5wc2e50804lq01r0br2i5p`](https://www.localmaxxing.com/runs/cmu5wc2e50804lq01r0br2i5p) (54.33 tok/s, approved September 17;
the 24,576-token recipe's [`cmu53h4l407o3lq01od0vwjrr`](https://www.localmaxxing.com/runs/cmu53h4l407o3lq01od0vwjrr), 53.43 tok/s, stands as history).
How it was built and tested: [recipe](../../repro/qwen38-27b-fp8-vllm-tp1-b70/README.md).

## What you need

- Linux with working Intel GPU drivers, Docker and Python 3
- One B70 not used by anything else, 16 GiB host RAM, about 60 GiB of disk
- The model: `Qwen/Qwen3.8-27B-FP8` at revision `017b9c7af6b5689d5dd426a76e0bc077eb5ca20a`

## Start

```bash
MODEL_DIR=/path/qwen3.8-27b-fp8 packages/qwen38-27b-fp8-tp1-b70/scripts/download-model.sh
MODEL_DIR=/path/qwen3.8-27b-fp8 packages/qwen38-27b-fp8-tp1-b70/scripts/verify.sh
docker pull ghcr.io/steveseguin/vllm-openai-xpu-qwen38-int4@sha256:7baa32bd3a4623e93ace18b369e366951fb4b618b17927450bbd9cce15cc4dc7
python3 packages/qwen38-27b-fp8-tp1-b70/scripts/serve.py start --model-dir /path/qwen3.8-27b-fp8 --state-dir /path/fp8-one-card-session
```

The download and verify steps check the pinned revision, every file size and
every SHA-256, so a pass means the exact bytes these measurements used.

Add `--profile max-context` for 40,960 tokens (it uses 0.983 of the card's memory instead of 0.975, so it has
less headroom), `--profile no-quantization` for the full-precision draft head, or `--gpu 1` to use the second card. Startup takes several minutes; wait for `Ready`.

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
  answers are unchanged. `no-quantization` avoids that copy at a small speed cost. Every profile was verified through
  this launcher on two fresh servers (12/12 identical to no MTP, 64 prompts back to back, 2K-16K prompts).
- **32,768 tokens of context (September 17, afternoon):** draft decoding used to keep six copies of the model's
  recurrent state per request (one per draft position, 0.94 GiB at depth 5). The R311b image adds a kernel that keeps
  one copy and replays the accepted draft tokens on the next step instead
  ([overlay](overlays/b70_gdn_checkpoint.py), [design](../../experiments/qwen38-27b-b70/notes/2026-09-17-gdn-single-checkpoint-plan.md));
  the KV budget goes from 26,178 to 40,140 tokens at the same memory setting, and the speed is unchanged. Two fresh
  servers at this setting: 54.36 / 54.29 tok/s, 12/12 identical to no MTP, 64 prompts back to back plus queued passes
  identical, 2K/8K/16K prompts identical, chat quality and a 21-request logprob replay identical
  ([receipts](../../experiments/qwen38-27b-b70/data/2026-09-17-fp8-onecard-32k/)). The max-context (40,960) and
  no-quantization (28,672) profiles passed the same strict, back-to-back and 2K-16K checks through this launcher.
- **24,576 tokens of context (September 17, morning):** the launcher reads prompts in 2,048-token chunks instead of
  4,096, which frees 0.35 GiB of GPU memory. Two fresh servers at that setting: 53.43 / 53.43 tok/s, every gate exact.
- **Both profiles passed the 64-prompt back-to-back test** against a no-MTP server (September 16-17), the check
  that catches rare wrong first tokens in draft decoding.
- **Replayed from a fresh download:** on September 16 the steps above were run
  from a new anonymous download of this repository on the lab host, reusing only
  the verified model files and the Docker layer cache: model verify, image pull,
  start, strict suite 12/12 identical to no-MTP at 53.497 tok/s (13,824-token profile), clean stop.
- Not yet tested: a machine without Intel drivers, Docker or the model already
  in place, and more than one user at a time.
