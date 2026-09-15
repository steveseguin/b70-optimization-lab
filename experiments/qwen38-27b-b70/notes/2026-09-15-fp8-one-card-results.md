# Official Qwen3.8 27B FP8 on one Intel Arc Pro B70

**Official FP8 now runs well on a single B70 without changing any output:
46.9 tokens/s with MTP depth 3 and a 16,384-token context, matching the
no-MTP answers exactly on two fresh servers.** Tested September 15, 2026 on the
qualified R304 image (`sha256:7cd7bb16…`) with the same settings as the two-card
service, changed only to one GPU.

## What made it fit

On one card the model weights take 27.57 GiB and compiled serving had no room
left for the cache (vLLM reported -1.19 GiB). The input embedding table
(248,320 × 5,120 FP16, 2.37 GiB) only turns token IDs into vectors, so it can
live in host memory: the new
[`b70_cpu_embed` plugin](../overlays/b70-cpu-embed/b70_cpu_embed.py) moves it
there after loading and gathers exactly the same rows on the CPU. The output
head and everything else stay on the GPU. It is a vLLM plugin loaded from a
mounted folder with `B70_CPU_EMBED=1`; the image is unchanged.

With the plugin, compiled no-MTP serving had 3.44 GiB for the cache at a 4,096
context (34,304 tokens). With MTP and the draft-only INT4 head, 1.82 GiB remains.

## Results

Settings for every row: one B70, official FP8 weights, FP16 activations and KV,
whole-graph compile, one user, prompt caching off, `--gpu-memory-utilization
0.965`, `--max-num-batched-tokens 4096`. Writing speed is the lab's strict
12-prompt suite (class-balanced median over tokens 1-100).

| MTP depth | Context | Writing speed, tok/s | Output check |
| --- | ---: | ---: | --- |
| 0 | 20,480 | 19.318 | reference |
| 1 | 20,480 | 32.546 / 32.582 | 12/12 identical to depth 0; two fresh servers identical |
| 3 | 16,384 | 46.900 / 46.868 | 12/12 identical to depth 0; two fresh servers identical |
| 4 | 13,312 | 49.706 | 9/12 (three answers split at tokens 127, 160, 479) |
| 5 | 11,264 | 51.705 | 9/12 (same three answers) |

Depth 3 is the fastest setting that passes the lab's exact-output rule. Depths 4
and 5 are faster but change three answers, so they are not qualified. The
context limits come from vLLM's own estimates for each depth (21,632, 16,640 and
11,648 tokens for depths 1, 3 and 5). One-card answers differ from the two-card
service on three prompts late in the answer; that is expected when the matrix
arithmetic is split differently and is why one-card runs are compared with a
one-card no-MTP reference. Prompt-reading (prefill) speed was not measured.

For comparison: the two-card FP8 service writes at 54.9 tok/s (depth 1) and 86.2
(depth 5), and one-card AutoRound INT4 at 81.2 tok/s.

Every run passed its canaries with zero cached tokens, no kernel faults and a
clean host-memory guard.

## Reproduce (research launcher)

```bash
python3 experiments/qwen38-27b-b70/scripts/run-fp8-tp1-server.py \
  --out /path/new-run --port 18133 --mem 0.965 --max-model-len 16384 \
  --batched 4096 --mtp 3 --draft-int4 --cpu-embed --keep
OUT_DIR=/path/new-strict BASE_URL=http://127.0.0.1:18133 MODEL_NAME=qwen38-27b-fp8 \
  bash repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/bench-w8a16-mtp1-strict.sh
```

The launcher builds its environment from the qualified two-card container record
on this host, so it is not yet a self-contained user package. A package would
embed that environment, the plugin and a serve helper like the two-card one.

Evidence: `/mnt/fast-ai/bench-results/optimization-validation-20260915/fp8-tp1-*`
and [copied receipts](../data/2026-09-15-fp8-one-card/).
