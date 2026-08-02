# PR #15 exact-model claim validation

Date: 2026-08-02

## Scope and safety

The lane owner kept Laguna paused and authorized validation of the community
Qwen3.6 contribution. The active Laguna Git worktree remained clean and was
not edited. Before each service start, no model service or relevant endpoint
was active. The initial claim-validation runs used logical B70 devices 0 and 1,
unique rootless-Podman container names, localhost ports 18216 or 18217, and
read-only model mounts; the later benchmark/MTP runs used ports 18218–18221
under the same isolation policy. A final Docker Engine replay used the same
two logical B70s, a unique exact container name, a read-only model mount, and
localhost port 18222. Docker Engine installation created and enabled the
Docker/containerd system services, but no model service, reset, driver reload,
or reboot was used. The unrelated
`aria2c` process stuck in D state on the external NTFS volume was left alone.

## Identity

- Contributor PR: #15.
- Contributor head: `975a097891fb00e0cdf989b9f3a13d3c09114321`.
- Model: `Qwen/Qwen3.6-35B-A3B` revision
  `995ad96eacd98c81ed38be0c5b274b04031597b0`; the preceding validation
  checked all 40 files, upstream sizes, and 27 LFS SHA-256 values.
- Image:
  `docker.io/intel/llm-scaler-vllm@sha256:5d87be271e4db54539f1dbb29c071e9122f4e57b74594dbb26a55d27a569d780`.
- Podman image/config ID:
  `2950f3361abbedc07719e8c4f4e032f007232c6ad23e6d1eb64703789cbba73a`.
- vLLM: `0.21.1.dev0+gad7125a43.d20260709`, commit `ad7125a431`.
- XPU kernels: `3cab97adf`.
- Pre-MTP claim-validation launcher SHA-256:
  `33854405b7c15402e25f30a1059268ec547080c07c27e2f95a6dd57483bdcd02`.
- Published post-audit launcher SHA-256:
  `737f8dd32523efb2101175748613a7ddc96856368cf08c3ec63221f17249c0ff`.
- Initial/default corrected runtime: TP2, eager, runtime FP8, float16 activation
  dtype, prefix caching disabled, no SSM-state override, max model length
  262144, max sequences 4. Later benchmark/MTP sections identify their separate
  float16-SSM and speculation settings explicitly.
- Container runtimes: rootless Podman 4.9.3 for the initial work and Docker
  Engine 29.7.1 for the follow-up. Both executed the digest-pinned image. The
  Docker run exercised the numeric render-GID and `--shm-size=32g` branch.

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
`finish_reason=stop`, and a final answer giving `408`. Its exact final replay
passed after reaching health in 121 seconds. A later MTP launcher replay
correctly returned `17 * 24 = 408`; the check was narrowed to accept only bare
`408` or that exact equivalent equation, avoiding a false engine-start failure
without accepting arbitrary explanatory text. The failure path also now invokes
`logs --tail N NAME`, which works with both supported CLI layouts; the prior
`logs NAME --tail N` ordering failed under this host's Podman.

## Claim classification

- Corrected OCI service under rootless Podman, TP2 online FP8 XPU path, bounded
  plain and thinking behavior, four-request concurrency, and near-256K
  retrieval plus next-request behavior: `B70-tested`.
- Contributor's original image, model revision, internal runtime, raw smoke,
  and actually exercised context: still `community-reported` / unknown.
- Original `150 tok/s` "golden" comment: unsupported. It has no workload,
  metric definition, repetitions, run identity, logs, or quality gate. This is
  separate from the later defined `llama-benchy` CSV described below.
- "No VRAM spike" and "correct scales": only the online FP8 path and kernel
  selection are observed. Peak memory, quantization granularity, scale
  correctness, and BF16-relative quality remain unverified.
- Pretrained-FP8 fallback being slow or incorrect: unverified; that checkpoint
  was not loaded.
- Optional float16 Mamba SSM state: later exercised for the matched throughput
  replay and bounded coherence, but still lacks quality equivalence and long-
  context comparison against checkpoint-declared float32.

