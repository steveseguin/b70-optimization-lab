# Experiment directory

This index covers all 37 immediate experiment directories, reviewed 2026-10-10.
Each entry points to the research record and a useful conclusion or limit.
Exact measurements, patch identities and qualification gates belong in those
sources. Old launch commands and sections called “current” describe their date;
[CURRENT.md](../CURRENT.md) owns active work and protected paths.

Use the [model effort index](../docs/model-effort-index.md) to find maintained
result packets and recipes, and the [research workflow playbook](../docs/research-workflow-playbook.md)
for lessons that transfer between models. Source history, failed patches,
negative results and original evidence remain preserved at their existing paths.
An index entry does not promote an experiment or authorize a launch.

## Model and runtime lanes

- **[deepseek-v4-flash-autoround-vllm](deepseek-v4-flash-autoround-vllm/README.md)** —
  Initial AutoRound bring-up, fit and runtime-support investigation.
  Its oversized artifact is separate from the later K160 derivative below.
- **[deepseek-v4-flash-reap-xpu-b70](deepseek-v4-flash-reap-xpu-b70/README.md)** —
  K160 derivative, target-verified drafting and full-model kernel integration.
  The [closeout](deepseek-v4-flash-reap-xpu-b70/notes/2026-07-21-deepseek-v4-flash-frontier-closeout.md)
  retains the frontier and rejected components; this is not the unmodified official model.
- **[gemma4-12b-int4-autoround-vllm](gemma4-12b-int4-autoround-vllm/README.md)** —
  Model-loader backport, image/text smoke tests and concurrent serving profiles.
  Retains resource failures and context/concurrency tradeoffs; old service state is historical.
- **[gemma4-26b-a4b-q8-b70](gemma4-26b-a4b-q8-b70/README.md)** —
  Q8 speculative decoding, kernels and per-card configuration sweeps.
  Use the [result packet](../results/gemma4-26b-a4b-q8-b70/README.md) for accepted identities; every sweep needs its own quality scope.
- **[laguna-s-2.1-xpu-b70](laguna-s-2.1-xpu-b70/RESUME.md)** —
  INT4 target with BF16 KV, DFlash and graph/kernel optimization.
  The handoff separates qualified records from long-context diagnostics with incomplete or differing outputs.
- **[laguna-s-2.1-fp8-kv-xpu-b70](laguna-s-2.1-fp8-kv-xpu-b70/README.md)** —
  Separate calibrated FP8-KV experiment with its own target-only teacher.
  Page-size component tests and collective initialization failures do not qualify a new endpoint result.
- **[ltx25-b70](ltx25-b70/README.md)** —
  Video pipeline scheduling, graph capture, output identity and continuation studies.
  The [handoff](ltx25-b70/RESUME.md) preserves reference changes; use the [recipe](../repro/ltx25-continuation-stream-b70-145f-20261010/README.md) for its exact timing and delivery limits.
- **[minicpm5-2b-b70](minicpm5-2b-b70/README.md)** —
  Native BF16 baseline and instruction-following qualification.
  Tested presets failed the registered gates; successful loading is not a qualified baseline.
- **[minimax-h3-b70](minimax-h3-b70/README.md)** —
  Video scheduling, process-based parallelism and repeatable decode/output files.
  Exactness is against the owner-selected fitted denoiser; the [recipe](../repro/minimax-h3-pruned-bf16-tp2-b70-20261004/README.md) records provenance and rebuild gaps.
- **[minimax-m27-reap-autoround-vllm](minimax-m27-reap-autoround-vllm/README.md)** —
  Smaller REAP/AutoRound checkpoint intake and fit comparison with MiniMax M2.7.
  A favorable storage estimate does not establish quality, repeatability or a promoted result.
- **[muse-glimmer-30b-b70](muse-glimmer-30b-b70/README.md)** —
  BF16 and compressed-target studies, DFlash and weight-only kernels.
  The retained Q8/WOQ result is not a BF16, lossless or universally token-exact claim.
