# Qwen3.8 Flash-Next FP8 A50 external-model preregistration

Date: 2026-09-01
Status: frozen before GPU launch

A50 bypasses the unstable local-NVMe bulk-read path. It is A49 with fresh
attempt `50`/port `19722` paths and the model/tokenizer path changed from the
local NVMe copy to:

```text
/mnt/usb-models/llm-models/Qwen3.8-Flash-Next-FP8
```

The external checkpoint has all 131 shards and is the original validated
download. Its config and index match the local copy byte-for-byte, with
SHA-256 `99c11efba4012d0f760f4e4831a8d6cafd845044e21d0aa9e6d9e70a15a90a8d`
and `0419e2c2dfbb925257d7409405433a793cf7ff7d96f3eba882a815ec6d9fe7a6`.
Weights become resident in the same four GPUs/host PLE placement, so storage
source is a startup-only change and not an inference optimization.

Every A49 model revision, source/runtime identity, graph, `twoshots`, MTP0,
placement, prompt, authority, quality, host guard, and postflight rule remains
unchanged.

## Frozen packet

- derived launcher SHA-256:
  `a1cb7e42c17acbb787190925f1bb52b0335db7b9819c276a79980de71992354e`;
- launcher SHA-256:
  `4ecbf76c233b520d7fd4e3e41ddd15ee7ac2ebd0d73d3ef2c8a008f4ac6c9fdf`;
- client SHA-256:
  `8fbed5e5b7bd3fe101abaef631a962d9194021473ea54757b1afc7f0bab8f976`;
- supervisor SHA-256:
  `b79008f44c2fd6c5d778029871e4ed8214f2b654a91cc14fd30324addce42ec7`;
- privileged host wrapper SHA-256:
  `fe9cd341ce7d227a14f678d98017e7f3354bb68ab73732c1b22e7323dea1de46`;
- rewrite helper SHA-256:
  `ce37ac2f0db3cee81e26f35976b18249356abbb11b23cd7f2d2a2e7644302671`;
- unchanged A48 runtime verifier SHA-256:
  `a3acec5018c4b1147f8efddb75f6678acee7f9802d4fb11f3c56bc7b2bd74ca8`.

A valid result requires the unchanged full quality/losslessness battery and
clean guarded postflight. The load may be slower; measured decode is compared
only after residency and cannot be credited unless every gate passes. No reboot
or one-load-per-boot rule applies.
