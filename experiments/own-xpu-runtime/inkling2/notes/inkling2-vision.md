# Inkling-2-Mini image path, as llama.cpp computes it (bytes -> rows the text model reads)

Source: Unsloth llama.cpp fork `b12588-mix-c0c3de8`, read-only copy at
`/home/steve/inkling-work/ref-f32-src/llama.cpp-b12588-mix-c0c3de8` (the lab "oracle" tree, see 5.1).
Model files (headers only were read, with a small header parser):
`/mnt/fast-ai/llm-models/Inkling-2-Mini-GGUF/mmproj-BF16.gguf` (encoder) and `Inkling-2-Mini-UD-IQ4_XS.gguf` (text, template).
Companion: `inkling2-forward.md` (text forward pass). Nothing was built or run for this note.

## 0. Conventions and file legend

- ggml shapes `[ne0, ne1, ...]`, `ne0` contiguous. `W [in, out]` with `ggml_mul_mat(W, x)` gives `y[o] = sum_i W[i,o] x[i]`.
- Padded image `nx x ny` pixels (multiples of 40). `Wp = nx/20`, `Hp = ny/20` patches, `P = Wp*Hp`, `NP = P+1`
  (CLS + patches), `C = 1024`, `NH = 16` heads, `D = 64` head dim, `M = (Wp/2)*(Hp/2)` output rows.

| short name | path (relative to the source tree) |
|---|---|
| inkling2v.cpp | tools/mtmd/models/inkling2v.cpp |
| mtmd-graph.cpp, mtmd-image.cpp/.h, mtmd-impl.h, mtmd-model.cpp/.h, mtmd-subcontext.cpp, mtmd.cpp, mtmd-helper.cpp, mtmd-cli.cpp | tools/mtmd/ |
| stb_image.h | vendor/stb/stb_image.h (v2.32) |
| ggml.c, ggml-impl.h | ggml/src/ |
| ops.cpp, vec.cpp, vec.h, ggml-cpu.c, common.h | ggml/src/ggml-cpu/ |
| inkling2.cpp, llama-graph.cpp, llama-arch.cpp | src/models/inkling2.cpp, src/llama-graph.cpp, src/llama-arch.cpp |
| parsers/inkling.cpp, chat.cpp, arg.cpp, common.cpp | common/parsers/inkling.cpp, common/chat.cpp, common/arg.cpp, common/common.cpp |
| conv/inkling2.py | conversion/inkling2.py (HF -> GGUF) |

---

## 1. mmproj file

GGUF v3, 19 KV, 422 tensors, `general.file_type = 32` (mostly BF16), `general.size_label = 318M`.

### 1.1 Metadata (all 19 keys) and values the loader sets in code

| key | value | used as / read at |
|---|---|---|
| general.architecture | clip | |
| general.type | mmproj | |
| general.name | Inkling-2-Mini | |
| general.size_label | 318M | |
| general.file_type | 32 | |
| general.quantization_version | 2 | |
| clip.has_vision_encoder | true | |
| clip.vision.projector_type | inkling2v | PROJECTOR_TYPE_INKLING2V (mtmd-impl.h:747) |
| clip.vision.image_size | 640 | 32 patches per side of the learned pos grid; only warmup default (mtmd-model.cpp:185, 241) |
| clip.vision.patch_size | 20 | mtmd-model.cpp:186 |
| clip.vision.embedding_length | 1024 | n_embd (mtmd-model.cpp:172) |
| clip.vision.feed_forward_length | 4096 | n_ff |
| clip.vision.block_count | 23 | n_layer |
| clip.vision.attention.head_count | 16 | n_head; n_head_kv defaults to 16 (mtmd-model.cpp:181); d_head = 1024/16 = 64 (mtmd-graph.cpp:30) |
| clip.vision.projection_dim | 2304 | read, not used by the graph (rows are `mm.2` ne1 = 2304, mtmd-model.cpp:5179-5180) |
| clip.vision.image_mean | [0.5, 0.5, 0.5] | mtmd-model.cpp:274-282 |
| clip.vision.image_std | [0.5, 0.5, 0.5] | mtmd-model.cpp:275-282 |
| clip.vision.attention.layer_norm_epsilon | 9.999999747378752e-06 (float 1e-5) | eps of every LayerNorm (mtmd-model.cpp:178) |
| clip.vision.spatial_merge_size | 2 | n_merge (mtmd-model.cpp:864) |

