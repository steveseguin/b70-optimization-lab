# Qwen3.8 Flash-Next FP8 A63 old-overlay-head control result

Date: 2026-09-02 19:24--19:58 EDT, boot `95bac684`-successor (GuC 70.72.1,
BIOS 2.4a, root SSD Gen4)
Status: diagnostic negative for the regression hypothesis; the 18 overlay
commits are excluded; no promotion claim; protected results unchanged

## Outcome

A63 served the A62 identity with the vLLM overlay checked out at
`1372c62d975c554f4b465c8299bc5f3295301ceb`, the head of the last server
proven exact on 2026-08-28, with no tuned MoE map (eager, bundled oneCCL,
external checkpoint, PLE-only UVA placement, 2304 max model length, staged
kernels `2f829747...`). Load took 13 minutes (weights 19:34, healthy 19:37).
The probe's first invocation failed closed on its own identity check
(`FAIL: server 73375 tuned folder is []`): the probe still asserted the A56
map that A63 deliberately drops. The stop file was not written, the server
stayed healthy, and the probe gained an explicit `--expect-no-tuned-folder`
mode (SHA-256 `60a5b214...`) and was rerun at 19:41. All 24 requests
completed; no hang occurred and the kernel log holds no fault. Teardown
exited 143 as in A62 (SIGTERM after the stop file), leaving no process.

| depth | first-step identical (8x) | top-1 logprob spread | 128-token repeats | first divergence |
| --- | --- | --- | --- | --- |
| 8 | no | 0.3143 nats | 3 distinct hashes | tokens 34, 19 |
| 64 | no | 0.0050 nats | 3 distinct hashes | tokens 18, 18 |
| 256 | no | 0.1531 nats | 3 distinct hashes | tokens 96, 9 |
| 2048 | no | 0.0005 nats | 3 distinct hashes | tokens 4, 4 |

The maximum top-1 logprob difference before divergence reached 0.62 nats at
depth 64; the depth-2048 repeats diverged at token 4 despite a 2.19-nat
top-1/top-2 gap at the divergence point in repeat 1, so the perturbation is
not confined to near-tie positions. Receipt:
`.../qwen38-flash-next-fp8-tp4-ep4-oldhead-mtp0-2304-ple-only-r1-attempt63/a63-logprob-determinism.json`.

## Reading

The prereg's second branch applies: the jitter is present at the old overlay
head, so the source lies below the overlay. The identity diff between this
server and the 2026-08-28 exact anchor (attempt 4 of the current-runtime
anchor) is now small: the same vLLM head, the same staged runtime build
`2f829747...` and manifest-checked binaries, the same Torch/Triton/oneAPI
versions, and the bundled oneCCL in both. What differs is the placement
(PLE-only UVA versus PLE plus embedding UVA), the checkpoint path (external
NTFS versus local NVMe, identical index and config hashes), the 2304/128-MiB
versus 4352/192-MiB capacity, and the host firmware (GuC 70.72.1, BIOS 2.4a).
The 08-29 record already shows that the older placement failed the exact-4K
repeat (A7) one day after the anchor, so placement is not a plausible cause,
and the 08-28 exactness rested on token-hash equality of peaky outputs, which
today's logprob probe shows can hold while logits still jitter. The most
economical reading is that the serving line was never logit-exact under TP4
and that the 2026-08-28 authorities were margin luck at the token level.

The strongest existing pointer is the 2026-08-30 A24/A25 fresh-start trace
pair: the first differing tensor was `layer_1_attn_output.attn_out`, the
GatedDeltaNet output of the PLE-bearing layer, with every upstream tensor
(model input, PLE lookup and projections, hyperconnection mix, and all of
layer 0's outputs) exact. The GDN-internal trace proposed there never ran.

## Next

1. Fixed-input repeatability gate for the staged `_xpu_C.gdn_attention`
   operator at TP4 shapes (8-token prefill, 64-token chunk with state, 32
   chained chunks, single decode, 128 chained decodes) plus the XCCL
   all-reduce at 1, 8 and 64 rows, two fresh processes each
   (`tools/run-q38-gdn-repeat-gate-a1.sh`).
2. A64: the A62 server with a default-off, report-only extension of the
   repeatability trace that records the GDN input projection, core output,
   gated norm, and output projection for layers 0-2 on all four ranks for
   the first three 8-token prefills, so the three depth-8 probe requests
   are compared op by op on one server.

The overlay was restored to `cbc3cb588...` at 20:00 before any other arm.
