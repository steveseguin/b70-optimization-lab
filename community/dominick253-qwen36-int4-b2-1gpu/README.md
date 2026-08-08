# Qwen3.6 27B/35B INT4 on Intel Arc B70 with vLLM B2 TP1

> **Community contribution by `dominick253`.** The contributor's files and
> measurements are valued and preserved, but they were not produced in this
> repository's reference lab. Maintainer review corrected evidence labels,
> isolated unsafe historical commands, and withdrew an unmatched A/B claim.
> Read [STATUS.md](STATUS.md) before use.

## What the contributor reported

- Qwen3.6 27B served on one B70 after online `sym_int4` conversion with FP8 KV.
- Qwen3.6 35B-A3B served in the same TP1 family but produced `!!!!` corruption
  with thinking enabled and MTP disabled.
- Historical context sweeps were collected with llama-benchy.
- Separate MTP-on and MTP-off runs suggested a large deep-context penalty.

These are `community-reported` observations. The model revisions and exact
container digest were not recorded.

## Correction to the MTP comparison

The submitted write-up described speculation as the only A/B change. The raw
artifacts show otherwise:

| Arm | Output tokens | Measured repeats | Date |
| --- | ---: | ---: | --- |
| MTP on | 1,024 | 5 | 2026-08-04/05 |
| MTP off | 512 | 3 | 2026-08-05 |

The reported values remain useful observations, but the 3.45x and 1.56x ratios
are not accepted as controlled treatment effects. They must not be used as a
shipping rule or LocalMaxxing result. A future A/B must match output length,
repeats, sampling, service identity, prompt set, cache state, and run order.

## Packet layout

- [`reported/exact-contributor-launcher.sh`](reported/exact-contributor-launcher.sh):
  original privileged, tag-based, container-replacing launcher.
- [`reported/benchmarks/`](reported/benchmarks/): original JSON/CSV, benchmark
  scripts, summaries, and contributor interpretation—including the unmatched
  A/B claim for historical transparency.
- [`vllm-qwen36-int4-b2-1gpu.sh`](vllm-qwen36-int4-b2-1gpu.sh):
  maintainer-hardened launcher requiring a digest-pinned image and explicit
  model path; defaults to localhost publication without privilege, persistence,
  or automatic replacement.
- [`tools/bench-openai-endpoint.sh`](tools/bench-openai-endpoint.sh): corrected
  benchmark wrapper that reads llama-benchy's actual `benchmarks` JSON key.
- [`validation/`](validation/): maintainer offline review; no model run.

## Safe dry run

The safe launcher deliberately has no default image because the contributor
submitted only a mutable tag:

```bash
IMAGE=intel/llm-scaler-vllm@sha256:<64-hex-digest> \
MODEL_HOST_DIR=/path/to/pinned-model-snapshot \
DRY_RUN=1 \
bash vllm-qwen36-int4-b2-1gpu.sh
```

Before device execution, record the image digest, model repository/revision,
model hashes, selected GPU, and a fresh artifact directory. The hardened
launcher itself is offline-reviewed but not model-tested.

## Validation required for promotion

1. fixed realistic prompts, one cold invocation each, and cache-zero telemetry;
2. a native-KV or declared teacher control for the FP8-KV quality class;
3. deterministic arithmetic, tool, retrieval, and long-output corruption gates;
4. a matched alternating MTP-on/off experiment with acceptance counters; and
5. clean startup/teardown and device-error evidence over multiple cold starts.

Until then, keep this packet in `community/` and treat the 35B corruption report
as a useful negative observation rather than a generalized model conclusion.