Set in code for INKLING2V (mtmd-model.cpp:860-868, mtmd-model.h:87-91, 261-287):
`ffn_op = FFN_GELU_ERF` (exact erf GELU; overrides the gelu_quick default of mtmd-model.cpp:257-259);
`rope_theta = 10000.0f`; `set_limit_image_tokens(1, 4096)` with `patch_area = 20*20*2*2 = 1600` ->
`image_min_pixels = 1600` (unused by this preprocessor), `image_max_pixels = 4096*1600 = 6,553,600`
(`--image-max-tokens N` replaces 4096, arg.cpp:2628, mtmd-model.cpp:4618-4619);
`image_resize_algo = RESIZE_ALGO_BICUBIC` (default, Pillow-compatible, not overridden); warmup 32x32 tokens.
`kq_scale = 1/sqrtf(64) = 0.125f` (mtmd-graph.cpp:34). No `image_min/max_pixels` or `resize_algo` key in the file.

### 1.2 Tensors (all 23 blocks `N = 0..22` hold the same 18 tensors; checked with a per-name count)

| tensor | ggml shape | type | notes |
|---|---|---|---|
| v.patch_embd.weight | [20, 20, 3, 1024] | F32 | conv kernel: ne0 = kx, ne1 = ky, ne2 = c (R,G,B), ne3 = out. From HF linear [1024, 20*20*3] over HWC patches, permuted to [out, c, ky, kx] (conv/inkling2.py:503-506) |
| v.position_embd.weight | [1024, 1024] | F32 | 32x32 learned grid, row `gy*32 + gx` (see 3.2) |
| v.class_embd | [1024] | F32 | CLS token |
| v.class_position_embd.weight | [1024] | F32 | CLS position embedding |
| v.pre_ln.weight, v.pre_ln.bias | [1024] | F32 | LayerNorm before block 0 |
| v.blk.N.ln1.weight/.bias, v.blk.N.ln2.weight/.bias | [1024] | F32 | pre-attention / pre-FFN LayerNorm |
| v.blk.N.attn_q.weight, attn_k.weight, attn_v.weight | [1024, 1024] | BF16 | separate Q, K, V |
| v.blk.N.attn_q.bias, attn_k.bias, attn_v.bias | [1024] | F32 | |
| v.blk.N.attn_out.weight | [1024, 1024] | BF16 | |
| v.blk.N.attn_out.bias | [1024] | F32 | |
| v.blk.N.ls1.weight, v.blk.N.ls2.weight | [1024] | F32 | per-channel layer scales (HF bare `lambda_1/lambda_2` or `.gamma`, conv/inkling2.py:508-509) |
| v.blk.N.ffn_up.weight | [1024, 4096] | BF16 | |
| v.blk.N.ffn_up.bias | [4096] | F32 | |
| v.blk.N.ffn_down.weight | [4096, 1024] | BF16 | |
| v.blk.N.ffn_down.bias | [1024] | F32 | |
| mm.1.weight | [4096, 4096] | BF16 | HF `proj_in` / `merger.linear_1` (conv/inkling2.py:496) |
| mm.2.weight | [4096, 2304] | BF16 | HF `proj_out` / `merger.linear_2` |