- **[ornith-15-b70](ornith-15-b70/README.md)** —
  Dense and MoE decode kernels, assisted generation and matched comparisons.
  Preserves exact-but-neutral fusions and regressions: isolated operator gains may vanish in the full stack.
- **[own-xpu-runtime](own-xpu-runtime/README.md)** —
  The lab's model-specific Intel Xe runtime design, source boundaries and staged qualification.
  CPU identity/parser/oracle preparation is distinct from native execution and model qualification.
- **[qwen27-dflash-sycl-b70](qwen27-dflash-sycl-b70/README.md)** —
  Single-card GGUF/DFlash kernel and verifier experiments.
  The [closure and transfer note](../notes/2026-07-13-qwen27-dflash-sycl-closure.md) preserves unmet goals and unfinished, unvalidated artifacts.
- **[qwen35-4b-b70](qwen35-4b-b70/HANDOFF.md)** —
  W4A16/MTP, batch-shape arithmetic and request-lifecycle repairs.
  Qualified single-request behavior does not qualify concurrent speculation; FP8 repeat failures remain separate.
- **[qwen35-9b-b70](qwen35-9b-b70/)** —
  W4A16 and FP8 identity, concurrency and draft-head studies.
  Start with the [W4A16 recipe](../repro/qwen35-9b-w4a16-b70/README.md) and [shortlist result](qwen35-9b-b70/notes/2026-09-12-the-draft-head-only-needs-a-shortlist.md); the target still verifies proposed tokens.
- **[qwen36-27b-autoround-int4-b70](qwen36-27b-autoround-int4-b70/README.md)** —
  INT4 vLLM/MTP, collective repair and graph/kernel campaign history.
  The retained record and later nonpromotable matched-source recovery are different evidence packets.
- **[qwen36-27b-mtp-gguf-q4-b70](qwen36-27b-mtp-gguf-q4-b70/README.md)** —
  Separate llama.cpp/SYCL Q4 target with intrinsic MTP and cache-off sweeps.
  Preserves harness fixes and configuration no-wins; it is not the AutoRound model/runtime.
- **[qwen36-27b-q8-gguf-b70](qwen36-27b-q8-gguf-b70/README.md)** —
  Q8 target-only and integrated-MTP kernels, context and replica studies.
  Separates qualified single-slot results from concurrent fairness, fit and output-identity limits.
- **[qwen36-35b-quark-int8-b70](qwen36-35b-quark-int8-b70/)** —
  Preserves a [detached dirty kernel-source snapshot](qwen36-35b-quark-int8-b70/notes/2026-07-04-vllm-xpu-kernels-detached-dirty-snapshot.md)
  related to GDN/MoE work. Rescuing a patch does not qualify it; the [result packet](../results/qwen36-35b-quark-int8-b70/README.md) owns the broader lane.
- **[qwen38-27b-b70](qwen38-27b-b70/DO-NOT-REPEAT.md)** —
  FP8, INT4 and GGUF research, exactness diagnostics and later context studies.
  Start with the negative-result index and [model effort map](../docs/model-effort-index.md); keep model, arithmetic and workload identities separate.
- **[qwen38-flash-next-fp8-b70](qwen38-flash-next-fp8-b70/)** —
  Official FP8 placement, graph and exact-GDN studies plus later loading/exit-fault investigation.
  The [result packet](../results/qwen38-flash-next-fp8-b70/README.md) and [reopen packet](qwen38-flash-next-fp8-b70/reopen-20261008/README.md) have different qualification boundaries.
- **[qwen38-flash-next-ud-iq3xxs-b70](qwen38-flash-next-ud-iq3xxs-b70/README.md)** —
  Separate Unsloth compressed model with authenticated weights and CPU reference preparation.
  Its own exact-output oracle is required; it inherits neither FP8 performance nor FP8 qualification.

