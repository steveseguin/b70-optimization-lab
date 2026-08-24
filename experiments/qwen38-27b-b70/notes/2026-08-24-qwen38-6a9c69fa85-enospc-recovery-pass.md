# 6a9c absolute-current ENOSPC receipt recovery pass

Date: 2026-08-24. State: **recovery passed; static evidence only; GPU
qualification pending.**

The single preregistered report-only recovery ran once from clean pushed
`main` at commit `521f3acdef61481ca1dad700543a8933f5b73c23`. It completed
at `2026-08-24T19:30:48Z` without building, pulling, retagging, removing an
image, exposing a GPU, loading a model, compiling a model cache, benchmarking,
or making a quality request.

The recovered aggregate receipt is tracked byte-for-byte at
[`2026-08-24-qwen38-6a9c69fa85-absolute-current-main-build.json`](../data/2026-08-24-qwen38-6a9c69fa85-absolute-current-main-build.json),
SHA-256
`a7b2d9a4fa1693c4ca83e98a494b249a380087963702c0f30cf558bb889400f3`.
It remains explicitly unqualified:
`static-preflight-passed-for-built-images-gpu-qualification-pending` and
`promotion.qualified=false`.

The inert USB archive is:

```text
/mnt/usb-models/llm-optimization-artifacts/qwen-current-main-transition-20260823/current-main-builds/20260824T185928Z-6a9c69fa85-baaa05bb4e
```

Its `SHA256SUMS` SHA-256 is
`b65dbf867d860e123576e5da62b00a63da72cbb55655f1ef06a6974cdd401c5e`.
All 18 covered members pass and the archived receipt is byte-identical to both
the build-root and tracked receipts. The separately bound failure snapshot is
`40947d134e2f68675cfda90fce7702908109f51f53ddf83001fea6e2feed0db5`;
it preserves the original zero-byte tag boundary and the exact ENOSPC error.

Three independent read-only audits and the local postflight agree:

- live vLLM `6a9c69fa851389dcf1ee5d3a2363e27af665d26d`, XPU kernels
  `baaa05bb4e92901219a5a072dd63f2474896f6d1`, and nightly digest
  `sha256:3ee0ec37825cc03e866a75198e6fee2a201efb68a717852ed35737a3ae59f876`
  remained exact;
- both immutable image IDs, tags, entrypoint, selector exclusions, and all 21
  labels per image passed;
- the complete protected performance ledger stayed exact at canonical SHA
  `e6ee2cb9908ce940087788243eac5b544c0d2831b94efa47fe6441232c740e8f`;
- all 78 TP2 and 152 TP4 decision files reverified against manifests
  `65c574c24d24804d250e5179e9a202ec9e77e8c5740cea121b7660d8ee854757`
  and `a2df36339567d2619e024351deeca98970ebf92497db0148eac0de7dd5df3ba2`;
- no decision was applied to either zero-overlay image, no captured speed was
  changed, and no performance claim was created;
- no container, server, benchmark, or GPU holder remained, and root free space
  stayed above 17 GiB.

The next gate is procedural and strict: commit and push this exact tracked
receipt and closeout, then derive a fresh-root TP1 packet that explicitly names
the 6a9c receipt. The old wrapper defaults and the 342b packets must not run.
Re-resolve vLLM, XPU kernels, and the nightly digest before packet commit and
again immediately before launch. A moving identity closes 6a9c as dated; it
does not authorize lowering any speed floor or discarding an accepted decision.
