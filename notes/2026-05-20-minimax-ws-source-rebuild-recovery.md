# MiniMax WS source rebuild recovery

Date: 2026-05-20

## Summary

The promoted MiniMax WS llm-scaler path is reproducible from source again. The earlier rebuild/import segfault happened in a dirty source state, but the important reproducibility issue was patch application context: the promoted patch is rooted at `vllm/custom-esimd-kernels-vllm`, not the llm-scaler repo root.

Correct patch application:

```bash
git -C /mnt/fast-ai/src/llm-scaler-promoted-rebuild-20260520T120230Z \
  apply --directory=vllm/custom-esimd-kernels-vllm \
  /mnt/fast-ai/src/llm-scaler-promoted-rebuild-20260520T120230Z/promoted-llm-scaler.patch
```

Successful isolated workspace:

- Path: `/mnt/fast-ai/src/llm-scaler-promoted-rebuild-20260520T120230Z`
- Base commit: `4bfc0070090cc54afdb2d46b8e57882359141568`
- Rebuilt extension SHA256: `30b19be4456abab814f3378561204d575e4e8c01f848634a059d72ff3b23db66`

The rebuilt extension imports cleanly and exposes:

- `moe_forward_tiny_cutlass_nmajor_int4_u4_minimax=True`
- `moe_forward_tiny_cutlass_nmajor_int4_u4_minimax_ws=True`
- `moe_forward_tiny_cutlass_nmajor_int4_full_fp16_shared_from_logits=True`

## Validation

Strict gate artifact:

- `/home/steve/bench-results/minimax-m2.7-post-repro-optimization/ws-restored-quality-20260520T121119Z`

Quality passed:

- raw145 n64: `267cbf30208d84929ee79284ac695467f7e80597bf8694130e1e1f8b180eb5bd`
- raw145 n256: `58f6e8251c7a0a17e8c441278b5861f7d5da914fa1823ecd10484b296f2d7537`
- semantic-suite n64/r2: `adacbf144264486ea7d378ebb6a4c0ba23951b72c4cf86251a762b07ebef5805`
- arithmetic-repeat n64/r16: `578ec378bf31cb16fb49ac5c0043270fd00a0f7898e18ac498a41ffe775d7994`
- extended-sixpack n64/r2: `1e3560554f57b2b56cec8f49f28bc8ba12e9e0ced26bdc99a976f1433c99caa7`

Throughput, p512/n1536, ctx2048, MBT512, block256:

- Mean output tok/s: `87.964466`
- Mean total tok/s: `117.285955`
- Output repeats: `88.823285`, `88.889003`, `86.989162`, `87.156415`
- Total repeats: `118.431047`, `118.518670`, `115.985549`, `116.208554`

## Interpretation

This recovers a source-built, quality-clean WS path and unblocks future source optimization. It does not beat the promoted LocalMaxxing result of `89.314195` output tok/s, so it was not submitted as a new LocalMaxxing result.

The next optimization pass should first reduce measurement variance with a warm-repeat benchmark mode, then resume lower-level fusion work around real kernel/collective boundaries rather than Python wrapper-only changes.
