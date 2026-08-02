# PR #15 exact-model claim validation

Date: 2026-08-02

## Scope and safety

The lane owner kept Laguna paused and authorized validation of the community
Qwen3.6 contribution. The active Laguna Git worktree remained clean and was
not edited. Before each service start, no model service or relevant endpoint
was active. Runs used logical B70 devices 0 and 1, unique rootless-Podman
container names, localhost ports 18216 or 18217, and read-only model mounts.
No service change, reset, driver reload, or reboot was used. The unrelated
`aria2c` process stuck in D state on the external NTFS volume was left alone.

## Identity

- Contributor PR: #15.
- Contributor head: `975a097891fb00e0cdf989b9f3a13d3c09114321`.
- Model: `Qwen/Qwen3.6-35B-A3B` revision
  `995ad96eacd98c81ed38be0c5b274b04031597b0`; the preceding validation
  checked all 40 files, upstream sizes, and 27 LFS SHA-256 values.
- Image:
  `docker.io/intel/llm-scaler-vllm@sha256:5d87be271e4db54539f1dbb29c071e9122f4e57b74594dbb26a55d27a569d780`.
- Image ID: `2950f3361abbedc07719e8c4f4e032f007232c6ad23e6d1eb64703789cbba73a`.
- vLLM: `0.21.1.dev0+gad7125a43.d20260709`, commit `ad7125a431`.
- XPU kernels: `3cab97adf`.
- Corrected final launcher SHA-256:
  `33854405b7c15402e25f30a1059268ec547080c07c27e2f95a6dd57483bdcd02`.
- Runtime: TP2, eager, runtime FP8, float16 activation dtype, prefix caching
  disabled, no SSM-state override, max model length 262144, max sequences 4.
- Container runtime: rootless Podman 4.9.3. This executed the pinned OCI image
  and Podman launcher branch; the Docker-specific render-GID and shared-memory
  branch was reviewed but not executed because the Docker CLI is absent on this
  host.

## Results

The fresh claim-validation service reached health in 121 seconds and again
selected `XPUFP8ScaledMMLinearKernel` plus the XPU FP8 MoE backend. Plain and
thinking smoke passed, as did the previously recorded structured arithmetic,
four-request contamination, and 30,049-token retrieval gates.

The fixed 12-prompt suite completed every prompt at 128 output tokens. Its
diagnostic median was `50.43388928995701 tok/s` under the historical
100-event formula and `49.92955039705744 tok/s` under conventional 99-interval
accounting. The strict result remains `invalid-or-incomplete`: all responses
again omitted `prompt_tokens_details`, so the required observable
`cached_tokens=0` gate could not pass. The earlier conventional diagnostic was
`48.095169967532186 tok/s`. Neither result is promoted or eligible for
LocalMaxxing.

The near-boundary gate constructed a deterministic 811,577-byte prompt and
confirmed its chat-template length through the server tokenizer. The request
used 261,794 prompt tokens and 18 completion tokens, 261,812 total under the
262,144 limit. It returned the exact early-context key
`PR15-NEAR256K-6F2A9C` in 63.7876 seconds. An immediate independent request
returned `PR15-AFTER256K-READY` exactly in 0.2940 seconds. This validates the
pinned corrected recipe near 256K; it does not identify what the contributor
ran.

## Thinking-budget correction

Simple explicit 32- and 128-token-budget probes both returned nonempty parsed
reasoning, `finish_reason=stop`, and final content `408`, with 37 and 133
completion tokens. That did not establish a general hard-budget guarantee.
When the launcher's smoke was strengthened to reject truncated reasoning, two
fresh candidates instead ended with `finish_reason=length`. Both failures were
preserved, but their complete request payloads were not; no narrower budget or
response-cap claim is made from those attempts.

The published smoke now uses the reproducible seeded 32-token case with a
separate 256-token total cap and requires nonempty reasoning,
`finish_reason=stop`, and final content exactly `408`. Its exact final replay
passed after reaching health in 121 seconds. The failure path also now invokes
`logs --tail N NAME`, which works with both supported CLI layouts; the prior
`logs NAME --tail N` ordering failed under this host's Podman.

## Claim classification

- Corrected OCI service under rootless Podman, TP2 online FP8 XPU path, bounded
  plain and thinking behavior, four-request concurrency, and near-256K
  retrieval plus next-request behavior: `B70-tested`.
- Contributor's original image, model revision, internal runtime, raw smoke,
  and actually exercised context: still `community-reported` / unknown.
- Original `150 tok/s` "golden" comment: unsupported. It has no workload,
  metric definition, repetitions, run identity, logs, or quality gate. The lab
  diagnostics are not a comparable metric and neither verify nor scientifically
  refute it.
- "No VRAM spike" and "correct scales": only the online FP8 path and kernel
  selection are observed. Peak memory, quantization granularity, scale
  correctness, and BF16-relative quality remain unverified.
- Pretrained-FP8 fallback being slow or incorrect: unverified; that checkpoint
  was not loaded.
- Optional float16 Mamba SSM state: untested and remains gated as a separate
  quality-changing experiment.

## Artifacts and teardown

Raw root:

`/mnt/fast-ai/bench-results/community-qwen36-pr14-pr15/pr15-claim-validation-20260802T045055Z`

Key SHA-256 values:

- primary claim-run container log:
  `fc8b0f57ccca7c7074706989f945bc84f1fb99e680371d43a5d1e8d311d95587`;
- qualified fixed suite:
  `2e5323acc7e91a26489d0460feeb600446685ff42da4d189b2dacb0e002522eb`;
- near-context summary:
  `3bd9de36ab6a98c39ecace8ba2b095fd82800c76268a3fc6e86546c86b6bbe92`;
- exact final-launcher log:
  `c41626a9976231d1598d7b3a762fe87b1193cdf552d56d41c8cb0b5e6cd94593`.

All exact test containers were stopped and removed. Ports 18216 and 18217
were clear. Post-teardown device memory was approximately 42.9 MiB on each
tested B70.
