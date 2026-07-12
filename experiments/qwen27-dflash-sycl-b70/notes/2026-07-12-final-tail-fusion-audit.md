# Qwen27 final-tail fusion audit

## Actual graph

The target and intrinsic-MTP head both end in:

1. RMS norm of the final hidden state;
2. multiply by the learned output-norm weight;
3. optional output-row selection;
4. Q4_0 x F32 LM-head `MUL_MAT` (internally quantized to Q8_1 by SYCL MMVQ);
5. backend sampler operations.

The weighted norm result is not a disposable intermediate. Qwen3.6 publishes
it as both `t_h_nextn` and `t_embd`; `llm_graph_result::set_outputs()` marks it
as an output. The intrinsic draft consumes the target `h_nextn`, so a fusion
that only produces private Q8_1 input for the LM head breaks MTP state/data
flow.

For greedy/temp-0 backend sampling, llama.cpp already appends one device
`GGML_OP_ARGMAX` to the logits and asynchronously copies one token ID to the
host. Normal stochastic sampling builds further backend operations from the
full logits. Speculative verification also needs per-position target logits.
Consequently, an LM-head epilogue that omits the logits is not semantics
preserving for the production path.

## Safe remaining boundary

The safe final-head fusion is a dual-output kernel:

- read the final hidden row once;
- compute RMS scaling and learned-weight multiplication;
- write the required F32 `h_nextn`/embedding output;
- simultaneously produce the Q8_1 (standard or reordered) LM-head input.

The LM-head MMVQ then consumes that Q8_1 buffer. This replaces RMS norm,
elementwise multiply, and activation quantization with one launch while
preserving the observable F32 tensor and all logits/sampler semantics. The
skipped unweighted RMS allocation is large enough to serve as fixed-address
Q8_1 scratch for M=1/4/8/16.

This should be a separate default-off flag and matcher, rather than weakening
`GGML_SYCL_FUSE_MMVQ_ADD_RMS_Q8`: the existing fusion is allowed to discard its
F32 norm result, whereas the final-head variant must write it. It should reject
non-contiguous output rows, split-device buffers, unsupported MMVQ dispatch,
observable unweighted-RMS tensors, and graphs with consumers other than the
LM head and required output aliases.

## Decision

No sampler/logits fusion was implemented in this audit. Folding argmax into
the LM-head kernel would still require a cross-workgroup reduction or a second
kernel, and preserving full logits means it removes at most the existing
single argmax launch. Eliding logits would change speculative and stochastic
sampler semantics.

Implement the dual-output final RMS+weight+Q8 kernel only after the recurrent
per-layer fusion work. It removes two launches once per target/draft head, not
multiple launches per layer, so it cannot materially close the current gap to
68 tok/s by itself.
