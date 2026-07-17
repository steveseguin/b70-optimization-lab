# MTP1 isolated M=2 gather/shared-add closure

Date: **2026-07-16**

Status: **bitwise exact; incremental saving is noise-floor; no service load**

## Decision

Do not add fixed-M=2 routed-gather/shared-output fusion to the QNorm-M2 + N128
portfolio. The transplanted operator is exact, but its conservative isolated
incremental saving is between `-0.0049` and `+0.0038 ms/cycle` across the four
B70s. That is far below the predeclared `0.25 ms/cycle` threshold for spending
a 103 GB TP4 service load.

No LocalMaxxing submission was made. The qualified MTP1 record remains
**63.349928 tok/s** with QNorm maximum M=1 and MXFP4 N64.

## Why the old estimate was not admissible

The earlier gather/shared-add note reported a `0.448-0.470 ms/cycle` worst-route
ceiling. That candidate also contained the unpromoted compact route-direct
scheduler. The scheduler overlaps and conflicts with the N128 grouped-MXFP4
portfolio component, so the old headline could not be added to the portfolio.

Difference-of-differences in the old card-0 evidence suggested only about
`-0.0023` to `+0.0772 ms/cycle` belonged to gather/add itself. This experiment
therefore transplanted only the exact gather/add operator onto the current
portfolio source and measured it directly against the production generic
gather followed by BF16 addition.

## Preserved implementation

- XPU branch: `codex/deepseek-v4-m2-portfolio-gather-add`;
- XPU kernel commits: `7b800ca`, `4acfd34`;
- XPU plumbing commit: `5d1a72e`;
- vLLM branch: `codex/deepseek-v4-m2-portfolio-gather-add`;
- vLLM plumbing commit: `eb4e39b4d`;
- selector: `VLLM_XPU_V4_M2_GATHER_SHARED_ADD=1`.

The vLLM path peeks at the completed XPU `SharedExperts` output, passes it into
the fused gather, consumes the shared-output lifetime slot exactly once, and
suppresses the later Python shared+routed addition. The final TP reduction is
unchanged. The selector defaults off.

## Isolated four-card gate

The reusable probe is
`../scripts/probe-m2-gather-shared-add.py`. It compares:

- control: generic `moe_gather` BF16 output, then BF16 `torch.add`; and
- candidate: one `moe_gather_shared_add_m2` submission preserving the routed
  FP32 accumulation -> BF16 rounding -> shared BF16 addition -> BF16 order.

Every card passed **140/140** changed fixed-address graph cases across same,
disjoint, overlap, duplicate, single-local, six-local, and all-remote routes.
Both separate-output and shared-output-alias forms were bitwise exact.

| Physical B70 | Conservative ms / 43 layers | Best route ms / 43 layers |
| --- | ---: | ---: |
| 0 | +0.003779 | +0.052803 |
| 1 | +0.000067 | +0.029817 |
| 2 | -0.004886 | +0.034222 |
| 3 | -0.000682 | +0.037084 |

Raw results are under
`../../../data/deepseek-v4-reap-m2-gather-shared-add-isolated-20260716/`.

The operator removes one graph node, but these 8 KiB BF16 rows are small and
the fused kernel still performs essentially the same data movement and
arithmetic. Graph replay makes the eliminated launch worth much less than the
old mixed-package estimate implied.

## Portfolio implication

The portfolio approach remains valid, but it does not make overlapping or
noise-floor projections additive. A component must have a freshly isolated,
non-overlapping lower bound on the actual portfolio source before its saving
enters the sum.

The frozen inventory now contains no additional exact component with positive
service evidence or a conservative `>=0.25 ms/cycle` incremental gate. The
next portfolio addition must come from a new architectural boundary or a new
complete-cycle measurement; do not revive native dual RMSNorm, M2 in-place
all-reduce, draft local argmax, output alias, or collective tuning, all of which
already have negative service evidence or interaction risk.
