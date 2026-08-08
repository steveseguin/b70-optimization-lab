# Qwen3.6 27B MTP Q4_K_M on Intel Arc Pro B70 with llama.cpp SYCL

> **Community contribution by `dominick253`.** The recipe and historical
> measurements are preserved and credited. A separate reference-lab run with
> an official artifact matching the reported filename and byte size now
> validates the narrow one-process/one-B70 recipe and depth claims. The contributor
> packet still has a 150K/175K identity mismatch. Read [STATUS.md](STATUS.md)
> before use.

## Contributor report

The contributor reports two independent llama.cpp/SYCL processes, one per B70,
serving a Qwen3.6-27B MTP Q4_K_M GGUF. The reported engine commit is
`15586e2d7165570fb3aa7c26e0d442e289ef69de`, with F16 target/draft KV,
Flash Attention, one slot per process, and a maximum of two MTP draft tokens.

The GGUF was reported as 17,106,773,120 bytes without a revision or SHA-256.
The reference lab selected an official artifact with the same filename and
exact byte size from `unsloth/Qwen3.6-27B-MTP-GGUF`, revision
`5cb35eb3dcbf52dbce5f87dbc64df6aaffadcace`, SHA-256
`a7cbd3ecc0e3f9b333edee61ae66bc87ed713c5d49587a8355814722ed329e0f`.
Because the contributor supplied neither a revision nor a hash, this does not
cryptographically establish that both hosts used identical model bytes.
The contributor head's launcher/table say 175,000 context while its retained
inspection finding says 150,000. The lab requested 150,000 and retained a
completed 120,000-prompt plus 128-output row.

## Packet layout

- [`reported/exact-contributor-launcher.sh`](reported/exact-contributor-launcher.sh):
  contributor head's final 175K launcher, retained verbatim.
- [`reported/benchmarks/qwen36-27b-mtp-b70.md`](reported/benchmarks/qwen36-27b-mtp-b70.md):
  historical summary without raw JSON/CSV/logs.
- [`llama-qwen36-27b-mtp.sh`](llama-qwen36-27b-mtp.sh): maintainer-hardened
  launcher requiring an explicit context and model SHA-256, validating GPU and
  port inputs, and permitting loopback only.
- [`validation/`](validation/): maintainer offline review and
  matching-name-and-size-model reference-lab validation.

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

## Reference-lab result

The matching-name-and-size official artifact and exact engine commit ran in
one process on one B70. A fixed greedy MTP2 request produced the same visible
128-token response bytes as its target-only control and improved
that 128-token decode from 25.31 to 38.11 tok/s. Exact 2K, 32K, and 120K token
prompts completed at 33.41, 24.75, and 16.03 decode tok/s. See
[`validation/2026-08-08-reference-lab-validation.md`](validation/2026-08-08-reference-lab-validation.md).

The packet is `B70-tested`, but still needs a realistic cold suite and a
long-context retrieval gate before any promotion beyond `community/`.
