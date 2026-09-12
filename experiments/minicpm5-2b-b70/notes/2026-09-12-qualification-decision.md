# MiniCPM5-2B native BF16 qualification decision — 2026-09-12

**Unqualified.** Setup is usable for further diagnosis, but this is not an
approved target for lossless optimization. No model optimization, quantization,
DSpark, permanent service, performance promotion, or LocalMaxxing submission.

## Evidence and decision

| Attempt | Declared preset | Observed outcome |
| --- | --- | --- |
| run1 | Greedy, thinking, no system,256 smoke budget | No final answer; cap reached |
| run2 | Same,2048 smoke budget | Repetition, no final answer; cap reached |
| run3 | Publisher HF sampling, seed7429, no system | Smoke passed;5/6 objective checks passed; JSON-only array wrapped in Python fences; stopped partial campaign |
| run4 | Same sampler/seed, neutral helpful-assistant system | Smoke passed;4/6 objective checks passed; array includes explanation, object wrapped in JSON fences; gate stopped campaign |

Run4 failed outputs reached EOS normally. Their numeric/object contents are
correct, but their final responses violate explicit JSON-only instructions.
The independent reviewer reran the checker and confirmed both failures. Actual
saved input tokens contain no instruction asking for code fences; the rendered
system/user template and single BOS are correct. No demonstrated harness defect
invalidates these results. This is evidence about these checkpoint/runtime/preset
combinations, not proof of an intrinsic checkpoint bug or a broad quality ranking.

The official pinned cookbook gives a no-thinking sampling row for1B, not2B.
Disabling reasoning would create another target; it cannot qualify this target
as lossless. Do not sweep seeds/prompts or strip fences to manufacture a pass.

Full fresh-process repeats, cache/no-cache parity, context screens and complete
practical-answer adjudication remain unqualified. Run3's ten512-token realistic
responses all reached the cap without a final answer; their thought-inclusive
speed is diagnostic only. They are not successful completed-answer benchmarks.

## Preserved artifacts

- [Machine decision](../data/qualification-decision.json)
- [Run4 strict checks](../data/campaign-run4/pilot-checks.json)
- [Run4 full raw pilot outputs](../data/campaign-run4/pilot-quality.json)
- [Run4 guard outcome](../data/guard-run4/result.json)
- [Run4 evidence hashes](../data/run4-evidence-sha256.json)
- [Preregistered source hashes](../campaign-run4-inputs.json), verified after execution
- Earlier raw attempts remain under `../data/campaign-run1`, `campaign-run2`,
  `campaign-run3` and their matching guard directories.

All four GPUs passed run4 preflight and postflight. The guard exited after the
pilot assertion; baseline A/B did not start and no owned service remains.
Original model weights remain on the8TB drive. Dedicated environment and harness
remain available; existing Qwen runtimes and protected queued lanes are preserved.

## Next action

Withhold speed optimization on this model. A useful next diagnostic, if this lane
is continued, is an independently implemented official-runtime comparison on the
same prompts and precision to distinguish runtime behavior from model behavior.
It would be a new preregistered experiment; no such cross-runtime result exists
here. Switching to another candidate requires its own native quality baseline.

Publisher source: [pinned OpenBMB vLLM cookbook](https://github.com/OpenBMB/MiniCPM/blob/310e3fce1d8378e26471577c55084ea44bd9c8c3/docs/deployment/vllm.md).
