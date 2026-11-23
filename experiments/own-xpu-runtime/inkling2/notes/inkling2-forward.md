# Inkling-2-Mini text forward pass, as llama.cpp computes it

Source: Unsloth llama.cpp fork `b12588-mix-c0c3de8` (read-only copy in
the unpacked release source tarball).
Model: `/mnt/fast-ai/llm-models/Inkling-2-Mini-GGUF/Inkling-2-Mini-UD-IQ4_XS.gguf` (only the header was read).
Scope: text only, one sequence, decode (1 token) and prompt (ubatch of N tokens).

## 0. Conventions, file legend, constants

### 0.1 Notation

- ggml shapes are written `[ne0, ne1, ne2, ...]`. `ne0` is the contiguous (fastest) axis.
- A weight `W [in, out]` in ggml means each of the `out` rows holds `in` contiguous values.
  `ggml_mul_mat(W, x)` with `x [in, T]` gives `y [out, T]`, `y[o,t] = sum_i W[i,o] * x[i,t]`.
- `rms(x)` = `x * 1/sqrt(mean_i(x_i^2) + eps)` over `ne0`, no gamma. `RMSNorm_w(x)` = `rms(x) * w`.
- `il` = layer application (0..47). `ip` = physical layer (0..23), whose weights are `blk.ip.*`.
- `T` = tokens in the ubatch. `pos[t]` = absolute position (0-based).
- `E = 2304` (n_embd), `H = 24` query heads, `Hkv = 8` KV heads, `D = 128` head dim, `R = 16` relative dim.

### 0.2 File legend (all paths relative to the source tree)

| short name | path |
|---|---|
| inkling2.cpp | src/models/inkling2.cpp |
| llama-hparams.cpp / .h | src/llama-hparams.cpp, src/llama-hparams.h |
| llama-model.cpp | src/llama-model.cpp |
| llama-graph.cpp | src/llama-graph.cpp |
| llama-kv-cache.cpp | src/llama-kv-cache.cpp |
| llama-kv-cache-iswa.cpp | src/llama-kv-cache-iswa.cpp |
| llama-memory-recurrent.cpp | src/llama-memory-recurrent.cpp |
| llama-memory-hybrid-iswa.cpp | src/llama-memory-hybrid-iswa.cpp |
| llama-context.cpp | src/llama-context.cpp |
| llama-vocab.cpp | src/llama-vocab.cpp |
| ops.cpp | ggml/src/ggml-cpu/ops.cpp |
| ggml-cpu.c | ggml/src/ggml-cpu/ggml-cpu.c |
| x86/quants.c | ggml/src/ggml-cpu/arch/x86/quants.c |
| cpu/quants.c | ggml/src/ggml-cpu/quants.c |
| vec.cpp / vec.h | ggml/src/ggml-cpu/vec.cpp, vec.h |
| ggml.c / ggml.h | ggml/src/ggml.c, ggml/include/ggml.h |
| ggml-common.h | ggml/src/ggml-common.h |
| ggml-quants.c | ggml/src/ggml-quants.c |
| ggml-impl.h | ggml/src/ggml-impl.h |
| tiled.cpp | ggml/src/ggml-cpu/tiled/tiled.cpp |
| repack.cpp | ggml/src/ggml-cpu/repack.cpp |
| dspark.cpp | src/models/dspark.cpp |
| speculative.cpp | common/speculative.cpp |
| conv/inkling2.py | conversion/inkling2.py (the HF to GGUF converter) |

### 0.3 Hyperparameters (GGUF header, read with a header-only parser)

| GGUF key | value | read at |
|---|---|---|
| inkling2.block_count (n_layer_all) | 48 (layer applications, not physical layers) | llama-model.cpp:1534 |
| inkling2.num_loops (loop_n_pass) | 3 | llama-model.cpp:1701 |
| inkling2.loop.core_start / core_end | 6 / 18 | llama-model.cpp:1698-1700 |
| inkling2.loop.gate_rank | 64 | inkling2.cpp:65 |
| embedding_length | 2304 | |
| attention.head_count / head_count_kv | 24 / 8 (all 48) | |
| attention.key_length / value_length (and _swa) | 128 / 128 | |
| attention.layer_norm_rms_epsilon | 9.999999974752427e-07 (float 1e-6) | inkling2.cpp:14 |
| attention.qk_clip | 22.627416610717773 (float sqrt(512)) | inkling2.cpp:15 |
| attn_res.block_size | 6 | inkling2.cpp:16 |
| shortconv.l_cache (n_conv) | 4 | inkling2.cpp:17 |
| attention.relative_length (n_relative) | 16 | inkling2.cpp:20 |
| attention.relative_extent | 1024 | inkling2.cpp:21 |
| attention.relative_clip | 8.0 | inkling2.cpp:22 |
| attention.log_scale_floor | 8192 | inkling2.cpp:23 |
| attention.log_scale_alpha | 0.10000000149011612 | inkling2.cpp:24 |
| vocab_size / vocab_size_unpadded | 201024 / 200058 | inkling2.cpp:27-28 |
| expert_count / expert_used_count | 128 / 8 | |
| expert_feed_forward_length | 1152 | inkling2.cpp:31 |
| activation.situ_beta / situ_linear_beta | 4.0 / 25.0 | inkling2.cpp:33-34 |
| expert_weights_scale | 8.0 | inkling2.cpp:35 |
| final_logit_softcapping | 30.0 | inkling2.cpp:37-38 |
| attention.sliding_window (n_swa) | 1024 | inkling2.cpp:41 |
| attention.sliding_window_pattern | 48 bools, `false` exactly at il % 6 == 5 | inkling2.cpp:42 |
| rope.dimension_count | 0 (no RoPE at all) | inkling2.cpp:76-77 |

Set in code, not in the file: `swa_type = STANDARD`, `expert_router_f32 = true`,
`expert_weights_norm_eps = 1e-20f` (inkling2.cpp:72-74);
`n_sconv_channels = max_il(2*n_embd_k_gqa + 2*n_embd) = 2*1024 + 2*2304 = 6656` (inkling2.cpp:80-96).

Cross-check with the official config (`base-config.json`): hidden 2304, 24 physical layers,
`local_layer_ids` = all except 5, 11, 17, 23; `d_rel 16`, `rel_extent 1024`, `log_scaling_n_floor 8192`,
`alpha 0.1`, `use_value_norm_no_gamma true`, `qk_l2_clip_threshold 22.627416997969522`,
`rel_l2_clip_threshold 8.0`, `sconv_kernel_size 4`, `n_layers_per_attn_res_block 6`,
`attn_res_normalize_values true`, `mlp_gate_softcap 4.0`, `mlp_up_softcap 25.0`, `route_scale 8.0`,
`use_gate_bias true`, loop core 6..18 x 3 passes, gate_rank 64. All match.

### 0.4 Tensor inventory (physical layer `p`, 24 layers, 734 tensors)

GGUF data starts at offset 11978720 (tensor-info end 11978691, default alignment 32).

