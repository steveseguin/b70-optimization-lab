// engine.hpp: the Inkling-2 forward pass on one card, one sequence. Activations are F32 and token-major
// ([ntok][n], the ggml order with ne0 contiguous); the K/V cache is FP16. Follows src/models/inkling2.cpp of the
// reference tree step by step (line numbers in the comments; the full write-up is notes/inkling2-forward.md).
// This first version aims at being right, not fast: plain kernels, one launch per step, no graphs.
#pragma once
#include "dump.hpp"
#include "model.hpp"
#include "ops.hpp"
#include <cmath>

namespace ink {

struct Engine {
    Device &d;
    const GGUF &g;
    Model m;
    Dumper dump;
    int T;        // most tokens per forward step (ubatch)
    int cap;      // KV capacity in positions
    bool all_logits;
    int n_past = 0;
    std::vector<float> logits; // host copy: vocab floats per returned token

    // persistent state
    std::vector<sycl::half *> Kc, Vc; // per application [cap][n_kv_head*head_dim]
    float *conv = nullptr;            // per application [6656*3], channel-major
    int conv_n = 0;                   // floats per application
    // per-step buffers
    int32_t *ids = nullptr;
    std::vector<float *> lbuf;        // lbuf[0] = normed embedding, lbuf[il+1] = l_out of application il
    float *mixb = nullptr, *inp[3] = {}, *msg[4] = {}, *mm2[2] = {};
    float *Q = nullptr, *Kr = nullptr, *Vr = nullptr, *Kx = nullptr, *Vx = nullptr, *dynK = nullptr, *dynV = nullptr;
    float *R = nullptr, *sinks = nullptr, *tab = nullptr, *P = nullptr, *att = nullptr, *gate = nullptr;
    float *ob = nullptr, *attn_out = nullptr, *ffn_inp = nullptr, *fx = nullptr, *ctl_h = nullptr, *ctl_z = nullptr;
    float *ctl_g = nullptr, *ctl_f = nullptr, *ctl_y = nullptr, *rlog = nullptr, *wts = nullptr, *gu = nullptr;
    float *hb = nullptr, *yk = nullptr, *moe = nullptr, *ffn_out = nullptr, *tau = nullptr, *fin = nullptr, *lg = nullptr;
    int32_t *eids = nullptr;
    int ldp = 0;

    Engine(Device &dev, const GGUF &gg, const Weights &wt, int capacity, int ubatch = 512, bool every_logit = false)
        : d(dev), g(gg), T(ubatch), cap(capacity), all_logits(every_logit) {
        m.bind(g, wt);
        const HParams &h = m.hp;
        const size_t E = (size_t)h.n_embd * T, QD = (size_t)h.n_head * h.head_dim * T;
        const int kd = h.n_head_kv * h.head_dim;
        const size_t KD = (size_t)kd * T;
        Kc.resize(h.n_app); Vc.resize(h.n_app);
        for (int a = 0; a < h.n_app; ++a) { Kc[a] = d.alloc<sycl::half>((size_t)cap * kd); Vc[a] = d.alloc<sycl::half>((size_t)cap * kd); }
        conv_n = (2 * kd + 2 * h.n_embd) * (h.n_conv - 1);
        conv = d.alloc_zero<float>((size_t)conv_n * h.n_app);
        ids = d.alloc<int32_t>(T);
        lbuf.resize(h.n_app + 1);
        for (auto &p : lbuf) p = d.alloc<float>(E);
        mixb = d.alloc<float>(3 * E);
        for (auto &p : inp) p = d.alloc<float>(E);
        for (auto &p : msg) p = d.alloc<float>(E);
        for (auto &p : mm2) p = d.alloc<float>(2 * E);
        Q = d.alloc<float>(QD); att = d.alloc<float>(QD); gate = d.alloc<float>(QD);
        Kr = d.alloc<float>(KD); Vr = d.alloc<float>(KD); Kx = d.alloc<float>(KD); Vx = d.alloc<float>(KD);
        dynK = d.alloc<float>((size_t)T * h.n_head_kv * h.n_conv); dynV = d.alloc<float>((size_t)T * h.n_head_kv * h.n_conv);
        R = d.alloc<float>((size_t)h.n_rel * h.n_head * T);
        sinks = d.alloc<float>((size_t)h.n_head * T);
        tab = d.alloc<float>((size_t)h.rel_extent * h.n_head * T);
        ldp = cap;
        P = d.alloc<float>((size_t)ldp * h.n_head * T);
        ob = d.alloc<float>(E); attn_out = d.alloc<float>(E); ffn_inp = d.alloc<float>(E); fx = d.alloc<float>(E);
        ctl_h = d.alloc<float>(2 * E); ctl_z = d.alloc<float>((size_t)h.gate_rank * T);
        ctl_g = d.alloc<float>(E); ctl_f = d.alloc<float>(E); ctl_y = d.alloc<float>(E);
        rlog = d.alloc<float>((size_t)h.n_expert * T);
        eids = d.alloc<int32_t>((size_t)h.n_used * T); wts = d.alloc<float>((size_t)h.n_used * T);
        gu = d.alloc<float>((size_t)h.n_used * T * 2 * h.n_ff); hb = d.alloc<float>((size_t)h.n_used * T * h.n_ff);
        yk = d.alloc<float>((size_t)h.n_used * T * h.n_embd);
        moe = d.alloc<float>(E); ffn_out = d.alloc<float>(E);
        tau = d.alloc<float>(T); fin = d.alloc<float>(E);
        lg = d.alloc<float>((size_t)h.vocab_padded * (all_logits ? T : 1));
    }

