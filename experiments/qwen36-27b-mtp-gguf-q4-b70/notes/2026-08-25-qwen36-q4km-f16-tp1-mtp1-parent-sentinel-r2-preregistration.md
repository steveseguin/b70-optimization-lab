# Qwen3.6 Q4_K_M F16-KV TP1 MTP1 parent sentinel R2 preregistration

R2 is a fresh two-arm rerun. It changes only the create-only campaign identity
and the interpreter used by the candidate quality client. R1 remains preserved,
failed, and ineligible for row reuse.

R1's control and candidate exact-depth requests each passed, but the captured
output-token hashes differed. The quality battery then served four exact
canaries and two repeat requests before its deferred tokenizer import failed;
no `quality.json` was persisted and the 8K needle did not run. R2 therefore has
no presumption of success. It must freshly pass target-output parity as well as
the complete quality battery.

The quality client alone uses
`/home/steve/.venvs/vllm-xpu/bin/python`. Preflight binds Python `3.12.13`, the
interpreter realpath/hash and `sys.prefix`, Transformers `5.10.2`, Tokenizers
`0.22.2`, NumPy `2.3.5`, and each distribution's METADATA hash. An isolated,
offline `AutoTokenizer.from_pretrained(..., local_files_only=True)` probe must
load the pinned Qwen tokenizer and reproduce the preregistered 22 token IDs and
hash. Exact-depth and terminal-validation clients retain the R1 interpreters.
The quality client's stderr is captured as a required R2 artifact.

The R1 runner is checksum-pinned and transformed with exact replacement-count
gates into a temporary R2 runner. Its transformed hash and the complete quality
environment capability record are checksum-gated and captured in `identity.txt`. All hardened R1
locks, DSO closure, readiness, bounded shutdown, signal, exact-depth, cache,
draft-engagement, parity, quality, and cleanup gates remain unchanged.

R2 uses
`/mnt/fast-ai/bench-results/qwen36-q4km-f16-tp1-mtp1-parent-8192-20260825-r2`.
The R1 root is read-only and no receipt may transfer.

Static check:

```bash
bash experiments/qwen36-27b-mtp-gguf-q4-b70/scripts/run-20260825-qwen36-q4km-f16-tp1-mtp1-parent-sentinel-r2.sh --check
```

Exact launch:

```bash
bash experiments/qwen36-27b-mtp-gguf-q4-b70/scripts/run-20260825-qwen36-q4km-f16-tp1-mtp1-parent-sentinel-r2.sh \
  --execute \
  --ack 'RUN qwen36-q4km-f16-tp1-mtp1-parent-8192-20260825-r2'
```

A pass fills zero matrix cells and authorizes only a separately preregistered
seven-depth MTP1 HTTP-serving curve. Any failure, including another parity
mismatch, preserves R2 and does not authorize expansion or a site edit.