| tensor | ggml shape | type in this file | notes |
|---|---|---|---|
| token_embd.weight | [2304, 201024] | Q8_0 | padded vocab rows |
| token_embd_norm.weight | [2304] | F32 | |
| output.weight | [2304, 201024] | Q6_K | |
| output_norm.weight, output_res_query.weight | [2304] | F32 | |
| loop_res_query.weight, loop_kv_res_query.weight | [2304, 24] | F32 | 2 rows per core layer |
| blk.p.attn_q.weight | [2304, 3072] | Q8_0 (Q6_K in p 1,18-21,23; Q5_K in p 22) | |
| blk.p.attn_k.weight | [2304, 1024] | Q8_0 (Q6_K in p 20-23) | |
| blk.p.attn_v.weight | [2304, 1024] | Q8_0 | |
| blk.p.attn_output.weight | [3072, 2304] | Q8_0 | |
| blk.p.attn_gate.weight | [2304, 3072] | Q8_0 (Q6_K in p 20,22,23) | |
| blk.p.attn_rel.weight | [2304, 384] | Q8_0 (Q6_K in p 2,5,7,13,23) | 384 = 16*24 |
| blk.p.attn_rel_bias.weight | [16, 1024] | F32 | |
| blk.p.attn_rel_clip.weight | [16, 24] | F32 | |
| blk.p.attn_q_clip.weight | [128, 24] | F32 | |
| blk.p.attn_sink_proj.weight | [2304, 24] | BF16 | |
| blk.p.attn_k_conv / attn_v_conv.weight | [4, 1024] | F32 | |
| blk.p.attn_post_conv / ffn_post_conv.weight | [4, 2304] | F32 | |
| blk.p.attn_norm.weight | [2304] | F32 | SWA layers only |
| blk.p.attn_{q,k,v}_inp_norm.weight | [2304] | F32 | full layers only (p 5, 11, 17, 23) |
| blk.p.attn_{k,v}_conv_proj.weight | [2304, 32] | BF16 | full layers only, 32 = 4 taps * 8 KV heads |
| blk.p.attn_res_query.weight | [2304] (SWA) / [2304, 3] (full) | F32 | absent for p = 0 |
| blk.p.ffn_res_query.weight, ffn_norm.weight | [2304] | F32 | |
| blk.p.ffn_gate_inp.weight | [2304, 128] | F32 | router |
| blk.p.exp_probs_b.bias | [128] | F32 | selection bias |
| blk.p.ffn_gate_up_exps.weight | [2304, 2304, 128] | NVFP4 (p 0-19), Q5_K (20,21), Q4_K (22), IQ4_XS (23) | rows 0..1151 gate, 1152..2303 up |
| blk.p.ffn_down_exps.weight | [1152, 2304, 128] | NVFP4 (p 0-19), Q5_0 (20-22), IQ4_NL (23) | |
| blk.p.ffn_gate_up_exps.scale, ffn_down_exps.scale | [128] | F32 | p 0-19 only (the NVFP4 layers) |
| blk.p.loop_{attn,k,v,mlp}_down.weight | [4608, 64] | F32 | core p 6-17 only |
| blk.p.loop_{attn,k,v,mlp}_{gain,forget}.weight | [64, 2304] | F32 | core p 6-17 only |

Shapes are created at inkling2.cpp:112-199. Type counts: F32 508, Q8_0 126, NVFP4 40, BF16 32, Q6_K 19,
Q5_K 3, Q5_0 3, Q4_K 1, IQ4_XS 1, IQ4_NL 1.

---

## 1. Layer schedule, caches, conv state

### 1.1 Loop functions

```
loop_n_extra()   = (loop_n_pass - 1) * (core_end - core_start) = 2 * 12 = 24      llama-hparams.cpp:371-373
loop_layer(il)   = il                                  if il < 6
                 = 6 + (il - 6) % 12                   if il < 6 + 3*12 = 42
                 = il - 24                             otherwise                     llama-hparams.cpp:375-384
loop_visit(ip)   = ip if ip < 18 else ip + 24          (first application of ip)     llama-hparams.cpp:386-388
n_layer()        = n_layer_all - n_layer_nextn = 48                                  llama-hparams.cpp:367-369
physical layers  = 48 - 24 = 24                                                      llama-hparams.cpp:390-392
pass (core only) = (il - 6) / 12  in {0, 1, 2}                                       inkling2.cpp:371
```

- Weights are loaded once per physical layer `i < 24` into `layers[i]` (inkling2.cpp:122-192), then copied
  to every application: `layers[il] = layers[loop_layer(il)]`, iterating il from 47 down (llama-model.cpp:2087-2093).
- The loader checks that every application has the same SWA flag, head counts and FFN sizes as the first
  visit of its physical layer (llama-model.cpp:1712-1720).
- `is_swa(il)` reads the 48-entry pattern by application index (llama-hparams.cpp:310-316). With this file,
  `is_swa(il) = (il % 6 != 5)`. The physical layer type matches because 6 and 12 are multiples of 6.

### 1.2 The 48 applications

Full (non-SWA) applications: il = 5, 11, 17, 23, 29, 35, 41, 47 (physical 5, 11, 17, 11, 17, 11, 17, 23).
All other 40 applications are SWA (window 1024).

| il | ip | pass | controllers (messages) |
|---|---|---|---|
| 0-5 | 0-5 | prelude | no |
| 6-17 | 6-17 | 0 | no |
| 18-29 | 6-17 | 1 | yes |
| 30-41 | 6-17 | 2 | yes |
| 42-47 | 18-23 | coda | no |

The full per-application trace of the residual blocks is in section 3.6.

### 1.3 Memory: one KV cache and one conv state per application

Memory type: `llama_memory_hybrid_iswa` with both filters returning `true` for every il
(llama-model.cpp:3455-3458, 3497-3514; llama-memory-hybrid-iswa.cpp:33-63).

KV caches (llama_kv_cache_iswa, llama-kv-cache-iswa.cpp:53-105):
- base cache holds the applications with `!is_swa(il)`, SWA cache holds `is_swa(il)` (filters at :53-67).
- `llama_kv_cache` loops `il < hparams.n_layer_all` (= 48) and allocates a separate K and V tensor for every
  application that passes the filter (llama-kv-cache.cpp:102, 165-250). `has_kv(il)` is true for all il
  because `kv_source_impl` is the identity (llama-model.cpp:1593). There is no KV sharing between passes:
  **each of the 48 applications has its own K/V cache** (8 in the base cache, 40 in the SWA cache).
- Per application: `K [1024, kv_size]` and `V [1024, kv_size]`, type F16 by default
  (llama-context.cpp:4503-4504; common/common.h:632-633). Row of 1024 = 8 KV heads x 128, head-major.
  With flash attention on, V is not transposed (`v_trans = !flash_attn`, llama-model.cpp:3502).
- Base cache size = `n_ctx_seq` cells. SWA cache size = `GGML_PAD(min(n_ctx, n_swa*1 + n_ubatch), 256)`
  (llama-kv-cache-iswa.cpp:73), for example 1536 cells with n_ubatch 512. SWA cells outside the window are
  reused (llama-kv-cache.cpp:1094).
- Bytes per token: 8 full apps x 4096 B = 32 KiB per token of context, plus the fixed SWA caches.
- No Hadamard rotation of K/V: only created for quantized KV types (llama-kv-cache.cpp:311-326).

Conv (recurrent) state (llama_memory_recurrent, llama-memory-recurrent.cpp:30, 74-108):
- One tensor `r_l[il]` per application, il in 0..47 (`n_layer = hparams.n_layer()` = 48, filter always true).
  **Each application has its own conv state**, so the 3 loop passes do not share conv history.
- `r_l[il]` is F32 `[n_embd_r, n_rows]`, `n_embd_r = n_sconv_channels * (n_conv - 1) = 6656 * 3 = 19968`
  floats (llama-hparams.cpp:208-217, checked before the LFM2 branch). `n_rows = rs_size * (1 + n_rs_seq)`
  (llama-memory-recurrent.cpp:101).
- Layout of one sequence row (19968 floats): channel-major, 3 time steps per channel, oldest first:
  `state[c*3 + tau]`, tau = 0 is x(t-3), tau = 2 is x(t-1) (relative to the first token of the next ubatch).
- Channel ranges inside the row (offsets passed to `convolve`, inkling2.cpp:449-452, 596, 636):