Absent (so skipped by the graph): `v.patch_embd.bias`, `v.post_ln.*`, `mm.1.bias`, `mm.2.bias` (optional loads,
mtmd-model.cpp:2196-2199), FFN gate, fused QKV, Q/K norms, attn/ffn post norms. Count: 4 + 2 + 23*18 + 2 = 422.
Loader: mtmd-model.cpp:2189-2200 (requires class_embd, position_embd, pre_ln), generic names 1604-1691.
`ff_up/ff_down` are not swapped for this projector (mtmd-model.cpp:1714-1730).

---

## 2. Preprocessing (image bytes -> planar F32 tensor `inp_raw [nx, ny, 3, 1]`)

### 2.1 Decode (mtmd-helper.cpp:461-470)
`stbi_load_from_memory(buf, len, &nx, &ny, &nc, 3)`: stb_image v2.32, 8-bit RGB, interleaved, row-major, top row first.
- RGBA/grey-alpha: alpha dropped, no compositing (stb_image.h:1851, 1844, 1908); grey replicated to R=G=B (1841, 1898).
- 16-bit PNG: `v >> 8` (stb_image.h:1265). JPEG: stb's own IDCT and fixed-point YCbCr->RGB (stb_image.h:3726-3727),
  not libjpeg/PIL, so pixels can differ by a few LSB from PIL. No EXIF orientation. WebP goes through the video
  decoder fallback (mtmd-helper.cpp:474-483). For a bit-faithful check feed the same RGB8 bytes to both sides.

### 2.2 Size, optional cap resize (mtmd-image.cpp:2303-2316)
```
align = patch_size * n_merge = 40                                     # :2304
ALIGN(v) = ((v + 39) / 40) * 40   (integer ceil to a multiple of 40)   # mtmd-impl.h:544
too_large = int64(ALIGN(w)) * ALIGN(h) > 6,553,600                    # :2307-2308
```
- Not too large (any image whose padded area is <= 4096 merged tokens): NO resize, NO upscale of small images
  (a 1x1 image becomes one 40x40 tile). The code comment says the HF reference never resizes (:2310).
- Too large: `size = calc_size_preserved_ratio(size, {align 40, max_pixels 6,553,600})` (mtmd-image.cpp:123-161):
  ```
  w_bar = max(40, int(std::round(float(w)/40.0f)) * 40)      # round half away from zero, float division
  h_bar = max(40, int(std::round(float(h)/40.0f)) * 40)
  if h_bar*w_bar > max_pixels (int):
      beta  = sqrtf(float(h) * w / max_pixels)               # float
      h_bar = max(40, int(floorf(float(h)/beta / 40.0f)) * 40)
      w_bar = max(40, int(floorf(float(w)/beta / 40.0f)) * 40)
  ```
  (if the round-to-nearest area already fits, the image is resized to that nearest-40 size, a slight stretch.)
  Then `resize_pillow(BICUBIC)`, no padding (mtmd-image.cpp:39-61, 210-511), Pillow `ImagingResample` clone:
  bicubic `a = -0.5` (:262); per axis `scale = in/out` (double), `filterscale = max(scale, 1)`,
  `support = 2*filterscale`, `ksize = ceil(support)*2+1`; output `xx`: `center = (xx+0.5)*scale`,
  `xmin = max(0, int(center - support + 0.5))`, `xmax = min(in, int(center + support + 0.5))`,
  `w_x = filter((x + xmin - center + 0.5) / filterscale)`, normalized by their double sum, then
  `int32(w*2^22 + (w<0 ? -0.5 : 0.5))` (:379); pass: horizontal first (if width changes) into uint8, then
  vertical; each output `clip8((2^21 + sum p*w) >> 22)` per channel (:406-419, :445-459).
  Example (hand-computed): 4000x3000 -> beta = 1.3532 -> 2920x2200 -> 73*55 = 4015 rows.

