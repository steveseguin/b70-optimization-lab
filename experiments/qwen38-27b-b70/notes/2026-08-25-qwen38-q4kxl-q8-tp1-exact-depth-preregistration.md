# Qwen3.8 UD-Q4_K_XL q8_0-KV TP1 exact-depth r1

Status: **preregistered, runnable after live gates, not launched**.

This packet replaces the seven matching grade-D estimates with measurements
only if one frozen `llama-bench` invocation and the exact-depth parser pass at
active depths `0/2048/4096/8192/16384/24576/32768`. It is Qwen3.8
UD-Q4_K_XL, TP1, MTP0, graph off, q8_0 K/V on one B70. It does not qualify
HTTP serving, add a quality result, or alter the artifact's existing separate
quality evidence.

The target is
`unsloth/Qwen3.8-27B-GGUF@4ca720788d1e01f1bff70c033e0d0028fd02e502`,
file SHA-256
`3f227079003add2511437e5b1e94812e363385225bf6a9b47b0054a72bc8b01e`.
The runtime is the clean llama.cpp source at
`fa0f3b25a47f346858a4d0d169f5181aa424b110`; `llama-bench` SHA-256 is
`908b78b77fc28ad23b2924b7f32f56f4a8415eac9c2a79a244dee85b49b19030`.
The manifest freezes all 32 effective shared libraries after clean oneAPI
2026.0 setup, including the benchmark implementation and every local
llama/ggml DSO.

## Frozen invocation

```text
/home/steve/src/llama.cpp-q38-tp1-lane/build-sycl-aot-bmg-g31/bin/llama-bench -m /mnt/usb-models/llm-models/qwen3.8-27b-unsloth-gguf/Qwen3.8-27B-UD-Q4_K_XL.gguf -dev SYCL0 -ngl 99 -sm layer -p 2048 -n 128 -d 0,2048,4096,8192,16384,24576,32768 -b 2048 -ub 512 -fa on -ctk q8_0 -ctv q8_0 -t 16 --poll 50 -r 5 -o json
```

The launcher rejects inherited accelerator/runtime variables, constructs a
clean oneAPI environment, selects only `level_zero:0`, and explicitly sets
`GGML_SYCL_ENABLE_GRAPH=0`. The complete accepted TP1 runtime-door set is
frozen in the manifest; no caller override is accepted.

## Lifecycle

The default mode and `--check` are inert. Execution requires the exact
acknowledgement, clean pushed `main`, the exact clean source/model/binary/DSO
identities, all three host/GPU locks, no model server or running container,
an idle GPU0 render node, and a fresh ext4 output root. Artifacts are
create-only. The run is bounded to one hour and produces a terminal receipt
after process/container/render-node cleanup checks.

```bash
python3 -B experiments/qwen38-27b-b70/scripts/run-20260825-qwen38-q4kxl-q8-tp1-exact-depth-r1.py --check
python3 -B experiments/qwen38-27b-b70/scripts/run-20260825-qwen38-q4kxl-q8-tp1-exact-depth-r1.py
python3 -B experiments/qwen38-27b-b70/scripts/run-20260825-qwen38-q4kxl-q8-tp1-exact-depth-r1.py \
  --execute \
  --ack 'RUN qwen38-q4kxl-q8-tp1-exact-depth-20260825-r1'
```

Output is fixed at
`/mnt/fast-ai/bench-results/qwen38-q4kxl-q8-tp1-exact-depth-20260825-r1`.
A retry needs a new packet and root; this launcher never overwrites r1.

There is no speed floor. A correct slow curve is still measured evidence.
The run cannot lower, relabel, or replace any featured or historical speed;
it can supersede only the seven same-selector grade-D estimates after all
seven exact cells pass. Raw-engine prefill/decode values remain distinct from
the site's conventional HTTP-serving metrics.