| channels | content | offset arg |
|---|---|---|
| 0 .. 1023 | K projection input of the K conv | 0 |
| 1024 .. 2047 | V projection input of the V conv | n_embd_k_gqa = 1024 |
| 2048 .. 4351 | wo output (input of attn_post_conv) | 2*1024 = 2048 |
| 4352 .. 6655 | MoE output (input of ffn_post_conv) | 2*1024 + 2304 = 4352 |

- What is stored is the raw conv input (pre-conv value), not the conv output (section 4.3).
- A new sequence starts from a zeroed state (`rs_z` row is filled with 0, llama-graph.cpp:4284-4285).
- Reading: `build_rs` gathers the state rows first (`ggml_get_rows`, llama-graph.cpp:4293); the stores come
  later in graph order, so every application reads the state from before the current ubatch.
- Writing (`build_conv_state_store`, llama-graph.cpp:4358-4385, case `n_rs_seq == 0`): the last 3 columns of
  the concatenated `[past(3) | current(T)]` sequence are copied into the row.
- Speculative rollback (`n_rs_seq > 0`, inkling2 supports it, llama-arch.cpp:1569-1592): K = n_rs_seq + 1
  snapshot slots per row, written by `ggml_set_rows` (llama-graph.cpp:4387-4415). Not needed for plain decode.
- Size: 48 x 19968 x 4 B = 3.83 MB per sequence.

---

## 2. Embedding

```
x = dequant_row(token_embd, token_id)            # Q8_0 row: x[i] = fp16_to_fp32(d_blk) * q[i]   (ggml-quants.c:585)
E = RMSNorm_{token_embd_norm}(x), eps = 1e-6     # inkling2.cpp:347-352, build_norm llama-graph.cpp:2001+
cur = E
```

- `build_inp_embd` is a plain `ggml_get_rows` with `tok_scale = 1` (llama-graph.h:1328, llama-graph.cpp:2928).
- The norm is skipped for raw-embedding (image) batches only (inkling2.cpp:349-352).
- CPU rms_norm: `sum += (double)(x*x)` (product in float, sum in double), `mean = (float)(sum/E)`,
  `scale = 1.0f/sqrtf(mean + eps)`, `y = x*scale*w` (ops.cpp:4157-4182).

---

## 3. Depth attention: mix(), blocks, loop passes, control()

### 3.1 mix(blocks, cur, query) (inkling2.cpp:221-234)

```
states  = concat(reshape(b, [E,1,T]) ... , dim 1)        # order along dim 1: [b_last, ..., b_1, b_0, cur]
states  = rms(states)  (eps 1e-6, over ne0 = E, separately for each state and token, no gamma)
queries = repeat(query [E, nq], [E, nq, T])               # nq = 1, 2 or 3
scores[s,q,t] = sum_e states[e,s,t] * query[e,q]          # ggml_mul_mat(states, queries) -> [S, nq, T]
p[:,q,t] = softmax_s( scores[:,q,t] * (1/sqrtf(2304)) )   # = 1/48, softmax over the S states (ne0)
out[e,q,t] = sum_s states[e,s,t] * p[s,q,t]               # mul_mat(cont(transpose(states)), p) -> [E, nq, T]
```

- The output is a weighted sum of the **normalized** states (rms without gamma), not of the raw states.
  This matches `attn_res_normalize_values = true` in the official config.
- The concat (inkling2.cpp:224) puts each block in front of the previous `states`, so the ggml order is
  newest block first, `cur` last. Only the float summation order depends on this.
- The softmax is `ggml_soft_max_ext(scores, NULL, 1/sqrt(E), 0)`: CPU computes `w = x*scale`, `max`,
  `exp(w - max)`, sum in double, multiply by `1/sum` (ops.cpp:5909-5946). For S <= 7 the scalar `expf` tail
  loop is used (vec.cpp:773-777).
- S is between 2 and 5 (section 3.6).

### 3.2 Blocks and the residual rule (inkling2.cpp:354, 414, 600-605)

At each application, `inpSA = cur` (the input of the application). After attention:

```
if ip % 6 == 0:   blocks.push_back(inpSA);  cur = attn_out          # a new residual stream starts
else:             cur = inpSA + attn_out
ffn_inp = cur
cur = ffn_inp + ffn_out                                              # inkling2.cpp:639
```

So at il = 0 the block list becomes [E], and the stream continues with the attention output only (no
residual add at block starts). Pushes happen at ip = 0, 6, 12, 18 (il = 0, 6, 12, 18, 24, 30, 36, 42).

### 3.3 Loop passes: prelude and bank (inkling2.cpp:356-400)

For applications with ip in [6, 18):

```
if ip == 6:
    if pass == 0:  prelude_blocks = blocks;  prelude_cur = cur           # blocks = [E], cur = h5
    else:          bank      = blocks[len(prelude_blocks) + 1 :]          # skip E and h5
                   bank_last = cur                                        # output of the previous pass
                   blocks    = prelude_blocks;  cur = prelude_cur         # restart from [E], h5
```

Every pass restarts from the prelude state h5. The previous pass reaches the current one only through the
messages. At ip = 6 of pass 1, `bank = [h11]`, `bank_last = h17`; at pass 2, `bank = [h23]`, `bank_last = h29`
(h_k = output of application k). The bank stays fixed for the whole pass.

### 3.4 Messages (pass 1 and 2 only, inkling2.cpp:385-399)

```
row    = 2*(ip - 6)                                      # 0, 2, ..., 22
q_attn = loop_res_query   rows [row, row+1]   ([E, 2])
q_kv   = loop_kv_res_query rows [row, row+1]  ([E, 2])
m_attn = mix(bank, bank_last, q_attn)    # [E, 2, T], states = [bank[0], bank_last] -> S = 2
m_kv   = mix(bank, bank_last, q_kv)
messages[0] (q)   = m_attn row 0
messages[3] (mlp) = m_attn row 1
messages[1] (k)   = m_kv   row 0
messages[2] (v)   = m_kv   row 1
```

The same query rows and the same controller weights are used in pass 1 and pass 2 (they depend on ip only).

### 3.5 control(cur, message, layer, m) (inkling2.cpp:236-246)

```
h      = [ rms(cur) ; rms(message) ]               # eps 1e-6 each, concatenated -> [2E = 4608, T]
z      = loop_down[m]   @ h                        # [4608, 64]  -> [64, T]
gain   = tanh(loop_gain[m]   @ z)                  # [64, 2304]  -> [2304, T]
forget = tanh(loop_forget[m] @ z)
return (1 - forget) * cur + gain * message         # 1 - forget via scale_bias(forget, -1, 1)
```

Module index m: 0 = q (`loop_attn_*`), 1 = k (`loop_k_*`), 2 = v (`loop_v_*`), 3 = mlp (`loop_mlp_*`)
(inkling2.cpp:180-190). All controller weights are F32.

### 3.6 Trace of the states used by each mix

h_k = output of application k (l_out), E = normalized embedding. States are listed oldest first; ggml
concatenates them as `[newest block, ..., oldest block, cur]`.