### 2.3 Pad bottom/right, rescale and normalize in one step (mtmd-image.cpp:2318-2335, mtmd-impl.h:958-967)
```
nx = ALIGN(w'), ny = ALIGN(h')                     # w', h' = size after 2.2
buf[(y*nx + x)*3 + c] = float(u8[y][x][c])   for x < w', y < h'     # 0..255 as float (copy_n from uint8)
buf[...]              = -1.0f                 in the padding (right columns, bottom rows)
buf = (buf - 127.5f) / 127.5f                  # mean*255 = 127.5f, std*255 = 127.5f, float sub then float div
```
So real pixels map to `(v - 127.5f)/127.5f` in [-1, 1] and padding to `(-1 - 127.5f)/127.5f = -1.0078431f`
(the unit test asserts exactly this, tests/test-mtmd-impl.cpp:282-311). No resampling, no centering, no crop.

### 2.4 Planar layout into the graph (mtmd-subcontext.cpp:804-845)
`inp_raw[x + nx*y + nx*ny*c] = buf[(y*nx + x)*3 + c]` (`F32 [nx, ny, 3, 1]`). One image = one batch entry.

### 2.5 Counts
`rows M = (nx/40) * (ny/40)` (n_output_tokens, mtmd-model.cpp:4834-4839; nx/ny tokens :4697-4698, :4732-4733).
Examples: 640x640 -> 16x16 = 256 rows (no pos-emb resize); 1024x768 -> padded 1040x800 -> Wp=52, Hp=40,
26x20 = 520 rows; max 4096 rows at the default cap.

---

## 3. Encoder forward (inkling2v.cpp:4-33), CPU backend

### 3.1 Patch embedding (build_inp, mtmd-graph.cpp:342-352; ggml_conv_2d, ggml.c:4717-4738)
`ggml_conv_2d` builds `im2col` with `dst_type = (kernel == BF16) ? F32 : F16` (ggml.c:4727); the kernel is F32,
so **im2col is F16**: every normalized pixel is rounded to F16 (RNE, `_cvtss_sh(x,0)`) (ops.cpp:6843-6920).
```
for py in 0..Hp-1, px in 0..Wp-1:  p = py*Wp + px                      # patch order: row-major, x fastest
  col_p[k] = f16(inp_raw[c][20*py+ky][20*px+kx]),  k = c*400 + ky*20 + kx   (k = 0..1199)  # ops.cpp:6896-6905
  E[p][o]  = sum_k f32(col_p[k]) * Wpe[o*1200 + k]       # mul_mat(im2col F16 as src0, kernel F32 as src1)
```
(F16 x F32 dot: `ggml_vec_dot_f16_f32`, 4 x 16-lane F32 FMA accumulators, vec.cpp:380-405.) No bias.
Result is `[C, P]` after the reshape/transpose in build_inp.

### 3.2 Position embeddings (inkling2v.cpp:15; resize_position_embeddings, mtmd-graph.cpp:82-102)
`PE0[gy][gx][c] = v.position_embd.weight[c + 1024*(gy*32 + gx)]` (reshape `[C, 32(x), 32(y)]`, :95).
If `Wp == 32 && Hp == 32`: `PEr = PE0` (:91-93). Otherwise `ggml_interpolate(..., Wp, Hp, C, 1, BILINEAR)`
(:96-99) with no ALIGN_CORNERS and no ANTIALIAS flag, CPU code ops.cpp:8238-8380:
```
fx = (float)Wp / 32.0f ; fy = (float)Hp / 32.0f                       # :8251-8252 (float ne / float ne)
for oy: yy = ((float)oy + 0.5f)/fy - 0.5f ; y0 = (int)floorf(yy) ; y1 = y0 + 1
        y0, y1 = clamp(.., 0, 31) ; dy = clamp(yy - (float)y0, 0, 1)   # dy uses the CLAMPED y0
  for ox: same -> x0, x1, dx
    a = PE0[y0][x0], b = PE0[y0][x1], c = PE0[y1][x0], d = PE0[y1][x1]
    PEr[oy][ox] = a*(1-dx)*(1-dy) + b*dx*(1-dy) + c*(1-dx)*dy + d*dx*dy        # :8376, left to right
```
Half-pixel centers (PyTorch `align_corners=False`), edge clamp, no antialias when downsampling (Wp or Hp < 32),
both axes interpolated whenever either differs from 32 (an axis with factor 1 reproduces its rows exactly).
`E[p] += PEr[py][px]` (inkling2v.cpp:15, F32 add).