## Kernel and runtime mechanism studies

- **[minimax_ar_fused_rms_xpu](minimax_ar_fused_rms_xpu/)** —
  All-reduce, residual-add and RMSNorm fusion prototypes.
  [Repeatability rejection](../notes/2026-05-19-minimax-ar-fused-rms-c10d-repeatability-negative.md) and [post-reduce failure](../notes/2026-05-19-minimax-attn-post-reduce-rms-xpu-quality-fail.md) show why correct microchecks were insufficient.
- **[minimax_moe_tuned_configs](minimax_moe_tuned_configs/README.md)** —
  Isolated MoE tile/configuration screens and a rejected older alias.
  Missing decode keys select the nearest larger key; they do not fall back to defaults.
- **[minimax_pair_argmax_xpu](minimax_pair_argmax_xpu/README.md)** —
  Gather-and-reduce helper for distributed greedy token selection.
  Avoids a problematic packed MAX reduction; standalone and full-model promotion gates remain explicit.
- **[minimax_qk_rms_xpu](minimax_qk_rms_xpu/README.md)** —
  Standalone Q/K normalization and RoPE extension, preserving the release kernel wheel.
  Numerically valid helpers regressed the measured model path; compiler/runtime compatibility also matters.
- **[minimax_qk_rms_xpu_ipc](minimax_qk_rms_xpu_ipc/README.md)** —
  Peer-memory mailboxes and cross-process variance reduction.
  Standalone success did not overcome integration latency; sequence-slot reuse can hang an unsafe test.
- **[minimax_xpu_kv_offload](minimax_xpu_kv_offload/README.md)** —
  Host-RAM KV storage, reload and attention-staging research.
  Session caching did not remove the active GPU working-set limit; compressed-KV variants remain separately scoped.
- **[qwen27_fused_postattn_rms_w4a16](qwen27_fused_postattn_rms_w4a16/README.md)** —
  Graph-compatible normalization plus INT4 projection prototype.
  The apparent gain used an unfair eager baseline; the production-like comparison was slower.
- **[qwen27_graphsafe_flash_attention](qwen27_graphsafe_flash_attention/README.md)** —
  Handler-owned scratch storage enabled captured attention without changing kernel math.
  Retains replay tests and integration evidence; the short-context decode fallback scales poorly at longer context.
- **[xpu_level_zero_peer_probe](xpu_level_zero_peer_probe/README.md)** —
  Small device-peer and cross-process memory-sharing probes.
  Functional remote-write checks inform larger designs; they are not model correctness or speed evidence.

## Cross-model research and lab tools

- **[lab-navigator-20261007](lab-navigator-20261007/README.md)** —
  Commit-pinned source search and evidence packs with original passages and hashes.
  Missed passages require fuller reading; retrieval and source integrity do not prove answer completeness.
- **[local-coding-worker](local-coding-worker/README.md)** —
  Real coding-task trials with independent acceptance checks and preserved failed attempts.
  Familiar-task improvements did not establish success on new tasks or general worker reliability.
- **[model-intake-resume-20261007](model-intake-resume-20261007/)** —
  Downloader repair for preallocated partial files with an aria2 control sidecar.
  [Offline tests](model-intake-resume-20261007/validation.json) and the later [application receipt](model-intake-resume-20261007/application.json) preserve the fix; size alone never replaces hash verification.
- **[project-decision-recall-20261007](project-decision-recall-20261007/RESULTS.md)** —
  Frozen-source comparison of ordinary search/read and complete-source delivery.
  A cited qualification was still omitted from an answer; the small diagnostic supports explicit completeness review.
- **[rapid-model-snapshots-b70](rapid-model-snapshots-b70/README.md)** —
  Reproducible first-pass model baselines and a shared cold-response gate.
  Diagnostic screens and promising intake candidates do not become headline results without that gate.
