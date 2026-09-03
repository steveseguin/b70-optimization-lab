# Qwen3.8 Flash-Next FP8 A85 preregistration: MTP1 in the graph with the serial-exact recurrent path

Date: 2026-09-03
Status: frozen before launch; diagnostic gated on the MTP0 line's hashes

## Question

A81/A83/A84 established that the MTP1 verification path is deterministic
but not equal to single-row decode after the first generated token, at
every depth. The kernel source carries an exact recurrent spec-decode path
(`VLLM_XPU_GDN_NATIVE_SPEC_RECURRENT_SERIAL_EXACT=1` with
`VLLM_XPU_GDN_SPEC_PERSISTENT_SCRATCH=1`), generalized to the MTP1 row
count in kernel commit `ad25aa9` (an ancestor of the line's `e421889`
source head) and sealed as the stage
`/mnt/usb-models/qwen38-build/runtime-mtp1-exact-ad25aa9-b70` (manifest
`runtime-stage-mtp1-exact-loadable.sha256`, verified today). Its only
end-to-end attempt (2026-08-27, attempt 3) died on a launcher path-length
defect before any worker started, so the mode has never been measured. Does
the exact recurrent path make MTP1 reproduce the MTP0 line's outputs, and
what does it cost?

## Design

`tools/rewrite-q38-a81-to-a85-exact-recurrent.py` derives A85 from the
frozen A81 packet (graph MTP1, capture sizes [1, 2], 32-block KV, NVMe
copy, 12 GB floor) with `MTP_EXACT=1`: the base's exact freeze lifts to
exactly 1, the kernel stage is the sealed exact build (stage build head
`ad25aa9`; source head stays `e421889`), the served model name carries the
base's `-mtp1-exact-recurrent` suffix and the campaign its
`-exact-recurrent-` infix; the base's own exact-mode canary and per-rank
"reached" marker receipt run before HEALTHY. Same driver battery and
pinned MTP0 hashes as A81 (driver model name follows the suffix). Attempt
85 / port 19757. Packet: launcher `b2d2002d...`, client `9f16a930...`,
supervisor `1acacd64...`, host wrapper `37ae3fd4...`.

## Reading

- All pinned hashes match (short, 2K, 4K, repeat) with the same quality
  outputs: the GDN recurrent path was the whole difference; MTP1 becomes a
  lossless candidate and its rates are the result (the exact path's cost
  against A81's 38.8 tok/s short is the second number).
- Hashes still differ at depth but the A84-style logprob gap shrinks or the
  first divergence moves later: the recurrent path was part of it; the
  remaining difference sits in the M=2 GEMM/MoE paths.
- Server refuses to start or capture (the exact path requires one request,
  one state column per verifier row and an in-order queue): record the
  boundary; an eager exact variant (A83 lineage) is the fallback.
