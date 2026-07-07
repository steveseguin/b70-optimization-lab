# Codex Agent Handoff

Last updated: 2026-07-05

This file is the first thing a new Codex agent should read when continuing the
Intel Arc Pro B70 LLM optimization work.

Gemma 4 26B A4B Q8 pause/resume bookmark: read
`results/gemma4-26b-a4b-q8-b70/HANDOFF.md` before doing more Gemma work. It
now contains the production backend recipe, smoke commands, current record
identity, and what remains worth trying. If the user switches to a different
model, treat Gemma as bookmarked/reference rather than continuing it by
inertia.

## Active Workspace Policy

Use `/home/steve/llm-optimizations` as the single active workspace for new
Gemma/Qwen/MiniMax work. It is the branch-attached `main` checkout and should track `origin/main`; run `git status --short --branch` and `git log -1 --oneline` for the exact current head.

Do not start new experiments from `/home/steve/qwen36-results-main`; that
stale detached linked worktree was archived and removed during cleanup. Raw
packets from that worktree are preserved locally at
`/home/steve/qwen36-raw-archives/qwen36-results-main-detached-4b33bb2f-20260702.tar.zst`;
use `results/qwen36-35b-quark-int8-b70/archive-retention.md` for the checksum,
retention policy, and future Qwen restart procedure. Restore raw packets only
into a temporary non-worktree directory, then promote compact summaries into
`main` if needed.

Never use broad `git add -A` in either worktree. Stage result packets, patches,
scripts, and notes by explicit path from the active workspace.

## Current Objective

Active target as of the latest switch request:

- `Intel/Qwen3.6-27B-int4-AutoRound` on Intel Arc Pro B70.
- Work in the single active workspace `/home/steve/llm-optimizations`.
- Start with `results/qwen36-27b-autoround-int4-b70/HANDOFF.md` and
  `experiments/qwen36-27b-autoround-int4-b70/README.md`.
- Immediate milestone is complete. TP1 vLLM/XPU serves at
  `max_model_len=2048`, the smoke passed, and the fixed Qwen realistic
  fresh-response gate exists.
- Current baseline valid row is the env-only promote-source candidate:
  `VLLM_XPU_GDN_PROMOTE_ACCEPTED_SPEC_STATE=1` plus
  `VLLM_XPU_GDN_NONSPEC_POSTPROCESS_ACCEPTED_STATE=0`, MTP3/cg8, one B70,
  XPU graph on. Conservative strict-suite headline is `53.522 tok/s` median
  generated-token throughput for tokens 1-100 after TTFT, with support rows
  `54.861` and `53.992`; same-window baseline control was `48.345`.
  Quality suite passed and matched baseline. Start from
  `results/qwen36-27b-autoround-int4-b70/promote-source-noacceptedpost-20260703.json`.
- LocalMaxxing approved this strict/fresh result as `cmr4gokx90061nv01lhoe3ft8`.
  Do not submit synthetic MTP5/cg16 or invalid postprocess-skip rows.
- Current fastest quality-gated practical row is the separate
  `webhie/Qwen3.6-27B-int4-AutoRound + runtime INT8 target LM-head
  (BF16 scales) + runtime INT4 draft LM-head (BF16 scales)` ReplaySSM lane:
  MTP3/cg8, one B70, exact GDN state handling, commit-in-forward, and
  conservative PyTorch slot management fallback. Strict fresh headline is
  `68.23626314761921 tok/s` median tokens 1-100 after TTFT, p10
  `62.316569643325344`, mean `67.82964696710413`, `cached_tokens=0` every row,
  repeat64 quality passed and matched baseline. LocalMaxxing approved it as
  `cmr9atqb800msqr01u760xh0t`. This is the current best measured valid
  same-recipe row; the improvement over the prior approved `67.519` row is
  small and should be treated with variance caution, not as a new mechanism.
  Start from
  `results/qwen36-27b-autoround-int4-b70/webhie-int8lmhead-bf16scale-draftint4-replayssm-current-confirm-20260706.json`
  and
  `experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-06-current-confirm-68tok-and-textonlymtp-no-win.md`.
- Important attribution for that current row: the native ReplaySSM slot-copy
  op passed direct BF16/FP16/FP32 parity, but endpoint A/B did not show a speed
  win (`66.871` native vs `67.300` PyTorch slot-management fallback), so do
  not credit native slot-copy as the source of the record. The previous
  BF16-scale INT8-LM-head record was `65.27648650325429 tok/s`, LocalMaxxing
  `cmr5iu3gk00bfq901nidgcana`.
- Latest target-body timing/no-win screen:
  `experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-07-targetbody-timing-and-mlp-workspace-no-win.md`.
  The checkpoint is dense `qwen3_5_text`, not MoE, so MoE layerlets are a
  distraction for this model. The graph-none/no-spec profile measured
  `39.971 ms/token` model-forward plus `2.755 ms/token` logits, and the
  enforce-eager split showed linear-attention/GDN, full-attention, dense MLP,
  and norms as the visible body buckets. The easy dense-MLP
  `VLLM_XPU_SHARED_EXPERT_ACT_WORKSPACE=1` idea is closed: it first failed
  Dynamo on `ContextVar.get`; after a compile guard patch it still failed
  vLLM graph splitting. Patch preserved at
  `patches/qwen36-27b-autoround-int4-b70/vllm-qwen2moe-act-workspace-compileguard-no-win-20260707.patch`;
  active source was reverted.