### 3.3 Token sequence and position ids
```
cls  = v.class_embd + v.class_position_embd                  # inkling2v.cpp:16
X    = [cls ; E[0] ; ... ; E[P-1]]        [C, NP], row 0 = CLS  # :17 ggml_concat dim 1
pos_w[0] = pos_h[0] = 0                                     # CLS
pos_w[1+p] = px + 1 ; pos_h[1+p] = py + 1   (p = py*Wp + px) # 1-indexed patches, mtmd-subcontext.cpp:904-916
```

### 3.4 ViT blocks (build_vit with NORM_TYPE_NORMAL, mtmd-graph.cpp:107-338; no learned_pos_embd, no mask)
```
LN(x; w, b):                                  # build_norm :399-422, ggml_norm ops.cpp:4030-4075
  s    = (float) sum_double(x[0..1023])       # vec.h:1664-1674
  mean = s / 1024.0f
  y    = x - mean                             # float
  var  = (float)( sum_double_over_64_blocks( float_reduce16(y^2) ) / 1024 )   # vec.cpp:628-702 (AVX-512)
  y    = y * (1.0f / sqrtf(var + 1e-5f))      # ops.cpp:4072
  y    = y * w ; y = y + b                    # separate F32 ops (no RMS norm anywhere)

X = LN(X; pre_ln)                                            # :129-133
for l in 0..22:                                              # :136-317
  h = LN(X; ln1[l])                                          # :146
  q = Wq h + bq ; k = Wk h + bk ; v = Wv h + bv              # :194-207, BF16 weights
  q, k -> [64, 16, NP]  (head n = features 64n .. 64n+63)    # :223-225
  q = rope2d(q) ; k = rope2d(k)                              # :243-248, 3.5
  o = attention(q, k, v) * (scale 0.125), all NP keys, no mask, bidirectional   # 3.6
  o = Wo o + bo                                              # :619-625
  X = X + o * ls1[l]            (ls1 multiply first, then residual add)   # :261-274
  h = LN(X; ln2[l])                                          # :283
  f = Wdown gelu_erf(Wup h + bup) + bdown                    # build_ffn :424-512 (no gate)
  X = X + f * ls2[l]                                         # :302-308
# no post_ln (tensor absent, :330-332)
gelu_erf(x) = 0.5f*x*(1.0f + erff(x*0.70710678118654752440f))   # vec.h:995, 1052-1057 (glibc erff)
```

### 3.5 2D RoPE (build_rope_2d(..., pos_w, pos_h, 10000, interleave=false), mtmd-graph.cpp:631-678)
Two `ggml_rope_ext` calls, mode 0 = NORMAL (adjacent pairs), `n_dims = 64/2 = 32`, `freq_scale = 1`,
`ext_factor = 0` (no YaRN), `attn_factor = 1`; the second gets `ggml_rope_set_offset(.., 32)` (ggml.c:4476-4487).
CPU code ops.cpp:6246-6260 (cache), 6334-6350 (rotate), 6353-6500:
```
s = powf(10000.0f, -2.0f/32)                         # ops.cpp:6414, = powf(10000, -0.0625f)
cache for a position p (int): th = (float)p ; for j = 0..15: c_j = cosf(th), s_j = sinf(th) ; th = th * s
dims  0..31 use p = pos_w :  (x[2j], x[2j+1])       -> (x0*c_j - x1*s_j, x0*s_j + x1*c_j)   # :6478, :6342-6348
dims 32..63 use p = pos_h :  (x[32+2j], x[33+2j])   -> same formula with the pos_h cache
```
`th` is the iterated float product (not `p * s^j` evaluated exactly). Applied to Q and K of all 16 heads and all
NP rows (CLS at (0,0) is unchanged). Frequencies of both halves are identical (`10000^(-j/16)`, j = 0..15).