| il | ip | pass | attn-input mix states | after attention | FFN-input mix states | bank (pass > 0) |
|---|---|---|---|---|---|---|
| 0 | 0 | - | none (blk.0 has no attn_res_query) | push E; cur = attn | [E, ffn_inp] | |
| 1-5 | 1-5 | - | [E, h(il-1)] | cur = inpSA + attn | [E, ffn_inp] | |
| 6 | 6 | 0 | [E, h5] | push h5; cur = attn | [E, h5, ffn_inp] | |
| 7-11 | 7-11 | 0 | [E, h5, h(il-1)] | add | [E, h5, ffn_inp] | |
| 12 | 12 | 0 | [E, h5, h11] | push h11; cur = attn | [E, h5, h11, ffn_inp] | |
| 13-17 | 13-17 | 0 | [E, h5, h11, h(il-1)] | add | [E, h5, h11, ffn_inp] | |
| 18 | 6 | 1 | [E, h5] | push h5; cur = attn | [E, h5, ffn_inp] | [h11, h17] |
| 19-23 | 7-11 | 1 | [E, h5, h(il-1)] | add | [E, h5, ffn_inp] | [h11, h17] |
| 24 | 12 | 1 | [E, h5, h23] | push h23; cur = attn | [E, h5, h23, ffn_inp] | [h11, h17] |
| 25-29 | 13-17 | 1 | [E, h5, h23, h(il-1)] | add | [E, h5, h23, ffn_inp] | [h11, h17] |
| 30 | 6 | 2 | [E, h5] | push h5; cur = attn | [E, h5, ffn_inp] | [h23, h29] |
| 31-35 | 7-11 | 2 | [E, h5, h(il-1)] | add | [E, h5, ffn_inp] | [h23, h29] |
| 36 | 12 | 2 | [E, h5, h35] | push h35; cur = attn | [E, h5, h35, ffn_inp] | [h23, h29] |
| 37-41 | 13-17 | 2 | [E, h5, h35, h(il-1)] | add | [E, h5, h35, ffn_inp] | [h23, h29] |
| 42 | 18 | - | [E, h5, h35, h41] | push h41; cur = attn | [E, h5, h35, h41, ffn_inp] | |
| 43-47 | 19-23 | - | [E, h5, h35, h41, h(il-1)] | add | [E, h5, h35, h41, ffn_inp] | |
| output | | | [E, h5, h35, h41, h47] | | | |

(At il = 18 and 30 the "cur" of the attention mix is h5 again, because of the restart in 3.3.)
The hidden states of pass 0 and pass 1 reach the output only through the messages.

---

## 4. Attention, per application

### 4.1 Inputs and norms (inkling2.cpp:414-444)

```
inputs[0..2] = cur                                           # il = 0: no mix
if attn_res_query exists (all il > 0):
    mixed = mix(blocks, cur, attn_res_query)                 # nq = 1 (SWA) or 3 (full)
    SWA : inputs[0] = inputs[1] = inputs[2] = mixed row 0
    full: inputs[j] = mixed row j   (0 = Q input, 1 = K input, 2 = V input)
if pass > 0 (messages exist):
    inputs[j] = control(inputs[j], messages[j], layer, j) for j = 0, 1, 2      # before the norms
norms:
    SWA without messages: x = RMSNorm_{attn_norm}(inputs[0]); inputs[0..2] = x
    SWA with messages   : inputs[j] = RMSNorm_{attn_norm}(inputs[j]) for j = 0, 1, 2 (same gamma, 3 inputs)
    full                : inputs[0] = RMSNorm_{attn_q_inp_norm}(inputs[0])
                          inputs[1] = RMSNorm_{attn_k_inp_norm}(inputs[1])
                          inputs[2] = RMSNorm_{attn_v_inp_norm}(inputs[2])
eps = f_norm_rms_eps = 1e-6
```

Below, `xq = inputs[0]`, `xk = inputs[1]`, `xv = inputs[2]` (all normalized, [2304, T]).

### 4.2 Projections (inkling2.cpp:446-458, 475, 595)

```
Q    = attn_q   @ xq     -> [3072, T] -> reshape [128, 24, T]     (index d + 128*h)
Kp   = attn_k   @ xk     -> [1024, T]
Vp   = attn_v   @ xv     -> [1024, T]
Rp   = attn_rel @ xq     -> [384, T]  -> reshape [16, 24, T]      (index r + 16*h)
t    = attn_sink_proj @ xq -> [24, T]                             (sink logit per head and token)
G    = attn_gate @ xq    -> [3072, T]                             (output gate, before sigmoid)
dynK = attn_k_conv_proj @ xk -> [32, T] -> [4, 8, T]  (full layers only; index lag + 4*kv_head)
dynV = attn_v_conv_proj @ xv -> [32, T] -> [4, 8, T]  (full layers only)
K    = convolve(Kp, attn_k_conv, dynK, offset 0)        (section 4.3)
V    = convolve(Vp, attn_v_conv, dynV, offset 1024)
```

No biases anywhere in attention. `build_lora_mm` adds nothing for this file (no LoRA, no Hadamard folding,
no per-tensor `.scale`, llama-graph.cpp:1869-1912).

### 4.3 convolve(x, w, dyn, offset) (inkling2.cpp:250-292)

`x` is `[C, T]` (C = 1024 for K/V, 2304 for the post convs), `w` is `[4, C]` (ne0 = tap).

```
past[c, 0..2] = state[(offset + c)*3 + 0..2]          # history view, inkling2.cpp:263, 410
xe[c, 0..2]   = past[c, 0..2]
xe[c, 3 + t]  = x[c, t]            t = 0..T-1          # concat(past, transpose(x)), inkling2.cpp:265-266
store: state[(offset + c)*3 + j] = xe[c, T + j], j = 0..2   # last 3 inputs, inkling2.cpp:268

# ggml_ssm_conv (ops.cpp:10031-10053): float sum, sequential over i0 = 0..3, starting from 0.0f
conv[c, t] = (((0 + xe[c,t]*w[0,c]) + xe[c,t+1]*w[1,c]) + xe[c,t+2]*w[2,c]) + xe[c,t+3]*w[3,c]
           # w[3,c] multiplies the current input x_t, w[2,c] x_{t-1}, w[1,c] x_{t-2}, w[0,c] x_{t-3}

if dyn (full-attention K and V only):                      # inkling2.cpp:273-289
    for lag = 0, 1, 2, 3 (in this order):
        conv[c, t] += xe[c, t + 3 - lag] * dyn[lag, c / 128, t]   # lag 0 = current token, lag 3 = x_{t-3}
y[c, t] = (x[c, t] + conv[c, t]) * s
s = 1.0f / sqrtf(9) = 1/3   for dynamic convs (full K and V)
s = 1.0f / sqrtf(5)          otherwise (SWA K and V, attn_post_conv, ffn_post_conv)
```

Note the opposite tap order: static `w[i0]` multiplies `x_{t-3+i0}`, dynamic `dyn[lag]` multiplies
`x_{t-lag}`. The converter flipped the checkpoint static taps to fit `ggml_ssm_conv` (conv/inkling2.py:362-365).
The dynamic heads are the 8 KV heads (`n_heads = dyn->ne0 / 4 = 8`, channel c belongs to head c/128).

### 4.4 Clip, V norm, log scale (inkling2.cpp:206-218, 339-345, 455-463)

```
clip(x, scale, thr):                               # per row of ne0 (one head of one token)
    if scale: x = x * scale                        # elementwise per (d, h), broadcast over tokens
    n = sqrtf(sum_d x^2)                           # sum_rows sums in double, ggml_sqr in float
    n = n*1 + 1e-6
    f = clamp(thr / n, 0, 1)
    return x * f

Q = clip(Q [128,24,T], attn_q_clip [128,24], 22.627416610717773)
K = clip(K [128, 8,T], none,                 22.627416610717773)
V = rms(V [128, 8,T]), eps 1e-6, no gamma           # per KV head
R = clip(R [16, 24,T], attn_rel_clip [16,24], 8.0)

full-attention layers only:
    tau[t] = 1 + alpha * logf( max(1, (float(pos[t]) + 1) * (1/8192)) ),  alpha = 0.1f
    Q = Q * tau[t];  R = R * tau[t]      # K is not scaled; tau = 1 exactly for pos < 8191
```

