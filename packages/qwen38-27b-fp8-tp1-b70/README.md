# Run Qwen3.8 27B official FP8 on one B70

The official Qwen FP8 weights on **one Intel Arc Pro B70 (32 GiB)**, one user,
with the model's own MTP draft at depth 5. Every answer is checked by the full
FP8 model, and outputs are identical to running without MTP. Since September 17 the
launcher keeps one copy of the model's recurrent state per request instead of six,
which is what makes 32K of context fit on the card. Since September 18 it also checks
the draft's five guesses in one pass over the cache instead of five separate passes,
which is worth 10-17% more writing speed after a long prompt and changes no output.

> **Status: candidate.** Accepted on the lab host on October 4. A fresh machine without Intel drivers, Docker
> or the model in place has not been tested. The [recipe](../../repro/qwen38-27b-fp8-vllm-tp1-b70/README.md) is
> the technical source of truth.

## Before you start

| Need | Tested with / required |
| --- | --- |
| OS | Linux. The October 4 acceptance host ran kernel `7.0.0-38`; its distribution, Intel driver package versions and Docker version were not recorded. No fresh-install test yet. |
| Driver stack | The Intel GPU kernel driver with a `/dev/dri/renderD*` node for the card. vLLM, PyTorch and the oneAPI runtime are inside the pinned container. |
| Docker | Docker, usable by your user without `sudo`; `serve.py` calls `docker` directly. |
| Tools | Python 3 (standard library only), `curl`, `fuser` (package `psmisc`) and permission to read the kernel log with `journalctl -k`. `serve.py start` checks the last two and refuses without them. `aria2c` is optional and speeds up the download. |
| Disk | About 60 GiB: 30.9 GB of model files plus the container image. |
| Host RAM | 16 GiB per the package manifest (20 GiB counting swap); the lab host that measured it has 15 GiB. The container is capped at 12 GiB with no swap. |
| GPU | One B70 that nothing else is using. Card 0 by default; `--gpu N` picks another. |
| Card memory | Measured on the lab's two-card host, which reported ECC off (32,656 MiB per card) when checked on 2026-08-30; the run receipts themselves do not record ECC state. With ECC on, a B70 shows about 28 GB instead of 32 GB, and this recipe was not tested that way. See [B70 ECC and usable VRAM](https://neural.download/learn/b70-ecc-and-vram.html). |