- Latest ReplaySSM state-digest trace:
  `experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-07-replayssm-state-digest-trace.md`.
  A default-off trace-only patch records `conv_state`, ReplaySSM `d/k/g` ring,
  `conv_pending`, and cursor metadata at commit/stage/spec-decode boundaries.
  Diagnostic endpoint run passed strict fresh/cached-zero mechanics at
  `67.453 tok/s` with quality skipped and wrote compact summaries under
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-replayssm-state-digest-trace-20260707T041855Z-summary.*`.
  This is transaction/tape evidence, not a promoted benchmark or LocalMaxxing
  candidate.
- Latest current-recipe subtiming check:
  `experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-07-current-mtp3-subtiming.md`.
  It reproduced the current recipe at `68.296 tok/s` with strict
  fresh/cached-zero mechanics and quality skipped. The sampled decode bucket is
  already fixed-shape MTP3 (`4` unpadded, `4` padded, `3` scheduled spec
  tokens, `PIECEWISE` graph). Do not chase padding cleanup or the noisy large
  draft/proposer labels from this run; synchronized timing already closed
  MTP-next as a sub-ms graph path.
- Latest target-body micro-screen:
  `experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-07-rmsnorm-gated-native-route-no-win.md`.
  A default-off `RMSNormGated.forward_xpu` route through existing `_C.rms_norm`
  plus SiLU multiply was faster in microbench but not bit-exact and lost a
  same-window 4-GPU endpoint A/B. Active source was reverted; patch artifact is
  preserved as no-win evidence. Do not repeat this Python routing version.
- Latest full-attention Q/K norm + RoPE screen:
  `experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-07-qgate-direct-qkrope-no-win.md`.
  A purpose-built native `_C.fused_qgate_qk_norm_rope` op beat the isolated
  section in microbench by about `0.06 ms` per full-attention layer, but the
  strict endpoint screen lost (`66.953 tok/s`, quality skipped) against the
  current `68.236 tok/s` record and `68.296 tok/s` current-recipe support row.
  Active source and `_C.abi3.so` were restored; patches/results are preserved
  only so we do not rediscover the same dead end.
- Latest true native gated RMSNorm kernel screen:
  `experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-07-rmsnorm-gated-native-xpu-kernel-no-win.md`.
  A purpose-built `_C.rms_norm_gated` op exactly matched Qwen's
  `norm_before_gate=True` GDN output norm (`max diff=0`) and was about `3.6x`
  faster in isolated hidden-size-128 microbench. The endpoint did not move:
  strict screen `68.453 tok/s` was within variance, and same-window A/B was
  baseline `67.980` vs native `67.928`. Active source and `_C.abi3.so` were
  restored. Do not repeat small RMS/GDN-output wrapper fusion as the next
  speed lane; target accepted tokens per verifier step, graph-safe GDN
  transaction work, or a producer-integrated LM-head shortcut instead.
- Latest intrinsic Qwen MTP adaptation screen:
  `experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-07-intrinsic-mtp-adaptation-screen.md`.
  New scripts `scripts/evaluate-qwen27-intrinsic-mtp-offline.py` and
  `scripts/train-qwen27-intrinsic-mtp-adapter.py` can evaluate and train
  mergeable `model_extra_tensors.safetensors` MTP candidates. The best v6
  direct `mtp.fc.weight` candidate improved offline acceptance under both BF16
  and endpoint-style INT4-dequant draft heads, but endpoint validation was a
  no-win: strict fresh speed `67.4025 tok/s` with quality skipped, and branch
  trace accepted draft prefix `1.5773`, worse than the current recipe trace
  `1.6727`. Do not repeat the same v6 FC-only intrinsic-MTP training loop; use
  endpoint-trace accepted-prefix behavior as the arbiter before spending speed
  runs on future drafter candidates.
- Latest MTP5 intrinsic adaptation screen:
  `experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-07-intrinsic-mtp5-adaptation-no-endpoint.md`.
  Parallel MTP5 INT4-dequant runs improved offline heldout accepted draft
  tokens from about `1.374` to at best `1.78198` (`2.78198` visible
  tokens/step), but this is not enough to justify cache16/MTP5 endpoint
  overhead and is only modestly above the current endpoint MTP3 branch trace.
  Closed without endpoint run. Next drafter work needs a materially stronger
  architecture or endpoint-trace accepted-prefix lift, not FC-only MTP5 tuning.
- Latest producer-side INT4 LM-head shortcut screen:
  `experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-07-int4-top1-prototype-runtime-hang.md`.
  A default-unwired `_xpu_C.int4_gemm_w4a16_top1` prototype was preserved as
  `patches/qwen36-27b-autoround-int4-b70/vllm-xpu-kernels-qwen27-int4-top1-prototype-runtime-hang-20260707.patch`,
  but it is not a win: the oneAPI 2026 BMG-only build required `libsycl.so.9`,
  the Qwen27 microbench hung with GPU idle and oneDNN `bad engine kind`, and
  the sycl8 runtime package binary was restored. Before revisiting this lane,
  make the op build/import in the normal runtime and prove dense-argmax
  correctness plus an isolated microbench win.
- Current-recipe deeper MTP is closed, not merely blocked on a missing
  cache16 dispatch. MTP4/MTP5 need a ring length of at least `16`; leaving
  cache8 fails readiness. A follow-up native cache16/spec6 patch compiled and
  passed direct BF16/FP16/FP32 parity, but endpoint screening still lost:
  MTP3/cache8 control `67.816 tok/s`, MTP3/cache16 `65.410`,
  MTP4/cache16/cg16 `61.637`, and MTP5/cache16/cg16 `58.140`, with heavy AOT
  spill warnings. Do not repeat config-only or simple dispatch-widening
  MTP4/MTP5 sweeps on this recipe. See
  `experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-06-draftint4-depth-cachelen-no-win.md`,
  `experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-06-replayssm-cache16-native-s6-no-win.md`, and
  `patches/qwen36-27b-autoround-int4-b70/vllm-qwen27-replayssm-cache16-spec6-no-win-20260706.patch`.
- Historical pre-20260706 draft-INT4 follow-up is closed diagnostic/no-win for
  the non-ReplaySSM recovery lanes. The runtime GDN
  metadata patch remains useful because it fixes graph-bypass device-lost
  crashes, but fast target-INT8 + draft-INT4 rows at `68-72 tok/s` fail repeat
  quality (`55/64` `blue, green, red, yellow`, `9/64` `blue, green, red`).
  Keeping scheduled spec rows on the spec path, graph-off, graph-off/no-async,
  cg4, and normal align/restore all failed the same way. Serial GDN flags are
  also closed: native-on `SERIAL_SPEC_*` runs were fast (`70-72 tok/s`) but
  still invalid and likely bypassed the Python serial path, while forcing
  `VLLM_XPU_GDN_NATIVE_SPEC_DECODE=0` exercised the serial/fallback path and
  collapsed to `~9.7-12.3 tok/s`, with no promotable quality result. See
  `experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-05-draft-int4-serial-gdn-nativeoff-no-win.md`.
  The later ReplaySSM+commit-in-forward+draft-INT4-LM-head lane supersedes the
  earlier `61-62 tok/s` clean ReplaySSM rows and is now the current record.
  Do not repeat the failed non-ReplaySSM rows; next credible work is a
  fixed-shape exact accepted-prefix GDN/DeltaNet state tape with GPU-side
  commit, a verifier/LM-head shortcut, or a stronger drafter/branch-regenerate
  path, not more `SERIAL_SPEC_*` source/offset sweeps. A later Python-only SSM promotion switch
  crashed before artifacts, and the matched C++ conv pre-copy disablement made
  repeat64 quality worse (`62/64` `blue, green red yellow`), so do not rerun
  blind conv-copy disablement. See
  `experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-05-draft-int4-gdn-runtime-metadata-and-replayssm.md`,
  `experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-05-draft-int4-specrows-and-graph-bisect-no-win.md`,
  `experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-05-native-promote-ssm-only-crash.md`,
  `experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-05-native-spec-conv-copy-gate-no-win.md`,
  `experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-05-accepted-prefix-tape-contract.md`,
  and
  `patches/qwen36-27b-autoround-int4-b70/vllm-qwen27-keep-scheduled-spec-rows-no-win-20260705.patch`.
  The executable contract starts at
  `scripts/check-gdn-spec-recurrent-exact.py`: it now verifies exact recurrent
  prefix state, accepted-prefix SSM/conv commit equality on XPU for k=3/4/5,
  and endpoint row-to-draft-prefix mapping for full reject, partial reject,
  full accept with bonus, shifted full accept, draft-only, and suppressed
  bonus/replacement tails. Run it before touching native GDN tape/commit code;
  see
  `experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-06-gdn-endpoint-row-contract-extension.md`.
  A second native
  prefix harness, `scripts/check-gdn-native-spec-prefix.py`, directly validates
  the packed `gdn_attention_spec_decode` column contract on XPU: column `j` is
  the state after packed row `j`, and `num_accepted_tokens=N` selects source
  column `N - 1`. It passed varied GPU/shape checks; see
  `experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-05-native-spec-prefix-contract-check.md`.
  Do not reopen plus-one/prefix-count source-column patches; the next credible
  patch is making ReplaySSM/tape commit exact and graph-safe, not changing the
  accepted-count convention. A first default-off commit-overhead patch,
  `VLLM_XPU_GDN_REPLAYSSM_COMMIT_IN_FORWARD=1` with the separate post-verify
  commit skipped when no restore correction is active, passed strict fresh and
  repeat64 quality at `63.854 tok/s`. It recovers some ReplaySSM overhead but
  remains below the `65.276` record, so keep it as no-promote evidence:
  `experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-05-replayssm-commit-in-forward-skippost-no-promote.md`
  and
  `patches/qwen36-27b-autoround-int4-b70/vllm-qwen27-replayssm-commit-in-forward-skippost-no-promote-20260705.patch`.
- The same-quality-class `cyankiwi/Qwen3.6-27B-AWQ-INT4` checkpoint was
  screened after download. It loads in vLLM/XPU with
  `--quantization compressed-tensors` and passes the strict fresh/cached-zero
  gate, but only reaches `56.565 tok/s`, so it is closed no-win and should not
  be repeated unless compressed-tensors W4A16 performance materially changes.
  See
  `experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-04-cyankiwi-awq-int4-screen-no-win.md`.
- Latest frontier audit: BF16-scale controls reconfirmed below the record,
  FP16 scale storage was slower, webhie target-only BF16 scope had lower TTFT
  but failed repeat32 quality once, standalone compact full-vocab
  top-1/candidate-max kernels were exact but slower than dense oneDNN, and a
  oneDNN Graph `MatMul -> ReduceMax` inspector did not find a fusion shortcut
  (BF16 stayed as two partitions; the tested INT8 graph MatMul form was
  rejected). Do not promote target-only webhie without a new stability fix, and
  do not spend more endpoint runs on wrapper-level sampler/reduction tweaks.
  The next credible speed lanes are a real oneDNN/XPU-class top-ID LM-head
  producer, a materially stronger target-matched drafter, or deeper
  partial-group / branch-regenerate support. See
  `experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-04-frontier-audit-onednn-graph-and-drafter.md` and
  `experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-03-fused-verifier-top1-design-blocker.md`.
- Latest branch/regenerate trace probe: after repairing local sycl9-built
  XPU extension binaries back to sycl8 (`_C`, `_moe_C`, `_vllm_fa2_C`, and
  `libattn_kernels_xe_2`), the default-off
  `VLLM_XPU_BRANCH_REGEN_TRACE=1` hook completed a strict fresh diagnostic row
  at `65.078 tok/s` with `cached_tokens=0`. It measured `220` scheduled
  verifier rows, mean accepted draft prefix `1.6727`, mean raw visible tokens
  `2.6727`, full accept `39.09%`, and `292` remaining branchable draft rows
  after partial rejects. This is useful transaction/tape evidence, but too
  narrow to be the primary `125+ tok/s` path alone. See
  `experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-06-branch-regen-trace-probe-and-sycl8-restore.md`.
- Latest wrapper-level MTP dispatch shortcut is closed no-win. A default-off
  `VLLM_XPU_MTP_TEXT_INPUT_IDS_NEXT=1` spike tried to pass token IDs into
  text-only recurrent Qwen3.5 MTP draft forwards instead of external
  `inputs_embeds`; it first crashed on `inputs_embeds=None` dynamic-shape
  sizing, then a compile-shape workaround stalled during decode PIECEWISE graph
  capture. Active vLLM source was reverted; preserve only the note and patch:
  `experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-05-mtp-text-inputids-next-no-win.md`
  and
  `patches/qwen36-27b-autoround-int4-b70/vllm-qwen27-mtp-text-inputids-next-no-win-20260705.patch`.
  Do not repeat this exact shortcut without a deeper compile/cudagraph design
  change.
- Latest GDN accepted-source packed decode precheck is also closed no-win. A
  default-off `VLLM_XPU_GDN_PACKED_DECODE_WITH_SOURCE=1` patch promoted conv
  and SSM accepted-source rows before the packed one-token helper. Same-window
  strict fresh screen passed but lost to control (`65.077` vs `65.631 tok/s`).
  Active vLLM source was reverted; preserve only
  `experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-05-gdn-packed-decode-with-source-no-win.md`
  and
  `patches/qwen36-27b-autoround-int4-b70/vllm-qwen27-gdn-packed-decode-with-source-no-win-20260705.patch`.
  Do not repeat Python-level source-promotion shortcuts; future GDN work should
  be an exact accepted-prefix tape/transaction or a native graph-safe commit.
- Latest draft top-k follow-up is closed as diagnostic-only. K64 tracing shows
  the target token is in draft alternatives very often, but Qwen27 MTP drafting
  is sequential, so independent post-hoc reranking invalidates later draft rows
  and the target-owned bonus row. Held-out margin/sparse-bias reranking did not
  improve acceptance, and the legal final-slot upper bound is too small to
  justify endpoint work. See
  `experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-04-draft-topk64-and-sequential-reranker-limit.md`.
- Latest token-tree follow-up is closed as config-only no-win. Existing vLLM
  `speculative_token_tree` works mechanically for Qwen27/XPU, but the current
  proposer still pays full draft logits for tree alternatives. Same-suite
  calibration results: MTP3/cg8 control `63.871 tok/s`, binary depth-2 tree
  `60.526`, root top-3 `63.107`; root top-2 stalled during drafter checkpoint
  load. See
  `experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-04-token-tree-mechanical-screen-no-win.md`.
- Latest short-decode `MAX_NUM_BATCHED_TOKENS` follow-up is closed no-win.
  MBT1536/2048/4096 passed the strict fresh gate at `63.829`, `64.239`, and
  `64.779 tok/s`, all below the `65.276` record. The same-window MBT1024
  control is invalid because GPU0 hit `UR_RESULT_ERROR_DEVICE_LOST` during
  bench after smoke passed. Keep MBT1024 for short decode and MBT4096 only for
  the separate 32K service lane. See
  `experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-04-short-decode-mbt-screen-no-win.md`.
- Latest draft-only subset follow-up is closed-negative. A default-off
  hot-vocab INT8 LM-head top-1 patch for Qwen MTP drafting passed the strict
  fresh gate but lost badly in a same-window four-GPU screen: dense control
  `65.631 tok/s`, hot512 `50.126`, hot1024 `52.614`, hot2048/1779-usable
  `56.418`; output hashes matched dense control on only `11/12` prompts. Do
  not repeat subset-vocab draft approximation. See
  `experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-04-draft-hot-vocab-top1-no-win.md`.
- Latest EAGLE1 local drafter lane is closed-negative for the current draft.
  The pipeline is mechanically useful, but not a record path yet. See
  `experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-04-eagle1-local-training-pipeline-smoke.md`
  and
  `experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-04-eagle1-heldout-endpoint-negative.md`.
  A four-GPU no-spec corpus produced `16384` usable hidden rows, `128` samples,
  and `0` continuity breaks. The best held-out local EAGLE1 draft reached
  `2.1016` mean accepted draft tokens over `1024` calibration starts, but the
  endpoint strict Qwen realistic suite failed badly: `cached_tokens=0` on all
  requests, but only 10 rows had enough token-id events for the primary metric,
  measurable-row median was `21.7408 tok/s`, and several prompts looped
  repeated tokens such as `Cooperativa` / `the, the`. Do not promote, submit,
  or repeat this exact endpoint attempt. Future EAGLE work needs a larger and
  more diverse non-final training corpus plus stricter held-out quality checks
  before endpoint validation.
  A follow-up isolation matrix also failed: default GDN state, graph-off/eager,
  and k1 depth did not rescue the draft (`19.828-22.410 tok/s`, all failed),
  while current-state graph k3 stalled before JSON output. See
  `experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-04-eagle1-endpoint-isolation-matrix.md`
  and the compact ignored-data summary force-tracked at
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-eagle1-endpoint-isolation-20260704T094450Z-summary.json`.
  If EAGLE is revisited, start with corpus/eval v2 rather than endpoint config
  sweeps.
  The corpus/eval v2 tooling entry point is
  `experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-04-eagle-corpus-v2-tooling.md`.
  The first v2 chat calibration smoke is
  `experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-04-eagle-corpus-v2-chat-calib-smoke.md`:
  `3840` rows and metadata on `24/24` samples, but only `0.240` mean accepted
  for a tiny two-epoch draft. It proves metadata plumbing, not draft quality.
  The four-GPU v2 heldout screen is
  `experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-04-eagle-corpus-v2-4gpu-heldout.md`:
  `96` chat prompts, `15360` rows, `96/96` sample metadata, and `0` continuity
  breaks, but only `0.489` mean accepted on heldout shard `3` after training on
  shards `0-2`. Do not endpoint-test this compact draft; future EAGLE work
  needs materially stronger data/training/init first.
  Followups in
  `experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-04-eagle-corpus-v2-followups-closed.md`
  did not rescue the lane: staged curriculum `0.616`, balanced task holdout
  `0.601`, old-draft transfer `0.201`, and all-96 training evaluated on a
  separate calibration suite `0.438`. Current compact EAGLE v2 is closed again.
  A v3 target-architecture/loss screen is also closed no-endpoint:
  target-shaped one-layer drafts and token-heavy losses underperformed, with
  the best compact frozen-base residual variant only `0.647` heldout mean
  accepted and `0.423` separate-calibration mean accepted. See
  `experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-04-eagle-v3-target-loss-offline-no-endpoint.md`.
  Do not repeat larger/target-shaped EAGLE on the same v2 corpus without a
  materially new data or architecture idea.
  Ex0bit EAGLE3/DFlash was then revisited with target-owned aux hidden states
  (`1,31,60`) and an Ex0bit-format adaptation path. Direct Ex0bit remained
  unusable (`0.289908` mean accepted); the larger four-GPU v3 adaptation used
  384 prompts / 61,440 rows, trained `fc-lm-head` on 288 prompts, and improved
  heldout rollout to `0.6003787878787878` mean accepted. This is positive
  training signal but still not an endpoint path: step-1 exact is `48.65%`,
  while step-2 conditional exact collapses to `20.10%`, far below current MTP3
  accepted depth. A first multi-step rollout objective improved the best
  heldout mean to `0.6693046536796536`; a narrowed original-init rollout-3
  sweep at `lr=2e-5` then reached `0.973146645021645` (`52.81%` step-1 exact,
  `50.04%` step-2 conditional, `49.40%` step-3 conditional). This is meaningful
  training progress, but still below endpoint threshold. Continuation training
  reached only `1.0142045454545454` and widened train/heldout overfit. A
  larger v4 corpus then collected 576 prompts / 92,160 rows and improved the
  best original-init rollout-3 recipe only modestly to
  `1.0592532467532467` (`55.98%` step-1 exact, `52.39%` step-2 conditional,
  `50.55%` step-3 conditional). This confirms the pipeline is learning, but
  not fast enough to justify endpoint plumbing. A bounded all-scope follow-up
  from the v4 best checkpoint reached only `1.0707972582972582`, and original
  all-scope low-LR runs underfit, so simple full-draft unfreezing is not the
  unlock. V5 rollout-5 training is the current best diagnostic family; the
  best checkpoint uses `decay=1.0`, `lr=2e-5` and reaches
  `1.2866838023088023` mean accepted (`59.02%` step-1 exact, `55.32%`
  step-2 conditional, `57.29%` step-3 conditional, `3056` full-5 accepts).
  A disk-cleanup retry plus accepted-prefix survival objective then raised the
  offline diagnostic best to `1.340886544011544` mean accepted (`59.92%`
  step-1 exact, `56.26%` step-2 conditional, `58.50%` step-3 conditional,
  `3602` full-5 accepts). This confirms the lane is learning but is still
  below endpoint threshold; continue training research, not endpoint/kernel
  integration. V6 broader chat-style aux-data collection completed at
  `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-eagle3-aux-v6-chat-4gpu-20260707T012928Z`
  with `179650` usable rows, zero continuity breaks, zero aux bad files, and
  one omitted five-token sample. The v5 survival checkpoint reaches only
  `0.8866846157479571` mean accepted on v6 heldout shard 3 (`42342` starts).
  A v6 survival-objective sweep from that checkpoint improved v6 heldout to
  `1.0069670776061594` mean accepted, and a first-step-emphasis continuation
  (`rollout_loss_decay=0.5`) improved it to `1.0401492607812575`, still below
  endpoint threshold. A v6 step-focus follow-up from that checkpoint reached
  only `1.0493835907609466` mean accepted
  (`v6sf-r3-lr1e-5-decay0p25-rank0p1`), with compact summary
  `experiments/qwen36-27b-autoround-int4-b70/diagnostics/qwen27-ex0bit-eagle3-v6-stepfocus-summary-20260707.json`.
  Current next move is offline-only but should not be another same-corpus
  first-step-emphasis sweep: improve v6 data quality with concrete snippets,
  tables, logs, and code fragments, or switch back to verifier/LM-head /
  graph-safe state-transaction work. Do not endpoint-test this adapted draft
  unless offline mean accepted reaches at least `1.5-2.0`.
  That concrete-context v6b data-quality screen is now complete:
  `experiments/qwen36-27b-autoround-int4-b70/eagle-chat-corpus-v6b-suite.json`
  produced `384` prompts / `61268` usable rows / zero continuity breaks
  (`diagnostics/qwen27-eagle3-aux-v6b-corpus-summary-20260707.json`).
  The best v6 draft scored `1.036561331974176` on v6b heldout, and v6b
  training improved only to `1.0597349643221203` mean accepted
  (`diagnostics/qwen27-ex0bit-eagle3-v6b-stepfocus-summary-20260707.json`).
  Treat this as diagnostic evidence that data quality helps but is not enough;
  do not repeat small EAGLE corpus/objective sweeps without a different
  architecture/loss/train-scope mechanism.
  See
  `experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-06-ex0bit-eagle3-aux-probe-no-win.md`
  and
  `experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-06-ex0bit-eagle3-target-adaptation-screen.md`.