### 3.6 Attention (build_attn, mtmd-graph.cpp:558-628)
- `-fa off`: `KQ[i][j] = dot(k_j, q_i)` (F32 mul_mat), `soft_max_ext(KQ, null, 0.125, 0)` (ops.cpp:5847-5950):
  `w = KQ*0.125f`; `m = max(w)`; `e = exp(w - m)` (16-lane `ggml_v_expf` blocks, tail `expf`; vec.cpp:704-777);
  `S = sum_double(e)`; `P = e * (float)(1.0/S)`; `o_i = sum_j P[i][j] v_j` (F32 mul_mat with cont V^T, :600-614).
- FA on (the default, 5.2): `K, V = ggml_cast(.., F16)` (:586-587), `ggml_flash_attn_ext(q, k, v, null, 0.125)`,
  F32 accumulation (:591-592). With NP >= 64 the CPU uses the tiled kernel (ops.cpp:9616-9640, 9137-9420):
  Q F32, K/V F16->F32, 64x64 tiles, KQ by `simd_gemm`, `*0.125`, online softmax per 64-key tile (row max,
  `ggml_vec_soft_max_f32`, rescale by `expf(Mold - Mnew)`), `VKQ += P*V`, final `* 1/S`.
Output heads are concatenated back to `[1024, NP]` (head n -> features 64n..64n+63).

### 3.7 Drop CLS, 2x2 merge, projector (inkling2v.cpp:27-30)
```
Y = X[:, 1..NP-1]                                   # view at offset nb[1] (:27) -> [C, P], patch order
# build_patch_merge_permute(Y, 2), mtmd-graph.cpp:718-747 (Wp, Hp are even, so no ggml_pad)
for yb in 0..Hp/2-1, xb in 0..Wp/2-1:  r = yb*(Wp/2) + xb          # output row order, x fastest
  Z[r][c + 1024*(dx + 2*dy)] = Y[(2*yb+dy)*Wp + (2*xb+dx)][c]   for dx, dy in {0,1}, c in 0..1023
  # i.e. Z[r] = [ Y(2xb,2yb) | Y(2xb+1,2yb) | Y(2xb,2yb+1) | Y(2xb+1,2yb+1) ]   (4096 values)
out[r] = mm2 · gelu_erf(mm1 · Z[r])                 # build_ffn(FFN_GELU_ERF), no biases -> [2304, M] F32
```
(derivation: reshape `[2C, Wp/2, Hp]` -> permute -> cont `[4C, Hp/2, Wp/2]` -> permute -> cont `[4C, M]`.)
The final node `projected` is the embedding tensor read back (mtmd-subcontext.cpp:655).

---

## 4. How the text model takes the rows

### 4.1 Rows and positions
- One image = one image chunk of `M` rows, each a contiguous 2304-float row (`n_embd_inp = n_embd = 2304`,
  llama-hparams.cpp:118-130; mtmd-helper.cpp:131). Row order = 3.7 (`r = yb*(Wp/2) + xb`).
- Positions: plain sequential `n_past, n_past+1, ...` (text model rope type NONE -> MTMD_POS_TYPE_NORMAL,
  mtmd.cpp:917-925; `set_position_normal`, mtmd-helper.cpp:156); the chunk advances n_past by M.
- Causal attention as for text (`mtmd_decode_use_non_causal` is false for INKLING2V, mtmd.cpp:4633-4654).
- Decoded in their own ubatches of up to `n_batch` rows (mtmd-helper.cpp:162-176); never mixed with token rows
  (INKLING2 has no mixed-batch support, llama-arch.cpp:1594-1606).

