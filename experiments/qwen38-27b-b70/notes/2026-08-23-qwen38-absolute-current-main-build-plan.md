# Qwen3.8 absolute-current-main build plan

Date: 2026-08-23. Status: **build tooling ready; zero-overlay GPU
qualification not yet run**.

## First execution attempt

The first CPU-only `--build-all` attempt used vLLM
`2ec6f0d71ea3b350952630e310efcda1c744ff4d` and XPU kernels
`4543b580fecca68a7dd54ddaf6e444dc5f11a6a4`. The vLLM wheel built, and the
control image passed its static imports, Torch schemas, Rust-artifact identity,
and DSO linkage checks. The image build then stopped before export because the
guard for the official base's one known `uv pip check` defect expected the
words `but it is not installed`; the actual stable diagnostic says
`but it's not installed`.

This was a validation-harness wording defect, not a source, binary, GPU, or
performance failure. No GPU was exposed and no immutable result tag was
created. The failed attempt is preserved at
`/home/steve/builds/qwen38-current-main-20260824T015706Z-2ec6f0d71e-4543b580fe/`;
the corrected guard continues to accept that exact optional-NIXL diagnostic
and nothing broader.

## Non-negotiable update rule

The newest literal upstream `main` is the base, not a replacement for the
lab's accepted optimization work. Historical results, patches, decision
caches, binaries, and performance highs remain append-only. Each still-needed
accepted behavior is forward-ported as a separately identified overlay and is
promoted only after matched correctness and performance gates pass.

The build script
[`build-20260823-qwen38-absolute-current-main-images.sh`](../scripts/build-20260823-qwen38-absolute-current-main-images.sh)
implements the first two zero-overlay identities:

1. literal-current vLLM plus the stock kernel from the immutable official base
   (the attribution control);
2. literal-current vLLM plus the official exact-current XPU-kernel wheel (the
   both-head zero-overlay baseline).

It refuses dirty or non-`main` source trees, fast-forwards only to a freshly
resolved upstream `main`, refuses to overwrite an existing image tag, copies
the unchanged Rust artifacts only after a source-equivalence check, builds a
real vLLM wheel rather than using a source mount, and rechecks both remote
heads after the images are built. A main-head change during the build makes
the result stale-before-qualification instead of silently relabeling it.

## Exact upstream kernel artifact

The official project already built the current kernel head, avoiding a risky
local full-kernel compile for the baseline:

- kernel head: `4543b580fecca68a7dd54ddaf6e444dc5f11a6a4`;
- successful GitHub Actions run: `32440448665`;
- artifact ID/name: `9432931548`,
  `vllm-xpu-kernels--20260821-024021`;
- wheel:
  `vllm_xpu_kernels-0.1.dev1+g4543b580f-cp38-abi3-manylinux_2_28_x86_64.whl`;
- wheel SHA-256:
  `1adf261d472ec9f0ee6f05fcefaa90de7336654955f812b0c37dac2cead06c8a`;
- uncompressed wheel payload: 2,402,400,975 bytes, including every required
  extension and auxiliary DSO;
- build-info SHA-256:
  `d970b44b6c47cc669778aadbd0ca4023b7d339f7ec7ea3e6f5885d2984a3117b`;
- artifact recovery directory:
  `/mnt/usb-models/llm-optimization-artifacts/qwen-current-main-transition-20260823/upstream-kernel-4543b580-artifact-9432931548/`.

The official wheel used the repository's full attention configurations. The
current-source hashes are
`6091d2b7cda8340333beb26d6dde09c45689c1fd19e5a9e77352d8dedb7cbc59`
for `chunk_prefill_full.conf` and
`2c46aea68f7d70a0e40acd3de15a4afefe5c9f2ff0f105592d8a7d0c828bcebc`
for `paged_decode_full.conf`.

Its shallow-checkout package version is
`0.1.dev1+g4543b580f`, which does not satisfy vLLM's public
`vllm-xpu-kernels==0.1.13.2` metadata pin even though its source identity is
newer and exact. Static validation accepts only that exact metadata mismatch,
plus the official base's pre-existing optional `nixl-cu13` mismatch. A local
overlay build will use a pin-compatible `0.1.13.2+g<head>` version and must not
repack or rewrite this official baseline wheel.

## Overlay disposition

Current upstream already contains the native Qwen GDN-MTP transaction, split
speculative convolution/delta paths, graph eager break, safety bounds/fences,
and opaque custom-op collectives. Those changes are tested as upstream code;
their old private forms are not replayed.

Two accepted performance behaviors are still absent and remain scheduled as
separate, default-off forward ports after the zero-overlay baseline:

1. target runtime INT8 LM head with BF16 scales;
2. draft runtime group-128 INT4 LM head with BF16 scales and an explicit
   target/draft role so equal weights cannot accidentally cause head sharing.

ReplaySSM, persistent graph scratch, force-chunk decode, and the old compiled
all-gather/oneCCL overrides are not default ports. They are obsolete, unsafe,
or potentially speed-lowering on the current design and may return only after
a current-source mechanism oracle proves a need.

## Qualification order and protected floors

No built image is record-grade until GPU qualification completes in this
order:

1. current-vLLM/stock-kernel target-only TP1;
2. both-current zero-overlay target-only TP1;
3. both-current plus accepted overlays, one delta at a time, TP1;
4. quality-clean TP2;
5. quality-clean TP4;
6. graph+MTP sentinel, then the MTP/context matrix.

The target-only promotion floors remain:

| Topology | Diagnostic floor | Strict floor |
|---|---:|---:|
| TP1 | 30.2178 | 30.31067504052998 |
| TP2 | 48.8301 | 49.01965141150585 |
| TP4 | 71.5488 | 71.29326283364946 |

TP4 additionally requires at least one same-identity strict repeat at or above
`71.39843006187554 tok/s`. Quality, token IDs, cache-zero, graph, baseline,
8K needle, and cache-immutability gates remain conjunctive. A lower current
result is useful diagnostic evidence but never replaces the certified high.

After the target-only column passes, test the upstream split-K speculative
route first. Use `VLLM_XPU_SPEC_DECODE_MAX_QLEN=1` only as an attribution
sentinel. The local-accessor/completion-barrier attention patches return only
if the failure follows the chunk route; global force-chunk remains excluded
because it can lower long-context performance.
