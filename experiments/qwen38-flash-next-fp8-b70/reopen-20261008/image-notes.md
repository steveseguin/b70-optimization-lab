# Image metadata and disk admission

Read on 2026-10-08 with `docker images`, `docker image inspect`, `docker history`,
and `docker manifest inspect --verbose` only. No containers, pull or build ran.

| Docker tag | Result | Compressed layers |
| --- | --- | --- |
| `vllm/vllm-openai-xpu:v0.30.0` | linux/amd64 manifest `e4446310…` | 4,311,802,107 bytes; 4.015679 GiB; 18 layers |
| `vllm/vllm-openai-xpu:v0.30.0-x86_64` | same amd64 digest | same |
| `vllm/vllm-openai-xpu:v0.30.0-amd64` | no such manifest | unavailable |
| `vllm/vllm-openai-xpu:v0.30.0-ubuntu24.04` | no such manifest | unavailable |

Full selected platform digest:
`sha256:e4446310b1d30015e8fdc1a0a2ef1669ac6bef857cbe772487571ed5c1a926a9`.
This is the amd64 **child** identity. Lumnus's Dockerfile names the multi-platform
parent `fc0e112a…`; the different digest alone is not evidence of tag drift.
The layer sum excludes the tiny config/manifest; the 5 GiB download allowance
covers these too. Variant failures and raw descriptors are retained in `evidence/`.

Registry manifests expose compressed sizes, not unpacked disk use. We cannot
derive an exact post-pull footprint without pulling or reading uncompressed
layers, neither authorized here. `docker images` reports the existing Qwen
images at 23.3–23.9 **decimal GB** (~21.7–22.3 GiB), and their base at 18.4 GB.
The current Docker image-store `image inspect .Size` values are much smaller
(~4.6–5.8 decimal GB); do not substitute these for the displayed disk footprint.
These measurements are retained separately in
[docker-images.jsonl](evidence/docker-images.jsonl) and
[local-images.json](evidence/local-images.json).

Conservative planning estimate: **24 GiB unpacked + 5 GiB download allowance +
10 GiB scratch + 50 GiB reserve = 89 GiB free before pull**. Do not deduct assumed
layer sharing. This is an admission estimate, not a proven upper bound on image
extraction; verify actual free space immediately after pull, before launch.
Current observation: 57,638,572,032 bytes = 53.680 GiB free, short by 35.320 GiB.
After an image is present, retain at least 60 GiB free. Both Docker and the run
output filesystem must pass; no automated model/image/cache deletion is supplied.

Local image inspection found eleven Qwen overlay image IDs plus the base.
The newest named local images are R276 dynamic-speculation variants. Their
labels identify kernel head `1e90ffa672ba02f17a909da11838a4c55b199783` and
history installs `vllm_xpu_kernels-0.1.dev1+g1e90ffa67…whl`.
No inspected label/history confirms vLLM ≥0.30 or kernels ≥0.1.14, and no R304
image is identified. Installed package versions remain unknown without opening
image contents; no container was started to resolve that uncertainty. R304's
presence on the other host or in repository guides is not local availability.

The future entrypoint records actual vLLM, torch, Triton, kernels and Transformers
versions and refuses an incompatible major/minor vLLM or older kernel package.
The future run captures full image inspect (creation time and image ID), exact
launch argv/environment, pinned source file hashes, model verification and logs.
The V30 package's source requirement pins torch 2.13.0, Triton 3.7.2+xpu and
kernels 0.1.14.1; those are source expectations, not an executed import result.
