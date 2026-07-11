## Purpose

Describe the focused change and why it is useful. Link the issue, experiment,
or result packet where applicable.

## Provenance And Rights

- Base commit:
- Candidate commit / patch path:
- Upstream or third-party sources and licenses:
- [ ] I have the right to submit this material under the repository `LICENSE`.
- [ ] I removed secrets, private data, model weights, and unrelated artifacts.

## Test Identity And Evidence

- GPU model/count/VRAM/interconnect:
- OS/kernel/driver/compiler/accelerator runtime:
- Model and exact revision:
- Quantization (including KV/draft model):
- Engine/runtime commits and local patches:
- Exact command and environment:
- Prompt/output/context, batch, concurrency, repeats:
- Cold/warm/cache/speculation policy:
- Metric definition and result:
- Quality gate and result:
- Result JSON/log paths:
- Closest known-good result:
- Exact delta from that baseline:

If a field does not apply, explain why rather than deleting it.

## Safety And Scope

- [ ] I inspected the diff for unintended or generated changes.
- [ ] I preserved relevant negative/superseded evidence and did not overwrite an
      older result silently.
- [ ] I did not expose credentials or require unnecessary privilege.
- [ ] I did not disturb the active Qwen 27B INT4 TP=2 lane, its processes, or
      modified external vLLM/XPU-kernel trees.
- [ ] I labeled contributor-reported and independently verified claims
      distinctly.

Review and hardware validation are manual and task-specific. Submission does
not guarantee execution, ranking, merge, support, or LocalMaxxing publication.
