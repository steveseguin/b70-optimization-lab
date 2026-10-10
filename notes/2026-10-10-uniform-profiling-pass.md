# Uniform one-card profiling pass, 2026-10-10

Owner ask: profile every model we can run on one or two B70s the same way, so the home page's picks come from
measurements rather than from whatever lane was worked on last, and so each entry has prefill, decode, many-user
and determinism numbers next to each other.

## How

- Harness `tools/profile-openai-endpoint.py` (any OpenAI-compatible endpoint, temperature 0, distinct seeded
  prompts): 1-user decode (300-token prompt, 256 tokens, median of 3), prefill at 512 / 2,048 / 8,192 tokens (cold),
  repeat identity (same cold 3K prompt x3), batch identity (same prompt alone vs N at once), N-stream decode aggregate,
  40 s closed-loop load (300 in / 150 out), the chat canary (`scripts/gemma4-text-canary.py`, 4 repeats).
- Runner `tools/profile-run.sh` (transient user unit around any server command; stops it afterwards). Campaign
  `tools/profile-campaign-20261010.sh` + `-llama16k.sh`. Results `data/profiles/2026-10-10/*.json` (+ `.canary.json`,
  `.server.log`), summary `tools/profiles-summary.py`, page section `tools/profiles-to-site.py` (+ `profiles-site-map.json`).
- Card 0 did the profiling; the Gemma LAN service stayed on card 1 (recipe `throughput-card1`) except during the two
  27B vLLM entries (host RAM). Host 15 GiB; vLLM compose containers capped at 9g no-swap via
  `scripts/apply-container-noswap.sh`; the FP8 TP1 launcher ships 12g/12g.
- Builds: vLLM packages ran their own pinned images via `compose.yaml one-gpu` / `serve.py`. llama.cpp entries ran the
  pinned 9fee29e build (`~/src/llama.cpp-neural-download-20260822/build-sycl-aot-bmg-g31`, the lfm/ornith/nemotron
  pin). The Qwen3.8 GGUF packages pin a patched mndodd 4302fb59 build that is not on this host, so their rows are
  "stock 9fee29e" and lower than the package headlines (23.8 vs 27.83 Q4_K_M, 15.7 vs 19.62 Q8). Gemma's row is the live
  shared-server shape (8 slots, no draft, deterministic oneDNN) measured on card 1.

## Results (one card, tok/s)

| entry | 1 user | prefill 512 / 2K / 8K | N | N-stream agg | load total / completion | repeats | batch | canary | card GB |
| --- | ---: | --- | ---: | ---: | ---: | --- | --- | --- | ---: |
| Qwen3.5-4B INT4 (vLLM pkg) | 227.7 | 3,505 / 4,066 / n/a (8K > ctx) | 8 | 1,312 | 2,412 / 782 | identical | differs | n/a (thinking text) | 28.5 |
| Qwen3.5-9B INT4 (vLLM pkg) | 156.6 | 2,193 / 2,452 / n/a | 8 | 988 | 1,655 / 536 | identical | identical | n/a | 27.7 |
| LFM2.5 2.6B Q8 (9fee29e) | 132.0 | 3,468 / 2,014 / 7,391 | 4 | 347 | 918 / 297 | identical | differs | empty reply on json case | 4.1 |
| Qwen3.5-9B FP8 (vLLM pkg) | 117.5 | 2,384 / 2,891 / n/a | 8 | 827 | 1,574 / 510 | identical | identical | n/a | 28.2 |
| Qwen3.8-27B INT4 one-card (vLLM pkg) | 92.2 | 1,107 / 1,165 / n/a | 4 | 283 | 693 / 206 | identical | identical | n/a | 27.1 |
| Gemma 4 26B Q8, 8 slots no draft (live) | 77.6 | 990 / 1,453 / n/a (4K slots) | 8 | 268 | 621 / 139 | identical | differs | 16/16 | 29.9 |
| Nemotron 3.5 30B-A3B UD-Q4_K_M (9fee29e) | 72.4 | 852 / 1,795 / 2,218 | 4 | 131 | 265 / 66 | 3 of 3 differ | differs | 2/3 (arithmetic 10) | 23.3 |
| Qwen3.8-27B FP8 TP1 (serve.py recommended) | 54.6 | 644 / 1,871 / 1,979 | 1 | 56 | 231 / 69 | identical | identical | n/a | 30.4 |
| Ornith 1.5 9B Q8 (9fee29e) | 49.6 | 1,436 / 2,359 / 2,514 | 4 | 146 | 410 / 98 | 2 of 3 differ | differs | 2/3 (arithmetic 22) | 10.7 |
| Qwen3.5-9B Q8 GGUF (9fee29e, no package) | 49.3 | 1,432 / 2,353 / 2,496 | 4 | 147 | 490 / 88 | identical | identical | 2/3 (arithmetic 10) | 10.7 |
| Qwen3.8-27B Q4_K_M GGUF (stock 9fee29e) | 23.8 | 592 / 917 / 988 | 2 | 36 | 148 / 29 | 2 of 3 differ | differs | 2/3 | 20.0 |
| Qwen3.6-27B Q8 GGUF (9fee29e, no draft, no package) | 15.9 | 451 / 733 / 786 | 2 | 28 | 111 / 23 | 2 of 3 differ | differs | 2/3 | 28.4 |
| Qwen3.8-27B Q8 GGUF (stock 9fee29e) | 15.7 | 448 / 733 / 787 | 2 | 28 | 118 / 21 | 2 of 3 differ | identical | 2/3 | 28.4 |

Also recorded: Qwen3.5-9B Q8 GGUF on the Gemma compat build (c926 + patches + deterministic oneDNN): 51.7, repeats and
batch identical. Nemotron on the compat build cannot load (tensor count mismatch). Nemotron with `GGML_SYCL_DISABLE_DNN=1`
on 9fee29e still differs run to run (4 of 4), so stock 9fee29e has a nondeterminism source beyond oneDNN.

## What it says

- The vLLM packages are both the fastest and the cleanest: repeat-identical everywhere, batch-identical on the 9B/27B
  entries. Qwen3.5-4B INT4 is the fastest thing on one card (228 alone, 1,312 for 8); Qwen3.5-9B INT4 is the sensible
  mid-size pick; the FP8 9B trades ~25% speed for no 4-bit compression.
- Stock llama.cpp 9fee29e is not repeat-deterministic on MoE/large models (Nemotron, Ornith, the 27B GGUFs); the small
  dense ones (LFM, Qwen3.5-9B Q8) repeat identically. The Gemma compat build with the deterministic-oneDNN switch is
  repeat-identical; batch composition still changes answers on every llama.cpp build (kernel choice by batch size).
- The chat canary is only meaningful for non-thinking chat endpoints: the vLLM compose packages reply with their
  thinking text, and three small models get the arithmetic case wrong with reasoning off. The vLLM packages' own strict
  suites remain the exactness evidence; this pass adds speed and determinism side by side.
- Gaps left: 2-card shapes were not re-run (the Gemma service held card 1); the Qwen3.8 GGUF packages' patched build is
  not on this host; Qwen3.6-27B INT4 / Qwen3.6-35B-A3B / the GPTQ-MTP 27B have no launcher in the repo and were skipped;
  the 8K prefill point needs the vLLM compose context raised (`--max-model-len`) to be measured.

Home page: `index.html` "What should I run?" re-ranked by size from these numbers, and the new "Same test, every
model" table is generated from this directory (`python3 tools/profiles-to-site.py data/profiles/2026-10-10 --write`).
