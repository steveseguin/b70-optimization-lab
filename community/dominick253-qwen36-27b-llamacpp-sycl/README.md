# Qwen3.6 27B MTP Q4_K_M on Intel Arc Pro B70 with llama.cpp SYCL

> **Community contribution by `dominick253`.** The recipe and historical
> measurements are preserved and credited, but no matching model run occurred
> in the repository's reference lab. Maintainer review found an unresolved
> 150K/175K identity mismatch. Read [STATUS.md](STATUS.md) before use.

## Contributor report

The contributor reports two independent llama.cpp/SYCL processes, one per B70,
serving a Qwen3.6-27B MTP Q4_K_M GGUF. The reported engine commit is
`15586e2d7165570fb3aa7c26e0d442e289ef69de`, with F16 target/draft KV,
Flash Attention, one slot per process, and a maximum of two MTP draft tokens.

The GGUF was reported as 17,106,773,120 bytes, but its model revision and
SHA-256 were not supplied. The contributor head's launcher/table say 175,000
context while its retained inspection finding says 150,000. Neither context is
treated as the independently confirmed current identity.

## Packet layout

- [`reported/exact-contributor-launcher.sh`](reported/exact-contributor-launcher.sh):
  contributor head's final 175K launcher, retained verbatim.
- [`reported/benchmarks/qwen36-27b-mtp-b70.md`](reported/benchmarks/qwen36-27b-mtp-b70.md):
  historical summary without raw JSON/CSV/logs.
- [`llama-qwen36-27b-mtp.sh`](llama-qwen36-27b-mtp.sh): maintainer-hardened
  launcher requiring an explicit context and model SHA-256, validating GPU and
  port inputs, and permitting loopback only.
- [`validation/`](validation/): maintainer offline review; no model run.

## Safe dry run

```bash
LLAMA_ROOT=/path/to/llama.cpp-at-15586e2d7 \
MODEL=/path/to/Qwen3.6-27B-Q4_K_M.gguf \
EXPECTED_MODEL_SHA256=<64-hex-sha256> \
EXPECTED_SERVER_SHA256=<64-hex-sha256> \
CTX_SIZE=150000 \
DRY_RUN=1 \
bash llama-qwen36-27b-mtp.sh
```

Choose `CTX_SIZE` deliberately after confirming the intended identity and
memory budget. The launcher also checks the reported llama.cpp commit, rejects
tracked source changes, and verifies both the model and server binary hashes.
Inspect the dry-run output before removing `DRY_RUN=1`. It defaults to
`127.0.0.1:18020` and does not install or enable systemd units.

## Historical reported measurements

The summary reports context depths 2K through 120K, one 128-token completion
per point, greedy temperature 0.0, and draft maxima 1 or 2. The reported service
defaults use temperature 0.6 and draft maximum 2, so the summary is not a
matching validation of that live configuration. It is retained as community
history, not a promoted performance result.

## What is needed next

1. exact GGUF repository revision and SHA-256;
2. one chosen context identity and captured runtime command;
3. raw matching benchmark JSON/logs with cold/cache policy and token hashes;
4. a deterministic target-only teacher plus MTP exactness/acceptance gate; and
5. long-context retrieval, next-request, teardown, and device-error checks.

Only a later maintainer-produced run under `validation/<date>/` can raise this
packet above `community-reported`.
