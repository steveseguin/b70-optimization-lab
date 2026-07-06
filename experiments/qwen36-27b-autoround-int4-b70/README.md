# Qwen3.6 27B INT4 AutoRound vLLM/XPU Lab

This experiment lane tracks bring-up and optimization for:

- Model: `Intel/Qwen3.6-27B-int4-AutoRound`
- Base model: `Qwen/Qwen3.6-27B`
- Quantization: AutoRound INT4, `bits=4`, `group_size=128`, symmetric,
  `packing_format=auto_round:auto_gptq`
- Runtime target: vLLM on Intel XPU / Level Zero
- Hardware target: Intel Arc Pro B70 32 GB, one replica per GPU first

## Immediate Goal

The initial TP1 single-B70 OpenAI-compatible endpoint works, and the lane now
has a strict fresh-response BF16-LM-head baseline plus faster quality-gated
runtime INT8/INT4 LM-head variants. Current optimization work must beat the
`68.23626314761921` tok/s ReplaySSM target-INT8/draft-INT4 row or improve
service/max-context behavior without using warmed/cache/history effects.

Completed first milestone:

1. Downloaded/pinned revision `abc86de19eb1ebbf6a7df4582341325c22ddcb7d`.
2. Served one TP1 replica at `max_model_len=2048`.
3. Passed the OpenAI smoke with thinking disabled.
4. Observed healthy MTP2 acceptance (`105/108` accepted draft tokens after
   manual probes plus smoke).

Current evidence:

- server log:
  `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/servers/tp1-gpu0-port19410-20260703T012317Z.log`;
- smoke JSON:
  `data/qwen36-27b-autoround-openai-smoke-20260703T013020Z.json`.

Current strict best:

- config: Intel checkpoint, TP1, one B70, XPU graph on, `qwen3_next_mtp`,
  `num_speculative_tokens=3`, `max_cudagraph_capture_size=8`,
  `max_num_batched_tokens=1024`;
- env delta: `VLLM_XPU_GDN_PROMOTE_ACCEPTED_SPEC_STATE=1` and
  `VLLM_XPU_GDN_NONSPEC_POSTPROCESS_ACCEPTED_STATE=0`;
- gate: Qwen realistic suite, chat mode, 12 unique prompts, each prompt once,
  `cached_tokens=0` every row, `return_token_ids=true`;
- conservative result: median `53.522 tok/s` for generated tokens 1-100 after
  TTFT, p10 `48.406`, mean `53.986`;
- evidence:
  `data/qwen36-27b-autoround-int4-b70-baselines/intel-mtp3-xpugraph1-cg8-promotesource-noacceptedpost-repeat2-realistic128-chat-tokenids-qwensuite-20260703T044519Z.json`;
- compact packet:
  `results/qwen36-27b-autoround-int4-b70/promote-source-noacceptedpost-20260703.json`.

Current fastest quality-gated variant:

- label: `webhie/Qwen3.6-27B-int4-AutoRound + runtime INT8 target
  LM-head (BF16 scales) + runtime INT4 draft LM-head (BF16 scales)`;
- config: same promote-source MTP3/cg8 recipe plus ReplaySSM exact GDN state
  handling, commit-in-forward, target INT8 LM-head BF16 scales, draft INT4
  LM-head BF16 scales, and conservative PyTorch slot-management fallback;
- strict fresh median: `68.236 tok/s`, p10 `62.317`, mean `67.830`,
  `cached_tokens=0`;
- support rows: `67.519` prior approved confirm, `68.397` same-recipe
  quality-skipped control, `68.481` native-slot-copy smoke, `66.871`
  native-slot-copy confirm, and `67.300` PyTorch-slot-management same-window
  control. Use `68.236` as the current quality-confirmed headline, not the
  quality-skipped `68.397` or the one-off `68.481`;