The sum uses `ggml_vec_sum_f32` with a double accumulator (vec.h:1664-1670). `ggml_scale_bias(x, s, b) = s*x + b`
(ggml.h:1365-1370). `ggml_fill(norm, thr)` makes a tensor filled with thr, then `ggml_div`.

K (after clip) and V (after rms) are written to the KV cache of this application, rounded to F16
(`cpy_k`/`cpy_v`, llama-graph.cpp:3911-3925, or inkling2.cpp:491-492 on the banded path).

### 4.5 Relative-position bias (inkling2.cpp:470, 514, 527; llama-kv-cache.cpp:2088-2100)

rel_pos is filled on the host for each (query token i, KV cell j):

```
distance = cell_empty(j) ? -1 : pos_q[i] - pos_k[j]
rel_pos[i, j] = (0 <= distance < extent) ? distance : extent
extent = n_relative_extent = 1024 for the base cache (full layers), n_swa = 1024 for the SWA cache
         (build_inp_mem_hybrid_iswa_rel(hparams.n_relative_extent, hparams.n_swa), inkling2.cpp:295)
```

The bias table per head and token:

```
table[d, h, t] = sum_{r=0..15} attn_rel_bias[r, d] * R[r, h, t],   d = 0..1023
table[1024, h, t] = 0        # padding row: ggml_pad(attn_rel_bias, 0, 1) adds a zero column (inkling2.cpp:527)
bias(i, j, h) = table[rel_pos[i,j], h, i]
```

So the "padding row" means: distance out of range (negative, >= 1024) or empty cell gives bias 0.
For full-attention layers keys more than 1023 positions back are still attended, with zero positional bias
(R still carries tau). For SWA layers those keys are masked anyway (4.6).

### 4.6 Masks (llama-kv-cache.cpp:1747-1912; llama-hparams.h:589-601)

- Causal: key cell masked (-inf) if empty, other sequence, or `pos_k > pos_q` (llama-kv-cache.cpp:1859-1877).
- SWA (SWA cache only, swa_type STANDARD): masked if `pos_q - pos_k >= 1024` (llama-hparams.h:596-601).
  **Key visible iff 0 <= pos_q - pos_k <= 1023** (1024 keys including the token itself).
- The base cache uses `LLAMA_SWA_TYPE_NONE` (llama-kv-cache-iswa.cpp:94-97): causal only.
- Mask type: F16 when flash attention is on, F32 otherwise, shape `[n_kv, T, 1, 1]` (llama-graph.cpp:35-52).
- `n_kv` (columns) = `min(cache_size, max(256, PAD(used_max_p1, 256)))` (llama-kv-cache.cpp:1296-1311).

### 4.7 Softmax with bias and sink (the math)

For query token i, head h (KV head h/3, GQA 24/8), visible keys j:

```
s_j  = (q_h . k_j) * (1/sqrtf(128)) + bias(i, j, h)
p_j  = exp(s_j) / ( exp(t_{h,i}) + sum_k exp(s_k) )           # t = sink logit from attn_sink_proj
o_h  = sum_j p_j * v_j                                         # [128]
attn = concat_h o_h  -> [3072, T]  (index d + 128*h)
```

The scale applies to q.k only, never to the bias or the sink. llama.cpp builds two equivalent forms:

**Dense form** (inkling2.cpp:525-593, llama-graph.cpp:4562-4604): the sink is moved into the bias,
`exp(s - t)/(1 + sum exp(s - t))`:

```
table' = table - t[h, i]                        # all 1025 rows, padding row becomes -t (inkling2.cpp:530)
kq_b[j, i, h] = table'[rel_pos[i,j], h, i]      # get_rows + permute -> [n_kv, T, 24, 1] (inkling2.cpp:557-559)
mask_total = kq_b + mask                        # F32 add (llama-graph.cpp:4597)
if flash_attn: mask_total = fp16(mask_total)    # ROUNDED TO F16 (llama-graph.cpp:4598-4600)
sinks = zeros[24]                               # a zero sink logit per head (inkling2.cpp:533)
```

The dense bias is `n_kv x T x 24`; long ubatches are split into row chunks, only the first chunk stores
K/V (inkling2.cpp:535-592). The chunking does not change the math.

**Banded form** (inkling2.cpp:477-524, ggml.h:2268-2280, ops.cpp:9051-9058):

```
relb[d, h, i] = table[d, h, i]  (d = 0..1023, F32, no padding, no sink)        # inkling2.cpp:514-515
rel_dist = i + (n_kv_b - T) - j           # = pos_q - pos_k because the cache is position-contiguous
s += relb[rel_dist, h, i]  only if 0 <= rel_dist < 1024
s += mask (F16 0/-inf)
sink = t[h, i] (F32, per head and token)                                        # inkling2.cpp:517
```

### 4.8 Which path and kernel runs (CPU backend, default parameters)

Defaults: `flash_attn_type = AUTO` (llama-context.cpp:4493, common/common.h:543). AUTO resolves to
enabled when the FA nodes land on the same device as the layer (llama-context.cpp:700-752), which is the
case on a CPU-only run (CPU `supports_op` returns true for FA and banded FA, ggml-cpu.cpp:424-499).
Default `n_ubatch = 512`, `n_batch = 2048` (common/common.h:495-496). KV type F16.

Banded is used when (inkling2.cpp:298-336): `flash_attn && T > 32`, and per layer: the cache is
position-contiguous (`get_n_kv_pos_contiguous() > 0`: one sequence, cell index == position for all
positions 0..pos_max, the ubatch is the contiguous tail, llama-kv-cache.cpp:1313-1350), head dim 64 or 128,
K/V type F32/F16/BF16, no KV scales, one stream, and the device supports the op.

| case | path | CPU kernel |
|---|---|---|
| decode, T = 1 | dense | `ggml_flash_attn_ext` one_chunk; if n_kv >= 512: split-KV (one chunk per thread, merged by `ggml_flash_attn_ext_reduce_partials`) (ops.cpp:9559-9583) |
| prompt, T <= 32 | dense | one_chunk (ops.cpp:9636-9638) |
| prompt, T > 32, cache contiguous (fresh base cache; SWA cache until it wraps past ~1536 cells) | banded | one_chunk with `rel` (tiled is excluded when `rel != NULL`, ops.cpp:9616) |
| prompt, T > 32, cache not contiguous (SWA layers on long prompts, multi-seq) | dense | T < 64: one_chunk; T >= 64: tiled (ops.cpp:9616-9640) |
| FA disabled (`-fa off`) | dense, non-FA | `mul_mat(K, Q)`, `soft_max_ext(kq, mask_total_F32, scale)` + zero sinks, `mul_mat(V^T, P)` (llama-graph.cpp:3332-3375) |

Kernel details (ops.cpp:8907-9135, one_chunk):
- In this fork F16 has `vec_dot_type = F32` and `vec_dot = ggml_vec_dot_f16_f32` (ggml-cpu.c:225-230).
  So Q is **not** rounded to F16: `q_to_vec_dot` is fp32->fp32 (ops.cpp:8983-8986, 9022). The dot is
  F16 K x F32 Q with F32 accumulation (AVX2+F16C: 4 x 8-lane FMA accumulators, vec.cpp:406-425).
  (Upstream ggml uses F16 here; this is a fork difference.)
- `s = dot * scale` (ops.cpp:9046), then `+ rel` (banded only), then `+ mask` (F16 -> F32) (ops.cpp:9060).
  Masked cells (`mask == -inf`) are skipped before the dot (ops.cpp:9032-9035).
- Online softmax with F32 `M`, `S`, `VKQ` accumulators; V F16 is accumulated with `ggml_vec_mad_f16_f32`
  (ops.cpp:9064-9093). `expf` from libm.