    void reset() {
        n_past = 0;
        d.q.memset(conv, 0, sizeof(float) * (size_t)conv_n * m.hp.n_app).wait();
    }

    // y[t] = W x[t] for ntok vectors, eight per launch
    void mm(const W &w, const float *x, float *y, int ntok) {
        int cols = (int)w.t->ne[0], rows = (int)w.t->rows();
        for (int t0 = 0; t0 < ntok; t0 += 8)
            gemv(d.q, *w.t, w.p, x + (size_t)t0 * cols, cols, y + (size_t)t0 * rows, rows, std::min(8, ntok - t0));
    }
    const float *f32(const W &w) const {
        if (!w) return nullptr;
        if (w.t->type != G_F32) throw std::runtime_error("engine: expected F32 tensor " + w.t->name);
        return (const float *)w.p;
    }
    std::string nm(const char *s, int il) const { return std::string(s) + "-" + std::to_string(il); }

    // mix(blocks, cur, query) with nq queries (inkling2.cpp:221); results query-major in out
    void mix(const std::vector<const float *> &blocks, const float *cur, const float *query, int nq, float *out, int n) {
        ops::MixArgs a;
        int nb = (int)blocks.size();
        if (nb + 1 > ops::MIX_MAX) throw std::runtime_error("engine: too many blocks");
        for (int s = 0; s < nb; ++s) a.st[s] = blocks[nb - 1 - s];
        a.st[nb] = cur;
        a.ns = nb + 1;
        ops::mix(d.q, a, m.hp.n_embd, query, nq, out, n, n_tok);
    }
    // control(cur, msg, layer, module) (inkling2.cpp:237) into y
    void control(const float *cur, const float *mg, const Layer &l, int mod, float *y) {
        const HParams &h = m.hp;
        int n = n_tok, E = h.n_embd;
        ops::rms_norm(d.q, cur, ctl_h, nullptr, E, n, 1e-6f, E, 2 * E);
        ops::rms_norm(d.q, mg, ctl_h + E, nullptr, E, n, 1e-6f, E, 2 * E);
        mm(l.loop_down[mod], ctl_h, ctl_z, n);
        mm(l.loop_gain[mod], ctl_z, ctl_g, n);
        mm(l.loop_forget[mod], ctl_z, ctl_f, n);
        ops::control_out(d.q, cur, mg, ctl_f, ctl_g, y, (size_t)n * E);
    }

