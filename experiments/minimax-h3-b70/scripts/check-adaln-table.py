#!/usr/bin/env python3
"""Is Comfy-Org's pruned MiniMax-H3 `adaln_t_table` an exact re-parameterisation?

CPU only, numpy only, memory-bounded (streams tensors in row chunks; never holds
more than a few hundred MB).

Full model (diffusers `MiniMaxH3Transformer3DModel`, see
diffusers/src/diffusers/models/transformers/transformer_minimax_h3.py):

    temb  = time_embedder(Timesteps(256, flip_sin_to_cos=True,
                                    downscale_freq_shift=0)(t))          # f32
          = proj_out(silu(proj_in(sinusoid(t))))
    m(t)  = adaln_proj.linear(silu(temb).to(bf16))                       # [96768]

Pruned model: m(t) ~= W8 @ adaln_t_table[i] + b8, with W8 [96768, 8] f16 and a
single shared table [1025, 8] f32 for all 50 blocks + final_layer.
"""

import argparse, json, os, struct, sys
import numpy as np

# ---------------------------------------------------------------- safetensors
def st_header(path):
    with open(path, "rb") as f:
        n = struct.unpack("<Q", f.read(8))[0]
        return json.loads(f.read(n)), 8 + n

_DT = {"F32": (np.float32, 4), "F16": (np.float16, 2), "BF16": (np.uint16, 2),
       "F64": (np.float64, 8)}

def st_read(path, hdr, base, key, row0=None, row1=None):
    """Read tensor `key`, optionally only rows [row0, row1), as float32."""
    e = hdr[key]
    dt, isz = _DT[e["dtype"]]
    shape = list(e["shape"])
    off = base + e["data_offsets"][0]
    if row0 is not None:
        stride = int(np.prod(shape[1:])) if len(shape) > 1 else 1
        off += row0 * stride * isz
        cnt = (row1 - row0) * stride
        shape = [row1 - row0] + shape[1:]
    else:
        cnt = int(np.prod(shape))
    with open(path, "rb") as f:
        f.seek(off)
        a = np.frombuffer(f.read(cnt * isz), dtype=dt, count=cnt)
    if e["dtype"] == "BF16":
        a = bf16_to_f32(a)
    return a.astype(np.float32).reshape(shape)

def bf16_to_f32(u16):
    return (u16.astype(np.uint32) << 16).view(np.float32)

def f32_to_bf16(x):
    """round-to-nearest-even bf16, returned as float32 (the value, not bits)."""
    u = np.ascontiguousarray(x, dtype=np.float32).view(np.uint32)
    lsb = (u >> 16) & 1
    r = (u + 0x7FFF + lsb) & 0xFFFF0000
    return r.view(np.float32)

# ------------------------------------------------------------------- the math
def silu(x):
    return x / (1.0 + np.exp(-x, dtype=np.float64)).astype(x.dtype) if False else \
           (x * (1.0 / (1.0 + np.exp(-x.astype(np.float64))))).astype(np.float32)

def timesteps_embed(t, dim=256, max_period=10000.0, flip_sin_to_cos=True,
                    downscale_freq_shift=0.0):
    """diffusers get_timestep_embedding, float32 math."""
    half = dim // 2
    exponent = -np.log(max_period) * np.arange(half, dtype=np.float32)
    exponent = exponent / (half - downscale_freq_shift)
    emb = t[:, None].astype(np.float32) * np.exp(exponent, dtype=np.float32)[None, :]
    out = np.concatenate([np.sin(emb), np.cos(emb)], axis=-1)
    if flip_sin_to_cos:
        out = np.concatenate([out[:, half:], out[:, :half]], axis=-1)
    return out.astype(np.float32)

def time_embedder(sin_emb, w1, b1, w2, b2):
    h = sin_emb @ w1.T + b1
    h = silu(h)
    return (h @ w2.T + b2).astype(np.float32)

