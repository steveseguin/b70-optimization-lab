# Featured picks for 32 GB B70 owners

The home page now starts with large models that have measured one-card setups,
then multiple-card choices, a separate LTX video item, and a collapsed section
for models of 9B and below. The first line gives a choice for one, two or four
cards. Size orders the first group; it is not a cross-model capability score.

Published order:

1. One card: Ornith 1.5 35B-A3B Q4_K_M; Nemotron 3.5 Lightning 30B-A3B;
   Qwen3.8 27B AutoRound INT4; Qwen3.8 27B FP8; Gemma 4 26B-A4B Q8.
2. Multiple cards: Flash-Next 125B-A6B FP8 (four); Qwen3.8 27B shared chat
   (two); MiniMax M2.7 (four); Laguna S 2.1 (four); Muse Glimmer 30B Q8 WOQ
   (four measured); DeepSeek V4 Flash 180B (four, explicitly lossy research).
3. LTX 2.5 continuation video (four).
4. Collapsed: Qwen3.5 9B INT4, Qwen3.5 9B FP8, Ornith 1.5 9B Q8,
   Qwen3.5 4B INT4 and LFM2.5 2.6B Q8.

## Evidence boundaries

The names in the request were examples, not new measurements. The current
Qwen27B AutoRound one-card receipt is Qwen3.8; the Qwen3.6 record guide is
historical TP2 and its old TP1 recipe remains in its history. Flash-Next is
125B-A6B with a certified four-card 46.854250 tok/s result, not a measured
one-card setup. The two-card 875 tok/s result belongs to Qwen3.8 27B and is two
same-server, short-prompt, output-exact passes with no speed certification.
Muse Q8 weights exceed one card's memory; its published measurement uses four.
LFM2.5 is 2.6B, not 26B, so it belongs in the small section.

Ornith35B and Nemotron retain visible strict-headline-pending labels. Their
measurements do not acquire certification through placement on the home page.
The DeepSeek entry is explicitly a trimmed, lossy research checkpoint with
compressed FP8 KV; exactness against that target is not equality to the original
model. Its retained measurement range appears as research prose, without a
headline bar. MiniMax's historical warm-run mean and Muse's three-prompt mean
keep their original scopes; neither is described as a new cold-suite record.

LTX's 0.875 figure is computed from the frozen 5.248-second raw delivery median
divided by six new video seconds (111 periods, including pacing). The separate
52-period unthrottled prefix is 5.2415 seconds. Compared chunks are byte-exact;
neither window establishes sustained 24/7 uptime, seam acceptance, or independent
replay. The site describes a continuing stream, not a current uptime promise.
The host halt and stream state were untouched.

## Generation and validation

Editorial source is [tools/featured_picks.py](../tools/featured_picks.py), called
by [tools/build-model-pages.py](../tools/build-model-pages.py). It reads package
identities from the generated catalog and each numeric observation from its
retained receipt. Every displayed speed links to its own evidence. The source
module is included in publication CI path triggers; the existing model-page
tests cover topology, withheld status, the collapsed section and evidence links.
No generated catalog was hand-edited. Regeneration used the same path as
`87c8c71933`: package validator with `--write-package-catalog`, family builder,
model builder, and public-summary synchronizer. Catalogs and detail pages
regenerated without changes. The uniform table and every later comparison
table remain byte-for-byte identical to the starting revision.

Local checks: 112 focused Python tests; four catalog browser-logic checks;
recipe-publication validation; guide validation; family-page and public-summary
freshness; Markdown links (zero broken); manifest paths (zero missing);
`git diff --check`. The hash-pin audit matches the previous publication:
318 literal pins, 87 match, 231 historical drift, zero absent. No frozen pin
was rewritten. Browser rendering at phone/desktop widths was not exercised;
no device-isolated browser is installed. The existing responsive grid is
retained, with extra narrow-screen room for the six-decimal Flash-Next value.

Publishing uses GitHub Pages, `main:/`, as in the prior commit. Push explicit
paths on main, wait for guides-and-packages and Pages, then fetch the home page,
catalog and linked detail pages with a cache-busting query and compare bytes.

All commands ran CPU-only at nice 19 with `OMP_NUM_THREADS=2`; no GPU, server,
unit, port 8188 or device operation was used. No persistent `/tmp` scratch was
created; test-owned temporary directories clean themselves up.
