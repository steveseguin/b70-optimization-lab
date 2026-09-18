# Run Qwen3.8 27B official FP8 on one B70

The official Qwen FP8 weights on **one Intel Arc Pro B70 (32 GiB)**, one user,
with the model's own MTP draft at depth 5. Every answer is checked by the full
FP8 model, and outputs are identical to running without MTP. Since September 17 the
launcher keeps one copy of the model's recurrent state per request instead of six,
which is what makes 32K of context fit on the card. Since September 18 it also checks
the draft's five guesses in one pass over the cache instead of five separate passes,
which is worth 10-17% more writing speed after a long prompt and changes no output.

| Profile | Context | Writing speed | Prompt reading (2K / 8K / 16K input) |
| --- | ---: | ---: | --- |
| `recommended` | 32,768 tokens | **54.2 tok/s** | 2,030 / 2,020 / 1,938 tok/s |
| `max-context` (0.983 of GPU memory) | 40,960 tokens | 54.3 tok/s | 2,031 / 2,020 / 1,936 tok/s |
| `no-quantization` (full-precision draft head) | 28,672 tokens | 52.4 tok/s | 2,015 / 2,012 / 1,930 tok/s |

Every row was measured through this launcher on the pinned image on September 18
([receipts](../../experiments/qwen38-27b-b70/data/2026-09-18-fp8-onecard-r312d/)).

