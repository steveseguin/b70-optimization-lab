# Where a clip's GPU work can go without changing a byte: a source survey (2026-10-04)

Read-only, offline. No GPU was touched, nothing was launched, no lane code
changed. Inputs: the 91c driver-counter budget
([2026-10-04-gpu-budget-from-driver-counters](2026-10-04-gpu-budget-from-driver-counters.md):
about 5.1 GPU-s of compute per clip, of which the sampler is about 2.3, text
encoding about 2.0 and decode about 0.65; 24 fps needs 4.17 GPU-s or less),
the runtime source of packet `prepared-encoder-decode-91b` as launched, the
control graph `graphs/graph-capture-all48-pipe-samp2-tsh.json`, the 91c
receipts, checkpoint headers (header bytes only) and the tokenizer stored in
the text-encoder checkpoint (one 32 MB `tokenizer_json` tensor, read on the CPU).

`SRC` below is
`/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-encoder-decode-91b/source`.
Every code claim carries a file:line in that tree. **[V]** marks what I
verified in code or data; **[I]** marks inference or arithmetic that a
measurement still has to confirm.

## Ranked candidates

Ranked by expected gain times the probability that the emitted bytes stay
identical. GPU-s are compute-engine seconds per clip against the 5.1 total.

| # | What | GPU-s per clip it could remove | Why the bytes would not change | Proof or test needed | Effort | Risk |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | **Encode a suffix window instead of 1024 padded tokens.** Real prompts are 30-56 tokens; the encoder computes 1024 rows and LTX keeps only the last N | **0.9 (L=512) to 1.6-1.7 (L=64-128)** of the ~2.0 [I] | Mathematically exact [V]: pad keys get an additive `finfo.min` mask, so their softmax weight underflows to exactly 0 for every real row; every other op is row-wise; pad rows are cropped before projection. Bit-exactness is NOT by construction: GEMM M changes, and SDPA key length changes | Hold absolute positions and the SDPA path; per-shape census of row bits at M=L vs M=1024 on the real kernels; then conditioning-byte equality on prompts of every length 1..L; then oracle clips (details in A2) | High: new position ids, forced `expand_kv`, one 48-layer capture set per bucket per worker | **High** that some bucket fails; the lane already saw batch-2 forwards differ from batch-1, i.e. M-dependent rounding on this stack |
| 2 | **Stop processing the unused negative conditioning** (BasicGuider, or a guider that never hands `negative` to `process_conds`) | **0.08-0.13** on xpu:0 [I] | cfg is 1.0, so the negative is never evaluated in any forward (`uncond_ = None`); only its connector pass runs, its result is discarded; the connector has no RNG | None by construction. Already screened exact once (BasicGuider, boat, Sept 13; `data/speed-resident/summary.json`, `basic_guider_screen`). One oracle arm | Low (graph edit) | Very low |
| 3 | **Process the conditioning through the connectors once per clip**, not once per sampler stage | **0.04-0.065** on xpu:0 [I] | Stage b calls the same 8+8-layer connectors on the same input bytes, same device, same shapes, under strict determinism | By construction for one clip (within-clip reuse, never across clips). Fingerprint both outputs once, then an oracle arm | Medium (memo around `preprocess_text_embeds` keyed per clip) | Low |
| 4 | **Crop the hidden-state stack before its CPU copy** (`ltx_crop_before_cpu`, already in the tree) | ~0 compute; **745 MB less pageable D2H on xpu:2** per clip [V bytes] | A slice and a copy commute; the projection sees the same values | Already qualified exact 25/25 (encoder-screen-02, Sept 14); currently refused by `host_embedding_clip.load_clip` | Low (sealed packet change) | Very low |
| 5 | **Keep the hidden state on xpu:3 through layers 24-47** and move only cropped intermediates back | ~0 compute; **~730 MB less PCIe per card (xpu:2 and xpu:3) and 46 fewer host waits** per clip [V bytes] | Copies are exact; xpu:3 computes on the same input bits | By construction; capture proofs plus an oracle arm | Medium (encoder loop / shadow / final cat) | Low |
| 6 | Share static buffers across the 48 encoder layer graphs (fill the constant RoPE tables once at capture, the mask once per encode, chain `x`) | ~0.005-0.01 [I]; **~1.2 GB of D2D fills** per clip | Only copies are removed; the video blocks already chain this way (`ltx_graph_capture.Slot`) | Recapture with shared buffers (existing bitwise capture proof) | Medium | Low |
| 7 | Clone only the last N rows into the 49-state stack, and cat those | ~0.003-0.006 [I]; **~1.5 GB of D2D traffic** per clip | Slicing before clone/cat yields the same values the crop keeps | By construction | Low-medium (touches `Gemma4Transformer.forward`) | Low |
| 8 | Timestep-embedding tables for the fixed 8+3 sigmas (adaLN family), computed once instead of every forward | **0.02-0.035** [I] | Same function, same constant inputs, same device and kernels | Tables compared bitwise against the per-forward values; oracle arm | Medium | Low (but it is a cross-clip constant: say so in the receipt) |
| 9 | Stage the text context to xpu:1 once per stage rather than every forward | ~0 compute; **139 MB PCIe + ~280 MB D2D** per clip | Copies only | By construction | Low-medium | Low |
| 10 | RoPE tables once per stage (4 sites x 11 forwards) | **~0.005** (measured 0.11 ms per site, `data/rope-table-cost-01.json`) | Positions, heads and dtype are constant within a stage | By construction | Low | Very low |
| 11 | Keep an fp32 copy of the Gemma weights instead of upcasting bf16 to fp32 on every Linear call | ~0.12 per clip at roofline [I] | bf16 to fp32 is exact | Trivial numerically | n/a | **Does not fit**: +43.6 GB; a partial precast into spare memory buys a fraction |

