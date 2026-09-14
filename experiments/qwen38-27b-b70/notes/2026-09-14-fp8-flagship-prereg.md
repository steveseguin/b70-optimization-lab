# Official 27B FP8: bounded package and practical replay

This is a usability and reproducibility pass, not a new optimization campaign.
The user selected official 27B FP8 and authorized one recommended setup, a clear
launch/health/stop path, public-artifact replay, and documentation/site publication.

## Fixed configuration

Reuse the already qualified R304 TP2/MTP1 32K-input configuration recorded at
`/mnt/fast-ai/bench-results/qwen38-fp8-r304-real-content-depth-20260913b/depth-mtp1/container-inspect.json`.
Model: `Qwen/Qwen3.8-27B-FP8`, revision
`017b9c7af6b5689d5dd426a76e0bc077eb5ca20a`, with the canonical direct manifest.
Public image: `ghcr.io/steveseguin/vllm-openai-xpu-qwen38-int4@sha256:7cd7bb16b1fd2e679f0230a38b2f0242fe1c278853867e697c0ce139be2133d2`.
Kernel head: `6d92b1bfbf32767ecda8e819613eb151e70030ad`.
Two B70s; fixed MTP1, full-vocabulary draft-only INT4 head; unchanged official
FP8 target/FP16 activations/native KV. Total capacity 33,024, batch 4,096,
one active sequence, utilization 0.95, requested block 64, prefix caching off.
V1 runner, whole-graph deterministic compile, XPU graphs off, CLASSPAD 0,
ROWCHUNK 32. No candidate patches or draft/capacity matrix.

## Public-source replay and ownership

Publish the helper and this plan before the one functional launch. Download a
GitHub source archive at that exact commit anonymously into a new directory;
record archive and source hashes. Use the public digest-pinned image, allowing
existing verified Docker layers. Reuse the existing model files after fresh
hash verification. This establishes a clean source/state directory on this
configured lab host, not a fresh driver installation, empty Docker cache,
independent-host certification, or a fresh 31 GB model download.

Record host/boot/driver, actual processes/listeners/render-device owners,
image and model verification, source identity, startup logs, container inspect,
health/models replies, compile-cache directory, and stop receipt. Preserve all
artifacts under a new `qwen-fp8-flagship-20260914` raw root, with a compact
hash-bound repository packet. Never overwrite earlier frozen evidence.

The main task owns GPU operations on the two-card host only. Verify CURRENT
and actual GPU availability, hold the exclusive lane lock, run one small
compute/XCCL preflight, then start one persistent server. No restarts or retries,
competing workloads, driver resets, reboots, or power/memory-setting changes.
Check kernel journal for faults; a fault ends new requests. Preserve the separate
four-card LTX service. Stop only the exact owned container once at the end;
run small compute/XCCL and journal postflights after complete teardown.

## Bounded acceptance session

1. Run the unchanged fixed 12-prompt, six-class natural-512 strict suite and
   canaries against the persistent endpoint. Compare complete output token
   arrays against the qualified R304 MTP1 reference at
   `/mnt/fast-ai/bench-results/qwen38-fp8-rebase-v0290-rb1-20260913/mtp1-a/strict`.
   Require 12/12 exact, natural output validity, zero cached tokens, and passing
   canaries. This is one additional replay, not fresh-server pair qualification.
2. Run three practical chat tasks twice: supplied multi-turn conversation
   context, a small code correction explained as JSON, and extraction from a
   supplied document. Use temperature 0, fixed seed, reasoning disabled, answer
   cap 256, one request at a time. Retain full prompts, raw SSE, complete output
   text/token IDs and usage. Require objective semantic checks, complete streams,
   zero cached tokens, and exact repeated outputs. Six requests total; this is
   limited acceptance coverage, not a broad quality or long-running soak claim.
3. Keep HTTP first-token wait and stream-based decode intervals separately
   identified; no new server-prefill headline is inferred from these requests.
   Record decode versus the prior 54.81761811873173 strict reference descriptively;
   differing configured capacity and one process prevent an optimization claim.
4. Check documented status while running, stop from a second terminal using
   the stored container identity, then verify durable stopped status and no
   remaining owned process or listener. Do not restart to repeat this check.

Fail-stop on a failed request, output/usage failure, GPU fault, or startup
failure. Preserve negative results; fix source/docs without cycling the server.
No quality failure may be relabeled a successful acceptance test.

## Publication

Update package/canonical/root READMEs, command metadata, generated Compose,
catalog, details page and homepage entry point. Preserve historical decode and
prefill records with their own identities. Run relevant lifecycle/client,
renderer, guide, container and publication checks, link/path/hash checks,
desktop/mobile/no-JavaScript review, focused main commits and CI/Pages/live
verification. Report practical and strict checks, exact public source commit,
remaining installation limits, and deployment status.
