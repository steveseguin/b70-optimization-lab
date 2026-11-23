// model.hpp: Inkling-2 hyperparameters, the 48-application schedule over 24 physical layers, and the weights on
// the card. Everything is read from the GGUF metadata (keys as in src/models/inkling2.cpp load_arch_hparams).
#pragma once
#include "device.hpp"
#include <cmath>

namespace ink {

struct HParams {
    int n_embd, n_head, n_head_kv, head_dim, n_rel, rel_extent, n_swa, n_conv, res_block;
    int n_expert, n_used, n_ff, core_start, core_end, passes, gate_rank, vocab_padded, vocab;
    int n_app, n_phys; // 48 applications of 24 physical layers
    float eps, qk_clip, rel_clip, log_floor, log_alpha, softcap, expert_scale, situ_beta, situ_linear_beta;
    std::vector<bool> swa; // per application
    int eos;

    void load(const GGUF &g) {
        const std::string a = "inkling2.";
        n_embd = (int)g.i(a + "embedding_length");
        n_app = (int)g.i(a + "block_count");
        n_head = (int)g.arr<std::vector<int64_t>>(a + "attention.head_count")[0];
        n_head_kv = (int)g.arr<std::vector<int64_t>>(a + "attention.head_count_kv")[0];
        head_dim = (int)g.i(a + "attention.key_length");
        n_rel = (int)g.i(a + "attention.relative_length");
        rel_extent = (int)g.i(a + "attention.relative_extent");
        n_swa = (int)g.i(a + "attention.sliding_window");
        n_conv = (int)g.i(a + "shortconv.l_cache");
        res_block = (int)g.i(a + "attn_res.block_size");
        n_expert = (int)g.i(a + "expert_count");
        n_used = (int)g.i(a + "expert_used_count");
        n_ff = (int)g.i(a + "expert_feed_forward_length");
        core_start = (int)g.i(a + "loop.core_start");
        core_end = (int)g.i(a + "loop.core_end");
        passes = (int)g.i(a + "num_loops");
        gate_rank = (int)g.i(a + "loop.gate_rank");
        vocab_padded = (int)g.i(a + "vocab_size");
        vocab = (int)g.i(a + "vocab_size_unpadded");
        eps = (float)g.f(a + "attention.layer_norm_rms_epsilon");
        qk_clip = (float)g.f(a + "attention.qk_clip");
        rel_clip = (float)g.f(a + "attention.relative_clip");
        log_floor = (float)g.f(a + "attention.log_scale_floor");
        log_alpha = (float)g.f(a + "attention.log_scale_alpha");
        softcap = (float)g.f(a + "final_logit_softcapping");
        expert_scale = (float)g.f(a + "expert_weights_scale");
        situ_beta = (float)g.f(a + "activation.situ_beta");
        situ_linear_beta = (float)g.f(a + "activation.situ_linear_beta");
        auto &pat = g.arr<std::vector<int64_t>>(a + "attention.sliding_window_pattern");
        swa.assign(pat.begin(), pat.end());
        eos = (int)g.i("tokenizer.ggml.eos_token_id");
        n_phys = n_app - (passes - 1) * (core_end - core_start);
        if ((int)swa.size() != n_app) throw std::runtime_error("model: window pattern length");
    }
    int loop_len() const { return core_end - core_start; }
    // physical layer of application il (llama.cpp hparams.loop_layer)
    int phys(int il) const {
        if (il < core_start) return il;
        if (il < core_start + passes * loop_len()) return core_start + (il - core_start) % loop_len();
        return il - (passes - 1) * loop_len();
    }
    // pass of a core application (0 for the others)
    int pass(int il) const {
        int p = phys(il);
        if (p < core_start || p >= core_end) return 0;
        return (il - core_start) / loop_len();
    }
    bool in_core(int il) const { int p = phys(il); return p >= core_start && p < core_end; }
};

// one physical layer's tensors (pointers into the card arenas plus the tensor descriptions)
struct W { const Tensor *t = nullptr; const uint8_t *p = nullptr; explicit operator bool() const { return t; } };
struct Layer {
    W wq, wk, wv, wo, wgate, q_clip, sink, rel, rel_bias, rel_clip;
    W k_conv, v_conv, attn_post_conv, ffn_post_conv;
    W attn_norm, q_inp_norm, k_inp_norm, v_inp_norm, k_conv_proj, v_conv_proj;
    W attn_res_query, ffn_res_query;
    W ffn_norm, gate_inp, exp_probs_b, gate_up, down, gate_up_s, down_s;
    W loop_down[4], loop_gain[4], loop_forget[4];
};
struct Model {
    HParams hp;
    std::vector<Layer> L;
    W tok_embd, tok_norm, output, output_norm, output_res_query, loop_res_query, loop_kv_res_query;