### 4.2 Difference from token rows (inkling2.cpp:347-352, llama-graph.cpp:2875-3050)
- Token rows: `get_rows(token_embd)` then `RMSNorm(eps 1e-6) * token_embd_norm.weight` (only `if (ubatch.token)`).
- Image rows: the F32 projector output is the residual-stream input **as is**: no token_embd lookup, no
  token_embd_norm, no scale (`f_embedding_scale = 0`, llama-hparams.h:292; `tok_scale = 1`, llama-graph.h:1328;
  no `n_embd_inp_impl`). Everything after the input (layers, positions, log-scale tau) is the same as for tokens.

### 4.3 Tokens around an image
- mtmd: `img_beg = "<|content_image|>"`, no `img_end` (mtmd.cpp:1152-1157); `add_media` appends img_beg with
  parse_special, then the image chunk (mtmd.cpp:1951-1953, 2171-2182). No per-row/per-line separators, no
  newline rows, no suffix rows (`MTMD_SUFFIX_NONE`), no image-size text (`has_prompt_img_size` false).
- Chat template (GGUF `tokenizer.chat_template`, line 88 of the extracted text): an image content part renders as
  `<header><|content_image|><|unused_200054|><|end_message|>`, only for user/tool messages. llama.cpp instead
  puts the media marker `<__media__>` (mtmd.cpp:579-580) inside text; `inkling_split_media`
  (parsers/inkling.cpp:8-46, applied by common_chat_params_init_inkling, :61; chosen in chat.cpp:1469-1471) turns
  `<|message_user|><|content_text|><__media__>TEXT<|end_message|>` into
  `<|message_user|><__media__><|end_message|><|message_user|><|content_text|>TEXT<|end_message|>`.
- Resulting sequence (ids from the text GGUF vocab; all type 3 control tokens):
  ```
  ... 200000 <|message_user|>, 200005 <|content_image|>, [M image rows], 200010 <|end_message|>,
      200000 <|message_user|>, 200004 <|content_text|>, <text tokens>, 200010 <|end_message|> ...
  ```
  llama.cpp never emits 200054 `<|unused_200054|>`; the M rows take its place. No BOS (inkling2 vocab,
  see inkling2-forward.md section 8). mtmd-cli single turn prepends one marker per image when the prompt has none
  (mtmd-cli.cpp:602-607), so with the template the full prompt is
  `<|message_system|><|content_text|>Thinking effort level: 0.9<|end_message|>` + the block above; the
  template has no `add_generation_prompt` branch, so the prompt ends at the last `<|end_message|>`.
  Each image of a message gets its own `<|message_user|><|content_image|>...<|end_message|>` block, in marker order.

---

## 5. Precision and nondeterminism in the reference (CPU), and how to switch it off

Build of this tree (build/CMakeCache.txt): CPU only, `GGML_NATIVE=ON` (`-march=native`, AMD EPYC 9015 / Zen 5,
AVX-512 + AVX512_BF16), `GGML_LLAMAFILE=OFF` (note: the other tree `ref-src` has it ON), REPACK on (no BF16/F16/F32
repack), OpenMP, flags `-O3 -std=gnu++17`/`gnu11` without `-ffp-contract=off`.

