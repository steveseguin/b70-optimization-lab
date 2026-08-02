# Laguna exact wide-prefill Q/K RMSNorm plus NeoX RoPE

Date registered: 2026-08-02 America/Toronto

Status: isolated source and host validation complete; XPU component and endpoint
validation remain blocked by the recorded device reset state and the scheduler
alignment dependency. No device probe, component run, service, reset, or
recovery action was performed for this treatment.

## Offline implementation checkpoint

The default-off treatment is preserved in isolated commits:

- vLLM `1234ff004d57f1f0c102bd2afff9690c16bf995a` in
  `/home/steve/src/laguna-vllm-wide-prefill-qknorm-rope-20260802`;
- XPU kernel `a67a396245696a9df2a8929b445c721fa8899c92` in
  `/home/steve/src/laguna-xpu-kernels-wide-prefill-qknorm-rope-20260802`.

The native op reuses the authenticated M8/M12 kernel arithmetic verbatim with
eight heads per workgroup. It accepts only the registered rows, paired
Q/rotary widths 1,536/64 or 2,304/128, aligned BF16 vector storage and row
strides, rank-one caller-bounded positions, separate non-overlapping outputs,
and one XPU device. The existing M8/M12 entry point and launcher are unchanged.

The vLLM selector is strict `0`/`1` and default off. Selector-on startup checks
that the rebuilt native symbol is present and rejects any drift from q12 DFlash,
BF16, exact attention/MoE/prefill/router flags, TP4/PP1/DP1/EP, one request,
eager/no-parity/no-async execution, or the explicit 8,202/8,192 scheduler pair.
Each forward is separately authenticated as a pure target-prefill chunk before
the model can dispatch the op; decode, verifier, draft, graph, padding,
multi-request, LoRA, encoder, cascade, and KV-scale-calculation paths fall back.

Offline validation completed:

- oneAPI 2025.3.3 core `_C` build passed for PVC and BMG targets;
- the built dispatcher exposes the intended two-output alias schema;
- four kernel static source-contract tests passed;
- 51 focused vLLM environment, runner, and model-dispatch tests passed,
  including the real computed=24,576, prompt=32,640, rows=8,064 final chunk;
- Ruff checks and diff whitespace checks passed; and
- an independent read-only audit found no arithmetic, workgroup,
  synchronization, decode-isolation, or default-off blocker. Its shape-pair,
  alignment, stale-DSO, and coverage findings were incorporated before these
  commits.

An unfiltered run of the three containing vLLM test files is not reported as a
pass: an unrelated generic CPU-runner test fails before this treatment because
the installed XPU-only PyTorch build cannot construct `torch.cuda.Stream`.
That failure leaves distributed fixture state dirty and cascades into later
tests. The existing Laguna prebuilt-metadata control passes when isolated; the
51 treatment-focused tests above ran together and passed cleanly.

The existing component harness now has a `wide-prefill` mode with changing
inputs, all required starts and the 32,767 boundary, immutable-input checks,
aligned guard regions, storage-level non-alias checks, exact BF16 comparison,
per-shape timing enforcement, and durable failure JSON. The companion
`aggregate_laguna_wide_qknorm_rope.py` requires all four rows on all four ranks
and enforces the 25 ms aligned-prefill projected-saving gate. These XPU gates
are implemented but intentionally unrun.

After authorized recovery, run one process at a time with the physical card
isolated by `ZE_AFFINITY_MASK`. For each `rank` in `0..3` and each `rows` in
`1024 4096 8064 8192`, use this command shape with a unique JSON output:

```bash
ZE_AFFINITY_MASK="$rank" \
PYTHONPATH=/home/steve/src/laguna-vllm-wide-prefill-qknorm-rope-20260802:/home/steve/src/laguna-xpu-kernels-wide-prefill-qknorm-rope-20260802 \
/home/steve/.venvs/deepseek-v4-xpu/bin/python \
  experiments/laguna-s-2.1-xpu-b70/tools/gate_laguna_qknorm_rope.py \
  --mode wide-prefill --rank "$rank" --rows "$rows" \
  --out "$run_dir/rank${rank}-rows${rows}.json"
```

Then aggregate all 16 JSON files; the aggregator rejects a missing/duplicate
rank-row identity, any failed component row, or any rank below the 25 ms
aligned 32,640-token projected-saving threshold:

```bash
/home/steve/.venvs/deepseek-v4-xpu/bin/python \
  experiments/laguna-s-2.1-xpu-b70/tools/aggregate_laguna_wide_qknorm_rope.py \
  "$run_dir"/rank*-rows*.json --out "$run_dir/aggregate.json"
```

