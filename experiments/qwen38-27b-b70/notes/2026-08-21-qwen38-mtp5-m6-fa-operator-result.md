# Qwen3.8 MTP5/M6 exact-shape FlashAttention operator result

Date: 2026-08-21

Classification: **terminal candidate-role correctness-gate rejection; no retry
or model run**

Preregistration:
[`2026-08-20-qwen38-mtp5-m6-fa-operator-prereg.md`](2026-08-20-qwen38-mtp5-m6-fa-operator-prereg.md)

Structured summary:
[`2026-08-21-qwen38-mtp5-m6-fa-operator-result.json`](../data/2026-08-21-qwen38-mtp5-m6-fa-operator-result.json)

## Outcome

The first r6 control arm passed and wrote a complete sealed packet. The first
candidate arm then failed its first checked eager correctness replay at KV 128:

```text
error: KV 128 eager 0 differs from CPU oracle: Tensor-likes are not close!
Mismatched elements: 3297 / 18432 (17.9%)
Greatest absolute difference: 0.1544189453125 at index (0, 5, 116) (up to 0.02 allowed)
Greatest relative difference: 1485.0 at index (0, 9, 89) (up to 0.01 allowed)
```

Those lines are an exact launch-console observation, not a retained file in
the r6 root. The failure happened after the candidate process entered the
KV-128 case and completed the harness's ten unscored warmups, but before it
could complete the 32 checked eager replays, graph capture, mutations, timing,
mapped-library inventory, marker validation, or atomic run packet. The
fail-fast path deleted the temporary candidate stderr capture. Consequently
there is no candidate JSON, candidate stderr artifact, or `comparison.json` to
hash or reinterpret.

This candidate-role launch was bound by the frozen driver and stage manifest to
the intended Q8 x K64 stage, and it failed the exact operator correctness gate;
the qualification is therefore rejected rather than infrastructure-invalid.
Because no candidate marker or mapped-library record survived, r6 does not
independently prove runtime Q8 x K64 dispatch/DSO mapping or isolate which
internal policy feature caused the mismatch. It is also not a timing result:
only the control has recorded timing samples, there is no paired candidate
sample, and none of the preregistered performance gates was evaluated.

## Post-result source diagnosis

The intended specialization reused
`decode_policy_qpacked_head<_8, _256, _64>`, whose subgroup layout is
`<1,4,1>`. In the chunk-prefill kernel, however, `sg_tile_q` is calculated as
`TileQ / SGPerWG` and the flat subgroup ID advances `row_base`; causal masking
then uses that row base. Four K-split subgroups that collectively own the same
eight query rows are therefore treated as query-row bases `0,2,4,6` before
their partials are combined. That is valid for the decode kernel's packed-head
interpretation, but not for six chunk-prefill token rows. The same structural
error rules out the superficially smaller decode-style Q8 x K32/ReduceK2
variant as well.

This is a source-level diagnosis of the intended candidate policy, not a
replacement for the candidate marker/mapping evidence that the failed process
did not persist. It explains why this policy is closed without attributing the
failure to generic ReduceK roundoff.

## Control evidence

The retained control arm is
`/home/steve/qwen38-mtp5-m6-fa-candidate-abba-20260820-r6/gpu2-1-control.json`
at SHA-256
`9384b4f46b79185cec24428f68899e1a2cb09fc9bfc88931f94446e64c817ba0`.
It records:

- schema `qwen38-mtp5-m6-fa-operator-run-v1`, `passed=true`, role `control`,
  arm `gpu2-a1`, and campaign slot 1;
- host `steve-b70s`, physical GPU 2 selected by `ZE_AFFINITY_MASK=2`, exactly
  one visible XPU, and logical device `xpu:0`;
- FP16 rows 6, local Q heads 12, local KV heads 2, head dimension 256, block
  size 64, KV lengths 128/1024/1300/2048, `is_mix_batch=true`, and forced
  chunk decode enabled;
- all four baseline eager/graph cases and every Q/K/V/`seqused_k` mutation
  passed the packet's poison, CPU-oracle, bit-stability, exact eager/graph,
  and static-output checks; and
