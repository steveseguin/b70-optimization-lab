# Qwen3.5 9B W4A16 — one- or two-B70 container packet (candidate)

RedHatAI's W4A16 quantization of Qwen3.5-9B (compressed-tensors INT4 weights, FP16 activations) served by vLLM XPU on
one or two Intel Arc Pro B70 32 GiB cards, with the publisher's own MTP head as a lossless speculative draft and full
decode-only XPU graph capture. The container image and the strict launcher chain are the Qwen3.8 lanes', unchanged.

> **Single request (2026-09-07, campaign w1):** MTP depth 3 with the draft-only INT4 lm_head `113.63 / 112.90 tok/s`,
> no speculation `64.33 / 64.34` (two fresh servers each, class-balanced median decode on the strict 12-prompt suite).
> Both speculative servers matched each other and the no-speculation oracle on all 12 complete token arrays, so the
> speedup is lossless. LocalMaxxing `cmtrhoyl1000cps01o43bhl72` at `113.265 tok/s`.

> **Concurrent users (c1-c64 identity ladder, 128 tokens per request):** without speculation this route is
> byte-identical to a single request at **every rung through 64 users, in both passes** (`1268.4 tok/s` at 64 users,
> 64/64), which is what the FP8 build of the same model cannot do. With depth 3 it is exact through 16 users
> (`750.8 tok/s`); 32 and 64 users are measured and withheld.

> **Two cards (2026-09-07, campaign w3):** MTP depth 3 `172.27 / 172.32 tok/s`, `+52%` over one card and `17%` above
> the FP8 route's two-card result. All strict gates pass 12/12 on both card counts. LocalMaxxing
> `cmtrn9hoy001ops01qzd4axry` at `172.296 tok/s`. One caveat is recorded rather than hidden: on two cards the
> no-speculation ladder holds 32 users exactly but drops to 63/64 at 64 users in both passes, which points at the
> cross-card reduction rather than the GEMM, since the same kernel is exact at 64 users on one card.

> **Long context:** not measured on this route yet; the FP8 route's 2K-32K ladder is in
> `repro/qwen35-9b-fp8-b70/README.md`.

> **Many users, faster (2026-09-11, R293):** the served image gained a switch, `CLASSPAD=1`, that keeps every
> unquantized FP16 linear in one verified oneDNN rounding class instead of re-reading the 2 GB vocabulary projection
> once per 32 rows. Lossless by the same gates; one card without speculation reaches `1955 tok/s` at 128 users
> (512/512 exact) against `1324`, two cards `3227`; depth 3 on one card `1225` at 64 users against `787`; and with a
> 5 ms admission stagger 64 users on two cards are byte-identical to the sequential oracle over twenty passes at `2557`.
> Single user costs 1-4%, so the default stays `CLASSPAD=0`. Recipe README, R293 section.

## Why this route rather than FP8

The same publisher's FP8-dynamic build of this model is packaged separately and is slower at every depth, but the real
difference is reproducibility. vLLM's compressed-tensors path selects `CompressedTensorsWNA16`, which on XPU is the
lab's `wNa16` kernel with the fixed-K two-tier W4A16 strategy. That kernel does not vary its reduction order with the
number of decode rows, so a token whose top two candidates are exactly tied resolves the same way no matter how many
requests share the step. The FP8 path has no such guarantee and flips a handful of prompts from 16 users up.

The determinism pad (`VLLM_XPU_W4A16_DETERMINISM_PAD`) is off and should stay off: measured on this model it is inert
below its 128-row threshold and costs 13% at 64 users above it, buying no identity.

## Commands

```bash
# image (public, anonymous pull verified 2026-09-07 by tag and digest)
docker pull ghcr.io/steveseguin/vllm-openai-xpu-qwen38-int4@sha256:40d46730c9a24f9396cc67c0e5578dd80d11dfae7a4d23a55f97620140a0b3e6
docker tag  ghcr.io/steveseguin/vllm-openai-xpu-qwen38-int4@sha256:40d46730c9a24f9396cc67c0e5578dd80d11dfae7a4d23a55f97620140a0b3e6 \
            neural-download/vllm-openai-xpu:qwen38-int4-fp16-linear-classpad-cheapest-r293

# serve (MTP_DEPTH=0 for the no-speculation profile)
MODEL_DIR=/models/Qwen3.5-9B-quantized.w4a16 VLLM_CACHE_DIR=/tmp/qwen35-w4a16-cache MTP_DEPTH=3 \
  repro/qwen35-9b-w4a16-b70/scripts/run-qwen35-9b-w4a16-server.sh

# strict benchmark with canaries
OUT_DIR=/tmp/strict-a BASE_URL=http://127.0.0.1:18131 MODEL_NAME=qwen35-9b-w4a16-mtp3 \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/bench-w8a16-mtp1-strict.sh
```

Full procedure, validation commands and the identity tables: [`repro/qwen35-9b-w4a16-b70/README.md`](../../repro/qwen35-9b-w4a16-b70/README.md).

## Container packet

This is a level-2 packet: a digest-pinned image, explicit GPU device mapping, read-only model and persistent cache
volumes, and one- and two-card profiles.

```bash
cd packages/qwen35-9b-w4a16-b70
export MODEL_DIR=/models/Qwen3.5-9B-quantized.w4a16

PROFILE=one-gpu ./scripts/preflight.sh     # GPUs, driver, RAM, storage, image
./scripts/download-model.sh                # exact bytes, from the publisher at the pinned revision
./scripts/verify.sh                        # revision, sizes, every SHA-256 and git blob
PROFILE=one-gpu ./scripts/smoke-test.sh    # start, health, and a repeat-identity gate
```

`compose.yaml` is **generated, not hand-written**. `scripts/render-compose.sh` runs the real recipe launcher behind a
docker shim that captures the `docker run` argv instead of starting anything, then renders both profiles from it, so
the packet reproduces the measured container's 73 environment variables and full serve command exactly rather than
approximately. `tools/check-container-packet.py` runs in CI and fails the build if the committed file stops matching
the launcher, if the image is not pinned by digest, if the model mount is not read-only, or if a port leaves loopback.

Regenerate after any launcher change:

```bash
MODEL_DIR=/models/Qwen3.5-9B-quantized.w4a16 ./scripts/render-compose.sh
```

## Still missing

- clean-host replay
- graph-off and 2K-32K rows (measured on the FP8 route only)
- the two-card 64-user identity gap above; the one-card route has no such gap