Expected-value order: 1 (about 1.3 x 0.3), then 2, 3, 8, 10. Items 4, 5, 6, 7
and 9 remove copy traffic rather than compute; their payoff depends on the
copy-engine question in section C, which I could not settle offline.

Sum of the low-risk compute items (2, 3, 6, 7, 8, 10): about 0.15-0.25 GPU-s,
all on xpu:0/xpu:2. That is real but far short of the 0.9 GPU-s the budget
needs. **Only item 1 (or prompt reuse, section E) moves the encoder.**

## A. Text encoding

### A1. What is computed per prompt [V]

- **One encoder pass per clip, positive only.** Node 364 (`LTXPipelineTextEncode`)
  feeds both `positive` and `negative` of node 365 (`LTXVConditioning`) in the
  control graph; `pipeline_node.native_encode` calls `CLIPTextEncode().encode`
  once (`SRC/scripts/pipeline_node.py:75-77`). No empty-prompt pass: weights
  are disabled (`SRC/comfy/text_encoders/gemma4.py:1610`, `disable_weights=True`),
  so the "has_weights" branch that would encode an empty prompt
  (`SRC/comfy/sd1_clip.py:39-43`) never runs.
- **Model**: the Gemma4 12B unified text stack, 48 layers, hidden 3840, MLP
  15360; 40 sliding layers (16 q heads, 8 kv heads, head 256) and 8 global
  layers (head 512, one kv head, k=v) (`SRC/comfy/text_encoders/gemma4.py:98-112`;
  checkpoint header and `gemma_config` metadata agree). Weights bf16
  (header; `--bf16-text-enc`, `SRC/../launch/serve-encoder.py:42`).
  Activations fp32: `dtype=torch.float32` into the stack
  (`SRC/comfy/sd1_clip.py:284`), and Linear weights are cast to the input dtype
  on each call (`SRC/comfy/ops.py:430-431`; [I] that every encoder Linear takes
  this path, which matches the September dtype probe).
- **Tokenizer**: the `tokenizer_json` stored in the checkpoint, BOS (2) added,
  no chat template (`skip_template=True` default,
  `SRC/comfy/text_encoders/gemma4.py:1470,1514-1518`), **left-padded with token 0
  to a minimum of 1024** (`SRC/comfy/text_encoders/lt.py:84-90`,
  `SRC/comfy/sd1_clip.py:571-574,673-674`). Attention mask 0 on the leading
  pads (`SRC/comfy/sd1_clip.py:198-205`).
