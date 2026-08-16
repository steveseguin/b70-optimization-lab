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
- The public SergiioB GPTQ/MTP route was captured and locally reproduced, but
  its GPTQ target failed a deterministic Python-result canary that Q8_0 and
  Q4_K_M passed. It is retained as research evidence, not the quality-default
  deployment.
- The mndodd, upstream llama.cpp, Intel driver/SYCL, Qwen3.6 lab, and public
  Qwen3.8 vLLM ideas have been inventoried. Neutral, negative, and unsafe
  experiments are kept so they are not accidentally repeated.

The immediate blocker is operational rather than conceptual. An experimental
peer-writing collective caused a Level Zero device-lost/reset storm and left
the current kernel warning-tainted. Both cards recovered to `normal`, but no
more GPU workload should run until a clean reboot.

## Next execution sequence

1. Reboot and run
   [`post-reboot-gpu-gate.sh`](../scripts/post-reboot-gpu-gate.sh). It fails
   closed unless the kernel is clean apart from the host's single audited
   boot-only KMS `dma_buf_vmap` warning, both B70s are `normal`, no model
   workload is active, and no Xe/GuC fault/reset/hang appears in this boot.
   Confirm both cards still expose their full 32 GiB BARs before the candidate
   benchmark.
2. Run only a one-token smoke of the already-built root-fused TP2 candidate.
   It keeps device-1 output work on device 1 and removes one device-0
   submission; it does not repeat the rejected cross-device output writes.
3. If the smoke is clean, bracket candidate and accepted mode 2 with identical
   short decode runs. Promote only a repeatable gain outside run noise.
4. If the bracket wins, run the complete 12-prompt cache-zero suite twice,
   require exact complete-output hashes, and rerun semantic/long-context
   canaries. Update the repro and model board only after those gates pass.
5. If it is neutral or unsafe, close it and move to a profile-driven kernel
   target. Do not spend another campaign on adapter, cache-row, sampling, or
   lossless-packing ideas already shown to be neutral or too small.

## Performance strategy

Forty Q8 tokens/s on TP2 requires about 572 GB/s of useful model traffic per
card, roughly 94% of the nominal 608 GB/s. That makes it a hard target: small
flag sweeps cannot supply the remaining gain. The credible target-only work is
to eliminate submissions, intermediate writes, and duplicate activation
quantization at the 128 recurrent/attention TP boundaries while retaining the
same FP32 reduction order and output bytes.

Work is ranked as follows:

1. root-fused collective boundary already staged and built;
2. new clean-boot profiling of the accepted stack to identify the largest
   remaining launch/stall buckets;
3. shape-scoped fused-Q8/down-projection handoff that keeps the accepted FP32
   boundary but avoids a materialize-and-requantize round trip;
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
