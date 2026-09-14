# Bounded prefill follow-up

Preregistered 2026-09-14 UTC (September 13 EDT) on the two-ASRock-B70 host
`steve-TURIND8-2L2T`. User selected a small measurement/documentation follow-up,
with at most three missing configurations and modest optimization investigation.

## Selected scope

| Setup | Runtime | Draft | Qualified reference |
| --- | --- | --- | --- |
| Qwen3.5 4B W4A16, two GPUs | public R304 | fixed MTP3, 67k shortlist | `qwen35-4b-w4a16-20260913-rt2/mtp3-a/strict` |
| Qwen3.5 9B W4A16, two GPUs | public R304 | fixed MTP3, 67k shortlist | `qwen35-9b-w4a16-20260913-rt2/mtp3-a/strict` |
| Qwen3.8 27B AutoRound INT4, one GPU | public R304 | fixed MTP4, 67k shortlist | `qwen38-int4-rebase-v0290-tp1-r304-20260913/mtp1-a/strict` |

Reference paths above are beneath `/mnt/fast-ai/bench-results`; complete reference
outputs and their hashes are copied into each new evidence directory. Published
R304 image ID is `sha256:7cd7bb16b1fd2e679f0230a38b2f0242fe1c278853867e697c0ce139be2133d2`.
These are additional measurements of existing frozen recipe identities, not a
runtime rebase or a new decode record. Verify the image contract and exact model
manifest through the existing public launchers. Use FP16 activations/native KV,
CLASSPAD0, rowchunk32, V1 runner, 1024 context/batch budget, one active sequence,
prefix caching off, default published graph settings. GPU utilization .95 for
4B/9B TP2, .96 for 27B TP1 matches their reference servers.

## Measurement

Use unrepeated representative prose, Python and structured-document material,
truncated to exactly 256 and 512 numeric input tokens. The extra 256 point is a
small companion for the existing measured-point graph schema, not a broad sweep.
One concurrent request, three measured repetitions per class/length per arm,
128 generated tokens with ignore_eos for the timing screen; separate warmups.
Measure baseline and final control in the same continuously loaded server.
Aggregate each metric by median within each class, median across the three
classes, then arithmetic mean across the two control arms. Publish 18 samples
per length, individual repetitions, dispersion and control drift.

Server prefill is input tokens divided by the vLLM histogram duration from first
scheduled execution to first token. Require exactly one histogram observation
and the exact input-token delta per serial request. HTTP TTFT and 99-interval
decode are separate metrics. Every request must report cached_tokens=0 and
complete numeric output IDs; all repetitions and final controls must be exact.
The 128-token forced-completion screen does not qualify a new decode headline.
Run the full 12-prompt natural-completion/512-cap suite and objective canaries
once on each unchanged server; require complete output identity with its original
qualified reference. Do not promote a baseline with a failed output gate.

## Optimization boundary and stopping rules

Take at most one short runtime-profiler trace on the 4B TP2 server after its
unprofiled baseline and full quality suite. Request one output token from a
512-token prompt, preserve profiler overhead separately, verify the token against
the unprofiled run, stop profiling, then collect final unprofiled controls.
No custom model probes or runtime mutation. See the [optimization review](2026-09-14-prefill-optimization-review.md):
the earlier direct-allocation idea is not rerun; prefill-only CLASSPAD changes
arithmetic and is declined within this bounded session. Trace evidence may
identify a specific later follow-up; no improvement is presumed.

One independently invoked owned server per selected configuration, no automatic
restart/retry chain. Check actual processes/listeners/render-node ownership, hold
the prefill lock, and pass both-card compute/XCCL health before/after each stage.
Monitor new journal faults during startup and requests. Any failure aborts that
stage; any GPU fault halts subsequent GPU work. Stop only the owned server once.
No power, clocks, governors, ASPM, swap, cache drops, driver reset or reboot changes.
Preserve the separate four-card LTX work. New evidence root:
`/mnt/fast-ai/bench-results/qwen-prefill-followup-20260914`.

Public additions must match GPU count/quantization/draft settings and explicitly
label this separate short-input test. Prior measurements used repeated/truncated
short paragraphs; this follow-up uses unrepeated source material, so it does not
establish a matched GPU-scaling ratio against the earlier four measurements.
LocalMaxxing disposition: withheld; prefill observations and profiling are not
new qualified single-stream decode records. Validate and publish only completed,
evidence-backed work; leave other gaps unmeasured rather than extend the campaign.
