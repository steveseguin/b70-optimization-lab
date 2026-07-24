# Laguna M8 actual-model gate: ZMQ path preflight abort

Date: 2026-07-24 America/Toronto

Status: sealed operational abort during incumbent client construction, before
EngineCore launch, worker creation, model load, XPU generation, evidence
capture, or any B/C arm. This is not a quality or performance result.

## Frozen identity

- approved record: LocalMaxxing `cmrx6p5dv001bo4017hb7sixz` at
  `33.89498511171744 tok/s`;
- gate tooling commit:
  `3fbf310f129a59c5f28abc8b77597a5e692539d3`;
- preregistration commit:
  `b6a7800e3`;
- reviewed recorder/segmented vLLM:
  `5c6c108bf152f985e126db9d77897ae442b75048`;
- frozen kernel descendant:
  `4772f727590c51b72add79350b913d098cf67872`;
- sealed run root:
  `/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-m8-actual-offline-3fbf310f1-20260724T160003Z`.

The run root is owner-readable and non-writable. Its retained `identity.txt`
and incumbent logs have SHA-256 digests:

```text
21537f00e6871280ca7c99972316804ecaa0390aeae4c15a4d407eb506b3d9eb  identity.txt
2b9284bbd8a25a335bc28cb666416361672ffdbd6edf6087961efeb7f6a29daa  incumbent-eager/stdout.log
1f43ed93dbb43d47685d1de0906b9a02074ab63677c57d5c702fa066740d1090  incumbent-eager/stderr.log
```

## What happened

The fixed model-content verification completed, and the global pre-arm plus
incumbent pre-arm strict JSON XPU-idle observers passed. The incumbent client
then asked pyzmq to bind this Unix-domain socket:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-m8-actual-offline-3fbf310f1-20260724T160003Z/incumbent-eager/private-tmp/70e3ac89-198c-407f-adcb-f3ef015ddb26
```

The filesystem path exceeded `sockaddr_un.sun_path`'s 107-character limit.
`zmq.Socket.bind` raised `ZMQError` while constructing the synchronous
EngineCore client. The stack had not started EngineCore or any worker.

The launcher then performed its failure postflight. The exact `/proc` worker
reports before the gate, before the arm, and after the failure are all empty,
and the strict post-arm JSON observer passed with only its own `xpu-smi` rows
on devices 0-3. There is no `driver.json`, recorder evidence directory, or
model-generation result. The segmented-eager and segmented-graph directories
contain only the private empty state prepared before arm A; neither arm ran.

## Decision

Classify this root as `operational_abort_before_engine_or_generation`. It says
nothing about segmented eager/graph exactness or speed, and it is never
reused.

The only authorized correction is to retain the private per-arm temp/cache
layout while setting `VLLM_RPC_BASE_PATH` to a separately fresh, short,
owner-private directory under the fixed internal-NVMe artifact temp root.
The driver and analyzer must bind and record that directory, conservatively
prove room for vLLM's UUID socket name, and reject any external, reused, or
unexpected path. The correction requires its own commit, independent audit,
and new exact preregistration before a fresh A/B/C attempt.

The approved LocalMaxxing record remains unchanged.
