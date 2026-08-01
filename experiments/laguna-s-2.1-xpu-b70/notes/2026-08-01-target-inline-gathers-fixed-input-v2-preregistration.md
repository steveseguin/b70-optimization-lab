# Laguna M12 target inline gathers with fixed inputs v2

Date: 2026-08-01 America/Toronto

Status: **closed negative at the preregistered non-scored model gate; no
endpoint score was run or authorized.**

## Evidence and distinct mechanism

The protected exact BF16-KV record remains `125.4619731637751 tok/s`
conventionally with target `146/145`, draft `14/13`, width 12 / DFlash 11,
and 13/13 canonical-q1 exactness.

The old inline-gather branch reduced target topology to `50/49`, but it only
preallocated gather outputs. Each captured XCCL call consumed a model-local
`local` tensor whose address, lifetime, ownership, and non-aliasing were not
retained or audited. Its CPU test mocked the collective as an immediate copy,
and the failed smoke did not preserve request 0 before a combined assertion.
That unchanged branch remains rejected.

The new M12 composition component separately proved that 96 legacy XCCL
gathers with captured producers and 48 interleaved eager consumers can replay
raw-exactly. The remaining model-specific gap is the ephemeral input contract.

V2 therefore adds one fixed `[1,12,3072]` BF16 input buffer per existing
runner-owned gather slot. While the surrounding graph is recording it:

1. copies the model-local input into that slot;
2. performs the unchanged TP4 `all_gather_into_tensor` from the fixed input to
   the existing fixed output;
3. leaves the literal rank-ordered BF16 sum and all model arithmetic unchanged;
4. asserts input/output pointer, shape, stride, dtype, device, contiguity,
   non-aliasing, slot order, and count; and
5. leaves selector-off behavior unchanged.

This adds a real dataflow edge and owned input lifetime. It is not a rerun of
the output-only patch and does not use the stale branch wholesale; it must be
rebased minimally onto protected vLLM `1a7f61fef` so the M12 Q/K-RoPE and
shared-elementwise record changes remain present.

## Gates

1. Work in a new vLLM worktree. Focused tests must prove selector-off
   inertness, 96 distinct fixed inputs and outputs, pointer stability,
   non-aliasing, copy-before-gather order, replay counters, exact `50/49`
   target topology, and failure on any contract drift.
2. Inspect the applied files and diff directly. Pass focused tests, Ruff,
   `compileall`, and whitespace checks before model load.
3. Run one non-scored changing-request smoke only. Persist the complete raw
   HTTP response before checking it. Require exact canonical-q1 token prefix,
   `cached_tokens=0`, normal non-flat DFlash acceptance, target `50/49` and
   draft `14/13` on all four ranks, fixed-input activation evidence on all
   ranks, and clean pre/post idleness.
4. Any token/cache mismatch, topology drift, pointer drift, collective error,
   hang, device error, or dirty teardown closes V2. Do not retry unchanged
   code, reset, reload, unbind, FLR, clear shared memory, or reboot.
5. A passed diagnostic authorizes a separately preregistered cold 13-prompt
   score. It is not itself throughput evidence. The first future valid score
   must be reported whether it wins or loses.

No weight, target/draft/KV precision, width/depth, verification, sampler,
teacher, prompt, cache, metric, acceptance rule, or scoring-window change is
authorized.

## Result

V2 was implemented in the dedicated vLLM worktree at `68a4a5f3e` on top of
protected vLLM `1a7f61fef`. The selector-off path allocates no new buffers. The
selector-on path owns 96 distinct fixed `[1,12,3072]` BF16 inputs and 96
distinct fixed `[4,12,3072]` BF16 outputs per rank, copies each model-local
input into its fixed slot immediately before the unchanged gather, and rejects
shape, pointer, aliasing, order, or count drift. Focused static and unit gates
passed before model load.

The one authorized smoke ran at:

`/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-target-inline-gathers-fixed-input-v2-smoke-20260801T161655Z`

It proved that all four ranks activated the 96 fixed input/output slots and
that capture and replay both had the intended target `50/49` and draft `14/13`
topologies. Request 0 returned 400 tokens with `cached_tokens=0` and a normal
decaying DFlash acceptance curve (`297/1188`, 108 draft cycles). It nevertheless
diverged from the canonical q=1 teacher at zero-based token index 176. The
first 176 tokens were exact. This is a real token mismatch, not the old
combined prefix/cache ambiguity.

The harness stopped normally after the assertion. `cleanup-status.txt` records
`stop_status=0`, `worker_status=0`, and `idle_status=0`; the post-failure idle
snapshot passed with only the four self-observer rows. The server log contains
no `RuntimeError`, traceback, or device error. No reset, reload, unbind, FLR,
shared-memory deletion, or reboot was performed.

Conclusion: stable runner-owned input addresses are insufficient to make the
model's captured target gathers exact. Together with the independent M12
composition pass, this narrows the problem to model-specific producer/consumer
semantics rather than a generic M12 XCCL inability. Do not retry V1 or V2
unchanged. Any future work on this seam requires first-divergent-layer tensor
localization under the model, not another address-lifetime variation.

Durable evidence:

- structured result: `data/laguna-target-inline-gathers-fixed-input-v2-negative-20260801.json`;
- complete vLLM bundle:
  `patches/laguna-s-2.1-xpu-b70/vllm-laguna-target-inline-gathers-fixed-input-v2-68a4a5f3e-20260801.bundle`,
  SHA256 `a181c0036436860b24cacea057e1f285ddd1fcf75a9e010f3d32fecb65095fad`;
- raw response SHA256:
  `7f1d855ffe472aae3ab60ce5f192839962ad2b62e7557cfba174620c489b7071`;
- server-log SHA256:
  `4bea2da23253ee4e39cf7918a0a7003bb259deb3f5dcbdabb2a36abff6995e81`.
