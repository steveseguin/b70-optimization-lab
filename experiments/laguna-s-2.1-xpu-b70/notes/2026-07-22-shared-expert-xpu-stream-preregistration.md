# Laguna exact M=8 shared-expert XPU stream preregistration

Date registered: 2026-07-22 America/Toronto

Status at registration: implementation is under static review; no component or
endpoint GPU run has been launched.

## Question and treatment

Laguna's target shared expert costs about 1.013 ms per DFlash target cycle:
two BF16 upstream projections, SiLU/multiply, and one BF16 down projection per
MoE layer. The record path runs that branch serially before/around the routed
expert work.

The candidate moves only the complete shared-expert branch to one process-wide
XPU auxiliary stream. It preserves the incumbent stride-zero BF16 BMMs,
activation, multiplication, down projection, shared+routed addition, and
fixed-rank reduction. The main stream forks after the shared input is ready and
joins before the addition/reduction.

The default-off selector is:

```text
VLLM_XPU_LAGUNA_M8_SHARED_EXPERT_STREAM=1
```

It must fail closed unless execution is Laguna's exact target verifier at
M=8, BF16 contiguous `[8,3072]`, configured TP4+EP4/DP1/PP1, eager with XPU
graph and deterministic graph disabled, and DBO disabled. Draft, prefill,
M=1, tail, and every nonmatching row count keep the incumbent main-stream path.

## Standalone component gate

Run
`experiments/laguna-s-2.1-xpu-b70/tools/gate_laguna_shared_expert_stream.py`
once on each B70 with exactly one visible device. Each rank must pass all of
the following:

- at least 128 changing-input and changing-weight epochs;
- raw bit equality and `torch.equal` at shared gate, up, SiLU/multiply, and
  down outputs;
- raw bit equality for an independent same-shape main-stream interference MLP;
- unique input, weight, and output hashes for every epoch;
- correct input `record_stream`, main-to-aux fork, and aux-to-main join;
- a post-timing exactness recheck after sustained repeated submissions; and
- strictly positive median overlap gain versus the serialized pair.

If any card fails correctness, race, or positive-overlap, stop before an
endpoint service. Do not average away a failing card.

The synthetic interference branch is only a concurrency/race and feasibility
gate. Its timing is not an endpoint claim and is not substituted for the fixed
realistic suite.

## Endpoint protocol and early stopping

If and only if all four component gates pass, use the approved eager depth-7
record stack with QKNorm+RoPE fusion off and change only the shared-stream
selector. Use new services, seed 1, BF16 KV, `enable_thinking=false`,
`max_tokens=512`, token IDs returned, and the fixed 13-prompt suite with SHA256
`9fdaacfdc4de59407a73cbe0d8130fa0f6abe91fed782e399a58adbc035ea638`.

The endpoint order is a sequential A-B-B-A design with a preregistered early
stop:

1. A1 control, shared stream off;
2. B1 candidate, shared stream on;
3. if the phase-1 gates below pass, B2 candidate;
4. then A2 control.

Every leg is a new server. A fixed 60-second device-free interval separates
legs. There is no generation warm-up, repeated prompt, prefix/history/ngram
reuse, concurrent request, or fifth rescue run.

Stop after B1 unless all phase-1 conditions pass:

- both legs pass every quality/honesty gate below;
- B1 headline throughput exceeds A1;
- B1 wins at least 9/13 paired prompt rows and has positive median paired
  percentage change;
- B1 aggregate request-decode seconds per DFlash target cycle is at least
  0.5 ms lower than A1; and
- pairwise acceptance-rate difference is at most 0.10 percentage point.

The component is worth only about 1.013 ms/cycle before contention, so failure
to save even 0.5 ms in the contemporaneous endpoint pair is a bounded negative.
The early stop does not authorize replacing either leg or starting another
block.

## Quality, attribution, and record gates

Every executed endpoint leg must pass:

- fixed-suite freshness and one request per unique prompt;
- 13/13 full token arrays bitwise equal to the canonical q=1 teacher;
- 13/13 `cached_tokens=0`;
- 512-token long-then-next exact 2/2;
- 863-input/512-output rollover exact 1/1; and
- cross-leg token equality 13/13.

Natural DFlash proposal variation is recorded rather than retroactively
forbidden. Attribution uses contemporaneous pairs, target-cycle-normalized
decode time, row-wise paired changes, and requires acceptance rates within
0.10 percentage point. Draft cycles, drafted/accepted totals, and
accepted-position histograms remain mandatory evidence.

If the full A-B-B-A block runs, call the shared stream a reproducible endpoint
win only if:

- B1 beats A1 and B2 beats A2 in headline throughput;
- each candidate wins at least 9/13 prompt rows with positive median paired
  change;
- each candidate saves at least 0.5 ms per normalized target cycle;
- pairwise acceptance-rate differences are at most 0.10 percentage point; and
- the lower candidate start exceeds the lower control start.

A LocalMaxxing record additionally requires the lower candidate start to
exceed `33.438926675602126 tok/s`. Only that lower candidate result may be
submitted after payload audit. Otherwise preserve the exact result as a win,
loss, or inconclusive experiment with no submission.

