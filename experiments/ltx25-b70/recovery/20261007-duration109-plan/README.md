# Duration109: 49-frame, 20/28 residency resource pilot

CPU plan only; no runtime packet, device admission, model request or qualification.
This is one explicit three-fixture pilot at 640×384, 49 frames, 24 fps, BF16,
8+3 sampler steps, W2/B1/shared pool. The named sampler layout is
`two-way20-28`: blocks 0–19 on xpu:0 and 20–47 on xpu:1. The intent is to
rebalance pre-load residency after 108b refused before producing any 49-frame
output. No speed, adoption, full-suite, endurance or quality-transfer claim.

The immutable source predecessor is 108b (`ef839f83…697ad7`), whose closeout
records the residency refusal and zero 49-frame outputs. The placement source
is packet100b (`50beee86…aef63`): its 128 exact four-tensor clips qualified only
a 256×256/25-frame screen, not this duration or resolution. The plan pins both
manifests and their separate closeouts. Accepted99b remains the original graph
constructor; this is provenance, not a claim that its old placement is selected.
The full pins and source hashes are recorded in `cpu-validation.json`.

The qualification basis includes the named layout, blocks, both source histories,
and unchanged engineering admission floors. In card order xpu:0/1/2/3 these are
native pre-load **8/8/2/9 GiB**, capture **7/7/2/9 GiB**, and decode preparation
**2/2/10/9 GiB**. Replica after-build free must be at least8 GiB; post-request
free remains at least2 GiB/card. These are engineering allowances, not a measured
49-frame peak bound. No lowering of guards, eviction, precision change or retry
is implied. The future runtime must enforce the named layout in launcher and
actual ownership checks; graphs contain no client-controlled sampler-layout hint.

The bounded sequence stays unchanged: six serial native executions (boat,
marble, bird, each twice), seven candidate submissions (four fills then three
scored), seven timed submissions (same), plus nine setup submissions. That is
**29 attempts and22 capture graphs**, including fills. Only two timing intervals
exist; this is a resource pilot. Fresh native repeats and exact comparison of all
four output tensors are mandatory. Before the second native request, the first
must pass its pinned49-frame header, ownership and memory barrier.

Full F32 shapes are images49×384×640×3, video1×128×7×12×20,
audio1×8×51×16, waveform1×2×96480:146,164,992 payload bytes per full clip.
The storage policy retains50 GiB free plus4 GiB planned writes. Fourteen
full-output equivalents (including two setup captures conservatively) and eight
at-most1 MiB placeholders, bounded headers/cache/previews/logs total3,867,555,440
bytes. No outputs are suppressed and no old raw archive is removed by this plan.
Actual fresh filesystem and category admission remain prerequisites.

Request namespace: `resolution-duration109-20261007`. Native indices99909000–5,
setup captures99909030 and99909041, candidate99909100–6, timed99909200–6.
CPU controls check no name/index collision against sealed101 through108b, plus
strict reconstructed-plan/schedule tamper refusal. All20 model-request graphs
match108 exactly after only name/index/QID normalization; prompts, seeds,
operations, shapes, steps and fill semantics are unchanged. Placement changes
physical ownership, so that equality does not establish numerical equivalence.

Reconstruct and test without runtime actions:

```sh
python3 -B plan_reference.py plan
python3 -B plan_reference.py validate --plan-file candidate-plan.json
python3 -B schedule.py
python3 -B -m unittest -q test_plan_reference.py test_schedule.py
```

These commands only read bounded pinned source/metadata and emit CPU results.
They do not materialize a runtime or grant launch admission. The future runtime
must retain durable native-setup refusal evidence, fault halt, no retries,
strict OOM-to-tiled refusal, original math and one application's finite plan.
