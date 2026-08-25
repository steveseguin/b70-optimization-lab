# Qwen3.6 Q4_K_M F16-KV TP1 exact-depth preregistration

Date: 2026-08-25. State: **preregistered; not launched**.

This is the next dense Qwen3.6 TP1 packet after the Q4_0 q8_0-KV r1 arm. It
targets the independently registered Q4_K_M child at repository revision
`5cb35eb3dcbf52dbce5f87dbc64df6aaffadcace`, 17,106,773,120 bytes, SHA-256
`a7cbd3ecc0e3f9b333edee61ae66bc87ed713c5d49587a8355814722ed329e0f`.
The file is already present on the read-only USB model store.

One frozen `llama-bench` invocation measures target-only MTP0 at exact active
depths `0`, `2048`, `4096`, `8192`, `16384`, `24576`, and `32768`. It uses
one B70, graph off, F16 K/V cache, FlashAttention on, `pp2048`, `tg128`, and
five repetitions. Passing the complete parser and lifecycle gate adds exactly
seven raw-engine cells. It neither measures HTTP serving nor runs a fresh
quality battery.

## Runtime choice and progress preservation

The packet reuses the exact checksum-pinned llama.cpp source, binary, shared
libraries, graph-off environment, canonical locks, idle checks, parser, and
create-only lifecycle that already completed the Qwen3.8 Q4XL exact-depth
curve. The referenced manifest and adapter hashes are frozen. This transfers
infrastructure only: no Qwen3.8 model bytes, speed, quality result, selector,
or estimate is inherited.

The Qwen3.6 wrapper closes two later-discovered coordination gaps in that
adapter: it also owns `/tmp/b70-gpu0.lock`, and its corrected process census
explicitly rejects `llama-batched-bench` as well as llama/vLLM serving and
benchmark processes.

This choice avoids depending on build 9976's absent stderr markers, which made
the earlier Q4_0 r1 arm fail closed after completing all raw rows. Graph-off is
instead bound by the controlled `GGML_SYCL_ENABLE_GRAPH=0` environment and the
same parser contract that produced the successful Qwen3.8 exact-depth receipt.
The source, executable, model, and effective shared-library identities all
remain hard preflight gates.

There is no minimum speed gate. A slower measured context point is evidence,
not a reason to lower or overwrite any featured, promoted, or historical
decode result. The packet fills only its seven currently missing Qwen3.6
Q4_K_M/F16 cells, and no result transfers across quantization or weight
revision.

## Launch

After these new files are committed and pushed on clean `main`, and only when
the canonical locks and GPU0 are idle:

```bash
python3 -B experiments/qwen36-27b-mtp-gguf-q4-b70/scripts/run-20260825-qwen36-q4km-f16-tp1-exact-depth-r1.py \
  --execute \
  --ack 'RUN qwen36-q4km-f16-tp1-exact-depth-20260825-r1'
```

The default invocation is inert; `--check` performs only static CPU checks.
