# First-token correctness: prompt inputs were mistaken for generated output

The reported device sequence `[846,198,2523,513,60566,449,13343,2015,...]`
is the beginning of the **prompt**, following input token `248045`. It is not
a generated answer. The live run's timing field is literally `input_token`.
The first audit snapshot, **2026-10-11 06:16:12 UTC**, had completed 16 of 87
prompt positions, an empty stdout file, no final runtime receipt and no
step-1 layer fixtures. The later snapshot is recorded separately in the
[CPU investigation packet](../experiments/own-xpu-runtime/stage2/packet13-integrate/correctness/README.md).
The alleged first-token failure therefore has not occurred in that evidence.

## Input and text

All 87 IDs in `build/input/tokens.txt`, `build/input/input.json` and the
BLAS-order oracle's `incident-retrospective/input.json` agree exactly.
The token-file SHA256 is
`9cab78bcdc3b7c19e289fa884b32f2771811b31a6a74d205c447425c13e485f1`.
The rendered prompt agrees byte-for-byte with the oracle's prompt file,
including `<|im_start|>user`, the assistant role and the empty thinking block.
There is no demonstrated prompt/template/tokenizer mismatch.

Using the oracle's own `Tokenizer` with the published GGUF header metadata:

- Alleged device output decodes to `user\nYou are advising an infrastructure team`.
  These are prompt tokens 1–8.
- The oracle's cited nine generated IDs decode to
  `**Incident Retrospective: Production API`.
- Its retained 64-token text is:

```text
**Incident Retrospective: Production API Outage (INC-2024-089)**

**Executive Summary**
On October 12, 2024, the primary User Profile API experienced a 45-minute total outage affecting 100% of read traffic.
```

Native generated text was **not yet available** at the observed boundary;
empty stdout during prefill is not an empty generated answer. The native
program processes every prompt position before appending any generated ID.
It writes `step1/layer-XX.bf16` only at prompt position **86**, not position 0.
The plan is `run/plan.json`, underneath the window directory; it is a tensor
and dispatch plan, while the command/input receipt binds the actual prompt.
The oracle's 23.5 versus 20.375 first-logit margin is real, but no opposing
native prediction exists in this snapshot to compare with it.

## CPU check and arithmetic diagnosis

An isolated GNU C++ build in `/tmp/iq3-first-token-cpu-check` links no
accelerator libraries. The original Packet 13 host CLI processes all 87 tokens
through layer 0 and exactly repeats its existing BF16 fixture:
`1b7f914b9ef1834a72aea1cb186b74c8dbecddff743fa529fe8e916e1352d82e`.
The prefix harness processes the same prompt through layers 0 and 1;
layer 0 is unchanged, and layer 1 is
`d45c7f0747e7cf589b09e6d82e3aa48d2956e5e4d8fb78e75e271a8dc1a3fe28`.
It completes in 22.30749 seconds with 297,644 KiB peak RSS.
The corrected harness repeats those two hashes in a fresh process.

The full 48-layer CPU pass completes all 87 prompt positions in
**492.112819 seconds**, with **897,220 KiB** peak RSS (0.919 GB), and predicts
first token **332**, decoded as `**`. Its independent finite-logit argmax
check agrees. All **48/48 hashes exactly match** the separate, freshly
committed runtime-order CPU oracle's step-1 fixtures at commit `9ee12b3527`.
That oracle shares the frozen math; agreement is repeat/execution evidence,
not an independent proof of the model equations. The
[full CPU fixtures](../experiments/own-xpu-runtime/stage2/packet13-integrate/correctness/full48/step1/layers.jsonl),
[run receipt](../experiments/own-xpu-runtime/stage2/packet13-integrate/correctness/full48/receipt.json),
[CPU comparison](../experiments/own-xpu-runtime/stage2/packet13-integrate/correctness/runtime-order-oracle-comparison.json)
and [pending device comparison](../experiments/own-xpu-runtime/stage2/packet13-integrate/correctness/device-comparison.json)
are retained. Every CPU owner drains cleanly to zero live bytes/events.

At **06:25:56 UTC**, the native job has completed only **27/87** prompt
positions, still with no answer and no step-1 fixtures: **0/48 device layers
can be compared**, explicitly pending rather than a pass. Its next device
observation is outside this CPU investigation's snapshot. This is why there
is no first divergent native operator to report or fix.

The fresh runtime layer-0 fixture versus the old BLAS-order oracle differs in
2,103 of 10,240 BF16 values. The first differing element, flat index 57,
is runtime **-0.000019550323486328125** versus oracle
**-0.000019431114196777344**. The largest absolute difference is
**0.0009765625** at index 5388: runtime **0.1650390625**, oracle
**0.166015625**. RMS difference is **0.00002469297739985483**, versus oracle
RMS magnitude **0.009817264322286969**, about **0.2515%** relative RMS.
These are small numerical differences, not evidence of a gross layer-0 math
failure, and are not an exactness pass.

Packet 4's historical unresolved result remains separate: 2,293 differing
values, the same maximum absolute difference, and about 0.2339% relative RMS.
Nothing in this investigation retrospectively qualifies that comparison or
proves every difference comes from GEMV order alone.

The read-only source review found no clear implementation defect in GDN head
mapping/decay, hyperconnections, QSA pooling/attention, routing or combination.
The runtime's scalar libm, `1/sqrt` and reduction order differ from the old
PyTorch/BLAS oracle. PLE additionally rounds its convolution accumulator to
BF16 before SiLU; that is already explicit in the runtime-order oracle's
frozen identity and affects layer 1, not layer 0. The
[arithmetic decision](2026-10-11-iq3-arithmetic-authority-decision.md) does not
make shared host/device source proof of transcendental parity.

## Conclusion and remaining device evidence

The root cause of the **reported** failure is a log-interpretation error:
prompt inputs were compared against oracle generated outputs. No divergent
device layer/operator has been established. The CPU-versus-BLAS layer-0
difference is an arithmetic diagnostic, not a located device defect.
An operator bisection premised on matching device layers would be premature
while those fixtures are missing. No production arithmetic was changed.

The added reporting regression tests prevent prompt timing rows from being
classified as generated output and prevent absent/partial device fixtures
from passing or falsely identifying the first divergent layer. The original
CLI's 13 integration cases also pass. Review additionally fixed the new
diagnostic harness's existing-output refusal so it preserves prior evidence;
this has no numerical effect and is covered by a regression receipt.

A new device run is **not needed to resolve this alleged failure**: the
already-running job must first finish prefill and provide its actual output
and fixtures. Its eventual files can be compared with the retained CPU
fixtures using `compare_layers.py`; only an observed mismatch can justify
an operator-localization capture. Device exactness and the required fresh
process repeat remain open. This work started no GPU program, server,
container or unit, touched no device node or port, changed no host settings,
and wrote nothing under the protected Packet 13 `build/` or USB model tree.
Only this job's own scratch is removed after retaining the evidence.