- Qwen27 current frontier closure:
  `experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-04-frontier-closure-and-next-projects.md`.
  Independent audits found no unclosed non-cheating config/runtime lane and no
  bounded atomic/single-pass/fused-quant LM-head tweak likely to beat dense
  oneDNN by `>10%`. Continue Qwen27 only for a deeper top-ID LM-head producer,
  materially stronger drafter/branch-regenerate architecture, or full
  partial-group source-support project; otherwise switch models.
- External `Qwen/Qwen3.5-0.8B` draft-model probe is closed no-win:
  `experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-06-qwen35-08b-external-draftmodel-zero-acceptance.md`.
  A compatibility patch got explicit `draft_model` serving, text-only Qwen3.5
  M-RoPE, mixed draft KV groups, mixed block sizes, graph capture, and smoke
  passing, but the live k8 run accepted `0` draft tokens and fell to
  `~2.3-2.6 tok/s`. Do not repeat this exact target/draft pairing without a
  separate fresh-prompt acceptance oracle showing nonzero target-verified
  acceptance.
- Alternate `unsloth/Qwen3.6-27B-MTP-GGUF` Q4 llama.cpp/SYCL lane was brought
  up and swept under the same fresh-response policy. It is valid but not
  competitive: best strict row `30.679 tok/s` (`draft-mtp n_max=3`) versus
  `23.567 tok/s` no-spec, with all config-only sweeps below the current
  AutoRound vLLM result. See
  `results/qwen36-27b-mtp-gguf-q4-b70/README.md`.

Previous bookmarked target:

- Gemma 4 26B A4B Q8/INT8-quality on Intel Arc Pro B70.
- Run one Q8 target/verifier replica per GPU where practical, using four GPUs
  for parallel research screens rather than TP4 unless explicitly testing a
  multi-GPU serving shape.
- Best strict realistic-suite one-B70 result is
  `124.97714084813418 tok/s` median generated-token throughput for tokens
  1-100 after TTFT across the fixed cold prompt suite. Evidence:
  `data/gemma4-q8-gpu0-finalpostnorm-reproexact-full512-20260701T084728Z/summary.json`.
  Standalone current repro:
  `repro/gemma4-26b-a4b-q8-b70-125tps-20260701/README.md`.
  It uses llama.cpp `c926ad098`, UD-Q8_K_XL target/verifier, Q4_0 MTP draft,
  reordered-Q8 VDR2, `FLASH_ATTN=on`, `CTX_SIZE=32768`,
  `GGML_SYCL_ENABLE_VMM=1`, `n_max=3`, `n_min=2`, `p_min=0.0475`,
  `UBATCH_SIZE=1024`, `LLAMA_SYCL_F16_P021_SMALL_NCOLS=1`,
  `LLAMA_SPEC_VERIFY_BULK_SAMPLED_IDS=1`,
  `LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM_REORDER_VDR2=1`,
  `LLAMA_GEMMA4_FUSED_FINAL_POST_NORM_RESIDUAL=1`,
  `cached_tokens=0` on every prompt, and
  `realistic_final_gate.passed=true`.
- Latest same-recipe doc-pass rerun:
  `data/gemma4-q8-gpu0-125repro-docpass-20260702T231635Z/summary.json`
  passed the strict gate at `120.92334534956485 tok/s`, with `cached_tokens=0`
  on all 12 prompts and `512/512` canary rows. This supports the promoted
  recipe but does not replace the `124.977` high.
- Representative / submitted status: this is the confirmed strict-gate VDR2
  selected-down fused weighted-sum family, now with FA-on 32K/VMM and final
  post-norm residual fusion. The current high is approved by LocalMaxxing as
  `cmr1u77na01k2ld01kalwzs1e`. Same-family support includes the prior
  `123.67689864739785 tok/s` high (`cmr01nnet000mld01x2tt6qds`), the prior
  `121.41411987308553 tok/s` high (`cmqztiqdn02vnoe01egox6q3f`) and
  `data/gemma4-q8-gpu2-baseline-recordconfirm-full512-20260629T225215Z/summary.json`
  at `119.94842631460949 tok/s`; the prior FA-on 32K/VMM row
  `cmqzq5zu402troe01t774uyox`, selected-down rows `cmqyrpox4021dqk01co5o4fcw`
  and `cmqyo0jyt08ippk01vhiobdnm`, and prior submitted rows
  `98.34046474459183` (`cmqxchyra03xmqr01b963gmi1`),
  `95.82453787677183` (`cmqx3687103v4qr01ace1ft3m`),
  `90.98312252660529` (`cmqwxep4a03qiqr010chjn93s`),
  `90.32179401019857` (`cmqwt1zk803ozqr01hctqss2z`),
  `89.45543282863798` (`cmqwqzayr03o8qr01j6lgx93n`), and
  `87.61145306230438` (`cmqwnl2ag03lgqr01ch5bxknq`) are superseded.
- Current valid no-spec control is `74.29709476830473 tok/s` median on the same
  suite:
  `data/gemma4-q8-gpu0-vdr4default-nospec-realistic-gate-v2-20260627T165335Z/summary.json`.
  This is the clean target-side baseline for continued optimization.
