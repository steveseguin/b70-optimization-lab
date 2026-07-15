# DeepSeek V4 K160 repeatability and oneCCL all-reduce routing

Date: 2026-07-15

## Outcome

The fast TP4 graph lane is now repeatable and exact-correct without giving up
its approximately 40 tok/s decode rate. The promoted recipe uses the packaged
oneCCL source version (`2021.17.2`) with only SYCL all-reduces larger than
131,072 bytes routed to the ordinary fallback. Two independent strict cold
suites measured:

- `40.096205` median tok/s, `39.541513` p10;
- `40.170350` median tok/s, `39.767015` p10.

Both suites passed the fixed realistic gate with 12/12 unique prompts,
`cached_tokens=0` in every row, and token-ID timing for generated tokens
1-100. Ten independent exact-canary captures passed 10/10. The four worker
process maps were inspected and all loaded the selected custom `libccl.so`,
the virtual-environment `libsycl.so.8`, and its matching Unified Runtime
loader.

This supersedes the previous interpretation of the 40.135724 tok/s row. That
row remains useful speed evidence and its LocalMaxxing ID must remain in the
history, but it was submitted before consecutive changed-prompt repeatability
exposed deterministic wrong arithmetic (`1113` instead of `1073`) on the
unmodified large-SYCL-collective path. It is no longer the quality authority.

## Why this was difficult

Two independent defects were stacked:

1. The fused KV insertion path wrote the entire 512-element BF16 KV row and
   then issued a second unordered vector store for the final 64 RoPE elements.
   The stores overlapped. Their result could depend on device scheduling even
   though each individual kernel looked numerically correct in isolation.
2. After that source bug was repaired, the installed oneCCL fast SYCL path
   still produced deterministic bad prefill state on realistic graph runs.
   Generic collectives were correct but collapsed decode to about 8.56 tok/s.

The KV store fix is vLLM commit
`93fde4186b34d61e2d31ee258be282a8f768f3ed`: the first store is now masked to
the 448-element no-RoPE region, so no output byte has two writers. Low-level
changing-input gates passed 24/24 and exact service canaries passed 10/10 under
the safe collective path.

The collective problem was localized by routing selected operation families
and payload sizes. Large all-gather-only and reduce-scatter-only routes still
returned the wrong first token (`111`); large all-reduce-only routing restored
the correct `107`. The failing realistic arithmetic prompt has 18 prompt
tokens, making its hidden BF16 all-reduce payload approximately 147,456 bytes.
A 131,072-byte all-reduce ceiling therefore sends that prefill operation to
the safe path while leaving small decode all-reduces on the fast SYCL path.

## Size and collective-family evidence

| Route | Correctness | Strict median tok/s | Decision |
| --- | --- | ---: | --- |
| eager, global 16 KiB ceiling | 10/10 exact | 10.318548 | correct diagnostic; graph is mandatory |
| graph, global 16 KiB ceiling | 10/10 exact | 35.528183 | correct but broad routing costs decode |
| graph, global 64 KiB ceiling | 10/10 exact | 36.547846 | correct but still broad |
| graph, global 128 KiB ceiling | 10/10 exact | 36.620884 | correct but still broad |
| graph, all-gather-only 128 KiB | wrong first token (`111`) | not run | not the corrupt family |
| graph, reduce-scatter-only 128 KiB | wrong first token (`111`) | not run | not the corrupt family |
| graph, all-reduce-only 128 KiB, 2022 tree | 10/10 exact | 36.537575 | localization pass; wrong source release |
| graph, all-reduce-only 128 KiB, exact 2021.17.2 tree | 10/10 exact | **40.096205 / 40.170350** | promote |

The approximately 9% loss in the first custom builds was not the size gate.
Those builds came from a merged 2022.0.0 development/release line, while the
pip runtime that established the record is oneCCL 2021.17.2. Reapplying the
minimal route to exact tag commit
`66499938b7a8b615e26361c52900e7aec306ce50` recovered the performance.

The exact-tag CMake logic also inspected the GNU C compiler instead of the
DPC++ C++ compiler and therefore omitted BF16 vector support. The first
exact-tag runtime failed during BF16 all-gather warmup. Commit
`6da44bcb540f1005de88276dd86465cf5de4dc2f` adds guarded Intel LLVM version
detection; the route itself is commit `d764c2a`. This is why merely rebuilding
the nominally matching source was not enough.

## Promoted identity

- model: `0xSero/DeepSeek-V4-Flash-180B`, revision
  `7c360e1cd4a5168099dbc54d16d929bf6df04990`;
- vLLM: `93fde4186b34d61e2d31ee258be282a8f768f3ed`;
- XPU kernels: `de979b9328408302129c10ba04ed2fe090d414df`;
- oneCCL source worktree:
  `/home/steve/src/oneccl-2021.17.2-b70-sizegate` at `6da44bc`;
- runtime:
  `/mnt/fast-ai/runtime/oneccl-2021.17.2-b70-sizegate/lib/libccl.so.1.0`;
- runtime SHA-256:
  `bf9f2e447ebb8373d7b0a41b15a32f2518a670a107d6f8fd84474798d8f2301b`;
- route: `B70_ONECCL_SYCL_ALLREDUCE_MAX_BYTES=131072` and
  `ONECCL_FORCE_PRELOAD=1`;
- graph: PIECEWISE, XPU graph enabled, no forced communication capture;
- GPU memory utilization: `0.94` (the earlier 0.95 preload attempt failed
  admission because 28.64 GiB was available versus 28.78 GiB requested).

Primary evidence:

`/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/nospec-graph-oneccl1712-bf16-allreduce128k-preload094-cache-fix-20260715T1530Z`

The earlier preload failure was not an ABI failure. `libtorch_xpu.so` carries
an RPATH to the virtual environment, so changing only `LD_LIBRARY_PATH` also
cannot guarantee a side runtime is selected. The launcher now records the
selected path, resolved path, hash, thresholds, and preload policy. Absolute
`LD_PRELOAD` is required for this experiment, and `/proc/<worker>/maps` is the
final loaded-library proof.

## Importance and next boundary

This repair does not create a large decode speedup; it makes the existing fast
decode rate trustworthy. That is more important than another speculative
headline because every later fusion, collective, and MTP comparison now has a
stable oracle. It also prevents a broad generic-collective workaround from
being mistaken for the cost of correctness.

Do not continue generic threshold sweeps. They have localized the fault and
the exact-version recipe recovers the roof. The next nonspeculative candidate
must show at least 0.50 ms/token on an exact real-model gate before a service
load. The attached one-layer MTP remains a separate later lane; keep the base
path primary until it is materially closer to the user's 50 tok/s checkpoint.