    int n_tok = 0;

    // one step of ntok <= T tokens at positions n_past..; logits for the last token (or all, if all_logits)
    void step(const int32_t *tok, int ntok) {
        const HParams &h = m.hp;
        const int E = h.n_embd, hd = h.head_dim, nh = h.n_head, nkvh = h.n_head_kv, kd = nkvh * hd;
        const int pos0 = n_past;
        n_tok = ntok;
        if (pos0 + ntok > cap) throw std::runtime_error("engine: context full");
        d.put(ids, tok, ntok);
        {   // log-scaled positions (inkling2.cpp:339-345), as the reference computes them in F32
            std::vector<float> tv(ntok);
            for (int t = 0; t < ntok; ++t) {
                float x = (float)(pos0 + t) * 1.0f + 1.0f;
                x = x * (1.0f / (float)h.log_floor);
                x = std::log(std::max(x, 1.0f));
                tv[t] = x * h.log_alpha + 1.0f;
            }
            d.put(tau, tv.data(), ntok);
        }
        // embedding and token norm (inkling2.cpp:347-352)
        ops::get_rows(d.q, *m.tok_embd.t, m.tok_embd.p, ids, lbuf[0], ntok);
        ops::rms_norm(d.q, lbuf[0], lbuf[0], f32(m.tok_norm), E, ntok, h.eps);

        std::vector<const float *> blocks, prelude_blocks, bank;
        const float *cur = lbuf[0], *prelude_cur = nullptr, *bank_last = nullptr;
        const int nloop = h.passes > 1 ? h.loop_len() : 0;
        const float kscale = 1.0f / std::sqrt((float)hd);

        for (int il = 0; il < h.n_app; ++il) {
            const int ip = h.phys(il);
            const Layer &l = m.L[ip];
            const bool swa = h.swa[il];
            const float *mg[4] = {nullptr, nullptr, nullptr, nullptr};
            if (nloop > 0 && ip >= h.core_start && ip < h.core_end) { // inkling2.cpp:367-399
                const int pass = (il - h.core_start) / nloop;
                if (ip == h.core_start) {
                    if (pass == 0) { prelude_blocks = blocks; prelude_cur = cur; }
                    else {
                        bank.assign(blocks.begin() + prelude_blocks.size() + 1, blocks.end());
                        bank_last = cur;
                        blocks = prelude_blocks;
                        cur = prelude_cur;
                    }
                }
                if (pass > 0) {
                    const int row = 2 * (ip - h.core_start);
                    mix(bank, bank_last, f32(m.loop_res_query) + (size_t)row * E, 2, mm2[0], E);
                    mix(bank, bank_last, f32(m.loop_kv_res_query) + (size_t)row * E, 2, mm2[1], E);
                    const size_t S = (size_t)ntok * E;
                    mg[0] = mm2[0]; mg[3] = mm2[0] + S; mg[1] = mm2[1]; mg[2] = mm2[1] + S;
                }
            }
            const float *inpSA = cur;
            // attention inputs (inkling2.cpp:418-444)
            const float *in[3] = {cur, cur, cur};
            if (l.attn_res_query) {
                int nq = (int)l.attn_res_query.t->rows();
                mix(blocks, cur, f32(l.attn_res_query), nq, mixb, E);
                for (int j = 0; j < 3; ++j) in[j] = mixb + (size_t)(swa ? 0 : j) * ntok * E;
            }
            if (mg[0]) {
                for (int j = 0; j < 3; ++j) { control(in[j], mg[j], l, j, msg[j]); in[j] = msg[j]; }
                dump.put(d, nm("loop_q_inp", il), msg[0], E, ntok);
            }
            if (swa && mg[0]) {
                for (int j = 0; j < 3; ++j) { ops::rms_norm(d.q, in[j], inp[j], f32(l.attn_norm), E, ntok, h.eps); in[j] = inp[j]; }
            } else if (swa) {
                ops::rms_norm(d.q, in[0], inp[0], f32(l.attn_norm), E, ntok, h.eps);
                in[0] = in[1] = in[2] = inp[0];
            } else {
                ops::rms_norm(d.q, in[0], inp[0], f32(l.q_inp_norm), E, ntok, h.eps);
                ops::rms_norm(d.q, in[1], inp[1], f32(l.k_inp_norm), E, ntok, h.eps);
                ops::rms_norm(d.q, in[2], inp[2], f32(l.v_inp_norm), E, ntok, h.eps);
                in[0] = inp[0]; in[1] = inp[1]; in[2] = inp[2];
            }
            // projections, convolutions, clips (inkling2.cpp:446-463)
            float *st = conv + (size_t)il * conv_n;
            mm(l.wq, in[0], Q, ntok);
            mm(l.wk, in[1], Kr, ntok);
            mm(l.wv, in[2], Vr, ntok);
            if (!swa) { mm(l.k_conv_proj, in[1], dynK, ntok); mm(l.v_conv_proj, in[2], dynV, ntok); }
            ops::convolve(d.q, Kr, st, 0, f32(l.k_conv), swa ? nullptr : dynK, nkvh, Kx, kd, ntok);
            ops::convolve(d.q, Vr, st, kd, f32(l.v_conv), swa ? nullptr : dynV, nkvh, Vx, kd, ntok);
            ops::conv_store(d.q, Kr, st, 0, kd, ntok);
            ops::conv_store(d.q, Vr, st, kd, kd, ntok);
            mm(l.rel, in[0], R, ntok);
            ops::clip(d.q, Q, f32(l.q_clip), nh, hd, nh * ntok, h.qk_clip);
            ops::clip(d.q, Kx, nullptr, 1, hd, nkvh * ntok, h.qk_clip);
            ops::rms_norm(d.q, Vx, Vx, nullptr, hd, nkvh * ntok, h.eps);
            ops::clip(d.q, R, f32(l.rel_clip), nh, h.n_rel, nh * ntok, h.rel_clip);
            if (!swa) {
                ops::scale_rows(d.q, Q, tau, nh * hd, ntok);
                ops::scale_rows(d.q, R, tau, nh * h.n_rel, ntok);
            }
            dump.put(d, nm("Qcur", il), Q, hd, nh, ntok);
            dump.put(d, nm("Kcur", il), Kx, hd, nkvh, ntok);
            dump.put(d, nm("Vcur", il), Vx, hd, nkvh, ntok);
            dump.put(d, nm("Rcur", il), R, h.n_rel, nh, ntok);
            mm(l.sink, in[0], sinks, ntok);
            // attention with the relative bias and the sink (spec 4.7, banded form)
            ops::kv_store(d.q, Kx, Kc[il], pos0, kd, ntok);
            ops::kv_store(d.q, Vx, Vc[il], pos0, kd, ntok);
            ops::rel_table(d.q, R, f32(l.rel_bias), h.n_rel, h.rel_extent, tab, nh, ntok);
            const int win = swa ? h.n_swa : 0;
            ops::attn_softmax(d.q, Q, Kc[il], tab, sinks, pos0, ntok, nh, nkvh, hd, h.rel_extent, win, kscale, P, ldp);
            ops::attn_pv(d.q, P, ldp, Vc[il], pos0, ntok, nh, nkvh, hd, win, att);
            // output gate, wo, post conv (inkling2.cpp:595-597)
            mm(l.wgate, in[0], gate, ntok);
            ops::mul_sigmoid(d.q, att, gate, (size_t)ntok * nh * hd);
            mm(l.wo, att, ob, ntok);
            ops::convolve(d.q, ob, st, 2 * kd, f32(l.attn_post_conv), nullptr, 1, attn_out, E, ntok);
            ops::conv_store(d.q, ob, st, 2 * kd, E, ntok);
            // block start or residual (inkling2.cpp:600-605)
            const float *fi;
            if (ip % h.res_block == 0) { blocks.push_back(inpSA); fi = attn_out; }
            else {
                dump.put(d, nm("attn_out", il), attn_out, E, ntok);
                ops::add(d.q, inpSA, attn_out, ffn_inp, (size_t)ntok * E);
                fi = ffn_inp;
            }
            dump.put(d, nm("ffn_inp", il), fi, E, ntok);
            // MoE (inkling2.cpp:609-634)
            mix(blocks, fi, f32(l.ffn_res_query), 1, fx, E);
            const float *xm = fx;
            if (mg[3]) { control(fx, mg[3], l, 3, ctl_y); xm = ctl_y; dump.put(d, nm("loop_ffn_inp", il), ctl_y, E, ntok); }
            ops::rms_norm(d.q, xm, fx, f32(l.ffn_norm), E, ntok, h.eps);
            mm(l.gate_inp, fx, rlog, ntok);
            const int K = ntok * h.n_used;
            ops::moe_route(d.q, rlog, f32(l.exp_probs_b), h.n_expert, h.n_used, h.expert_scale, eids, wts, ntok);
            gemv_routed(d.q, *l.gate_up.t, l.gate_up.p, eids, K, fx, E, h.n_used, gu, 2 * h.n_ff);
            ops::situ(d.q, gu, f32(l.gate_up_s), eids, h.n_ff, h.situ_beta, h.situ_linear_beta, hb, K);
            gemv_routed(d.q, *l.down.t, l.down.p, eids, K, hb, h.n_ff, 1, yk, E);
            ops::moe_combine(d.q, yk, f32(l.down_s), eids, wts, h.n_used, E, moe, ntok);
            ops::convolve(d.q, moe, st, 2 * kd + E, f32(l.ffn_post_conv), nullptr, 1, ffn_out, E, ntok);
            ops::conv_store(d.q, moe, st, 2 * kd + E, E, ntok);
            dump.put(d, nm("ffn_out", il), ffn_out, E, ntok);
            float *lo = lbuf[il + 1];
            ops::add(d.q, fi, ffn_out, lo, (size_t)ntok * E);
            dump.put(d, nm("l_out", il), lo, E, ntok);
            cur = lo;
        }
        // output (inkling2.cpp:643-669)
        mix(blocks, cur, f32(m.output_res_query), 1, fin, E);
        ops::rms_norm(d.q, fin, fin, f32(m.output_norm), E, ntok, h.eps);
        dump.put(d, "result_norm", fin, E, ntok);
        const int nl = all_logits ? ntok : 1;
        const float *xl = all_logits ? fin : fin + (size_t)(ntok - 1) * E;
        mm(m.output, xl, lg, nl);
        ops::softcap(d.q, lg, (size_t)nl * h.vocab_padded, h.softcap);
        logits.resize((size_t)nl * h.vocab);
        d.q.wait();
        for (int t = 0; t < nl; ++t)
            d.q.memcpy(logits.data() + (size_t)t * h.vocab, lg + (size_t)t * h.vocab_padded, sizeof(float) * h.vocab);
        d.q.wait();
        if (dump.want("result_output")) {
            // logits are in host memory already
            std::ofstream o(dump.dir + "/result_output.f32", std::ios::binary);
            o.write((const char *)logits.data(), logits.size() * 4);
            std::fprintf(dump.index, "result_output\tf32\t%d\t%d\t1\t1\n", h.vocab, nl);
            std::fflush(dump.index);
        }
        n_past += ntok;
    }

    // feed tokens (any number) in steps of T; returns the logits of the last token (or of every token of the last
    // step when all_logits)
    const std::vector<float> &feed(const std::vector<int32_t> &tok) {
        for (size_t p = 0; p < tok.size(); p += T) step(tok.data() + p, (int)std::min<size_t>(T, tok.size() - p));
        return logits;
    }
    int argmax_last() const {
        const int V = m.hp.vocab;
        const float *l = logits.data() + logits.size() - V;
        int b = 0;
        for (int i = 1; i < V; ++i) if (l[i] > l[b]) b = i;
        return b;
    }
};

} // namespace ink