- Latest verifier-top2 diagnostic is closed as an instrumentation failure, not
  a performance result. The v2 patch built and made the host top2 profile path
  non-missing, but raw records stayed at initialized `-1` values (`top1=-1`,
  `top2=-1`, NaN logits) because the added side tensor was not produced by the
  active MTP verifier graph path. Do not draw LM-head margin, candidate-vs-max,
  or row-adaptive conclusions from this diagnostic. The active llama.cpp source
  was restored to the pre-top2 record stack (`cmp_rc=0`) and rebuilt. Evidence:
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260701-verifier-top2-v2-instrumentation-failure.md`.
- Post-restore sanity after removing the v2 top2 hooks and rebuilding passed
  the fixed cold gate at `MAX_TOKENS=64`: `16/16` canary rows,
  `cached_tokens=0`, median `124.03008933114222 tok/s` for tokens 1-50 after
  TTFT. This confirms the active binary is back on the promoted lane, but it is
  a compact sanity check, not a full512 record claim. Evidence:
  `data/gemma4-q8-gpu0-post-top2v2-revert-sanity-20260701T201036Z/summary.json`.
- Latest candidate-proof diagnostic:
  `LLAMA_SPEC_VERIFY_CANDIDATE_PROOF_PROFILE=1` is a host-side profile only,
  not a performance result. A compact cold gate (`MAX_TOKENS=64`) passed
  canary and `cached_tokens=0`, with the final cumulative profile line:
  `steps=452`, `verifier_rows=1802`, `draft_rows=1350`,
  `draft_match_rows=1102` (`81.630%`), `full_draft_matches=277`
  (`61.283%`), `missing_sampled_rows=0`, `nonconsecutive_steps=0`,
  `first_mismatch_counts=(0:72, 1:48, 2:59, 3:273)`. This confirms the
  default full-bonus verifier rows are inspectable and often candidate-matched,
  but a draft-candidate-only shortcut is not exact enough because early
  mismatches still require the true target top token. Use this only to guide a
  deeper exact accept-prefix / verifier graph design. Evidence:
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260701-candidate-proof-profile.md`.
- Latest verifier-lane audit:
  Candidate-bound LM-head proof is not a credible exact shortcut unless it can
  avoid full-vocab Q8 LM-head work; the current design cannot, and exact
  verification still needs the target top token on the first mismatch. The next
  source lane is exact accept-prefix row economics: preserve one target decode
  boundary and the full-match bonus row, but make the existing row-gated backend
  path cheaper than its earlier serialized prototype. Evidence:
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260701-candidate-bound-lmhead-proof-design.md`
  and `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-row-economics-profile.md`.
- Latest accept-prefix top1-epilogue follow-up:
  `LLAMA_SYCL_ACCEPT_PREFIX_TOP1_EPILOGUE=1` plus
  `LLAMA_SPEC_VERIFY_ACCEPT_PREFIX_ARGMAX=1` is closed negative. It kept exact
  target verification and all four A/B lanes passed the fixed cold suite with
  `cached_tokens=0`, but candidates averaged `105.080 tok/s` versus controls
  at `116.498 tok/s` (`-9.80%`). The source was restored exactly to the preedit
  record stack and rebuilt; `libggml-sycl.so.0.15.2` is back to
  `61c364b690ea6f852ad71c77abd65605c33de967dc9186c19d322c28e4ea8864`.
  Do not repeat row-by-row accept-prefix variants; future verifier work needs a
  non-serial backend row-adaptive design or a real candidate-bound certificate.
  Evidence:
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260702-acceptprefix-top1-epilogue-negative.md`.
- Latest direct-confidence / logit-gap follow-up:
  Tail-only MTP direct-confidence producer is closed negative. A source patch
  made `LLAMA_MTP_DRAFT_DIRECT_ARGMAX_SCORES=1` compute top2 score rows only
  at/after `LLAMA_MTP_DRAFT_LOGIT_GAP_MIN_START_POS`, padding earlier ID-only
  rows so the fixed score-mode stride remained intact. The patch built and all
  four strict128 cold-suite lanes passed with `cached_tokens=0`, but the best
  candidate (`tail3-gap0`) reached only `118.4709837563259 tok/s` versus the
  same-window control at `120.49223560283977 tok/s`, and the real gap-filter
  lane (`tail3-gap050`) reached only `117.52940584638576 tok/s`. Do not
  promote, submit, or continue simple draft-confidence filtering as a record
  lane. The patch/result are preserved, and the active source/binary were
  restored to the pre-experiment record stack. Evidence:
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260702-tail-only-direct-confidence-negative.md`.
- Latest post-norm combo MTP follow-up:
  The only bounded follow-up from no-spec calibration was tested in a four-GPU
  same-window MTP full512 run. All lanes passed the fixed realistic gate with
  `cached_tokens=0`, but the combo remained inconclusive and below the current
  record: controls `116.787` / `113.962`, combo-on `117.227` / `115.861`,
  paired 95% CI `-2.754% / +0.395% / +3.346%`. Do not promote or submit.
  Evidence:
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260701-postnormcombo-mtp-followup.md`.
- Latest no-spec target-side calibration batch:
  Paired no-spec A/B closed packed GEGLU all as `no_win`
  (`-1.046% / -0.858% / -0.570%`) and confirmed the LM-head subgroup closure.
  Attention post-norm (`+0.431% / +0.804% / +1.119%`) and the final +
  attention + per-layer post-norm combo (`+0.744% / +1.014% / +1.292%`) are
  small target-side positives but below the `+1%` lower-bound promotion rule.
  The post-norm combo is the only eligible bounded MTP same-window follow-up; do
  not submit or promote no-spec-only results. Evidence:
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260701-nospec-retest-candidates.md`.
- Latest LM-head subgroup calibration:
  `LLAMA_SYCL_Q8_0_LM_HEAD_1COL_SUBGROUPS=2` is closed by the lower-variance
  no-spec calibration workflow. The candidate and controls all passed the fixed
  realistic final gate with `cached_tokens=0`, but paired prompt analysis gave
  a median-ratio 95% CI of `-0.649% / -0.338% / -0.073%`, decision `no_win`.
  Do not retest the LM-head one-column subgroup family, DMMV, or no-reorder
  variants unless a future source change materially alters the kernel shape.
  Evidence:
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260701-lmhead1col-subgroups.md`
  and `data/gemma4-q8-nospec-lmheadsg2-ab-20260701T140828Z.md`.
- Latest service/prefill source win:
  `GGML_SYCL_FATTN_DV512_GQA8_KQ_REG_BCAST=1` is a default-off global
  FlashAttention service flag that now covers both `DKQ=512` and the profiled
  `DKQ=576`, `DV=512`, `ncols=16` Gemma global GQA shape. The DKQ576 extension
  built and passed a balanced four-wave long-context A/B + crossover:
  48/48 exact JSON rows valid, `cached_tokens=0`, prefill `+0.722%` mean /
  `+0.813%` median, TTFT `-0.765%`, positive by GPU and by case. A candidate
  short-decode guard also passed four lanes at `MAX_TOKENS=256`,
  `CANARY_REPEATS=8`, `cached_tokens=0`, with no regression signal. A later
  full512 short-decode A/B isolated the KQ flag on top of
  `GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8`; all eight lanes passed the fixed cold
  gate with `cached_tokens=0`, but paired median-ratio CI was
  `-2.666% / -0.040% / +3.119%`, decision `no_win`. This is service/prefill
  only, not a LocalMaxxing headline decode result; do not add it to the short
  recipe or submit it. Evidence:
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260702-global-fattn-kq-reg-bcast-dkq576-service-win.md`,
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260702-kq-reg-bcast-short-full512-no-win.md`,
  `data/gemma4-global-fattn-kq-reg-bcast-dkq576-comparison-20260702.json`, and
  `data/gemma4-kqregbcast-short-full512-ab-20260702T112211Z-kqregbcast-short-full512-ab.json`.
- Latest hot global FlashAttention scheduler follow-up:
  `GGML_SYCL_FATTN_DV512_GQA8_GLOBAL_PB1=1` is closed no-win. A default-off
  source patch forced `parallel_blocks=1` only for the profiled global GQA8
  service shape and excluded SWA/decode paths. It built and passed a one-case
  exact JSON smoke, then a four-wave service A/B + crossover on top of the KQ
  register/broadcast service stack. All 48 rows were exact-valid with
  `cached_tokens=0`, but prefill moved only `+0.102%` mean / `+0.260%`
  median, below the service threshold. The patch was reverted exactly and the
  active binary rebuilt to the baseline `libggml-sycl.so.0.15.2` hash
  `61c364b690ea6f852ad71c77abd65605c33de967dc9186c19d322c28e4ea8864`. Do not
  repeat broad or narrow one-pass `parallel_blocks=1` retunes unless the tile
  implementation changes materially. Evidence:
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260702-hotglobalpb1-service-no-win.md`
  and
  `data/gemma4-global-fattn-hotglobalpb1-comparison-20260702Thotglobalpb1-service-ab1.json`.
- Latest current-service context ladder:
  the current service stack (`GQA_NCOLS2=8`, SWA left-bound min-Q `2048`, KQ
  register/broadcast, phase prefill ubatch `2048`, `BATCH_SIZE=2048`,
  `UBATCH_SIZE=1024`, 32K context, FA/VMM on) was validated across all four
  B70s on all long-context suite cases from 512 through 24K target prompt
  tokens. All 32 long-context rows were exact-valid with `cached_tokens=0`, and
  all 64 canary rows passed. Average lane median prefill was `1192.965 tok/s`;
  average lane median long-context decode was `131.786 tok/s`. This is the
  service/prompt-processing baseline, not a short-decode LocalMaxxing headline.
  Evidence:
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260702-current-service-context-ladder.md`
  and
  `data/gemma4-long-context-service-gate-20260702Tservice-ladder-current-rep4.json`.
