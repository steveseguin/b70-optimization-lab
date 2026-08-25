# Qwen3.8 Q8_0-weight/F16-KV TP1 exact-depth r1

Status: **preregistered, awaiting exact model staging, not launched**.

This packet fills seven currently missing cells only if one frozen
`llama-bench` invocation and the exact-depth parser pass at active depths
`0/2048/4096/8192/16384/24576/32768`. Its selector is Qwen3.8 ggml-org
Q8_0 weights, TP1, MTP0, graph off, and F16 K/V on one B70. It does not
qualify HTTP serving, create new model-quality evidence, or alter an existing
featured speed.

## Why F16 KV is first

The existing matched TP1 Q4_K_M sweep found F16 KV faster at every depth;
q8_0 KV fell from a 2% decode penalty at depth zero to 51% at 32K. For this
architecture, 32K F16 KV is exactly 2.0 GiB (16 full-attention layers, four
KV heads, head dimension 256, K plus V). The Q8_0 file is 26.63 GiB, leaving
about 2.87 GiB of paper headroom on a 31.5-GiB card before compute buffers.
That is a plausible but unmeasured fit, so allocation failure remains a real
risk. A clean allocation failure closes r1 as a bounded fit result; it does
not authorize an in-place q8_0-KV substitution or retry.

## Frozen identities and staging prerequisite

The exact model is `ggml-org/Qwen3.8-27B-GGUF` revision
`0669b98607d47046c7c2b3f801011d54a08cfccf`, 28,595,763,552 bytes, SHA-256
`f5c702d8820d36fb55985bb238fc83ee3a313e920f4b752a437c3a6a9e14e4c8`.
It was not present on this host at preregistration. Before execution it must
be staged at:

```text
/mnt/usb-models/models/qwen3.8-27b-gguf/Qwen3.8-27B-Q8_0.gguf
```

The launcher hashes the full file before creating a run root. The USB volume
was mounted read-only during packet preparation; this packet does not remount
it or download weights.

The runtime is the clean llama.cpp source at
`fa0f3b25a47f346858a4d0d169f5181aa424b110`; `llama-bench` SHA-256 is
`908b78b77fc28ad23b2924b7f32f56f4a8415eac9c2a79a244dee85b49b19030`.
The 32-library runtime inventory and certified lifecycle implementation are
referenced by path and immutable SHA-256, then revalidated by the wrapper.

## Frozen invocation

```text
/home/steve/src/llama.cpp-q38-tp1-lane/build-sycl-aot-bmg-g31/bin/llama-bench -m /mnt/usb-models/models/qwen3.8-27b-gguf/Qwen3.8-27B-Q8_0.gguf -dev SYCL0 -ngl 99 -sm layer -p 2048 -n 128 -d 0,2048,4096,8192,16384,24576,32768 -b 2048 -ub 512 -fa on -ctk f16 -ctv f16 -t 16 --poll 50 -r 5 -o json
```

The wrapper adds the post-race canonical `/tmp/b70-gpu0.lock` while retaining
the host-wide Muse lock, host-wide benchmark lock, and legacy Qwen GPU lease.
It also excludes `llama-batched-bench` explicitly during process scans.

## Launch lifecycle

Default mode and `--check` are CPU-only and inert:

```bash
python3 -B experiments/qwen38-27b-b70/scripts/run-20260825-qwen38-q8weights-f16-tp1-exact-depth-r1.py --check
```

After the exact model is staged, execution requires clean pushed `main`, idle
GPU0, no model process or running container, all four locks, and this exact
acknowledgement:

```bash
python3 -B experiments/qwen38-27b-b70/scripts/run-20260825-qwen38-q8weights-f16-tp1-exact-depth-r1.py \
  --execute \
  --ack 'RUN qwen38-q8weights-f16-tp1-exact-depth-20260825-r1'
```

Output is create-only at
`/mnt/fast-ai/bench-results/qwen38-q8weights-f16-tp1-exact-depth-20260825-r1`.
There is no speed floor: a valid slow curve remains evidence. A passing receipt
can fill only the seven matching missing Q8_0-weight/F16-KV raw-engine cells.