- The sink is folded in after the KV loop, on the chunk with `ic_start == 0` only (ops.cpp:9095-9110).
- Output `VKQ * (1/S)` (ops.cpp:9123-9124), written in `[128, 24, T]` order.
- Tiled path (T >= 64, dense only): Q kept in F32, K converted F16 -> F32, `simd_gemm`, sink read as
  `sinks[h]` only (fine, the dense sinks are per head zeros) (ops.cpp:9137-9420).

Precision consequence: on the default CPU path, **decode adds `fp16(bias - sink)` to the scores**, while
banded prompt processing adds the F32 bias and the F32 sink. The two paths are not bitwise equal.

### 4.9 Output gate, wo, post conv (inkling2.cpp:595-597)

```
a   = attn [3072, T] * sigmoid(G)            # sigmoid(x) = 1/(1 + expf(-x)), vec.h:965
a   = attn_output @ a                        # [3072, 2304] -> [2304, T]
out = convolve(a, attn_post_conv, none, offset 2048)    # scale 1/sqrt(5)
```

Then the residual rule of 3.2.

---

## 5. MoE

### 5.1 FFN input (inkling2.cpp:607-616)

```
x = mix(blocks, ffn_inp, ffn_res_query)         # blocks already include the push of this application
if pass > 0: x = control(x, messages[3], layer, 3)
x = RMSNorm_{ffn_norm}(x), eps 1e-6
```

### 5.2 build_moe_ffn for this call (inkling2.cpp:618-634 -> llama-graph.cpp:2392-2880)

Arguments: `up_exps = gate_exps = NULL`, `gate_up_exps = ffn_gate_up_exps`, `down_exps = ffn_down_exps`,
`exp_probs_b`, n_expert 128, n_used 8, `LLM_FFN_SITU`, `norm_w = true`, `w_scale = 8.0`, gating SIGMOID,
`up_exps_s = ffn_gate_up_exps.scale`, `gate_exps_s = NULL`, `down_exps_s = ffn_down_exps.scale`.

```
logits[e,t] = ffn_gate_inp[:, e] . x[:, t]           # F32 x F32 (llama-graph.cpp:2475); prec F32 hint is a no-op on CPU
probs       = sigmoid(logits)                         # llama-graph.cpp:2498
sel         = probs + exp_probs_b                     # selection only (llama-graph.cpp:2517)
ids[0..7]   = argsort_desc(sel)[0..7]                 # std::sort, not stable; slot order = descending sel
w[k]        = probs[ids[k]]                           # unbiased sigmoid (llama-graph.cpp:2574)
w[k]        = w[k] / (sum_k w[k] + 1e-20)             # sum_rows (double acc), scale_bias, div (:2582-2606)
w[k]        = w[k] * 8.0                              # llama-graph.cpp:2611
```

No expert groups (n_expert_groups not set), no softmax.

### 5.3 Experts (llama-graph.cpp:2648-2803, 1951-1999)

For each token t and slot k with expert e = ids[k]:

```
gu    = W_gu[e] @ x_t                      # [2304] ; mul_mat_id
gu    = gu * gate_up_scale[e]              # per-expert F32 scalar, only where the .scale tensor exists (p 0-19)
g     = gu[0 .. 1151]                      # gate = first half (view offset 0, llama-graph.cpp:2667)
u     = gu[1152 .. 2303]                   # up   = second half (view offset n_ff, :2670)
act   = (4 * tanh(g * 0.25)) * sigmoid(g)  # SITU gate, beta = 4       (llama-graph.cpp:2736-2750)
u'    = 25 * tanh(u * (1/25.0f))           # linear-beta clamp, lb = 25 (applied because lb > 0)
h     = act * u'                           # [1152]
y     = W_down[e] @ h                      # [2304]
y     = y * down_scale[e]                  # only p 0-19
y     = y * w[k]                           # llama-graph.cpp:2834
moe   = y[slot 0] + y[slot 1] + ... + y[slot 7]   # sequential adds in slot order (llama-graph.cpp:2854-2860)
```

Exact SITU op order (ggml ops): `ggml_scale(g, 1/beta)`, `tanh`, `ggml_scale(., beta)`,
`ggml_mul(., sigmoid(g))`, `ggml_scale(u, 1/lb)`, `tanh`, `ggml_scale(., lb)`, `ggml_mul(act, u')`.
`1/beta = 0.25f` exactly; `1/lb = 0.04f` (float rounding).

Where the scales come from: the generic pass in llama-model.cpp:1926-1999 loads
`blk.i.ffn_down_exps.scale` into `ffn_down_exps_s` (:1988-1990) and, because the layer has
`ffn_gate_up_exps`, loads `blk.i.ffn_gate_up_exps.scale` into `ffn_up_exps_s` (:1997-1999).
`ffn_gate_exps_s` stays NULL. Each scale is `[128]` F32. In `build_lora_mm_id` the scale is
`get_rows(repeat(reshape(scale, [1, 128, 1]), [1,128,T]), ids)` -> `[1, 8, T]` and multiplies the
matmul output before anything else (llama-graph.cpp:1972-1979). For gate_up it scales both halves,
before SITU. For down it scales before the router weight. The scale is the ModelOpt global scale
`amax / outer_scale_denominator` per expert (conv/inkling2.py:221-230, 351).

The gate/up order was produced by the converter from interleaved checkpoint rows: even rows -> first half
(gate), odd rows -> second half (up) (conv/inkling2.py:83-89).

### 5.4 Post conv and residual (inkling2.cpp:636-640)

```
f   = convolve(moe, ffn_post_conv, none, offset 4352)   # scale 1/sqrt(5)
cur = ffn_inp + f
```

---

## 6. Output (inkling2.cpp:643-669)

```
y = mix(blocks, cur, output_res_query)          # blocks = [E, h5, h35, h41], cur = h47 -> S = 5
y = RMSNorm_{output_norm}(y), eps 1e-6
t_layer_inp[48] = y                             # (DSpark target feature 48)
y = rows of the output tokens only (inp_out_ids, usually the last token)
z = output @ y                                  # Q6_K [2304, 201024] -> [201024, n_out]
z = 30 * tanh(z * (1/30.0f))                    # ggml_scale, tanh, ggml_scale
logits = z[0 .. 200057]                         # drop the padded vocab (rows 200058..201023)
```

---

## 7. Quant formats and CPU dot-product activation types

### 7.1 NVFP4 (ggml-common.h:236-242, 1177-1181; ggml-quants.c:638-660; ggml-impl.h:524-540)

```
block_nvfp4 (36 bytes, 64 weights):
    uint8 d[4]    # one UE4M3 scale per 16-element sub-block
    uint8 qs[32]  # sub-block s uses qs[8s .. 8s+7]

for s in 0..3, j in 0..7:
    byte = qs[8s + j]
    w[16s + j]     = kvalues_fp4[byte & 0xF] * ue4m3(d[s])
    w[16s + 8 + j] = kvalues_fp4[byte >> 4]  * ue4m3(d[s])

kvalues_fp4 = {0, 1, 2, 3, 4, 6, 8, 12, 0, -1, -2, -3, -4, -6, -8, -12}   # 2 * E2M1 value

ue4m3(x):                       # unsigned E4M3, bias 7, returns HALF the value (pairs with the doubled table)
    if x == 0 or x == 0x7F: return 0
    e = (x >> 3) & 0xF;  m = x & 7          # bit 7 is ignored
    raw = (e == 0) ? m * 2^-9 : (1 + m/8) * 2^(e-7)
    return raw * 0.5
```

So a weight is `E2M1(nibble) * E4M3(d)` and the per-expert global scale is applied after the matmul
(section 5.3). There is no activation global scale (no `input_scale` tensors in the file). The converter
rejects scale bytes with bit 7 set or equal to 0x7F (conv/inkling2.py:75-76). Row sizes: gate_up row
(2304 inputs) = 36 blocks = 1296 B, 2304 rows per expert (2,985,984 B); down row (1152 inputs) = 18 blocks
= 648 B, 2304 rows per expert (1,492,992 B).

