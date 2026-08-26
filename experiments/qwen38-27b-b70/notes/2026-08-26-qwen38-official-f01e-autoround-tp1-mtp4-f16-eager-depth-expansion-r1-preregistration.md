# Official f01e AutoRound TP1 eager MTP4/F16 depth expansion R1

Status: **preregistered and executable; not launched**.

The identical current-f01e TP1/MTP4/eager/F16 parent passed exact 8K at
`15.694764790035633 tok/s`, accepted `92/140` isolated drafts
(`65.7143%`), matched all 128 frozen MTP0 tokens, passed the full quality
battery, and cleaned up. Its terminal receipt is pinned by SHA-256 here.

This one server lifetime keeps the exact native embedded MTP binding: no
external draft artifact, the same revision-pinned target repository, all 29
`mtp.*` tensors in pinned `model_extra_tensors.safetensors`, one trained MTP
module recurrently reused for four steps, requested `qwen3_next_mtp` depth
four resolving to `mtp`, F16/auto KV, explicit eager mode, and no graph.

Exact active contexts 2K, 4K, 8K, 16K, 24K, and 32K each get an independent
128-token receipt. Immediately before and after every individual request, the
runner snapshots speculative metrics. That depth passes mechanism engagement
only when drafted delta is positive, accepted delta is positive, and accepted
does not exceed drafted. Traffic from startup, another depth, or the later
quality suite cannot satisfy its counter gate.

Each candidate's 128 token IDs must exactly equal the corresponding frozen
same-image TP1/MTP0/eager/F16 R3 receipt. All six raw receipts and token hashes
are pinned. A mismatch quarantines the expansion; because the comparison is
cross-boot and target compile variability exists, it does not alone prove
causal MTP corruption.

After all six depths, the same server runs the complete frozen quality battery.
All six depth gates, all six acceptance gates, all six target oracles, full
quality, exact startup identity, and strict cleanup must pass for
`passed-quality-clean-expansion`. Partial passing receipts remain screened
evidence rather than disappearing.

The runner requires clean pushed `main`, exact f01e image/source/package,
native MTP artifact/config/index, parent authorization receipt, six target
oracles, model verification, frozen helpers/baseline, fresh ext4 roots, port
`19474`, an idle host, the canonical GPU lock, global EXIT/INT/TERM cleanup,
and strict postflight.

There is no speed floor. Results are additive and cannot replace protected
values. Site publication is separate and failed gates have no speed authority.

Static check:

```bash
experiments/qwen38-27b-b70/scripts/run-20260826-qwen38-official-f01e-autoround-tp1-mtp4-f16-eager-depth-expansion-r1.sh --check
```

GPU execution:

```bash
experiments/qwen38-27b-b70/scripts/run-20260826-qwen38-official-f01e-autoround-tp1-mtp4-f16-eager-depth-expansion-r1.sh \
  --execute \
  --ack 'RUN qwen38-official-f01e-autoround-tp1-mtp4-f16-eager-depth-expansion-20260826-r1'
```