    void bind(const GGUF &g, const Weights &wt) {
        hp.load(g);
        auto get = [&](const std::string &n, bool need = true) {
            W w;
            w.t = g.find(n);
            if (!w.t) { if (need) throw std::runtime_error("model: missing " + n); return w; }
            w.p = wt[n];
            return w;
        };
        tok_embd = get("token_embd.weight");
        tok_norm = get("token_embd_norm.weight");
        output = get("output.weight");
        output_norm = get("output_norm.weight");
        output_res_query = get("output_res_query.weight");
        loop_res_query = get("loop_res_query.weight", hp.passes > 1);
        loop_kv_res_query = get("loop_kv_res_query.weight", hp.passes > 1);
        L.resize(hp.n_phys);
        static const char *mods[4] = {"attn", "k", "v", "mlp"};
        for (int i = 0; i < hp.n_phys; ++i) {
            auto n = [&](const char *s) { return "blk." + std::to_string(i) + "." + s; };
            Layer &l = L[i];
            l.wq = get(n("attn_q.weight")); l.wk = get(n("attn_k.weight")); l.wv = get(n("attn_v.weight"));
            l.wo = get(n("attn_output.weight")); l.wgate = get(n("attn_gate.weight"));
            l.q_clip = get(n("attn_q_clip.weight")); l.sink = get(n("attn_sink_proj.weight"));
            l.rel = get(n("attn_rel.weight")); l.rel_bias = get(n("attn_rel_bias.weight")); l.rel_clip = get(n("attn_rel_clip.weight"));
            l.k_conv = get(n("attn_k_conv.weight")); l.v_conv = get(n("attn_v_conv.weight"));
            l.attn_post_conv = get(n("attn_post_conv.weight")); l.ffn_post_conv = get(n("ffn_post_conv.weight"));
            l.attn_norm = get(n("attn_norm.weight"), false);
            l.q_inp_norm = get(n("attn_q_inp_norm.weight"), false); l.k_inp_norm = get(n("attn_k_inp_norm.weight"), false);
            l.v_inp_norm = get(n("attn_v_inp_norm.weight"), false);
            l.k_conv_proj = get(n("attn_k_conv_proj.weight"), false); l.v_conv_proj = get(n("attn_v_conv_proj.weight"), false);
            l.attn_res_query = get(n("attn_res_query.weight"), false); l.ffn_res_query = get(n("ffn_res_query.weight"));
            l.ffn_norm = get(n("ffn_norm.weight")); l.gate_inp = get(n("ffn_gate_inp.weight"));
            l.exp_probs_b = get(n("exp_probs_b.bias"), false);
            l.gate_up = get(n("ffn_gate_up_exps.weight")); l.down = get(n("ffn_down_exps.weight"));
            l.gate_up_s = get(n("ffn_gate_up_exps.scale"), false); l.down_s = get(n("ffn_down_exps.scale"), false);
            if (i >= hp.core_start && i < hp.core_end && hp.passes > 1)
                for (int m = 0; m < 4; ++m) {
                    l.loop_down[m] = get(n((std::string("loop_") + mods[m] + "_down.weight").c_str()));
                    l.loop_gain[m] = get(n((std::string("loop_") + mods[m] + "_gain.weight").c_str()));
                    l.loop_forget[m] = get(n((std::string("loop_") + mods[m] + "_forget.weight").c_str()));
                }
        }
    }
};

} // namespace ink