- **Masks**: additive pad mask `finfo(float32).min` on pad keys plus a causal
  mask (`SRC/comfy/text_encoders/gemma4.py:465-474`). The sliding-window mask is
  only added when the sequence is longer than 1024
  (`SRC/comfy/text_encoders/gemma4.py:328`), so it is inactive.
- **What is consumed**: all 49 hidden states (the embedding output, the 47
  between-layer states and the final normed state), collected by
  `x.unsqueeze(1).clone()` and concatenated (`SRC/comfy/text_encoders/gemma4.py:565-567,639-643`),
  **then cropped to the last N = real-token positions**
  (`SRC/comfy/text_encoders/lt.py:188`), cast to bf16 on xpu:2 (`lt.py:190-191`),
  per-token-per-layer RMS normalised and projected by the dual linear
  projection to video 4096 + audio 2048 (`lt.py:110-123,207`; header:
  `video_aggregate_embed [4096, 188160]`, `audio_aggregate_embed [2048, 188160]`),
  returned as fp32 `[1, N, 6144]` on the CPU (`lt.py:210`).
- **Downstream**: the sampler splits 4096/2048 and runs each half through an
  8-layer bidirectional connector that **pads to 1024 tokens with learnable
  registers** (`SRC/comfy/ldm/lightricks/av_model.py:585-602`,
  `SRC/comfy/ldm/lightricks/embeddings_connector.py:282-292`; header:
  `connector_num_layers 8`, `num_learnable_registers 128`,
  `caption_proj_before_connector True`). Cross-attention sees all 1024 context
  tokens with no mask (the conditioning carries no `attention_mask`,
  `lt.py:208`). So no encoder pad position reaches the sampler; the context
  length is fixed at 1024 regardless of N.

**Real versus padded token counts** (BOS included; computed on the CPU with the
checkpoint's tokenizer; the boat count matches the `[1, 56, 6144]`
conditioning recorded in [streaming-conditioning-cache-01](streaming-conditioning-cache-01.md)):

| Fixture | seed | real N | pad rows | real share |
| --- | ---: | ---: | ---: | ---: |
| boat | 42 | 56 | 968 | 5.5 % |
| marble | 17 | 31 | 993 | 3.0 % |
| bird | 123 | 31 | 993 | 3.0 % |
| pendulum | 271 | 30 | 994 | 2.9 % |
| rain | 314 | 34 | 990 | 3.3 % |
| paper | 519 | 36 | 988 | 3.5 % |
| candle | 808 | 32 | 992 | 3.1 % |
| pour | 1201 | 34 | 990 | 3.3 % |
| fabric | 2026 | 31 | 993 | 3.0 % |
| wheel | 4096 | 32 | 992 | 3.1 % |

Mean 34.7 real tokens of 1024: **about 96.6 % of the encoder's rows are pads
whose outputs are thrown away.**

### A2. Provably irrelevant work, and what bit-identity would need

**No unused or constant encode exists** [V]. There is one encoder pass and no
negative or empty-prompt encode. There is no fixed prefix or system template
(raw text plus BOS). The BOS row is not constant across prompts: its absolute
position is 1024 - N. The pad rows *are* prompt-independent (a pad row only
attends earlier pads, so its value depends only on its position), but they
are also never consumed, so the right move is to drop them, not to precompute
them.

(The unused negative work that does exist is in the sampler: item 2, section B.)

**The pad rows are mathematically irrelevant** [V]. A real row's dependence on
pad rows runs only through attention, where each pad key carries the additive
`finfo.min` (gemma4.py:467-469); every real row has at least one unmasked key
(BOS), so `exp(min - rowmax)` underflows to exactly 0 in fp32. RMSNorm,
q/k/v/o, RoPE, MLP and `layer_scalar` are all row-wise
(gemma4.py:184-283, 322-361). The crop removes the pad rows before anything
mixes tokens again (lt.py:188).

**Bit-identity is not by construction**, because shortening the sequence to a
window of L rows (L >= N) changes four things:

1. *Absolute positions.* `position_ids` default to `arange(0, seq_len)`
   (gemma4.py:460-461). The real tokens must keep positions 1024-N..1023, so
   the window must pass `position_ids = arange(1024 - L, 1024)`. The RoPE
   angles are a K=1 product followed by cos/sin (gemma4.py:432-440); [I]
   likely invariant, still to check.
