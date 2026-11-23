// DSpark drafter for Inkling-2 (Unsloth's dspark-Inkling-2-Mini-Q8_0.gguf) on the target's card: guesses the next
// tokens for Engine::check. Its numbers only decide how many guesses the target keeps, never the text (every guess
// is checked against the target's own choice). Graph from the reference source, with file:line references:
// /home/steve/inkling-work/notes/dspark-spec.md.
//   target taps (Engine::feat): the stream entering visits 5, 23, 41 (before the depth mix) and the final normed row
//   inject(pos0, n): per processed row p: c_l = RMSNorm(sum_j A[l][j] f_j) * dflare_norm[l] (l < 3), context K/V of
//     drafter layer l at p (K: per-head RMSNorm * k_ctx_norm, NeoX RoPE theta 1e6), r(p) = the 4th mixture's norm
//   draft(P0, t0, n): block [t0, mask x 7] at P0..P0+7 through 3 layers (non-causal; layers 0 and 2 see the 1024
//     positions before P0, layer 1 all of them, all see the 8 block keys), then the chained head per guess:
//     u = Wj [s; w1[prev]; y_i; r(P0-1)] + bj, s = g s + (1-g) tanh(u1), z = tanh(u2), guess = argmax over the
//     real tokens of 30 tanh(W_lm (y_i + Wh z + bh) / 30)
#pragma once
#include "engine.hpp"

namespace ink {

struct Drafter {
    static constexpr int B = 8, NL = 3, R = 256, HQ = 24, HKV = 8, HD = 128, WIN = 1024, AWG = 256;
    Engine &e;
    Device &d;
    GGUF g;
    Weights w;
    std::map<std::string, WView> views;
    struct DL { W attn_norm, wq, wk, wv, q_norm, k_norm, wo, k_ctx, v_ctx, k_ctx_norm, dflare_norm, ffn_norm, gate, up, down; };
    DL L[NL];
    W dnorm, mask, onorm, w1, jp, jpb, ho, hob;
    float A[16];  // softmax of each dspark_fuse row (row l < 3: drafter layer l's context, row 3: the head context)
    int E, Vp, V, cap, T, kd;
    float eps, theta;
    sycl::half *Kc[NL] = {}, *Vc[NL] = {};
    int kmask[NL];
    float *cb = nullptr, *kc = nullptr, *vc = nullptr, *rrows = nullptr;
    float *x, *hh, *q, *k, *v, *att, *ao, *gt, *upb, *y, *sc, *cat, *uu, *s, *z, *eh, *hs, *lgd;
    float *Xt = nullptr;    // the tile kernels' gathered inputs (one tile of 16 slots, up to the widest input)
    float *base = nullptr;  // W_lm y_i of the guess slots [B - 1][Vp]
    float *cvec = nullptr;  // W_lm bh [Vp]
    sycl::ext::oneapi::bfloat16 *Pt = nullptr; // (W_lm Wh)^T [R][Vp]: the correction of latent z is sum_j z_j Pt[j]
    int32_t *gids;
    float *yl = nullptr, *amv = nullptr, *ams = nullptr, *gp = nullptr; int32_t *ami = nullptr; // argmax scratch; guess probabilities
    std::vector<float> probs; // the last draft's guess probabilities (the drafter's own softmax)
    // split attention (INK_DSP_SPLIT=0: one work-group per query row): work-groups of (key head, key span) for all
    // 24 rows of a key head, partial softmax sums combined by a second launch
    bool split = true;
    static constexpr int NR = B * (HQ / HKV), CH = 128, NCH = 64; // rows per key head; keys per pass; spans per head
    float *pO = nullptr, *pM = nullptr, *pL = nullptr;
    float *hl = nullptr, *attl = nullptr, *gl = nullptr; // the 8 slots' product inputs in lane order (xlane.hpp)
    bool fold = true;       // INK_DSP_FOLD=0: each guess passes y_i + Wh z + bh through W_lm (the reference's way)
    int r_last = -1; // the row of rrows that holds r(P0 - 1)
    size_t sc_keys;  // score scratch per (slot, head)

    static W wof(const WView &v) { W r; r.t = v.t; r.p = v.p; r.rb = v.rb; r.kind = v.kind; return r; }
    W get(const std::string &n) const {
        auto it = views.find(n);
        if (it == views.end()) throw std::runtime_error("dspark: missing tensor " + n);
        return wof(it->second);
    }
    const float *f32(const W &t) const { return e.f32(t); }