- Latest Q-global FlashAttention staging follow-up:
  `GGML_SYCL_FATTN_DV512_GQA8_KQ_REG_BCAST_QGLOBAL=1` is closed negative. The
  patch built and passed an exact one-case long-context smoke with
  `cached_tokens=0`, but same-binary same-case control showed Q-global was
  slower: prefill `1188.722` vs `1232.948 tok/s` (`-3.59%`), decode `123.438`
  vs `128.226 tok/s` (`-3.73%`), and TTFT `+3.72%`. The source was restored to
  the known record-stack hash
  `7220e022ae836b2a885f6e1ba5d73422f1ddd9c74e0c3e4582a0d7066fa295e3`, and
  `libggml-sycl.so.0.15.2` was rebuilt to baseline hash
  `61c364b690ea6f852ad71c77abd65605c33de967dc9186c19d322c28e4ea8864`.
  Do not retest direct global-Q reload for this hot service shape. Evidence:
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260702-qglobal-qstaging-negative.md`.
- Latest sampled-ID egress follow-up:
  `LLAMA_SPEC_VERIFY_DIRECT_SAMPLED_EGRESS=1` is a closed negative /
  incomplete implementation. The first parity smoke passed only because the
  parity check ignored `LLAMA_TOKEN_NULL`; the stricter diagnostic showed
  direct sampled IDs stayed `-1` while copied sampled IDs were valid, and
  `LLAMA_SPEC_VERIFY_DIRECT_SAMPLED_EGRESS_SKIP_COPY=1` crashed the sampler
  because logits are not exported in backend-argmax mode. Backend-copy and
  pre-allocation `op_params` variants rebuilt and passed canaries, but still
  failed strict parity (`356` and `355` mismatches respectively: direct `-1`,
  copied token valid). The failed source hooks were removed from the active
  llama.cpp checkout, rebuilt, and sanity-checked with a compact cold gate
  (`32/32` canary, `cached_tokens=0`, median tokens 1-50 `120.302963`). Do not
  enable skip-copy, and do not keep retesting pointer-only `op_params` variants
  without a producer-side graph/output design. Any future version must patch the
  actual sampled-row producer and prove null-sensitive direct-vs-copied parity
  first. Evidence:
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260701-direct-sampled-egress-negative.md`.
- Latest prompt-processing source follow-up: DV512 Gemma GQA `ncols2=16` is a
  closed negative. The candidate branch rebuilt, but both candidate lanes failed
  the first JSON canary with empty text before long-context cases could run.
  Keep `GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8` for the validated service/prefill
  lane. The active llama.cpp source was restored to the preedit record stack and
  rebuilt; `llama-server --version` reports `c926ad098`, and the failed branch
  is absent. Evidence:
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260701-fattn-dv512-gqa-ncols16-negative.md`.
- Latest full512 follow-up: fused selected-softmax into selected-down VDR2
  (`LLAMA_GEMMA4_MOE_FUSED_DOWN_SELECTED_SOFTMAX=1`) and the EOG-clip
  interaction were valid but lost. Best candidate was `111.90908727268967
  tok/s` with EOG clip, below controls and below the `124.97714084813418` record.
  Do not submit or retest this interaction as a record lane. Evidence:
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260629-fused-selected-softmax-full512-negative.md`.
- Latest strict128 source follow-up: adaptive bonus-row skipping is a closed
  negative. It preserved exact verification and passed the realistic cold gate,
  but the best adaptive lane reached only `109.5558044655227 tok/s` versus the
  same-build control at `112.02098406811635 tok/s`, with worse p10 and
  full-output speed. Do not full512-confirm or submit it. Evidence:
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260629-adaptive-bonus-row-negative.md`.
- Latest verifier-copy follow-up: deferred verifier pending-`h` copy
  (`LLAMA_MTP_DEFER_VERIFIER_PENDING_H_COPY=1`) is also a closed negative. A
  first paired screen had one attractive flag-on outlier (`118.10959835079939
  tok/s`), but the cross-over disproved it: control medians averaged
  `114.45317635681107`, flag-on medians averaged `112.421810001393`, with all
  lanes valid and `cached_tokens=0`. Do not full512-confirm or submit it.
  Evidence:
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260629-defer-verifier-pending-h-copy-negative.md`.
- Latest verifier-design audit: exact LM-head candidate-vs-max has usable row
  plumbing in the narrow full-output MTP verifier shape, but it is not a
  current record lane. Exact speculative verification still needs the true
  target top token on mismatch, so the full-vocab max/challenger work remains.
  A follow-up row-semantics audit confirmed no small exact accept-prefix patch
  remains: the current accept-prefix backend is already the simple serial
  row-gated design and it lost. Future verifier work needs a non-serial backend
  row-adaptive LM-head path or a real candidate-bound certificate that avoids
  full-vocab work; do not repeat post-hoc masks, conditional/no-bonus variants,
  or row-by-row accept-prefix variants. Evidence:
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260702-verifier-row-adaptive-readonly-audit.md`,
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260629-candidate-threshold-lmhead-no-go.md`.
- Latest selected-down rowpack follow-up: `ROWPACK=2` for the VDR2
  selected-down weighted-sum path is valid but rejected for the short-record
  metric. The strict128 screen looked mildly positive, but the full512
  cross-over lost primary tokens 1-100 versus controls while improving only
  full-output / wall throughput. Keep it as a possible service-lane idea, not
  a headline record path. Evidence:
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-vdr2-selecteddown-rowpack2-negative.md`.
- Latest profile refresh: the rebuilt baseline/profile run
  `gemma4-q8-gpu0-record-refresh-specprofile-strict128-20260630T002301Z`
  passed the fixed cold gate and `cached_tokens=0`, but is diagnostic only
  because profiling and `MAX_TOKENS=128` were enabled. It confirms the record
  identity is target/verifier-bound: target decode `38529.540 ms` versus draft
  `2665.342 ms`; target `process_ubatch_ms=36833.360`; sampled-ID extraction
  `1665.262 ms` is a backend read/sync boundary, not an integer-copy loop.
  Host sampler/accept bookkeeping remains negligible. Evidence:
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-record-refresh-specprofile.md`.
  Follow-up `LLAMA_SPEC_VERIFY_SYNC_PROFILE=1` timing showed the later
  accept-side `llama_synchronize(ctx)` is only `1.734 ms` total over `896`
  verifier calls (`0.002 ms/call`), so do not chase sampler-side sync cleanup
  as a record lever. The remaining credible target is real verifier graph cost
  or the backend sampled-output extraction boundary itself. Follow-up
  `LLAMA_SPEC_VERIFY_ROW_ECON_PROFILE=1` measured the default full-bonus
  verifier row economics on the same record identity:
  `steps=921`, `rows_current=3679`, `rows_oracle=2893`,
  `rows_saved=786` (`21.365%` oracle row-output saving), and
  `full_match_with_bonus=541` (`58.7%` of steps). Evidence:
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-row-economics-profile.md`.
  This supports a bonus-preserving row-output design only; simple no-bonus,
  adaptive bonus skip, staged MTP3, late-head, and prefix-tail variants remain
  closed negatives.
- Latest config follow-up: final-record FA-on 32K/VMM UBATCH screen tested
  `UBATCH_SIZE=768`, `896`, `1024` control, and `1152`. The strict128 pass made
  `BATCH_SIZE=1152`, `UBATCH_SIZE=1152` look promotion-worthy
  (`121.24708378127268 tok/s`), but the paired full512 confirmation closed it:
  all lanes stayed valid, candidate average was `117.36308529017367 tok/s`
  versus paired-control average `114.3071667009025`, and the best candidate was
  `118.43353215490006`, still below the `124.97714084813418` headline. Do not
  change the recipe or submit it. Evidence:
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-faon-vmm-ubatch-screen.md`.
  Treat `UBATCH_SIZE=768`, `896`, and `1152` as closed for the short-record
  lane unless a future source patch changes the memory/workgroup tradeoff.
- Latest verifier-shape audit: the apparent one-column Q8 LM-head profile
  detail is not enough evidence for a row-coalescing patch. A verbose
  `LLAMA_BATCH_DEBUG=1` diagnostic showed the standard MTP verifier path already
  forms full-bonus microbatches with `n_tokens=4`, `n_outputs=4`; the SYCL node
  profiler preserves the first detail for a node name, which can be a one-output
  prompt/decode graph. Two read-only audits agreed the only remaining exact
  row-output reduction is a deeper accept-prefix verifier LM-head backend op:
  compute row 0 target top-1, compare to draft on-device, then compute later
  verifier/bonus rows only if prior rows matched. Expected upside is modest and
  implementation risk is high. Evidence:
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-verifier-row-shape-and-accept-prefix-audit.md`.
  Do not reopen row-shape/config screens without new profile evidence.
- Latest node-profile refresh:
  `gemma4-q8-gpu0-recordstack-profile128-20260702T113037Z` passed the fixed
  cold gate (`cached_tokens=0`, `16/16` canary rows), but is diagnostic only
  because `GGML_SYCL_NODE_PROFILE=1` disables SYCL graph execution and the run
  used `MAX_TOKENS=128`. Do not submit or compare its `76.928 tok/s` median to
  record rows. The useful hotspot order is target/verifier LM-head
  (`MUL_MAT:node_1715`, `817.753 ms`), MoE gate-up, and three separate MTP
  draft argmax LM-head nodes (`mtp_direct_argmax_unroll_token_0/1/2`,
  about `239-240 ms` each, `q6_K` draft output weights). Host sync/bookkeeping
  is negligible. Follow-up source audit found the backend already supports
  multi-column `MUL_MAT_ARGMAX`, but these draft heads are autoregressive and
  cannot be naively batched because each sampled token feeds the next draft
  step. Future draft work needs a new single-node `q6_K` argmax kernel design or
  a different draft algorithm; verifier LM-head work should only be reopened
  for exact, non-serial row-adaptive or candidate-bound designs. A full512
  current-record A/B of `LLAMA_SYCL_MUL_MAT_ARGMAX_TILE_SUBGROUPS=16` on this
  draft path is also closed no-win: all 8 lanes passed with `cached_tokens=0`,
  but paired median-ratio CI was `-2.594% / +0.001% / +4.021%`.
  Evidence:
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260702-recordstack-nodeprofile-hotspots.md`
  and
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260702-argmaxtile16-draft-q6k-no-win.md`.
- Latest p_min gap follow-up: `0.04625`, `0.04725`, `0.047625`, and `0.04875`
  were tested under the current FA-on 32K/VMM selected-down VDR2 strict128
  identity. All passed, but best was only `118.41776692242152 tok/s`, below
  matching-stack `0.0475` controls at `119.79709987498046` and
  `119.51944277144372`. This is a closed negative; do not full512-confirm or
  submit. Evidence:
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-faon-vmm-pmin-gap-screen-negative.md`.
- Latest full512 record-repeat: four lanes of the current promoted FA-on
  32K/VMM selected-down VDR2 recipe all passed the strict cold final gate,
  `cached_tokens=0`, and 128/128 canary, but no lane beat the
  `121.41411987308553 tok/s` record. Medians were `118.21311630972258`,
  `117.71732552906994`, `114.87763475869593`, and
  `112.94544241316387 tok/s`. Closed as variance/no-new-record; do not submit.
  Evidence:
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-record-repeat-full512-variance.md`.
- Latest source follow-up / current record: final post-FFN RMS norm + residual
  fusion (`LLAMA_GEMMA4_FUSED_FINAL_POST_NORM_RESIDUAL=1`) was retested on the
  same FA-on 32K/VMM selected-down VDR2 identity. It passed strict128,
  cross-over, and full512 validity. The best full512 lane reached
  `123.67689864739785 tok/s`, with p10 `105.67252530778094`, mean
  `120.82536080117124`, full512 after-TTFT `110.68310696601407`, wall full512
  `106.44076646173642`, and LocalMaxxing `cmr01nnet000mld01x2tt6qds`.
  Paired full512 averages were positive but noisy (`120.11414175477651` vs
  controls `116.29133772533568`), so repeat confirmations remain useful before
  inferring a stable effect size. Evidence:
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-final-postnorm-fusion-screen.md`.
- Latest exact reproduction / current record: after the LM-head/Q8 one-column
  subgroup experiment, the exact full512 promoted recipe was rerun across all
  four GPUs with `CANARY_REPEATS=128` (`512/512` canary rows), LM-head subgroup
  unset, fixed realistic suite, and `cached_tokens=0`. GPU0 reproduced and
  exceeded the previous high at `124.97714084813418 tok/s`, p10
  `103.83610041293263`, mean `122.47435471668817`, full512 after-TTFT
  `114.87107033590866`, wall full512 `108.58112847853889`, TTFT
  `178.6938319564797 ms`. LocalMaxxing approved it as
  `cmr1u77na01k2ld01kalwzs1e`. Same exact batch support rows were `121.591`,
  `119.264`, and `113.633`, confirming the lane is valid but high-variance.
  Evidence:
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260701-finalpostnorm-reproduction-check.md`.
- Latest thermal / fairness check: the exact promoted final-postnorm recipe was
  rerun four times sequentially on GPU0 with privileged `xpu-smi dump`
  telemetry. All four repeats passed the fixed cold gate, `cached_tokens=0`,
  and 512/512 canary; medians were `115.515`, `119.019`, `114.520`, and
  `120.202 tok/s`. Active core max stayed `77-78 C`, memory max `86-90 C`,
  frequency stayed near max, and no thermal-throttle samples appeared. Current
  variance is therefore not explained by simple temperature throttling in this
  band. Future close A/B and record-repeat work should capture telemetry and
  avoid comparing hot/cold historical outliers without same-window controls.
  Evidence:
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260701-finalpostnorm-thermal-variance.md`.
- Latest reliability-method update: use
  `scripts/analyze-gemma-realistic-ab.py` and
  `results/gemma4-26b-a4b-q8-b70/reliability-protocol.md` for micro-change
  decisions. The thermal repeatability set measured `2.324%` run-median CV and
  `4.409%` p90 pairwise absolute run-median delta. A fake A/B split of the
  same exact recipe produced higher "candidate" raw medians but only
  `-1.186% / +3.057% / +7.067%` median paired-ratio CI, so it is correctly
  `inconclusive_positive`. Do not promote `+1-4%` one-off changes without a
  paired bootstrap lower bound above `+1.0%` and clean quality/telemetry.
