# Long-context CPU oracles — closeout

<!-- campaign-closeout -->

## Question and identity

Can the sealed `iq3-p17-detmath-v2` CPU arithmetic produce exact, resumable
long-context reference bytes, including QSA selection beyond its budget?
Unsloth UD-IQ3_XXS Qwen3.8 Flash-Next is the separate quantized compressed model.
The model admission, official chat template, tokenizer, arithmetic, BF16 state,
and fixture layout match the suite128 lane. Source and model identities are bound
in [build-receipt.json](build-receipt.json) and each run receipt. CPU only on
`steve-b70s`, 2026-10-12–13; context capacity 4096; two OpenMP threads;
original affinity 4–15,20–31; nice 19 and idle I/O.

## Outcome

Accepted as CPU reference coverage for the two requested prompts. Both complete
runs were individually committed and pushed: LONG-A `42b48b954`, LONG-B `e9c8c8096`.
This does not establish device parity, context capacity 32768, full-response quality,
or serving performance. Device comparison belongs to packet44.

| Run | Prompt tokens | Generated | Fixtures | Elapsed hours | CPU hours | Mean seconds/position |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| LONG-A | 598 | 32 | 384 | 2.9446 | 5.2273 | 16.8193 |
| LONG-B | 2271 | 32 | 384 | 8.5268 | 15.3273 | 13.3060 |

The two runs total 11.4713 numerical-process elapsed hours
and 20.5545 measured CPU hours, including all 31 execution segments.
Both stop at the 32-token cap, not EOG. The instruction asks for about 200 words;
the requested oracle cap intentionally retains only the first 32 generated tokens.
The qualification and preparation attempts are separate from these totals and retain
their own receipts. Peak monitored combined anonymous memory was
1.533 GB. No numerical process remains running.

## What worked

- [Capacity equality](capacity-incident/equality-proof.json): all 64 sealed incident
  tokens, logit hashes/top-five records, 384 BF16 fixtures and eight layer ledgers
  match byte for byte at capacity 4096. [Source argument](capacity-analysis.md):
  capacity changes allocations and bounds only; valid-position arithmetic and the
  frozen 4096-position RoPE table are unchanged.
- [Resume equality](resume-equality-proof.json): restore after 80 consumed positions
  and again after 90, then compute four more predictions. Eight predictions and
  all 384 fixtures match the first eight of the uninterrupted capacity gate.
- Full-state checkpoints every 100 positions are written temporarily, reread and
  hashed before rename. The 7 LONG-A and 24 LONG-B processes carry that exact state;
  they bound allocator-history overhead without resetting model history.
- [Checker tests](checker-tests.json): two self comparisons pass; twelve corrupted
  copies fail (tail token, generation stream, selection ID, mid-prompt stream,
  truncated list and missing position for each run).
- [Final audit](final-audit.json) verifies both receipts, input bundles, fixture
  inventories, original source snapshots, capacity/resume proof bindings and lossless
  restoration of every retained compressed log and teardown receipt.

The exact budget edge is four-token pooled selection: 512 complete pools, plus up
to three trailing positions. Zero-based positions 2040, 2047, 2048, 2049 and 2050
admit all 2041, 2048, 2049, 2050 and 2051 available positions respectively. At 2051,
all twelve layers admit 2048 and drop 4; at 2100 they admit 2049 and drop 52; at the
last prompt position 2270 they admit 2051 and drop 220. No score ties or cutoff ties
occur in any captured layer. Exact ordered IDs, FP32 score bits and layer-47 streams
remain under [LONG-B/midprompt](LONG-B/midprompt).

LONG-B's measured QSA attention cost grows from 0.0808 seconds/position at 0–99 to
0.6560 at 1024–1535, 0.8875 at 1536–2047 and 1.0480 at 2048–2299. Pool/select site
timings and full-position bins are in both READMEs and
[site-cost-summary.json](LONG-B/site-cost-summary.json). Whole-position time is not
monotonic: shared-host load, weight staging, logging and allocator bookkeeping also
contribute. LONG-B's lower overall mean than LONG-A is not evidence that longer
context is faster. The final 2300–2301 bin has only two measured positions.

## What failed or remains uncertain

The original 256 MiB temporary pool is insufficient from 1225 admitted positions.
The [two-constant patch](scratch-capacity.patch) enlarges backing allocation and
bounds to 512 MiB; no numerical equation changes. The final binary passed both
equality gates. The [shape probe](scratch-analysis.json) records the allocation bound.

The first six-token resume diagnostic ended at EOG after three generated tokens.
Its bytes matched, but it could not prove further generation after restoring decode
state. Its [narrow proof](resume-equality-proof-short-eog.json) is retained separately;
the full incident diagnostic replaced it before LONG-A proceeded. Earlier cooperative
preparation stops and their receipts are preserved under `preparation-stopped-*`.
Neither long run suffered a numerical failure or required an unplanned retry.

Post-run review found two recovery bookkeeping gaps: active logs after an exceptional
supervisor exit lacked their old endpoint, and a completed partial could lack timing
receipts. These are fixed and covered by [CPU-only tests](recovery-tests.json).
They did not occur in either long run. Original campaign sources remain hash-named
in [runner-snapshots](runner-snapshots); the numerical binary and completed receipts
were not changed by the bookkeeping fixes. Gate reuse now also checks proof receipt
and binary hashes. Missing timing after a future supervisor crash is explicitly
unknown; it is never fabricated or counted as a complete measurement.

## Evidence and patches

[Run instructions and timing tables](README.md), [LONG-A receipt](LONG-A/receipt.json),
[LONG-B receipt](LONG-B/receipt.json), [input manifest](../../../../own-xpu-runtime/stage2/long-inputs-20261012/suite-manifest.json),
[prompt source records](../../../../own-xpu-runtime/stage2/long-inputs-20261012/prompts.json),
[preregistration](preregistration.md), [allocation patch](scratch-capacity.patch).
All generated tokens and decoded text are in each `result.json`.

Raw BF16 and int32 fixtures are retained directly. Gzip logs and teardown receipts
are necessary evidence; their retention ledgers give original/compressed hashes.
Restore to a temporary filename, hash, then rename. Checkpoints and executables are
regenerable scratch, excluded from Git; checkpoint hashes survive after complete
validation. Model files are external read-only inputs, identified by the original
admission receipts. No power, memory, swap, cache or device operation was used.

## When to revisit

Use these fixed bundles and byte records to gate packet44's device path at 4096.
A changed arithmetic/model identity needs new oracles. Testing beyond position 4095
needs an explicitly qualified RoPE/capacity extension; this campaign makes no claim
about that range. Preserve the CPU-only resource, disk and exact-output rules when
reproducing or recovering these runs.
