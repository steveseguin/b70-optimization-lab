# 79bb untreated TP1 qualification r2: corrected host-gate preregistration

Date: 2026-08-24. State: preregistered, not yet launched.

## Purpose and unchanged qualification contract

This is one infrastructure-corrected retry of the atomic program frozen in
[`2026-08-24-qwen38-79bb-untreated-tp1-prereg.md`](2026-08-24-qwen38-79bb-untreated-tp1-prereg.md).
The first attempt closed before any candidate container or model arm because
the host-only XCCL gate mixed incompatible runtime libraries. Its raw root and
classification are preserved in the
[`failure note`](2026-08-24-qwen38-79bb-hardware-gate-mixed-runtime-failure.md).

The source and image identity remains exactly:

- vLLM `79bb395eea64dbfef99a55f010d2854db71f8571`, tree
  `3dc459a78f843186bb8a510631f9f1d34448a243`;
- XPU kernels `baaa05bb4e92901219a5a072dd63f2474896f6d1`, tree
  `e7e7d1063f232a383c98c1820cebb94c45b4906e`;
- official nightly base
  `sha256:3ee0ec37825cc03e866a75198e6fee2a201efb68a717852ed35737a3ae59f876`;
- zero-overlay both-current image
  `sha256:786681b8aa4150d30e12af93b3038a03daba110719bf650a5c9d7c8804e0bdf3`;
- host kernel `7.0.0-30-generic`, boot
  `086de284-0771-4269-9cb2-e064fe303e40`.

All live identities must be resolved again after the correction is committed
and immediately before launch. Any upstream head, nightly digest, image,
kernel, boot, or lab-commit movement closes this packet stale and requires a
new build or preregistration as appropriate.

The candidate benchmark contract is unchanged: exactly three serialized
untreated TP1/GPU0 arms, MTP0, F16 KV, 32K maximum length,
`FULL_AND_PIECEWISE` graph sizes `[1,2]`, sequence count 1, 1024 batched
tokens, memory utilization 0.90, async scheduling, prefix cache off, chunked
prefill on, returned token IDs, and `PYTHONHASHSEED=0`. The diagnostic floor
remains `30.2178 tok/s`; both strict replay floors remain
`30.31067504052998 tok/s`. The exact quality, canary, model, cache, response,
freshness, cleanup, journal, and frozen-interpretation gates from the original
preregistration remain binding. No decision, source, DSO, binary, generated
kernel, or cache overlay may run.

The benchmark runner must retain SHA-256
`cec5f3d852c84255822a4a5ee14d6829cd5efa6719ff9e8c59a904090d11c2b0`.
The corrected hardware-gate runner must retain SHA-256
`84b9f5025476f40cb3218dbe513718c6d37da1e4852d17031b403fa410e4c506`.
The correction does not touch its successful timing path or any protected
historical result.

## Exact infrastructure correction

The hardware prefix may run once on the fresh root:

```text
/home/steve/qwen38-current-main-runs/postreboot-hardware-gate-79bb-20260824-086de284-venvlib-r2
```

If it passes, the three model arms use the fresh root:

```text
/home/steve/qwen38-current-main-runs/tp1-untreated-79bb-20260824-r2
```

The corrected health gate changes only these fail-closed infrastructure
checks:

1. `sycl-ls` and the standalone peer binary retain the system oneAPI 2026
   runtime they were built for.
2. Host Torch compute and XCCL use only
   `/home/steve/.venvs/vllm-xpu/lib` as `LD_LIBRARY_PATH`, keeping Torch,
   SYCL, oneCCL, and the UR loader from one coherent virtualenv.
3. The gate hashes `libtorch_xpu.so`, `libsycl.so.8`, both oneCCL DSOs, and
   `libur_loader.so.0`, records `ldd`, and requires each critical library to
   resolve to its frozen virtualenv path before touching a GPU.
4. Each expected init, barrier, and `allreduce ok 4.0` marker must occur
   exactly once as a fixed substring, so interleaved rank output cannot create
   a false whole-line failure.
5. Kernel rejection now includes generic segfaults. The summary exposes the
   reached failure stage and gate-complete state, and finalization always
   records post-attempt taint.

The collective command, four ranks, single barrier, single one-element FP16
all-reduce, numeric oracle, 180-second bound, device mask, network interfaces,
locks, and no-selector-plus-mask rule remain unchanged. There is no internal
retry. Any nonzero command, wrong marker count, journal reject, stale identity,
cleanup failure, or sealing failure closes r2 as failed-incomplete and no model
arm runs.

## Frozen interpretation and continuation

The original outcome rules remain exact. A full untreated pass authorizes a
new TP2 preregistration on this same source/image identity, then TP4. A
completed speed miss with every non-speed gate clean preserves the measurements
and stops without an overlay; only then may a new 79bb compatibility packet be
derived. Any other failure is not performance evidence.

No r2 outcome lowers or replaces the protected diagnostic
`30.2178 / 48.8301 / 71.5488` column, its captured highs, the strict TP1/TP2
floors, or the two-part TP4 strict floor. Current-main site cells remain
pending until actual current-main measurements exist; this infrastructure
failure cannot close or mark them unsupported.