- Latest repeat / variance check: four more full512 lanes of the promoted
  final-postnorm recipe all passed the strict cold gate, `cached_tokens=0`, and
  512/512 canary, but no lane beat the record. Medians were
  `118.78941183022032`, `115.48824790393866`, `112.71902407241845`, and
  `116.80124865921995 tok/s`. Closed as valid variance/no-new-record; do not
  submit. Evidence:
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-finalpost-repeat2-full512-variance.md`.
- Latest source follow-up / closed negative: attention post-norm residual
  fusion (`LLAMA_GEMMA4_FUSED_ATTN_POST_NORM_RESIDUAL=1`) was implemented as a
  default-off Gemma source patch after snapshotting the source. The harness was
  updated to pass and record the flag. Verified strict128 A/B passed the cold
  gate and 512/512 canary on every lane, but lost the primary short metric:
  controls averaged `119.3616057307415 tok/s`, flag-on averaged
  `116.75359048324216 tok/s`. It improved full-output medians, so keep only as
  a possible service/full-output lane. Do not full512-confirm or submit for the
  short record. Evidence:
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-attn-postnorm-residual-fusion-negative.md`.
- Latest source follow-up / inconclusive small result: per-layer embedding
  post-norm residual fusion
  (`LLAMA_GEMMA4_FUSED_PER_LAYER_POST_NORM_RESIDUAL=1`) was tested as the
  next sibling of the final-postnorm win. The source was snapshotted before and
  after, and harness metadata now passes/records the flag. Four strict128 lanes
  all passed the cold gate, `cached_tokens=0`, and 512/512 canary. Controls
  averaged `115.80942063480597 tok/s`; flag-on lanes averaged
  `116.81238861292647 tok/s`; best flag-on was `119.96280008214512 tok/s`,
  still below the `124.97714084813418` record. Treat as small/inconclusive,
  keep default-off, and do not submit or full512-confirm for the short record.
  Evidence:
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-perlayer-postnorm-residual-fusion-inconclusive.md`.
- Latest verifier-design follow-up / diagnostic proof: accept-prefix parity was
  implemented as a default-off fail-fast check under
  `LLAMA_SPEC_VERIFY_ACCEPT_PREFIX_PARITY=1`. It reconstructs the accepted
  token vector from backend sampled verifier rows and compares it to the
  existing sampler accept path on the standard full-bonus MTP verifier shape.
  The initial `n_draft == 3` guard was too narrow and rejected valid short-tail
  steps; the rebuilt helper accepts any full-bonus tail with `n_draft > 0`,
  consecutive verifier rows, and `spec_i_batch.size() == n_draft + 1`. The
  validated full512 diagnostic passed the fixed cold gate, `cached_tokens=0`,
  and 128/128 canary at `117.60357286123875 tok/s`, below the active record.
  This proves the sampled-row invariant needed for a future backend
  accept-prefix verifier LM-head op, but it does not reduce work and is not a
  LocalMaxxing candidate. Evidence:
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-accept-prefix-parity-probe.md`.
- Current context/service diagnostic split: the short-record recipe is now
  also the FA-on 32K/VMM service profile after a realistic-gate retest. The
  promoted row is `123.67689864739785 tok/s` with `FLASH_ATTN=on`,
  `CTX_SIZE=32768`, and `GGML_SYCL_ENABLE_VMM=1`; LocalMaxxing
  `cmr01nnet000mld01x2tt6qds`. For medium-long service, MTP with FA off
  remains useful through about `ctx24576` / `ctx25600`, degrades around
  `ctx26624`, and cliffs by `ctx27648`. For true
  `ctx32768`, enable `FLASH_ATTN=on`: the same MTP stack reached
  `~102.7-103.2 tok/s` after TTFT at `27648`, `28672`, and `32768` on the
  synthetic ~11K-token diagnostic, with `cached_tokens=0`. These are not
  LocalMaxxing headline records. Evidence:
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260629-context-threshold-mtp-vs-nospec.md`.
  New 2026-06-30 service baseline: the FA-on 32K/VMM record recipe was run as
  a prefill ladder with unique prompts, `BATCH_SIZE=1024`, `UBATCH_SIZE=1024`,
  16 generated tokens, `cached_tokens=0`, and canary pass on all rows. Summary:
  `~1.09K-1.11K tok/s` approximate prefill at 2.9K-5.6K actual prompt tokens,
  `~1.07K tok/s` at 8.1K, then `955.9`, `887.7`, and `794.2 tok/s` at 12.1K,
  16.2K, and 21.5K actual tokens. Evidence:
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-prefill-ladder-baseline.md`.
  Next service tests may screen larger batch/ubatch on representative long
  prompts, but must keep this separate from the short-decode record and rerun
  the short fixed suite before any recipe promotion.
  Follow-up service UBATCH screen:
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-prefill-ubatch-service-screen.md`.
  `BATCH_SIZE=2048`, `UBATCH_SIZE=2048` is the best general long-prefill
  candidate so far (`+10.8%`, `+9.2%`, `+7.4%`, `+6.1%` approximate prefill
  over UB1024 at 8.1K, 12.1K, 16.2K, and 21.5K actual tokens). UB2560 is a
  possible very-long-prompt follow-up; UB3072 fit but regressed. Follow-up
  fixed realistic cold-suite control is complete:
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-ub2048-short-suite-control.md`.
  UB2048 passed with `cached_tokens=0` and averaged
  `118.30159066915866 tok/s` versus UB1024 controls at
  `116.46794311469674 tok/s`, but the best candidate
  (`118.70031578164084 tok/s`) did not beat the active
  `124.97714084813418 tok/s` record. Keep UB1024 for headline reproduction;
  UB2048 is validated as the best general service/default candidate so far.
  Repeat UB2048-vs-UB2560 long-prefill confirmation is also complete:
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-prefill-ub2048-vs-ub2560-confirm.md`.
  UB2048 wins the 12K-requested shape and is an effective prefill tie at the
  16K-requested / ~21K actual-token shape while decoding faster; do not
  standardize on UB2560.
- Latest long-context service gate: a fixed JSON-retrieval suite and paired
  service/short guards were added under
  `repro/gemma4-26b-a4b-q8-b70/long-context-suite-v1.json`,
  `scripts/bench-openai-long-context-suite.py`,
  `repro/gemma4-26b-a4b-q8-b70/run-vdr2-long-context-service-gate.sh`, and
  `repro/gemma4-26b-a4b-q8-b70/run-vdr2-short-decode-guard.sh`. UB2048 passed
  exact long-context retrieval, `cached_tokens=0`, and canaries through
  `22730` actual prompt tokens with `+8.22%` median approximate prefill over
  UB1024 (`1013.884` vs `936.865 tok/s`), and passed the corrected near-32K
  boundary case at `30400` actual prompt tokens with `+5.98%` prefill
  (`701.487` vs `661.905 tok/s`). A paired full512 fixed short-suite guard
  passed on all lanes and did not show a decode regression (`119.153` UB2048
  average vs `116.402` UB1024), but did not beat the short record. Decision:
  UB2048 is the validated long-context/prefill service candidate; keep UB1024
  for short-record reproduction. Follow-up heavy-context UB1792/2048/2304/2560
  cross-over screens at `16213`, `22730`, and `30400` actual prompt tokens
  found UB2560 fastest for narrow near-32K prefill (`718.968` tok/s at 30400
  vs UB2048 `710.342`), but UB2560 and UB2304 both lost short-suite speed in
  their guards, so they are diagnostics only. A profiled UB2048 near-32K run
  showed prompt processing is dominated by `FLASH_ATTN_EXT` / KV-cache
  attention work; do not reopen generic UBATCH roulette without new evidence.
  The failed `MAX_TOKENS=64` near-32K attempt is archived as a harness
  truncation, not a model/context failure. Evidence:
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-long-context-prefill-service-gate.md`.
- Latest source service follow-up: a default-off SYCL FlashAttention tile
  selector patch for Gemma full-attention `DV=512` / GQA8 layers adds
  `GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8`. It is the first large validated
  prompt-processing win after the UBATCH/profile work. Same-build GPU
  crossover on the cold `30400` actual-token JSON retrieval case improved mean
  prefill from `702.605` to `947.589 tok/s` (`+34.87%`) with identical output
  hash, exact validation, and `cached_tokens=0`. A broader gate over `16213`,
  `22730`, and `30400` actual prompt tokens passed on all lanes; median prefill
  was `1039.603 tok/s` for UB2048, `1075.983` for UB2304, and `1066.029` for
  UB2560. Fixed cold short-suite guards passed but did not beat the active
  `124.97714084813418 tok/s` short record, so do not submit it to
  LocalMaxxing. Keep UB1024 for short-record reproduction; use the patch with
  UB2048 as the balanced long-service recipe and UB2304 only for pure prefill.
  Patch:
  `patches/gemma4-26b-a4b-q8-b70/20260630-sycl-fattn-dv512-gqa8-ncols2.patch`.
  Evidence:
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-sycl-fattn-dv512-gqa8-prefill-win.md`.
- Latest source service negative: the KV-max mask pre-scan threshold patch is
  a useful diagnostic knob but not a win. With the GQA8 tile patch active,
  disabling the scan via `GGML_SYCL_FATTN_KV_MAX_SCAN_MIN_Q=-1` passed exact
  cold long-context validation and `cached_tokens=0`, but regressed the
  `30400` actual-token case from `955.2365` to `862.9161 tok/s`. Keep the scan
  enabled. Patch:
  `patches/gemma4-26b-a4b-q8-b70/20260630-sycl-fattn-kv-max-scan-threshold.patch`.
  Evidence:
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-sycl-fattn-kv-max-scan-threshold-negative.md`.
- Latest source service negative: forcing the remaining GQA8 tile `ncols1`
  value is slower than the current selector. With
  `GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8` active, paired controls at the implicit
  `ncols1=2` path measured `953.0630` and `950.5813` prefill tok/s on the
  cold `30400` actual-token case; forced `ncols1=1` measured `821.6392`, and
  forced `ncols1=4` measured `856.8965`. All lanes passed exact validation,
  canary, `cached_tokens=0`, and identical output hash. Keep implicit
  `ncols1=2`; do not use `GGML_SYCL_FATTN_DV512_GQA8_NCOLS1` in promoted
  recipes. Patch:
  `patches/gemma4-26b-a4b-q8-b70/20260630-sycl-fattn-dv512-gqa8-ncols1-negative.patch`.
  Evidence:
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-sycl-fattn-dv512-gqa8-ncols1-negative.md`.
- Latest source service negative: retuning the selected GQA8 FP16 tile from
  `nbatch_fa=64` to `128` is noise, not a win. With
  `GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8` active, four valid cold lanes on the
  `30400` actual-token case averaged `951.5273 tok/s` prefill with per-lane
  results `953.3767`, `944.6846`, `955.1166`, and `952.9311`, matching recent
  controls (`950.5813-955.2365`). Keep
  `GGML_SYCL_FATTN_TILE_CONFIG_CASE(576, 512, 16, 256, 2, 64, 64)`. Patch:
  `patches/gemma4-26b-a4b-q8-b70/20260630-sycl-fattn-dv512-gqa8-nbatchfa128-negative.patch`.
  Evidence:
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-sycl-fattn-dv512-gqa8-nbatchfa128-negative.md`.
- Latest source service follow-up: phase-specific prompt/decode ubatch is a
  valid service candidate, not a new short-record lane. v1 context-only
  `LLAMA_PREFILL_UBATCH_SIZE=2048` with `BATCH_SIZE=2048`,
  `UBATCH_SIZE=1024` passed validation but hit repeated KV retry fallback and
  fell to `880.2510 tok/s` prefill. v2 additionally sizes SWA/ISWA attention
  memory with `max(n_ubatch, n_ubatch_prefill)`, removed retries, and measured
  `956.7217 tok/s` long-prefill, `112.9063 tok/s` long-context decode, and
  `120.8849 tok/s` on the short fixed guard for `2048/1024 + prefill2048`.
  It does not beat the `124.97714084813418 tok/s` short record, so do not
  submit it. `prefill2304` and `prefill2560` were valid but not better
  balanced. Patches:
  `patches/gemma4-26b-a4b-q8-b70/20260630-llama-phase-prefill-ubatch-experiment.patch`
  and
  `patches/gemma4-26b-a4b-q8-b70/20260630-llama-phase-prefill-ubatch-memory-sized-experiment.patch`.
  Evidence:
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-phase-prefill-ubatch-service.md`.
- Current best non-duplicate Gemma code target is still verifier cost, but not
  by removing the bonus pipeline or by a naive candidate-threshold head scan.
  Work inside the existing target decode boundary only if it removes real
  verifier rows/full-vocab dot work or reduces the verifier MoE/kernel
  boundary. Bonus-preserving row-output designs remain interesting, but need a
  concrete exactness and cost argument before GPU time. See
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260629-verifier-next-target-audit.md`.
- Current synthetic diagnostic one-B70 best is `176.21623213048554 tok/s` after
  TTFT on row0 with `cached_tokens=0`, `1536` canary repeats / `6144` rows
  passed, LocalMaxxing `cmqwkedg303jeqr013z753j62`. Under the stricter
  2026-06-27 policy, this is diagnostic only. Its VDR2 setting does not
  transfer to the fixed cold suite and must not be submitted or advertised as
  real-world throughput.
