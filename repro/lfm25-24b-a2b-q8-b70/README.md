# LFM2.5-24B-A2B Q8_0 on one Intel Arc Pro B70: 3.3x faster, same output

**One B70 runs Liquid AI's LFM2.5-24B-A2B (8-bit) at about 137 tokens per second for one user, up from 41.7 on
llama.cpp's plain SYCL path, reads prompts at about 1,700 tokens per second, and every generated token and every
log-probability is identical to that plain path.** Nothing is approximated: the speed comes from reading the weights in a faster memory layout and from doing
chains of small steps in one GPU kernel each, while doing the arithmetic in exactly the same order.

Status: **candidate** (measured on the lab's machine and rebuilt from this folder's public files; not yet replayed
on a freshly installed host). Measured 2026-10-15. The first version (published the same morning, about 111
tokens per second) is still available as `serve.sh unfused`. The evening update (v3) makes prompt reading 35-52%
faster than the afternoon build ([why](#reading-prompts)); generation and output are unchanged.

| | |
| --- | --- |
| Model | [LiquidAI/LFM2.5-24B-A2B-GGUF](https://huggingface.co/LiquidAI/LFM2.5-24B-A2B-GGUF) at revision `0912d33141f77e10705345a6732bfd83f0252fdc`, file `LFM2.5-24B-A2B-Q8_0.gguf` (25,493,732,640 bytes, SHA-256 `f09bf094a8a138c5b645598ca1abb6696a0fde26662d7af649b0713fdef330b6`) |
| What it is | a 24B mixture-of-experts model (64 experts, 4 used per token, about 2B parameters active), 40 blocks of which 10 are attention and 30 short convolutions; up to 128K context |
| Card | one Intel Arc Pro B70 (32 GiB); the model takes about 24 GiB, the rest holds the context |
| Runtime | upstream llama.cpp `c926ad09857517978575d6a74d225b463f7417a0` (tag b9769) plus one patch: [`llama-cpp-c926ad098-lfm25-24b-a2b-exact-fused-prefill-20261015.diff.gz.b64`](../../patches/lfm25-24b-a2b-q8-b70/llama-cpp-c926ad098-lfm25-24b-a2b-exact-fused-prefill-20261015.diff.gz.b64) (decoded SHA-256 `4b1a4cd014daafb74e2e44d2fc9c19e49d9d9e2626d1a29b998d919ce8d7af07`) |
| Compiler | Intel oneAPI Base Toolkit 2026.1 (icpx), SYCL ahead-of-time for the B70 (bmg-g31) |
| Host measured | AMD EPYC 9015, 15 GiB RAM, Ubuntu 24.04 with Linux 7.0 (xe driver) |

## Results

The lab's 12-prompt suite (six kinds of writing, two prompts each, 512 tokens each, greedy, prompt cache off, one
user). Speed is the median over the six kinds of each kind's median generation rate for tokens 1-100 after the
first token.

| Path | tok/s | Output compared with the reference |
| --- | --- | --- |
| Reference: llama.cpp's plain SYCL path (`serve.sh reference`) | 41.6 | (the reference; two fresh servers agree 12/12) |
| The lab's general SYCL speed switches (the ones its Gemma recipe uses) | 113-114 | **different**: 0 of 12 answers token-identical |
| The first version of this recipe (`serve.sh unfused`) | 111.3-114.1 | **identical**: 12 of 12 answers, every token |
| **This recipe (`serve.sh fast`)** | **136.3-138.3** | **identical**: 12 of 12 answers, every token, on every fresh server tried |

Also identical on the fast path: the top-8 log-probabilities at every step of a 12-prompt probe (bit for bit), the
same on three long prompts of about 2K, 8K and 24K tokens, and the neural.download canary questions.

**Rebuilt from this folder and checked, 2026-10-15 (v3).** `build.sh` (fresh upstream clone plus the patch, 11
minutes with 6 jobs) and `serve.sh`/`check.sh` exactly as written, on one card of the lab's host, each run on a
freshly started server:

| Run | tok/s | Token-identical to the lab's original reference run |
| --- | --- | --- |
| `serve.sh reference` | 41.7 | 12 of 12 |
| `serve.sh unfused` | 111.7 | 12 of 12 |
| `serve.sh fast`, server A | 136.3 | 12 of 12 |
| `serve.sh fast`, server B | 138.0 | 12 of 12 (and 12 of 12 to server A) |

On server B the canary questions all pass, and the log-probability probe is bit-identical to the lab's reference
run on 12 of 12 prompts and 3 of 3 long prompts. Records:
[`data/2026-10-15-lfm25-24b-a2b-package-check-prefill/`](../../data/2026-10-15-lfm25-24b-a2b-package-check-prefill/summary.json)
(the afternoon build's: [`data/2026-10-15-lfm25-24b-a2b-package-check-fused/`](../../data/2026-10-15-lfm25-24b-a2b-package-check-fused/summary.json),
138.1 and 138.3 tok/s; the first version's:
[`data/2026-10-15-lfm25-24b-a2b-package-check/`](../../data/2026-10-15-lfm25-24b-a2b-package-check/summary.json)).

### Reading prompts

How fast the server reads a whole prompt before it starts answering, by llama-server's own counters (one user,
prompt cache off, after the server has answered other requests; each prompt twice):

| Prompt length | This build (v3) | The afternoon build |
| --- | --- | --- |
| 1,775 tokens | 1,706-1,712 tok/s | 1,027-1,124 tok/s |
| 7,314 tokens | 1,650-1,654 tok/s | 1,100-1,119 tok/s |
| 26,138 tokens | 1,246-1,247 tok/s | 917-924 tok/s |

Why it changed: after the first answer the weights are kept in the reordered layout, and for every prompt the
server converts them to 16-bit numbers for the large matrix products (about half the model per 512 prompt tokens).
The old conversion kernel gave each GPU lane a whole 32-value block, and its speed depended on the build: on the
afternoon build it ran about a third slower. The new one (`LLAMA_SYCL_Q8_0_REORDER_DEQ_COALESCED=1`) gives each
lane 8 neighbouring values with the same arithmetic, so the converted numbers are the same bytes (checked call by
call), and it gave the same speed on every build tried.

### With more context

`llama-bench` on the fast path (raw engine rates, not the suite's measure; 3 repetitions each, all within 2%;
each prompt measurement after the first runs right after a generation run, so on the weight layout a running
server uses):

| Context already held | Generating (tok/s) | Reading a 2,048-token prompt (tok/s) |
| --- | --- | --- |
| none | 150.7 | 2,072 |
| 2K | 146.0 | 1,993 |
| 4K | 139.6 | 1,875 |
| 8K | 130.1 | 1,636 |
| 16K | 113.4 | 1,229 |
| 32K | 90.7 | 801 |

## Run it

You need Linux, one Arc Pro B70, about 26 GB of disk for the model, the Intel oneAPI Base Toolkit (2026.1 was
measured) in `/opt/intel/oneapi`, and `git`, `cmake`, `ninja` and Python 3. From the root of this repository:

```bash
# 1. The model (about 25 GB), then check it byte for byte against the manifest
hf download LiquidAI/LFM2.5-24B-A2B-GGUF LFM2.5-24B-A2B-Q8_0.gguf \
  --revision 0912d33141f77e10705345a6732bfd83f0252fdc --local-dir ~/models/lfm25-24b-a2b
python3 scripts/verify-neural-download-model.py repro/lfm25-24b-a2b-q8-b70/model-manifest.json ~/models/lfm25-24b-a2b

# 2. Build llama.cpp with the patch (clones upstream into a new folder; 12 minutes with 4 jobs on the 8-core test host)
SOURCE_DIR=~/src/llama.cpp-lfm25 repro/lfm25-24b-a2b-q8-b70/build.sh

# 3. Serve it (foreground; Ctrl-C stops it). GPU picks the card if you have several (default 0).
BUILD_DIR=~/src/llama.cpp-lfm25/build MODEL_DIR=~/models/lfm25-24b-a2b repro/lfm25-24b-a2b-q8-b70/serve.sh fast
```

The server speaks the OpenAI API on `http://127.0.0.1:18110/v1` (model name `lfm25-24b-a2b`):

```bash
curl -s http://127.0.0.1:18110/v1/chat/completions -H 'Content-Type: application/json' \
  -d '{"model":"lfm25-24b-a2b","messages":[{"role":"user","content":"Name three uses of a hash table."}],"max_tokens":200}'
```

Options (environment variables): `GPU`, `PORT`, `HOST` (default `127.0.0.1`; set `0.0.0.0` to serve your network),
`CTX` (context tokens, default 32768, the measured size; the model's full 131072 needs about 2.6 GB of cache and
should fit, but was not measured), `ALIAS`.

## Check it on your machine

`check.sh` runs the same 12-prompt suite against a running server (about 2 minutes on the fast path, 4 on the
reference) and compares every token with the lab's reference run:

```bash
repro/lfm25-24b-a2b-q8-b70/check.sh run fast                   # with serve.sh fast running
```

A different compiler or driver version can legitimately change the reference itself, so the proof that the fast
path changes nothing is your own pair: start `serve.sh reference`, `check.sh run ref`, stop it, start `serve.sh
fast`, `check.sh run fast`, then `check.sh compare lfm25-check/ref.json lfm25-check/fast.json`. Every prompt should
say identical. If one does not, `serve.sh unfused` (the same fast layouts without the fusions) tells you which half
of the speed-up is involved.

## What the patch changes

llama.cpp's SYCL backend can store 8-bit weights in a reordered layout that the card reads much faster, but its
kernels for that layout add numbers up in a different order, which changes the last bits of results and, a few
hundred tokens later, the words. The patch adds kernels that read the reordered layout but keep the reference
kernels' order of operations exactly, and `serve.sh fast` turns them on:

| Setting | What it does |
| --- | --- |
| `GGML_SYCL_DISABLE_OPT=0` | store weights in the reordered layout (llama.cpp's own option; the speed) |
| `GGML_SYCL_PRIORITIZE_DMMV=1` | keep ordinary matrix-vector products on the reference kernel family ... |
| `LLAMA_SYCL_DMMV_Q8_0_REORDER_EXACT=4` | ... reading the reordered layout with the reference arithmetic |
| `LLAMA_SYCL_MUL_MAT_ID_Q8_0_REORDER=1` | the experts on the reordered layout ... |
| `LLAMA_SYCL_MMVQ_ID_XOR_REDUCE=1` | ... summed in the reference order |
| `GGML_SYCL_DNNL_DETERMINISTIC=1` | (all modes) deterministic oneDNN matrix products for prompt processing |
| `LLAMA_SYCL_Q8_0_REORDER_DEQ_COALESCED=1` | (`fast` only) the steadier conversion of the reordered weights for prompt reading |

Then `serve.sh fast` (not `unfused`) adds twelve exact fusions. Each generated token used to take about 1,080 GPU
kernel launches, most of them tiny steps between the big matrix products; each fusion does a chain of those steps
in one kernel with the same arithmetic in the same order (floating-point contraction and reassociation switched
off where the compiler could otherwise change it):

| Setting | Steps done in one kernel |
| --- | --- |
| `LLAMA_SYCL_FUSE_RMS_NORM_MUL` | norm, then multiply by its weight |
| `LLAMA_SYCL_FUSE_ADD_RMS_NORM_MUL` | residual add, norm, multiply |
| `LLAMA_SYCL_FUSE_MOE_SUM` | weighted sum of the four experts' outputs |
| `LLAMA_SYCL_FUSE_MOE_ROUTE` | expert routing: sigmoid, bias, top 4, weights |
| `LLAMA_SYCL_FUSE_SHORTCONV` | the short-convolution blocks' small steps |
| `LLAMA_SYCL_FUSE_F16_SHADOW` | the norms also write the 16-bit copy the next matrix product reads |
| `LLAMA_SYCL_FUSE_Q8_SHADOW` | an 8-bit input copy made once and reused by the next product on the same input |
| `LLAMA_SYCL_FUSE_MOE_GATE_UP` | the experts' gate and up products in one launch |
| `LLAMA_SYCL_FUSE_NORM_ROPE` | attention q/k norm, rotary position, write of K into the cache |
| `LLAMA_SYCL_FUSE_NORM_Q8` | the norm before the experts writes their 8-bit input |
| `LLAMA_SYCL_FUSE_MOE_DOWN_SUM` | the experts' down product and their weighted sum |
| `LLAMA_SYCL_FUSE_CONV_STATE_ROWS` | the short-convolution state read straight from its cache |

Every fusion was checked by running the fused and the unfused steps side by side and comparing every output byte for
byte (`LLAMA_SYCL_FUSE_VERIFY=1`, over 800,000 comparisons, none different), then on fresh servers against the
reference. One more fusion (`LLAMA_SYCL_FUSE_MOE_FFN`, gate + up + SWIGLU + 8-bit quantization in one kernel) is in
the patch but **not** used: the GPU compiler rounds about 1 in 30,000 of its quantized values differently, which
changes the text, so `serve.sh` leaves it off.

The patch also carries the lab's earlier B70 work on this llama.cpp version (all behind switches that are off
unless set). Every attempt, including what did not help, is in the
[lab note](../../experiments/lfm25-24b-a2b-b70/notes/2026-10-14-lfm25-24b-a2b-bringup.md).

## Limits

- Measured with one user at a time (`--parallel 1`) on one card, prompt cache off, 32K context. Prompt caching
  and several users at once should work but have not been checked for identical output.
- `--reasoning auto`: the model may think before answering, and the thinking counts toward `max_tokens`.
- Identical output is proven against llama.cpp's plain SYCL path on the same build, not against other backends
  (CPU, CUDA), which do their arithmetic differently.
- Not yet replayed on a freshly installed host.

## Files

- [`build.sh`](build.sh): clone, patch (checksum checked), build; writes `lfm25-24b-a2b-build.json` with the
  compiler version and the server binary's SHA-256
- [`serve.sh`](serve.sh): the server command, `fast`, `unfused` or `reference`
- [`check.sh`](check.sh): the suite and the token-by-token comparison
- [`model-manifest.json`](model-manifest.json): the model file's revision, size and SHA-256
- Evidence: [lab note](../../experiments/lfm25-24b-a2b-b70/notes/2026-10-14-lfm25-24b-a2b-bringup.md),
  [package check of this version](../../data/2026-10-15-lfm25-24b-a2b-package-check-fused/summary.json),
  [reference run](../../experiments/lfm25-24b-a2b-b70/data/r0-suite-a.json),
  [fast runs](../../experiments/lfm25-24b-a2b-b70/data/x1final-suite-a.json)
  ([second server](../../experiments/lfm25-24b-a2b-b70/data/x1final-suite-b.json)),
  [canaries](../../experiments/lfm25-24b-a2b-b70/data/x1final-canaries.json)