Background reading: [runtimes](https://neural.download/learn/runtimes.html) (why this one uses vLLM) and
[the MTP ladder](https://neural.download/learn/mtp-ladder.html) (what the draft depth does).

## Quick start

Clone this repository and run every command below from its root. Replace every `/path/...` with your own
absolute directories.

```bash
git clone https://github.com/steveseguin/b70-optimization-lab.git
cd b70-optimization-lab
```

### 1. Download and verify the model

```bash
MODEL_DIR=/path/qwen3.8-27b-fp8 packages/qwen38-27b-fp8-tp1-b70/scripts/download-model.sh
MODEL_DIR=/path/qwen3.8-27b-fp8 packages/qwen38-27b-fp8-tp1-b70/scripts/verify.sh
```

This fetches `Qwen/Qwen3.8-27B-FP8` at revision `017b9c7af6b5689d5dd426a76e0bc077eb5ca20a` (30.9 GB). Re-running
the download skips files that are already complete. The verify step checks the pinned revision, every file size
and every SHA-256, so a pass means the exact bytes these measurements used.

### 2. Get the runtime

```bash
docker pull ghcr.io/steveseguin/vllm-openai-xpu-qwen38-int4@sha256:ea61e69834d02b4abfe435eaaf56b2eda7b7b7c5ac78fffa3740779d8f27353a
```

The image name says INT4 because packages share a runtime; it serves the FP8 model.

### 3. Start the server

```bash
python3 packages/qwen38-27b-fp8-tp1-b70/scripts/serve.py start --model-dir /path/qwen3.8-27b-fp8 --state-dir /path/fp8-one-card-session
```

`--state-dir` must not exist yet: `serve.py` creates it, keeps the logs there, and refuses a directory that is
already there. Use a new one for every start. Add `--profile max-context` for 40,960 tokens (it uses 0.983 of the
card's memory instead of 0.975, so it has less headroom), `--profile no-quantization` for the full-precision draft
head, `--gpu 1` to use the second card, or `--port N` for another port (default 18130).

### 4. Wait until it is ready

The start command stays in the foreground. It loads the model, sends one warm-up request, then prints
`Ready: http://127.0.0.1:18130/v1`. On the lab host that took 132-149 seconds for every profile (October 3-4
receipts). It gives up after 30 minutes (`--startup-timeout`, in seconds). Leave this terminal open and use a second
one for the next steps.

### 5. Send a first request

```bash
curl -s http://127.0.0.1:18130/v1/chat/completions -H 'Content-Type: application/json' \
  -d '{"model":"qwen38-27b-fp8","messages":[{"role":"user","content":"Say hello in five words."}],"max_tokens":64,"chat_template_kwargs":{"enable_thinking":false}}'
```

From Python, after `pip install openai`:

```bash
python3 -c "from openai import OpenAI; c=OpenAI(base_url='http://127.0.0.1:18130/v1', api_key='none'); print(c.chat.completions.create(model='qwen38-27b-fp8', messages=[{'role':'user','content':'Say hello in five words.'}], max_tokens=64, extra_body={'chat_template_kwargs':{'enable_thinking':False}}).choices[0].message.content)"
```

Any other OpenAI-compatible app works the same way: base URL `http://127.0.0.1:18130/v1`, model `qwen38-27b-fp8`,
any API key.

### 6. Check status

```bash
python3 packages/qwen38-27b-fp8-tp1-b70/scripts/serve.py status --state-dir /path/fp8-one-card-session
```

It prints the state (`ready` while serving), whether the container runs, and whether the API answers.

### 7. Stop

```bash
python3 packages/qwen38-27b-fp8-tp1-b70/scripts/serve.py stop --state-dir /path/fp8-one-card-session
```

Ctrl+C in the start terminal does the same. The logs stay in the state directory; the next start needs a new
`--state-dir`.

## What you get

| Profile | Context | Writing speed | Prompt reading (2K / 8K / 16K input) |
| --- | ---: | ---: | --- |
| `recommended` | 32,768 tokens | **54.0 tok/s** | 2,031 / 2,023 / 1,939 tok/s |
| `max-context` (0.983 of GPU memory) | 40,960 tokens | 54.0 tok/s | 2,028 / 2,018 / 1,936 tok/s |
| `no-quantization` (full-precision draft head) | 28,672 tokens | 52.2 tok/s | 2,019 / 2,014 / 1,932 tok/s |

- **Speed:** every row was measured through this launcher on the pinned image on October 4, with the chunked-upload
  overlay the package now ships ([receipts](../../experiments/qwen38-27b-b70/data/2026-10-04-fp8-onecard-chunked-upload/);
  the October 3-4 run without it is within 0.1 % on every row:
  [receipts](../../experiments/qwen38-27b-b70/data/2026-10-03-fp8-onecard-noswap/); the
  first acceptance on this image, September 18, is within 0.7 % on every row:
  [receipts](../../experiments/qwen38-27b-b70/data/2026-09-18-fp8-onecard-r312d/)).
  Graphs and every measured point are on the
  [details page](https://neural.download/models/qwen38-27b-fp8-vllm-tp1-b70.html).
- **Quality:** answers are identical to the same model without MTP on every gate the receipts list (strict suite,
  64-prompt test, long prompts, chat quality). How it was built and tested:
  [recipe](../../repro/qwen38-27b-fp8-vllm-tp1-b70/README.md).
- **Use:** one request at a time. The context limit covers the prompt, chat history and the answer.
- **Not measured yet:** a machine without Intel drivers, Docker or the pinned model already present; multiple
  simultaneous users; contexts above 40,960 tokens on one card; prompt reading at a 512-token prompt on this profile.

## If it fails

`serve.py` never restarts or retries anything by itself. It prints `ERROR: ...` and stops.

- **`[Errno 17] File exists`**: the `--state-dir` is already there. Pick a new path.
- **`[Errno 98] Address already in use`**: something already listens on port 18130, often a server that is still
  running. Stop it (step 7) or pass `--port`.
- **`GPU index N is not available`**: `--gpu` names a card that is not there. Count the `renderD*` nodes in
  `/dev/dri`.
- **`The selected GPU is in use or ownership could not be checked`**: another process has the card open, or
  `fuser` is not installed. Stop the other GPU work first.
- **`Cannot read the kernel journal for fault monitoring`**: your user cannot run `journalctl -k`. Give it read
  access to the kernel log, then start again.
- **`Pull the pinned runtime first`** or **`The local image is not the pinned runtime`**: run step 2.
- **`Model directory does not exist`** or **`Model and serving state must be separate directories`**: check the
  two paths in step 3.
- **`New GPU fault detected. Halting this server`**: the kernel logged a GPU fault and `serve.py` stopped the
  server. Keep `kernel.log` and `server.log` from the state directory. The fault the lab saw at model load, and the
  overlay that avoids it (on by default), are described in
  [this note](../../experiments/qwen38-27b-b70/notes/2026-10-04-gpu-fault-mtp-start.md).
- **`Server exited (N); see server.log`** or **`Startup deadline reached`**: read `server.log` in the state
  directory. If the card ran out of memory, make sure nothing else uses it and check the card-memory row under
  [Before you start](#before-you-start); `max-context` leaves the least headroom.
- **`Container identity is not yet recorded; use Ctrl+C in the start terminal`**: `stop` ran before the container
  existed. Use Ctrl+C in the start terminal.
- **`verify.sh` reports a mismatch**: delete that file, download it again and re-run `verify.sh`. Do not start the
  server on unverified files.

## Details

### Good to know

- **LocalMaxxing records.** [`cmu6ytqyr0827lq01b76whp6d`](https://www.localmaxxing.com/runs/cmu6ytqyr0827lq01b76whp6d) (54.22 tok/s, approved
  September 18 on this image; it supersedes the R311b record
  [`cmu5wc2e50804lq01r0br2i5p`](https://www.localmaxxing.com/runs/cmu5wc2e50804lq01r0br2i5p), 54.33 tok/s, and the
  24,576-token recipe's [`cmu53h4l407o3lq01od0vwjrr`](https://www.localmaxxing.com/runs/cmu53h4l407o3lq01od0vwjrr),
  53.43 tok/s, both of which stand as history). The same payload was posted a second time by mistake and approved as
  `cmu6ytvxr082alq015dpjgiz4`; that record is an accidental duplicate, not a second measurement, and is withheld in
  [`results/localmaxxing-submissions.md`](../../results/localmaxxing-submissions.md) pending withdrawal.
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
  `ghcr.io/steveseguin/vllm-openai-xpu-qwen38-int4:r312d-fp8-tp1-20260918`. **The image was pushed on September 18 and
  the registry digest was checked against the pinned one: they match**
  (`experiments/qwen38-27b-b70/docker/rebase-v0290/publish-r312d-image-ghcr.sh`, run by the repository owner); on the
  lab host, which uses Docker's containerd store, the registry digest is the same value as the local image id, as it
  was for R311b. The source-build route is four steps on top of the public R310 image:
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
- **Accepted again on the current launcher (October 4, 01:08-02:06 UTC, kernel 7.0.0-38).** The launcher now starts the
  container with no swap allowance (`--memory-swap 12g`). The same campaign, all three profiles: `recommended` 12/12
  twice (54.06 / 54.03 tok/s), `max-context` 12/12 at 53.98, `no-quantization` 12/12 at 52.20, every other gate exact,
  no out-of-memory kill, 6.9-7.7 GiB of working memory against the 12 GiB limit
  ([receipts](../../experiments/qwen38-27b-b70/data/2026-10-03-fp8-onecard-noswap/)).
- **Accepted again with the chunked-upload overlay (October 4, 16:33-17:32 UTC).** The package now ships
  `overlays/b70_chunked_upload.py`, which moves the 2.5 GB output-layer and embedding weights between host and card in
  128 MiB pieces while the model loads. That avoids the driver path behind the model-load GPU fault
  ([what it is](../../experiments/qwen38-27b-b70/notes/2026-10-04-gpu-fault-mtp-start.md)); the bytes that arrive are
  the same and `serve.py` is unchanged. The same campaign, all three profiles: `recommended` 12/12 twice
  (54.05 / 54.03 tok/s), `max-context` 12/12 at 54.02, `no-quantization` 12/12 at 52.19, every other gate exact, no
  GPU fault ([receipts](../../experiments/qwen38-27b-b70/data/2026-10-04-fp8-onecard-chunked-upload/)).
  `B70_CHUNKED_UPLOAD=0` turns the overlay off.
- The image is public: it was pushed on September 18 as `r312d-fp8-tp1-20260918`, so the `docker pull` in step 2
  works anywhere. What is still untested is listed under [What you get](#what-you-get).