- Start from `results/gemma4-26b-a4b-q8-b70/README.md`,
  `results/gemma4-26b-a4b-q8-b70/reproduce.md`, and
  `results/gemma4-26b-a4b-q8-b70/validity-gates.md`.
- Headline throughput must pass the fixed realistic final gate: each prompt
  once as a cold first response, `cached_tokens=0` every row, no prompt/KV
  cache reuse, no context checkpoints, no response reuse, no n-gram/history
  acceleration, and primary metric = median generated-token throughput for
  tokens 1-100 after TTFT across the suite. Do not use warmed n-gram/history
  rows, repeated-output continuation learning, prefix/cache reuse, context
  checkpoints, or any prior generated continuation as a record claim.
- Post-100 status: the reliable `>100 tok/s` barrier is broken. Do not spend
  more time on configuration-only repeats for this Gemma lane. The
  accept-prefix parity check has validated the sampled-row invariant; the next
  plausible short-decode record attempt is the real backend accept-prefix
  verifier LM-head op or a profile-backed verifier/MoE boundary reduction beyond
  selected-down fusion. If not implementing that, move to a separate
  prefill/long-context service lane and rerun the short fixed suite afterward to
  prove no regression.

Historical / service targets:

- MiniMax M2.7 INT4 AutoRound on 4x Intel Arc Pro B70 32GB.
- Preserve answer quality while improving single-session decode, context,
  prefill, and eventually concurrent-session throughput.
- Do not use power-limit or overclocking changes as optimization paths.

Secondary targets:

- Qwen3.6 27B Q4_0 GGUF and FP8 on B70.
- MiniMax M2.7 GGUF remains useful as a capacity/quality comparison but is not
  the current speed path.

## Current Promoted MiniMax State

Current validated structured-output fast lane:

- Model: `Lasimeri/MiniMax-M2.7-int4-AutoRound`
- Hardware: 4x Intel Arc Pro B70 32GB
- Engine: local vLLM/XPU `0.20.1-local`, TP4
- Backend stack: Level Zero/XPU, llm-scaler INT4 MoE kernels, forced XPU graph
  with communicator capture no-op
- Task: constrained simple HTML, `skeleton_status_html`
- Result: `94.406 tok/s` effective accepted output, `94.692 tok/s` post-first
- Quality gate: `30/30` accepted, `0` rejects, `100%` first-attempt pass
- LocalMaxxing: `cmphg048s00mppc0192sahyug`
- Note: `notes/2026-05-22-minimax-structured-fast-lane-regex2.md`
- Payload: `data/localmaxxing-minimax-m27-autoround-structured-regex2-20260522.payload.json`

Important caveat:

- This is a constrained structured-output lane. It does not prove unconstrained
  free-form website generation is clean on the forced XPU graph path.
- Structured JSON cross-check passed `9/9` with `0` rejects at `87.956 tok/s`
  and stable parsed JSON hashes.

Current older strict long-run MiniMax baseline:

- p512/n1536, ctx2048, batch 1
- Result: `89.314195 tok/s` output, `119.085594 tok/s` total
- LocalMaxxing: `cmpct6t4m007fnw01yjdtlcs4`
- Repro folder: `repro/minimax-m27-b70-89tps-20260520/`

Current fresh Ubuntu 24 deployment repro:

- Date: 2026-05-23
- Purpose: reproduce the deployable OpenAI-compatible vLLM endpoint on a mostly
  fresh Ubuntu 24.04 host with 4x B70s.
- Model: `/mnt/fast-ai/llm-models/minimax-m2.7-int4-autoround`
- Endpoint: vLLM OpenAI-compatible server on `0.0.0.0:8000`
- Served context default: `32768` via `/home/steve/bin/minimax-vllm-serve` and
  `repro/minimax-m27-b70-110tps-ubuntu24-20260523/scripts/06-serve-openai-compatible.sh`
- Context used for the comparable smoke/quality lane: `2048`
- Quality gate: passed raw token-hash canaries, semantic suite, arithmetic
  repeat, and extended sixpack.
- Benchmark: `110.896 total tok/s`, `83.172 output tok/s` for p512/n1536.
- OpenAI endpoint context validation: `24576` started with
  `gpu_memory_utilization=0.95`, vLLM reported `25,344` GPU KV-cache tokens,
  prompt 24,400 / output 64 completed without OOM, and short decode remained
  `83.78-83.79 output tok/s` before/after the long-context request.
- After moving display to ASPEED VGA and booting with `xe.disable_display=1`,
  `32768` started successfully, vLLM reported `33,792` GPU KV-cache tokens,
  prompt `32408` / output `64` completed without OOM, and warm short decode was
  `84.12 output tok/s`. `33792` was tried but did not expose `/v1/models`
  within the wait window and is not promoted. Detailed note:
  `notes/2026-05-23-b70-display-disable-32768-context.md`. LocalMaxxing:
  `cmpj1fmvv001hqr01oj4hiu3d` (`APPROVED`).
- PCIe/prefill follow-up on 2026-05-23:
  `notes/2026-05-23-current-host-pcie4-prefill-check.md`.
  Current host upstream links are PCIe4 x16 (`16.0 GT/s`, width 16) while the
  cards advertise PCIe5 capability. XCCL broad allreduce measured `13.79 GB/s`
  at 256 MiB versus the older `27.88 GB/s` reference, making PCIe4 fabric
  bandwidth a credible explanation for most of the `89 -> 83` strict decode
  delta: `13.79 / 27.88 = 0.494`, roughly half the older bandwidth, while
  `83.8 / 89.314 = 0.938`, about a 6% end-to-end decode drop. Live endpoint
  prefill measured about `1.7k-1.8k tok/s` with `max_tokens=1` prompt-heavy
  requests. Keep warm and cold numbers separate; the older repro had a
  `69.33` output tok/s first post-reboot pass and `88.72` output tok/s warm
  rerun.
- Repro folder:
  `repro/minimax-m27-b70-110tps-ubuntu24-20260523/`
- Human deployment guide: `docs/b70-minimax-ubuntu24-deployment.md`
- Docs index: `docs/README.md`
- Model/community recipe index: `docs/model-recipes.md`
- Community results/build notes: `docs/community-results.md`
- Intel feedback: `docs/intel-b70-minimax-feedback-20260523.md`
- Lessons learned:
  `repro/minimax-m27-b70-110tps-ubuntu24-20260523/notes/learnings-20260523.md`

This fresh deployment is not the fastest output-token lane known in the repo.
Treat it as the current best documented "install from a fresh system and serve
on the LAN" baseline.

Current session-cache / long-context research state:

- Production c1 service docs:
  `docs/minimax-production-c1-service.md`
- Systemd unit source:
  `deploy/systemd/minimax-vllm.service` for the localhost backend and
  `deploy/systemd/minimax-openai-frontdoor.service` for the no-auth LAN
  OpenAI-compatible frontdoor.
- Service installer:
  `scripts/install-minimax-vllm-service.sh`
- LAN frontdoor:
  `scripts/openai-lan-frontdoor.py`; public URL remains
  `http://<server-lan-ip>:8000/v1`, backend is `http://127.0.0.1:18080`,
  and auth is intentionally `none`.