    Drafter(Engine &eng, const std::string &path) : e(eng), d(eng.d), g(path) {
        if (g.s("general.architecture") != "dflash") throw std::runtime_error("dspark: not a dflash file");
        const HParams &h = e.m.hp;
        E = h.n_embd; Vp = h.vocab_padded; V = h.vocab; cap = e.cap; T = e.T; kd = HKV * HD;
        if (E > 2304) throw std::runtime_error("dspark: the mixture kernel holds 2304 values per row");
        if (g.i("dflash.embedding_length") != E || g.i("dflash.block_count") != NL || g.i("dflash.block_size") != B ||
            g.i("dflash.attention.head_count") != HQ || g.i("dflash.attention.head_count_kv") != HKV ||
            g.i("dflash.dspark.markov_rank") != R || g.i("dflash.attention.sliding_window") != WIN)
            throw std::runtime_error("dspark: unexpected shape");
        eps = (float)g.f("dflash.attention.layer_norm_rms_epsilon");
        theta = (float)g.f("dflash.rope.freq_base");
        const auto &tl = g.arr<std::vector<int64_t>>("dflash.target_layers");
        if (tl.size() != 4 || tl[3] != h.n_app) throw std::runtime_error("dspark: target layers");
        for (int j = 0; j < 3; ++j) e.feat_vis[j] = (int)tl[j];
        w.upload(d, g, false);
        views = planarize(d, g, w, false);
        for (int l = 0; l < NL; ++l) {
            const std::string p = "blk." + std::to_string(l) + ".";
            DL &a = L[l];
            a.attn_norm = get(p + "attn_norm.weight"); a.wq = get(p + "attn_q.weight"); a.wk = get(p + "attn_k.weight");
            a.wv = get(p + "attn_v.weight"); a.q_norm = get(p + "attn_q_norm.weight"); a.k_norm = get(p + "attn_k_norm.weight");
            a.wo = get(p + "attn_output.weight"); a.k_ctx = get(p + "attn_k_ctx.weight"); a.v_ctx = get(p + "attn_v_ctx.weight");
            a.k_ctx_norm = get(p + "attn_k_ctx_norm.weight"); a.dflare_norm = get(p + "dflare_norm.weight");
            a.ffn_norm = get(p + "ffn_norm.weight"); a.gate = get(p + "ffn_gate.weight"); a.up = get(p + "ffn_up.weight");
            a.down = get(p + "ffn_down.weight");
        }
        dnorm = get("dspark_norm.weight"); mask = get("mask_embd.weight"); onorm = get("output_norm.weight");
        w1 = get("markov_w1.weight"); jp = get("joint_proj.weight"); jpb = get("joint_proj.bias");
        ho = get("dspark_hidden_out.weight"); hob = get("dspark_hidden_out.bias");
        { // the mixtures' softmax (fixed weights)
            const W fw = get("dspark_fuse.weight");
            float raw[16];
            d.get(raw, (const float *)fw.p, 16);
            for (int r = 0; r < 4; ++r) {
                float m = raw[4 * r];
                for (int j = 1; j < 4; ++j) m = std::max(m, raw[4 * r + j]);
                float sum = 0.0f;
                for (int j = 0; j < 4; ++j) sum += std::exp(raw[4 * r + j] - m);
                for (int j = 0; j < 4; ++j) A[4 * r + j] = std::exp(raw[4 * r + j] - m) / sum;
            }
        }
        // context caches: layer 1 every position, layers 0 and 2 a ring (a window plus a step and more)
        const char *pat = "dflash.attention.sliding_window_pattern";
        const auto &swp = g.arr<std::vector<int64_t>>(pat);
        for (int l = 0; l < NL; ++l) {
            const bool win = swp.at(l) != 0;
            int ring = 1; // a power of two holding the window, a step and a block
            while (ring < WIN + T + B) ring *= 2;
            const int slots = win ? ring : cap;
            kmask[l] = win ? ring - 1 : 0x7fffffff;
            Kc[l] = d.alloc<sycl::half>((size_t)slots * kd);
            Vc[l] = d.alloc<sycl::half>((size_t)slots * kd);
        }
        e.feat = d.alloc<float>((size_t)4 * T * E);
        cb = d.alloc<float>((size_t)3 * T * E);
        kc = d.alloc<float>((size_t)T * kd); vc = d.alloc<float>((size_t)T * kd);
        rrows = d.alloc<float>((size_t)T * E);
        x = d.alloc<float>((size_t)B * E); hh = d.alloc<float>((size_t)B * E); y = d.alloc<float>((size_t)B * E);
        q = d.alloc<float>((size_t)B * HQ * HD); k = d.alloc<float>((size_t)B * kd); v = d.alloc<float>((size_t)B * kd);
        att = d.alloc<float>((size_t)B * HQ * HD); ao = d.alloc<float>((size_t)B * E);
        const int F = (int)L[0].gate.t->rows();
        gt = d.alloc<float>((size_t)B * F); upb = d.alloc<float>((size_t)B * F);
        sc_keys = (size_t)cap + B;
        sc = d.alloc<float>((size_t)B * HQ * sc_keys);
        cat = d.alloc<float>((size_t)2 * R + 2 * E); uu = d.alloc<float>(3 * R); s = d.alloc<float>(R); z = d.alloc<float>(R);
        eh = d.alloc<float>(E); hs = d.alloc<float>(E); lgd = d.alloc<float>(Vp);
        gids = d.alloc<int32_t>(B);
        int widest = 0;
        for (int l = 0; l < NL; ++l) for (const W *t : {&L[l].wq, &L[l].wo, &L[l].gate, &L[l].down}) widest = std::max(widest, (int)t->t->ne[0]);
        Xt = d.alloc<float>((size_t)widest * MOE_TS);
        base = d.alloc<float>((size_t)(B - 1) * Vp);
        yl = d.alloc<float>((size_t)B * xlane_floats(E));
        hl = d.alloc<float>((size_t)B * xlane_floats(E));
        attl = d.alloc<float>((size_t)B * xlane_floats(HQ * HD));
        gl = d.alloc<float>((size_t)B * xlane_floats((int)L[0].gate.t->rows()));
        amv = d.alloc<float>(ops::ARGMAX_G); ami = d.alloc<int32_t>(ops::ARGMAX_G); ams = d.alloc<float>(ops::ARGMAX_G);
        gp = d.alloc<float>(B);
        if (const char *ev = std::getenv("INK_DSP_FOLD")) fold = std::atoi(ev) != 0;
        if (const char *ev = std::getenv("INK_DSP_SPLIT")) split = std::atoi(ev) != 0;
        pO = d.alloc<float>((size_t)HKV * NR * (NCH + 1) * HD);
        pM = d.alloc<float>((size_t)HKV * NR * (NCH + 1)); pL = d.alloc<float>((size_t)HKV * NR * (NCH + 1));
        if (fold) make_fold();
        e.on_step = [this](int pos0, int n) { inject(pos0, n); };
    }

