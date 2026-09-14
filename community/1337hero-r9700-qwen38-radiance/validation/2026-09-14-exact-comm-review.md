# Radiance communication review for official FP8 + MTP

Static review only; no contributed code or GPU workload executed. Official FP8
weights, FP16 target activations/native KV, exact outputs and MTP remain the
constraints. The [source identity receipt](2026-09-14-exact-comm-review.json)
records SHA256 values, source lines and the installed R304 communicator snapshot.
No optimization was adopted or measured in this review.

## Most useful remaining idea: an exact two-card collective

Radiance has a genuine uncompressed communication path. StillDeadcode's pinned
[libr4d kernel](https://codeberg.org/StillDeadcode/libr4d/src/commit/e8de4bc1f3dbd608dcb8d3ffceb6b48acdf83bb7/r4d_ar_oneshot_2rank_exact.hip#L9-L24)
pushes each rank's input into peer scratch, then adds the local input to received
data. Double buffering and device counters keep scratch reusable. Each block
has its own handshake. Only scratch and flags are shared, so graph execution
does not need to register every model input/output address. Radiance's
[wrapper](https://github.com/magiccodingman/vllm-radiance/blob/f295b9ef51ad413a68e4192371e0377741a354ce/radiance_allreduce.py#L81-L107)
provides persistent scratch and current-stream dispatch.

The original B70 communicator currently clones its input, submits asynchronous
XCCL all-reduce, and waits. A native out-of-place one-shot implementation could
remove the clone and some general collective machinery. This is a plausible
engineering direction, **not a demonstrated speedup or an inexpensive flag**.
The lab already proposed this direction in its
[September 4 decode profile](../../../experiments/qwen38-27b-b70/notes/2026-09-04-qwen38-fp8-r187-decode-profile-r199c-result.md);
Radiance supplies a concrete implementation reference, rather than first
introducing the idea. The older profile includes peer waiting and overlapping
queues; its collective totals cannot be converted into predicted savings.
The [recent 512-token profile](../../../experiments/qwen38-27b-b70/notes/2026-09-14-fp8-prefill-focus-results.md)
records 20.5–27.2 ms summed all-reduce device time against 107–112 ms matrix work,
also not additive wall time.

A responsible next step is source-level Level Zero/SYCL feasibility followed,
only in an exclusive test window, by one small operator gate. Preserve
the native FP16 payload and require bitwise XCCL equality, changing-message
reuse tests, both-rank agreement and a matched latency comparison. Cover actual
1/2-row decode and 512/4096-row prefill shapes. Test cancellation, subnormal,
overflow and signed-zero inputs because libr4d adds in FP32 and casts back to
FP16; the word `exact` alone does not qualify XCCL equality.

Do not transplant AMD ordering or failure behavior. The source depends on
fine-grained HIP IPC and `s_wait_storecnt`. Its peer-spin loop eventually breaks
and proceeds into reduction without a failed-result signal
([lines 92–121](https://codeberg.org/StillDeadcode/libr4d/src/commit/e8de4bc1f3dbd608dcb8d3ffceb6b48acdf83bb7/r4d_ar_oneshot_2rank_exact.hip#L92-L121)).
A B70 implementation needs proven system-scope ordering and must fail closed.
Given the recent host incident and absence of a native implementation, this is
best retained as a separate bounded project rather than altering the live server.

## Useful accounting practice, no missing B70 switch

Radiance's [message-cap patch](https://github.com/magiccodingman/vllm-radiance/blob/f295b9ef51ad413a68e4192371e0377741a354ce/patch_ar_maxbytes.py#L2-L26)
fixes a silent dispatch mismatch: 4096 rows × 5120 channels × two bytes is
40 MiB, below its 48 MiB limit; 8192 rows is 80 MiB, above it. The portable lesson
is to check the actual operator path after changing prefill chunk sizes.
The B70 launcher already sets XCCL simple-algorithm thresholds to 4 GiB, and
has no Radiance custom-kernel gate. No analogous missing setting was found.

The separate [geometry patch](https://github.com/magiccodingman/vllm-radiance/blob/f295b9ef51ad413a68e4192371e0377741a354ce/patch_ar_geometry.py#L2-L25)
tunes the **compressed six-bit** communication branch. Do not carry its speed
claims over to exact FP8/MTP or describe those knobs as lossless optimizations.

## Changes that do not qualify for adoption here

- **Collective/residual/normalization fusion:**
  [ARNQ](https://github.com/magiccodingman/vllm-radiance/blob/f295b9ef51ad413a68e4192371e0377741a354ce/radiance_arnq.py#L63-L102)
  emits FP8 activations for its W4A8 consumer. Our FP16 activation contract
  excludes that implementation. A separate FP16-only fusion is conceivable,
  but must preserve existing normalization reduction order and rounding.
  The same source's SiLU helper explicitly admits differing quantized codes;
  `exact_nq` is not an end-to-end exactness certificate.
- **Graph current-stream handling:** Radiance
  [backports upstream vLLM PR 53818](https://github.com/magiccodingman/vllm-radiance/blob/f295b9ef51ad413a68e4192371e0377741a354ce/patch_rocm_cudagraph_current_stream.py#L2-L8)
  for ROCm graph capture. It does not patch our original XPU/V1 MTP service.
  Prior unchanged B70 graph/compiled-allreduce attempts were neutral or negative.
- **Attention geometry:** its
  [AITER LDS patch](https://github.com/magiccodingman/vllm-radiance/blob/f295b9ef51ad413a68e4192371e0377741a354ce/patch_unified_attention_lds.py#L2-L18)
  addresses gfx1201 shared-memory limits and AMD wave geometry. Native XPU
  attention uses a different backend. Keeping FP16 KV while changing attention
  tiling still requires arithmetic qualification.
- **Removing XCCL waits:** already tested lossless and neutral in R207, while
  opaque compiled all-reduce was neutral in R60. These are explicitly closed
  in the [do-not-repeat index](../../../experiments/qwen38-27b-b70/DO-NOT-REPEAT.md).

Recognition remains acknowledgement of 1337Hero's report, StillDeadcode's exact
collective implementation and Radiance's integration/accounting work. No
validated B70 boost or integration credit is claimed.
