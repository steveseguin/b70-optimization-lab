# Qwen3.6 27B INT4 input-dependency experiment

Status: **preserved experiment; failed the normal production gate**.

This packet freezes the exact working-source states used by the final warmed
four-prompt run. It does not promote the dependency change and it is not a
standalone patch to apply on an arbitrary vLLM checkout. Each `*.working.patch`
is a cumulative working-tree patch against the Git head recorded by the run.

## Source identities

| Component | Git head | Baseline patch SHA256 | Candidate patch SHA256 |
| --- | --- | --- | --- |
| `llm-optimizations` | `79685b896ceabc42b54da9cc30eb57bbe3963692` | `2952d461ccf0f1305ed97b57037c1a42b10171f117d8b8953d9ba554acd93ea2` | `ee9f75c99acbc780d685be021b92217d1db141617ffa3826bb6bc5840d8ab534` |
| `vllm` | `a63ff886e1c9c90f919e8b46a63f34027dfae823` | `5ce66291d1be54199c5ebf91899f85efe1240bc720f656d592e9bff5096158ab` | `d36ad75e4f09313a07c9608090a7105b6365b0f9719106c5b53ca2e462e5ac98` |
| `vllm-xpu-kernels` | `6a40e2baf3f8710b89e48d18bf214708ba2dbf9a` | `10d7cb28a11d7ddcc1caf5737368a014a06ffd0ec15be699e8e8f31da8649062` | `e053da6e606be53e1e552efcc8dcbe906b07f5436349cea7ebe0c50539ba4ae7` |

The tested candidate extension was
`ccbeecb4e49eb3419f5a8734c82e2b004bfdd9dffea5f0a9bbe2e8884041ef38`.
The retained pre-input-dependency extension is
`f494925774cf50cd2038684cb64325fcd491c51f2eab94454878c5e804dbaa61`.
No runtime was restored while closing this packet.

`SHA256SUMS` verifies every file in this packet.

## Final bounded result

The finished run is
`/mnt/usb-models/bench-results/qwen36-27b-autoround-int4-b70/int4-input-dependency-layer0-four-spec-a-20260817T014146Z`.
Its final manifest verifies and has SHA256
`988ff654c1a3d0ddf7efd4a6331cfe955ceafdd914d82c90314896b8e2cd36a4`.

It was a warmed, compiled PIECEWISE MTP3 run with the dependency scoped to
`language_model.model.layers.0.linear_attn.in_proj_qkvz`. All four complete
token arrays matched both sealed target controls. The preferred 99-interval
median was `110.67515578910192 tok/s` (the legacy-inclusive helper reported
`111.79308665565851 tok/s`).

The later matched final-source gate failed. The layer0-scoped candidate was
15/25 exact at `96.38550998322077 tok/s` strict. The one permitted correction,
publishing the dependency for all INT4 calls, was 12/25 exact at
`96.57755136578547 tok/s`. Both quality/cache gates passed, but neither target
parity nor the `100 tok/s` objective passed. The approach is not promotable.

See [the chronological note](../../../notes/2026-08-17-qwen36-int4-input-dependency-closeout.md)
and [the structured control summary](../../../data/qwen36-27b-autoround-int4-input-dependency-controls-20260817.json).
