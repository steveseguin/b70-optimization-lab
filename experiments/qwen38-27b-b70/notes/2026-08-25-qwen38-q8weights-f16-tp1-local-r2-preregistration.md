# Qwen3.8 Q8_0 weights / F16 KV TP1 local r2 preregistration

The earlier r1 packet remains frozen for its intended four-B70 host and absent
source path. This r2 names the exact model and reconstructed llama.cpp binary
that are actually present on the two-B70/15-GiB host. It does not rewrite or
inherit r1 results.

One create-only invocation measures raw `pp2048` and `tg128` at existing
context depths `0/2K/4K/8K/16K/24K/32K`, five repetitions each, on one B70
with Q8_0 weights, F16 KV, flash attention, graph off, and no MTP. There is no
speed floor. A clean allocation failure is the publishable one-card fit
boundary; it does not authorize changing KV precision or dropping the 32K
point under this identity.

After this preregistration is committed and pushed:

```bash
experiments/qwen38-27b-b70/scripts/run-qwen38-q8weights-f16-tp1-local-r2.sh \
  --execute --ack 'RUN qwen38-q8weights-f16-tp1-local-20260825-r2'
```

The exact machine-readable contract is
[`2026-08-25-qwen38-q8weights-f16-tp1-local-r2-prereg.json`](../data/2026-08-25-qwen38-q8weights-f16-tp1-local-r2-prereg.json).
