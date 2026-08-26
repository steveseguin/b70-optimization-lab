# Qwen3.8 Q5_K_S target-only HTTP exact-depth + quality R1

This create-only packet measures the current Qwen3.8 27B UD-Q5_K_S target on
one B70 at TP1, MTP0, graph off, fit off, and Q8_0 K/V. One fresh
`llama-server` lifetime receives exact active-context requests at
0/2/4/8/16/24/32K, each returning 128 token IDs with cache-zero enforcement,
followed by the complete Qwen3.8 quality battery.

The 8K row must reproduce the successful target-only control hash
`e2f7a659…e141c` from the sealed external-MTP route sentinel. The x=0 point is
zero prior active context plus one explicit ordinary token; it is not a literal
empty prompt. Positive depths are exact submitted token counts. The context
fixture is synthetic repeated-token Grade C evidence; full semantic, repeat,
and long-context quality are separate mandatory gates.

If every gate and cleanup check passes, the validator authorizes exactly seven
target-only HTTP serving-curve cells. It authorizes no MTP, TP2/TP4, prefill,
headline, protected-speed replacement, or LocalMaxxing claim. In particular,
the protected decode values recorded in the manifest remain immutable.

Static check (inert):

```bash
python3 -B experiments/qwen38-27b-b70/scripts/run-20260825-qwen38-q5ks-q8kv-tp1-target-http-depth-quality-r1.py --check
```

Execution requires clean pushed `main`, all host/GPU locks, an idle GPU0 render
node, a new ext4 result root, and the exact acknowledgement:

```bash
python3 -B experiments/qwen38-27b-b70/scripts/run-20260825-qwen38-q5ks-q8kv-tp1-target-http-depth-quality-r1.py \
  --execute \
  --ack 'RUN qwen38-q5ks-q8kv-tp1-target-http-depth-quality-20260825-r1'
```