2. *The SDPA call itself.* Sliding layers expand the kv heads with
   `repeat_interleave` only when `kv_len >= sliding_window`
   (gemma4.py:276-282). At 1024 that is true; at L < 1024 it flips to
   `enable_gqa`, a different kernel call. The window must force the 1024 path.
3. *GEMM shapes.* Every Linear runs with M = L instead of 1024. Row results
   can only change if oneDNN picks a different kernel or K-blocking (split-K
   is likelier at small M). The lane's batch-2 result (M doubled, not
   bit-exact) is direct evidence that M changes rounding on this stack.
4. *Softmax and P.V reduction length.* Adding exact zeros never changes a
   partial sum, but the *grouping* of the nonzero terms can change if their
   index offset changes. Choosing L so that 1024 - L is a multiple of every
   tile and work-group width involved (L in {512, 256, 128, 64}) keeps the
   nonzero keys at the same offsets within tiles, so this is plausibly
   invariant. [I] for the XPU fp32 masked SDPA backend, which I could not
   identify offline.

Test plan (GPU-gated, so it needs authorisation; one card, offline, no server):

- (a) a kernel census at the real shapes: for each of the 7 sliding-layer and
  5 global-layer GEMM shapes, fp32 inputs, M = 1024 against M = L with the
  real rows placed at the tail, rows compared bitwise; the same for masked
  SDPA (forced expand path), RMSNorm and the RoPE op.
- (b) the real encoder at 1024 against each passing bucket, positions held
  and expand forced, on prompts of **every** length 1..L plus the ten
  fixtures, comparing the cropped 49 x N x 3840 stack and the final
  `[1, N, 6144]` conditioning bytes. Equal conditioning bytes make the rest
  of the clip identical by construction (same sampler inputs).
- (c) one oracle-gated server arm with the ten fixtures.
- A failed bucket is a valid negative; record it and move on to the next
  larger L.

### A3. Sizing [I]

Per-layer model from the September exclusive-card probe
([text-encoder-is-fp32-bound](text-encoder-is-fp32-bound.md): 30.15 ms per
layer at 1024 tokens): fp32 GEMMs ~22 ms (0.46 TFLOP at ~21 TFLOP/s), the
per-call bf16-to-fp32 weight upcast ~2.5 ms (fixed, 0.45 GB read + 0.9 GB
written at the 537 GB/s roofline), attention and elementwise ~5.6 ms. GEMMs
fall roughly linearly with L until they hit the fp32 weight-read floor
(~1.7 ms per layer).

| Window L | ms per layer | Share of encoder work removed | GPU-s per clip removed (of ~2.0) |
| ---: | ---: | ---: | ---: |
| 1024 (today) | 30 | 0 | 0 |
| 512 | ~16 | ~45 % | ~0.9 |
| 256 | ~9.4 | ~65-70 % | ~1.35 |
| 128 | ~6 | ~80 % | ~1.6 |
| 64 | ~4.6 | ~85 % | ~1.7 |

Below L = 128 the fixed weight upcast dominates. Copy and clone bytes in the
encoder (section C) fall by the same factor.

## B. Sampler: work outside the transformer blocks

Eleven forwards per clip (8 at 64 video tokens, 3 at 256; 26 audio tokens),
one cond each: the uncond is never evaluated because cfg is 1.0
(`SRC/comfy_extras/nodes_lt.py:1226-1229` falls back to the single-CFG path;
`SRC/comfy/samplers.py:610-611` sets `uncond_ = None`; confirmed by the
packet 52 receipts in [concurrent-cfg-inert](concurrent-cfg-inert.md)).

