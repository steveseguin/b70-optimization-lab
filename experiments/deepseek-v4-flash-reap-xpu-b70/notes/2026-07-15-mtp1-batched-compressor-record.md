# DeepSeek V4 K160 MTP1 batched-compressor record

Date: 2026-07-15

## Outcome

A strided-batch FP32 compressor projection raises the target-verified MTP1
record from 54.464909 to **55.524496 tok/s**:

- strict headline: 55.524496 median, 52.029542 p10;
- independent strict support: 54.708889 median, 52.297798 p10;
- prior record: 54.464909 median;
- sustained exact gate: 20/20, including ten after both strict suites;
- every realistic and exact request reports `cached_tokens=0`;
- measured acceptance: 1,560/2,001, or 77.96%;
- LocalMaxxing: `cmrmgacdq1nmimj01i4sfqytp`.

Evidence:

`/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/mtp1-rowexact-bmm-w8a16-m2-candidate-20260715T2000Z`

## Mechanism

The previous correctness repair executed every M=2 verifier compressor as two
independent M=1 `torch.mm` calls followed by `torch.cat`. The new default-off
`VLLM_XPU_V4_COMPRESSOR_M2_BATCHED_EXACT=1` route keeps each row as a separate
batch item but uses one `torch.bmm` call with a stride-zero expanded view of the
same read-only weight:

```python
torch.bmm(
    hidden_states[:, None, :],
    weight.T[None, :, :].expand(2, -1, -1),
    out_dtype=torch.float32,
)[:, 0, :]
```

This removes one GEMM dispatch plus concatenation per compressor while keeping
the two rows independent. The original row-exact flag remains required and is
the outer safety gate.

## Hardware gate

The gate loads the real K160 layer-2 and layer-3 compressor weights, covering
the C4 M2/N2048/K4096 and C128 M2/N1024/K4096 shapes. On each of four B70s:

- 40/40 changing eager comparisons match two M=1 projections bit-for-bit for
  both shapes;
- 40/40 changed-input XPU graph replays match bit-for-bit for both shapes;
- the batched call is 1.84-1.91x faster than two M=1 calls plus concatenation;
- isolated 41-layer savings project to 1.964-2.046 ms per verifier cycle.

Raw artifacts:

`/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/compressor-m2-bmm-exact-card{0,1,2,3}-20260715.json`

The end-to-end gain is smaller because compressor work overlaps other streams.
The measured improvement is 0.45-1.95% across the two suites, which is still a
real record.

## Identity and quality

- vLLM: `3bd0eb32188357a4e1d631a8fe5bb529e065a048`;
- XPU kernels: `de979b9328408302129c10ba04ed2fe090d414df`;
- oneCCL: `6da44bcb540f1005de88276dd86465cf5de4dc2f`;
- libccl SHA-256:
  `bf9f2e447ebb8373d7b0a41b15a32f2518a670a107d6f8fd84474798d8f2301b`.

All workers mapped the selected libccl plus the virtual environment's matching
SYCL and Unified Runtime libraries. The two strict suites show the same
long-generation hash-repeatability pattern as the previous record: only the
two deterministic invariant prompts repeat byte-for-byte across suites, while
all six exact canaries remain stable through 20 ordered captures. This result
therefore does not claim full 128-token byte determinism; it passes the same
promotion contract as the preceding record.

K160 remains an experimental hash-pruned performance checkpoint, not the
quality-selected final DeepSeek V4 pack.

## Next action

Keep this service live on `127.0.0.1:18080`. The next bounded candidate is the
M=2 shared-expert clamp/SwiGLU plus FP8-quant producer: the current fused path
is explicitly M=1-only, and the prior M=1 service A/B saved about 0.55 ms.
Require exact changed-input M=2 output and at least 0.50 ms/cycle projected
savings before another TP4 load. A custom small-M W8A16 kernel is the next
larger pool after that; draft-only dense changes and N32/N128 MXFP4 retuning
remain closed.
