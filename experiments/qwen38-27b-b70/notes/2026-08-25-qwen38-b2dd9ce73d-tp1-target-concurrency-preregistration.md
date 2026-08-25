# Qwen3.8 27B b2dd TP1 target-only concurrency preregistration

Status: **preregistered, not launched**. This packet creates no performance
claim and does not change a neural.download package or headline.

The first missing Qwen3.8 aggregate curve will use the exact dated b2dd/1e90
AutoRound W4A16 image on one B70, MTP0, eager execution, F16 KV, and no prefix
cache. It measures batch sizes `1/2/4/8/16/32/64` in one persistent engine,
with 128 distinct input tokens and 512 forced output tokens per request. Each
batch size runs twice with the same seed. No point is projected, interpolated,
or filled from another model, quant, runtime, topology, or graph treatment.

Before the aggregate ladder, the same engine generates every one of the 64
distinct prompts alone. Every batched response is compared with its own
same-prompt sequential token sequence, and the full output token arrays are
retained. This closes the blind spot in the earlier Qwen3.8 Q8 c3/c4 screen
and the Qwen3.6 35B aggregate work: a stable request zero cannot certify the
other requests in a batch.

The campaign distinguishes three outcomes:

- `complete-exact`: timing and literal canaries pass, both repeats agree, and
  every batched request matches its sequential oracle;
- `measured-output-variant`: timing and literal canaries pass, but at least one
  repeat or sequential comparison differs. Throughput remains a direct
  experimental measurement with the mismatch disclosure, not a validated
  deployment profile;
- `quarantined`: identity, lifecycle, completeness, timestamp, or literal
  quality fails, so no throughput curve is published.

There is deliberately no speed floor. An underwhelming but sound eager curve
is the control needed to choose graph capture shapes and kernel work. A later
graph curve is a separate treatment; capturing only some sizes and joining
them to eager rows would not be one coherent profile. Likewise, TP2 and TP4
will receive separately pinned packets rather than inheriting TP1 results.

The launch is restricted to the four-B70 measuring host. The two-B70, 15-GiB
source/audit host must not load this full AutoRound server. Execution requires
the exact image, direct-plus-ordinary model verification, clean pushed `main`,
fresh ext4 output/cache roots, idle runtime and render nodes, and the canonical
host/GPU locks. The structured identity and measurement contract are in
[`2026-08-25-qwen38-b2dd9ce73d-tp1-target-concurrency-r1.json`](../data/2026-08-25-qwen38-b2dd9ce73d-tp1-target-concurrency-r1.json).

Publication comes only after measurement and optimization. The eventual
neural.download recipe must pin and link the model revision, image/runtime,
required patches, command, environment, benchmark definition, quality state,
and structured evidence using repository-relative links. Machine-local model,
cache, and result paths are lab execution details, not portable user commands.

From a clean clone on the four-B70 measuring host, the packet is checked and
launched with repository-relative commands:

```bash
python3 -B experiments/qwen38-27b-b70/scripts/run-20260825-qwen38-b2dd-tp1-target-concurrency-r1.py --check
python3 -B experiments/qwen38-27b-b70/scripts/run-20260825-qwen38-b2dd-tp1-target-concurrency-r1.py --plan --attempt 1
python3 -B experiments/qwen38-27b-b70/scripts/run-20260825-qwen38-b2dd-tp1-target-concurrency-r1.py \
  --execute --stage c1-eager-target-ladder --attempt 1 \
  --ack 'RUN qwen38-b2dd9ce73d-tp1-target-concurrency-20260825-r1 c1-eager-target-ladder r1'
```

The launcher itself resolves the lab checkout, pins all repository inputs by
hash, verifies the exact local image ID and all model files, creates fresh
roots, and records the fully expanded Docker argument vector. Users do not
need to copy this lab-only launcher into a deployment recipe; the eventual
package guide will translate the validated configuration into portable
download, image/build, launch, benchmark, and cleanup steps.
