# K160 EAGLE signal milestone: capture passed, training blocked

Date: 2026-07-20  
Verdict: **STOP before the acceptance gate**  
Recommendation: **do not fund the 10M-20M capture/train expansion yet**

## Numbers first

- Feature smoke: PASS, 16/16 K160 target IDs aligned, 15 adjacency checks,
  zero failures, and all four TP ranks tensor-equal under the validator.
- Train corpus: PASS, exactly 1,000,000 K160 completion tokens in 2,272
  trajectory shards; 450,000 prose, 150,000 code, 150,000 math, 150,000
  extraction, and 100,000 low-locality tokens.
- DEV corpus: PASS, exactly 50,000 tokens in 143 disjoint trajectory shards
  with the same 45/15/15/15/10 category proportions.
- Train alignment: 997,728 adjacency checks, zero failures; all 1,000,000
  captured next-token IDs equal the saved K160 greedy continuation IDs.
- DEV alignment: 49,857 adjacency checks, zero failures; all 50,000 captured
  next-token IDs equal the saved K160 greedy continuation IDs.
- XPU/BF16/DDP smoke: FAIL, 0/100 optimizer steps. Four ranks initialized XCCL
  and allocated about 3.9 GiB/card, then remained in the first recursive
  teacher-forced forward for more than 600 seconds. SIGINT did not unwind the
  workers in 30 seconds and torchrun used SIGKILL.
- CPU compatibility probe: 1/1 step, loss 74.59212494, CE 72.93784332,
  feature regularization 0.11685995, gradient norm 5520.34033, and
  63.09829140 seconds for one microbatch-1 update on 16 CPU threads.
- Milestone head training: not run. The unchanged recipe requires 500 updates
  and initially 8K anchors/update. The measured local CPU fallback cannot run
  that recipe in a viable milestone window, and no off-host H100/A100 trainer
  is available in this workspace.
- DEV conditional acceptance P1-P7 and overall: not evaluated because no
  milestone-trained checkpoint exists.

## Gate table

| Metric | Required | Measured | Status |
|---|---:|---:|---|
| P1 conditional acceptance | >=76% | not evaluated | BLOCKED |
| Mean conditional P2-P7 | >75% | not evaluated | BLOCKED |
| Overall acceptance | >=40% | not evaluated | BLOCKED |

The gate verdict is **STOP / not evaluable**. This is a pre-gate training
blocker, not a threshold failure and not evidence that the architecture passes
or fails the signal hypothesis.

## Exact capture path and smoke

The guarded capture patch is default-off unless
`VLLM_XPU_EAGLE_TRAINING_CAPTURE_DIR` is set. The model-runner installer is
called only in that guarded branch. Unit tests cover default-off behavior,
aligned tensor/shard persistence, stable replay-ID canonicalization, and
rejection of non-replay requests: 4/4 passed.

The final 16-token V11 smoke used boundaries `[4,22,43]`,
`post_mhc_mean_stream`, exact greedy teacher forcing, one active generation,
and speculation disabled. The stable request key was identical on ranks 0-3;
the validator compared rank tensors and passed. V10 is preserved as a negative
result because vLLM decorated the internal engine request ID; the fixed path
hashes the canonical external `eaglereplay-...` transaction prefix instead.

- V11 validation:
  `/media/steve/CorsairExternal/llm-optimization-artifacts/deepseek-v4-eagle-signal-20260719T210100Z/smoke/capture-v11-validation.json`
- capture source commit: `ca0648d600c6c47cf163e96eb66b3a365d104987`
- base vLLM: `264c7f2f7df21ddeeab32ecca0353133344f1ac9`
- XPU kernels: `31315673737d95da0f79179c8f755260ef02c1d6`
- oneCCL: `48fda4f0e074db005596d6899d5227d3f0316c12`
- K160 model revision: `7c360e1cd4a5168099dbc54d16d929bf6df04990`

## Corpus and checksum ledger

Artifact root:

`/media/steve/CorsairExternal/llm-optimization-artifacts/deepseek-v4-eagle-signal-20260719T210100Z`

Train:

- trajectory manifest:
  `capture-v1/train-trajectories-clean-v2.jsonl`, SHA-256
  `b3a408b1bcab107efc593a64fb6dc9184f9fb094ef4e24d822444eb73dfeb57c`;
- replay manifest: `capture-v1/train-replay-requests.jsonl`, SHA-256
  `89170d3383daa0712b73e286abf86b9b5205845955b348216a51499aebcddc44`;
- feature directory: `capture-v1/features-v1/eagletrain/rank-000`,
  32,792,000,012 bytes;
- per-shard checksum ledger: `capture-v1/train-feature-sha256-manifest.txt`,
  2,272 entries, SHA-256
  `e6b7965346a937f3e36621ce9b253b34c1b12da41c70af095b5320489a453260`;
- validation: `capture-v1/train-capture-validation.json`, SHA-256
  `2c54fd94ec49b56c59fd55479edf42c8bcf026b6fcd791e9523176940b685555`;
- used prompt-set SHA-256:
  `01e1617bf77d5aec5fbc9e3d0417f437ce5a8695ab7305efd6b90135b95563fb`.

DEV:

- trajectory manifest: `capture-v1/dev-trajectories.jsonl`, SHA-256
  `0aa63bcd47a93d3b084d5e01092707ebd9526da63756dbb643b7ee0795b8f4a6`;
