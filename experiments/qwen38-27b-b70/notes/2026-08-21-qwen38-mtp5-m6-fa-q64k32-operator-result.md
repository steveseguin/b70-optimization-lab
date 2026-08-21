# Qwen3.8 MTP5/M6 Q64xK32 FlashAttention operator result

Date: 2026-08-21

Classification: **infrastructure-invalid/incomplete campaign; valid GPU2
supporting result; candidate neither qualified nor rejected**

Preregistration:
[`2026-08-21-qwen38-mtp5-m6-fa-q64k32-operator-prereg.md`](2026-08-21-qwen38-mtp5-m6-fa-q64k32-operator-prereg.md)

Structured summary:
[`2026-08-21-qwen38-mtp5-m6-fa-q64k32-operator-result.json`](../data/2026-08-21-qwen38-mtp5-m6-fa-q64k32-operator-result.json)

## Outcome

The corrected r2 candidate built successfully. Physical GPU2 then completed
the preregistered fresh-process A-B-B-A sequence. All four immutable packets
passed the current strict validator, every baseline and Q/K/V/`seqused_k`
mutation had exact control/candidate eager/graph digests, and the candidate
cleared every preregistered per-device timing gate.

The campaign stopped at physical GPU3's first selector-off incumbent control.
That process did not publish a success packet, failure receipt, final stderr,
mapping record, correctness result, or timing sample. No GPU3 candidate ran and
no eight-packet comparison exists. The Q64xK32 candidate is therefore neither
qualified nor rejected. The result root is terminal and must not be appended
to, compared, retried, or used to authorize a model/full-25 run.

## Valid GPU2 evidence

The graph-replay medians and independently recomputed paired savings are:

| KV length | Control A1 / A2 (us/call) | Candidate B1 / B2 (us/call) | Central saving (us/call) | Bootstrap 95% CI |
| ---: | ---: | ---: | ---: | ---: |
| 128 | 26.97474 / 27.03922 | 19.58658 / 19.47296 | 7.477210 | [7.437820, 7.500350] |
| 1024 | 121.57028 / 121.42832 | 62.85396 / 62.93014 | 58.607250 | [58.541340, 58.6740765] |
| 1300 | 151.67568 / 151.54802 | 76.35264 / 76.51722 | 75.176920 | [75.02039675, 75.31030325] |
| 2048 | 228.88918 / 228.91310 | 112.87562 / 113.25964 | 115.833510 | [115.7629135, 115.90345325] |

At the representative KV-1300 shape, the measured saving is
`1.20283072 ms` across the 16 full-attention calls in a target step. Relative
to the approximately `35.3 ms` target-step context used to set the gate, that
is a `3.407%` latency reduction. Applied mechanically to the `101.170 tok/s`
research anchor, it projects to about `104.74 tok/s`. This is operator-level
headroom, not endpoint evidence: it excludes integration overhead, different
production KV weighting, GPU3 behavior, full-model correctness, and the
existing lane nondeterminism.

All four packets recorded 32 poison-and-replay correctness checks per KV shape,
four mutations per shape, exact eager/graph digest equality, and maximum
CPU-oracle absolute difference `0.00048828125`. Candidate arms each emitted
exactly one policy marker and mapped the exact candidate extension/device/stock
libraries; controls emitted no marker and mapped the incumbent stage. The
packets are:

- A1 control: `gpu2-1-control.json`, SHA-256
  `b1f155c023f5fc310716f0cc37ee2969fe4a71dfab1ad0585864f823ecad58bb`;
- B1 candidate: `gpu2-2-candidate.json`, SHA-256
  `338e0be18f56c324124dcafce6b8e22f32b649a02bf7598c91d402193c023c2c`;
- B2 candidate: `gpu2-3-candidate.json`, SHA-256
  `df2387902cd34ccb852264146ca658d1665f1463fc9c9bdc633bdf0ad98b7983`;
- A2 control: `gpu2-4-control.json`, SHA-256
  `a305e01605f2b7c1fcef9e886992e1cf38f1d92bf665d9d961e4ce8fa386a44f`.

The two candidate stderr logs are byte-identical at SHA-256
`716fbc36d48ff49d214682f6b48857261378b11a99c92031fc6895141111dcc4`;
the two control logs are empty at SHA-256
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.

## GPU3 stop and evidence boundary

The only durable GPU3 file is the unpublished temporary
`gpu3-1-control.json.stderr.log.tmp`, mode `0664`, size zero, SHA-256
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
It is not a success packet or failure receipt.

The driver launched the selector-off control. The launch console and a one-shot
`py-spy` observation placed it in its first warmup `torch.xpu.synchronize()`
for more than ten minutes; the operator terminated it and the driver returned
`143`. Those are
external operational observations, not facts independently proved by the
result root. A later bounded discovery enumerated four devices, while a
separate `xpu-smi dump` process was subsequently observed blocked for roughly
two hours and was terminated. Neither observation establishes GPU3 compute
health or identifies a Q64xK32 failure. No subsequent GPU3 candidate arm was
started; whether the unsealed control process mapped only the intended stock
libraries is unknown because no mapping evidence survived.

## Frozen build and harness identity

The successful r2 build is preserved at
`/home/steve/qwen38-m6-head256-q64k32-attn-override-20260821-r2`:

- candidate-stage JSON SHA-256
  `16f9f972b03cdc3a1fe041840f1061db9307af7d0ae16a6569a5ddf7200a27c2`;
- build-input manifest SHA-256
  `0a38d154dba9929d388d2db36e49eaeb08a663fe417915b115c3099acbde4605`;
- graph manifest SHA-256
  `d662dba3927fac706ff221902f536b67178b6875f66604597a1f2fe98a4defc4`;
- source identity SHA-256
  `36e74e5202f9aed151bca85f54997eb0c09ef93227959837f4e6c8ceb67c5f6c`;
- candidate `libattn_kernels_xe_2.so` SHA-256
  `01a5b35b5a9c6321b436b137f95403db9e45ce4aabb44257dc7e4f45c84aecf5`.

The launch used lab commit
`e3d38951d116625de61b635ba078f60c90fe8ca3`, qualifier SHA-256
`31862ea6a8b9e11a59d643e0d3500179d938261e62b93fb920439c664ce21fbc`,
driver SHA-256
`e7480d5768e366a5797f6c32afe8456281336238fb96e6cae4206b5257a53fb9`,
source patch SHA-256
`9386432015f5c9cd330dd7cfb785a16f259cce8563f44da9f812dcceb342138a`,
and build-helper SHA-256
`11480161dce25cba56e00f2f48c95d74164bac1f5af2dbc945eddceff6d57d47`.

## Decision

Preserve the r2 build and result roots. Do not write a comparison, append GPU3
arms, rerun the same root, carry GPU2 forward as half of a later pass, or start
an endpoint/full-25 model run. The candidate remains a high-value source and
operator hypothesis because GPU2 showed exact outputs and large repeatable
headroom, but this campaign did not satisfy its conjunctive two-device gate.

The narrow next action is a separately preregistered, incumbent-control-only
GPU3 diagnostic under a fresh root. It needs a hard watchdog and atomic phase
receipts before and after import, first launch, and first synchronize. Only a
clean control-health result may authorize a new full eight-arm campaign under
a separate preregistration. Any future endpoint campaign must still validate
the exact full model, MTP5 outputs, quality, freshness, cache, and repeatability;
none of those are established here.
