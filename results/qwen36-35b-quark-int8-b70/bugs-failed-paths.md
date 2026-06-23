# Bugs And Failed Paths

This file preserves the useful negative results. Do not delete these lessons;
they prevent repeated work.

## Spec Decode Did Not Produce A Valid >150 Result

The target for MTP/spec decode was `>150 tok/s`, not merely "within 20 percent
of the non-spec baseline." That target was not reached with a valid endpoint
result.

What happened:

- K1 MTP can look fast in raw metrics, but it cannot realistically clear `>150`
  unless the verifier/proposer step is much cheaper or accepts many more tokens
  per step.
- `tp4-mtp-k1-parity-fix-v2` reached `107.77 tok/s`, but JSON and color failed
  immediately.
- ReplaySSM made K1 correctness plausible in eager mode, but graph capture
  introduced state races, and eager mode was far too slow.
- The K3 graph throughput probe crashed before producing a result:
  [`qwen36-ablation-tp4-mtp-k3-graph-throughput-probe-20260623024028.log`](../../data/qwen36-ablation-tp4-mtp-k3-graph-throughput-probe-20260623024028.log).

## ReplaySSM / GDN State Findings

ReplaySSM was the right correctness direction for GDN speculative verify, but
the graph path exposed two state hazards:

- captured prefill could corrupt the first decode token;
- eager full-accept restore could race captured decode replay, producing the
  `blue, green, red, yellow` double-processing signature.

Important artifacts:

- [`codex-gdn-parity-fix.md`](../../notes/codex-gdn-parity-fix.md): detailed
  chronological notes from the ReplaySSM/MTP work.
- [`replayssm iter14 graph full`](../../data/qwen36-ablation-tp4-mtp-k1-replayssm-iter14-graph-capnonuni-full-summary-20260622193709.json):
  graph captured non-uniform shapes, fast but color failed.
- [`replayssm iter19 graph cap-small full`](../../data/qwen36-ablation-tp4-mtp-k1-replayssm-iter19-graph-capsmall-full-summary-20260622222755.json):
  keeping prefill eager removed garbage, but JSON/color still failed at lower
  rate.
- [`replayssm iter20 restore-sync`](../../data/qwen36-ablation-tp4-mtp-k1-replayssm-iter20-graph-restoresync-summary-20260623023236.json):
  targeted restore sync did not fix correctness and lowered throughput.

Do not revive this lane with more flag roulette. The credible next step would
be deeper engineering: make rollback/commit graph-compatible or remove the
eager-between-replays dependency entirely.

## DFlash Status

DFlash remains the most plausible speculative direction, but no clean serving
result exists for this model lane.

Observed state:

- clean serial windows showed useful acceptance in smaller diagnostics;
- graph/forcegraph attempts hit dummy logits, static metadata, OOM, device-loss,
  or capture failures;
- recent clean-forcegraph and static-pool runs are untracked data artifacts, not
  promoted results.

If DFlash is reused on another model, start from the smallest canary-clean
serial verifier and add graph capture only after endpoint correctness is locked.

## Metadata And Scheduler Shortcuts

Rejected or unsafe shortcuts:

- broad metadata copy skipping: hung or failed quality;
- safer copy-skip variants: still failed known-good quality lanes;
- GPU-side `num_computed_tokens` update: failed quick JSON gate and did not
  improve speed;
- `cudagraph_copy_inputs=true`: crashed warmup in one ReplaySSM graph attempt
  with an inductor index-out-of-bounds error.

See:

- [`2026-06-21-qwen36-phase3-copy-skip.md`](../../notes/2026-06-21-qwen36-phase3-copy-skip.md)
- [`qwen36-research-map.md`](../../docs/qwen36-research-map.md)

## Patches Worth Remembering

- [`vllm-xpu-kernels-qwen36-routegemm1-blayoutfix-20260620.patch`](../../patches/vllm-xpu-kernels-qwen36-routegemm1-blayoutfix-20260620.patch):
  real routed-GEMM B-layout correctness bug.
- [`vllm-qwen36-decode-replay-boundary-20260613o.patch`](../../patches/vllm-qwen36-decode-replay-boundary-20260613o.patch):
  decode replay boundary instrumentation.
- [`vllm-qwen36-replay-correctness-stack-20260614bd.patch`](../../patches/vllm-qwen36-replay-correctness-stack-20260614bd.patch):
  replay correctness stack reference.

The live `/home/steve/src/vllm` tree is dirty with active experimental changes
as of this packet. Do not assume it represents a promoted patch set. Preserve
new useful diffs into `patches/` with linked results before resetting or
reworking that tree.
