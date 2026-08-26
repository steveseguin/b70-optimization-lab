# Official f01e AutoRound TP1 E4M3-KV exact-depth expansion R1

Status: **preregistered and executable; not launched**.

The preceding f01e AutoRound TP1/MTP0/eager E4M3-KV sentinel closed green:
its exact 8K receipt passed at `11.824452787933243 tok/s`, the complete quality
battery passed with all frozen-baseline comparisons matching, and strict
cleanup passed. Its terminal receipt is pinned by SHA-256 in this runner. That
separately completed low-dose gate authorizes this exact-depth expansion; it
does not authorize graph, MTP, or TP descendants.

This packet keeps the identical immutable image, model revision, TP1/MTP0,
explicit eager mode, E4M3 KV dtype, server sizing, GPU0 selection, and quality
contract. One server lifetime measures exact active contexts 2K, 4K, 8K, 16K,
24K, and 32K, each with 128 generated tokens and the conventional first-100
event/99-interval metric. The complete frozen quality battery runs after all
six depth requests on the same server.

Every depth has an independent receipt and return code. All six plus the full
quality battery and strict cleanup must pass for
`passed-quality-clean-expansion`. Passing depths remain screened evidence if
another depth fails. If all depths pass but quality fails, measurements are
quarantined. Historical E4M3 and F16 speeds are immutable; all new values are
additive profile-specific evidence and site publication is separate.

The runner requires clean pushed `main`, exact frozen hashes, the successful
sentinel authorization receipt, the exact resident f01e image/source/package
identity, direct model verification, fresh ext4 roots, port `19469`, no active
container/model server/render owner, and the canonical GPU lock. The exact
container has global EXIT/INT/TERM cleanup and strict postflight checks.

Static checks:

```bash
experiments/qwen38-27b-b70/scripts/run-20260826-qwen38-official-f01e-autoround-tp1-e4m3kv-depth-expansion-r1.sh --check
```

GPU execution:

```bash
experiments/qwen38-27b-b70/scripts/run-20260826-qwen38-official-f01e-autoround-tp1-e4m3kv-depth-expansion-r1.sh \
  --execute \
  --ack 'RUN qwen38-official-f01e-autoround-tp1-e4m3kv-depth-expansion-20260826-r1'
```