## PR-discussion benchmark replay

The original claim classification above was based on the submission content.
The PR discussion additionally contains a contributor-attached
`llama-benchy` CSV posted on 2026-08-01. The contributor described a
2,048-token prompt, 1,024-token generation, depths 0/4,096/8,192/16,384/32,768,
five runs per depth, concurrency 1, and generation-latency mode. The CSV reports
127.8645–135.0527 decode tok/s and 8,330.49–9,250.63 prefill tok/s. It is now
tracked, newline-normalized, under the community entry's `reported/` directory;
the original attachment SHA-256 is
`36b9b376c4948a333797e3b1c211e392113245edda6225d098648f6e7b735483`.

The closest recoverable lab replay pinned the model/image identities above,
used TP2, eager mode, online FP8, the submitted float16 SSM override, prefix
caching off, and `llama-benchy` commit
`e9be344578cec17745066b220798b80a0d2686d3`, the last upstream commit before
the post. All 25 measured requests completed without API errors. The five
decode means were 54.9226, 53.5833, 54.0094, 53.9365, and 54.8300 tok/s. Their
54.2564 overall mean is about 59.2% below the contributor's 132.8771 overall
mean. Prefill means were broadly similar. A v0.4.0 tool calibration gave
55.5351 tok/s and a graph-disabled non-eager calibration gave 21.1090 tok/s,
so neither tested tool revision nor simply disabling eager explains the gap.

Docker Engine 29.7.1 was then installed from Docker's official Ubuntu apt
repository. The exact corrected launcher, pinned OCI digest, model revision,
TP2/eager/online-FP8 identity, submitted float16 SSM override, and benchmark
command were retained. The Docker-specific launcher branch reached health in
121 seconds and passed both smokes. Its full five-depth replay completed all
25 measured requests without API errors and produced decode means of 53.8852,
54.2868, 53.8959, 54.4105, and 55.0716 tok/s. The 54.3100 tok/s overall mean
is `+0.10%` versus the 54.2564 tok/s Podman mean and 59.13% below the
contributor's 132.8771 tok/s mean. Docker versus Podman is therefore ruled out
as the discrepancy's cause for the pinned image and recovered command.

The contributor did not preserve the exact tool version/command, benchmark
JSON/per-request output, immutable image digest, model revision, or effective
XPU graph/communication environment. The result is therefore classified as a
real `community-reported` measurement that was not reproduced, not as fabricated
or invalid evidence.

## MTP and image patch audit

The checkpoint does contain an MTP head: `text_config.mtp_num_hidden_layers`
is 1 and `model.safetensors.index.json` maps the `mtp.*` weights. The submitted
launcher nevertheless had no vLLM `--speculative-config`; adding
`qwen36-35b-mtp` to `--served-model-name` created only an API alias. Its logged
engine identity had speculative decoding off.

The model card recommends two speculative tokens for vLLM. Adding only that
MTP2 setting to the eager float16-SSM matched identity loaded
`Qwen3_5MoeMTP`, accepted 1,247 of 1,800 draft tokens (69.28%), and completed
exactly 1,024 output tokens at 46.4358 tok/s. The comparable MTP-off result was
54.9226 tok/s. Reported KV-cache capacity fell from 1,010,114 to 860,623 tokens.
Four exact-answer cases, four deterministic repeats, and a bounded concurrency-
4 run passed. MTP was genuinely absent from the submitted recipe, but enabling
it does not explain the reported speed and is a regression on this identity.
The corrected launcher exposes the tested `MTP_TOKENS=2` mode while keeping
the default at 0.
The final launcher path was executed with `MTP_TOKENS=2` and the checkpoint's
default float32 SSM state; it reached health in 142 seconds and passed both
plain and thinking smoke checks before exact-name teardown.

