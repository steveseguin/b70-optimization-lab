# 2026-06-27T2248 - Q8 Reorder Pair-Slot Kernel Negative

## Question

Can Gemma4 MoE verifier throughput improve by computing selected expert slots
for the same token in one reordered-Q8 VDR2 workgroup, sharing the quantized
activation row load?

This is different from the known-negative grouped reordered-Q8 path: it does
not deduplicate experts across tokens and preserves both `[token, slot]`
outputs exactly.

## Patch

Default-off source patch in
`/home/steve/src/llama.cpp-gemma-record-repro-c926`:

- `ggml/src/ggml-sycl/mmvq.cpp`: add
  `ggml_sycl_mul_mat_vec_q_id_multi_token_pair_slots_q8_0_reorder()`;
- `ggml/src/ggml-sycl/mmvq.hpp`: declare the helper;
- `ggml/src/ggml-sycl/ggml-sycl.cpp`: add
  `LLAMA_SYCL_MUL_MAT_ID_Q8_0_REORDER_PAIR_SLOTS=1` dispatch and graph
  eligibility for `src0=Q8_0`, reordered, `ne11=1`, `n_experts_used=2`.

Important correction: the active Gemma 4 26B verifier shape observed in the
node profile is `ids ne=[8,2]` for the `ffn_moe_gate_up-*` `MUL_MAT_ID` nodes,
meaning `n_experts_used=8`, not `2`. With the current guard, this experimental
branch likely did **not** fire in the strict screen below. Treat the run as a
shape-mismatched/no-op-ish control, not as evidence about the pair-slot kernel's
raw speed.

The patch is default-off and was built in the existing VDR2 build directory:

```bash
cmake --build build-sycl-b70-aot-bmg-g31-q8reorder-vdr2 \
  --target llama-server -j 8
```

## Run

Run directory:
`data/gemma4-q8-gpu0-pairslots-vdr2-screen-n3-nmin2-p00475-ub1024-20260627T224855Z/`

Key identity:

- target/verifier:
  `/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`;
- draft:
  `/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/MTP/gemma-4-26B-A4B-it-Q4_0-MTP.gguf`;
- strict fresh-response realistic suite, each prompt once, `cached_tokens=0`;
- VDR2 reordered-Q8 record identity: `n_max=3`, `n_min=2`, `p_min=0.0475`,
  `UBATCH_SIZE=1024`, f16 KV, no n-gram/history acceleration;
- added env: `LLAMA_SYCL_MUL_MAT_ID_Q8_0_REORDER_PAIR_SLOTS=1`.

## Result

Strict gate passed, but throughput did not beat the promoted record:

- canary: 16 repeats / 64 rows, all pass;
- realistic final gate: pass, all `cached_tokens=0`;
- median tokens 1-100 after TTFT: **89.39584434969193 tok/s**;
- p10: `80.62685827385998`;
- mean: `88.12575811572829`;
- median full-512 after TTFT: `83.7701947076745`.

Current promoted record is **90.98312252660529 tok/s**, so this is not
promotable.

## Interpretation

Because the active shape is top-8, the run cannot be attributed to the
pair-slot kernel. Preserve the patch as a default-off, mis-specified experiment
artifact, but do not promote or submit it. If revisiting this idea, design for
the actual `n_experts_used=8` shape; be cautious, because accumulating multiple
expert slots per subgroup is likely to increase register pressure.

Next source lane: lower-level Q8 VDR2 direct-addressing specialization that
keeps the existing one-route-per-workgroup shape and only removes generic
trait/addressing overhead from the active reordered-Q8 MMVQ body.