| # | what | where | effect | switch |
|---|---|---|---|---|
| 1 | BF16 weight matmuls (QKV, out, FFN, mm.1/mm.2): activations rounded to BF16 (RNE) and summed by `_mm512_dpbf16_ps` | ggml-cpu.c:422-427, 1358-1405; vec.cpp:139-170; ggml-impl.h:739-753 | ~3 significant digits on every matmul input | `GGML_CPU_F32_ACT=1` (oracle patch, ggml-cpu.c:3899-3927): exact BF16->F32 weights, F32 activations, double accumulation; prints `INKLING ORACLE: ...` on stderr |
| 2 | Flash attention: K and V cast to F16; tiled online softmax | mtmd-graph.cpp:583-597; ops.cpp:9137-9420 | F16 K/V | `-fa off` (arg.cpp:1738; passed to mtmd at mtmd-cli.cpp:162; the same flag sets the text context, common.cpp:1777). Default is AUTO -> enabled when the backend supports FA (mtmd.cpp:600, mtmd-subcontext.cpp:184-218; check the log line `flash attention is enabled/disabled`) |
| 3 | Patch embedding im2col is F16: normalized pixels rounded to F16 | ggml.c:4727; ops.cpp:6896-6905 | pixel error up to ~2.4e-4 (values `(2v-255)/255` are not F16-exact except +-1) | none: needs a code change (e.g. im2col F32 for an F32 kernel). To be bit-faithful, our engine rounds pixels to F16 RNE before the patch matmul |
| 4 | F16 x F32 patch dot / F32 dots in `-fa off` attention: F32 FMA accumulators | vec.cpp:380-405; ggml-cpu.c:219-230 | order-dependent F32 rounding | `GGML_CPU_F32_ACT=1` makes these double too (F16 and F32 are in the patched list) |
| 5 | Softmax exp: `ggml_v_expf` (SIMD polynomial) on 16-lane blocks, libm `expf` on the tail; sums in double | vec.cpp:704-777 | ~1 ulp | none |
| 6 | libm `cosf/sinf` (RoPE), `erff` (GELU), `sqrtf`, `powf` | ops.cpp:6242-6243, 6414; vec.h:1055 | ulp-level | none |
| 7 | GCC may contract `a*b+c` into FMA in scalar code (RoPE rotate, bilinear sum, GELU) | default `-ffp-contract=fast` for gnu dialects | ulp-level, site-dependent | none (rebuild with `-ffp-contract=off`, or compare with a tolerance) |
| 8 | Pillow bicubic resize (only above 4096 rows) | mtmd-image.cpp:210-511 | integer exact, deterministic | `--image-max-tokens` larger to avoid resizing |

Thread count: as read, every op here computes each output element in one thread (row-partitioned norm/softmax,
per-element dots, per-row FA tiles; the split-KV FA path needs a single query row, ops.cpp:9559), so results should
not depend on `-t`. Recommended oracle run: `GGML_CPU_F32_ACT=1`, `-fa off`, and accept item 3 (or replicate it).
Debug output: `MTMD_DEBUG_EMBEDDINGS=/path` writes the projected rows as `[int32 M][int32 2304][f32 M*2304]`
(mtmd-subcontext.cpp:2946-2964). Named graph tensors (cb, mtmd-graph.cpp:73-79): `patch_embd`, `embeddings`,
`pre_ln`, `layer_inp_normed-l`, `Qcur_pos-l`, `Kcur_pos-l`, `kqv_out-l`, `attn_out-l`, `ffn_inp-l`, `ffn_out-l`,
`layer_out-l`, `encoder_out`, `pixel_shuffle`, `projected`.

---

## 6. UNKNOWN / not verified

- Which scalar expressions GCC actually fused into FMA in this build (item 7); check with `objdump` of
  ops.cpp.o / mtmd-image.cpp.o if bit-exactness of RoPE, bilinear or GELU matters.
- Exact Zen 5 `VDPBF16PS` internal rounding (only matters without `GGML_CPU_F32_ACT=1`).
- glibc versions of `cosf/sinf/erff/expf` (correct rounding not guaranteed).
- How the HF reference uses `<|unused_200054|>` (one placeholder expanded to M slots, or something else) and
  whether its preprocessing truly equals 2.3 (llama.cpp's comments claim so, mtmd-image.cpp:2310, 2329; the HF
  processor is not available locally). The HF reference does not cap/resize large images (comment :2310);
  llama.cpp does above 4096 rows.
- Which of HF `lambda_1` or `.gamma` names the layer scales carry (irrelevant to the math).
