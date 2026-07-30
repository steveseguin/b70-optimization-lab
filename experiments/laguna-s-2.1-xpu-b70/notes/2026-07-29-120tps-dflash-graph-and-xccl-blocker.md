# Laguna BF16 120 tok/s push: length-generic DFlash graph candidate and XCCL blocker

Date: 2026-07-29 America/Toronto

Status: **candidate implemented and CPU-tested; TP4 measurement blocked before
candidate execution by a classified collective-stage failure.**

## Objective and constraint

Reach 120 conventional tok/s without changing the target, lowering quality,
warming/reusing prompts, changing the fixed realistic suite, or relaxing the
13/13 canonical-q1 exactness gate.

The incumbent remains:

- BF16 KV;
- width 12 / DFlash depth 11;
- E4M3FN W8A16 for 31 disposable DFlash projections;
- `VLLM_XPU_LAGUNA_SCALE_VEC=1`;
- `VLLM_XPU_LAGUNA_DEQUANT_MAD=0`;
- median `102.134914` conventional tok/s over 13 exact/cache-zero legs.

The required gain is about 17.5% over the incumbent median. The active
prefetch-distance campaign was stopped because its observed movement was
noise-class and, even if real, could not close that gap.

## Candidate

The drafter runs eager at roughly 9.0 ms of an approximately 30.5 ms cycle.
Earlier graph attempts failed at 0/13 because warmup captured attention with
`max_seq_len=12`, then replayed that launch at real context lengths.

The new candidate captures DFlash attention using `max_model_len=8192` as the
launch-safe upper bound while retaining:

- fixed-capacity persistent block-table, query-start, sequence-length, and
  slot-mapping buffers;
- static-input enforcement;
- full-capacity block-table shape;
- the target's unchanged 146/145 topology audit;
- default-off activation through
  `VLLM_XPU_LAGUNA_DRAFT_BREAKABLE_GRAPH=1`;
- a runtime marker proving the capture width and maximum sequence length.

This follows vLLM's newer native `DFlashCudaGraphManager`, which also builds
capture metadata with `max_seq_len=max_model_len`.

Candidate source:

```text
worktree=/home/steve/src/laguna-vllm-dflash-graph-bf16-20260729
branch=experiment/laguna-dflash-graph-bf16-20260729
commit=d606d60cf
```

Targeted CPU gate:

```text
tests/models/test_laguna_dflash_context_kv_workspace.py
60 passed
```

The candidate commit changes only:

- `vllm/v1/spec_decode/dflash.py`;
- `vllm/model_executor/models/laguna_dflash.py`;
- `tests/models/test_laguna_dflash_context_kv_workspace.py`.

## Interrupted prefetch evidence

Five completed campaign legs were preserved:

| arm | round | conventional tok/s | exact |
| --- | ---: | ---: | --- |
| old | 1 | 100.904798 | 13/13 |
| new-pd6 | 1 | 100.445530 | 13/13 |
| new-pd12 | 1 | 99.050769 | 13/13 |
| new-pd3 | 1 | 101.684689 | 13/13 |
| old | 2 | 101.661279 | 13/13 |

The `new-pd6` round-2 leg is not evidence. It produced no benchmark artifact
and failed with an `execute_model` RPC timeout:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/
  pfreach-new-pd6-r2-20260729T025138Z
```

## Candidate attempt: did not reach candidate code

Formal run:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/
  laguna-dflash-maxlen-20260729T043226Z
```

Identity was BF16 KV, width 12/depth 11, frozen incumbent grouped-GEMM binary,
FP8 draft projections, `SCALE_VEC=1`, and only the corrected drafter graph
enabled.

The run stalled during four-rank XCCL initialization. Successful controls move
from `distributed_init_method` to model loading in roughly three seconds. This
run made no log progress for more than four minutes and never reached model
loading or the new DFlash capture marker. It was stopped through the formal
leg's cleanup trap. It is neither a pass nor a failure of `d606d60cf`.

## One corrected probe: classified host boundary

Exactly one corrected minimal probe was run after all vLLM processes exited:

```text
artifacts=/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/tmp/
  xccl-gate-20260729-BmAx62/probe-dflash-gate
interface=eth1
```

Every rank proved:

```text
import-done
device-set Intel(R) Arc(TM) Pro B70 Graphics
pg-initialised
tensor-allocated
all_reduce-start
```

No rank returned from `all_reduce`. Final marker:

```text
PROBE_RESULT=COLLECTIVE_STAGE_FAILURE clean_teardowns=0/4
```

This is executed and classified evidence. No driver reload, FLR, shared-memory
deletion, repeat probe, or other recovery action followed.

## Recovery and resume

A clean reboot is the conservative next action. After reboot:

1. verify strict device/process idle;
2. run exactly one fresh corrected collective probe;
3. require `PROBE_RESULT=PASS clean_teardowns=4/4`;
4. launch one formal `d606d60cf` candidate leg;
5. require four `length-generic attention metadata` runtime markers with
   `query_width=12 max_seq_len=8192`;
6. reject flat acceptance, any missing graph replay, any topology drift, or
   anything below 13/13 exact/cache-zero/text-hash equality;
7. only then interpret throughput.

If the graph is exact and its conventional rate is promising, measure it
interleaved against the frozen `46a88e0` incumbent. Do not report the first
high draw as 120; promote only a repeated median win.

## Post-reboot draft-graph results

The reboot restored the four-rank probe:

```text
PROBE_RESULT=PASS clean_teardowns=4/4
```

The length-generic warmup candidate then ran, but was rejected:

| candidate | result |
| --- | --- |
| max-model-length attention metadata | 0/13 exact; median 540.006 tok/s; token id 0 after capture |
| retain final graph output | 0/13 exact; median 535.338 tok/s; first request plausible, later requests flat 100% acceptance |
| retain output + materialize graph/eager boundaries | rejected early; later requests again flat 100% acceptance |

The apparent 535–540 tok/s rates are corrupt-output artifacts and must never
be quoted as throughput. Retaining the final output and materializing
cross-boundary intermediates did not fix replay. Their source commits remain
preserved as failed experiments:

```text
15202057c xpu: retain captured Laguna drafter outputs
28684cb3b xpu: materialize Laguna drafter graph boundaries
```

The stronger pattern is request rollover: the first request has a normal
decaying acceptance curve near 50%, while later requests become flat 100%.
That rules out a graph that is universally unable to replay and points at the
synthetic-warmup to live-request state transition.

A guarded first-live capture candidate was therefore implemented:

```text
worktree=/home/steve/src/laguna-vllm-dflash-graph-bf16-20260729
commit=ea6dac25f
```

It leaves synthetic DFlash warmup eager, then authorizes exactly one capture
from the first live request after real context K/V, positions, and block-table
state exist. The 60-test CPU gate passes. It has **not** reached candidate code
on TP4: its first formal launch stalled during XCCL initialization.

After clean harness teardown, exactly one corrected probe classified the host:

```text
PROBE_RESULT=COLLECTIVE_STAGE_FAILURE clean_teardowns=0/4
artifacts=/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/tmp/xccl-livecapture-uJl0ll/probe-livecapture-gate-20260730T0152Z
```

All ranks reached `all_reduce-start`; none completed. No causal claim about the
live-capture candidate can be made from this infrastructure failure. Recovery
policy remains a clean reboot followed by one corrected probe—never driver
reload, FLR, shared-memory deletion, or a ladder triggered from summary
counters.
