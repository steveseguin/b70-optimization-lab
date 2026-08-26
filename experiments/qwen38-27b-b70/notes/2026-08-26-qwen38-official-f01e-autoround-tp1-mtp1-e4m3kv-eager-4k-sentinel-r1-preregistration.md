# TP1/MTP1 eager E4M3-KV exact-4K sentinel R1 preregistration

This packet changes only KV cache dtype relative to the clean TP1/MTP1 eager F16 mechanism at exact 4K. It launches the current-f01e image with native embedded MTP1, eager execution, and `--kv-cache-dtype fp8_e4m3` for one exact-4K sentinel.

The token oracle is the same-image TP1/MTP0/eager/E4M3 exact-4K receipt (`a3d7ad63...`), not the F16 token stream. The TP1/MTP1/eager/F16 4K receipt is pinned only as evidence that native MTP1 boots and produces isolated positive acceptance (`56/71`) on this image. A candidate pass requires exact/cache-zero measurement, positive conserved drafting and acceptance, equality of all 128 tokens to the E4M3 target, full objective and baseline quality, exact TP1/eager/E4M3/native-MTP1 startup identity, model verification, fresh cache/output roots, and strict cleanup.

The packet is inert by default and grants no publication, replacement, descendant, or other-cell authority. Only 4K is selected. Historical 8K cross-boot/speculative divergence means no success here may be generalized automatically.

Static validation:

```bash
experiments/qwen38-27b-b70/scripts/run-20260826-qwen38-official-f01e-autoround-tp1-mtp1-e4m3kv-eager-4k-sentinel-r1.sh --check
```

Authorized launch form after a clean pushed `main`:

```bash
experiments/qwen38-27b-b70/scripts/run-20260826-qwen38-official-f01e-autoround-tp1-mtp1-e4m3kv-eager-4k-sentinel-r1.sh \
  --execute \
  --ack 'RUN qwen38-official-f01e-autoround-tp1-mtp1-e4m3kv-eager-4k-sentinel-20260826-r1'
```
