# Official f01e AutoRound TP1 PIECEWISE MTP2/F16 exact-4K sentinel R1

Status: **preregistered and executable; not launched**.

This is one corruption-sensitive parent probe for the exact current-f01e
TP1/PIECEWISE/native-MTP2/F16 tuple. It measures only exact 4K. It does not
authorize a context ladder, another MTP depth, TP2/TP4, a KV variant, site
publication, record replacement, or an automatic follow-up run.

Its exact pending family selector is the existing
`qwen38-tp1-vllm-xpu-autoround-mtp-matrix` cell at
TP1/MTP2/PIECEWISE/F16/4096/native-MTP. The packet authorizes no sibling cell.

The parent is deliberately 4K rather than 8K. The corrected human adjudication
found that same-image TP1/MTP0 PIECEWISE and eager outputs match at 4K across
all 128 tokens (hash `3febb16e...`), while the PIECEWISE 8K output diverges at
generated token 99: graph token 411 versus eager target token 579. The original
compact R3 validator passed because it checked both arms independently but did
not compare their token arrays. The original artifact remains immutable; the
corrective adjudication is pinned here by SHA-256 `565687bd...`.

Historical graph-plus-MTP evidence also contains this alternate token family.
That makes 8K an invalid clean parent, not a reason to waive parity. A 4K pass
cannot be generalized to 8K or long context, and a failure cannot erase prior
measurements or lower protected values.

Both clean same-image 4K parents are pinned: eager raw SHA-256 `c9dbfb8b...`
and PIECEWISE raw SHA-256 `dbe75235...`. Before candidate execution, the runner
requires both parent receipts to pass exact-depth/cache-zero gates and requires
their complete token arrays to equal each other. The clean PIECEWISE MTP0
quality receipt (`34701095...`) is both pinned parent evidence and the candidate
baseline.

The same-image TP1/MTP2 eager 4K mechanism parent is also pinned: exact raw
`fc29f965...`, verification `9601176e...`, output hash `3febb16e...`, and
isolated acceptance `80/94`. Its six-depth terminal receipt is intentionally
retained as quarantined: 2K diverged at token 90, 8K at token 99, and 16K at
token 32. Only its explicitly clean 4K point transfers.

The new TP2/MTP1 PIECEWISE 4K pass is pinned by raw terminal SHA-256
`2613733c...` at launch commit `2f3100406...`. It proves graph plus native MTP
can pass at 4K on the same image, but its different topology gives it no TP1
token-oracle, speed, publication, or expansion authority.

The candidate uses native embedded MTP only:
`{"method":"qwen3_next_mtp","num_speculative_tokens":2}`. Startup must prove
method `mtp`, the exact target path, two recurrent speculative steps from the
single embedded MTP module, AutoRound `quantization=inc`,
F16/auto KV, `enforce_eager=False`, TP1 topology, and size-one PIECEWISE graph
capture. It requires both the mixed-prefill/decode PIECEWISE marker and graph
capture completion, and rejects FULL decode capture.

Speculative counters are snapshotted immediately before and after the one exact
4K request. The isolated deltas must prove drafted > 0, accepted > 0, and
accepted <= drafted. That request must be exact-depth, 128-token, cache-zero,
and byte-for-byte token-identical to both clean MTP0 parents.

The subsequent candidate quality run must explicitly pass all gates, not merely
return zero: `pass_all`, `baseline_match_all`, seven exact cases, eight repeats
with one unique hash, the 8K needle, 24 true baseline comparisons, and cache
zero on all 16 requests. The quality needle is a semantic battery component;
it is not authority for an exact-8K performance cell.

Execution uses fresh port `19526`, output root, ext4 cache root, and container.
The execute path additionally requires clean pushed `main`, the exact resident
image, verified model bytes, an idle host, and the canonical GPU lock. Global
EXIT/INT/TERM cleanup preserves logs and removes the container; strict sealing
requires the container absent, port closed, no model-server process, and no
render-node owner.

There is no speed floor. Only exact 4K + positive isolated acceptance + exact
dual-parent parity + the full quality audit + graph/topology/cache identity +
cleanup can classify the sentinel as passed. Every other outcome fails or is
quarantined with diagnostic evidence. Even a pass requires a separate human
decision before publication or expansion.

Static check (inert):

```bash
experiments/qwen38-27b-b70/scripts/run-20260826-qwen38-official-f01e-autoround-tp1-mtp2-f16-piecewise-4k-sentinel-r1.sh --check
```

GPU execution (not performed by this preparation):

```bash
experiments/qwen38-27b-b70/scripts/run-20260826-qwen38-official-f01e-autoround-tp1-mtp2-f16-piecewise-4k-sentinel-r1.sh \
  --execute \
  --ack 'RUN qwen38-official-f01e-autoround-tp1-mtp2-f16-piecewise-4k-sentinel-20260826-r1'
```