| Item | Where | How often | Invariant across | Already hoisted or captured? | Hoist byte-identical? | Size [I unless noted] |
| --- | --- | --- | --- | --- | --- | --- |
| **Connector pass for the positive** (8 video layers at 4096 wide, 8 audio at 2048, 1024 tokens; 4.03 GB of weights per header; ~4.3 TFLOP bf16 per pass) | `model_base.LTXAV.extra_conds` (`SRC/comfy/model_base.py:1189-1191`) from `process_conds` (`SRC/comfy/samplers.py:1046-1048`), redone each `sample()` (`samplers.py:1316-1318`) | once per stage = 2 per clip | both stages of one clip (same input bytes) | no, eager, outside the captured blocks | yes, within the clip | ~40-65 ms per pass |
| **Connector pass for the negative** | same | 2 per clip | n/a: never used | no | removal is exact | ~80-130 ms per clip |
| Text context staged xpu:0 -> xpu:1 (v 8.4 MB + a 4.2 MB bf16) and filled into the static slots on both cards | `_staged_cached` (`SRC/scripts/ltx_graph_capture.py:967,978-993`), cache cleared per forward (`SRC/scripts/ltx_layer_shard.py:57-70`); slot fill (`ltx_graph_capture.py:447-463`) | every forward | all forwards of a clip | no (per-forward cache only) | yes (copies) | 139 MB PCIe + ~280 MB D2D per clip |
| Timestep embeddings: `adaln_single`, prompt adaLN, audio adaLN, four AV cross adaLNs (851 MB of weights per header, M of 1-4) | `av_model._prepare_timestep` (`SRC/comfy/ldm/lightricks/av_model.py:740-849`) | every forward | **all clips**: the 11 sigmas are fixed (`ManualSigmas` nodes 404/395) | no | yes, same kernels on constant inputs | ~1.6-3 ms per forward, 0.02-0.035 GPU-s per clip |
| RoPE tables: video, audio, two AV cross sets | `av_model._prepare_positional_embeddings` (`av_model.py:873-910`) | every forward | all forwards of a stage, all clips | no | yes (lane's own probe says so) | 0.11 ms per site measured, ~5 ms per clip |
| Patchify, `audio_patchify_proj`, output norm and projection | `model.py:1108-1180`, `av_model.py:1030-1066` | every forward | no (depend on x) | in the glue, not captured | n/a | part of the ~0.09 s glue (packet 65) |
| Latent upsampler | `LTXVLatentUpsampler` (`SRC/comfy_extras/nodes_lt_upsampler.py:29-59`) | once per clip | no | eager (mode `original`) | n/a | ~30-60 ms; it also pulls the VAE's per-channel stats from xpu:3 with `.to(x)` (`SRC/comfy/ldm/lightricks/vae/causal_video_autoencoder.py:1145-1149`), a tiny blocking cross-card copy |
| Initial noise | `prepare_noise` on the CPU (`SRC/comfy/sample.py:9-11`) under the lane's lock | once per stage | no (seeded per clip) | n/a | n/a | negligible |
| Concat/separate AV latent | `nodes_lt.py:941-967` | 2+2 per clip | no | n/a | n/a | ~0.2 ms wall each (91c phases) |

Not in this graph, but noted: the adaLN fusion (packet 89, proven exact,
~0.05 s) is off here (node 424 `mode: original`).

The connector finding is the new one. With 4 passes per clip, 3 redundant, the
connectors are a plausible part of the xpu:0 overload (xpu:0 is the busier
sampler card, 80-86 %). Packet 65 left ~0.35 s per clip outside the forwards
(upsampler, oracle, turnaround and these passes), which caps the four
connector passes at roughly 0.25 s; the 40-65 ms per pass is my FLOP estimate,
not a measurement.

Cross-step text K/V reuse stays rejected: `cross_attention_adaln` modulates the
context by the timestep before K/V
([cross-step-text-kv-audit-01](cross-step-text-kv-audit-01.md)).

## C. Copies: inventory per clip [V for sources and bytes; I for times]

| Source | Card(s) | Bytes per clip | Needed? | Avoidable how |
| --- | --- | ---: | --- | --- |
| 49-state hidden stack, full 1024 rows, fp32, to the CPU (pageable; launcher has `--disable-pinned-memory`, no `--gpu-only`) | xpu:2 D2H | **770.7 MB** | only 26 MB of it (N=35) | crop first (`SRC/comfy/sd1_clip.py:66-73`; `lt.py:184-185`), refused today by `SRC/scripts/host_embedding_clip.py:288` |
| Cropped stack back to xpu:2 for the projection | xpu:2 H2D | ~26 MB (49 x N x 3840 x 4) | yes, while the CPU detour exists | keep on device under `--gpu-only`-like placement (not checked) |
| Encoder shard: `x` staged into each of layers 24-47 and back (`SRC/scripts/ltx_graph_text_encoder.py:285,350`; split at `graph_text_encoder_node.py:26`), pinned host, host `event.synchronize()` each (`ltx_graph_capture.py:547-565`) | xpu:2 377 MB D2H + 377 MB H2D; xpu:3 the same | **~755 MB per card** (48 x 15.7 MB legs) | 2 moves are; 46 are not | item 5 |
| Mask + both RoPE tables to xpu:3, once per encode (`ltx_graph_text_encoder.py:287-289`) | xpu:2 -> xpu:3 | ~10.5 MB | RoPE part is constant forever | stage at capture |
| Per-layer static fills: x 15.7 + mask 4.2 + RoPE 6.3 MB into each layer's own buffers (`ltx_graph_text_encoder.py:338-341`; 4 mirrored tensors per layer in the 91c capture receipts) | xpu:2/xpu:3 D2D | **~1.26 GB** | x only, and only if not chained | item 6 |
| `all_intermediate` clones and `torch.cat` (`gemma4.py:567,643`) | xpu:2 D2D | ~0.77 GB clones + 0.77 GB cat | only the last N rows | item 7 |
| Conditioning `[1, N, 6144]` fp32 back to the CPU (`lt.py:210`), then to xpu:0 for each of the 4 connector passes (`model_base.py:1190`) | xpu:2 D2H, xpu:0 H2D x4 | ~0.85 MB x 5 | once each | items 2 and 3 cut the H2D to one |
| Sampler: text context (12.6 MB), RoPE (1.3 / 4.5 MB), timesteps and activations (0.6-2.2 MB each way) staged per forward to xpu:1 (`ltx_graph_capture.py:962-974`) | xpu:0 D2H, xpu:1 H2D (activations also back) | **~200 MB** | activations yes; context and RoPE once per stage | item 9 |
| Sampler slot fills, context on both cards every forward | xpu:0/xpu:1 D2D | ~280 MB | once per stage | item 9 |
| Latents between nodes: every `SamplerCustomAdvanced` returns on the CPU (`SRC/comfy_extras/nodes_custom_sampler.py:1056`) and goes back for the next stage | xpu:0 | < 1 MB | inherited from ComfyUI | not worth it |
| Decoded frames `[25, 256, 256, 3]` fp32 and waveform to the CPU (`SRC/comfy/sd.py:1093,1178`) | xpu:3 (or xpu:1 replica) D2H | 19.7 + 0.4 MB | **yes**: these are the product | no |
| Oracle capture `.cpu()` and sha256 (`SRC/scripts/capture_node.py:44-58`), sampler/decode sentries (`pipeline_sampler_node.py:213-215,359-362`; `pipeline_decode_node.py:416`), preview writer copy (`pipeline_decode_node.py:171-172`) | host only | 0 device bytes | verification / preview | they read tensors already on the CPU, so a speed arm that drops them saves **CPU** time, not GPU or copy-engine time |

Headline: per clip about **0.8 GB of PCIe traffic per encoder card plus 0.77 GB
of pageable D2H on xpu:2, about 0.2 GB per sampler card, and about 3 GB of
on-device copies (mostly in the encoder)**. Every one of the large items is
avoidable without touching arithmetic. Verification and preview cost no
device copies.

**The byte inventory does not explain the copy-engine counter.** At an assumed
20-25 GB/s pinned and 5-10 GB/s pageable, these bytes are ~0.1-0.15 s of copy
engine per encoder card and ~0.01 s per sampler card, against 0.84-1.14 s
measured. Either on-device copies are routed to the copy engine with large
per-command overheads, or (more likely, [I]) the `drm-cycles-bcs` counter
also accrues while a copy batch is scheduled and waiting on its dependency
(each staged move first waits for the preceding compute on its stream). If
the second, "51-69 % copy busy" overstates the transfer cost, and eliding
copies buys less GPU time than the counter suggests, although the 48 host
`event.synchronize()` calls per encode still stall the issuing thread.
Settling this takes a counter sample on an idle server and on a probe that
only copies.

## D. Other work that is identical every clip [V sources, I sizes]

- Encoder RoPE tables (positions 0..1023): computed every encode
  (`gemma4.py:463`), staged to xpu:3, and filled 48 times. Constant for the
  server's life.
- The causal half of the encoder mask (constant); the pad half depends only on N.
- Sampler RoPE tables per stage, and the timestep-embedding family for the 11
  fixed sigmas (section B).
- The connector's input tail is constant (learnable registers), but the
  connector is bidirectional, so its outputs still depend on the prompt. Not
  hoistable.
- The VAE per-channel statistics moved across cards for every upsample (tiny).
- The per-call bf16-to-fp32 upcast of every Gemma weight (`ops.py:430-431`):
  about 65 GB of memory traffic per encode, identical every time; only an
  fp32 resident copy removes it, and that does not fit.

## E. Continuous stream with an unchanged prompt (sizing only) [I]

If the encoder runs only on a prompt change, a repeated-prompt clip costs
about **5.1 - 2.0 = 3.1 GPU-s** (sampler 2.3 + decode 0.65 + small change).
With one sampler pipeline, xpu:0 and xpu:1 then set the pace: 1.32 and
1.01 s of compute per clip in the control placement, so no better than ~1.3 s
per clip (~19 fps-equivalent) however idle xpu:2/xpu:3 are, until work moves
there.

A second, independent two-card sampler on xpu:2/xpu:3 needs what xpu:0/xpu:1
hold today: 23.9 / 21.3 GB allocated and **30.5 / 29.5 GB reserved** (91c
text-encoder receipts, including both workers' static buffers and graph
pools), out of about 32.6 GB per card.

- It fits **only if the whole text encoder leaves the GPUs** (15.3 GB on
  xpu:2, 10.9 GB on xpu:3). The VAEs (1.84 GB) can stay on xpu:3 (29.5 + 1.84
  = 31.3 GB, about 1.2 GB spare: within the band where the lane has seen
  driver paging) or sit beside the existing xpu:1 replica, which 91c proved
  exact and which fits.
- Total demand: 2 x (42 GB weights + ~15 GB buffers) + 1.84 GB of VAEs ≈ 116 GB
  of ~130 GB, so the 26 GB encoder has no resident home. A prompt change
  would have to evict something and reload ~26 GB over PCIe (on the order of
  1-2 s plus 96 graph recaptures), unless per-pipeline buffers shrink (one
  clip in flight per pipeline could roughly halve the 6.5-8.2 GB of reserve
  per card) far enough to fit a four-way encoder shard into the slack. That is
  speculative.
- Throughput if it fits: per clip ~2.95 GPU-s over four cards, a 0.74 s floor
  (~34 fps-equivalent) at perfect balance; at the 83 % efficiency seen in 91c,
  about 0.9 s per clip (~27 fps-equivalent). Each pipeline alone runs today's
  ~1.6 s interval, with decode alternating across the two VAE copies.

## What I could not determine offline

- Whether any window L keeps fp32 GEMM and masked-SDPA rows bit-identical on
  oneDNN/XPU (the whole value of item 1), and which SDPA backend fp32 with a
  float mask takes.
- The actual milliseconds of a connector pass (items 2 and 3 are FLOP
  estimates bounded by packet 65's 0.35 s outside the forwards).
- Why the copy engine reads 0.84-1.14 s busy per clip when the bytes account
  for about a tenth of that; whether D2D copies use the copy engine; the real
  pinned and pageable PCIe bandwidths on this host.
- Whether every Gemma Linear takes the per-call weight-upcast path (the 6.8x
  fp32 GEMM penalty says the GEMMs are fp32; the cast cost itself is not
  measured).
- Upsampler GPU time in the current placement.

## Suggested order

1. Items 2 + 3 + 4 together in one sealed packet: all exact by construction
   or already qualified, about 0.12-0.19 GPU-s off xpu:0 and ~0.75 GB off
   xpu:2's copies. One oracle-gated control/candidate pair.
2. The item 1 census (a + b above) as an offline probe, once GPU use is
   authorised. It decides whether fresh-prompt 24 fps is within reach
   (5.1 - ~1.4 ≈ 3.7 GPU-s < 4.17) or only the repeated-prompt workload can
   get there.
3. Items 5-7 and 9 together (encoder and sampler copy elision), after the
   copy-counter question is settled, so the gain can be attributed.