# ------------------------------------------------------------------ reporting
def stats(name, err, ref):
    a = np.abs(err)
    denom = np.maximum(np.abs(ref), 1e-30)
    rel = a / denom
    scale = np.abs(ref).max()
    print(f"  {name}: max|err|={a.max():.6e}  rms={np.sqrt((err.astype(np.float64)**2).mean()):.6e}"
          f"  max rel(elemwise)={rel.max():.6e}  max|err|/max|m|={a.max()/scale:.6e}")
    return a

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--full-dir", default="/mnt/fast-ai/llm-models/minimax-h3/transformer")
    ap.add_argument("--pruned-dir", required=True, help="dir with the .bin blobs fetched by range request")
    ap.add_argument("--blocks", default="0,25")
    ap.add_argument("--grid", default="i/1024")
    ap.add_argument("--chunk", type=int, default=8192)
    ap.add_argument("--grid-check", default="0",
                    help="block index to run the off-grid interpolation check on ('' to skip)")
    args = ap.parse_args()

    # ---- locate keys across the sharded full model -------------------------
    shards, where = {}, {}
    for fn in sorted(os.listdir(args.full_dir)):
        if not fn.endswith(".safetensors"):
            continue
        p = os.path.join(args.full_dir, fn)
        h, b = st_header(p)
        shards[p] = (h, b)
        for k in h:
            if k != "__metadata__":
                where[k] = p
    te = [k for k in where if "time_embed" in k]
    print("time embedder keys:", sorted(te))

    def get(key, **kw):
        p = where[key]
        h, b = shards[p]
        return st_read(p, h, b, key, **kw)

    def pick(*cands):
        for c in cands:
            if c in where:
                return c
        raise KeyError(cands)

    k1w = pick("time_embedder.proj_in.weight", "time_embedder.linear_1.weight")
    k1b = k1w.replace("weight", "bias")
    k2w = pick("time_embedder.proj_out.weight", "time_embedder.linear_2.weight")
    k2b = k2w.replace("weight", "bias")

    # ---- timestep grid -> temb -> silu(temb) -------------------------------
    n = 1025
    i = np.arange(n, dtype=np.float32)
    t = eval(args.grid, {"i": i, "np": np, "n": n})
    sin_emb = timesteps_embed(t.astype(np.float32))
    w1, b1 = get(k1w), get(k1b)
    w2, b2 = get(k2w), get(k2b)
    print(f"proj_in {w1.shape} proj_out {w2.shape}  dtypes "
          f"{shards[where[k1w]][0][k1w]['dtype']}/{shards[where[k2w]][0][k2w]['dtype']}")
    temb = time_embedder(sin_emb, w1, b1, w2, b2)          # [1025, 2688] f32
    S = silu(temb)                                          # adaln input, f32
    S_bf = f32_to_bf16(S)                                   # what the bf16 linear sees
    del w1, b1, w2, b2, sin_emb

    # ---- the shared table --------------------------------------------------
    T = np.fromfile(os.path.join(args.pruned_dir, "adaln_t_table.bin"),
                    dtype=np.float32).reshape(n, 8)

    # SVD of the *shared* activation matrix: this is what bounds every block.
    sv = np.linalg.svd(S, compute_uv=False)
    mean_S = S.mean(axis=0)
    Sc = S - mean_S
    Uc, svc, Vtc = np.linalg.svd(Sc, full_matrices=False)
    print("\n== silu(temb) over the grid, [1025 x 2688] ==")
    print("  raw      sv[0:12] =", np.array2string(sv[:12], precision=6))
    print("  centered sv[0:12] =", np.array2string(svc[:12], precision=6))
    print(f"  raw      rank-8 truncation ||S-S8||_F/||S||_F      = "
          f"{np.sqrt((sv[8:]**2).sum())/np.sqrt((sv**2).sum()):.6e}")
    print(f"  centered rank-8 truncation ||Sc-Sc8||_F/||Sc||_F   = "
          f"{np.sqrt((svc[8:]**2).sum())/np.sqrt((svc**2).sum()):.6e}")
    print(f"  centered rank-8 truncation ||Sc-Sc8||_F/||S||_F    = "
          f"{np.sqrt((svc[8:]**2).sum())/np.sqrt((sv**2).sum()):.6e}")

    # Which subspace does the table span?  (columns live in R^1025, i.e. over t)
    Q, _ = np.linalg.qr(T)
    for nm, P in (("raw top-8", np.linalg.svd(S, full_matrices=False)[0][:, :8]),
                  ("centered top-8", Uc[:, :8])):
        cs = np.linalg.svd(Q.T @ P, compute_uv=False)
        print(f"  principal cosines(span(table), {nm}) =", np.array2string(cs, precision=8))
    r_aff = Sc - Q @ (Q.T @ Sc)
    print(f"  ||Sc - proj_span(table)(Sc)||_F / ||Sc||_F = "
          f"{np.linalg.norm(r_aff)/np.linalg.norm(Sc):.6e}   (affine fit: bias carries the mean row)")
    # coordinates of the centered activations in the table basis
    TtT_inv = np.linalg.inv((T.T @ T).astype(np.float64)).astype(np.float32)
    Ccoef = (T @ TtT_inv)          # [1025, 8]; W8_ls = (M - b8) @ Ccoef

    # ---- off-grid behaviour: ComfyUI lerps between the two neighbouring rows
    if args.grid_check != "":
        gb = args.grid_check
        kwg = f"transformer_blocks.{gb}.adaln_proj.linear.weight"
        S_mid = silu(time_embedder(timesteps_embed(((i[:-1] + 0.5) / 1024.0).astype(np.float32)),
                                  get(k1w), get(k1b), get(k2w), get(k2b)))
        R = shards[where[kwg]][0][kwg]["shape"][0]
        mx_m = mx_step = mx_snap = mx_lin = 0.0
        for r0 in range(0, R, args.chunk):
            Wc = get(kwg, row0=r0, row1=min(R, r0 + args.chunk))
            Mg = Wc @ S.T; Mm = Wc @ S_mid.T
            mx_m = max(mx_m, float(np.abs(Mg).max()))
            mx_step = max(mx_step, float(np.abs(np.diff(Mg, axis=1)).max()))
            mx_snap = max(mx_snap, float(np.abs(Mm - Mg[:, :-1]).max()))
            mx_lin = max(mx_lin, float(np.abs(Mm - 0.5 * (Mg[:, :-1] + Mg[:, 1:])).max()))
            del Wc, Mg, Mm
        print(f"\n== off-grid t, block {gb} (bias-free part, max|m| = {mx_m:.4f}) ==")
        print(f"  max |m(t_i+1) - m(t_i)| across the 1/1024 grid  = {mx_step:.6e}")
        print(f"  worst-case nearest-grid SNAP error              = {mx_snap:.6e}")
        print(f"  worst-case LINEAR-INTERP error (ComfyUI's lerp) = {mx_lin:.6e}")
        del S_mid

    # ---- per block ---------------------------------------------------------
    for spec in args.blocks.split(","):
        spec = spec.strip()
        if spec == "final":
            kw, fw = "final_layer.adaln_proj.linear.weight", "final_layer_adaln_proj_linear_weight.bin"
            fb = "final_layer_adaln_proj_linear_bias.bin"
        else:
            kw = f"blocks.{spec}.adaln_proj.linear.weight"
            fw = f"blocks_{spec}_adaln_proj_linear_weight.bin"
            fb = f"blocks_{spec}_adaln_proj_linear_bias.bin"
        kb = kw.replace("weight", "bias")
        if kw not in where:
            alt = "norm_out.linear.weight" if spec == "final" else kw.replace("blocks.", "transformer_blocks.")
            if alt in where:
                kw, kb = alt, alt.replace("weight", "bias")
            else:
                print(f"\n!! {kw} not found in full model; keys sample:",
                      sorted(where)[:5]); continue
        e = shards[where[kw]][0][kw]
        R, C = e["shape"]
        print(f"\n===== {kw}  {e['dtype']} {e['shape']} =====")

        W8 = np.fromfile(os.path.join(args.pruned_dir, fw), dtype=np.float16).reshape(R, 8)
        b8 = np.fromfile(os.path.join(args.pruned_dir, fb), dtype=np.float16).reshape(R)
        b_full = get(kb)
        print(f"  bias: pruned f16 vs full {shards[where[kb]][0][kb]['dtype']}  "
              f"max|diff|={np.abs(b8.astype(np.float32)-b_full).max():.6e}  "
              f"identical after f16 round-trip: "
              f"{np.array_equal(b8, b_full.astype(np.float16))}")

        m_pr = (W8.astype(np.float32) @ T.T) + b8.astype(np.float32)[:, None]  # [R, 1025]

        gram = np.zeros((n, n), dtype=np.float64)
        gram_c = np.zeros((n, n), dtype=np.float64)
        maxabs = 0.0; sq = 0.0; cnt = 0; mmax = 0.0
        allerr = []; allref = []
        w8_ls = np.zeros((R, 8), dtype=np.float32)
        maxabs_bf = 0.0; maxabs_ls = 0.0; sq_ls = 0.0; maxabs_bfref = 0.0; sq_bfref = 0.0
        bias_hat = np.zeros(R, dtype=np.float32)   # W @ mean_S + b_full
        for r0 in range(0, R, args.chunk):
            r1 = min(R, r0 + args.chunk)
            Wc = get(kw, row0=r0, row1=r1)                    # [c, 2688] f32
            Mc = Wc @ S.T                                     # [c, 1025], no bias
            full = Mc + b_full[r0:r1, None]
            bias_hat[r0:r1] = Wc @ mean_S + b_full[r0:r1]
            gram += Mc.T.astype(np.float64) @ Mc.astype(np.float64)
            Mcc = full - full.mean(axis=1, keepdims=True)
            gram_c += Mcc.T.astype(np.float64) @ Mcc.astype(np.float64)
            err = m_pr[r0:r1] - full
            maxabs = max(maxabs, float(np.abs(err).max()))
            mmax = max(mmax, float(np.abs(full).max()))
            sq += float((err.astype(np.float64) ** 2).sum()); cnt += err.size
            allerr.append(np.abs(err).astype(np.float32).ravel()[::13].copy())
            allref.append(np.abs(full).astype(np.float32).ravel()[::13].copy())
            Mc_bf = f32_to_bf16(Wc) @ S_bf.T + f32_to_bf16(b_full[r0:r1])[:, None]
            maxabs_bf = max(maxabs_bf, float(np.abs(m_pr[r0:r1] - Mc_bf).max()))
            maxabs_bfref = max(maxabs_bfref, float(np.abs(Mc_bf - full).max()))
            sq_bfref += float(((Mc_bf - full).astype(np.float64) ** 2).sum())
            # least-squares W8 given the stored bias b8 and the stored table
            w8_ls[r0:r1] = (full - b8[r0:r1].astype(np.float32)[:, None]) @ Ccoef
            els = w8_ls[r0:r1] @ T.T + b8[r0:r1].astype(np.float32)[:, None] - full
            maxabs_ls = max(maxabs_ls, float(np.abs(els).max()))
            sq_ls += float((els.astype(np.float64) ** 2).sum())
            del Wc, Mc, full, err, Mc_bf, Mcc, els

        rms = np.sqrt(sq / cnt)
        print(f"  m_full range +-{mmax:.4f}")
        print(f"  pruned vs full (f32 reference):  max|err| = {maxabs:.6e}   rms = {rms:.6e}"
              f"   max|err| / max|m| = {maxabs/mmax:.6e}")
        print(f"  pruned vs full (bf16 runtime path): max|err| = {maxabs_bf:.6e}")
        print(f"  BASELINE  full-bf16 runtime path vs the same f32 reference: max|err| = {maxabs_bfref:.6e}"
              f"   rms = {np.sqrt(sq_bfref/cnt):.6e}   <- error the unpruned checkpoint already has")

        db = b8.astype(np.float32) - b_full
        print(f"  bias: max|b8 - b_full| = {np.abs(db).max():.6e}   "
              f"max|b8 - (W@mean(S)+b_full)| = {np.abs(b8.astype(np.float32)-bias_hat).max():.6e}   "
              f"b8 == f16(W@mean(S)+b_full) for {np.mean(b8 == bias_hat.astype(np.float16)):.4f} of rows")

        ae = np.concatenate(allerr); ar = np.concatenate(allref)
        big = ar > 0.05 * mmax
        print("  |err| percentiles:", {f"p{q}": f"{np.percentile(ae, q):.3e}" for q in (50, 90, 99, 99.9, 100)})
        print(f"  relative error on outputs with |m| > 5% of peak ({big.sum()} samples): "
              f"max = {(ae[big]/ar[big]).max():.4e}  p99 = {np.percentile(ae[big]/ar[big], 99):.4e}")
        hist, edges = np.histogram(np.log10(np.maximum(ae, 1e-12)), bins=12)
        print("  log10|err| histogram (1/13 subsample, %d pts):" % ae.size)
        for h, lo, hi in zip(hist, edges[:-1], edges[1:]):
            print(f"    [{lo:6.2f},{hi:6.2f}) {h:9d}  {100*h/ae.size:6.2f}%")

        for nm, G in (("raw (bias excluded)", gram), ("row-mean-centered", gram_c)):
            ev = np.linalg.eigvalsh(G)[::-1]
            svm = np.sqrt(np.maximum(ev, 0))
            print(f"  singular values of the modulation matrix [{R} x {n}], {nm}:")
            print("   ", np.array2string(svm[:11], precision=5))
            print(f"    sv[8]/sv[0] = {svm[8]/svm[0]:.6e}   rank-8 truncation "
                  f"||M-M8||_F/||M||_F = {np.sqrt((svm[8:]**2).sum())/np.sqrt((svm**2).sum()):.6e}"
                  f"   absolute ||M-M8||_F = {np.sqrt((svm[8:]**2).sum()):.6e}")

        d = w8_ls - W8.astype(np.float32)
        ulp = np.abs(np.nextafter(W8, np.float16(np.inf)).astype(np.float32) - W8.astype(np.float32))
        print("  W8 (f16) vs the exact least-squares W in the stored table basis / stored bias:")
        print(f"    max|W8 - W_ls| = {np.abs(d).max():.6e}   rms = {np.sqrt((d.astype(np.float64)**2).mean()):.6e}")
        print(f"    f16(W_ls) == W8 elementwise for {np.mean(w8_ls.astype(np.float16) == W8):.6f} of entries")
        print(f"    max |W8 - W_ls| / ulp(W8) = {np.nanmax(np.abs(d)/np.maximum(ulp,1e-12)):.4f}"
              f"   (<=0.5 <=> pure f16 rounding of the exact fit)")
        m_ls = w8_ls @ T.T
        m_r = W8.astype(np.float32) @ T.T
        print(f"    error contributed by the f16 rounding of W8 alone: max = {np.abs(m_r - m_ls).max():.6e}"
              f"   (of a total max error of {maxabs:.6e})")
        # error of the *ideal* rank-8 affine fit in this basis (f32 W8)
        print(f"    SAME table, SAME bias, but a float32 least-squares W8: max|err| = {maxabs_ls:.6e}"
              f"   rms = {np.sqrt(sq_ls/cnt):.6e}   <- pure rank-8 truncation error, no f16 loss")
        del W8, b8, m_pr, w8_ls, gram, gram_c

if __name__ == "__main__":
    main()
