# STATUS — Qwen3.8-27B FP8 vLLM XPU: shape-aliased prefill misdispatch into the spec-decode uniform-decode path (silent GDN state loss → degenerate output)

## Classification

| Field | Value |
| --- | --- |
| Evidence level | `community-reported`; the upstream defect and PR are open items on the upstream tracker, not lab-confirmed |
| Patch review status | complete diff reviewed; applied and CPU-tested against both actual local R50 source copies, 2026-09-08 |
| Tested in reference lab | Original classifier: 15 CPU cases/copy, normal 12/12 parity but tiny screen fails. Separate maintainer GDN phase guard: 8 CPU cases/copy, 120/120 probes, two fresh compiled MTP strict suites with 12/12 exact parity. No multi-hour soak |
| Safe to merge as documentation | yes |
| Eligible for `repro/` or `results/` | no until `B70-tested` |

## Provenance

- Contributor: [`dominick253`](https://github.com/dominick253)
- Source: [PR #45](https://github.com/steveseguin/b70-optimization-lab/pull/45), commit `f12e834cf3eb53a03ce4eae46ae54029b51b86d6`; original packet preserved in local commit `41c934a39`
- Upstream defect: [vllm-project/vllm issue #53051](https://github.com/vllm-project/vllm/issues/53051) ("Prefill misdispatched into spec-decode FULL cudagraph when prompt length == 1 + num_speculative_tokens → silent GDN state loss, garbage output (hybrid/Qwen3-Next models)")
- Upstream fix (adopted here): [vllm-project/vllm PR #53059](https://github.com/vllm-project/vllm/pull/53059) — "[Bugfix] Reject shape-aliased prefills in uniform-decode classification" by `allenzz-dev` (open, unmerged at capture time)
- Right-to-submit statement: present in the PR description
- Third-party material and attribution: vLLM (Apache-2.0, upstream issue/PR credited above); Intel `neural-download/vllm-openai-xpu` image lineage built by this lab's own `repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/` chain; `Qwen/Qwen3.8-27B-FP8` official block-FP8 checkpoint

## Contributor Claim

On a two-B70 production host serving the lab's R50-lineage image
(`neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-serial-fa-split-gdn-r50`,
vLLM `0.27.2rc1.dev77+gac7509e2b.xpu`), the service emits degenerate
single-token repetition walls (`!!!!!`, `00000…`, `oooooo…`, `||||…`) after
6–24 h of uptime under real multi-session load, while health, throughput, and
short probes stay clean. Root cause matches upstream issue #53051:
`GPUModelRunner._is_uniform_decode` classifies a batch as uniform decode by
shape only; with speculative decoding (`uniform_decode_query_len = 1 +
num_spec_tokens`), any prefill step scheduling exactly that many tokens per
request aliases the uniform-decode shape, replays capture-time metadata with
null/stale GDN state indices, and silently skips recurrent-state writes.
Applying upstream PR #53059's classifier guard plus a microbatch veto, then
restarting, cleared the signature on the contributor's host (clean probes and
soak-start after deployment; longer soak in progress at capture time).

## Relation To This Lab's Records

This looks like the same failure family as the lab's own
[2026-08-22 chunked-prefill corruption finding](../../experiments/qwen38-27b-b70/notes/2026-08-22-qwen38-longkv2-closure-and-chunk-corruption-finding.md)
(`B70_QWEN3!!!!…` degeneration after multi-chunk prefill history,
dose-dependent, mitigated by `VLLM_XPU_GDN_SPEC_PERSISTENT_SCRATCH=0`) and the
R178–R186 depth-2 phantom-first-token investigation (stale GDN metadata inside
a compiled piece). They may share the "stale/absent GDN recurrent-state write
under an aliased or split prefill step" mechanism, but that equivalence is a
hypothesis, not a measured result: different images (R50 vs the lane's
sealed/split stage), different trigger shapes (prompt-length aliasing vs
chunked prefill dose), different workloads. The lab's d5 discriminator
(persistent scratch off) and the upstream classifier fix are two different
mitigation points that would both silence a shared root cause.

## Contributor Environment

| Field | Value |
| --- | --- |
| GPU model / count / VRAM | 2x Intel Arc Pro B70 (Battlemage G31, PCI `8086:e223` at `0000:03:00.0` and `0000:08:00.0`), 32 GiB each |
| OS / kernel | Ubuntu 26.04; `7.0.0-30-generic` |
| GPU driver | `xe` `srcversion 85B7CA089405934276CBAD3` |
| Engine / image | `neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-serial-fa-split-gdn-r50`, image digest `sha256:dcdbfca2b7904b67dde6625d0b49733f6b76adce2199c2bd948dafca75f211a1`; vLLM `0.27.2rc1.dev77+gac7509e2b.xpu` |
| Docker | 29.1.3, `--privileged --network host`, `ZE_AFFINITY_MASK=0,1`, `ONEAPI_DEVICE_SELECTOR=level_zero:0,1` |
| Model repo and revision | `Qwen/Qwen3.8-27B-FP8` (official block-FP8: 66 shards, 1606 tensors, 407 `weight_scale_inv`, 882 `modules_to_not_convert`, 30.87 GB) |
| Quantization | native block-FP8 weights (`--quantization fp8`), `--kv-cache-dtype fp8_e4m3`, `--mamba-ssm-cache-dtype bfloat16` |
| Command and env | served via the contributor's launcher (equivalent to the lab's R50 chain): `--dtype float16 --tensor-parallel-size 2 --max-model-len 200000 --max-num-seqs 4 --max-num-batched-tokens 8192 --block-size 64 --gpu-memory-utilization 0.95 --enable-chunked-prefill --enable-prefix-caching --disable-sliding-window --language-model-only --enable-auto-tool-choice --tool-call-parser qwen3_coder --reasoning-parser qwen3 --compilation-config '{"cudagraph_mode":"PIECEWISE","cudagraph_capture_sizes":[1],"max_cudagraph_capture_size":1,"splitting_ops":[], …}' --speculative-config '{"method":"qwen3_next_mtp","num_speculative_tokens":1}'` |
| Speculation policy at incident time | MTP1 (`num_speculative_tokens=1`), so `uniform_decode_query_len=2` |
| Prompt / output / concurrency | real multi-session agent traffic (3–4 concurrent sessions, mixed prompt lengths, chunked prefills, prefix-cache hits), 512-token probes for the recorder |
| Metric | incident signature + post-fix smoke, not a rate: `finish_reason=stop`, exact arithmetic (`17*23=391`), exact 1–30 counting, no degeneration |
| Logs / evidence | streaming recorder + frozen incident folders (contributor host paths, not redistributed): `~/qwen-bang-logs/run-*`; incident-window screenshots 2026-09-08 ~00:48–01:02 EDT showing `oooo…` walls (~40+ lines) and a full-panel zero wall in a dsh IDE-agent session |

## What Was Actually Run (contributor host)

- Production service on the R50 image with MTP1, live agent traffic, 2026-09-07→09-08: degenerate walls observed after 6–24 h dwell; restart cleared them each time.
- Post-fix (bind-mounted patched `gpu_model_runner.py` over the image's editable install `/workspace/vllm/vllm/v1/worker/gpu_model_runner.py`): clean startup, health, alias, exact arithmetic/counting smokes; a 400-record context probe and the streaming `!!!!!` detector recorded zero events before the next planned restart. Soak in progress; not complete.
- NOT RUN here: controlled reproduction of the aliased prefill on demand (the incident needs real mixed traffic dwell); the lab's strict 12-prompt identity suite; vision; depth >1 profiles post-fix.

## The Fix (for review, not promoted)

`reported/vllm-gpu-model-runner-uniform-decode-alias.patch` — 47-line diff,
`_is_uniform_decode` only:

1. Reject the shape-aliased prefill: after the shape test passes, additionally
   require every request to be past its prompt
   (`num_computed_tokens_cpu[:num_reqs] >= num_prompt_tokens[:num_reqs]`).
   This is upstream PR #53059's guard.
2. **Maintainer correction:** no microbatch veto is present in the supplied
   patch. `_allow_microbatching` appears only as unchanged trailing context.
   A separate deployed contributor guard, if any, was not submitted or tested.

`reported/test_is_uniform_decode_red_green.py` — illustrative RED/GREEN test
with embedded stock and patched method strings, running 14 cases:
stock must misclassify all 5 aliased shapes (2-token prompt at MTP1,
3-token at MTP2, chunked last chunk, mixed batch, 1-token no-spec) and
preserve all genuine decode classifications. Contributor run: RED PASS,
GREEN PASS.

Deployment shape used by the contributor: the R50 image's live module is the
editable install at `/workspace/vllm/vllm/v1/worker/gpu_model_runner.py`
(`/opt/venv` site-packages copies are shadowed); the fix is bind-mounted
read-only over it by the launcher with a grep assert, so it survives container
recreation. Keep the stock copy for rollback.

## Known Issues

- The upstream PR is open and unmerged at capture time; this packet records
  adoption, not an upstream endorsement.
- The supplied patch has no microbatch veto; the original description of (2)
  was inaccurate. No such guard is part of the local candidate image.
- The original illustrative test prints failures without a failing exit code.
  The maintainer's actual-source test enforces failures and covers capture
  overrides before `input_batch` exists, prompt boundaries and padded rows.
- No controlled on-demand reproduction exists here; the claim rests on the
  incident signature matching upstream #53051 plus post-fix stability, which
  is consistent-but-not-conclusive evidence.

## Open Questions For The Lab

- Does the aliased-prefill trigger reproduce on the lab's R187 sealed lane
  (MTP depth ≥ 1, piecewise compile) with a 2-token prompt under the strict
  harness, or does the whole-graph `splitting_ops=[]` line avoid it the way it
  avoids the depth-2 phantom?
- Does `VLLM_XPU_GDN_SPEC_PERSISTENT_SCRATCH=0` (the lab's d5 mitigation)
  also suppress the alias path, or is the alias handled purely in the
  scheduler/classifier layer?
- Is the 2026-08-22 chunk-dose corruption the same mechanism (shared stale GDN
  state write), or an independent kernel-path defect?

## Disposition

The classifier fix is integrated in a separate local candidate image; build
identity, reproduction commands, limits and contributor credit are in
[validation/README.md](validation/README.md). No promoted runtime, benchmark
identity or score was changed. Bounded GPU tests did not eliminate tiny-prompt
output walls; they do not establish the cause or resolution of the contributor's
multi-hour incident. See the [GPU record](validation/gpu-20260909/README.md).

A separate maintainer GDN phase-aware prefill correction subsequently passed
the bounded local screen and normal-suite/fresh-server parity. See the
[follow-up](validation/priority-20260909/README.md). This local finding is
`B70-tested`; the original contributor incident remains `community-reported`.

The [matched-image target-oracle matrix](validation/target-oracle-20260909.md)
subsequently passed all five 12/12 comparisons, with 96 additional passing
probes and healthy teardown. The multi-hour soak remains pending.

September 12 upstream review: the separate one-token phase defect is already
tracked in vLLM #51562 with PR #51565. Current-source CPU tests confirm the
fresh-request routing failure, but also expose trailing-padding mishandling in
our narrower local guard. Prefer validating the upstream proposal before
promotion; the earlier bounded B70 evidence and contributor incident status
remain unchanged. See the [review packet](../../experiments/qwen38-27b-b70/upstream-review-20260912/README.md).

Remains `community-reported` documentation. If the lab reproduces the alias
trigger on its sealed lane and finds the classifier guard effective, this
belongs in the R187/R50 chain's README as a known upstream defect with the
chosen mitigation; until then it is a pointer, not a recipe.
