# Post-Restore Record Recipe Sanity - 2026-07-01

Purpose: verify that the active llama.cpp source tree was restored to the
promoted record stack after the failed verifier-top2 diagnostic hooks were
preserved and removed. This is a short sanity run, not a new LocalMaxxing or
full512 record claim.

## Source / Runtime

- Active workspace: `/home/steve/llm-optimizations` on branch-attached `main`.
- llama.cpp source: `/home/steve/src/llama.cpp-gemma-record-repro-c926`.
- Server binary: `build-sycl-b70-aot-bmg-g31-q8reorder-vdr2/bin/llama-server`.
- `llama-server --version`: `c926ad098`, IntelLLVM 2026.0.0.
- Top2 diagnostic hooks were absent before this run (`LLAMA_SPEC_VERIFY_TOP2_PROFILE`,
  `LLAMA_SPEC_VERIFY_BACKEND_ARGMAX_SCORES`, sampled-top2 symbols not present in
  active source).

## Command Shape

Short promoted-recipe sanity on GPU0:

```bash
cd /home/steve/llm-optimizations
LABEL=gemma4-q8-gpu0-postrestore-record-sanity-20260701T174651Z \
GPU_INDEX=0 PORT=18420 \
FLASH_ATTN=on CTX_SIZE=32768 GGML_SYCL_ENABLE_VMM=1 \
BATCH_SIZE=1024 UBATCH_SIZE=1024 \
CANARY_REPEATS=16 MAX_TOKENS=128 REALISTIC_METRIC_TOKENS=100 REALISTIC_GATE=1 \
bash repro/gemma4-26b-a4b-q8-b70/run-vdr2-selecteddown-record.sh
```

## Result

Evidence directory:
`data/gemma4-q8-gpu0-postrestore-record-sanity-20260701T174651Z/`

Tracked compact artifacts:

- `summary.json`
- `realistic-suite.json`
- `chat-canary.json`
- `models.json`

Raw `server.stdout.log` is intentionally not tracked; the canonical server log
path is recorded in `summary.json` as
`/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/gemma4-q8-gpu0-postrestore-record-sanity-20260701T174651Z.server.log`.

Metrics from `summary.json`:

```text
realistic_final_gate.passed: true
cached_tokens_all_zero: true
canary_rows_completed: 64/64
max_tokens: 128
median tok/s 1-100 after TTFT: 122.23871192082832
p10 tok/s 1-100 after TTFT: 105.93778758937947
mean tok/s 1-100 after TTFT: 119.78027741280415
median full-output after TTFT: 116.99020819065922
median wall full-output: 100.43733473770232
median TTFT: 178.7877315073274 ms
```

Interpretation: the restored/rebuilt binary is back on the promoted Gemma Q8
record lane. Because this run used `MAX_TOKENS=128` and only 16 canary repeats,
it is a sanity result only; the current headline remains the full512
`124.97714084813418 tok/s` run at
`data/gemma4-q8-gpu0-finalpostnorm-reproexact-full512-20260701T084728Z/summary.json`.

## Next Work

Continue optimization only from `/home/steve/llm-optimizations`. For
micro-changes, use the paired reliability protocol and no-spec calibration lane
when the expected effect is below the current MTP variance band. Preserve source
patches and compact result packets before changing the active source again.