- replay manifest: `capture-v1/dev-replay-requests.jsonl`, SHA-256
  `474745e5ab4eade29830cd5c73e34d46ac421055c2f7a3c0ec24878168551962`;
- feature directory: `capture-v1/features-v1/eagledev/rank-000`,
  1,639,651,458 bytes;
- per-shard checksum ledger: `capture-v1/dev-feature-sha256-manifest.txt`,
  143 entries, SHA-256
  `1fca76f5b5161865dda434ca1db35c9d859995e6c2243cee83ceb5189fba3139`;
- validation: `capture-v1/dev-capture-validation.json`, SHA-256
  `5299d46a1f095aed5a864ae53cf9a309519e1e7714c09d68cff8d57ff909f69e`;
- used prompt-set SHA-256:
  `026c35b992fca1abf2bec9f2380e99040198804d31c546934ad6db646cab61a0`.

The validator proved reciprocal train/DEV prompt-set disjointness. Generation
and replay were one-active-request only. The final category counts are exact,
not estimates.

## Capture runtime negative results

The feature transactions are valid, but bulk replay exposed serious K160/XPU
operational instability. Nineteen train replay deadlocks were recovered at
exact matched replay/shard cursors. Fifteen occurred under the committed
supervisor and are preserved in restart logs; four occurred during the manual
bring-up. Two supervised train startups, one DEV startup, and one supervisor
startup-race run failed before replay. Eager execution avoided some early
piecewise failures but later developed initialization hangs; piecewise mode
completed the final train and DEV segments. No trajectory was dropped,
modified, or duplicated.

Supervisor and all per-cycle server/replay logs are under:

- `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/k160-eagle-train-feature-capture-supervised-20260720T1020Z-restart*`
- `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/k160-eagle-dev-feature-capture-supervised-20260720T1300Z-restart*`

## Intended head and training blocker

The unchanged milestone head is a one-layer dense GQA decoder, width 2048,
16 query heads, 4 KV heads, head dimension 128, SwiGLU width 5504, context 128,
recursive M=7, full frozen K160 embedding and LM head, and 94,654,464 trainable
parameters. The loss is teacher-forced conditional seven-position CE with the
normalized `[1.0,1.0,1.1,1.25,1.4,1.6,1.8]` depth weights plus the specified
SmoothL1/cosine feature regularizer.

The XPU smoke produced no loss curve because it never completed step 1. The
CPU probe produced the single point above; it is a compatibility checkpoint,
not a milestone-trained head and must not be evaluated or promoted.

- blocker record: `training/training-blocker.json`, SHA-256
  `f72f0b803fe7d12d39875cf1e02ba9043ab36721747ddb9b73c84a608d7c4cb3`;
- CPU probe checkpoint: `training/cpu-compat-1/head-final.pt`, SHA-256
  `e01678fffb56adb34d2d433e1ca6c21b1b77e5e98d2f14d407069dd97e8888db`;
- CPU probe metrics: `training/cpu-compat-1/training-metrics.jsonl`, SHA-256
  `11005b669c398320f2db68b4b569c87d7d520b81f298869691079a2fe175a29d`.

The probe also exposed a JSON handoff bug after checkpoint save; commit
`f9fbce594426c7e811bfb64a6a8b26ed7059901e` excludes the argparse callback
from `training-config.json` and preserves the valid checkpoint.

## Source and repository commits

- capture patch source: `ca0648d600c6c47cf163e96eb66b3a365d104987`;
- stable replay lineage: `63155de09dffbc33f5a6269cd4859af26382bf66`;
- replay supervisor: `ceb1624a0aa659a2ee629a941a111088fb02cef3`;
- supervisor teardown fix: `997ec5d5b45e255f272e5b5e5a8dbd431e7a0a75`;
- slow-readiness guard: `51bd827b94e6b59ed452aeb7b15cb6bc712b7a33`;
- config serialization fix: `f9fbce594426c7e811bfb64a6a8b26ed7059901e`;
- recursive trainer: `20cb7f373`;
- training provenance hardening: `3fa3b517c`.

Patch artifacts:

- `patches/deepseek-v4-flash-reap-xpu-b70/0001-xpu-add-guarded-K160-EAGLE-training-capture.patch`,
  SHA-256 `a2dd4c8afd3acd1b2d77c534b0efad322557bbc0d62aa15ba6805945edab986f`;
- `patches/deepseek-v4-flash-reap-xpu-b70/0002-xpu-stabilize-EAGLE-replay-request-lineage.patch`,
  SHA-256 `693dfeb311f5ffcae25b9cbf4dff65b99e92b3806ad3a38199866950c81d98f0`.

## Recommendation

Do not fund the 10M-20M capture or serving integration. The next bounded spend
should be off-host head training on 2-4 H100/A100-class GPUs using these frozen,
checksummed K160 features and the unchanged trainer/recipe, followed by the
same non-frozen DEV gate. Only a checkpoint that passes P1 >=76%, mean
conditional P2-P7 >75%, and overall acceptance >=40% should justify the full
capture. Do not reveal held-out packs before that decision.

No frozen held-out pack was accessed in this run. No endpoint integration or
LocalMaxxing submission was made. All K160 services and training processes were
stopped; all four B70 cards were free at handoff.