    // the head's correction through W_lm, folded: W_lm (y + Wh z + bh) = W_lm y + (W_lm Wh) z + W_lm bh. (W_lm Wh)^T is
    // W_lm applied to Wh's 256 columns (the engine's own products, 256 vectors), kept as BF16
    void make_fold() {
        const double t0 = now_s();
        const int E_ = E;
        float *cols = d.alloc<float>((size_t)R * E), *Y = d.alloc<float>((size_t)R * Vp);
        const sycl::ext::oneapi::bfloat16 *wh = (const sycl::ext::oneapi::bfloat16 *)ho.p; // [E rows][R]
        d.q.parallel_for(sycl::range<2>(R, (size_t)E), [=](sycl::id<2> id) {
            cols[(size_t)id[0] * E_ + id[1]] = (float)wh[(size_t)id[1] * R + id[0]];
        }).wait();
        for (int j0 = 0; j0 < R; j0 += e.T) e.mm(e.m.output, cols + (size_t)j0 * E, Y + (size_t)j0 * Vp, std::min(e.T, R - j0));
        Pt = d.alloc<sycl::ext::oneapi::bfloat16>((size_t)R * Vp);
        auto *pt = Pt;
        d.q.parallel_for(sycl::range<1>((size_t)R * Vp), [=](sycl::id<1> i) { pt[i] = sycl::ext::oneapi::bfloat16(Y[i]); }).wait();
        cvec = d.alloc<float>(Vp);
        e.mm(e.m.output, f32(hob), cvec, 1);
        d.q.wait();
        d.release(Y); d.release(cols);
        e.prof.rows.clear(); e.prof.busy_ms = e.prof.span_ms = 0; e.prof.steps = 0;
        std::fprintf(stderr, "[dspark] folded head table (%.0f MB) in %.2f s\n", (double)R * Vp * 2 / 1e6, now_s() - t0);
    }

    // y[t] = W x[t] for the 8 slots, x in lane order (rows xlane_floats(cols) apart): blocks of 8 vectors per sub-group
    // (bench_gemv card 3, 8 vectors: ffn_gate 75 us, ffn_down 88; the tile kernels 123 and 225)
    void lmm(const W &wt, const float *xin, float *yout, const char *label) {
        const int cols = (int)wt.t->ne[0], rows = (int)wt.t->rows();
        e.pr(label, gemv_v(d.q, wt.view(), xin, (int)xlane_floats(cols), yout, rows, B, Tune{1, 1, false, 8, false}, true));
    }
    // y[t] = W x[t] for the n <= 16 slots through the token-parallel tile kernels (one weight read for all slots)
    void tmm(const W &wt, const float *xin, float *yout, int n, const char *label) {
        const int cols = (int)wt.t->ne[0], rows = (int)wt.t->rows();
        e.pr("dsp_gather", dense_gather(d.q, xin, cols, n, cols, Xt));
        e.pr(label, dense_t(d.q, wt.view(), n, Xt, yout, rows, DTune{1, 1}));
    }

