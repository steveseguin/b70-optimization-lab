# Embedded-Q8 F16 TP1 MTP route 8K sentinel R2

R1 stopped before any GPU or server launch because its exact DSO gate searched
for each SONAME at column zero. Real `ldd` output indents those rows, so the
first exact library was falsely reported missing. The immutable R1 root and
terminal remain preserved; R1 grants no route or speed authority.

R2 is a fresh create-only retry. Its sole execution change is:

```text
^{soname}\s+=>\s+(\S+)
^\s*{soname}\s+=>\s+(\S+)
```

Canonical resolved-path equality, exact binary and eight-DSO hashes and sizes,
the runtime-origin closed set, model, environment, five fresh MTP0/1/2/3/4
lifetimes, exact 8K 128-token parity, draft conservation, cleanup, and frozen
authority are unchanged. No R1 measurement row is reused.

The default command is inert:

```bash
python3 -B experiments/qwen36-27b-mtp-gguf-q4-b70/scripts/run-20260825-qwen36-mtpq8-f16-tp1-mtp-route-8k-sentinel-r2.py --check
```

The separately acknowledged future launch is:

```bash
python3 -B experiments/qwen36-27b-mtp-gguf-q4-b70/scripts/run-20260825-qwen36-mtpq8-f16-tp1-mtp-route-8k-sentinel-r2.py \
  --execute \
  --ack 'RUN qwen36-mtpq8-f16-tp1-mtp-route-8k-sentinel-20260825-r2'
```

R2 writes only to
`/mnt/fast-ai/bench-results/qwen36-mtpq8-f16-tp1-mtp-route-8k-sentinel-20260825-r2`.
It cannot edit the site, replace protected speeds, or change the successful
MTP3 R3 result.