- latest reproducibility repair/support:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-regressionfix-quality-confirm-20260706T102729Z-candidate-summary-20260706T102729Z.json`
  at `67.33805616805299 tok/s`, strict fresh/cached-zero with repeat64
  quality and baseline match all. The focused source guard is captured at
  `patches/qwen36-27b-autoround-int4-b70/vllm-qwen27-mixed-draft-kv-metadata-guard-20260706.patch`;
- quality: repeat64 passed, baseline matched, strict fresh gate passed;
- evidence:
  `../../results/qwen36-27b-autoround-int4-b70/webhie-int8lmhead-bf16scale-draftint4-replayssm-current-confirm-20260706.json`;
- note:
  `notes/2026-07-06-current-confirm-68tok-and-textonlymtp-no-win.md`;
- LocalMaxxing: approved as `cmr9atqb800msqr01u760xh0t`.

Latest stronger-drafter result:

- Ex0bit EAGLE3/DFlash aux-hidden probing is closed as a direct import path.
  The new target-owned aux corpus runner collected 96 prompts / 15,360 rows
  with aux layers `1,31,60` and no continuity breaks, and the new offline
  evaluator successfully loads both Ex0bit compressed and full-vocab EAGLE3
  checkpoints. Acceptance is far too low: compressed mean accepted
  `0.289908` over 14,784 starts (`24.40%` step-1 exact), while the full-vocab
  spot check is the same class at `0.291016` over 512 starts. Do not spend
  endpoint/kernel work on the off-the-shelf Ex0bit checkpoint as-is. The useful
  artifact is the EAGLE3 aux collection/eval path, which can now support a
  target-matched EAGLE3/DFlash training attempt. See
  `notes/2026-07-06-ex0bit-eagle3-aux-probe-no-win.md`.
- First target-matched adaptation screen is also diagnostic-only. The new
  `scripts/train-qwen27-ex0bit-eagle3-adapter.py` can adapt Ex0bit-format
  checkpoints from `qwen36_eagle_sequence_v2` data. The larger follow-up used
  all 4 B70s to collect 384 target-owned prompts / 61,440 rows, trained
  `fc-lm-head` on 288 prompts, and held out 96 prompts. It improved heldout
  rollout from direct Ex0bit `0.289` and the first adaptation `0.539` to
  `0.6003787878787878` mean accepted, with `48.65%` step-1 exact but only
  `20.10%` step-2 conditional exact. This is still far below current MTP3
  accepted depth and not endpoint-worthy. Next EAGLE/DFlash work needs a
  multi-step rollout / accepted-prefix training objective, not endpoint
  plumbing. See
  `notes/2026-07-06-ex0bit-eagle3-target-adaptation-screen.md`.

Previous fastest quality-gated variant:

- label: `webhie/Qwen3.6-27B-int4-AutoRound + runtime INT8 LM-head
  (BF16 scales)`;
- config: same promote-source MTP3/cg8 recipe plus
  `VLLM_XPU_LM_HEAD_INT8=1` and
  `VLLM_XPU_LM_HEAD_INT8_SCALE_DTYPE=bf16`;
- strict fresh median: `65.276 tok/s`, p10 `59.609`, mean `65.077`,
  `cached_tokens=0`;
- support rows: `65.005` and `64.864 tok/s`;
- latest unchanged-recipe support:
  `notes/2026-07-04-post-awq-record-repro-support.md` at
  `66.12771533602819 tok/s`, strict fresh/cached-zero gate passed, smoke
  passed, no LocalMaxxing update because the recipe is unchanged and no fresh
  quality rerun was required for a support check;
- same-window/crossover FP32-scale controls: `64.234` and `64.090 tok/s`;
- prior webhie INT8-LM-head record: `64.306 tok/s`;
- full quality gate passed against the Intel INT8-LM-head baseline, including
  1K long-context needle;
- evidence:
  `results/qwen36-27b-autoround-int4-b70/webhie-int8-lmhead-bf16scale-20260703.json`;
- note:
  `notes/2026-07-03-int8-lmhead-bf16-scale-quality-pass.md`.
- LocalMaxxing: approved as `cmr5iu3gk00bfq901nidgcana`.
- latest continuation bookmark:
  `notes/2026-07-04-continuation-source-and-awq-state.md`. This preserves the
  active source snapshots, closes another no-repeat audit of cheap env/config
  knobs, and records the `cyankiwi/Qwen3.6-27B-AWQ-INT4` strict screen result:
  compressed-tensors AWQ loaded and passed the fresh/cached-zero gate
  mechanically, but only reached `56.565 tok/s` and is closed no-win. See
  `notes/2026-07-04-cyankiwi-awq-int4-screen-no-win.md`.

Prior Intel-checkpoint fastest quality-gated variant:

- label: `AutoRound W4A16 + runtime INT8 LM-head`;
- config: same promote-source MTP3/cg8 recipe plus
  `VLLM_XPU_LM_HEAD_INT8=1`;
- strict fresh median: `62.628 tok/s`, p10 `58.104`, mean `62.998`,
  `cached_tokens=0`;
- repeat: `62.276 tok/s` on GPU3;
- same-window BF16-LM-head control: `53.332 tok/s`;
- full quality gate passed against the BF16-LM-head baseline, including
  1K long-context needle;
- evidence:
  `results/qwen36-27b-autoround-int4-b70/int8-lmhead-20260703.json`;
- patch:
  `patches/qwen36-27b-autoround-int4-b70/vllm-xpu-lm-head-int8-quality-pass-20260703.patch`.

Service-oriented INT8-head variant:

- config: same recipe plus `VLLM_XPU_LM_HEAD_INT8_SCOPE=target`;
- strict fresh median: `61.898 tok/s`, p10 `57.494`, mean `62.432`;
- full quality gate passed against the BF16-LM-head baseline;
- interpretation: target verifier LM-head dominates the speedup; draft-only
  INT8 was essentially BF16 control. Use all-head INT8 for the submitted
  max-throughput row. The older Intel-checkpoint target-only lane passed its
  quality gate, but the later webhie BF16-scale target-only follow-up failed
  repeat32 stability once (`blue, green, red`), so treat target-only as an
  attribution/service idea that must be revalidated per checkpoint/revision and
  scale dtype;
- note:
  `notes/2026-07-03-int8-lmhead-scope-attribution.md`;
- patch:
  `patches/qwen36-27b-autoround-int4-b70/vllm-xpu-lm-head-int8-scope-target-quality-pass-20260703.patch`.

Synthetic search reference:

- config: MTP5/cg16;
- p512/o512 synthetic `vllm-random`: `81.773 tok/s`;
- evidence:
  `data/qwen36-27b-autoround-int4-b70-baselines/intel-mtp5-xpugraph1-cg16-specmetrics-p512o512-r3-20260703T031846Z.json`;
- status: diagnostic only. It loses under the realistic chat gate.

Next milestone:

1. Treat Phase 0/1 as complete. The current record family reproduced at
   `65.56930784255283 tok/s`, and the timing refresh is captured in
   `notes/2026-07-04-phase0-phase1-baseline-and-timing.md`.
2. Use four independent TP1 replicas for parallel candidate screening when the
   candidate is cheap enough to run as a config/source screen.
3. Keep synthetic `vllm-random` metrics diagnostic-only.
4. Rerun the Qwen realistic suite with `--return-token-ids` before promoting
   any change.
   Use `scripts/run-vllm-candidate.sh` for single-replica strict candidate
   screens so server logs, smoke output, strict fresh gate results, optional
   quality checks, and compact summaries are captured consistently.
5. Do not keep config-sweeping the current INT8 lane without a new mechanism:
   MTP depth remains k=3, capture size remains cg8, MBT1024 remains the short
   decode setting, and the cheap LM-head/sampler/logits wrappers are closed.
   The 2026-07-05 timing refresh shows the current measured path is no longer
   dominated by a large dense LM-head block: INT8 LM-head/local-argmax is small,
   while target forward plus recurrent MTP draft forward dominates. See
   `notes/2026-07-05-replayssm-stage-profile-and-frontier.md`.
6. Remaining credible lanes need a real mechanism: a materially stronger
   target-matched drafter, accepted-token-per-target-step gains that keep exact
   verification, target-forward/kernel reductions, or graph-safe
   GDN/DeltaNet/spec-state transactions. Older LM-head/verifier notes remain
   useful historical context, but do not rerun wrapper-level LM-head work
   unless the candidate is a genuinely new backend producer rather than another
   reduction around dense logits. See
   `notes/2026-07-04-frontier-audit-onednn-graph-and-drafter.md`,
   `notes/2026-07-04-compact-lmhead-top1-kernel-no-win.md`, and
   `notes/2026-07-05-replayssm-stage-profile-and-frontier.md`.
   The latest synchronized MTP-forward diagnostic in
   `notes/2026-07-06-draft-proposer-timing-split.md` closes the apparent
   `~11 ms` recurrent MTP-next cost as async timing attribution: recurrent
   dispatches are `PIECEWISE` graph mode and synchronized
   `model_forward_first/next` are sub-millisecond. Do not chase MTP-next as an
   eager-kernel bug; use accepted-token, target-forward, stronger-drafter, or
   graph-safe state-transaction work for the next real speed attempt.
   The latest graph-safe transaction precheck is
   `notes/2026-07-06-replayssm-commit-pending-active-slot-guard.md`: native
   `gdn_replayssm_commit_pending` used to mutate metadata for null,
   out-of-range, or inactive rows; the new guard script
   `../../scripts/check-gdn-replayssm-commit-pending.py` now passes BF16/FP16/FP32
   plus native prefix/recurrent checks after an active-slot guard. This is
   infrastructure for partial-group / branch-regenerate work, not a throughput
   win or LocalMaxxing row.
   The follow-up branch-fork composition guard is
   `notes/2026-07-06-replayssm-branch-fork-composition-guard.md`: native
   `copy_slots` + compacted native `commit_pending` can fork a valid branch
   slot and commit an accepted prefix exactly, but committing raw destination
   rows after invalid-source copies corrupts unrelated pending slots. Any
   branch/regenerate endpoint prototype must compact valid `(src, dst)` rows
   before commit.
   The 2026-07-06 replacement-suppression plumbing/margin follow-up is also
   closed no-win: active scheduler recovery passed quality only at `~34-49
   tok/s`, and margin gating stayed below record. See
   `notes/2026-07-06-replacement-mask-plumbing-and-margin-no-win.md` and
   `../../patches/qwen36-27b-autoround-int4-b70/vllm-qwen27-replacement-mask-plumbing-margin-no-win-20260706.patch`.
   The external `Qwen/Qwen3.5-0.8B` draft-model probe is also closed no-win:
   compatibility work got explicit `draft_model` serving, text-only Qwen3.5
   M-RoPE, mixed draft KV groups, and mixed block sizes past startup, but the
   live k8 run accepted `0` draft tokens and fell to only `~2.3-2.6 tok/s`
   while rejecting every draft. See
   `notes/2026-07-06-qwen35-08b-external-draftmodel-zero-acceptance.md` and
   `../../patches/qwen36-27b-autoround-int4-b70/vllm-qwen27-qwen35-08b-explicit-draftmodel-compat-zeroaccept-20260706.patch`.
7. Closed source precheck: the default-off spec greedy top-token-ID
   verifier path passed the strict gate at `65.25583870721442 tok/s`, but it
   was flat versus the `65.27648650325429 tok/s` record because
   `get_top_tokens()` still pays the dense LM-head. Treat
   `notes/2026-07-04-spec-greedy-topids-no-headline-win.md` as integration
   groundwork for a future true compact LM-head kernel, not a path to retest by
   itself.
8. Latest closed kernel precheck:
   `notes/2026-07-04-compact-lmhead-top1-kernel-no-win.md`. The native
   `int8_lm_head_top1_w8a8` prototype was exact but slower than dense oneDNN:
   final 8x64 policy measured compact `2.66-2.68 ms` versus dense
   `2.57-2.61 ms` for rows `1-4`, so do not wire it into vLLM.
9. Latest model-variant / MTP-layer audit:
   `notes/2026-07-04-autoround-variant-screening-and-stepidx-audit.md`.
   Local `webhie-Code` and `acyildirimer` AutoRound variants passed the strict
   gate but were slower than the same-window webhie control, and the possible
   `spec_step_idx` MTP fix is a no-op for this lane because the checked
   Qwen27 AutoRound configs all have `mtp_num_hidden_layers=1`. The focused
   future-use patch is preserved at
   `../../patches/qwen36-27b-autoround-int4-b70/vllm-qwen-mtp-spec-step-idx-pass-through-future-20260706.patch`
   and documented in
   `notes/2026-07-06-qwen-mtp-spec-step-idx-pass-through.md`; do not treat it
   as a current Qwen27 speed candidate unless a checkpoint with multiple
   `mtp.layers.N` tensors is introduced.
10. Latest current-recipe depth screen:
    `notes/2026-07-04-webhie-depth-screen-no-win.md`. On the fastest
    webhie/BF16-scale INT8-LM-head recipe, strict same-window MTP4/cg8
    (`60.478 tok/s`), MTP5/cg8 (`59.257 tok/s`), and MTP5/cg16
    (`59.817 tok/s`) all lost to the MTP3/cg8 control (`65.809 tok/s`).
    Treat the control as support/variance only, not a new LocalMaxxing row.
11. Latest shallow-depth coverage screen:
    `notes/2026-07-04-webhie-mtp1-mtp2-depth-coverage-no-win.md`.
    The missing MTP1/MTP2 current-recipe coverage is closed: MTP1/cg8
    `51.246`, MTP2/cg8 `59.589`, MTP3/cg8 control `64.730`, MTP4/cg8
    `59.886`, all `cached_tokens=0` and gate-passing. Keep MTP3/cg8.
12. Latest current-recipe capture-size screen:
    `notes/2026-07-04-webhie-bf16scale-capture-size-screen-no-win.md`.
    On the same webhie/BF16-scale MTP3 recipe, a four-GPU strict same-window
    screen found cg8 remains best: cg4 `64.507`, cg8 control `65.153`, cg16
    `63.500`, cg32 `64.071`, all `cached_tokens=0` and gate-passing. Keep
    `max_cudagraph_capture_size=8` unless a source change alters graph shapes,
    row counts, or acceptance.
13. Latest INT8 GEMM scratchpad ring-size screen:
    `notes/2026-07-04-int8-gemm-scratchpad-ring-screen-no-win.md`.
    The low-level ring-size screen found ring4 highs (`65.708`, `65.817`) but
    paired crossover deltas versus ring1 controls were only `+0.42%` and
    `+0.27%`, below the practical variance band. Do not promote or submit;
    keep default ring behavior unless a future trace shows scratchpad reuse as
    a real issue.
14. Latest INT4 W4A16 GEMM scratchpad ring-size screen:
    `notes/2026-07-06-int4-gemm-scratchpad-ring-no-win.md`.
    A default-off `VLLM_XPU_INT4_GEMM_SCRATCHPAD_RING_SIZE` patch built and
    endpoint-ran, but ring1 only measured `+0.08%` mean / `+0.18%`
    median-of-runs over ring0 controls after crossover, while ring2/ring4 did
    not help. The active source and live `_C` binary were restored; preserve
    the patch as negative evidence only.
15. Latest GDN qkvz/ba quant-reuse screen:
    `notes/2026-07-05-gdn-qkvz-ba-quant-reuse-no-win.md`.
    A same-window four-GPU strict fresh screen of
    `VLLM_XPU_GDN_REUSE_QKVZ_BA_QUANT=clone`, `clone-ba`, and `clone-qkvz`
    found no credible win over control: control `64.398 tok/s`, best
    `clone-qkvz` `64.824 tok/s`, inside variance. Keep the promoted recipe
    unchanged.
16. Latest target-forward quick screens and backlog:
    `notes/2026-07-05-target-forward-low-risk-screens-and-backlog.md`.
    M-RoPE text-only fast path (`65.797` vs control `65.960`) and GDN fallback
    `prefill` only (`65.655` vs control `65.967`) both passed the strict fresh
    gate but did not beat controls. Continue with source/kernel work, not more
    easy env knobs.
16. Latest QK-norm + RoPE fusion spike:
    `notes/2026-07-05-qk-norm-rope-fused-spike-no-win.md`.
    A default-off Qwen3Next-specific XPU fusion for the gated
    `[q, gate, k, v]` layout passed direct BF16 parity, but regressed the
    strict fresh endpoint to `45.980 tok/s` versus the `65.276 tok/s` record.
    The patch is preserved at
    `../../patches/qwen36-27b-autoround-int4-b70/vllm-qwen27-qk-norm-rope-fused-spike-20260705.patch`.
    Do not repeat this endpoint lane unless a new kernel first beats the
    existing separate Q/K norm + RoPE primitives in a standalone microbench.
17. Latest GDN output norm native spike:
    `notes/2026-07-05-gdn-output-norm-native-no-win.md`.
    A default-off `_xpu_C.gdn_rms_norm_gated_xpu_out` path was very fast in a
    direct microbench and passed repeat32 quality, but same-window strict fresh
    controls beat the endpoint candidate on average (`65.299` control vs
    `64.569` native). The live vLLM/XPU source and local extension binary were
    restored. Keep only the preserved no-win patches; do not repeat this lane
    unless a future trace shows GDN output norm as a large standalone region.
18. Native GDN SSM-only promotion precheck:
    `notes/2026-07-05-native-promote-ssm-only-crash.md`.
    The Python-only `VLLM_XPU_GDN_NATIVE_PROMOTE_CONV_STATE=0` switch passed
    OpenAI smoke but hit `UR_RESULT_ERROR_DEVICE_LOST` during the strict run
    before benchmark or quality artifacts. Treat it as crash/inconclusive, not
    a speed or quality result. The next attempt must add a matching default-off
    C++ gate around `copy_conv_rows_to_indices` in `gdn_attention_spec_decode`
    so the packed native path and Python promotion agree on whether conv rows
    are copied. That follow-up is now closed no-win too:
    `notes/2026-07-05-native-spec-conv-copy-gate-no-win.md` disabled both
    native conv promotion paths and made repeat64 quality worse (`62/64`
    `blue, green red yellow`, plus one runaway repetition). Do not rerun blind
    conv-copy disablement; future GDN state work needs a traced/taped exact
    conv-window transaction.
19. Latest MTP text `input_ids` dispatch shortcut:
    `notes/2026-07-05-mtp-text-inputids-next-no-win.md`.
    Dispatch tracing showed recurrent Qwen3.5 MTP-next draft calls used
    `inputs_embeds=[1,5120]` with `input_ids=None`, so a default-off source
    spike tried to keep text-only embedding lookup inside the captured draft
    forward by passing token IDs. Attempt 1 crashed before readiness because
    torch compile tried to size `inputs_embeds=None`; the compile-shape
    workaround got past that but stalled during decode PIECEWISE graph capture.
    Active vLLM source was reverted, and the no-win patch is preserved at
    `../../patches/qwen36-27b-autoround-int4-b70/vllm-qwen27-mtp-text-inputids-next-no-win-20260705.patch`.
    Do not repeat this wrapper-level shortcut without a deeper compile/cudagraph
    design change.
20. Latest GDN accepted-source packed decode precheck:
    `notes/2026-07-05-gdn-packed-decode-with-source-no-win.md`.
    A default-off `VLLM_XPU_GDN_PACKED_DECODE_WITH_SOURCE=1` patch allowed the
    packed one-token GDN decode helper when accepted source rows were present
    and promoted both conv and SSM before the packed update. Same-window strict
    fresh/cached-zero screen passed mechanically, but the candidate lost to
    control (`65.077` vs `65.631 tok/s`). Active vLLM source was reverted, and
    the no-win patch is preserved at
    `../../patches/qwen36-27b-autoround-int4-b70/vllm-qwen27-gdn-packed-decode-with-source-no-win-20260705.patch`.
    Do not repeat Python-level accepted-source promotion shortcuts; future GDN
    state work needs a traced exact accepted-prefix transaction or native
    graph-safe tape/commit path.
20. Latest variable-depth source precheck:
    `notes/2026-07-04-dynamic-drafter-depth-partial-group-crash.md`.
    A default-off prototype that actually shortened the MTP proposer loop
    crashed with an XPU indexing assert when it created partial speculative
    groups. A follow-up with upstream-style placeholder `-1` rejection applied
    also failed the same way:
    `notes/2026-07-04-dynamic-depth-placeholder-reject-retry-no-win.md`.
    Do not retry dynamic depth by changing only sampler placeholder handling;
    partial groups need explicit support across proposer output, verifier
    metadata, sampler rows, GDN state commit, and graph capture shapes.
20. Latest DFlash revisit:
    `notes/2026-07-04-dflash-swa-revisit.md`. Real mixed SWA support crashes
    before readiness because the current DFlash/EAGLE proposer assumes all
    draft layers belong to one KV-cache group. The target-verified
    `all-sliding` single-group diagnostic passed the fresh gate but dropped to
    `20.630 tok/s`, so DFlash remains closed no-win until multi-KV-group draft
    metadata is implemented.
21. Latest DFlash multi-KV implementation attempt:
    `notes/2026-07-04-dflash-multikv-mixed-swa-attempt.md`. The experimental
    patch
    `../../patches/qwen36-27b-autoround-int4-b70/vllm-dflash-multikv-mixed-swa-attempt-20260704.patch`
    gets mixed full/sliding DFlash through startup and graph capture with draft
    KV groups `[64, 65, 66, 67, 68]`, but endpoint testing is still no-win:
    graph mode device-loses during the strict suite, and graph-off/no-async
    shows only about `2-3%` draft acceptance with low-teens or worse generation
    throughput. Preserve the patch as upstream/plumbing research, not as a
    record lane.
22. Latest service-memory flag screen:
    `notes/2026-07-04-language-model-only-no-win.md`.
    `--language-model-only` correctly enters text-only mode and reduced model
    memory from `19.02 GiB` to `18.15 GiB`, but the MTP3/cg8 XPU graph path
    hung before readiness at `Capturing CUDA graphs (decode, PIECEWISE): 0/1`.
    Do not use it for the current strict decode recipe; only revisit for
    non-MTP/non-graph service-memory work or after XPU graph capture changes.
23. Latest scheduler screen:
    `notes/2026-07-04-scheduler-mbt-and-chunked-prefill-screen.md`.
    MBT768 (`64.131 tok/s`) and MBT1280 (`64.346 tok/s`) passed the strict
    fresh gate but lost to the current `65.276 tok/s` record family; disabling
    chunked prefill is invalid for `MAX_MODEL_LEN=2048` / MBT1024. Keep
    `MAX_NUM_BATCHED_TOKENS=1024` and chunked prefill enabled.
24. Latest local EAGLE1 endpoint isolation:
    `notes/2026-07-04-eagle1-endpoint-isolation-matrix.md`.
    The first local EAGLE1 draft looked promising offline (`2.1016` mean
    accepted tokens on held-out calibration starts) but did not survive endpoint
    isolation. Current-state eager k3, default-state graph k3, and
    current-state graph k1 all failed the calibration gate at only
    `19.828-22.410 tok/s`; current-state graph k3 stalled before JSON output.
    The compact summary is
    `../../data/qwen36-27b-autoround-int4-b70-baselines/qwen27-eagle1-endpoint-isolation-20260704T094450Z-summary.json`.
    Do not repeat endpoint config sweeps for this draft; future EAGLE work
    starts with diverse chat-style corpus/eval v2 and stronger held-out
    diagnostics.
25. EAGLE corpus/eval v2 tooling:
    `notes/2026-07-04-eagle-corpus-v2-tooling.md`.
    The collector now supports `--suite`, chat mode, request extra JSON, stable
    request IDs, and prompt metadata; the dataset builder copies that metadata
    into `.pt` samples; and offline eval reports acceptance by prompt family.
    This is preparation only, not a speed result, but it is the correct restart
    point if EAGLE is revisited.
26. EAGLE corpus/eval v2 chat smoke:
    `notes/2026-07-04-eagle-corpus-v2-chat-calib-smoke.md`.
    A one-GPU calibration-suite chat collection produced `3840` hidden rows,
    `24` samples, `0` continuity breaks, and metadata on `24/24` samples after
    fixing suffix-tolerant request-ID matching. A tiny two-epoch draft reached
    only `0.240` mean accepted offline, so it is not an endpoint candidate; it
    only proves the metadata path works.
27. EAGLE corpus/eval v2 four-GPU heldout screen:
    `notes/2026-07-04-eagle-corpus-v2-4gpu-heldout.md`.
    The four-GPU runner collected `96` chat prompts, `15360` hidden rows, `96`
    samples, metadata on `96/96` samples, and `0` continuity breaks. A compact
    draft trained on shards `0-2` and evaluated on heldout shard `3` reached
    only `0.489` mean accepted over `1024` starts, far below the prior `2.1016`
    offline draft that still failed endpoint quality. Do not endpoint-test this
    draft; future EAGLE work needs materially stronger data/training/init first.
28. EAGLE corpus/eval v2 followups:
    `notes/2026-07-04-eagle-corpus-v2-followups-closed.md`.
    The staged curriculum improved OOD-family heldout only to `0.616`, a
    balanced task-holdout split scored `0.601`, the old stronger v1 draft
    transferred poorly to v2 heldout (`0.201`), and all-96 training scored only
    `0.438` on the separate calibration suite. Current compact v2 EAGLE is
    closed again; do not endpoint-test these drafts.
29. EAGLE v2 stronger offline screen:
    `notes/2026-07-04-eagle-v2-stronger-offline-screen-no-endpoint.md`.
    The stronger residual/two-layer screen improved heldout only to `0.695`
    mean accepted and separate calibration only to `0.441`. It is
    diagnostic-only and not an endpoint candidate. The reusable runner is
    `scripts/run-eagle-v2-stronger-offline-screen.sh`.
30. EAGLE v3 target-architecture/loss offline screen:
    `notes/2026-07-04-eagle-v3-target-loss-offline-no-endpoint.md`.
    Target-shaped one-layer drafts and token-heavy losses did not help on the
    current v2 corpus. Best row was the compact frozen-base residual variant at
    only `0.647` heldout mean accepted and `0.423` separate-calibration mean
    accepted, below the prior v2 stronger screen and far below the offline
    endpoint gate. Do not rerun larger/target-shaped EAGLE on this same corpus
    without a materially new data or architecture idea. Reusable runner:
    `scripts/run-eagle-v3-target-loss-offline-screen.sh`.
31. EAGLE v4 large-corpus offline screen:
    `notes/2026-07-06-eagle-v4-large-corpus-no-endpoint.md`.
    A larger four-GPU non-final chat corpus collected `384` prompts,
    `61,440` hidden rows, `384` samples, metadata on `384/384` samples, and
    `0` continuity breaks. The best larger compact draft reached only
    `0.718` heldout mean accepted and `0.512` separate-calibration mean
    accepted, far below the endpoint gate (`2.0` heldout / `1.5` calibration).
    This closes "just more non-final data and hparams on the same compact
    EAGLE architecture"; no endpoint run and no LocalMaxxing submission.
32. Draft top-k calibration diagnostic:
    `notes/2026-07-04-draft-topk-calibration-diagnostic.md`.
    The target verifier token is in the built-in draft top-32 for `96-99%` of
    MTP positions and an oracle reranker would reach `3.910` target-verified
    tokens/step on the 24-prompt trace; a larger 96-prompt non-final trace
    confirmed base `2.595` vs oracle `3.864`, but simple static token-bias and
    margin rerankers were flat or worse on prompt-heldout split. A small
    learned top-k MLP also moved only `2.7123 -> 2.7184` target tokens/step on
    a separate calibration trace, too little for runtime overhead. Preserve the
    trace/analyzers; do not ship a heuristic or tiny top-k reranker. Future
    accepted-token work needs a materially stronger drafter/reranker on
    isolated non-final data.
33. Draft top-k64 / sequential-reranker limit:
    `notes/2026-07-04-draft-topk64-and-sequential-reranker-limit.md`.
    A full 96-prompt K64 diagnostic found target-in-top64 rates of
    `99.7%`, `98.4%`, and `96.8%` by draft position, but held-out margin
    reranking was flat and sparse-bias reranking regressed. The independent
    oracle is an invalid post-hoc endpoint shortcut for sequential MTP, and
    the final-slot upper bound still needs recomputing/branching the target
    bonus row while adding only about `+0.16` target tokens/step. Do not
    reopen cheap top-k reranker endpoint patches.
33. Token-tree mechanical screen:
    `notes/2026-07-04-token-tree-mechanical-screen-no-win.md`.
    Existing vLLM `speculative_token_tree` support works mechanically for
    Qwen27/XPU, but config-only tree shapes do not beat MTP3/cg8. A same-suite
    24-prompt control reached `63.871 tok/s`; binary depth-2 tree reached
    `60.526 tok/s`; root top-3 reached `63.107 tok/s`; all completed rows were
    strict fresh/cached-zero diagnostics. Root top-2 stalled during drafter
    checkpoint load, and root top-3 already closed the same root-alternative
    idea. Do not reopen token-tree sweeps unless the branch design avoids the
    current full-logits tree proposer cost or uses a stronger legal drafter.
34. Token-tree retest on current ReplaySSM/draft-INT4 recipe:
    `notes/2026-07-06-token-tree-current-recipe-no-win.md`.
    Same-window strict fresh diagnostics with the current target-INT8/draft-INT4
    ReplaySSM recipe found no win: ordinary MTP3 control `67.797 tok/s`,
    root-3 `67.691`, root-2 `59.159`, and binary-depth-2 `12.709`. No quality
    run was warranted. Do not repeat config-only token-tree sweeps on this
    recipe.
35. Short-decode `MAX_NUM_BATCHED_TOKENS` screen:
    `notes/2026-07-04-short-decode-mbt-screen-no-win.md`.
    The current record recipe should stay at MBT1024 for short decode.
    Same-window candidates MBT1536, MBT2048, and MBT4096 all passed the strict
    fresh/cached-zero gate but landed at `63.829`, `64.239`, and `64.779 tok/s`,
    below the `65.276` record and inside recipe variance. The MBT1024 control
    row is invalid because GPU0 device-lost during the first benchmark request
    after smoke passed; existing support rows already cover the default recipe.
36. Frontier closure:
    `notes/2026-07-04-frontier-closure-and-next-projects.md`.
    Independent audits found no unclosed non-cheating config/runtime lane and
    no bounded atomic/single-pass/fused-quant LM-head kernel tweak likely to
    beat dense oneDNN by `>10%`. Do not launch more Qwen27 endpoint/config
    screens until the candidate is a real top-ID LM-head producer, a materially
    stronger drafter/branch-regenerate architecture, or full partial-group
    source support.
37. Branch/regenerate feasibility envelope:
    `notes/2026-07-06-branch-regenerate-feasibility-envelope.md`.
    The existing top-k64 trace was converted into a legal cost envelope. With
    the then-current `67.519 tok/s` record and `2.6243` target-verified tokens/step,
    the inferred verifier step is `38.87 ms`. A perfect MTP3 first-reject
    branch/regenerate path with top-64 access reaches only `3.9565`
    tokens/step, or `101.8 tok/s` if it adds zero step cost; it has only
    `0.697 ms/step` budget for a `100 tok/s` endpoint and cannot reach `125+`
    at the current step cost. Treat MTP3 branch work as a narrow `~100 tok/s`
    infrastructure lane, not the main `125+` route.
38. Native prefix-base exact-state rescreen after the extra state-column fix:
    `notes/2026-07-06-native-prefix-exact-state-rescreen-no-win.md`.
    The old July 5 exact-native/prefill replay flags were stale because
    prefix-base later gained the needed extra state column. Rescreening them on
    four GPUs closed the lane anyway: offset/writeout exact-native rows landed
    at `~4.6-4.9 tok/s` and failed quality, prefill-column replay collapsed
    acceptance to zero, and replaypartial passed local repeat16 but only
    reached `6.323 tok/s`. The durable lesson is that same-forward exact
    target-tail GDN state is impossible with current data flow because the
    verifier-sampled replacement/bonus token has no projected GDN input row yet.
    Do not continue native serial/prefill flag sweeps; move to a real
    graph-safe state transaction/tape, target-tail projection/branch-regenerate
    support, or a stronger drafter.

## Folder Map

- `configs/`: reusable env files.
- `scripts/`: downloader, launcher, smoke, and future benchmark helpers.
- `notes/`: chronological run notes.
- `patches/`: patch snapshots for successful and failed source attempts.
- `results/`: compact experiment summaries.
- `quality/`: quality gates and prompt suites as they mature.
- `localmaxxing/`: queued payloads and response copies after valid records.

## Current Research Frontier

The active headline family is now
`webhie/Qwen3.6-27B-int4-AutoRound` with the current promote-source MTP3/cg8
recipe plus runtime INT8 target LM-head BF16 scales, runtime INT4 draft LM-head
BF16 scales, and ReplaySSM exact GDN state handling:
`68.23626314761921 tok/s` median generated-token throughput for tokens 1-100
after TTFT on the strict fresh Qwen realistic suite, with `cached_tokens=0` on
every request and repeat64 quality passing. This is a small same-recipe confirm
over the prior approved `67.51904968102535 tok/s` row, not a new mechanism.
The prior `65.27648650325429 tok/s` row remains the older BF16-scale comparison
baseline; the current promoted packet is
`../../results/qwen36-27b-autoround-int4-b70/webhie-int8lmhead-bf16scale-draftint4-replayssm-current-confirm-20260706.json`.

Older reference points remain useful for attribution: plain MTP3/cg8 was about
`47.6-48.5 tok/s`, and promote-source/no-accepted-postprocess lifted the lane
to `53.5-54.9 tok/s` before the webhie variant and INT8 LM-head work. A fast
invalid flag, `VLLM_XPU_GDN_NONSPEC_POSTPROCESS_FULL_ACCEPT=0`, reached
`51.273 tok/s` on the strict suite and `74.877 tok/s` synthetically, but failed
1024-token needle recall. Tracing explains the lift: the valid path copies
large GDN/Mamba state from the accepted speculative slot back to the running
slot after verification.

Current trace summary:
`data/qwen36-27b-autoround-int4-b70-baselines/mamba-copy-trace-summary-mtp3-cg8-p512o128-20260703T042542Z.json`.

Prompt-processing / long-context service work is tracked separately from the
short-decode record. The current service ladder lives in
`notes/2026-07-04-long-context-ladder-baseline.md`, with suite
`../../repro/qwen36-27b-autoround-int4-b70/long-context-suite-v1.json` and
runner `scripts/run-long-context-ladder.sh`. The latest 32K-capability anchor
uses the same webhie/BF16-scale INT8-LM-head MTP3/cg8 recipe at
`MAX_MODEL_LEN=32768` and passes exact JSON retrieval through `17706` actual
prompt tokens with `cached_tokens=0`, TTFT median `22.443s`, approximate
prefill median `224.67 tok/s`, and after-TTFT short-output median
`60.19 tok/s`. This is a service-lane baseline, not a LocalMaxxing headline
decode row. For production-visible OpenAI content deltas, use the validated
no-parser service variant (`QWEN36_27B_REASONING_PARSER=`), which passed the
same 32K exact-retrieval gate with `reasoning_delta_count=0`.
The MBT follow-up is `notes/2026-07-04-long-context-mbt-screen.md`: same-window
screening kept `MAX_NUM_BATCHED_TOKENS=4096` for the 32K no-parser service lane;
MBT2048 passed but was slower, and MBT8192 stalled without a complete gate
artifact.

The current valid env-only win appears to preserve the accepted-state transition
by reading from the accepted speculative slot as the running source, then
disabling the now-redundant accepted-state postprocess copy. Later timing first
moved attention toward full LM-head/logits, but the 2026-07-05 refresh corrected
that for the current record family: INT8 LM-head/local-argmax is already small,
and the active frontier is target forward plus recurrent MTP draft forward.
Bad candidates already closed: blind copy skips, skipping
full-accept state, changing the Triton memcpy block size, exact argmax plumbing
that still computes full logits, draft local-argmax plumbing that still
computes full logits, FP8 LM-head (quality fail), INT8 MTP k2/k4/k5,
INT8 cg4/cg16/cg32, draft-only INT8 LM-head, output-buffer reuse, bonus-token
argmax fast-path, chunked INT8 top-1 argmax-only verification, compressed/full
EAGLE3 (device-loss or too slow), DFlash (no-win locally), and simple draft
top-k reranking. The latest draft-INT4 fast-path screens are also closed:
keep-scheduled-spec-row routing, graph-off, graph-off/no-async, cg4, and normal
align/restore all kept the same repeat64 failure (`55/64` expected
`blue, green, red, yellow`, `9/64` truncated `blue, green, red`) despite
strict fresh `cached_tokens=0` speed rows at `68-72 tok/s`; see
`notes/2026-07-05-draft-int4-specrows-and-graph-bisect-no-win.md`.
Serial GDN is closed as well: native-on `SERIAL_SPEC_*` rows were fast but
still repeat-invalid and likely bypassed the Python serial path, while
native-off serial/fallback actually exercised the path and fell to
`~9.7-12.3 tok/s`; see
`notes/2026-07-05-draft-int4-serial-gdn-nativeoff-no-win.md`.
The next GDN-state implementation lane should be a fixed-shape exact
accepted-prefix tape / GPU-side commit, not more serial source/offset sweeps.
The 2026-07-06 branch/regenerate feasibility model further narrows the MTP3
branch lane: even a perfect legal MTP3 first-reject correction and regenerated
suffix reaches only `~101.8 tok/s` at zero overhead and cannot reach `125+`
without reducing verifier-step cost or increasing speculative depth. See
`notes/2026-07-06-branch-regenerate-feasibility-envelope.md`.
The executable contract is `../../scripts/check-gdn-spec-recurrent-exact.py`;
as of 2026-07-06 it validates exact recurrent prefix state,
accepted-prefix SSM/conv commit equality on XPU for k=3/4/5, and the
endpoint row-to-draft-prefix mapping for full reject, partial reject, full
accept with bonus, shifted full accept, draft-only, and suppressed
bonus/replacement tails. See `notes/2026-07-05-accepted-prefix-tape-contract.md`
and `notes/2026-07-06-gdn-endpoint-row-contract-extension.md`.
The native packed spec prefix contract is also now checked directly by
`../../scripts/check-gdn-native-spec-prefix.py`; see
`notes/2026-07-05-native-spec-prefix-contract-check.md`. It confirms the native
op publishes column `j` as the state after packed row `j` and selects source
column `num_accepted_tokens - 1`. That closes the simple off-by-one/source
column explanation for the invalid fast draft-INT4 rows and points future work
at an exact ReplaySSM/tape commit transaction.
A metadata-only attempt to feed a separate GDN accepted-prefix count buffer
into attention metadata is closed no-win:
`notes/2026-07-06-gdn-accepted-prefix-counts-no-win.md` and
`../../patches/qwen36-27b-autoround-int4-b70/vllm-qwen27-gdn-accepted-prefix-counts-no-win-20260706.patch`.
It passed GDN contracts and repeat64 quality, but the strict candidate was not
promotable and slowed to `37.451 tok/s`; do not confuse this with the deeper
fixed-shape GDN transaction still on the backlog.
A first commit-overhead reduction for that direction was tested:
`VLLM_XPU_GDN_REPLAYSSM_COMMIT_IN_FORWARD=1` plus skipping the redundant
post-verify commit when no restore correction is active. It passed strict fresh
and repeat64 quality at `63.854 tok/s`, improving over prior ReplaySSM rows but
still below the `65.276 tok/s` record. Preserve it as no-promote evidence:
`notes/2026-07-05-replayssm-commit-in-forward-skippost-no-promote.md` and
`../../patches/qwen36-27b-autoround-int4-b70/vllm-qwen27-replayssm-commit-in-forward-skippost-no-promote-20260705.patch`.
The corrected Ex0bit EAGLE3 nested-aux-layer patch is preserved as a
compatibility artifact, but the retest still showed prompt-dependent
acceptance collapse and unusable endpoint throughput, so EAGLE3 remains closed
for this local vLLM/XPU + webhie/Intel AutoRound target unless the drafter
runtime, accepted-token bookkeeping, or target/draft pairing changes
materially.
Draft-side `mtp.fc` runtime INT8 is closed too: the default-off patch quantized
only the BF16 Qwen3.5 MTP `mtp.fc` layer and kept target verification exact, but
same-window strict fresh screening showed the completed candidate slower
(`66.777 tok/s`) than controls (`67.954` and `67.994 tok/s`), while another
candidate hit TorchDynamo fake-tensor unsupported-op handling for the custom
INT8 GEMM inside compiled MTP. See
`notes/2026-07-06-mtp-fc-int8-no-win.md` and
`../../patches/qwen36-27b-autoround-int4-b70/vllm-qwen27-mtp-fc-int8-no-win-20260706.patch`.
GDN gated-RMSNorm `rstd` skip is another closed model-body micro-optimization:
the patch skipped an ignored Triton `rstd` allocation/writeback behind
`VLLM_XPU_RMSNORM_SKIP_RSTD=1`, but strict fresh candidates (`66.329` and
`66.595 tok/s`) lost to controls (`67.716` and `67.910 tok/s`). See
`notes/2026-07-06-rmsnorm-skip-rstd-no-win.md` and
`../../patches/qwen36-27b-autoround-int4-b70/vllm-qwen27-rmsnorm-skip-rstd-no-win-20260706.patch`.
Current-recipe deeper MTP is closed. MTP4/MTP5 require
`VLLM_XPU_GDN_REPLAYSSM_SPEC_CACHE_LEN>=16` because the ring length must
satisfy `ring_len >= 2 * max_spec_len`; with cache8 they fail readiness
(`got 8 < 10` / `got 8 < 12`). A follow-up native cache16/spec6 dispatch patch
compiled and passed direct native-vs-fallback parity for BF16/FP16/FP32, but
endpoint screening still lost: same-window MTP3/cache8 control was
`67.816 tok/s`, MTP3/cache16 `65.410`, MTP4/cache16/cg16 `61.637`, and
MTP5/cache16/cg16 `58.140`. The wider ReplaySSM templates also emitted heavy
AOT spill warnings. See
`notes/2026-07-06-draftint4-depth-cachelen-no-win.md`,
`notes/2026-07-06-replayssm-cache16-native-s6-no-win.md`, and
`../../patches/qwen36-27b-autoround-int4-b70/vllm-qwen27-replayssm-cache16-spec6-no-win-20260706.patch`.
Do not repeat config-only or simple dispatch-widening MTP4/MTP5 sweeps on this
recipe.
The latest DFlash revisit is also closed:
`notes/2026-07-06-dflash-swa-pr40898-repair-no-record.md`. After reviewing
upstream vLLM PR #40898, a local DFlash SWA/full-KV repair was implemented and
syntax-checked. It fixed the old catastrophic mixed-SWA acceptance symptom and
produced strict fresh diagnostic rows, but remained far below the `67.519 tok/s`
record: k2 `49.087`, k4 `54.836`, k8 `50.918` tok/s, all quality-skipped and
not promotable. Preserve the patch for future upstream/DFlash comparison, but
do not repeat k/capture-size DFlash sweeps for this draft.
The latest source-drift repair is
`notes/2026-07-06-mixed-draft-kv-metadata-guard-and-draft-int4-group-screen.md`.
The external `Qwen/Qwen3.5-0.8B` draft-model experiment accidentally enabled
mixed draft-KV metadata for normal intrinsic MTP and dropped the record recipe
to `~60-61 tok/s`. Active source now keeps mixed draft-KV metadata DFlash-only
by default, with `VLLM_XPU_SPEC_DECODE_MIXED_DRAFT_KV_METADATA=1` as an
explicit opt-in for future external-draft work. A quality-backed confirm
restored `67.338 tok/s`. Same-window screens closed draft INT4 group64,
group256, and fp32-scale as no-win versus group128/BF16 scales.

## Current Entry Points

```bash
cd /home/steve/llm-optimizations

