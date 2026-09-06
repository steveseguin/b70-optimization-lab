# A187: frozen-client certification battery on the promoted overlay with the headroom placement (2026-09-05, 20:08-20:27)

Packet A78's frozen client (quality suite, short r1-r3, exact-2K r1/r2, exact-4K r1/r2,
deterministic summary) on the promoted overlay `2169dbfe` itself, with the only
change being the placement flags: `--cpu-offload-params
ple_embedding.ngram_embedding.weight embed_tokens.weight mlp.experts --cpu-offload-gb
13.4` (every rank reports 13.78 GiB host-offloaded: embedding, layer-0 experts, PLE,
layer-1 experts, layer-2 `w13_weight`). The only edits to the frozen client were the
identity pins for those flags, the placement description in its summary, and the
W13-N32 selection verifier's hash, which changed on 2026-09-03 21:14 after the client
was frozen. The battery took four minutes; under paging it took thirty-five.

| gate | A78 (promoted placement, 2026-09-03) | A187 (headroom placement) |
|---|---|---|
| recovery canary / status | passed / passed | passed / passed |
| semantic quality | 6/7; sole known miss code_execution=30 | 6/7; sole known miss code_execution=30 |
| repeat | 16/16 one hash | 16/16 one hash |
| long context | 2048 prompt tokens, exact needle, cache zero | same |
| short p146/o256/c1, tok/s after TTFT | 22.36 / 23.35 / 22.32 | 25.38 / 25.39 / 25.39 |
| exact-2K conventional 99-interval | 13.44 / 14.47, TTFT 58.3 / 56.1 s | **25.43 / 25.43**, TTFT 12.6 / 12.6 s |
| exact-2K output ids sha256 | `afffd211…` (authority) | `afffd211…` |
| exact-4K conventional 99-interval | 13.50 / 12.24, TTFT 102.5 / 96.4 s | **25.43 / 25.40**, TTFT 25.2 / 25.2 s |
| exact-4K output ids sha256 | `c6193cc6…` (authority) | `c6193cc6…` |
| protected results changed | false | false |

Both depth hashes are the deterministic line's own two-server authorities; the placement
changes no output pin. Prefill was also paying the paging tax: TTFT at 2K and 4K drops
about fourfold. Data: `../data/20260905-tp4-mtp0-a187-fresh-repeat-deterministic-summary.json`
and the per-artifact copies `../data/20260905-tp4-mtp0-a187-*.json`; exact-2K pair across
three servers (A179, A180 at `08df70ea`; A187 at `2169dbfe`):
`../data/20260905-tp4-mtp0-a179-a180-a187-exact-2k-pair-summary.json`.
