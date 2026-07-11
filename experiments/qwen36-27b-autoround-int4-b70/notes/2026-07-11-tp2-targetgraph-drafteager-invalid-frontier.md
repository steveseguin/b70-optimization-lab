# 2026-07-11 - TP2 target-graph / draft-eager frontier is fast but invalid

## Status

This is a high-value diagnostic frontier, **not a valid result and not a
LocalMaxxing candidate**. It obeyed the strict fresh-response benchmark
mechanics and reached `79.53482335166211 tok/s`, but failed repeat64 and the
1K needle quality gate.

The current valid headline remains the TP1 ReplaySSM result at
`68.23626314761921 tok/s`.

## Exact configuration recovered from the session ledger

- checkpoint: `webhie/Qwen3.6-27B-int4-AutoRound`, snapshot
  `f5750c90b3776db658594df5fe8051098226dd8e`;
- TP2 on two B70s, `max_model_len=2048`, `max_num_seqs=1`,
  `max_num_batched_tokens=1024`;
- intrinsic MTP3;
- target `PIECEWISE` XPU graph with capture size `8`, forced communication
  capture, and no-op communication capture enabled;
- draft graph disabled with `VLLM_XPU_DRAFT_DISABLE_CUDAGRAPHS=1`;
- ReplaySSM cache8, native recurrent path, native stage-conv,
  commit-in-forward, and PyTorch slot management;
- runtime INT8 target LM head with BF16 scales;
- runtime INT4 group128 draft LM head with BF16 scales;
- oneCCL OFI transport, topology P2P access enabled, PIDFD IPC exchange.

The exact runnable wrapper is
`../scripts/run-tp2-targetgraph-drafteager-candidate.sh`. It defaults to the
full 512-token strict suite plus repeat64 quality, and the generic candidate
harness now snapshots the dirty vLLM/kernel diffs and runtime binary hashes in
the raw run directory.

## Speed evidence

Artifact:
`data/qwen36-27b-autoround-int4-b70-baselines/qwen27-tp2-mtp3-targetgraph-drafteager-full512-promotion-20260711.json`

- 12 unique realistic prompts, each sent once;
- `cached_tokens=0` for all 12 requests;
- 512 generated token IDs for every request;
- median tokens 1-100 after TTFT: `79.53482335166211 tok/s`;
- p10: `72.39039083841648 tok/s`;
- mean: `79.85401870134352 tok/s`;
- median TTFT: `723.8815014716238 ms`.

The filename contains `promotion`, but the result must not be promoted because
the separate quality gate failed.

## Quality failure

Artifact:
`data/qwen36-27b-autoround-int4-b70-baselines/quality-qwen27-tp2-mtp3-targetgraph-drafteager-repeat64-ctx1024-20260711.json`

- exact short controls: pass and baseline match;
- repeat64: fail, with three unique hashes;
- repeat index 8 produced a corrupted continuation after `blue, green`;
- repeat index 20 duplicated `green`;
- 1K needle: fail, returning `B70_QW36_NEEDLE_20260609` instead of
  `B70_QWEN36_NEEDLE_20260609`;
- all requests reported `cached_tokens=0`, so this is not benchmark caching;
  it is a runtime correctness failure.

The fully eager TP2 control passed the same quality suite:
`data/qwen36-27b-autoround-int4-b70-baselines/quality-qwen27-tp2-eager-control-repeat64-ctx1024-20260711.json`.
That isolates the current blocker to the compiled/graph target path rather
than TP2 arithmetic or the base ReplaySSM transaction itself.

## Next controlled bisection

1. Reproduce this exact fast/invalid lane from the dedicated wrapper.
2. Test `VLLM_XPU_SKIP_COMPILED_SPEC_DECODE=1` while preserving target graph
   for ordinary decode and keeping the draft eager. This distinguishes the
   compiled packed verifier from graph replay.
3. If that is exact but too slow, narrow the eager boundary to only the
   recurrent GDN/ReplaySSM mutation or fix its static-buffer/stream ordering;
   do not disable the complete target graph permanently.
4. Require repeat64 and the 1K needle before spending a strict speed
   confirmation. If the speed delta is small, use paired/crossover runs across
   both two-GPU pairs to resolve variance.

No submission is allowed until strict fresh throughput and the complete
quality gate pass in the same source/config identity.