Graphs and every measured point are on the
[details page](https://neural.download/models/qwen38-27b-fp8-vllm-tp1-b70.html). LocalMaxxing:
[`cmu5wc2e50804lq01r0br2i5p`](https://www.localmaxxing.com/runs/cmu5wc2e50804lq01r0br2i5p) (54.33 tok/s, approved September 17
on the R311b image; the 24,576-token recipe's [`cmu53h4l407o3lq01od0vwjrr`](https://www.localmaxxing.com/runs/cmu53h4l407o3lq01od0vwjrr),
53.43 tok/s, stands as history). The R312d-c payload that supersedes it is built and queued, not submitted, until the image is pushed.
How it was built and tested: [recipe](../../repro/qwen38-27b-fp8-vllm-tp1-b70/README.md).

## What you need

- Linux with working Intel GPU drivers, Docker and Python 3
- One B70 not used by anything else, 16 GiB host RAM, about 60 GiB of disk
- The model: `Qwen/Qwen3.8-27B-FP8` at revision `017b9c7af6b5689d5dd426a76e0bc077eb5ca20a`

## Start

```bash
MODEL_DIR=/path/qwen3.8-27b-fp8 packages/qwen38-27b-fp8-tp1-b70/scripts/download-model.sh
MODEL_DIR=/path/qwen3.8-27b-fp8 packages/qwen38-27b-fp8-tp1-b70/scripts/verify.sh
docker pull ghcr.io/steveseguin/vllm-openai-xpu-qwen38-int4@sha256:ea61e69834d02b4abfe435eaaf56b2eda7b7b7c5ac78fffa3740779d8f27353a
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

- **Faster after a long prompt (September 18, R312d-c image):** checking the draft's guesses used to issue one
  attention call per guessed position, each re-reading the whole cache; the new kernel reads the cache once and
  computes all the rows together ([overlay](overlays/b70_fa_multiq.py)). Every row is still computed with exactly the
  arithmetic a single token uses, so nothing about the answers changes -- and that was measured, not assumed. Through
  this launcher on a fresh server the strict suite was 12/12 identical to no MTP twice (54.24 / 54.01 tok/s), the
  64-prompt test 64/64 three times, the 2K/8K/16K screen exact, the 2,048-30,720-token long corpus exact in all three
  content types, the chat quality suite and the 21-request replay exact
  ([receipts](../../experiments/qwen38-27b-b70/data/2026-09-18-fp8-onecard-r312d/); the earlier research-launcher run
  of the same image is [here](../../experiments/qwen38-27b-b70/data/2026-09-18-fp8-lc4/)). Writing speed right after a
  prompt, against the same package on the R311b image:

  | Prompt | 2,048 | 8,192 | 16,384 | 24,576 | 30,720 |
  | --- | ---: | ---: | ---: | ---: | ---: |
  | R311b | 59.2 | 76.9 | 65.8 | 39.8 | 37.5 |
  | **R312d-c** | **59.2** | **80.0** | **72.4** | **45.5** | **44.0** |
  | Change | 0% | +4% | +10% | +14% | +17% |

  All in tokens/s, median across code, documentation and prose, two repeats each. Short prompts stay on the old
  per-guess path on purpose (`B70_FA_MULTIQ_MIN_K=4096`): below about 4,000 tokens of cache the one-pass kernel
  measured 1-2% slower, which is why the 2,048 row is unchanged. The by-content-type numbers at 30,720 tokens: code
  54.6 to 63.4, documentation 28.7 to 33.5, prose 37.5 to 44.0 tok/s.
- **Which image, and how it was built.** The pinned runtime is
  `sha256:ea61e69834d02b4abfe435eaaf56b2eda7b7b7c5ac78fffa3740779d8f27353a`, published as
  `ghcr.io/steveseguin/vllm-openai-xpu-qwen38-int4:r312d-fp8-tp1-20260918`. **The registry digest is verified after the
  push** (`experiments/qwen38-27b-b70/docker/rebase-v0290/publish-r312d-image-ghcr.sh`, run by the repository owner);
  on the lab host, which uses Docker's containerd store, the registry digest is the same value as the local image id,
  as it was for R311b. The source-build route is four steps on top of the public R310 image:
  R310 -> **r311** (`Dockerfile.r311-gdn-checkpoint`, the single-checkpoint GDN op) -> **r312c**
  (`Dockerfile.r312c-multiq` with `build-kernels-0.1.14.1-r312c-multiq.sh`, which adds `paged_decode_multiq` to
  `_xpu_C` and leaves the upstream flash-attention library untouched) -> **r312d-c**
  (`Dockerfile.r312d-multiq` with `build-kernels-0.1.14.1-r312d-multiq-toolchain.sh VARIANT=c`, which rebuilds only
  `libattn_multiq_kernels_xe_2.so`). The last step exists because of one rule: **a kernel rebuild must use the
  `CUTLASS_REVISION` the kernel's own `CMakeLists.txt` pins** -- `87f6850` for vllm-xpu-kernels 0.1.14.1, with DPC++
  2026.0.0, IGC 2.34.4 and ocloc 26.18. Built against the older `cd76379` the same kernel is off by 7.6e-6 on 8 of 22
  census cases; built against the pinned revision it is bit-exact on all 22
  ([census](../../experiments/qwen38-27b-b70/data/2026-09-18-fa-multiq-census/)).
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
  Long prompts, same evening: with an unrepeated corpus the `recommended` profile reproduced the no-MTP
  continuations token for token after 24,576- and 30,720-token prompts, and `max-context` after 36,864-token ones
  (three content types, two repeats each; [probe receipts](../../experiments/qwen38-27b-b70/data/2026-09-17-fp8-probe1/)).
  Writing speed right after a 24K+ prompt was about 38-40 tok/s on that image (66 after 16K; the no-MTP server
  writes 18); the September 18 kernel raises those to 45 and 72 -- see the first item above.
- **24,576 tokens of context (September 17, morning):** the launcher reads prompts in 2,048-token chunks instead of
  4,096, which frees 0.35 GiB of GPU memory. Two fresh servers at that setting: 53.43 / 53.43 tok/s, every gate exact.
- **Both profiles passed the 64-prompt back-to-back test** against a no-MTP server (September 16-17), the check
  that catches rare wrong first tokens in draft decoding.
- **Replayed from a fresh download:** on September 16 the steps above were run
  from a new anonymous download of this repository on the lab host, reusing only
  the verified model files and the Docker layer cache: model verify, image pull,
  start, strict suite 12/12 identical to no-MTP at 53.497 tok/s (13,824-token profile), clean stop.
- **All three profiles accepted on this image (September 18, 05:02-05:58 UTC).** The
  [acceptance campaign](../../experiments/qwen38-27b-b70/scripts/run-20260918-fp8-onecard-r312d-campaign.py) started,
  measured and stopped each profile through this launcher on the pinned image: `recommended` 12/12 identical to no MTP
  twice (54.24 / 54.01 tok/s) plus the ladder, both context screens, quality and the logprob replay; `max-context`
  12/12 at 54.32; `no-quantization` 12/12 at 52.42; ladders 64/64 and the 2K/8K/16K screen exact on all three
  ([receipts](../../experiments/qwen38-27b-b70/data/2026-09-18-fp8-onecard-r312d/)).
- Not yet tested: a machine without Intel drivers, Docker or the model already
  in place, and more than one user at a time. The image is also not in the registry yet, so the `docker pull` above
  works only where it was built; it is pushed as `r312d-fp8-tp1-20260918` by the repository owner.