The pinned OCI image contains more than upstream vLLM commit `ad7125a431`.
Its embedded vLLM Git working tree has 64 modified tracked files (4,283
insertions, 340 deletions) and 18 untracked files: 17 source/test files and one
release-note file. The embedded
`vllm-xpu-kernels` tree has 25 tracked files changed by 2,192 insertions and 379
deletions beyond `3cab97adf`, including GDN and paged-decode native kernels.
The image also installs `custom-esimd-kernels-vllm 0.1.0`; its included source
tree has no Git metadata. The changes include Intel XPU GDN/ESIMD, FP8,
scheduler, sampler, and speculative-decode work. The Qwen MTP loader files are
byte-identical to upstream, while common speculative paths differ. No
contributor-local patch was supplied or discovered. Exact image-integrated
diffs and the custom-ESIMD source were exported to the raw artifact root, making
the pinned OCI digest—not plain upstream commits—the correct reproducibility
unit.

The most directly relevant delta is the image's fused ESIMD Qwen3.5/3.6 GDN
decode path. Its source requires actual float16 SSM cache state; the
contributor's override makes the path eligible while checkpoint-declared
float32 falls back. The matched replay retained float16 SSM and registered the
custom ESIMD operations. This known image fast-path prerequisite was therefore
not missed, yet decode remained near 54 tok/s.

## Artifacts and teardown

Raw root:

`/mnt/fast-ai/bench-results/community-qwen36-pr14-pr15/pr15-claim-validation-20260802T045055Z`

Matched benchmark, MTP, and image source-audit root:

`/mnt/fast-ai/bench-results/community-qwen36-pr14-pr15/pr15-llama-benchy-replication-20260802T133000Z`

Docker Engine launcher, inspect, log, and matched-benchmark root:

`/mnt/fast-ai/bench-results/community-qwen36-pr14-pr15/pr15-docker-engine-replay-20260802T151250Z`

Key SHA-256 values:

- primary claim-run container log:
  `fc8b0f57ccca7c7074706989f945bc84f1fb99e680371d43a5d1e8d311d95587`;
- qualified fixed suite:
  `2e5323acc7e91a26489d0460feeb600446685ff42da4d189b2dacb0e002522eb`;
- near-context summary:
  `3bd9de36ab6a98c39ecace8ba2b095fd82800c76268a3fc6e86546c86b6bbe92`;
- exact final-launcher log:
  `c41626a9976231d1598d7b3a762fe87b1193cdf552d56d41c8cb0b5e6cd94593`.
- matched five-depth benchmark JSON:
  `423941e06ce9a725105a151053204f42675cf0f7f5dfcdfb9a83dd89446ae925`;
- MTP2 eager calibration JSON:
  `5d74690a81ab2f85dee84f8d3a8c0729fe652525743bf038f6a3d1f5ad7f79b8`;
- image-integrated tracked vLLM diff:
  `65b9842578560d1ca42eba754119bf36d9d244d504fcbb768975c3febbee5dd6`;
- image-integrated tracked XPU-kernels diff:
  `c3d5e80737ccfda6a01e4527e5793f881dd1931ba75cb3076c0c96ea9d86c922`;
- custom-ESIMD source archive:
  `9bc63ee91cebdc9958bccf0e3d489ee7376197bdb1995403a41341bfe4f45e9b`;
- final corrected MTP2 launcher transcript:
  `c42a22d8a6c0b71a89e386970c06291a971f573ffe2ebeaffb8ddd431df25fed`.
- Docker matched five-depth benchmark JSON:
  `aeded8f24d79081baa7aab3ab894b2faec560126502e458b0ddd69178c0b442d`;
- Docker benchmark progress stream:
  `d4bb76ebc16d07f7f8e880fe70b7d06ec7c2f983afe02a535247e61fa0b8a3c7`;
- Docker container log:
  `d3fca863d074825f0597bcf6f33b7b1d7e7284e0ddbc3305c5596adc337d8387`;
- Docker container inspect:
  `319d99c314ced8ebcb409889cc8bf4e238e9b00bb7a0920640188de4ec339f4e`.

All exact test containers were stopped and removed. Ports 18216 through 18222
were clear after their respective runs. Docker and Podman both had zero
containers after teardown. Post-teardown device memory after the initial
validation was approximately 42.9 MiB on each tested B70; the final Docker
teardown process report contained only the observing `xpu-smi` process.
