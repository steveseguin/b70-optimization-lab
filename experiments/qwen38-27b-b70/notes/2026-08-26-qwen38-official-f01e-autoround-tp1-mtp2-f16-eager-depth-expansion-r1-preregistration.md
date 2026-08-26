# Official f01e AutoRound TP1 eager MTP2/F16 depth expansion R1

Status: **preregistered and executable; not launched**.

The identical current-f01e TP1/MTP2/eager/F16 parent passed exact 8K at
`11.648189531678828 tok/s` under historical 100-event accounting
(`11.53170763636204` conventional), accepted `82/94` isolated drafts
(`87.2340%`), passed the full quality battery, and cleaned up. It did not match
the frozen MTP0 output: the first divergence was token 99. Its quarantined
terminal receipt is pinned by SHA-256 here.

That receipt deliberately authorizes no descendant. The user's coverage policy
separately authorizes this lower-grade diagnostic/per-depth expansion. It can
classify and retain each measured point, but can never replace historical speed
or correctness evidence and does not automatically authorize publication.

This one server lifetime keeps the exact native embedded MTP binding: no
external draft artifact, the same revision-pinned target repository, all 29
`mtp.*` tensors in pinned `model_extra_tensors.safetensors`, one trained MTP
module recurrently reused for two steps, requested `qwen3_next_mtp` depth
two resolving to `mtp`, F16/auto KV, explicit eager mode, and no graph.

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
`passed-diagnostic-quality-clean-expansion`. Partial passing receipts remain
screened evidence rather than disappearing.

The MTP4 expansion on this same current image killed EngineCore at 32K on the
speculative-token shape assertion. That does not predict MTP2's outcome. This
runner nevertheless classifies a nonzero 32K request plus an EngineCore fatal
marker as `failed-32k-engine-fatal`, preserves the partial depth receipts,
skips impossible post-fatal quality traffic, and still requires global cleanup.

The runner requires clean pushed `main`, exact f01e image/source/package,
native MTP artifact/config/index, parent authorization receipt, six target
oracles, model verification, frozen helpers/baseline, fresh ext4 roots, port
`19478`, an idle host, the canonical GPU lock, global EXIT/INT/TERM cleanup,
and strict postflight.

There is no speed floor. Results are additive and cannot replace protected
values. Site publication is separate and failed gates have no speed authority.

Static check:

```bash
experiments/qwen38-27b-b70/scripts/run-20260826-qwen38-official-f01e-autoround-tp1-mtp2-f16-eager-depth-expansion-r1.sh --check
```

GPU execution:

```bash
experiments/qwen38-27b-b70/scripts/run-20260826-qwen38-official-f01e-autoround-tp1-mtp2-f16-eager-depth-expansion-r1.sh \
  --execute \
  --ack 'RUN qwen38-official-f01e-autoround-tp1-mtp2-f16-eager-depth-expansion-20260826-r1'
```