- for the identical KV-128 fixture (seed `380128`, SHA-256
  `0acb368f76405cfab88e47944437d0399bce0866fe9452096d3d5e0a2c9570cd`),
  the control's eager output had maximum absolute CPU-oracle difference
  `0.00048828125`, about 316 times smaller than the candidate's console-observed
  `0.1544189453125`; and
- the exact selected extension, control device library, and stock library
  were mapped from the control stage with their recorded hashes.

Its expected empty marker log is
`/home/steve/qwen38-mtp5-m6-fa-candidate-abba-20260820-r6/gpu2-1-control.json.stderr.log`
at the empty-file SHA-256
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
The r6 root contains exactly these two regular files. No candidate or compare
artifact exists there.

## Frozen candidate and harness identity

The rejected build remains sealed under
`/home/steve/qwen38-m6-head256-q8k64-attn-override-20260820-r4`:

- candidate-stage JSON:
  `/home/steve/qwen38-m6-head256-q8k64-attn-override-20260820-r4/qwen38-m6-head256-q8k64-candidate-stage.json`,
  SHA-256 `ec3b31cad3c89b1bf0d4a747cb011ebea248b7c55c8766563489e09bfcde7a7e`;
- build-input manifest:
  `/home/steve/qwen38-m6-head256-q8k64-attn-override-20260820-r4/qwen38-m6-head256-q8k64-build-inputs.sha256`,
  SHA-256 `21ded717f108feaada2018f360c4c781cf91f5893b28478842859a429962a53b`;
- candidate graph manifest:
  `/home/steve/qwen38-m6-head256-q8k64-attn-override-20260820-r4/qwen38-m6-head256-q8k64-candidate.graph.sha256`,
  SHA-256 `db0f01bdf72670c119ff95e40cdf4b967f0613e0b1dd0b383d581150245fab62`;
- source identity:
  `/home/steve/qwen38-m6-head256-q8k64-attn-override-20260820-r4/qwen38-m6-head256-q8k64-source-identity.txt`,
  SHA-256 `5096b9c8df15ed1d0ef3eb60ba6ab4510fc5745b50bc28bde285a92003063fb2`;
  and
- candidate `libattn_kernels_xe_2.so` SHA-256
  `f777decfe23efb45fe7797d16d9f6378dfef531a5ce66aab3ddee5567b65013e`.

The launch used lab commit
`080e4b2e131bdb994d07125d7b5087e3532780db`, qualifier SHA-256
`0dd7b945ef35a11ff4d0a1ec085e604920524b996d539e089d89b4a019a5de1f`,
driver SHA-256
`5aa23300d7e3cfd64e10964c7a395b11e8ba70099908d48d6bc8fc58f0d7b9f1`,
policy patch SHA-256
`06467757a7482ad0e3225c9a59ce3d2de144453a608016737c7a24dbe48b5fc1`,
and build-helper SHA-256
`1235e181bcd3ca0782d0faef9416927435564cf7eb44d0d8bcc0e6470886e445`.

The candidate manifest proves the intended stage bytes, but it is not a
substitute for the missing candidate run packet. In particular, there is no
durable candidate-side mapped-library or captured-marker record after the
correctness exception.

## Decision and scope

Reject and preserve this qualification attempt for the intended Q8 x K64
policy. Do not retry it, rebuild it under a new root, continue the remaining
ABBA arms, or spend a model/full-25 run on it. The r6 control timing must not be
compared to another run or used to estimate endpoint headroom.

This direct operator failure makes no claim about model output, target
exactness, speculative acceptance, endpoint throughput, or the broader
FlashAttention optimization surface. Any later FlashAttention experiment must
be a materially distinct source policy with a new correctness-first
preregistration; it must not relabel or waive this result.

The narrow next policy worth qualifying is chunk-native Q64 x K32 with
`ShapeQK/ShapePV=<64,32,32>`, `ShapeOut=<64,256>`, and subgroup layout
`<8,1,1>`. It preserves the incumbent per-subgroup Q8/K32/ReduceK1 arithmetic
while reducing the workgroup from 32 to 8 subgroups. This is only a
source-backed hypothesis: it requires a new patch, build, result root,
preregistration, and the same eager/graph/oracle gates before timing or model
work.