NVFP4 dot on CPU: `vec_dot_type = Q8_0` (ggml-cpu.c:296-301). One NVFP4 block pairs with 2 Q8_0 blocks.
Generic form (cpu/quants.c:335-368):

```
for each nvfp4 block ib, sub-block s:
    dy   = fp16_to_fp32(y[2ib + s/2].d)
    sumi = sum_{j<8} y.qs[(s%2)*16 + j] * kv[lo nibble] + y.qs[(s%2)*16 + 8 + j] * kv[hi nibble]   (int32, exact)
    sumf += dy * ue4m3(d[s]) * sumi
```

The AVX2 version (x86/quants.c:1086-1140) computes the same integer sums, scale `ue4m3(d[s]) * dy` per
sub-block, and accumulates with `_mm256_fmadd_ps` in 8 lanes, then a horizontal sum.
`build_lora_mm(_id)` sets `GGML_PREC_BF16` on NVFP4 matmuls (llama-graph.cpp:1880-1882, 1967-1969);
the CPU ignores precision hints for matmuls (ggml-cpu.c:1309).

### 7.2 Activation type per weight type (ggml-cpu.c `type_traits_cpu`, :219-430)

The CPU matmul converts src1 (activations, F32) to the weight's `vec_dot_type` once per row
(ggml-cpu.c:1358-1405), then calls `vec_dot` per output element.

| weight type (where) | vec_dot_type (activation) | line |
|---|---|---|
| Q8_0 (most attention weights, token_embd if used as matmul) | Q8_0 | ggml-cpu.c:275-284 |
| Q6_K (output, some attn) | Q8_K | :336-345 |
| Q5_K (gate_up p 20-21, attn_q p 22) | Q8_K | :330-335 |
| Q4_K (gate_up p 22) | Q8_K | :320-329 |
| Q5_0 (down p 20-22) | Q8_0 | :263-268 |
| IQ4_XS (gate_up p 23) | Q8_K | :413-418 |
| IQ4_NL (down p 23) | Q8_0 | :407-412 |
| NVFP4 (experts p 0-19) | Q8_0 | :296-301 |
| BF16 (sink_proj, conv_proj) | BF16 (activation rounded fp32 -> bf16, round-to-nearest-even) | :422-427, ggml-impl.h:739-752 |
| F32 (router, loop controllers, mixes) | F32 | :219-224 |
| F16 (KV cache in attention) | **F32** in this fork (no rounding of Q or P) | :225-230 |

Activation quantizers:
- **Q8_0 (x86 AVX2/AVX build, x86/quants.c:302-345)**: per 32 values, `amax = max|x|`, `d = amax/127`,
  stored as `fp16(d)`; `id = (amax != 0) ? 127/amax : 0`; `q = round_half_even(x * id)` (`_mm256_round_ps`
  nearest). The generic reference (ggml-quants.c:273-296) differs: `id = 1/d`, `roundf` (half away from 0).
  Block `{fp16 d; int8 qs[32]}` = 34 B.
- **Q8_K (x86 uses the reference, x86/quants.c:505-507; ggml-quants.c:2914-2951)**: per 256 values, `max` =
  the signed value with the largest |x| (first one wins), `iscale = -127/max`,
  `q = min(127, nearest_int(iscale * x))` (nearest_int = round half even via the 12582912 trick,
  ggml-quants.c:676-681), `d = 1/iscale` (float, negative when max > 0), `bsums[16]` = sums of 16-groups.
  Block `{float d; int8 qs[256]; int16 bsums[16]}`. All-zero block: d = 0, qs = 0.
- The quantized weight formats Q8_0, Q6_K, Q5_K, Q4_K, Q5_0, IQ4_XS, IQ4_NL are the standard ggml layouts
  (ggml-common.h), unchanged in this fork as far as read.

### 7.3 CPU matmul path selection (affects summation order, not the formulas)

- `llamafile_sgemm` (tinyBLAS) is compiled in by default (top CMakeLists.txt:168) and tried first, but it
  returns false for `n < 2` (sgemm.cpp ~4361), so **decode (1 token) always uses the vec_dot path**.
  For prompts it runs on the quantized activations (second call, ggml-cpu.c:1418-1440).
- `ggml_compute_forward_mul_mat_tiled` (tiled.cpp:1209-1223) handles Q6_K, Q5_K, Q4_K, IQ4_XS (and other
  K/IQ types) when src1 has >= 8 rows (per expert for MUL_MAT_ID), unless `GGML_CPU_TILED_MM=0`.
- CPU repack (`GGML_CPU_REPACK` ON by default, ggml/CMakeLists.txt:152): on AVX2, Q4_K -> q4_K_8x8 and
  IQ4_NL -> iq4_nl_8x8 interleaved layouts (repack.cpp:5011-5015, 5078-5082). Only blk.22 gate_up and
  blk.23 down are affected. Q8_0, Q6_K, Q5_K are repacked only on ARM.
- Other CPU op precisions: rms_norm sums in double (ops.cpp:4160-4167); sum_rows in double (vec.h:1664);
  softmax uses a SIMD `ggml_v_expf` for 8-wide chunks and libm `expf` for the tail (vec.cpp:704-777);
  tanh/sigmoid/log use libm `tanhf`, `expf`, `logf` (vec.h:907, 944, 965); `ggml_vec_dot_f32` uses
  4 x 8-lane FMA accumulators on AVX2 (vec.cpp:100-130); the split-KV FA decode depends on the thread count.

---

## 8. Tokenizer and chat template

- `tokenizer.ggml.model = gpt2` (BPE), `pre = inkling2` -> GPT-4o pre-tokenizer regex
  (llama-vocab.cpp:2706-2710, regex at :455-461). 200058 tokens, 424413 merges.
- **No BOS**: `special_bos_id = LLAMA_TOKEN_NULL` for pre `inkling2` (llama-vocab.cpp:2709) and
  `add_bos_token = false`. `add_eos_token = false`.
- EOS = EOT = 200006 `<|content_model_end_sampling|>`. Padding 199999 `<|endoftext|>`.
- Control tokens (type 3): 199998 `<|unused|>`, 199999 `<|endoftext|>`, 200000 `<|message_user|>`,
  200001 `<|message_model|>`, 200002 `<|message_system|>`, 200003 `<|message_tool|>`, 200004 `<|content_text|>`,
  200005 `<|content_image|>`, 200006 `<|content_model_end_sampling|>`, 200008 `<|content_thinking|>`,
  200010 `<|end_message|>`, 200022 `<|content_tool_error|>`, 200024 `<|content_xml|>`,
  200028 `<|begin_of_text|>`, 200049 `<|content_invoke_tool_json|>`, 200057 `<|content_invoke_tool_text|>`;
  the other 44 ids in 200007..200056 are `<|unused_*|>`/reserved.
- Chat template: GGUF key `tokenizer.chat_template` (6868 chars), identical to the official
  `chat_template.jinja`. Shape of a prompt:
  `[<|message_system|><|content_text|>{system}<|end_message|>]`
  `<|message_system|><|content_text|>Thinking effort level: 0.9<|end_message|>` (emitted before the first
  non-system message; default 0.9; "none" prints 0)
  `<|message_user|><|content_text|>{text}<|end_message|>` ...
  Assistant turns are blocks `<|message_model|><|content_thinking|>...<|end_message|>`,
  `<|message_model|><|content_text|>...<|end_message|>`, then `<|content_model_end_sampling|>`.
