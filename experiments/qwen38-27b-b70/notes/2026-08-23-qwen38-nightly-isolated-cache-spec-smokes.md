# Qwen3.8 nightly isolated-cache speculative smokes

Date: 2026-08-23. This is the bounded follow-up to the infrastructure-invalid
TP4 MTP2 arm. It uses the immutable nightly image digest
`sha256:bc979d1ba312dc8a666c57a40205f35d7fc5d96b2f7450c2c77f5b3d5243f0e0`
and the new opt-in strict runner. The historical runner and all prior speed
captures remain unchanged.

## TP2 MTP2 door: PASS

Identity:

- AutoRound INT4 W4A16, F16 KV, max model length 32,768;
- TP2 on GPUs 2,3, graph disabled, memory utilization 0.60;
- MTP2, `PYTHONHASHSEED=0`, existing tuner defaults;
- fresh ext4 cache with only `VLLM_CACHE_ROOT` and `XDG_CACHE_HOME` set;
- no explicit shared `TORCHINDUCTOR_CACHE_DIR` or `TRITON_CACHE_DIR`;
- boot plus one exact code canary only; no performance suite.

Raw root:
`/mnt/usb-models/bench-results/qwen38-27b-autoround-int4-b70/nightly-strict-20260823/tp2-mtp2-f16-isolated-seed0-smoke-b`.

The two ranks compiled distinct AOT artifacts (`rank_0_0` and `rank_1_0`),
the service became healthy, and the canary returned exactly `14` with
`cached_tokens=0` and `finish_reason=stop`. Engine initialization took 110.51
seconds, including 98.93 seconds of compilation. One 60-second shared-memory
broadcast warning occurred while rank 0 was still compiling; it had no
preceding worker exception, compilation subsequently completed, and the
service/canary passed. It is therefore a wait symptom, not a deadlock.

Evidence SHA-256:

| Artifact | SHA-256 |
| --- | --- |
| `canary.json` | `e9345b337d665361ee37691d59d1e84813b9308bcae791379a587ba91e773368` |
| `server.log` | `b06b0f89975edb97131dd81c085f74013eb156c779174c840c1fc48c91bfc9cb` |
| `identity.env` | `1d5a14f8e1064c360f97896c6efacb7a7922f973621b71e3166ecbbd8f89b107` |
| complete 2,836-file cache manifest | `8e348fce5faf203e09455defa4ade36925135177eebda3decfcfbfa4e4ff0929` |

This result disproves the blanket claim that speculative decode at TP greater
than one cannot boot on this container stack. It does not establish TP2 MTP
speed, acceptance, full-suite quality, or determinism.

## Next qualified door

Run the identical graph-off MTP2 boot/canary at TP4, memory utilization 0.60,
all four cards, and a different fresh ext4 cache. Stop before a performance
suite. Only a clean TP4 canary pass permits a bounded performance screen.

The first runner invocation used a results parent that had not yet been
created and stopped before Docker launch; its empty cache directory is retained
as `tp2-mtp2-f16-isolated-seed0-smoke-a`. It contains no model or GPU result.
