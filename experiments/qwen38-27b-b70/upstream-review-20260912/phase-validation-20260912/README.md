# PR #51565 full-builder CPU follow-up

**22/22 candidate tests pass; stock 14 pass and 8 fail.** This executes actual
complete builder methods with CPU dependency adapters. It is stronger than the
previous split-call-only test, but is not an installed-vLLM integration test,
CUDA graph execution, GPU kernel test, or deployment qualification.

Refreshed upstream identity:

- PR #51565 head: `53995de1e5781416206cabfc3ddf539611f82cc0`,
  `taking-lying-flat/vllm`; remains open.
- Current API base/main: `d8f840071efd631f71b06d4b31cb6dba2275a356`.
- These are different source trees, not a single-base one-delta A/B. The PR head
  predates some current-main changes. No merge/rebase or current-main port is
  validated by these tests.
- Source snapshots are upstream Apache-2.0 code with original notices retained.

## What actually executes

`test_full_builder.py` loads the complete `GDNAttentionMetadataBuilder` class and
metadata dataclass from the pinned source, including unchanged `__init__`, `build`
and `build_for_cudagraph_capture` bodies. All 17 upstream test cases execute with
their original assertions and test/factory bodies. Five further cases cover
persistent buffer reuse across requests, stale phase flags on zero-query padding,
and a mixed continuing/short-resumed/long-extend/fresh batch.

The split helper, convolution metadata builder, Mamba block-table helper, and FLA
chunk index/offset helpers are actual source functions extracted from the PR head.
All tensors are real CPU torch tensors. The fixture exercises cache mode `none`.

Dependency adapters, explicitly not tested:

- Top-level import plumbing is replaced; no installed vLLM or protected source
  tree is imported or mutated.
- Model configuration and backend resolution use minimal in-memory fixtures;
  the resolver selects Triton. No model download/loading or device discovery.
- CommonAttentionMetadata is a SimpleNamespace fixture implementing `replace`
  and computed-context subtraction, not the installed dataclass/cache lifecycle.
- `_init_reorder_batch_threshold` is a no-op, because scheduling/reordering is
  outside this metadata test. Input batch ordering is supplied by the fixture.
- Async copy maps to CPU `tensor.to`; pinned host allocation is ordinary host
  allocation; Triton integer cdiv uses equivalent integer arithmetic.
- Chunk-helper caching decorators are removed for extraction. Numerical GPU
  kernels and graph dispatch/capture/replay do not run.

This isolation avoids a full runtime import through the existing venv, whose
editable vLLM install points at the protected `/home/steve/src/vllm` tree.

## Results and replay

Interpreter: `/home/steve/.venvs/vllm-xpu/bin/python`, torch `2.11.0+xpu`;
CPU tensors only. From the repository root:

```bash
/home/steve/.venvs/vllm-xpu/bin/python -m pytest -p no:cacheprovider -q experiments/qwen38-27b-b70/upstream-review-20260912/phase-validation-20260912/test_full_builder.py
GDN_ARM=stock /home/steve/.venvs/vllm-xpu/bin/python -m pytest -p no:cacheprovider -q experiments/qwen38-27b-b70/upstream-review-20260912/phase-validation-20260912/test_full_builder.py
```

Logs: `candidate.log`, `stock.log`. Candidate 22 pass. Stock 8 failures are fresh
first-chunk classification, both fresh graph-staging cases, padded fresh request,
both reuse-buffer cases, and both stale-phase padding cases. Remaining 14 pass,
including resumed chunks, speculative mixtures and capture dummy metadata.
Ruff format/check pass (dynamic AST names/imports have documented lint exemptions).

## Decision and next gates

Evidence supports the intended metadata fix in existing #51565. Do not create a
competing PR. This test does not approve production or establish current-main
compatibility: first port the exact accepted delta onto the newly resolved
runtime; run the full installed upstream metadata tests in that isolated image;
then exercise graph-mode dispatch together with the separate uniform-decode fix.
Device validation should cover recycled fresh state, resumed/chunked/mixed
requests, padded graph replay, and target/MTP quality on the unchanged model.
Long-session incident resolution still requires the registered soak. No GPU,
services, shared runtime trees, Git branches/commits or remote writes were used.

## Same-base follow-up

The later [same-base confirmation](same-base/README.md) removes the different-tree
confound for these tests: exact PR diff applies cleanly without fuzz to pinned
main, and with current-main helpers yields stock 14 pass/8 fail versus candidate
22 pass. CPU dependency-adapter limitations remain.
