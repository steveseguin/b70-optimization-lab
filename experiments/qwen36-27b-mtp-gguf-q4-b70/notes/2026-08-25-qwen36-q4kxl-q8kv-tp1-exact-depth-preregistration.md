# Qwen3.6 UD-Q4_K_XL q8_0-KV TP1 exact-depth preregistration

## Question

What are the raw target-only prefill and decode rates for the seven currently
missing Qwen3.6 UD-Q4_K_XL, TP1, MTP0, graph-off, q8_0-KV exact active-context
cells at 0/2K/4K/8K/16K/24K/32K?

## Frozen identity

- Model: `unsloth/Qwen3.6-27B-MTP-GGUF` at
  `5cb35eb3dcbf52dbce5f87dbc64df6aaffadcace`.
- Artifact: `Qwen3.6-27B-UD-Q4_K_XL.gguf`, 17,909,097,600 bytes,
  SHA-256 `4085665ee36d82a672a238a43f0e5643f2f0e39f2d7bd5d373f0ef10ecf53095`.
- Runtime: the checksum-pinned llama.cpp/SYCL lifecycle and shared-library
  inventory inherited from the preregistered Qwen3.6 UD-Q4_K_XL F16 packet.
- Selectors: TP1, MTP0, graph off, q8_0 K/V, depths
  `0,2048,4096,8192,16384,24576,32768`.
- Workload: one `llama-bench` invocation, prompt 2048, generation 128,
  batch 2048, ubatch 512, FlashAttention on, 16 threads, poll 50, five repeats.

This packet changes only the KV cache selector and its fresh campaign/output
identity. It transfers no F16 measurement, speed, quality conclusion, or
cross-revision claim.

## Safety and interpretation

The runner is inert without the exact acknowledgement, refuses a dirty or
unpushed `main`, uses create-only artifacts on ext4, checks the protected
historical metric manifest, rejects active `llama-bench`,
`llama-batched-bench`, `llama-server`, and vLLM processes, and acquires all
four canonical host/GPU0 locks before preflight and launch.

A complete passing receipt fills only these seven exact cells. There is no
speed floor and no new semantic quality claim; artifact quality remains
separate. Failure closes this r1 identity without publication or automatic
retry. Historical featured speeds remain immutable.

## Launch command

Only after every other GPU campaign has reached a clean terminal state and
GPU0 plus all four locks are idle:

```bash
python3 -B experiments/qwen36-27b-mtp-gguf-q4-b70/scripts/run-20260825-qwen36-q4kxl-q8kv-tp1-exact-depth-r1.py \
  --execute \
  --ack 'RUN qwen36-q4kxl-q8kv-tp1-exact-depth-20260825-r1'
```
