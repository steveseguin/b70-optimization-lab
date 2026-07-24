# Laguna M8 direct-XCCL runtime graph: terminal negative

Date: 2026-07-24 America/Toronto

## Result

The frozen direct-collective graph probe failed cleanly and the direct-capture
branch is closed.

All four ranks reported the same terminal boundary on changing-input replay
sample 2:

```text
raw final all-reduce mismatch
```

The command exited 1 without its 240-second outer timeout, device loss, or a
stranded process. A post-run `xpu-smi ps -j` showed only the querying
`xpu-smi` process on all four cards.

Because the probe checks each boundary in order, the retained control flow
shows that both sample 1 and sample 2 passed all 97 raw gathered tensors and
all 97 literal fixed-rank BF16 sums before every rank reached the failing final
all-reduce assertion. Sample 1 also passed the final all-reduce. The first
observed stale or changed boundary is therefore localized to direct replay of
the final XCCL all-reduce. This is not evidence that a full target graph is
exact.

## Identity and evidence

- preregistration:
  [2026-07-24-m8-xccl-direct-runtime-graph-preregistration.md](2026-07-24-m8-xccl-direct-runtime-graph-preregistration.md);
- tool commit: `d9e88ff060c9b98dd169547d6aeb9ae31f55c629`;
- tool SHA-256:
  `1797ae4df5f61f6583fa0ba8942cac7e212f4dfbdc36a28e971734d4f89f264f`;
- run root:
  `/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-m8-xccl-direct-graph-d9e88ff06-20260724T141124Z`;
- structured result:
  `data/laguna-m8-xccl-direct-runtime-graph-negative-20260724.json`.

Each rank left an immutable 0444 failure marker. Their SHA-256 values are
recorded in the structured result.

## Decision

The unchanged direct-capture probe will not be rerun. Direct recording of all
98 collectives is rejected for this stack.

The runtime-command-graph hypothesis remains open only in the segmented form:

1. keep every one of the 97 all-gathers and the final all-reduce eager;
2. give each collective caller-owned persistent input and output buffers;
3. capture only the unchanged noncollective kernels between those boundaries;
4. enforce the committed recursive tensor identity guard on every replay;
5. require changing-input raw-byte equality on all four cards; and
6. stop before an endpoint unless tracing shows at least 75% fewer
   noncollective direct submissions and paired component timing saves at least
   1.0 ms/cycle on every card and 1.5 ms/cycle fleet median.

No model was loaded, no endpoint or generation ran, and no payload or
LocalMaxxing submission was created. The approved record remains
`33.89498511171744 tok/s`, LocalMaxxing
`cmrx6p5dv001bo4017hb7sixz`.
