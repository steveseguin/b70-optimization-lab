# Qwen3.8 27B forward plan

Date: 2026-08-16
Scope: quality-preserving Qwen3.8 27B performance on Intel Arc Pro B70

Before opening an experiment, check the
[do-not-repeat index](../DO-NOT-REPEAT.md) and its two transferred Q8
notebooks.

## Plain-language state

The reusable Qwen3.8 work is already real:

- Q8_0 target-only TP2 reaches `36.772932 tok/s` conventional on two ASRock
  B70s, with no MTP, DFlash, draft model, prompt reuse, or speculation.
- Q4_K_M target-only TP2 reaches `49.717503 tok/s` conventional. It is faster
  because the weights are smaller, but it is a separate quantization choice,
  not proof that Q8 reached 40.
- Both promoted lanes use F16 KV, pass the cache-zero benchmark gate, preserve
  the complete-output oracle, and passed the Qwen3.8 semantic canaries.
- The same accepted Q8 stack sustains `57.398122 tok/s` aggregate for two
  synchronized requests (about `28.70 tok/s` each), exact to the two fixed
  cache-cold sequential oracles. This is a separately labeled c2 service
  result, not a replacement for the single-request record or a general quality
  guarantee. A disjoint prompt pair later diverged 0/2 under c2.
- The public SergiioB GPTQ/MTP route was captured and locally reproduced, but
  its GPTQ target failed a deterministic Python-result canary that Q8_0 and
  Q4_K_M passed. It is retained as research evidence, not the quality-default
  deployment.
- The mndodd, upstream llama.cpp, Intel driver/SYCL, Qwen3.6 lab, and public
  Qwen3.8 vLLM ideas have been inventoried. Neutral, negative, and unsafe
  experiments are kept so they are not accidentally repeated.

The reset-tainted boot was cleared. The clean-boot gate permits only the
host's audited one-time KMS warning, and the safer root-fused candidate was
tested without a compute fault. It regressed decode by `3.388%` and is closed.

## Next execution sequence

1. The clean-boot host-side census is complete: no standalone copies remain,
   and Q8 activation quantization is already almost entirely fused/deduped.
   Do not retry a generic materialize/copy/requantize removal.
2. Select a candidate that shortens or overlaps the fused MMVQ/collective
   critical path. Do not
   extend the device-0 root kernel or make device 1 wait for device-0-local
   RMS/Q8 work.
3. Preserve the accepted FP32 boundary and operation order. The selective
   256-GRF arm regressed by 2.789%, so retain the default compiler-selected
   register allocation.
4. Require a bounded smoke and position-balanced same-binary bracket before
   any endpoint work. Promote only a repeatable gain outside run noise.
5. For a winning bracket, run the complete 12-prompt cache-zero suite twice,
   require exact complete-output hashes, and rerun semantic/long-context
   canaries before updating the model board.

## Performance strategy

Forty Q8 tokens/s on TP2 requires about 572 GB/s of useful model traffic per
card, roughly 94% of the nominal 608 GB/s. That makes it a hard target: small
flag sweeps cannot supply the remaining gain. The credible target-only work is
to eliminate submissions, intermediate writes, and duplicate activation
quantization at the 128 recurrent/attention TP boundaries while retaining the
same FP32 reduction order and output bytes.

Work is ranked as follows:

1. Retain VDR4. The c2-specific VDR2 build regressed aggregate throughput by
   `2.981%` and changed one prompt across sequential/concurrent scheduling.
2. Do not publish c3/c4 as quality-cleared: they reach `77.212`/`91.895 tok/s`
   aggregate but fail the exact fixed-slot oracle. Retain c2 only as a narrow
   fixed-prompt capacity capture; its large-batch sweep also diverged on a
   disjoint prompt pair.
3. The hardware-control audit is closed: both cards reached their configured
   `2800 MHz` ceiling without a throttle reason, and exclusive scheduling is
   unsupported on this stack. No persistent setting was changed.
4. Q4_K_M concurrency and deep-prefill package as a separate production lane,
   using the verified `-b 8192 -ub 2048` prefill setting where it helps;
5. vLLM/FP8 only when the official artifact and Intel runtime pass the same
   semantic canaries—never by inheriting the rejected GPTQ result.

Every future headline must state model revision and SHA, quantization, GPU
count, reasoning mode/API mode, speculation status, KV type, exact server and
patch identity, conventional interval accounting, cache state, and quality
gate. A faster row that changes answers is a diagnostic, not a record.

## Publication status

The Q4_K_M `49.717503 tok/s` and Q8_0 `36.772932 tok/s` LocalMaxxing queues
both pass local preflight. Server dry-run and submission are waiting only for
the missing credential at `~/.config/localmaxxing/api_key` (or
`LMX_API_KEY`). Nothing should be posted until the authenticated dry-run
accepts the exact `ggml-org/Qwen3.8-27B-GGUF` identity.
