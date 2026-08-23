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

## TP4 MTP2 door: PASS

The identical graph-off MTP2 boot/canary also passed at TP4 on GPUs 0,1,2,3,
memory utilization 0.60, seed 0, and a separate fresh ext4 cache. Engine
initialization took 117.72 seconds, including 101.59 seconds of compilation.
All four ranks produced distinct AOT artifacts. The canary returned exactly
`14` with `cached_tokens=0` and `finish_reason=stop`. As at TP2, one 60-second
shared-memory warning occurred during live compilation and was followed by a
healthy service; there was no worker exception or missing artifact.

Raw root:
`/mnt/usb-models/bench-results/qwen38-27b-autoround-int4-b70/nightly-strict-20260823/tp4-mtp2-f16-isolated-seed0-smoke-a`.

| Artifact | SHA-256 |
| --- | --- |
| `canary.json` | `e6b6b8f4c6e3c29f137ccc13c95b50f7c89778695bfebaaea3081cb13fa8926a` |
| `server.log` | `46c0edc9c82a8410adcb120ca48681e862bdbe5ee89ceaaf10f864347d7b142a` |
| `identity.env` | `749f67e33442a2f0957e6da253e8a66ccaecd99b70ee62364c8119102b044a23` |
| complete 5,534-file cache manifest | `6fcf6486096d18460f6da06f7d0290efad2ed951d72d622cb45924102e93a691` |

This closes the TP4 boot goal at smoke depth and supersedes the old blanket
"TP greater than one does not boot" conclusion. It does not make MTP2 a speed
win or promotion candidate. The next qualified door is a replay-cache,
two-prompt, 128-token performance/acceptance screen. A full 25-prompt arm is
forbidden unless the screen is competitive and correct.

## Runner-only preflight miss

The first runner invocation used a results parent that had not yet been
created and stopped before Docker launch; its empty cache directory is retained
as `tp2-mtp2-f16-isolated-seed0-smoke-a`. It contains no model or GPU result.
