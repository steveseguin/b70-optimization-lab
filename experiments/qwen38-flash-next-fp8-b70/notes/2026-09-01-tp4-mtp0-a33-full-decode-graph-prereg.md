# Qwen3.8 Flash-Next FP8 A33 full-decode graph preregistration

Date: 2026-09-01
Status: frozen before model load

## Question

Can compilation-free, size-1 `FULL_DECODE_ONLY` XPU graph replay remove the
dominant target-token launch/submission overhead while preserving the exact
Qwen3.8 Flash-Next FP8 TP4/MTP0 output contract?

A28 measured about `181.30 ms/token` at the protected `5.515783 tok/s` rate,
while its concrete noncollective work plus isolated collective cost accounts
for only about `54.84 ms`. Small kernel tuning cannot plausibly double the
endpoint. Full target-step replay is the first mechanism with enough scope to
do so. The public `flashnext-harness` input was reviewed, but its mixed
GGUF/CPU/llama.cpp path contains no comparable FP8 hot-path implementation;
the transferable lesson is to optimize whole-step movement and scheduling,
not substitute its quantized checkpoint or throughput claim.

## Prerequisites already passed

- Public oneCCL `4ceafd1` passed 100/100 changing-input graph replays at the
  production `4096` threshold on all four ranks; the installed libccl failed
  at replay 1.
- One graph containing 97 ordered BF16 `[1,2560]` reductions passed 9,700
  exact outputs per rank.
- The exact selective-UVA PLE decode path passed 100/100 changing-ID graph
  replays on all four ranks.

These are component gates, not endpoint or speed claims.

## Frozen A33 identity

- official `Qwen/Qwen3.8-Flash-Next-FP8`, revision
  `bcd9f01ddc9cff2316eb84281bebcd5b058bddce`;
- vLLM `797769b34b6db5c934609b75dc04cc61ec66e5f9`, clean kernel-source
  provenance `e421889999bc1e5a5f11044d14548b9afdba644d`, and unchanged accepted
  staged runtime built at `2f829747503c77d4814834dffd0840fb1dd9f75a`;
- TP4/EP4, MTP0, one sequence, 4,352-token capacity, 128 MiB KV cache;
- synchronous selective-UVA PLE-only placement, exactly 12.0 GiB host budget
  per rank; input embedding remains on device;
- untuned Triton MoE, no M1/M4 alternate config, no grouped HC, no async PLE,
  no async scheduler, no diagnostic trace;
- `CompilationMode.NONE`, `FULL_DECODE_ONLY`, capture sizes `[1]`, maximum
  capture size 1, compile sizes `[]`, one graph warmup;
- `VLLM_XPU_ENABLE_XPU_GRAPH=1`; all legacy graph selectors absent;
- public graph-safe libccl SHA-256
  `43d94d43506e30096dd099b9d53b54f932be964751e92ff0cbb8d3a37fad6700`;
- oneCCL device kernel SHA-256
  `0d549c35a558f1b216cb7d1efeaa9f86d7596ffc47b383644e075290d314f0c9`;
- direct send/receive, peer access, and explicit
  `CCL_SYCL_ALLREDUCE_LL_THRESHOLD=4096`;
- attempt 33, port 19705, and unused run/cache/compile/RPC/supervisor paths.

The arm derives mechanically from the frozen A28 launcher, client, and
supervisor. It removes the A28 report-only profiler and the obsolete
one-load-per-boot guard. Reuse is governed by exclusive host/GPU locks,
unused evidence paths, exact source/runtime/storage checks, four-card health,
cleanup, journal review, and postflight; a reboot is not part of this plan.

## Fail-closed runtime and quality gates

- verify at least four live collective workers map only the exact public
  libccl and carry the exact graph/oneCCL environment;
- reject any TorchInductor output: this is a compilation-free arm;
- require the server config and completed full-graph capture receipts;
- require a nonzero size-1 `CUDAGraphMode.FULL` runtime dispatch count;
- retain A28's recovery canary, accepted 6/7-or-7/7 semantic boundary, 16/16
  exact repeat, cache-zero 4K needle, three protected short hashes, and two
  exact-4K authority rows unchanged;
- tear down and preserve a negative on any mismatch, unavailable graph,
  memory-fit failure, endpoint failure, or health failure.

## Frozen interpretation

- A full pass with the same exact hashes and a higher short median is a
  lossless graph candidate; it does not replace protected results until a
  separately started repeat confirms it.
- A quality or output mismatch closes the arm as unsafe regardless of speed.
- A graph-use failure is an orchestration/runtime negative, not an eager speed
  measurement.
- A memory-fit failure motivates a separately preregistered memory-recovery
  arm; it does not authorize lowering context, silently moving another tensor,
  or changing the protected baseline.
- The protected `5.515783 tok/s` MTP0 and `20.727176 tok/s` MTP4 results remain
  unchanged under every outcome.

## Frozen files

- rewriter: `4ba75fb0eb0311b3feed20072fdceb30802c7425737b9405d22febcbd6b990aa`;
- runtime verifier: `239f80b93531762ee607b2b651b3c69d4ba3d7b888c783ef989d321e7d834fae`;
- runtime-verifier tests: `4156cb55e6c623223e4005c5b2554407aff01648cd8bafdf4f389b62b6ac3679`;
- launcher: `776f608eee77fb8ad4b5d02496e9e68fa4e16392639e0fa471c857de5fffe02e`;
- client: `034b08e0eea247c98715646e2211c1507c4b435a06e5ba94703e12784d4e5ce1`;
- supervisor: `d2d7e09a230f616f6594b3ee56d546c39889938586a16394bc65d3fb7a27705e`;
- generated inner launcher: `fd25c815e4acb95fdc08d5aed050885dcda072bf9028931a86ce89e4194acad0`.
