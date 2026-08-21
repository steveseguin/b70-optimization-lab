# Qwen3.8 27B Q4_K_M target-only TP1 lane

Date: 2026-08-21

Status: **lane opened; baseline protocol registered; no result yet.**

## Goal and identity

Single-B70 (TP1) target-only decode on the four-B70, 125-GiB measuring host
(`steve-b70s`), no MTP/DFlash/draft/speculation, aiming first at an honest
baseline and then a fusion lever ladder toward **30+ tok/s per GPU**. This is
a **new identity**, separate from the promoted two-ASRock-B70 TP2 result
(`49.717503 tok/s`, LocalMaxxing `cmsy530c70cpwms01bl1sjk6g`): different host,
one device instead of two, and a different compiler minor version. Absolute
numbers must not be pooled with reference-host TP2 evidence.

- Source: `/home/steve/src/llama.cpp-q38-tp1-lane` — mndodd
  `intel-sycl-optimization` base `4302fb59969a5d8cf9f8e5f55fdd4506d0ed2126`
  plus the full lab TP2 stack (decoded patch
  `f21e9b557c3d024527ac98d5f189cf7ea72fa8c38a5faf2a22ee339fd1988998`) plus the
  Q4_K gate/up/SwiGLU increment (decoded patch
  `0a27858525f6a402cf9c92d1b93daee0a80e2ffaef9137bf7bce784a549b58b6`), both
  verified at restore time. Identical source identity to the promoted TP2
  recipe.
- Build: `build-sycl-aot-bmg-g31`, Intel oneAPI DPC++/C++ **2026.0.0**
  (`2026.0.0.20260331`; the reference host's accepted build used 2026.1.1 —
  recorded difference), Release, BMG-G31 AOT, same CMake flags as the
  accepted recipe, `-j12` on this 32-core host.
- Model: `Qwen3.8-27B-Q4_K_M.gguf`, SHA-256
  `31629f53165ab6a7dad8c9847dcfd1fdf55829dac1e6e748f4a68581b0033d34`
  (byte-copy of the accepted reference-host file), at
  `/mnt/usb-models/models/qwen3.8-27b-gguf/`.
- Server: [`run-qwen38-q4km-tp1-gpu0-server.sh`](../scripts/run-qwen38-q4km-tp1-gpu0-server.sh)
  — `--device SYCL0` with `ONEAPI_DEVICE_SELECTOR=level_zero:<gpu>`, FA on,
  F16 KV, batch 1024 / ubatch 256, one slot, `--cache-ram 0`,
  `--ctx-checkpoints 0`, ctx 8192, the complete accepted runtime-door set
  (TP2 communication doors are shape-gated and inert with one device), and a
  48/64 GiB host-memory scope on this 125-GiB host (the reference recipe's
  8/10 GiB scope is a low-RAM-host constraint, not part of the result
  identity).
- Bench: [`bench-qwen38-q4km-tp1.sh`](../scripts/bench-qwen38-q4km-tp1.sh) —
  the fixed realistic 12-prompt suite, one cold pass per prompt,
  `cache_prompt=false`, `temperature=0`, 512 tokens, conventional 99-interval
  median primary metric, `cached_tokens=0` required on every request.

## Baseline protocol

1. Fresh server on GPU 0, health check, then one cold 12-prompt suite (run A).
2. Full server restart, then a second cold suite (run B). The TP1 route's
   output hashes must reproduce 12/12 between A and B before any number from
   this lane is quotable; A/B medians bound run-to-run noise.
3. TP2-oracle output equality is recorded as evidence but is not a gate: a
   one-device reduction order may legitimately differ. Before any promotion,
   the lane must pass the standard semantic/arithmetic/JSON/factual/logic/
   Python-result canaries and a fresh cold suite on the promoted
   configuration, and any LocalMaxxing submission goes to the 1-GPU
   configuration class.
4. GPU 3 remains excluded until its post-recovery stock-health retest passes;
   this lane uses GPU 0 and must never overlap another model workload or an
   AOT build on the same card.

## Lever ladder (initial)

After the baseline: per-door A/B attribution at TP1 (the TP2-transferred
doors have never been attributed on one device), ubatch/batch sweep, ctx
sweep, then new TP1-specific fusion work (the Q64K32 chunk-native FA policy
qualified on GPU2 at KV1300 is a later candidate once its campaign
authorizes integration). Every lever lands with a same-binary A/B, exact
12/12 hash reproduction, and cache-zero evidence, or it dies with a recorded
negative.
