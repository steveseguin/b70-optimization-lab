// Inkling-2's image encoder (Unsloth's mmproj-BF16.gguf; the math as the reference computes it is in
// notes/inkling2-vision.md, sections cited as V2.3 etc.) on the target's card: a picture's RGB pixels -> the rows the
// text model reads in place of token rows (2304 floats each, fed without the token norm, Engine::step).
// Decoding and any resize happen before (the server, with Pillow): this takes 8-bit RGB, pads it to multiples of 40,
// normalizes, rounds to F16 as the reference's im2col does, then runs the 23-block ViT and the projector in F32 with
// fixed summation orders (deterministic; BF16 weights decoded exactly).
#pragma once
#include "engine.hpp"
#include <cmath>
#include <memory>

namespace ink {

struct Vision {
    static constexpr int C = 1024, NH = 16, HD = 64, FF = 4096, NL = 23, PS = 20, GRID = 32, OUT = 2304, KP = 3 * PS * PS;
    static constexpr int TILE = 64; // attention tiles (64 x 64 outputs per work-group, 4 x 4 per thread)
    static constexpr float EPS = 1e-5f;
    Engine &e;
    Device &d;
    std::unique_ptr<GGUF> g;
    Weights wt;
    struct Blk { W ln1w, ln1b, q, qb, k, kb, v, vb, o, ob, ls1, ln2w, ln2b, up, upb, down, downb, ls2; };
    std::vector<Blk> B;
    W patch, pos, cls, clsp, prew, preb, mm1, mm2;
    int max_rows = 4096, max_np = 0, max_side = 0, qb = 1024, rb = 0;
    float *X = nullptr, *H = nullptr, *QKV = nullptr, *A = nullptr, *F = nullptr, *S = nullptr, *rc = nullptr, *rs = nullptr;
    bool ok = false, attn_split = false, attn_v1 = false;
    size_t bytes = 0;
    double last_s = 0;

    explicit Vision(Engine &e_) : e(e_), d(e_.d) {}

    // loads the encoder when it fits beside what the card holds, with INK_SNAP_ROOM_MB (default 256) to spare;
    // INK_VISION_MAX_ROWS (default 4096, the reference's cap) sizes the buffers
    void init(const std::string &path) {
        if (const char *s = std::getenv("INK_VISION_MAX_ROWS")) max_rows = std::max(1, std::atoi(s));
        if (const char *s = std::getenv("INK_VISION_ATTN")) attn_split = std::string(s) == "split", attn_v1 = std::string(s) == "fused1";
        g = std::make_unique<GGUF>(path);
        auto it = g->kv.find("clip.vision.projector_type");
        if (it == g->kv.end() || !std::holds_alternative<std::string>(it->second) || std::get<std::string>(it->second) != "inkling2v")
            throw std::runtime_error("vision: " + path + " is not an Inkling-2 image encoder (clip.vision.projector_type inkling2v)");
        size_t wbytes = 0;
        for (auto &t : g->tensors) wbytes += (t.bytes + 255) & ~(size_t)255;
        max_np = 4 * max_rows + 1;
        max_side = 2 * max_rows; // patches along one side at most: (Wp / 2) * (Hp / 2) <= rows with Hp >= 2
        rb = std::min(e.T, 2048);
        const size_t fl = (size_t)max_np * C * 6 + (size_t)rb * FF + (size_t)qb * max_np + (size_t)2 * (max_side + 1) * 16;
        bytes = wbytes + fl * sizeof(float);
        const size_t spare = (size_t)(std::getenv("INK_SNAP_ROOM_MB") ? std::atol(std::getenv("INK_SNAP_ROOM_MB")) : 256) << 20;
        if (d.allocated + d.hold + bytes + spare > d.limit()) {
            std::fprintf(stderr, "[vision] no room on the card for the image encoder (%.0f MiB; images are refused)\n", bytes / 1048576.0);
            return;
        }
        wt.upload(d, *g, false);
        auto get = [&](const std::string &n) {
            W w;
            w.t = g->find(n);
            if (!w.t) throw std::runtime_error("vision: missing " + n);
            w.p = wt.ptr.at(n);
            w.rb = w.t->row_bytes();
            w.kind = K_RAW;
            return w;
        };
        patch = get("v.patch_embd.weight"); pos = get("v.position_embd.weight");
        cls = get("v.class_embd"); clsp = get("v.class_position_embd.weight");
        prew = get("v.pre_ln.weight"); preb = get("v.pre_ln.bias");
        mm1 = get("mm.1.weight"); mm2 = get("mm.2.weight");
        B.resize(NL);
        for (int l = 0; l < NL; ++l) {
            const std::string p = "v.blk." + std::to_string(l) + ".";
            Blk &b = B[l];
            b.ln1w = get(p + "ln1.weight"); b.ln1b = get(p + "ln1.bias");
            b.q = get(p + "attn_q.weight"); b.qb = get(p + "attn_q.bias");
            b.k = get(p + "attn_k.weight"); b.kb = get(p + "attn_k.bias");
            b.v = get(p + "attn_v.weight"); b.vb = get(p + "attn_v.bias");
            b.o = get(p + "attn_out.weight"); b.ob = get(p + "attn_out.bias");
            b.ls1 = get(p + "ls1.weight"); b.ls2 = get(p + "ls2.weight");
            b.ln2w = get(p + "ln2.weight"); b.ln2b = get(p + "ln2.bias");
            b.up = get(p + "ffn_up.weight"); b.upb = get(p + "ffn_up.bias");
            b.down = get(p + "ffn_down.weight"); b.downb = get(p + "ffn_down.bias");
        }
        X = d.alloc<float>((size_t)max_np * C);
        H = d.alloc<float>((size_t)max_np * C);
        QKV = d.alloc<float>((size_t)max_np * C * 3);
        A = d.alloc<float>((size_t)max_np * C);
        F = d.alloc<float>((size_t)rb * FF);
        S = d.alloc<float>((size_t)qb * max_np);
        rc = d.alloc<float>((size_t)(max_side + 1) * 16);
        rs = d.alloc<float>((size_t)(max_side + 1) * 16);
        ok = true;
        std::fprintf(stderr, "[vision] image encoder on the card (%.0f MiB, up to %d rows per image)\n", bytes / 1048576.0, max_rows);
    }

