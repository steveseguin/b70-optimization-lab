# Next steps after 2026-09-03: Flash-Next lossless speed, complete recipes, faster iteration

Written at the close of the 2026-09-03 day shift on the four-B70 host.
Goal order from the user: every published recipe complete and reproducible
by a third party; Flash-Next faster, lossless, and faster to iterate; a
host-tuning guide (done); general improvements.

## Where things stand

- Deterministic full-decode-graph MTP0 line promoted at 4352 tokens (A73/A78:
  short 22.66, exact-2K 13.99, exact-4K 12.78 tok/s; identical outputs on two
  fresh servers; hashes with four and seven servers). Attempts take 16 min
  from the NVMe copy; `tools/q38-launch-frozen-attempt.sh` launches them.
- MTP1 on that line: 1.7x at short context but not lossless (A81-A90). The
  exact recurrent path (A85) removes part of the gap at 32.3 tok/s short;
  dense GEMMs are M-invariant (offline gate); the model's full-attention
  layers are its own query-sparse attention (QSA), so the 27B serial-FA
  fix does not apply. Prefill runs at about 410 tok/s (64-token chunks), so
  TTFT at 4K is 90-100 s.
- Recipes: audit filed, every validator green, R139 release assets bound,
  scanner covers all 30 lanes, banners on every guide. The Flash-Next lane
  itself is still `research-status` (no runnable recipe).

## Next steps, in order

1. **Offline two-row equivalence gates for the MTP1 verify step** (no
   server; minutes each, A1-gate style with sha256 receipts). Feed the same
   hidden state as one row and as row two of a two-row batch through:
   (a) the QSA indexer and top-k selection; (b) `qsa_sparse_paged_attention`;
   (c) the Triton block-FP8 fused MoE with the tuned map at M=2 versus two
   M=1 calls; (d) the rejection sampler's bonus/accept logic on identical
   logits. The first component that differs gets the serial-exact
   treatment (27B pattern: same kernel, one row at a time, or an
   M-invariant config). Then A91 = A85 plus that fix, gated on the pinned
   MTP0 hashes.
2. **If A91 matches all four pins:** frozen MTP1-exact client (identity
   `mtp=1`, exact-recurrent, capture sizes [1,2], KV 376569856, 12 GB
   floor) plus a receipt verifier that counts size-2 FULL dispatches; A92
   and A93 as the promotion pair. Expected record: 30+ tok/s short,
   lossless. Also profile why MTP1 at depth runs at 7 tok/s (what runs
   outside the captured graph in the spec step); it is only worth fixing
   once exact.
3. **Prefill and TTFT on the deterministic line.** 64-token chunks give
   about 410 tok/s prefill; preregister a chunk sweep (128, 256, 512
   `max_num_batched_tokens`, KV budget permitting) gated on the exact-2K and
   exact-4K hashes. Chunk size moves GDN chunk boundaries, so a change may
   alter outputs; if it does, that is a new authority question for the
   deterministic line, not a lossless win, and the plan stops there.
   Otherwise a 2-3x TTFT cut is the largest user-visible gain available.
4. **Family page and packet for the promoted line.** Codex applies the
   handoff note (`notes/2026-09-03-codex-handoff-family-page-deterministic-line.md`);
   then turn the deterministic line into a `candidate-portable-repro`:
   publish the staged runtime as release assets (R139 pattern), the overlay
   commits `805cde59`/`2169dbfe` as patches or a bundle, the tuned config
   folder, a launch script without `/mnt` or `/home/steve` paths, and the
   model contract. This is the recipe-completeness goal applied to the
   newest result.
5. **Clean-host replay of one candidate recipe** (the certification gap
   every guide still has). Replay the 27B FP8 TP2 recipe from a fresh user
   and a fresh clone on this host following only the README; fix anything
   that stops; record it as the first `clean_host_tested` entry.
6. **Exact 8K on the deterministic line.** The 8448-capacity lineage exists
   for the eager line; a graph-line 8K arm with the logprob probe first,
   then the frozen client with exact-8K rows, extends the certified context.

## Standing rules that saved time today

- Register any new `VLLM_*` control in `envs.py` before exporting it.
- `/proc/<pid>/environ` of vLLM engine and worker processes is rewritten
  by the process title; do not use it as evidence.
- Never `pgrep -f`/`pkill -f` a pattern that appears in the calling shell's
  own command; wait on the wrapper's `.rc` file.
- Swap must be unused and the page cache dropped before every launch; the
  helper does both.
- The MTP0 line's authority hashes (`afffd211...`, `c6193cc6...`) are the
  lossless gate for every MTP arm; a run that matches them and nothing
  less is a candidate.
