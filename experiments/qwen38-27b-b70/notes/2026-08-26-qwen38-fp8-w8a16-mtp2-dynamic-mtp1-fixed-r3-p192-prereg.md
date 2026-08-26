# Preregistration: dynamic MTP2→MTP1 R3, 192-token capacity treatment

## Question

Can the repaired dynamic MTP2→MTP1 service clear **875 aggregate tok/s at
c64** once all 64 measured short requests can reside concurrently?

R2 is closed at 817.007910 tok/s. Its server measured 12,595 KV-cache tokens,
reported 49.20× concurrency at a 256-token cap, and logged 49 running plus 15
waiting requests at full cache. This R3 changes only the maximum service length
from 256 to 192 tokens. It is a distinct short-context deployment profile, not
a fix for or claim about long-context capacity.

## Frozen identity

- model `Qwen/Qwen3.8-27B-FP8`, revision
  `017b9c7af6b5689d5dd426a76e0bc077eb5ca20a`;
- image
  `neural-download/vllm-openai-xpu:f01e-kernel-1e90-w8a16-dynamic-mtp-width-r1`,
  ID `sha256:9918c4477d2d3bdbd84732c5beb13619a89740f9915b1d7393fb48f1d3c8ed72`;
- active-width patch SHA-256
  `68c486a9a10a2f7e85d7d88783a05f89919e931d2b81922f85be733bfb59f1b5`;
- TP2 on B70 devices 0 and 1, FP16 activations/KV, block-W8A16 enabled,
  prefix cache disabled, block size 64, 128 sequence slots, MBT512, direct
  oneCCL P2P, PIECEWISE graph size 1;
- dynamic schedule exactly `[[1,1,2],[2,128,1]]`;
- **treatment:** `--max-model-len 192` instead of R2's 256;
- new compile cache and output directory.

The measured request is 40 tokenizer-reported prompt tokens plus 128 returned
tokens, 168 total. All rows must return the full 128 tokens; no truncated row is
eligible.

## Ordered gates

1. Start the exact image with a new cache and confirm the server-reported KV
   capacity. This log value is diagnostic, not a performance claim.
2. Run one excluded single-user conditioner, then five single-user rows. The
   first eligible row must remain at or above **82.810053 tok/s after TTFT**,
   report 128 completion tokens, and report zero cached prompt tokens.
3. Run one excluded c64 transition. Require 64 requests, 8,192 completion
   tokens, zero cached prompt tokens, complete token-ID capture, and zero
   cross-base oracle collisions.
4. Run one separately declared c64 measurement with the same requirements.
   It passes only at **≥875 tok/s**; >1,000 tok/s remains preferred.
5. If and only if step 4 passes, stop. Before any replication, write and push a
   separate preregistration for fresh-server replication and the 512-token
   semantic concurrency canary.

R2's 7/7 + 8/8 semantic result and c2 repair canary remain the code/runtime
quality evidence because R3 changes only the service length cap. R3 will not
run c128, schedule sweeps, threshold sweeps, context sweeps, site updates, or
LocalMaxxing. A failure closes this treatment without reporting its excluded
transition as the selected result.

No result will be interpolated or extrapolated.