- Production health and benchmark helpers:
  `scripts/minimax-prod-health.py`,
  `scripts/minimax-prod-benchmark.py`
- Current service-managed c1 LocalMaxxing result:
  `cmpm35jsa0003rt01zghtmwip`, prompt `32264`, output `64`, `63.91`
  output tok/s after TTFT, approximate prefill `1382.57` tok/s, TTFT
  `23.336 s`.
- Research folder: `experiments/minimax_xpu_kv_offload/`
- Start with: `experiments/minimax_xpu_kv_offload/REPRODUCE.md`
- Artifact index: `experiments/minimax_xpu_kv_offload/ARTIFACTS.md`
- Operations note:
  `experiments/minimax_xpu_kv_offload/notes-20260525-session-cache-operations.md`
- Profile switcher:
  `experiments/minimax_xpu_kv_offload/scripts/switch_session_cache_profile.sh`
- Status helper:
  `experiments/minimax_xpu_kv_offload/scripts/session_cache_status.sh`
- c1 remains production: `32768`, `max_num_seqs=1`, no CPU KV offload.
- c2 is the current known-good RAM-backed session-cache profile for two parked
  `32768`-token window sessions. The near-full strict ladder passed two
  `32474`-prompt-token sessions (`64948` combined) with exact expected-word
  matches and second-pass reload TTFT of `0.668-1.232 s`. A smaller live ops
  smoke with two `22540`-token fact-word sessions matched exact output hashes
  across passes; treat that as an operations canary, not the target context
  ceiling.
- c4/c8 are still research. Earlier c4/c8 ladders produced useful results, and
  c4/c8 sustained small-context warmed total decode was about `110 tok/s`, but
  live c4 service switching later hit a second-pass waiting/deferred stall and
  `UR_RESULT_ERROR_DEVICE_LOST` during vLLM block-table copy to GPU.
- TurboQuant is experimental. The patch
  `patches/vllm-turboquant-xpu-workspace-fallback-20260525.patch` gets past
  the first XPU locked-workspace crashes, and `turboquant_k8v4` can report
  about `80128` GPU KV tokens at 32K. It remains much slower than the
  FP16-family KV baseline and does not provide true 196K active context.
- Dirty live-source snapshots are tracked for audit:
  `patches/vllm-live-src-snapshot-20260525.patch` and
  `patches/llm-scaler-live-src-snapshot-20260525.patch`. These capture the
  originating host's broad local source deltas after the current experiments;
  they are not clean upstream-ready patches.
- Full `196608` active context is not solved. The current exact-quality path is
  CPU-paged attention, documented in
  `experiments/minimax_xpu_kv_offload/notes-20260525-cpu-paged-attention-design.md`.

## Quality Rules

Do not promote a speed result unless quality is preserved.

For low-level MiniMax performance changes, use the strict gates already in the
repo:

- raw145 exact token hashes at n64 and n256
- semantic canaries
- arithmetic repeat
- extended sixpack

For practical task lanes:

- validate generated output structurally, not just token speed
- count rejected attempts against effective throughput
- keep raw outputs and result JSON under `/home/steve/bench-results/...`
- label constrained-output results as constrained; do not present them as
  unconstrained general generation quality

## Key Repro Paths

Start here on a fresh machine:

- `AGENTS.md`
- `docs/current-reproducibility-map.md`
- `docs/b70-minimax-ubuntu24-deployment.md`
- `repro/minimax-m27-b70-110tps-ubuntu24-20260523/README.md`
- `repro/minimax-m27-b70-110tps-ubuntu24-20260523/scripts/`
- `experiments/minimax_xpu_kv_offload/REPRODUCE.md`
- `experiments/minimax_xpu_kv_offload/ARTIFACTS.md`
- `repro/minimax-m27-b70-89tps-20260520/README.md`
- `repro/minimax-m27-b70-89tps-20260520/scripts/00-install-system-deps.sh`
- `repro/minimax-m27-b70-89tps-20260520/scripts/01-download-model.sh`
- `repro/minimax-m27-b70-89tps-20260520/scripts/02-build-stack.sh`
- `repro/minimax-m27-b70-89tps-20260520/configs/promoted-env.sh`
- `repro/minimax-m27-b70-89tps-20260520/patches/`

Important notes:

- The 2026-05-23 repro is the best starting point for building a working
  endpoint from a fresh Ubuntu 24 system. It includes low-RAM SSD swap handling,
  a LAN bind server script, and Intel-facing failure notes.
- The repro folder is for the `89 tok/s` strict baseline, not the latest
  `94 tok/s` constrained HTML lane.
- The latest structured regex2 fix is recorded as a patch in
  `patches/minimax-website-structured-regex2-20260522.patch`.
- For the latest `94 tok/s` structured regex2 lane, use the focused public
  runner at `scripts/run-minimax-structured-skeleton-quality.py`. The broader
  local lab harness has more exploratory options, but this runner is the
  public reproducible harness for the promoted constrained HTML lane.

## Known Good Runtime Shape

Typical promoted environment flags include:

```bash
source repro/minimax-m27-b70-89tps-20260520/configs/promoted-env.sh
unset VLLM_XPU_CUDAGRAPH_PARTITION_COLLECTIVES || true
unset VLLM_XPU_CUDAGRAPH_STATIC_INPUT_COPY || true
```

For the structured HTML fast lane:

```bash
python scripts/run-minimax-structured-skeleton-quality.py \
  --mode graph \
  --warmup-runs 1 \
  --repeat 30 \
  --retry-until-pass 5 \
  --max-tokens 96 \
  --max-model-len 4096 \
  --max-num-batched-tokens 512
```

Expected regex2 result class:

- `30/30` accepted
- `0` rejected attempts
- output throughput around `94 tok/s` after warmup on matching hardware

## What Is Not Fully Solved

- Unconstrained free-form website output on the forced XPU graph path can still
  corrupt or degrade. Keep validating practical tasks.
- JSON structured lanes are better than free-form but can run below the HTML
  fast lane; use parsed JSON validation and count retries.
- True active-context overflow is not ready. CPU KV offload works as a
  session-cache/reload path for contexts that individually fit in GPU KV; it
  does not yet let one exact-attention request exceed live GPU KV.
- c4/c8 are not production-ready. They have useful ladder data, but c4 live
  operations hit a scheduler stall and a Level Zero device-lost path.
- Larger prefill chunks such as 1024 tokens can trigger Intel `ocloc`/IGC
  compiler failures on this stack; keep `max_num_batched_tokens=512` unless
  testing that specifically.
- Generic in-place allreduce thresholds were usually slower. Favor exact
  shape/dtype fusion with quality proof.

## Optimization Directions

Best next work:

- Expand validated practical tasks while keeping the 90+ tok/s lane.
- Build reliable prefill/context measurements without lowering decode quality.
- Long-context/concurrency RAM-overflow work is now tracked as a separate
  research lane in `experiments/minimax_xpu_kv_offload/`. Keep the stable 32K
  endpoint as the fallback. The initial CUDA-only CPU KV offload blocker was
  moved forward with an XPU worker prototype. That prototype can move KV blocks
  through pinned host RAM and supports session-cache/reload behavior, but the
  active request still needs its working KV in live GPU memory. The next real
  task for full context is CPU-paged attention, not another launch-flag change.
- Next context/speed options are captured in
  `notes/2026-05-23-minimax-context-speed-next-options.md`. Best first
  candidate is FP8 KV cache (`--kv-cache-dtype fp8`, optionally
  `--calculate-kv-scales`) at 32K, then 49K/65K only if exact and semantic
  quality gates pass. TurboQuant is now exposed in this vLLM build, including
  XPU routing, but should be treated as experimental; upstream guidance favors
  FP8 KV as the default and `turboquant_4bit_nc` only for memory pressure.
  N-gram speculation remains low priority for MiniMax because the local
  historical result was strongly negative, though it helped Qwen FP8.
- Endpoint-facing measurement script:
  `scripts/measure-openai-endpoint-metrics.py`. It uses `/v1/completions`
  streaming plus vLLM `/metrics` deltas to capture TTFT, e2e, output tok/s,
  total tok/s, VRAM snapshots, and a conservative prefill lower-bound without
  changing server settings. First p510/n1536 32K endpoint artifact:
  `data/minimax-m27-openai-endpoint-metrics-32k-20260524.json`; measured
  `85.453` output tok/s after first streamed chunk, `111.635` total tok/s,
  `351.068 ms` vLLM TTFT, and `1445.634 tok/s` conservative prefill
  lower-bound. A LocalMaxxing payload with TTFT was prepared at
  `data/localmaxxing-minimax-m27-autoround-openai-32k-endpoint-metrics-20260524.payload.json`,
  but POST attempts returned HTTP 502; retry later.
- TurboQuant repro script:
  `scripts/repro-minimax-turboquant-xpu-workspace-bug.sh`. The current
  workspace fallback patch is tracked at
  `patches/vllm-turboquant-xpu-workspace-fallback-20260525.patch`; after the
  patch, `turboquant_k8v4` can answer strict-word canaries at about 8K and
  32.5K prompt sizes and reports about `80128` GPU KV tokens at 32K, but decode
  is much slower than the normal FP16-family KV lane.
- Speed recovery policy:
  `notes/2026-05-23-speed-recovery-quality-plan.md`. Do not promote 90+ tok/s
  graph/runtime paths unless exact-token, semantic, arithmetic, and practical
  quality gates pass.
- Debug c4/c8 service-mode failures with small canaries before trying long
  sustained decode. c2 is the current safer RAM-backed lane.
- Continue lower-level fusion only where math is exactly preserved:
  Q/K variance allreduce plus RMS apply, hidden allreduce plus residual/RMSNorm,
  MoE output plus epilogue, and final projection/lm-head boundaries.
- Mine llm-scaler for ideas, but require strict quality gates before promotion.

Avoid:

- claiming constrained decode as unconstrained quality
- comparing AutoRound INT4 as equivalent to Q4_0/FP8 without separate quality
  checks
- disabling clones/allreduces broadly without exact shape and quality proof
- power tuning as the explanation for speed

## GitHub And LocalMaxxing

Use whichever GitHub write path is configured for the environment, and record
the commit IDs in the final response. On this host, local git push over the
installed deploy key has been used successfully.

Significant benchmark results should be submitted to LocalMaxxing with payloads
and responses recorded under `data/`.

Recent important LocalMaxxing IDs:

- MiniMax structured regex2: `cmphg048s00mppc0192sahyug`
- MiniMax strict p512/n1536 high: `cmpct6t4m007fnw01yjdtlcs4`
- MiniMax OpenAI 32K context endpoint: `cmpj1fmvv001hqr01oj4hiu3d`
- JSON gated c1 practical task: `cmpgv9p9j007qpc01oq5zqhdg`
- JSON c1 2k-context follow-up: `cmpgx0yrb009fpc0183xjri4j`

## Models Expected On Disk

Main models of interest:

- `Lasimeri/MiniMax-M2.7-int4-AutoRound`
- Qwen3.6 27B Q4_0 GGUF
- Qwen3.6 27B FP8
- MiniMax M2.7 GGUF/UD-IQ4_XS for comparison

The model weights themselves are not in GitHub. Use the repro download scripts
and local Hugging Face cache conventions from the repro folder.