## Premise

Laguna's pure target prefill still launches Q RMSNorm, K RMSNorm, and NeoX
RoPE separately in every attention layer. The promoted M12 decode treatment
already proves that these three operations can be fused while preserving the
incumbent 16-lane RMSNorm reduction, the explicit BF16 norm boundary, the BF16
weight multiply, and the existing BF16 cosine/sine cache.

Under TP4, each 8,192-token chunk materializes about 1.734 GiB of Q/K outputs
per rank across 12 full-attention and 36 sliding-attention layers. The separate
RoPE pass rereads and rewrites those outputs. For an aligned 32,640-token
schedule of 8,192/8,192/8,192/8,064, fusing three submissions to one removes
384 eager submissions and approximately 13.82 GiB/rank of redundant RoPE
read/write traffic. This is a traffic estimate, not a speed claim.

The generic `fused_qk_norm_rope` op is not eligible: it uses a different
reduction tree and does not retain Laguna's authenticated BF16 boundary. The
candidate must derive from the exact Laguna M8/M12 implementation while
leaving that promoted op unchanged.

## Isolated source treatment

- vLLM base: exact-prefill source
  `4ddb915284d4442885f72bed48311fd04640977c`;
- XPU kernel base: `99886d783372e621941228250091dc8ebdc1595d`;
- selector: `VLLM_XPU_LAGUNA_WIDE_PREFILL_QKNORM_ROPE`, literal `0` or `1`,
  default off;
- new, separately named out-of-place native op; do not alias or overwrite the
  qkv input in this experiment;
- supported rows: exactly 1,024, 4,096, 8,064, or 8,192;
- supported TP4 shapes: full Q/K widths 1,536/256 with rotary dimension 64,
  or sliding Q/K widths 2,304/256 with rotary dimension 128; and
- BF16 Q/K, weights, outputs, and cache; int64 positions; head dimension 128;
  no tail workgroup or generic fallback under selector-on eligibility.

Eligibility must be authenticated by `GPUModelRunner` through forward-context
state. Require one pure target-prefill request, no prompt crossing, no spec
tokens, encoder input, LoRA, cascade attention, ubatching, padding, graph,
compile, parity probe, async scheduling, draft layer, or non-BF16 input. The
strict integrated contract additionally requires q12, the exact-prefill
selector, `max_num_batched_tokens=8202`, and explicit
`max_num_scheduled_tokens=8192`.

## Host and component gates

Host tests must cover selector parsing and default-off behavior, integrated
configuration rejection, all positive row/shape contracts, and rejection of
decode, verifier, draft, graph, padding, multi-request, and unsupported-row
drift. Existing M8/M12 op tests and source behavior must remain unchanged.

Extend the existing QKNorm/RoPE component harness to compare the candidate
against the actual incumbent two `ops.rms_norm` calls plus
`ops.rotary_embedding`. Test both physical attention shapes at rows 1,024,
4,096, 8,064, and 8,192 with changing inputs, chunk-start positions 0, 8,192,
16,384, and 24,576, plus the 32,767 boundary. Require:

- raw BF16 Q and K equality for every comparison;
- immutable Q/K inputs, norm weights, cosine/sine cache, and positions;
- intact output guard regions and no input/output alias;
- candidate time no worse than 0.95x incumbent for each physical shape; and
- at least 25 ms projected saving over the complete aligned 32,640-token,
  48-layer prefill before any vLLM endpoint integration.

Any arithmetic mismatch, mutation, dispatch fallback, build/runtime failure,
or missed performance threshold preserves the result and closes the treatment
before endpoint work.

## Endpoint dependency and gate

Source and host tests may proceed offline. No XPU component may run in the
current `0000:47:00.0` reset-loop state. The scheduler-budget A/B in
`2026-08-02-long-scheduler-budget-alignment-preregistration.md` must pass
before this treatment may enter a model endpoint.

If both dependencies pass, compare selector off/on under the winning aligned
8,202/8,192 q12 identity, with one 1K warmup, all three 32,640-token rows, and
their sentinels. Require exact repeat-oracle output and prompt hashes, q1-exact
sentinels, retrieval and cache-zero passes, identical accepted/drafted/cycle
counters, exact 146/145 target and 14/13 draft topology on every rank, and
clean memory/teardown gates. The candidate 32K median must reach at least
1.01x prefill throughput, at most 0.99x TTFT, and at least 0.98x conventional
decode, with no long decode row below 0.95x control.

This is a prompt-processing treatment. It cannot change the protected short
decode record or produce a LocalMaxxing submission.
