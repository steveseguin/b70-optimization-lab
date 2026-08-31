# Qwen3.8 Flash-Next FP8 exact-shape GDN history replay

Date: 2026-08-30
Status: bounded synthetic negative; production reliability still open

## Question

A24 and A25 first differed at the output of zero-based layer 1's
GatedDeltaNet after matching through PLE and the attention hyperconnection
input. Does the exact staged recurrent operator vary when exercised with the
Flash-Next TP4-local BF16/FP32 shape, 64-token chunking, and accumulated 4K
history?

## Frozen gate

`check-q38-flash-next-gdn-history-replay.py` binds the A24/A25 runtime stage,
model configuration, identities, 23-argument operator ABI, and source build.
On one B70 it executes the following synthetic contract:

- global K/V heads `16/48`, TP4-local heads `4/12`, dimensions `128/128`;
- BF16 projected QKVZ `[64,4096]`, BA `[64,24]`, convolution state
  `[2,3,2560]`, and outputs;
- FP32 recurrent state `[2,12,128,128]` and `A_log`;
- 64 sequential 64-token calls per trajectory, covering exactly 4,096 tokens;
- chunk 0 without initial state and chunks 1--63 with initial state;
- full cache reset per trajectory, entering and outgoing cache digests,
  output-overwrite checks, immutable input/metadata checks, and automatic
  snapshot replay on a first mismatch.

Synthetic inputs are deliberate. This gate does not load checkpoint weights
or test projections, normalization, the output projection, TP reduction,
state-slot selection, scheduling, or cross-stream interaction.

## Result

Two independent qualification processes each completed 100 trajectories and
6,400 native calls on physical GPU 3. All 200 trajectories and 12,800 calls
were exact. Both processes reported no first mismatch, complete source and
metadata immutability, and identical canonical digests for all 64 chunks. The
fresh-process comparison passed.

Tracked evidence:

- `data/20260830-gdn-history-qualification-gpu3-r1.json`, SHA-256
  `2bc9ae6af982942ad4b193aa149b3d51c3c8225c02583d84526d77d150a4675e`;
- `data/20260830-gdn-history-qualification-gpu3-r2.json`, SHA-256
  `12f7b7ea457785759b02b420152a96ccc79ad45d4b262d9d2513784fe883fe66`;
- `data/20260830-gdn-history-qualification-fresh-process-compare.json`,
  SHA-256
  `5a3fc0fbe93e1cb90a8d5237253e4bcd55041ada7bf7a6a0bfda800a9d2f21c6`.

## Interpretation and next action

This is a bounded negative for basic nondeterminism in the exact staged native
operator under synthetic TP4/history inputs. It materially weakens that
hypothesis but does not clear the production path. The next reliability arm
must remain report-only and default-off: capture layer-1 production QKVZ/BA,
the selected state slot and metadata, convolution/recurrent caches before and
after each 64-token chunk, core output, gated norm output, and local/reduced
output projection. The first real fixture should then be replayed with this
tool before any arithmetic treatment is attempted.

No target-only or MTP speed, quality, coverage, or protected result changes.