    static int align40(int v) { return (v + 39) / 40 * 40; }
    // rows a w x h picture gives (V2.5; the caller resizes pictures above the cap first, V2.2)
    static int64_t rows_for(int w, int h) { return (int64_t)(align40(w) / 40) * (align40(h) / 40); }

    const float *f32(const W &w) const { return (const float *)w.p; }

    void mm(const W &w, const float *x, float *y, int n) { // in steps of at most T rows (the engine's buffers)
        const int cols = (int)w.t->ne[0], rows = (int)w.t->rows();
        e.xd_src = nullptr;
        for (int r0 = 0; r0 < n; r0 += e.T)
            e.mm(w, x + (size_t)r0 * cols, y + (size_t)r0 * rows, std::min(e.T, n - r0));
    }

    // LayerNorm of rows of C floats (V3.4): mean, centered values, variance, then * w + b; x and y may be the same
    void layer_norm(const float *x, float *y, const W &w, const W &b, int nrows) {
        const float *w_ = f32(w), *b_ = f32(b);
        e.pr("v_norm", d.q.submit([&](sycl::handler &h) {
            sycl::local_accessor<float, 1> slm(ops::OPS_WG / SG, h);
            h.parallel_for(ops::rows_range(nrows), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(SG)]] {
                const int r = (int)it.get_group(0), l = (int)it.get_local_id(0);
                constexpr int MV = C / ops::OPS_WG;
                const float *xr = x + (size_t)r * C;
                float xv[MV];
                float s = 0.0f;
#pragma unroll
                for (int u = 0; u < MV; ++u) { xv[u] = xr[l + ops::OPS_WG * u]; s += xv[u]; }
                const float mean = ops::wg_sum<ops::OPS_WG>(it, s, &slm[0]) / (float)C;
                float s2 = 0.0f;
#pragma unroll
                for (int u = 0; u < MV; ++u) { xv[u] = xv[u] - mean; s2 = mac(s2, xv[u], xv[u]); }
                const float var = ops::wg_sum<ops::OPS_WG>(it, s2, &slm[0]) / (float)C;
                const float sc = 1.0f / sycl::sqrt(var + EPS);
                float *yr = y + (size_t)r * C;
#pragma unroll
                for (int u = 0; u < MV; ++u) {
                    const int i = l + ops::OPS_WG * u;
                    yr[i] = (xv[u] * sc) * w_[i] + b_[i];
                }
            });
        }));
    }

    void add_bias(float *y, const W &b, int n, int nrows) {
        const float *b_ = f32(b);
        e.pr("v_bias", d.q.parallel_for(sycl::range<1>((size_t)nrows * n), [=](sycl::id<1> id) { y[id] += b_[id % n]; }));
    }

    // X += (Y + b) * ls  (V3.4: the bias, then the layer scale, then the residual add)
    void residual(float *x, const float *y, const W &b, const W &ls, int nrows) {
        const float *b_ = f32(b), *l_ = f32(ls);
        e.pr("v_res", d.q.parallel_for(sycl::range<1>((size_t)nrows * C), [=](sycl::id<1> id) {
            const int c = (int)(id[0] % C);
            x[id] = x[id] + (y[id] + b_[c]) * l_[c];
        }));
    }

    // y = gelu_erf(y + b) (b may be null), rows of n
    void gelu(float *y, const float *b, int n, int nrows) {
        e.pr("v_gelu", d.q.parallel_for(sycl::range<1>((size_t)nrows * n), [=](sycl::id<1> id) {
            const float v = b ? y[id] + b[id % n] : y[id];
            y[id] = 0.5f * v * (1.0f + sycl::erf(v * 0.70710678118654752440f));
        }));
    }

    // 2D RoPE of the 16 heads of each row (V3.5): dims 0..31 by the column (pos_w), 32..63 by the row (pos_h);
    // the CLS row is at (0, 0), patch p at (p % Wp + 1, p / Wp + 1); adjacent pairs, cos/sin from the host tables
    void rope(float *x, int np, int wp) {
        const float *c_ = rc, *s_ = rs;
        e.pr("v_rope", d.q.parallel_for(sycl::range<2>((size_t)np, (size_t)NH * 32), [=](sycl::id<2> id) {
            const int i = (int)id[0], hh = (int)id[1] / 32, j = (int)id[1] % 32;
            const int pw = i == 0 ? 0 : (i - 1) % wp + 1, ph = i == 0 ? 0 : (i - 1) / wp + 1;
            const int hf = j / 16, jj = j % 16, p = hf ? ph : pw;
            float *v = x + (size_t)i * C + hh * HD + hf * 32 + 2 * jj;
            const float co = c_[p * 16 + jj], si = s_[p * 16 + jj];
            const float x0 = v[0], x1 = v[1];
            v[0] = x0 * co - x1 * si;
            v[1] = x0 * si + x1 * co;
        }));
    }

    // S[i][j] = (q_i . k_j) * 0.125 for the query rows i0..i0+nq of head hh against all np keys (V3.6, -fa off)
    void scores(const float *q, const float *k, int hh, int i0, int nq, int np) {
        float *S_ = S;
        const int ldS = np;
        const size_t gi = (size_t)(nq + TILE - 1) / TILE * 16, gj = (size_t)(np + TILE - 1) / TILE * 16;
        e.pr("v_scores", d.q.submit([&](sycl::handler &h) {
            sycl::local_accessor<float, 2> qs(sycl::range<2>(TILE, HD + 1), h), ks(sycl::range<2>(TILE, HD + 1), h);
            h.parallel_for(sycl::nd_range<2>(sycl::range<2>(gi, gj), sycl::range<2>(16, 16)), [=](sycl::nd_item<2> it) {
                const int ti = (int)it.get_local_id(0), tj = (int)it.get_local_id(1);
                const int bi = (int)it.get_group(0) * TILE, bj = (int)it.get_group(1) * TILE;
                const int t = ti * 16 + tj;
                for (int e2 = t; e2 < TILE * HD; e2 += 256) {
                    const int r = e2 / HD, c = e2 % HD;
                    qs[r][c] = bi + r < nq ? q[(size_t)(i0 + bi + r) * C + hh * HD + c] : 0.0f;
                    ks[r][c] = bj + r < np ? k[(size_t)(bj + r) * C + hh * HD + c] : 0.0f;
                }
                sycl::group_barrier(it.get_group());
                float acc[4][4] = {};
                for (int c = 0; c < HD; ++c) {
                    float a[4], b[4];
#pragma unroll
                    for (int u = 0; u < 4; ++u) { a[u] = qs[ti + 16 * u][c]; b[u] = ks[tj + 16 * u][c]; }
#pragma unroll
                    for (int u = 0; u < 4; ++u)
#pragma unroll
                        for (int v = 0; v < 4; ++v) acc[u][v] = mac(acc[u][v], a[u], b[v]);
                }
#pragma unroll
                for (int u = 0; u < 4; ++u)
#pragma unroll
                    for (int v = 0; v < 4; ++v) {
                        const int i = bi + ti + 16 * u, j = bj + tj + 16 * v;
                        if (i < nq && j < np) S_[(size_t)i * ldS + j] = acc[u][v] * 0.125f;
                    }
            });
        }));
    }

    // each row of S: exp(s - max) / sum (V3.6)
    void softmax(int nq, int np) {
        float *S_ = S;
        e.pr("v_softmax", d.q.submit([&](sycl::handler &h) {
            sycl::local_accessor<float, 1> slm(ops::OPS_WG / SG, h);
            h.parallel_for(ops::rows_range(nq), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(SG)]] {
                const int r = (int)it.get_group(0), l = (int)it.get_local_id(0);
                float *sr = S_ + (size_t)r * np;
                float m = -INFINITY;
                for (int j = l; j < np; j += ops::OPS_WG) m = sycl::fmax(m, sr[j]);
                m = sycl::reduce_over_group(it.get_group(), m, sycl::maximum<float>());
                float s = 0.0f;
                for (int j = l; j < np; j += ops::OPS_WG) { const float ev = sycl::exp(sr[j] - m); sr[j] = ev; s += ev; }
                const float inv = 1.0f / ops::wg_sum<ops::OPS_WG>(it, s, &slm[0]);
                for (int j = l; j < np; j += ops::OPS_WG) sr[j] = sr[j] * inv;
            });
        }));
    }

    // A[i0 + i][hh * 64 + c] = sum_j P[i][j] v_j[c], j ascending (V3.6)
    void pv(const float *v, int hh, int i0, int nq, int np) {
        const float *S_ = S;
        float *A_ = A;
        const size_t gi = (size_t)(nq + TILE - 1) / TILE * 16;
        e.pr("v_pv", d.q.submit([&](sycl::handler &h) {
            sycl::local_accessor<float, 2> ps(sycl::range<2>(TILE, TILE + 1), h), vs(sycl::range<2>(TILE, HD + 1), h);
            h.parallel_for(sycl::nd_range<2>(sycl::range<2>(gi, 16), sycl::range<2>(16, 16)), [=](sycl::nd_item<2> it) {
                const int ti = (int)it.get_local_id(0), tj = (int)it.get_local_id(1);
                const int bi = (int)it.get_group(0) * TILE;
                const int t = ti * 16 + tj;
                float acc[4][4] = {};
                for (int j0 = 0; j0 < np; j0 += TILE) {
                    for (int e2 = t; e2 < TILE * TILE; e2 += 256) {
                        const int r = e2 / TILE, c = e2 % TILE;
                        ps[r][c] = (bi + r < nq && j0 + c < np) ? S_[(size_t)(bi + r) * np + j0 + c] : 0.0f;
                        vs[r][c] = j0 + r < np ? v[(size_t)(j0 + r) * C + hh * HD + c] : 0.0f;
                    }
                    sycl::group_barrier(it.get_group());
                    const int jn = sycl::min(TILE, np - j0);
                    for (int jj = 0; jj < jn; ++jj) {
                        float a[4], b[4];
#pragma unroll
                        for (int u = 0; u < 4; ++u) { a[u] = ps[ti + 16 * u][jj]; b[u] = vs[jj][tj + 16 * u]; }
#pragma unroll
                        for (int u = 0; u < 4; ++u)
#pragma unroll
                            for (int w = 0; w < 4; ++w) acc[u][w] = mac(acc[u][w], a[u], b[w]);
                    }
                    sycl::group_barrier(it.get_group());
                }
#pragma unroll
                for (int u = 0; u < 4; ++u)
#pragma unroll
                    for (int w = 0; w < 4; ++w) {
                        const int i = bi + ti + 16 * u;
                        if (i < nq) A_[(size_t)(i0 + i) * C + hh * HD + tj + 16 * w] = acc[u][w];
                    }
            });
        }));
    }

    // attention of all rows and heads in one launch (V3.6, bidirectional, scale 0.125): a work-group per (64 query rows,
    // head), key tiles of KT in order, a running row max (the scores of a tile, then each row's new max and the factor
    // for the sums so far, then exp, then the row sums and P.V); fixed orders throughout, so the same values every run
    void attention(const float *q, const float *k, const float *v, int np) {
        constexpr int QT = 64, KT = 32;
        float *A_ = A;
        const int nblk = (np + QT - 1) / QT;
        e.pr("v_attn", d.q.submit([&](sycl::handler &h) {
            sycl::local_accessor<float, 2> qs(sycl::range<2>(QT, HD + 1), h), ks(sycl::range<2>(KT, HD + 1), h),
                vs(sycl::range<2>(KT, HD + 1), h), ps(sycl::range<2>(QT, KT + 1), h);
            sycl::local_accessor<float, 1> mrow(QT, h), lrow(QT, h), alpha(QT, h);
            h.parallel_for(sycl::nd_range<2>(sycl::range<2>((size_t)nblk * NH * 16, 16), sycl::range<2>(16, 16)),
                           [=](sycl::nd_item<2> it) [[sycl::reqd_sub_group_size(SG)]] {
                const int ti = (int)it.get_local_id(0), tj = (int)it.get_local_id(1), t = ti * 16 + tj;
                const int g = (int)it.get_group(0), blk = g / NH, hh = g % NH, i0 = blk * QT;
                for (int e2 = t; e2 < QT * HD; e2 += 256) {
                    const int r = e2 / HD, c = e2 % HD;
                    qs[r][c] = i0 + r < np ? q[(size_t)(i0 + r) * C + hh * HD + c] : 0.0f;
                }
                if (t < QT) { mrow[t] = -INFINITY; lrow[t] = 0.0f; }
                float o[4][4] = {};
                for (int k0 = 0; k0 < np; k0 += KT) {
                    for (int e2 = t; e2 < KT * HD; e2 += 256) {
                        const int r = e2 / HD, c = e2 % HD;
                        const bool in = k0 + r < np;
                        ks[r][c] = in ? k[(size_t)(k0 + r) * C + hh * HD + c] : 0.0f;
                        vs[r][c] = in ? v[(size_t)(k0 + r) * C + hh * HD + c] : 0.0f;
                    }
                    sycl::group_barrier(it.get_group());
                    { // scores: rows ti + 16u, keys tj + 16w
                        float sc[4][2] = {};
                        for (int c = 0; c < HD; ++c) {
                            float a[4], b[2];
#pragma unroll
                            for (int u = 0; u < 4; ++u) a[u] = qs[ti + 16 * u][c];
#pragma unroll
                            for (int w = 0; w < 2; ++w) b[w] = ks[tj + 16 * w][c];
#pragma unroll
                            for (int u = 0; u < 4; ++u)
#pragma unroll
                                for (int w = 0; w < 2; ++w) sc[u][w] = mac(sc[u][w], a[u], b[w]);
                        }
#pragma unroll
                        for (int u = 0; u < 4; ++u)
#pragma unroll
                            for (int w = 0; w < 2; ++w)
                                ps[ti + 16 * u][tj + 16 * w] = k0 + tj + 16 * w < np ? sc[u][w] * 0.125f : -INFINITY;
                    }
                    sycl::group_barrier(it.get_group());
                    if (t < QT) { // the row's new max and the factor for what it has summed so far
                        float mx = mrow[t];
                        for (int j = 0; j < KT; ++j) mx = sycl::fmax(mx, ps[t][j]);
                        alpha[t] = sycl::exp(mrow[t] - mx);
                        mrow[t] = mx;
                    }
                    sycl::group_barrier(it.get_group());
#pragma unroll
                    for (int u = 0; u < 4; ++u)
#pragma unroll
                        for (int w = 0; w < 2; ++w) {
                            const int r = ti + 16 * u, j = tj + 16 * w;
                            ps[r][j] = sycl::exp(ps[r][j] - mrow[r]);
                        }
                    sycl::group_barrier(it.get_group());
                    if (t < QT) {
                        float s = 0.0f;
                        for (int j = 0; j < KT; ++j) s += ps[t][j];
                        lrow[t] = lrow[t] * alpha[t] + s;
                    }
#pragma unroll
                    for (int u = 0; u < 4; ++u) {
                        const int r = ti + 16 * u;
                        const float al = alpha[r];
#pragma unroll
                        for (int w = 0; w < 4; ++w) o[u][w] = o[u][w] * al;
                        for (int jj = 0; jj < KT; ++jj) {
                            const float p = ps[r][jj];
#pragma unroll
                            for (int w = 0; w < 4; ++w) o[u][w] = mac(o[u][w], p, vs[jj][tj + 16 * w]);
                        }
                    }
                    sycl::group_barrier(it.get_group());
                }
#pragma unroll
                for (int u = 0; u < 4; ++u) {
                    const int r = ti + 16 * u;
                    if (i0 + r < np) {
                        const float inv = 1.0f / lrow[r];
#pragma unroll
                        for (int w = 0; w < 4; ++w) A_[(size_t)(i0 + r) * C + hh * HD + tj + 16 * w] = o[u][w] * inv;
                    }
                }
            });
        }));
    }

    // attention as register tiles (the layout of attn_flash.hpp): a work-group = NSG sub-groups of NR query rows each,
    // one head, key blocks of 32 (two groups of 16) staged in local memory. Per block and row: the scores with lane =
    // key (mac over c ascending of q[c], a register region, and k[c]; then x 0.125; keys past np: -inf), the block's
    // maximum (sub-group maximum), Mn = fmax(M, m), al = exp(M - Mn), p = exp(s - Mn), l = p(group 0) + p(group 1)
    // then + xor-shuffles 8, 4, 2, 1, L = L * al + l; P.V with lane = channel: o = o * al, then mac over the block's
    // keys ascending of p and v. out = o * (1 / L). Fixed orders: the same bits every run.
    void attention_rt(const float *q, const float *k, const float *v, int np) {
        constexpr int NR = 16, NSG = 8, KB = 32, QT = NR * NSG;
        float *A_ = A;
        const int nblk = (np + QT - 1) / QT;
        e.pr("v_attn", d.q.submit([&](sycl::handler &h) {
            sycl::local_accessor<float, 2> ks(sycl::range<2>(KB, HD + 1), h), vs(sycl::range<2>(KB, HD), h);
            auto body = [=](sycl::nd_item<2> it) {
                auto sg = it.get_sub_group();
                const int sgi = (int)it.get_local_id(0), lane = (int)it.get_local_id(1), t = sgi * 16 + lane;
                const int g = (int)it.get_group(0), hh = g % NH, r0 = (g / NH) * QT + sgi * NR;
                float ql[NR][4], o[NR][4], M[NR], L[NR];
#pragma unroll
                for (int a = 0; a < NR; ++a) {
#pragma unroll
                    for (int m = 0; m < 4; ++m) {
                        ql[a][m] = r0 + a < np ? q[(size_t)(r0 + a) * C + hh * HD + lane + 16 * m] : 0.0f;
                        o[a][m] = 0.0f;
                    }
                    M[a] = -INFINITY;
                    L[a] = 0.0f;
                }
                for (int k0 = 0; k0 < np; k0 += KB) {
                    for (int e2 = t; e2 < KB * HD; e2 += NSG * 16) {
                        const int rr = e2 / HD, c = e2 % HD;
                        const bool in = k0 + rr < np;
                        ks[rr][c] = in ? k[(size_t)(k0 + rr) * C + hh * HD + c] : 0.0f;
                        vs[rr][c] = in ? v[(size_t)(k0 + rr) * C + hh * HD + c] : 0.0f;
                    }
                    sycl::group_barrier(it.get_group());
                    float sc[2][NR];
#pragma unroll
                    for (int gq = 0; gq < 2; ++gq) {
#pragma unroll
                        for (int a = 0; a < NR; ++a) sc[gq][a] = 0.0f;
#pragma unroll
                        for (int c = 0; c < HD; ++c) {
                            const float kf = ks[16 * gq + lane][c];
#pragma unroll
                            for (int a = 0; a < NR; ++a) sc[gq][a] = mac(sc[gq][a], sycl::select_from_group(sg, ql[a][c / 16], c % 16), kf);
                        }
                        const bool in = k0 + 16 * gq + lane < np;
#pragma unroll
                        for (int a = 0; a < NR; ++a) sc[gq][a] = in ? sc[gq][a] * 0.125f : -INFINITY;
                    }
#pragma unroll
                    for (int a = 0; a < NR; ++a) {
                        const float mb = sycl::reduce_over_group(sg, sycl::fmax(sc[0][a], sc[1][a]), sycl::maximum<float>());
                        const float mn = sycl::fmax(M[a], mb), al = sycl::exp(M[a] - mn);
                        M[a] = mn;
                        sc[0][a] = sycl::exp(sc[0][a] - mn);
                        sc[1][a] = sycl::exp(sc[1][a] - mn);
                        float ls = sc[0][a] + sc[1][a];
                        ls = ls + sycl::permute_group_by_xor(sg, ls, 8);
                        ls = ls + sycl::permute_group_by_xor(sg, ls, 4);
                        ls = ls + sycl::permute_group_by_xor(sg, ls, 2);
                        ls = ls + sycl::permute_group_by_xor(sg, ls, 1);
                        L[a] = L[a] * al + ls;
#pragma unroll
                        for (int m = 0; m < 4; ++m) o[a][m] = o[a][m] * al;
                    }
#pragma unroll
                    for (int gq = 0; gq < 2; ++gq)
#pragma unroll
                        for (int u = 0; u < 16; ++u) {
                            float vf[4];
#pragma unroll
                            for (int m = 0; m < 4; ++m) vf[m] = vs[16 * gq + u][lane + 16 * m];
#pragma unroll
                            for (int a = 0; a < NR; ++a) {
                                const float pb = sycl::select_from_group(sg, sc[gq][a], u);
#pragma unroll
                                for (int m = 0; m < 4; ++m) o[a][m] = mac(o[a][m], pb, vf[m]);
                            }
                        }
                    sycl::group_barrier(it.get_group());
                }
#pragma unroll
                for (int a = 0; a < NR; ++a)
                    if (r0 + a < np) {
                        const float inv = 1.0f / L[a];
#pragma unroll
                        for (int m = 0; m < 4; ++m) A_[(size_t)(r0 + a) * C + hh * HD + lane + 16 * m] = o[a][m] * inv;
                    }
            };
            h.parallel_for(sycl::nd_range<2>(sycl::range<2>((size_t)nblk * NH * NSG, 16), sycl::range<2>(NSG, 16)),
                           fz::FlashK<decltype(body), true>{body});
        }));
    }

    // rows (M x 2304) for an RGB picture (w x h, 8 bits per channel, rows top first); throws when it gives more rows
    // than the buffers hold
    std::vector<float> encode(const uint8_t *rgb, int w, int h, int &M) {
        if (!ok) throw std::runtime_error("vision: the image encoder is not loaded");
        if (w < 1 || h < 1) throw std::runtime_error("vision: empty picture");
        const int nx = align40(w), ny = align40(h), wp = nx / PS, hp = ny / PS, P = wp * hp, np = P + 1;
        M = (wp / 2) * (hp / 2);
        if (M > max_rows || std::max(wp, hp) > max_side)
            throw std::runtime_error("vision: the picture gives " + std::to_string(M) + " rows, more than " + std::to_string(max_rows));
        const double t0 = now_s();
        // V2.3-2.4: pad right / bottom with -1, (v - 127.5) / 127.5, planar, then F16 as the reference's im2col (V3.1)
        std::vector<float> pix((size_t)3 * nx * ny);
        const float padv = (float)(sycl::half)((-1.0f - 127.5f) / 127.5f);
        for (int c = 0; c < 3; ++c)
            for (int y = 0; y < ny; ++y)
                for (int x = 0; x < nx; ++x) {
                    float v = padv;
                    if (x < w && y < h) v = (float)(sycl::half)(((float)rgb[((size_t)y * w + x) * 3 + c] - 127.5f) / 127.5f);
                    pix[((size_t)c * ny + y) * nx + x] = v;
                }
        float *pixd = QKV; // (free until the first block)
        d.q.memcpy(pixd, pix.data(), sizeof(float) * pix.size());
        // V3.5: cos / sin tables, theta multiplied by 10000^(-2/32) per pair (float, as the reference iterates it)
        {
            const int npos = std::max(wp, hp) + 1;
            std::vector<float> co((size_t)npos * 16), si((size_t)npos * 16);
            const float sf = ::powf(10000.0f, -2.0f / 32.0f);
            for (int p = 0; p < npos; ++p) {
                float th = (float)p;
                for (int j = 0; j < 16; ++j) { co[p * 16 + j] = ::cosf(th); si[p * 16 + j] = ::sinf(th); th = th * sf; }
            }
            d.q.memcpy(rc, co.data(), sizeof(float) * co.size());
            d.q.memcpy(rs, si.data(), sizeof(float) * si.size());
            d.q.wait();
        }
        // V3.1-3.3: patch embedding + resized position table into rows 1..P, the CLS row 0
        {
            const float *wpe = f32(patch), *pe0 = f32(pos), *cl = f32(cls), *cp = f32(clsp);
            float *X_ = X;
            const int nx_ = nx, ny_ = ny;
            e.pr("v_patch", d.q.submit([&](sycl::handler &hd) {
                sycl::local_accessor<float, 1> col(KP, hd);
                hd.parallel_for(sycl::nd_range<1>(sycl::range<1>((size_t)P * C), sycl::range<1>(256)), [=](sycl::nd_item<1> it) {
                    const int p = (int)(it.get_group(0) / (C / 256)), o = (int)(it.get_group(0) % (C / 256)) * 256 + (int)it.get_local_id(0);
                    const int px = p % wp, py = p / wp, l = (int)it.get_local_id(0);
                    for (int k = l; k < KP; k += 256) {
                        const int c = k / (PS * PS), ky = (k / PS) % PS, kx = k % PS;
                        col[k] = pixd[((size_t)c * ny_ + PS * py + ky) * nx_ + PS * px + kx];
                    }
                    sycl::group_barrier(it.get_group());
                    const float *wr = wpe + (size_t)o * KP;
                    float acc = 0.0f;
                    for (int k = 0; k < KP; ++k) acc = mac(acc, col[k], wr[k]);
                    float pe;
                    if (wp == GRID && hp == GRID) pe = pe0[(size_t)(py * GRID + px) * C + o];
                    else { // V3.2: half-pixel bilinear, edge clamp, no antialias
                        const float fx = (float)wp / (float)GRID, fy = (float)hp / (float)GRID;
                        const float yy = ((float)py + 0.5f) / fy - 0.5f, xx = ((float)px + 0.5f) / fx - 0.5f;
                        int y0 = (int)sycl::floor(yy), x0 = (int)sycl::floor(xx);
                        int y1 = y0 + 1, x1 = x0 + 1;
                        y0 = sycl::clamp(y0, 0, GRID - 1); y1 = sycl::clamp(y1, 0, GRID - 1);
                        x0 = sycl::clamp(x0, 0, GRID - 1); x1 = sycl::clamp(x1, 0, GRID - 1);
                        const float dy = sycl::clamp(yy - (float)y0, 0.0f, 1.0f), dx = sycl::clamp(xx - (float)x0, 0.0f, 1.0f);
                        const float a = pe0[(size_t)(y0 * GRID + x0) * C + o], b = pe0[(size_t)(y0 * GRID + x1) * C + o];
                        const float c2 = pe0[(size_t)(y1 * GRID + x0) * C + o], d2 = pe0[(size_t)(y1 * GRID + x1) * C + o];
                        pe = a * (1.0f - dx) * (1.0f - dy) + b * dx * (1.0f - dy) + c2 * (1.0f - dx) * dy + d2 * dx * dy;
                    }
                    X_[(size_t)(1 + p) * C + o] = acc + pe;
                    if (p == 0 && o < C) X_[o] = cl[o] + cp[o];
                });
            }));
        }
        layer_norm(X, X, prew, preb, np);
        float *Q = QKV, *K = QKV + (size_t)max_np * C, *V = QKV + (size_t)2 * max_np * C;
        for (int l = 0; l < NL; ++l) {
            const Blk &b = B[l];
            layer_norm(X, H, b.ln1w, b.ln1b, np);
            mm(b.q, H, Q, np); add_bias(Q, b.qb, C, np);
            mm(b.k, H, K, np); add_bias(K, b.kb, C, np);
            mm(b.v, H, V, np); add_bias(V, b.vb, C, np);
            rope(Q, np, wp);
            rope(K, np, wp);
            if (attn_split) // (the first version: scores, softmax and P.V in separate launches, INK_VISION_ATTN=split)
                for (int hh = 0; hh < NH; ++hh)
                    for (int i0 = 0; i0 < np; i0 += qb) {
                        const int nq = std::min(qb, np - i0);
                        scores(Q, K, hh, i0, nq, np);
                        softmax(nq, np);
                        pv(V, hh, i0, nq, np);
                    }
            else if (attn_v1) attention(Q, K, V, np); // (INK_VISION_ATTN=fused1: one launch, all threads on 64 x 32 tiles)
            else attention_rt(Q, K, V, np);
            mm(b.o, A, H, np);
            residual(X, H, b.ob, b.ls1, np);
            layer_norm(X, H, b.ln2w, b.ln2b, np);
            for (int r0 = 0; r0 < np; r0 += rb) {
                const int nr = std::min(rb, np - r0);
                mm(b.up, H + (size_t)r0 * C, F, nr);
                gelu(F, f32(b.upb), FF, nr);
                mm(b.down, F, A + (size_t)r0 * C, nr);
                residual(X + (size_t)r0 * C, A + (size_t)r0 * C, b.downb, b.ls2, nr);
            }
        }
        // V3.7: drop the CLS row, 2 x 2 merge (top-left, top-right, bottom-left, bottom-right), projector
        float *Z = QKV, *Z2 = QKV + (size_t)M * 4 * C, *Y = QKV + (size_t)2 * M * 4 * C;
        {
            const float *X_ = X;
            const int mw = wp / 2;
            e.pr("v_merge", d.q.parallel_for(sycl::range<2>((size_t)M, (size_t)4 * C), [=](sycl::id<2> id) {
                const int r = (int)id[0], j = (int)id[1], c = j % C, q4 = j / C, dx = q4 % 2, dy = q4 / 2;
                const int xb = r % mw, yb = r / mw;
                Z[(size_t)r * 4 * C + j] = X_[(size_t)(1 + (2 * yb + dy) * wp + 2 * xb + dx) * C + c];
            }));
        }
        mm(mm1, Z, Z2, M);
        gelu(Z2, nullptr, 4 * C, M);
        mm(mm2, Z2, Y, M);
        std::vector<float> out((size_t)M * OUT);
        d.q.memcpy(out.data(), Y, sizeof(float) * out.size()).wait();
        last_s = now_s() - t0;
        return out;
    }
};

} // namespace ink
