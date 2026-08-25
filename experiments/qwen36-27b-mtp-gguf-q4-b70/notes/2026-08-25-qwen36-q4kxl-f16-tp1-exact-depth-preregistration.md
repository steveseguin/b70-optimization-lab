# Qwen3.6 UD-Q4_K_XL F16-KV TP1 exact-depth preregistration

Date: 2026-08-25. State: **preregistered; not launched**.

This packet targets seven missing cells in the Qwen3.6 llama.cpp/SYCL
target-only matrix: UD-Q4_K_XL, TP1, MTP0, graph off, F16 K/V cache, and exact
active depths `0`, `2048`, `4096`, `8192`, `16384`, `24576`, and `32768`.
The family contract currently resolves every one of those selectors only to
its default `missing` rule. The historical 4K-configured serving row used a
different runtime and only requested graph use; it is not an exact active-depth
or graph-off substitute.

## Exact model identity

The older download originally lacked a recorded Hugging Face commit. This
packet closes that identity gap without borrowing the sibling Q4_K_M identity:
Hugging Face blobs metadata at repository revision
`5cb35eb3dcbf52dbce5f87dbc64df6aaffadcace` reports
`Qwen3.6-27B-UD-Q4_K_XL.gguf` as 17,909,097,600 bytes with LFS SHA-256
`4085665ee36d82a672a238a43f0e5643f2f0e39f2d7bd5d373f0ef10ecf53095`.
The local read-only artifact matches both fields. The revision binding is
therefore filename-and-byte exact even though that commit was not captured at
the original July download time. The immutable-revision blobs API URL is
recorded in the machine-readable preregistration.

## Frozen measurement and preservation boundaries

One `llama-bench` invocation uses one B70, target-only MTP0, graph off, F16
K/V, FlashAttention on, `pp2048`, `tg128`, and five repetitions. A complete
parser and lifecycle pass may add exactly seven raw-engine cells. It is not an
HTTP-serving benchmark and does not run or transfer a new quality battery.

The wrapper inherits the checksum-pinned Qwen3.8 lifecycle infrastructure used
by the successful exact-depth curve, while binding Qwen3.6 selectors and this
exact artifact. It owns all four current and legacy coordination locks and
rejects `llama-batched-bench` in addition to ordinary llama/vLLM model
processes. The output root is fresh, ext4, and create-only.

There is no minimum speed gate. A slower depth point remains evidence for this
exact cell and cannot lower, overwrite, or relabel any featured, promoted, or
historical decode result. No measurement transfers across revisions,
quantizations, MTP modes, graph modes, KV types, or runtime identities.

## Launch

After these files are committed and pushed on clean `main`, and only when the
canonical locks and GPU0 are idle:

```bash
python3 -B experiments/qwen36-27b-mtp-gguf-q4-b70/scripts/run-20260825-qwen36-q4kxl-f16-tp1-exact-depth-r1.py \
  --execute \
  --ack 'RUN qwen36-q4kxl-f16-tp1-exact-depth-20260825-r1'
```

The default invocation is inert; `--check` performs only static CPU checks.