    // RMSNorm over 128 values per head (weight wn), then NeoX RoPE at position pos (pairs j, j + 64)
    static inline void head_norm_rope(sycl::nd_item<1> it, float xv, const float *wn, int pos, float theta, float eps, float *slm,
                                      float &out) {
        const int dd = (int)it.get_local_id(0);
        const float ss = ops::wg_sum<HD>(it, xv * xv, slm);
        const float xn = xv * (1.0f / sycl::sqrt(ss / HD + eps)) * wn[dd];
        slm[HD / SG + dd] = xn;
        sycl::group_barrier(it.get_group());
        const int j = dd & (HD / 2 - 1);
        const float fr = sycl::pow(theta, -2.0f * (float)j / (float)HD) * (float)pos;
        const float c = sycl::cos(fr), sn = sycl::sin(fr);
        const float a = slm[HD / SG + j], b = slm[HD / SG + j + HD / 2];
        out = dd < HD / 2 ? a * c - b * sn : a * sn + b * c;
    }

    // after every target step: the rows' context K/V (3 layers) and head-context rows r(p)
    void inject(int pos0, int n) {
        const float *feat = e.feat;
        const int E_ = E, T_ = T;
        float Am[16];
        std::memcpy(Am, A, sizeof(Am));
        struct NW { const float *p[4]; } nw{{f32(L[0].dflare_norm), f32(L[1].dflare_norm), f32(L[2].dflare_norm), f32(dnorm)}};
        float *cb_ = cb, *rr = rrows;
        const float ep = eps;
        e.pr("dsp_mix", d.q.submit([&](sycl::handler &hd) {
            sycl::local_accessor<float, 1> slm(ops::OPS_WG / SG, hd);
            hd.parallel_for(ops::rows_range(4 * n), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(SG)]] {
                const int gi = (int)it.get_group(0), l = gi / n, t = gi % n, li = (int)it.get_local_id(0);
                float mv[(2304 + ops::OPS_WG - 1) / ops::OPS_WG];
                float ss = 0.0f;
                int u = 0;
                for (int i = li; i < E_; i += ops::OPS_WG, ++u) {
                    float m = 0.0f;
                    for (int j = 0; j < 4; ++j) m += Am[4 * l + j] * feat[((size_t)j * T_ + t) * E_ + i];
                    mv[u] = m;
                    ss += m * m;
                }
                const float tot = ops::wg_sum<ops::OPS_WG>(it, ss, &slm[0]);
                const float scale = 1.0f / sycl::sqrt(tot / E_ + ep);
                float *out = l < 3 ? cb_ + ((size_t)l * T_ + t) * E_ : rr + (size_t)t * E_;
                u = 0;
                for (int i = li; i < E_; i += ops::OPS_WG, ++u) out[i] = mv[u] * scale * nw.p[l][i];
            });
        }));
        for (int l = 0; l < NL; ++l) {
            e.mm(L[l].k_ctx, cb + (size_t)l * T * E, kc, n);
            e.mm(L[l].v_ctx, cb + (size_t)l * T * E, vc, n);
            sycl::half *K = Kc[l], *Vv = Vc[l];
            const float *kn = f32(L[l].k_ctx_norm), *kc_ = kc, *vc_ = vc;
            const int km = kmask[l], kd_ = kd;
            const float th = theta;
            e.pr("dsp_ctx_kv", d.q.submit([&](sycl::handler &hd) {
                sycl::local_accessor<float, 1> slm(HD / SG + HD, hd);
                hd.parallel_for(sycl::nd_range<1>(sycl::range<1>((size_t)n * HKV * HD), sycl::range<1>(HD)),
                                [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(SG)]] {
                    const int gi = (int)it.get_group(0), t = gi / HKV, hh_ = gi % HKV, dd = (int)it.get_local_id(0);
                    const size_t i = (size_t)t * kd_ + hh_ * HD + dd;
                    float ko;
                    head_norm_rope(it, kc_[i], kn, pos0 + t, th, ep, &slm[0], ko);
                    const size_t o = (size_t)((pos0 + t) & km) * kd_ + hh_ * HD + dd;
                    K[o] = sycl::half(ko);
                    Vv[o] = sycl::half(vc_[i]);
                });
            }));
        }
        r_last = n - 1;
    }

    // n guesses (n <= B - 1) for positions P0 + 1.. after the token t0 (on the card) at P0; returns them
    std::vector<int32_t> draft(int P0, const int32_t *t0, int n) {
        if (n < 1 || n > B - 1) throw std::runtime_error("dspark: 1 to 7 guesses");
        if (r_last < 0) throw std::runtime_error("dspark: no context row (nothing injected)");
        if (P0 + B > cap) throw std::runtime_error("dspark: context full");
        const HParams &h = e.m.hp;
        const int E_ = E, F = (int)L[0].gate.t->rows();
        // slot 0: the target's normed embedding of t0; slots 1..7: the mask embedding
        e.pr("dsp_embd", ops::get_rows(d.q, *e.m.tok_embd.t, e.m.tok_embd.p, t0, x, 1));
        e.pr("dsp_embd", ops::rms_norm(d.q, x, x, e.f32(e.m.tok_norm), E, 1, h.eps));
        {
            float *x_ = x;
            const float *me = f32(mask);
            e.pr("dsp_mask", d.q.parallel_for(sycl::range<2>(B - 1, (size_t)E), [=](sycl::id<2> id) {
                x_[(size_t)(id[0] + 1) * E_ + id[1]] = me[id[1]];
            }));
        }
        for (int l = 0; l < NL; ++l) {
            const DL &a = L[l];
            e.pr("dsp_norm", ops::rms_norm(d.q, x, nullptr, f32(a.attn_norm), E, B, eps, -1, -1, hl));
            lmm(a.wq, hl, q, "dsp_q");
            lmm(a.wk, hl, k, "dsp_k");
            lmm(a.wv, hl, v, "dsp_v");
            { // q and k: per-head norm and RoPE at P0 + slot
                float *q_ = q, *k_ = k;
                const float *qn = f32(a.q_norm), *kn = f32(a.k_norm);
                const float th = theta, ep = eps;
                e.pr("dsp_qk", d.q.submit([&](sycl::handler &hd) {
                    sycl::local_accessor<float, 1> slm(HD / SG + HD, hd);
                    hd.parallel_for(sycl::nd_range<1>(sycl::range<1>((size_t)B * (HQ + HKV) * HD), sycl::range<1>(HD)),
                                    [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(SG)]] {
                        const int gi = (int)it.get_group(0), dd = (int)it.get_local_id(0);
                        const int t = gi / (HQ + HKV), hh_ = gi % (HQ + HKV);
                        const bool isq = hh_ < HQ;
                        float *p = isq ? q_ + ((size_t)t * HQ + hh_) * HD : k_ + ((size_t)t * HKV + (hh_ - HQ)) * HD;
                        const float xv = p[dd];
                        float o;
                        head_norm_rope(it, xv, isq ? qn : kn, P0 + t, th, ep, &slm[0], o);
                        sycl::group_barrier(it.get_group());
                        p[dd] = o;
                    });
                }));
            }
            attend(l, P0);
            lmm(a.wo, attl, ao, "dsp_o");
            add(x, ao, (size_t)B * E);
            e.pr("dsp_norm", ops::rms_norm(d.q, x, nullptr, f32(a.ffn_norm), E, B, eps, -1, -1, hl));
            lmm(a.gate, hl, gt, "dsp_gate_w");
            lmm(a.up, hl, upb, "dsp_up_w");
            {
                const float *g_ = gt, *u_ = upb;
                float *gl_ = gl;
                const size_t lf = xlane_floats(F);
                e.pr("dsp_silu", d.q.parallel_for(sycl::range<2>(B, (size_t)F), [=](sycl::id<2> id) {
                    const size_t i = id[0] * (size_t)F + id[1];
                    const float gv = g_[i];
                    gl_[id[0] * lf + xlane_at((int)id[1])] = gv / (1.0f + sycl::exp(-gv)) * u_[i];
                }));
            }
            lmm(a.down, gl, ao, "dsp_down_w");
            add(x, ao, (size_t)B * E);
        }
        e.pr("dsp_norm", ops::rms_norm(d.q, x, y, f32(onorm), E, B, eps, -1, -1, yl));
        // the chained head
        d.q.memset(s, 0, sizeof(float) * R);
        const float *ctx = rrows + (size_t)r_last * E;
        if (fold) { // W_lm y_i of slots 1..n, one read of W_lm (lane-order rows: multi_m, bench_gemv card 3 3 rows 777 us)
            const int lx = (int)xlane_floats(E);
            for (int i0 = 0; i0 < n; i0 += 4) { // up to 4 rows per read (gemv_multi_m)
                const int ni = std::min(4, n - i0);
                const float *xi = yl + (size_t)(1 + i0) * lx;
                float *bi = base + (size_t)i0 * Vp;
                if (ni == 1) e.pr("dsp_base", gemv_v(d.q, e.m.output.view(), xi, lx, bi, Vp, 1, Tune{1, 1}, true));
                else {
                    MultiJobs mj;
                    multi_add(mj, e.m.output.view(), xi, bi, 1, lx, Vp);
                    e.pr("dsp_base", gemv_multi_m(d.q, mj, ni, true, 1));
                }
            }
        }
        for (int i = 1; i <= n; ++i) {
            {
                float *c = cat;
                const float *s_ = s, *yi = y + (size_t)i * E, *cx = ctx;
                const sycl::ext::oneapi::bfloat16 *w1p = (const sycl::ext::oneapi::bfloat16 *)w1.p;
                const int32_t *prev = i == 1 ? t0 : gids + (i - 2);
                e.pr("dsp_cat", d.q.parallel_for(sycl::range<1>((size_t)2 * R + 2 * E_), [=](sycl::id<1> id) {
                    const int j = (int)id[0];
                    float vv;
                    if (j < R) vv = s_[j];
                    else if (j < 2 * R) vv = (float)w1p[(size_t)prev[0] * R + (j - R)];
                    else if (j < 2 * R + E_) vv = yi[j - 2 * R];
                    else vv = cx[j - 2 * R - E_];
                    c[j] = vv;
                }));
            }
            e.mm(jp, cat, uu, 1);
            {
                const float *u_ = uu, *bj = f32(jpb);
                float *s_ = s, *z_ = z;
                e.pr("dsp_gate", d.q.parallel_for(sycl::range<1>(R), [=](sycl::id<1> id) {
                    const int j = (int)id[0];
                    const float ga = 1.0f / (1.0f + sycl::exp(-(u_[j] + bj[j])));
                    const float cand = sycl::tanh(u_[R + j] + bj[R + j]);
                    z_[j] = sycl::tanh(u_[2 * R + j] + bj[2 * R + j]);
                    s_[j] = ga * s_[j] + (1.0f - ga) * cand;
                }));
            }
            if (fold) {
                const float *b_ = base + (size_t)(i - 1) * Vp, *c_ = cvec, *z_ = z;
                const sycl::ext::oneapi::bfloat16 *pt = Pt;
                float *lg_ = lgd;
                const int Vp_ = Vp;
                e.pr("dsp_corr", d.q.submit([&](sycl::handler &hd) {
                    sycl::local_accessor<float, 1> zs(R, hd);
                    hd.parallel_for(sycl::nd_range<1>(sycl::range<1>((size_t)(Vp + 255) / 256 * 256), sycl::range<1>(256)), [=](sycl::nd_item<1> it) {
                        const int li = (int)it.get_local_id(0);
                        zs[li] = z_[li];
                        sycl::group_barrier(it.get_group());
                        const int r = (int)it.get_global_id(0);
                        if (r >= Vp_) return;
                        float acc = 0.0f;
                        for (int j = 0; j < R; ++j) acc += zs[j] * (float)pt[(size_t)j * Vp_ + r];
                        lg_[r] = sycl::tanh((b_[r] + (acc + c_[r])) * (1.0f / 30.0f)) * 30.0f;
                    });
                }));
            } else {
                e.mm(ho, z, eh, 1);
                {
                    const float *yi = y + (size_t)i * E, *e_ = eh, *bh = f32(hob);
                    float *hs_ = hs;
                    e.pr("dsp_hsum", d.q.parallel_for(sycl::range<1>((size_t)E), [=](sycl::id<1> id) { hs_[id] = yi[id] + (e_[id] + bh[id]); }));
                }
                e.mm(e.m.output, hs, lgd, 1);
                e.pr("dsp_softcap", ops::softcap(d.q, lgd, (size_t)Vp, 30.0f));
            }
            e.pr("dsp_argmax", ops::argmax_p_rows(d.q, lgd, Vp, V, 1, gids + (i - 1), gp + (i - 1), amv, ami, ams));
        }
        std::vector<int32_t> r(n);
        d.get(r.data(), gids, n);
        probs.resize(n);
        d.get(probs.data(), gp, n);
        return r;
    }

    void add(float *a, const float *b, size_t n) {
        e.pr("dsp_add", d.q.parallel_for(sycl::range<1>(n), [=](sycl::id<1> i) { a[i] += b[i]; }));
    }

    // non-causal attention of the 8 block slots of layer l: context keys lo..P0-1 (cache) then the 8 block keys
    void attend(int l, int P0) {
        if (split) { attend_split(l, P0); return; }
        const int lo = kmask[l] == 0x7fffffff ? 0 : std::max(0, P0 - WIN);
        const int nctx = P0 - lo, nk = nctx + B;
        const sycl::half *K = Kc[l], *Vv = Vc[l];
        const float *q_ = q, *k_ = k, *v_ = v;
        float *sc_ = sc, *att_ = attl;
        const size_t la = xlane_floats(HQ * HD);
        const size_t sk = sc_keys;
        const int km = kmask[l], kd_ = kd;
        const float scale = 1.0f / std::sqrt((float)HD);
        e.pr("dsp_attn", d.q.submit([&](sycl::handler &hd) {
            sycl::local_accessor<float, 1> slm(HD, hd);
            hd.parallel_for(sycl::nd_range<1>(sycl::range<1>((size_t)B * HQ * AWG), sycl::range<1>(AWG)),
                            [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(SG)]] {
                const int gi = (int)it.get_group(0), t = gi / HQ, hq = gi % HQ, kvh = hq / (HQ / HKV), li = (int)it.get_local_id(0);
                float *qs = &slm[0];
                if (li < HD) qs[li] = q_[((size_t)t * HQ + hq) * HD + li];
                sycl::group_barrier(it.get_group());
                float *srow = sc_ + (size_t)gi * sk;
                float mx = -INFINITY;
                for (int j = li; j < nk; j += AWG) {
                    float dot = 0.0f;
                    if (j < nctx) {
                        const sycl::half *kp = K + (size_t)((lo + j) & km) * kd_ + kvh * HD;
                        for (int dd = 0; dd < HD; ++dd) dot += qs[dd] * (float)kp[dd];
                    } else {
                        const float *kp = k_ + ((size_t)(j - nctx) * HKV + kvh) * HD;
                        for (int dd = 0; dd < HD; ++dd) dot += qs[dd] * kp[dd];
                    }
                    const float sv = dot * scale;
                    srow[j] = sv;
                    mx = sycl::max(mx, sv);
                }
                mx = sycl::reduce_over_group(it.get_group(), mx, sycl::maximum<float>());
                float sum = 0.0f;
                for (int j = li; j < nk; j += AWG) {
                    const float p = sycl::exp(srow[j] - mx);
                    srow[j] = p;
                    sum += p;
                }
                sum = sycl::reduce_over_group(it.get_group(), sum, sycl::plus<float>());
                sycl::group_barrier(it.get_group());
                // P.V: thread li takes dimension li % HD, keys of parity li / HD
                const int dd = li % HD, half = li / HD;
                float acc = 0.0f;
                for (int j = half; j < nk; j += AWG / HD) {
                    const float vv = j < nctx ? (float)Vv[(size_t)((lo + j) & km) * kd_ + kvh * HD + dd]
                                              : v_[((size_t)(j - nctx) * HKV + kvh) * HD + dd];
                    acc += srow[j] * vv;
                }
                sycl::group_barrier(it.get_group());
                float *pv = &slm[0]; // q is no longer needed
                if (half == 1) pv[dd] = acc;
                sycl::group_barrier(it.get_group());
                if (half == 0) att_[(size_t)t * la + xlane_at(hq * HD + dd)] = (acc + pv[dd]) / sum;
            });
        }));
    }

    // attend() by key spans: work-group (key head kvh, span c) scores the NR = 24 rows of kvh (row r = slot r / 3,
    // query head kvh * 3 + r % 3) against its keys in passes of CH, keeping a running max / sum / P.V per row; thread
    // (key or dimension li % 128, rows 12 * (li / 128) ..+12). The combine launch merges the spans per row.
    void attend_split(int l, int P0) {
        constexpr int G = HQ / HKV, WG = 256, RH = NR / 2;
        const int lo = kmask[l] == 0x7fffffff ? 0 : std::max(0, P0 - WIN);
        const int nctx = P0 - lo, nk = nctx + B;
        const int span = CH * std::max(1, (nk + CH * NCH - 1) / (CH * NCH)), nch = (nk + span - 1) / span;
        const sycl::half *K = Kc[l], *Vv = Vc[l];
        const float *q_ = q, *k_ = k, *v_ = v;
        float *pO_ = pO, *pM_ = pM, *pL_ = pL, *att_ = attl;
        const size_t la = xlane_floats(HQ * HD);
        const int km = kmask[l], kd_ = kd;
        const float scale = 1.0f / std::sqrt((float)HD);
        e.pr("dsp_attn", d.q.submit([&](sycl::handler &hd) {
            sycl::local_accessor<float, 1> qs(NR * HD, hd), ps(NR * CH, hd), rs(3 * NR, hd);
            hd.parallel_for(sycl::nd_range<1>(sycl::range<1>((size_t)HKV * nch * WG), sycl::range<1>(WG)),
                            [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(SG)]] {
                const int gi = (int)it.get_group(0), kvh = gi / nch, c = gi % nch, li = (int)it.get_local_id(0);
                const int ki = li % CH, rg = li / CH;
                const auto sg = it.get_sub_group();
                const int sgi = (int)sg.get_group_linear_id(), ln = (int)sg.get_local_linear_id(), nsg = WG / SG;
                for (int i = li; i < NR * HD; i += WG) {
                    const int r = i / HD, dd = i % HD;
                    qs[i] = q_[((size_t)(r / G) * HQ + kvh * G + r % G) * HD + dd] * scale;
                }
                if (li < NR) { rs[li] = -INFINITY; rs[NR + li] = 0.0f; }
                float acc[RH];
#pragma unroll
                for (int r = 0; r < RH; ++r) acc[r] = 0.0f;
                const int j0 = c * span, j1 = sycl::min(nk, j0 + span);
                for (int sb = j0; sb < j1; sb += CH) {
                    const int nkc = sycl::min(CH, j1 - sb);
                    sycl::group_barrier(it.get_group());
                    // scores of key sb + ki for rows rg * 12 ..+12
                    {
                        float sv[RH];
#pragma unroll
                        for (int r = 0; r < RH; ++r) sv[r] = 0.0f;
                        if (ki < nkc) {
                            const int j = sb + ki;
                            const bool cache = j < nctx;
                            const sycl::half *kp = K + (size_t)((lo + j) & km) * kd_ + kvh * HD;
                            const float *kf = k_ + ((size_t)(j - nctx) * HKV + kvh) * HD;
                            for (int d0 = 0; d0 < HD; d0 += 32) {
                                float kv[32];
                                if (cache) {
#pragma unroll
                                    for (int u = 0; u < 4; ++u) {
                                        const sycl::vec<sycl::half, 8> h8 = *reinterpret_cast<const sycl::vec<sycl::half, 8> *>(kp + d0 + 8 * u);
#pragma unroll
                                        for (int w = 0; w < 8; ++w) kv[8 * u + w] = (float)h8[w];
                                    }
                                } else {
#pragma unroll
                                    for (int w = 0; w < 32; ++w) kv[w] = kf[d0 + w];
                                }
#pragma unroll
                                for (int r = 0; r < RH; ++r) {
                                    const float *qr = &qs[(rg * RH + r) * HD + d0];
#pragma unroll
                                    for (int w = 0; w < 32; ++w) sv[r] += qr[w] * kv[w];
                                }
                            }
                        }
#pragma unroll
                        for (int r = 0; r < RH; ++r) ps[(rg * RH + r) * CH + ki] = ki < nkc ? sv[r] : -INFINITY;
                    }
                    sycl::group_barrier(it.get_group());
                    // running max and sum per row; rs[2 NR + r] = the factor for the P.V sums so far
                    for (int r = sgi; r < NR; r += nsg) {
                        float m = -INFINITY;
                        for (int i = ln; i < CH; i += SG) m = sycl::max(m, ps[r * CH + i]);
                        m = sycl::reduce_over_group(sg, m, sycl::maximum<float>());
                        const float mo = rs[r], mn = sycl::max(mo, m);
                        float su = 0.0f;
                        for (int i = ln; i < CH; i += SG) {
                            const float pv = sycl::exp(ps[r * CH + i] - mn);
                            ps[r * CH + i] = pv;
                            su += pv;
                        }
                        su = sycl::reduce_over_group(sg, su, sycl::plus<float>());
                        if (ln == 0) {
                            const float f = sycl::exp(mo - mn);
                            rs[r] = mn; rs[NR + r] = rs[NR + r] * f + su; rs[2 * NR + r] = f;
                        }
                    }
                    sycl::group_barrier(it.get_group());
                    // P.V for dimension ki, rows rg * 12 ..+12
#pragma unroll
                    for (int r = 0; r < RH; ++r) acc[r] *= rs[2 * NR + rg * RH + r];
                    for (int kk = 0; kk < nkc; ++kk) {
                        const int j = sb + kk;
                        const float vv = j < nctx ? (float)Vv[(size_t)((lo + j) & km) * kd_ + kvh * HD + ki]
                                                  : v_[((size_t)(j - nctx) * HKV + kvh) * HD + ki];
#pragma unroll
                        for (int r = 0; r < RH; ++r) acc[r] += ps[(rg * RH + r) * CH + kk] * vv;
                    }
                }
#pragma unroll
                for (int r = 0; r < RH; ++r) pO_[(((size_t)kvh * NR + rg * RH + r) * nch + c) * HD + ki] = acc[r];
                if (li < NR) { pM_[((size_t)kvh * NR + li) * nch + c] = rs[li]; pL_[((size_t)kvh * NR + li) * nch + c] = rs[NR + li]; }
            });
        }));
        e.pr("dsp_attn_comb", d.q.parallel_for(sycl::nd_range<1>(sycl::range<1>((size_t)HKV * NR * HD), sycl::range<1>(HD)),
                                                [=](sycl::nd_item<1> it) {
            const int gi = (int)it.get_group(0), kvh = gi / NR, r = gi % NR, dd = (int)it.get_local_id(0);
            const float *m = pM_ + (size_t)gi * nch, *lsum = pL_ + (size_t)gi * nch, *o = pO_ + (size_t)gi * nch * HD;
            float mx = -INFINITY;
            for (int cc = 0; cc < nch; ++cc) mx = sycl::max(mx, m[cc]);
            float su = 0.0f, ov = 0.0f;
            for (int cc = 0; cc < nch; ++cc) {
                const float f = sycl::exp(m[cc] - mx);
                su += lsum[cc] * f;
                ov += o[(size_t)cc * HD + dd] * f;
            }
            att_[(size_t)(r / G) * la + xlane_at((kvh * G + r % G) * HD + dd)] = ov / su;
        }));
    }
};

} // namespace ink