experiments/qwen36-27b-autoround-int4-b70/scripts/download-model.sh

GPU_INDEX=0 PORT=19410 MAX_MODEL_LEN=2048 \
  experiments/qwen36-27b-autoround-int4-b70/scripts/serve-vllm.sh

BASE_URL=http://127.0.0.1:19410/v1 MODEL=qwen36-27b-int4-autoround \
  experiments/qwen36-27b-autoround-int4-b70/scripts/smoke-openai.sh
```

## Local Storage

The pinned Intel snapshot currently lives on the internal NVMe HF cache:

```text
/mnt/fast-ai/llm-cache/hf/hub/models--Intel--Qwen3.6-27B-int4-AutoRound/snapshots/abc86de19eb1ebbf6a7df4582341325c22ddcb7d
```

An external 4 TB USB drive is mounted at `/mnt/usb-models` for overflow model
variants and archived artifacts. Keep active hot-path benchmarks on the
internal NVMe when practical; use `/mnt/usb-models/llm-cache/hf` or
`/mnt/usb-models/models` for additional variants if internal space becomes a
constraint. Do not commit model weights or generated cache contents.

## External References

- Hugging Face:
  https://huggingface.co/Intel/Qwen3.6-27B-int4-AutoRound
- Base model: https://huggingface.co/Qwen/Qwen3.6-27B
- AutoRound: https://github.com/intel/auto-round
- vLLM Qwen3.6 recipe: https://recipes.vllm.ai/Qwen/Qwen3.6-27B
- vLLM Intel quant docs:
  https://docs.vllm.ai/en/stable/features/quantization/inc/
- LocalMaxxing model index: https://www.localmaxxing.com/en/models
- Local vLLM source: `/home/steve/src/vllm`