- The template has no `add_generation_prompt` branch: after the last message the model itself writes
  `<|message_model|>...`. llama.cpp uses a dedicated Inkling handler (common/chat.cpp:1468-1471,
  common/parsers/inkling.cpp:56-80).
- Sampling defaults in the GGUF: temp 1.0, top_k 0, top_p 1.0, min_p 0.

---

## 9. DSpark drafter (short)

- Separate GGUF: `dspark-Inkling-2-Mini-Q8_0.gguf`, `general.architecture = dflash`, 3 layers
  (SWA pattern [T, F, T], window 1024, +1 for the anchor, dspark.cpp:104), dense SwiGLU FFN 9216,
  RoPE theta 1e6 (rope dim 128), q/k head norms, non-causal block, `block_size 8`, `markov_rank 256`,
  `sample_from_anchor false`, no confidence head, softcap 30 (dspark.cpp:79-108, 211-248).
- Target features: `dflash.target_layers = [5, 23, 41, 48]` index `t_layer_inp`: entries 5, 23, 41 are the
  **inputs** of applications 5, 23, 41 (`res->t_layer_inp[il] = cur` before the attention mix,
  inkling2.cpp:412), i.e. h4, h22 (pass 1), h40 (pass 2); entry 48 is the final mixed and `output_norm`-ed
  hidden (inkling2.cpp:646). All tokens, 4 x 2304 floats each (llama-context.cpp:2865-2898).
- Context injection (embd batch): per drafter layer, `softmax(dspark_fuse row)` mixes the 4 features,
  RMSNorm (`dflare_norm`), then `attn_k_ctx`/`attn_v_ctx`, k-norm, RoPE, written into the drafter KV cache
  (dspark.cpp:1004-1035).
- Draft block (token batch): `[anchor, mask x 7]`; the anchor is embedded with the **target** `token_embd`
  and `token_embd_norm`, masks use `mask_embd` (dspark.cpp:1060-1068). After the 3 layers and `output_norm`,
  base logits come from the **target** `output.weight`; a recurrent Markov head (GRU-like gate over
  `joint_proj [5120, 768]`, `markov_w1`, `hidden_out`) adds a correction through the target lm head, then
  softcap 30 (dspark.cpp:946-969, 1092-1125). Each position takes the first maximum (argmax with a
  tie rank, host sampling with temp 0, speculative.cpp:1440-1450). Yields up to 7 draft tokens.
- Verification: the target decodes `[last, d1..dk]` in one batch; `common_sampler_sample_and_accept_n`
  accepts drafts while the target sample equals the draft and stops at EOG (common/sampling.cpp:698-730).
  Rejected positions need the KV cells removed and the conv state rolled back (`n_rs_seq` snapshots, 1.3).

---

## 10. Compact pseudocode (one ubatch, one sequence)

```
E = RMSNorm_tok(emb[ids]);  cur = E;  blocks = []
tau[t] = 1 + 0.1*log(max(1, (pos[t]+1)/8192))
for il in 0..47:
    ip = loop_layer(il); L = layers[ip]; swa = (il % 6 != 5); st = conv_state[il]; kv = kv_cache[il]
    if 6 <= ip < 18:
        pass = (il-6)//12
        if ip == 6:
            if pass == 0: pre_blocks, pre_cur = blocks, cur
            else: bank, bank_last = blocks[len(pre_blocks)+1:], cur; blocks, cur = pre_blocks, pre_cur
        if pass > 0:
            r = 2*(ip-6); ma = mix(bank, bank_last, LRQ[r:r+2]); mk = mix(bank, bank_last, LKVQ[r:r+2])
            msg = [ma[0], mk[0], mk[1], ma[1]]                       # q, k, v, mlp
    inpSA = cur
    x3 = [cur]*3 if il == 0 else rows_of(mix(blocks, cur, L.attn_res_query))   # SWA: one row used 3x
    if msg: x3 = [control(x3[j], msg[j], L, j) for j in 0..2]
    x3 = norms (4.1)
    Q = clip(Wq x3[0], q_clip, 22.6274); K = clip(convolve(Wk x3[1], kconv, dynK?, st, 0), -, 22.6274)
    V = rms(convolve(Wv x3[2], vconv, dynV?, st, 1024)); R = clip(Wrel x3[0], rel_clip, 8)
    if not swa: Q *= tau; R *= tau
    t = Wsink x3[0]; store fp16(K), fp16(V) in kv
    O = attention(Q, kv, bias(R, rel_bias, pos), sink t, scale 1/sqrt(128), mask causal (+SWA 1024))
    a = convolve(Wo (O * sigmoid(Wgate x3[0])), attn_post_conv, -, st, 2048)
    if ip % 6 == 0: blocks.append(inpSA); cur = a
    else:           cur = inpSA + a
    ffn_inp = cur
    x = mix(blocks, cur, L.ffn_res_query); if msg: x = control(x, msg[3], L, 3)
    x = RMSNorm_ffn(x)
    m = MoE(x)   (5.2-5.3)
    cur = ffn_inp + convolve(m, ffn_post_conv, -, st, 4352)
y = RMSNorm_out(mix(blocks, cur, output_res_query))
logits = (30*tanh((Wout y)/30))[:200058]
```

---

## 11. Open questions / unsure

1. **FMA contraction in scalar CPU loops.** `ggml_ssm_conv` (`sumf += s*c`, ops.cpp:10048), `scale_bias`,
   rms_norm `x*scale*w` and similar scalar loops may be fused into FMA by the compiler (`-march=native`,
   GCC default `-ffp-contract=fast` for GNU C/C++). Not determinable from source; matters only for bitwise
   comparison with a CPU build.
2. **Bitwise matching with the CPU is limited** by SIMD reduction trees (vec_dot lanes, split-KV FA merge
   order that depends on the thread count, llamafile/tiled GEMM for prompts, repack kernels for blk.22/23),
   `ggml_v_expf` vs libm, and the unstable `std::sort` for exactly tied expert scores. The deterministic
   parts that can be matched exactly: activation quantization (Q8_0 x86 rule, Q8_K, BF16 RNE), the integer
   block sums, fp16 KV rounding, fp16 rounding of `bias - sink` in the dense FA path, and op order.
3. **Q8_0 activation rule depends on the build.** AVX/AVX2 builds use `127/amax` and round-half-even;
   non-x86 or generic builds use `1/(amax/127)` and `roundf`. Which one to match depends on the reference build.
4. **SWA banded/dense switch point.** The exact token count at which the SWA cache stops being
   position-contiguous depends on cell reuse in `find_slot`/SWA pruning (llama-kv-cache.cpp:1094), not
   traced in detail; it changes only the numeric path (fp16 bias rounding), not the math.
5. **`ggml_flash_attn_ext_reduce_partials` with a zero sink.** In split-KV decode the zero sink is added only
   on thread 0's chunk (ops.cpp:9095-9110); verified by reading, not by running.
6. **Tiled K-quant matmul activation handling** (tiled.cpp) was not read in detail: I assume it quantizes
   activations to Q8_K like the vec_dot path, but did not confirm.
7. **Generation-prompt behaviour.** With no `add_generation_prompt` branch, I assume the model is expected to
   emit `<|message_model|>` itself; the `common_chat_template_generation_prompt_impl` result for this
   template was not traced.
8. **MoE cache** (`llama_moe_cache`, host-resident expert caching) was not read; it only changes where the
   expert weights come from (llama-graph.cpp:2627-2630, 2803-2808), not the math, and is assumed off by default.
9. The DSpark section is deliberately shallow: the Markov head equations (joint_proj chunk order: gate,
   candidate, latent; `state = cand + gate*(state - cand)`) are from dspark.cpp:946-969 but the
   speculative bookkeeping (context feature storage per position, rollback) was only skimmed.
