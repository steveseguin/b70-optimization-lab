// engine.hpp: the Inkling-2 forward pass on one card, one sequence. Activations are F32 and token-major
// ([ntok][n], the ggml order with ne0 contiguous); the K/V cache is FP16. Follows src/models/inkling2.cpp of the
// reference tree step by step (line numbers in the comments; the full write-up is notes/inkling2-forward.md).
// This first version aims at being right, not fast: plain kernels, one launch per step, no graphs.
#pragma once
#include "dump.hpp"
#include "model.hpp"
#include "attn_tiles.hpp"
#include "attn_flash.hpp"
#include "fused.hpp"
#include "tok_tiles.hpp"
#include "multi.hpp"
#include "warm.hpp"
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
    std::vector<sycl::half *> Kc, Vc; // per application [cap][n_kv_head*head_dim]; Vc transposed when vld > 0
    int vld = 0;                      // V cache [n_kv_head*head_dim][vld] (INK_VT=0: [cap][n_kv_head*head_dim])
    static constexpr int PVB_RING_MIN = 128;
    int ring_w = 0;                   // windowed applications' ring size (positions)
    std::vector<int> kvl, kmask;      // per application: V cache stride, cache slot mask
    float *conv = nullptr;            // two copies (previous call, this call) of [n_app][6656*3], channel-major
    int conv_n = 0;                   // floats per application
    int cpar = 0;                     // which copy holds the state of the previous call
    // per-step buffers
    int32_t *ids = nullptr;
    std::vector<float *> lbuf;        // lbuf[0] = normed embedding, lbuf[il+1] = l_out of application il
    float *mixb = nullptr, *inp[3] = {}, *msg[4] = {}, *mm2[2] = {};
    float *Q = nullptr, *Kr = nullptr, *Vr = nullptr, *Kx = nullptr, *Vx = nullptr, *dynK = nullptr, *dynV = nullptr;
    float *R = nullptr, *Rc = nullptr, *sinks = nullptr, *tab = nullptr, *P = nullptr, *att = nullptr, *gate = nullptr;
    float *ob = nullptr, *attn_out = nullptr, *ffn_inp = nullptr, *fx = nullptr, *ctl_h = nullptr, *ctl_z = nullptr;
    float *ctl_g = nullptr, *ctl_f = nullptr, *ctl_y = nullptr, *rlog = nullptr, *wts = nullptr, *gu = nullptr;
    float *hb = nullptr, *yk = nullptr, *moe = nullptr, *ffn_out = nullptr, *tau = nullptr, *fin = nullptr, *lg = nullptr;
    int32_t *eids = nullptr;
    int ldp = 0;
    int prow = 0; // score rows (tokens) P holds; a step's attention runs in chunks of prow tokens
    float *mix_inv = nullptr, *mix_sc = nullptr;
    // the loop mixes of a whole pass at its start (their states are fixed for the pass): INK_LOOP_PRE=0 one per layer
    bool loop_pre = true;
    // steps of up to this many tokens compute the pass's loop mixes in two launches (writing steps and checks: fewer
    // launches); longer steps mix per layer into mm2 (the same values), so lmix_out holds 48 x lp_tok tokens, not 48 x T
    // (216 MiB at 512-token steps; INK_LOOP_PRE_TOK)
    int lp_tok = 16;
    int loop_nq = 0;
    float *lmix_inv = nullptr, *lmix_sc = nullptr, *lmix_out = nullptr;
    // one-token steps: the three attention controls of a layer in three launches instead of nine (INK_CTL_BATCH=0)
    bool ctl_batch = true;
    bool route_sg = true;
    // steps of at least att_tile tokens: attention scores and P.V as register tiles (attn_tiles.hpp, the bias computed
    // in place); INK_ATT_TILE (0 = never)
    int att_tile = 16;
    // writing steps: attn_scores_g + attn_softmax_sum + attn_pv_ti (INK_DEC_ATTN, default on); wmax: per row
    // (16 tokens x heads) the sub-group maxima of the scores, nsgmax per row; pinv: per row 1 / softmax total
    bool dec_attn = true;
    float *wmax = nullptr, *pinv = nullptr;
    float *pmaxb = nullptr; // per row the softmax maximum (prompt tiles with pv_exp)
    float *pvpart = nullptr; // attn_pv_bo_part's block sums: pv_rows tokens x heads x (cap / PVB + 2) blocks x head_dim
    // prompt chunks past 32K keys: the block-split P.V tiles take up to 64 score rows per launch (INK_PV_ROWS; 16 = one
    // launch per 16 rows as before). Each row's block sums do not depend on the other rows: the same values.
    int pv_rows = 16;
    int nsgmax = 0;
    // baseline v4 (2026-11-24): attention of the layers without a window in blocks of PVB keys with a running maximum
    // (attn_flash.hpp; INK_FLASH=0 = baseline v3's softmax over the whole row). Steps of at least flash_min tokens
    // (INK_FLASH_MIN) in one launch that keeps the scores in local memory; else attn_flash_dec (each block's scores in
    // local memory, its maximum and sum in pml) and attn_flash_sum. Every path gives the same values. With both on, only
    // the windowed layers use P, whose rows start at each row's window: P rows are the window wide, not the context
    bool q5k_tiles = !std::getenv("INK_Q5K_TILES") || std::atoi(std::getenv("INK_Q5K_TILES")) != 0;
    bool flash = true;
    bool flash_dec = true; // INK_FLASH_DEC=0: steps below flash_min keep scores in P (attn_scores_* + attn_flash_part)
    bool flash_lean = true; // INK_FLASH_LEAN=0: the prompt kernel without constant Q offsets, local block loads, rows' maxima
    int dec_rows = 16;     // rows per attn_flash_dec launch (its parts buffer holds this many rows of the whole context)
    int flash_min = 128;
    float *pml = nullptr;
    int pv_u = 64;             // attention P*V keys per batch (INK_PV_U: 16 = attn_pv_gate2, 32, 64, 128)
    // decode copies (gemv2.hpp dec_kind) of the expert weights in formats without a planar layout (layers 20-23), used
    // below the tile threshold: INK_DEC=0 reads the file layout
    std::vector<WView> gu_dec, dn_dec;      // expert routing with one sub-group per token (INK_ROUTE_SG=0: one work-group)
    float *ctl_h3 = nullptr, *ctl_z3 = nullptr;
    float *tau_all = nullptr;  // log-scaled position factor of every position
    int32_t *next_id = nullptr;
    MoeGroups grp;             // slots grouped by expert (steps of several tokens)
    float *Xt = nullptr, *Ht = nullptr; // transposed tiles of the token-parallel expert kernels (moe_group.hpp)
    int tile_bound = 0;
    int tile_min = 128;        // steps of at least this many tokens use the token-parallel kernels (INK_TILE_MIN)
    float *Xd = nullptr;       // transposed tiles of the dense token-parallel kernels (tok_tiles.hpp)
    int dense_min = 16;        // steps of at least this many tokens use them for the dense matrices (INK_DENSE_MIN)
    bool multi_proj = true;    // one-token steps: the attention-input matrices in one launch (INK_MULTI=0: one each)
    static constexpr int XD_COLS = 4608; // widest dense input (loop down: 2 x 2304)
    int n_logit_rows = 1;      // logits rows the last step left in lg
    bool host_logits = true;   // copy the logits to the host after each step (false: next_token() reads them on the card)
    bool mix_v1 = std::getenv("INK_MIX_V1") && std::atoi(std::getenv("INK_MIX_V1")); // the one-launch mix (slower)
    // saved states' mix scores in a table (fz::mix_fused): INK_MIX_TAB=0 computes every state's score in each mix
    bool mix_tab = true;
    // warm (INK_WARM=0 off): in one-token steps the attention mix (fz::mix_fused, latency-bound) carries INK_WARM_WG
    // extra work-groups (default 12) that read the first INK_WARM_MB (default 3) of the attention input weights into
    // L2, so the matrix kernel after it finds them there (card 3: 12.14 -> 11.99 ms per token; values unchanged).
    // (A warm kernel on a second queue does not run beside the main queue on this card: reads nobody needs cost their
    // full time, 2026-11-23.)
    int warm_on = 1;
    bool route_stats = std::getenv("INK_ROUTE_STATS") && std::atoi(std::getenv("INK_ROUTE_STATS"));
    float *fxl = nullptr; // the feed-forward input of one token in lane order
    // steps of 2-8 tokens (INK_SB=0 off): the attention inputs in lane order (3 inputs x SB_MAX tokens), read by one
    // multi-matrix launch for all tokens (multi.hpp gemv_multi_m)
    static constexpr int SB_MAX = 8;
    bool sb_on = true;
    int sb_r = 2, sb_sgw = 2; // rows per sub-group (INK_SB_R), sub-groups per work-group (INK_SB_SGW)
    float *ainl = nullptr;
    bool sb_moe = true;     // INK_SB_MOE=0: steps of 2-8 tokens use the 8-slot grouped expert kernels
    int sb_np = 1, sb_dr = 2; // NVFP4 small steps: gate|up row pairs (INK_SB_NP), down rows (INK_SB_DR) per sub-group
    float *fxls = nullptr;  // the feed-forward input of 2-8 tokens in lane order (SB_MAX rows)
    // checking guesses (check / accept): every token but the last of the step also writes its convolution states,
    // token t at cst + t * n_app * conv_n (all applications); the choice after each row goes to cids
    float *cst = nullptr;
    int32_t *cids = nullptr;
    // guesser hooks (dspark.hpp): feat [4][T][n_embd] gets the stream entering visits feat_vis[0..2] and the final normed
    // rows of every step; on_step(pos0, ntok) runs after each step's launches
    float *feat = nullptr;
    int feat_vis[3] = {-1, -1, -1};
    // steps of 1-8 tokens: the final norm also writes lane-order rows (finl) for the lane-order output kernels
    // (INK_OUT_LANE=0 off); argmax scratch of the two-launch argmax (ops::argmax_rows2)
    bool out_lane = true, att_share = true, tile_sm = true;
    // prompt tiles of layers without a window: the softmax writes only each row's maximum and 1 / total, P.V computes the
    // exponentials as it reads the scores (INK_PV_EXP=0 off; the same values, P written once less)
    bool pv_exp = true;
    int att_share_min = 4096; // INK_ATT_SHARE_MIN: keys from which checks share key reads
    float *finl = nullptr, *amx_v = nullptr;
    int32_t *amx_i = nullptr;
    std::function<void(int, int)> on_step;
    bool keep_states = false;
    int chk_n = 0;          // tokens of the last check
    // INK_XL=0: matrix inputs in the plain layout only (else lane order where the producer writes it, gemv2.hpp)
    bool xl_on = !std::getenv("INK_XL") || std::atoi(std::getenv("INK_XL"));
    int dn_sgw = std::getenv("INK_DN_SGW") ? std::atoi(std::getenv("INK_DN_SGW")) : 1; // lane-order down: sub-groups per group
    bool split_on = !std::getenv("INK_SPLIT") || std::atoi(std::getenv("INK_SPLIT")); // gemv_split for few F32 rows
    int warm_wg = 12;
    int gu_sgw = std::getenv("INK_GU_SGW") ? std::atoi(std::getenv("INK_GU_SGW")) : 1; // gate|up pair kernel, one token (1 < 2 by ~0.5 us)
    uint32_t *warm_sink = nullptr;
    void warm_add(fz::WarmSet &s, const W &w) { if (w) s.add(w.p, w.rb * (size_t)w.t->rows()); }
    fz::WarmSet attn_in_set(int il) {
        const HParams &h = m.hp;
        fz::WarmSet s;
        if (il >= h.n_app) return s;
        const Layer &l = m.L[h.phys(il)];
        warm_add(s, l.wq); warm_add(s, l.wk); warm_add(s, l.wv);
        if (!h.swa[il]) { warm_add(s, l.k_conv_proj); warm_add(s, l.v_conv_proj); }
        warm_add(s, l.rel); warm_add(s, l.sink); warm_add(s, l.wgate);
        return s;
    }
    fz::Warm pend; // carried by the next mix_fused launch
    size_t warm_bytes = (size_t)3 << 20;
    // the attention input weights of the current application, warmed in turn by kernels before their product (now
    // the mix only: warm work-groups in the norms after it cost more than they saved, 2026-11-23)
    fz::WarmSet wsrc;
    size_t wcur = 0;
    fz::Warm take_warm(size_t bytes) {
        if (!warm_on || n_tok != 1 || wcur >= (size_t)64 << 20) return {};
        fz::Warm w{fz::warm_range(wsrc, wcur, bytes), warm_wg, warm_sink};
        wcur += bytes;
        if (!w.s.k) w.nwg = 0;
        return w;
    }
    int mix_nqa = 0, qi_out = -1;
    std::vector<int> qi_attn, qi_ffn;
    uint64_t *mix_qall = nullptr;
    float *tab_inv = nullptr, *tab_sc = nullptr;
    int slot_of(const float *p) const {
        for (size_t k = 0; k < lbuf.size(); ++k) if (lbuf[k] == p) return (int)k;
        return -1;
    }

    Engine(Device &dev, const GGUF &gg, const Weights &wt, int capacity, int ubatch = 512, bool every_logit = false,
           const std::map<std::string, WView> *views = nullptr)
        : d(dev), g(gg), T(ubatch), cap(capacity), all_logits(every_logit) {
        m.bind(g, wt, views);
        const HParams &h = m.hp;
        if (!m.tok_embd.p) { // the embedding table stays in host memory (embed())
            const Tensor &t = *m.tok_embd.t;
            if (t.ne[0] % 32) throw std::runtime_error("engine: embedding rows must hold whole blocks of 32");
            embd_tab.resize(t.bytes);
            g.read_at(embd_tab.data(), t.bytes, g.data_off + t.off);
        }
        const size_t E = (size_t)h.n_embd * T, QD = (size_t)h.n_head * h.head_dim * T;
        const int kd = h.n_head_kv * h.head_dim;
        const size_t KD = (size_t)kd * T;
        Kc.resize(h.n_app); Vc.resize(h.n_app);
        if (!std::getenv("INK_VT") || std::atoi(std::getenv("INK_VT"))) vld = (cap + 15) / 16 * 16;
        // windowed applications keep a ring of ring_w positions (slot = position & (ring_w - 1)): a step reads at most
        // window + T - 1 keys plus the rounding down to a block of PVB, so ring_w >= window + T + PVB holds them all
        // (INK_RING=0: every cache holds the whole context)
        ring_w = PVB_RING_MIN;
        while (ring_w < h.n_swa + T + fz::PVB) ring_w <<= 1;
        const bool ring = vld && !(std::getenv("INK_RING") && !std::atoi(std::getenv("INK_RING"))) && ring_w < cap;
        kvl.assign(h.n_app, vld); kmask.assign(h.n_app, 0x7fffffff);
        for (int a = 0; a < h.n_app; ++a) {
            const bool r = ring && h.swa[a];
            if (r) { kvl[a] = ring_w; kmask[a] = ring_w - 1; }
            Kc[a] = d.alloc<sycl::half>((size_t)(r ? ring_w : cap) * kd);
            Vc[a] = d.alloc<sycl::half>((size_t)(r ? ring_w : (vld ? vld : cap)) * kd);
        }
        conv_n = (2 * kd + 2 * h.n_embd) * (h.n_conv - 1);
        conv = d.alloc_zero<float>((size_t)2 * conv_n * h.n_app);
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
        R = d.alloc<float>((size_t)h.n_rel * h.n_head * T); Rc = d.alloc<float>((size_t)h.n_rel * h.n_head * T);
        sinks = d.alloc<float>((size_t)h.n_head * T);
        tab = d.alloc<float>((size_t)h.rel_extent * h.n_head * T);
        if (const char *e = std::getenv("INK_FLASH")) flash = std::atoi(e) != 0;
        if (const char *e = std::getenv("INK_FLASH_MIN")) flash_min = std::atoi(e);
        if (const char *e = std::getenv("INK_FLASH_DEC")) flash_dec = std::atoi(e) != 0;
        if (const char *e = std::getenv("INK_FLASH_LEAN")) flash_lean = std::atoi(e) != 0;
        // long contexts: 8 rows (a check of 5-8 tokens reads the keys and values once; 0.75 KB per position), past 480K
        // positions 4 (0.4 KB; a 5-8 token check takes two launches)
        dec_rows = cap <= 131072 ? 16 : cap <= 491520 ? 8 : 4;
        if (const char *e = std::getenv("INK_DEC_ROWS")) dec_rows = std::max(1, std::min(16, std::atoi(e)));
        // P's row stride: the window (the windowed kernels store column j - lo of each row) when the layers without a
        // window keep their scores in local memory, else the context (their rows store column j)
        const bool p_win = flash && flash_dec && h.n_swa > 0;
        ldp = p_win ? (h.n_swa + 15) / 16 * 16 : cap;
        { // score rows (a multiple of 16, at least 16, at most T): as many as fit INK_P_MB MiB if set; else as many as fit
            // 512 MiB, or more, up to INK_P_ROWS (default 256), while the card keeps INK_P_FREE_GB (default 6) GiB for the
            // allocations after this one and the drafter. Long prompts then run their attention in fewer, larger chunks
            // (the keys and values read fewer times; from 128 rows P.V needs no block parts), the same values
            const double row_b = (double)ldp * h.n_head * 4.0;
            long rows;
            if (const char *e = std::getenv("INK_P_MB")) rows = (long)(std::atof(e) * 1048576.0 / row_b);
            else {
                const long want = std::getenv("INK_P_ROWS") ? std::atol(std::getenv("INK_P_ROWS")) : 256;
                const double keep = (std::getenv("INK_P_FREE_GB") ? std::atof(std::getenv("INK_P_FREE_GB")) : 6.0) * 1073741824.0;
                const double room = (double)d.limit() - (double)d.allocated - keep;
                rows = std::max((long)(512.0 * 1048576.0 / row_b), std::min(want, room > 0 ? (long)(room / row_b) : 0L));
            }
            prow = (int)std::min<long>(T, std::max<long>(16, rows / 16 * 16));
        }
        P = d.alloc<float>((size_t)ldp * h.n_head * prow);
        nsgmax = ldp / 16 + 2;
        // rows: 16 (writing steps) or the score rows (prompt tiles of layers without a window, INK_TILE_SM)
        wmax = d.alloc<float>((size_t)std::max(16, prow) * h.n_head * nsgmax);
        pinv = d.alloc<float>((size_t)std::max(16, prow) * h.n_head);
        pmaxb = d.alloc<float>((size_t)std::max(16, prow) * h.n_head);
        pv_rows = cap > 32768 ? std::max(16, std::min(prow, 64)) : 16;
        if (const char *e = std::getenv("INK_PV_ROWS")) pv_rows = std::max(16, std::min(prow, std::atoi(e))) / 16 * 16;
        { // block parts: rows x heads x blocks (attn_flash_dec: dec_rows rows of the whole context; the windowed layers'
            // P.V: pv_rows or 16 rows of a window's blocks); without p_win every path may take pv_rows of the context
            const size_t r16 = (size_t)std::max(16, pv_rows), ctx_b = (size_t)(cap / fz::PVB + 2);
            const size_t pr_n = p_win ? std::max((size_t)dec_rows * ctx_b, r16 * ((ldp + r16) / fz::PVB + 3)) : r16 * ctx_b;
            const size_t ml_n = p_win ? (size_t)dec_rows * ctx_b : r16 * ctx_b;
            pvpart = d.alloc<float>(pr_n * h.n_head * h.head_dim);
            pml = d.alloc<float>(ml_n * h.n_head * 2);
        }
        if (vld == 0 || h.n_head != 3 * h.n_head_kv) // the block-order P.V reads the transposed cache, 3 heads per KV head
            throw std::runtime_error("engine: INK_VT=0 and head groups other than 3 are not supported");
        ob = d.alloc<float>(E); attn_out = d.alloc<float>(E); ffn_inp = d.alloc<float>(E); fx = d.alloc<float>(E);
        ctl_h = d.alloc<float>(2 * E); ctl_z = d.alloc<float>((size_t)h.gate_rank * T);
        ctl_g = d.alloc<float>(E); ctl_f = d.alloc<float>(E); ctl_y = d.alloc<float>(E);
        rlog = d.alloc<float>((size_t)h.n_expert * T);
        eids = d.alloc<int32_t>((size_t)h.n_used * T); wts = d.alloc<float>((size_t)h.n_used * T);
        gu = d.alloc<float>((size_t)h.n_used * T * 2 * h.n_ff); hb = d.alloc<float>((size_t)h.n_used * T * std::max((size_t)h.n_ff, xlane_floats(h.n_ff)));
        yk = d.alloc<float>((size_t)h.n_used * T * h.n_embd);
        moe = d.alloc<float>(E); ffn_out = d.alloc<float>(E);
        fin = d.alloc<float>(E);
        {   // log-scaled positions (inkling2.cpp:339-345) for every position, as the reference computes them in F32
            std::vector<float> tv(cap);
            for (int p = 0; p < cap; ++p) {
                float x = (float)p * 1.0f + 1.0f;
                x = x * (1.0f / (float)h.log_floor);
                x = std::log(std::max(x, 1.0f));
                tv[p] = x * h.log_alpha + 1.0f;
            }
            tau_all = d.alloc<float>(cap);
            d.put(tau_all, tv.data(), cap);
        }
        next_id = d.alloc<int32_t>(1);
        grp.alloc(d, h.n_expert, T * h.n_used);
        if (const char *e = std::getenv("INK_TILE_MIN")) tile_min = std::atoi(e);
        if (T >= tile_min) {
            tile_bound = MoeGroups::max_tiles(h.n_expert, T * h.n_used);
            Xt = d.alloc<float>((size_t)tile_bound * h.n_embd * MOE_TS);
            Ht = d.alloc<float>((size_t)tile_bound * h.n_ff * MOE_TS);
        }
        if (const char *e = std::getenv("INK_DENSE_MIN")) dense_min = std::atoi(e);
        if (const char *e = std::getenv("INK_MULTI")) multi_proj = std::atoi(e) != 0;
        if (T >= dense_min) Xd = d.alloc<float>((size_t)((T + MOE_TS - 1) / MOE_TS) * XD_COLS * MOE_TS);
        mix_inv = d.alloc<float>((size_t)T * ops::MIX_MAX); mix_sc = d.alloc<float>((size_t)T * 3 * ops::MIX_MAX);
        if (const char *e = std::getenv("INK_LOOP_PRE")) loop_pre = std::atoi(e) != 0;
        if (const char *e = std::getenv("INK_CTL_BATCH")) ctl_batch = std::atoi(e) != 0;
        if (const char *e = std::getenv("INK_ROUTE_SG")) route_sg = std::atoi(e) != 0;
        if (const char *e = std::getenv("INK_PV_U")) pv_u = std::atoi(e);
        if (const char *e = std::getenv("INK_ATT_TILE")) att_tile = std::atoi(e);
        if (const char *e = std::getenv("INK_DEC_ATTN")) dec_attn = std::atoi(e) != 0;
        {
            const bool dec = dec_on();
            auto mk = [&](const W &w) {
                WView v = w.view();
                if (!dec || !w || v.kind != K_RAW || dec_kind(*w.t) == K_RAW) return v;
                v.kind = dec_kind(*w.t);
                v.rb = dec_stride(*w.t);
                uint8_t *b = d.alloc<uint8_t>(v.rb * (size_t)w.t->rows());
                dec_repack(d.q, *w.t, w.p, b).wait();
                v.p = b;
                return v;
            };
            for (const Layer &l : m.L) { gu_dec.push_back(mk(l.gate_up)); dn_dec.push_back(mk(l.down)); }
        }
        if (h.passes > 1 && m.loop_res_query && m.loop_kv_res_query) {
            const int nr = (int)m.loop_res_query.t->rows();
            if (nr != 2 * h.loop_len() || (int)m.loop_kv_res_query.t->rows() != nr) loop_pre = false;
            if (loop_pre) {
                loop_nq = 2 * nr;
                if (const char *e = std::getenv("INK_LOOP_PRE_TOK")) lp_tok = std::atoi(e);
                lp_tok = std::max(1, std::min(T, lp_tok));
                lmix_inv = d.alloc<float>((size_t)lp_tok * ops::MIX_MAX);
                lmix_sc = d.alloc<float>((size_t)lp_tok * loop_nq * ops::MIX_MAX);
                lmix_out = d.alloc<float>((size_t)loop_nq * lp_tok * h.n_embd);
            }
        } else loop_pre = false;
        ctl_h3 = d.alloc<float>((size_t)3 * SB_MAX * 2 * h.n_embd); ctl_z3 = d.alloc<float>((size_t)3 * SB_MAX * h.gate_rank);
        if (const char *e = std::getenv("INK_MIX_TAB")) mix_tab = std::atoi(e) != 0;
        if (const char *e = std::getenv("INK_WARM")) warm_on = std::atoi(e);
        if (const char *e = std::getenv("INK_WARM_WG")) warm_wg = std::max(1, std::atoi(e));
        if (const char *e = std::getenv("INK_WARM_MB")) warm_bytes = (size_t)(std::atof(e) * 1048576.0);
        warm_sink = d.alloc<uint32_t>(16);
        fxl = d.alloc<float>(xlane_floats(h.n_embd));
        if (const char *e = std::getenv("INK_SB")) sb_on = std::atoi(e) != 0;
        if (const char *e = std::getenv("INK_SB_R")) sb_r = std::atoi(e);
        if (const char *e = std::getenv("INK_SB_SGW")) sb_sgw = std::atoi(e);
        ainl = d.alloc<float>(3 * SB_MAX * xlane_floats(h.n_embd));
        fxls = d.alloc<float>(SB_MAX * xlane_floats(h.n_embd));
        cst = d.alloc<float>((size_t)(SB_MAX - 1) * h.n_app * conv_n);
        cids = d.alloc<int32_t>(SB_MAX);
        finl = d.alloc<float>(SB_MAX * xlane_floats(h.n_embd));
        amx_v = d.alloc<float>((size_t)SB_MAX * ops::ARGMAX_G); amx_i = d.alloc<int32_t>((size_t)SB_MAX * ops::ARGMAX_G);
        if (const char *e = std::getenv("INK_OUT_LANE")) out_lane = std::atoi(e) != 0;
        if (const char *e = std::getenv("INK_ATT_SHARE")) att_share = std::atoi(e) != 0;
        if (const char *e = std::getenv("INK_TILE_SM")) tile_sm = std::atoi(e) != 0;
        if (const char *e = std::getenv("INK_PV_EXP")) pv_exp = std::atoi(e) != 0;
        if (const char *e = std::getenv("INK_ATT_SHARE_MIN")) att_share_min = std::atoi(e);
        if (const char *e = std::getenv("INK_SB_MOE")) sb_moe = std::atoi(e) != 0;
        if (const char *e = std::getenv("INK_SB_NP")) sb_np = std::atoi(e);
        if (const char *e = std::getenv("INK_SB_DR")) sb_dr = std::atoi(e);
        if (mix_v1) mix_tab = false;
        if (mix_tab) { // every mix query row of the model (attention, MoE, output), in one index
            std::vector<uint64_t> qa;
            auto add = [&](const W &w) {
                if (!w) return -1;
                const int i0 = (int)qa.size();
                for (int64_t r = 0; r < w.t->rows(); ++r) qa.push_back((uint64_t)(uintptr_t)(f32(w) + (size_t)r * h.n_embd));
                return i0;
            };
            qi_attn.resize(m.L.size()); qi_ffn.resize(m.L.size());
            for (size_t ip = 0; ip < m.L.size(); ++ip) { qi_attn[ip] = add(m.L[ip].attn_res_query); qi_ffn[ip] = add(m.L[ip].ffn_res_query); }
            qi_out = add(m.output_res_query);
            mix_nqa = (int)qa.size();
            mix_qall = d.alloc<uint64_t>(qa.size());
            d.put(mix_qall, qa.data(), qa.size());
            tab_inv = d.alloc<float>(lbuf.size() * T);
            tab_sc = d.alloc<float>(lbuf.size() * T * (size_t)mix_nqa);
        }
        lg = d.alloc<float>((size_t)h.vocab_padded * std::max(all_logits ? T : 1, SB_MAX));
    }

    void reset() {
        n_past = 0;
        d.q.memset(conv, 0, sizeof(float) * (size_t)2 * conv_n * m.hp.n_app).wait();
        cpar = 0;
    }

    // launch shapes per layout (tools/bench_gemv, card 3, 2026-11-22): rows per sub-group R, sub-groups per group
    // (honest timing from distinct copies, card 2-4, 2026-11-22: notes in README)
    static Tune tune(const W &w) {
        const int64_t rows = w.t->rows();
        switch (w.kind) {
        case K_Q8_0P: return rows <= 1024 ? Tune{1, 4} : Tune{2, 2};
        case K_Q6_KP: return Tune{2, 2}; // output too since the 4-values-at-a-time decode (720 vs 802 us)
        default: return w.t->ne[0] <= 64 ? Tune{2, 2} : Tune{1, 4}; // F32 / BF16 in the file layout
        }
    }
    static Tune tune_routed(const WView &v) { // IQ4 copies: one row per sub-group (their decode is the longer part)
        return (v.kind == K_IQ4_NLP || v.kind == K_IQ4_XSP) ? Tune{1, 2} : Tune{2, 2};
    }
    // several vectors: blocks of mr vectors per sub-group (bench_gemv BENCH_M=8, card 3, 2026-11-22)
    static Tune tune_m(const W &w) {
        switch (w.kind) {
        case K_Q8_0P: return Tune{2, 2, false, 8, false};
        case K_Q6_KP: return Tune{2, 2, false, 8, true};
        case K_NVFP4P: return Tune{2, 2, false, 8, false};
        default: return Tune{1, 4, false, 4, true};
        }
    }
    // y[t] = W x[t] for ntok vectors: one launch for the whole blocks of vectors, one for the rest
    // dense token-parallel kernels for this matrix at ntok tokens? (tools/bench_gemv BENCH_M=16..512, card 3,
    // 2026-11-22: Q8_0 / Q6_K / F32 2.5-4x from 16 tokens; F32 rows of 2304 need >= 128 tokens; few rows lose)
    bool dense_tiles(const W &w, int ntok, DTune &dt) const {
        if (!Xd || ntok < dense_min || w.t->ne[0] > XD_COLS || w.t->rows() < 64) return false;
        // INK_DENSE_R / INK_DENSE_SGW: rows and sub-groups per work-group of the Q8_0 / Q6_K tiles from 64 tokens
        // (default 4 rows, 32 sub-groups; the same values. INK_PROF 3K prompt, card 3: attn_output 1,323 -> 935 us per
        // launch; rows are the independent sums a lane keeps going, 2 = before)
        static const int dr = std::getenv("INK_DENSE_R") ? std::atoi(std::getenv("INK_DENSE_R")) : 4;
        static const int dsg = std::getenv("INK_DENSE_SGW") ? std::max(1, std::atoi(std::getenv("INK_DENSE_SGW"))) : 32;
        switch (w.kind) {
        case K_Q8_0P: dt = ntok >= 64 ? DTune{dr, dsg} : DTune{1, 1}; return true;
        case K_Q6_KP: dt = ntok >= 64 ? DTune{dr, dsg} : DTune{1, 1}; return true;
        case K_RAW:
            if (w.t->type == G_F32) { dt = DTune{1, 1}; return w.t->ne[0] <= 64 || ntok >= 128; }
            if (w.t->type == G_BF16) { dt = DTune{1, 1}; return w.t->ne[0] <= 64 || ntok >= 128; }
            // Q5_K (attn_q of layer 22, file layout): ran the generic multi-vector kernel in prompt steps
            if (w.t->type == G_Q5_K && q5k_tiles) { dt = ntok >= 64 ? DTune{dr, dsg} : DTune{1, 1}; return true; }
            return false;
        default: return false;
        }
    }
    void mm(const W &w, const float *x, float *y, int ntok) {
        int cols = (int)w.t->ne[0], rows = (int)w.t->rows();
        if (ntok == 1) {
            if (split_on && split_ok(w.view())) { // few F32 rows: chunks split across sub-groups (multi.hpp gemv_split)
                SplitJobs sj;
                split_add(sj, w.view(), x, y);
                pr(wlabel(w), gemv_split(d.q, sj));
                return;
            }
            pr(wlabel(w), gemv_v(d.q, w.view(), x, cols, y, rows, 1, tune(w)));
            return;
        }
        DTune dt;
        if (dense_tiles(w, ntok, dt)) {
            pr("dense_gather", dense_gather(d.q, x, cols, ntok, cols, Xd));
            pr(wlabel(w), dense_t(d.q, w.view(), ntok, Xd, y, rows, dt));
            return;
        }
        Tune tm = tune_m(w);
        int nfull = ntok / tm.mr * tm.mr, rem = ntok - nfull;
        if (nfull) pr(wlabel(w), gemv_v(d.q, w.view(), x, cols, y, rows, nfull, tm));
        if (rem) {
            Tune tr = tm;
            tr.mr = rem;
            pr(wlabel(w), gemv_v(d.q, w.view(), x + (size_t)nfull * cols, cols, y + (size_t)nfull * rows, rows, rem, tr));
        }
    }
    const float *f32(const W &w) const {
        if (!w) return nullptr;
        if (w.t->type != G_F32) throw std::runtime_error("engine: expected F32 tensor " + w.t->name);
        return (const float *)w.p;
    }
    Prof prof;
    void pr(const std::string &label, sycl::event e) { prof.add(label, e); }
    // the token embedding table in host memory (ink_run leaves it off the card: m.tok_embd.p null; INK_EMBD_HOST=0 keeps
    // it there): each step's rows are decoded on the host with the kernel's expressions (F<type>::decode32: Q8_0 y = q * d,
    // one multiply) into one of two staging buffers and copied to the card in queue order
    std::vector<uint8_t> embd_tab;
    std::vector<float> embd_stage[2];
    sycl::event embd_ev[2];
    int embd_k = 0;
    int32_t last_tok = -1; // the host's copy of next_token()'s choice (ids[0] for step(nullptr, 1))
    void embed(const int32_t *tok, int ntok, float *dst) {
        const Tensor &t = *m.tok_embd.t;
        const int n = (int)t.ne[0], nc = n / 32;
        const size_t rb = t.row_bytes();
        const int64_t rows = (int64_t)t.rows();
        std::vector<float> &st = embd_stage[embd_k];
        embd_ev[embd_k].wait(); // the copy that last read this buffer
        st.resize((size_t)ntok * n);
        fmt::dispatch(t.type, [&]<class FT>() {
            for (int i = 0; i < ntok; ++i) {
                if (tok[i] < 0 || tok[i] >= rows) throw std::runtime_error("engine: token id " + std::to_string(tok[i]) + " out of range");
                const uint8_t *row = embd_tab.data() + (size_t)tok[i] * rb;
                for (int c = 0; c < nc; ++c) FT::decode32(row, c, st.data() + (size_t)i * n + 32 * c);
            }
        });
        embd_ev[embd_k] = d.q.memcpy(dst, st.data(), sizeof(float) * (size_t)ntok * n);
        pr("get_rows", embd_ev[embd_k]);
        embd_k ^= 1;
    }
    static std::string wlabel(const W &w) {
        const std::string &n = w.t->name;
        size_t a = n.rfind(".weight");
        std::string s = n.substr(0, a);
        if (s.compare(0, 4, "blk.") == 0) s = s.substr(s.find('.', 4) + 1);
        static const bool types = std::getenv("INK_PROF_TYPES") != nullptr; // profile labels with the weight format
        return types ? "w:" + s + ":" + type_name(w.t->type) : "w:" + s;
    }
    std::string nm(const char *s, int il) const { return std::string(s) + "-" + std::to_string(il); }

    // the table form of a mix (fz::mix_fused) when every block has a table slot and the query has a table index;
    // mk >= 0: also save cur at table slot mk
    bool mix_f(const std::vector<const float *> &blocks, const float *cur, const float *query, int nq, int qi0, int mk,
               float *out, const fz::NormOut *no, int n, const char *label) {
        if (!mix_tab || qi0 < 0) return false;
        fz::MixF a;
        const int nb = (int)blocks.size();
        if (nb + 1 > ops::MIX_MAX) throw std::runtime_error("engine: too many blocks");
        for (int s = 0; s < nb; ++s) {
            a.st[s] = blocks[nb - 1 - s];
            a.slot[s] = slot_of(a.st[s]);
            if (a.slot[s] < 0) return false;
        }
        a.st[nb] = cur;
        a.ns = nb + 1;
        a.query = query; a.nq = nq; a.qi0 = qi0;
        a.tinv = tab_inv; a.tsc = tab_sc; a.T = T; a.NQA = mix_nqa; a.mk_slot = mk; a.qall = mix_qall;
        if (!pend.sink) pend.sink = warm_sink;
        pr(label, fz::mix_fused(d.q, a, m.hp.n_embd, out, no, m.hp.eps, n, n_tok, pend));
        pend = {};
        return true;
    }
    // save cur's scale and query scores at table slot mk (role B of mix_fused alone)
    void save_state(const float *cur, int mk) {
        if (!mix_tab || mk < 0) return;
        fz::MixF a;
        a.st[0] = cur; a.ns = 1; a.nq = 0;
        a.tinv = tab_inv; a.tsc = tab_sc; a.T = T; a.NQA = mix_nqa; a.mk_slot = mk; a.qall = mix_qall;
        pr("mix_save", fz::mix_fused(d.q, a, m.hp.n_embd, nullptr, nullptr, m.hp.eps, m.hp.n_embd, n_tok));
    }
    // mix(blocks, cur, query) with nq queries (inkling2.cpp:221); results query-major in out
    void mix(const std::vector<const float *> &blocks, const float *cur, const float *query, int nq, float *out, int n,
             int qi0 = -1, int mk = -1) {
        if (mix_f(blocks, cur, query, nq, qi0, mk, out, nullptr, n, "mix_out")) return;
        save_state(cur, mk);
        ops::MixArgs a;
        int nb = (int)blocks.size();
        if (nb + 1 > ops::MIX_MAX) throw std::runtime_error("engine: too many blocks");
        for (int s = 0; s < nb; ++s) a.st[s] = blocks[nb - 1 - s];
        a.st[nb] = cur;
        a.ns = nb + 1;
        if (mix_v1) { pr("mix", ops::mix(d.q, a, m.hp.n_embd, query, nq, out, n, n_tok)); return; }
        pr("mix_scores", fz::mix_scores(d.q, a, m.hp.n_embd, query, nq, mix_inv, mix_sc, n, n_tok));
        pr("mix_out", ops::mix_out(d.q, a, m.hp.n_embd, nq, mix_inv, mix_sc, out, n, n_tok));
    }
    // mix() followed by rms_norm (eps of the model) of each query's result: no.y[j] = norm(mix_j) * no.w[j]
    void mix_norm(const std::vector<const float *> &blocks, const float *cur, const float *query, int nq, fz::NormOut no, int n,
                  int qi0 = -1, int mk = -1) {
        if (mix_f(blocks, cur, query, nq, qi0, mk, nullptr, &no, n, "mix_norm")) return;
        save_state(cur, mk);
        ops::MixArgs a;
        int nb = (int)blocks.size();
        if (nb + 1 > ops::MIX_MAX) throw std::runtime_error("engine: too many blocks");
        for (int s = 0; s < nb; ++s) a.st[s] = blocks[nb - 1 - s];
        a.st[nb] = cur;
        a.ns = nb + 1;
        pr("mix_scores", fz::mix_scores(d.q, a, m.hp.n_embd, query, nq, mix_inv, mix_sc, n, n_tok));
        pr("mix_norm", fz::mix_out_norm(d.q, a, m.hp.n_embd, nq, mix_inv, mix_sc, nullptr, no, m.hp.eps, n, n_tok));
    }
    // control(cur, msg, layer, module) (inkling2.cpp:237) into y
    void control(const float *cur, const float *mg, const Layer &l, int mod, float *y) {
        const HParams &h = m.hp;
        int n = n_tok, E = h.n_embd;
        const fz::NormJob jobs[2] = {{cur, ctl_h, nullptr, E, 2 * E}, {mg, ctl_h + E, nullptr, E, 2 * E}};
        pr("ctl_norm", fz::rms_norm_multi(d.q, jobs, 2, E, n, 1e-6f));
        mm(l.loop_down[mod], ctl_h, ctl_z, n);
        const W &ga = l.loop_gain[mod], &fo = l.loop_forget[mod];
        if (ga.t->type != fo.t->type || ga.rb != fo.rb || ga.kind != fo.kind) throw std::runtime_error("engine: gain/forget layouts differ");
        DTune dt;
        if (n > 1 && dense_tiles(ga, n, dt)) {
            pr("dense_gather", dense_gather(d.q, ctl_z, h.gate_rank, n, h.gate_rank, Xd));
            dt.R = std::min(dt.R, 2); // pairs: 2 x R rows per sub-group
            pr("ctl_out", dense_pair_t(d.q, ga.view(), fo.p, E, n, Xd, CtlOp{cur, mg, y, E}, dt));
            return;
        }
        if (n == 1 && ctl_batch && ctl_multi_ok(ga.view(), fo.view())) {
            CtlJobs cj;
            ctl_add(cj, ga.view(), fo.view(), ctl_z, CtlOp{cur, mg, y, E});
            if (ctl_rows_ok(cj)) { pr("ctl_out", ctl_rows(d.q, cj)); return; }
        }
        pr("ctl_out", gemv_pair(d.q, ga.view(), fo.p, 0, E, nullptr, n, ctl_z, h.gate_rank, 0, CtlOp{cur, mg, y, E}, 2));
    }

    // control() of modules mods[0..nm) (nm <= 3) for n_tok <= SB_MAX tokens in three launches (norms, down products,
    // gain|forget outputs into out[j]); false (nothing launched) when a weight's format has no multi kernel. Each
    // (token, row) sum is the one-token kernels' (gemv1_rows / gemvM_rows, CtlRows), so the values are control()'s.
    bool control_multi(int nm, const int *mods, const float *const *in, const float *const *mg, float *const *out, const Layer &l) {
        const HParams &h = m.hp;
        const int E = h.n_embd, n = n_tok, R = h.gate_rank;
        if (nm < 1 || nm > 3 || n < 1 || n > SB_MAX) return false;
        CtlJobs cj;
        for (int j = 0; j < nm; ++j) {
            const int k = mods[j];
            if (!multi_ok(l.loop_down[k].view()) || !ctl_multi_ok(l.loop_gain[k].view(), l.loop_forget[k].view())) return false;
            ctl_add(cj, l.loop_gain[k].view(), l.loop_forget[k].view(), ctl_z3 + (size_t)j * SB_MAX * R, CtlOp{in[j], mg[j], out[j], E});
            cj.j[j].ldx = R;
        }
        cj.nt = n;
        if (n > 1 && !ctl_rows_ok(cj)) return false; // (ctl_multi takes one token)
        fz::NormJob jobs[6];
        for (int j = 0; j < nm; ++j) {
            jobs[2 * j] = {in[j], ctl_h3 + (size_t)j * SB_MAX * 2 * E, nullptr, E, 2 * E};
            jobs[2 * j + 1] = {mg[j], ctl_h3 + (size_t)j * SB_MAX * 2 * E + E, nullptr, E, 2 * E};
        }
        pr("ctl_norm", fz::rms_norm_multi(d.q, jobs, 2 * nm, E, n, 1e-6f));
        MultiJobs mj; // (gemv_split is slower for these three: multi.hpp split_ok)
        for (int j = 0; j < nm; ++j)
            multi_add(mj, l.loop_down[mods[j]].view(), ctl_h3 + (size_t)j * SB_MAX * 2 * E, ctl_z3 + (size_t)j * SB_MAX * R, 1, 2 * E, R);
        pr(nm == 3 ? "w:loop_down3" : "w:loop_down1", n == 1 ? gemv_multi(d.q, mj, 2) : gemv_multi_m(d.q, mj, n, false, 2));
        pr("ctl_out", n > 1 || ctl_rows_ok(cj) ? ctl_rows(d.q, cj) : ctl_multi(d.q, cj, 2));
        return true;
    }

    int n_tok = 0;

    // one step of ntok <= T tokens at positions n_past..; logits for the last token (or all, if all_logits)
    void step(const int32_t *tok, int ntok) {
        const HParams &h = m.hp;
        const int E = h.n_embd, hd = h.head_dim, nh = h.n_head, nkvh = h.n_head_kv, kd = nkvh * hd;
        const int pos0 = n_past;
        n_tok = ntok;
        if (pos0 + ntok > cap) throw std::runtime_error("engine: context full");
        if (ntok < 1 || ntok > T) // the buffers hold T tokens: a bigger step writes past them (a card page fault)
            throw std::runtime_error("engine: step of " + std::to_string(ntok) + " tokens, buffers hold " + std::to_string(T));
        if (tok) d.put(ids, tok, ntok); // else ids[0..ntok) are on the card already (next_token())
        tau = tau_all + pos0;
        // embedding and token norm (inkling2.cpp:347-352)
        if (m.tok_embd.p) pr("get_rows", ops::get_rows(d.q, *m.tok_embd.t, m.tok_embd.p, ids, lbuf[0], ntok));
        else {
            if (!tok && (ntok != 1 || last_tok < 0)) throw std::runtime_error("engine: step(nullptr) needs next_token() first");
            embed(tok ? tok : &last_tok, ntok, lbuf[0]);
        }
        pr("rms_norm", ops::rms_norm(d.q, lbuf[0], lbuf[0], f32(m.tok_norm), E, ntok, h.eps));

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
                        if (loop_pre && ntok <= lp_tok) { // every loop mix of this pass (12 layers x 2 calls x 2 queries) in two launches
                            ops::MixArgs a;
                            const int nb = (int)bank.size();
                            if (nb + 1 > ops::MIX_MAX) throw std::runtime_error("engine: too many blocks");
                            for (int s = 0; s < nb; ++s) a.st[s] = bank[nb - 1 - s];
                            a.st[nb] = bank_last;
                            a.ns = nb + 1;
                            const int nr = loop_nq / 2;
                            pr("loop_mix_scores", fz::mix_scores_many(d.q, a, E, f32(m.loop_res_query), nr, f32(m.loop_kv_res_query), nr,
                                                                      lmix_inv, lmix_sc, E, ntok));
                            pr("loop_mix_out", ops::mix_out(d.q, a, E, loop_nq, lmix_inv, lmix_sc, lmix_out, E, ntok));
                        }
                    }
                }
                if (pass > 0) {
                    const int row = 2 * (ip - h.core_start);
                    const size_t S = (size_t)ntok * E;
                    if (loop_pre && ntok <= lp_tok) {
                        const float *res = lmix_out + (size_t)row * S, *kv = lmix_out + (size_t)(loop_nq / 2 + row) * S;
                        mg[0] = res; mg[3] = res + S; mg[1] = kv; mg[2] = kv + S;
                    } else {
                        mix(bank, bank_last, f32(m.loop_res_query) + (size_t)row * E, 2, mm2[0], E);
                        mix(bank, bank_last, f32(m.loop_kv_res_query) + (size_t)row * E, 2, mm2[1], E);
                        mg[0] = mm2[0]; mg[3] = mm2[0] + S; mg[1] = mm2[1]; mg[2] = mm2[1] + S;
                    }
                }
            }
            const float *inpSA = cur;
            if (feat)
                for (int j = 0; j < 3; ++j)
                    if (il == feat_vis[j]) d.q.memcpy(feat + (size_t)j * T * E, cur, sizeof(float) * (size_t)ntok * E);
            // a block starts here: cur is saved (its mix scores into the table) by the attention mix, or alone
            const int mk = (ip % h.res_block == 0 && mix_tab) ? slot_of(cur) : -1;
            // attention inputs (inkling2.cpp:418-444)
            const float *in[3] = {cur, cur, cur};
            bool normed = false;
            // a step of 2-8 tokens: the norms also write their outputs in lane order (inl), for gemv_multi_m
            const bool sb = sb_on && multi_proj && ntok >= 2 && ntok <= SB_MAX;
            const size_t sbs = (size_t)SB_MAX * xlane_floats(E);
            const float *inl[3] = {nullptr, nullptr, nullptr};
            if (!l.attn_res_query) save_state(cur, mk);
            if (warm_on && ntok == 1) { wsrc = attn_in_set(il); wcur = 0; pend = take_warm(warm_bytes); }
            if (l.attn_res_query) {
                int nq = (int)l.attn_res_query.t->rows();
                if (!mg[0] && (!swa || nq == 1)) { // the norm follows the mix directly: one kernel for both
                    fz::NormOut no{};
                    if (swa) { no.y[0] = inp[0]; no.w[0] = f32(l.attn_norm); }
                    else {
                        no.y[0] = inp[0]; no.y[1] = inp[1]; no.y[2] = inp[2];
                        no.w[0] = f32(l.q_inp_norm); no.w[1] = f32(l.k_inp_norm); no.w[2] = f32(l.v_inp_norm);
                    }
                    if (sb) for (int j = 0; j < (swa ? 1 : 3); ++j) no.yl[j] = ainl + j * sbs;
                    mix_norm(blocks, cur, f32(l.attn_res_query), nq, no, E, qi_attn.empty() ? -1 : qi_attn[ip], mk);
                    for (int j = 0; j < 3; ++j) in[j] = inp[swa ? 0 : j];
                    if (sb) for (int j = 0; j < 3; ++j) inl[j] = ainl + (swa ? 0 : j) * sbs;
                    normed = true;
                } else {
                    mix(blocks, cur, f32(l.attn_res_query), nq, mixb, E, qi_attn.empty() ? -1 : qi_attn[ip], mk);
                    for (int j = 0; j < 3; ++j) in[j] = mixb + (size_t)(swa ? 0 : j) * ntok * E;
                }
            }
            if (mg[0]) {
                static constexpr int m012[3] = {0, 1, 2};
                if (ctl_batch && control_multi(3, m012, in, mg, msg, l)) {
                } else {
                    for (int j = 0; j < 3; ++j) control(in[j], mg[j], l, j, msg[j]);
                }
                for (int j = 0; j < 3; ++j) in[j] = msg[j];
                dump.put(d, nm("loop_q_inp", il), msg[0], E, ntok);
            }
            if (normed) {
            } else if (swa && !mg[0]) {
                pr("rms_norm", ops::rms_norm(d.q, in[0], inp[0], f32(l.attn_norm), E, ntok, h.eps, -1, -1, sb ? ainl : nullptr));
                in[0] = in[1] = in[2] = inp[0];
                if (sb) inl[0] = inl[1] = inl[2] = ainl;
            } else {
                const float *wn[3] = {f32(l.attn_norm), f32(l.attn_norm), f32(l.attn_norm)};
                if (!swa) { wn[0] = f32(l.q_inp_norm); wn[1] = f32(l.k_inp_norm); wn[2] = f32(l.v_inp_norm); }
                fz::NormJob jobs[3];
                for (int j = 0; j < 3; ++j) jobs[j] = {in[j], inp[j], wn[j], E, E, sb ? ainl + j * sbs : nullptr};
                pr("rms_norm3", fz::rms_norm_multi(d.q, jobs, 3, E, ntok, h.eps));
                in[0] = inp[0]; in[1] = inp[1]; in[2] = inp[2];
                if (sb) for (int j = 0; j < 3; ++j) inl[j] = ainl + j * sbs;
            }
            // projections, convolutions, clips (inkling2.cpp:446-463)
            // this call reads the state of the previous call and writes its own (two copies)
            const float *st_in = conv + ((size_t)cpar * h.n_app + il) * conv_n;
            float *st_out = conv + ((size_t)(cpar ^ 1) * h.n_app + il) * conv_n;
            float *st_tok = keep_states ? cst + (size_t)il * conv_n : nullptr;
            const size_t sst = (size_t)h.n_app * conv_n;
            if (ntok == 1 && multi_proj) { // one launch for the matrices that read the attention inputs (multi.hpp)
                MultiJobs mj;
                const W *ws[8] = {&l.wq, &l.wk, &l.wv, swa ? nullptr : &l.k_conv_proj, swa ? nullptr : &l.v_conv_proj, &l.rel, &l.sink, &l.wgate};
                const float *xs[8] = {in[0], in[1], in[2], in[1], in[2], in[0], in[0], in[0]};
                float *ys[8] = {Q, Kr, Vr, dynK, dynV, R, sinks, gate};
                bool ok = true;
                for (int k = 0; k < 8; ++k) if (ws[k] && !multi_ok(ws[k]->view())) ok = false;
                if (ok) {
                    for (int k = 0; k < 8; ++k) if (ws[k]) multi_add(mj, ws[k]->view(), xs[k], ys[k], std::min(tune(*ws[k]).R, 2));
                    pr("w:attn_in", gemv_multi(d.q, mj, 2));
                } else {
                    for (int k = 0; k < 8; ++k) if (ws[k]) mm(*ws[k], xs[k], ys[k], ntok);
                }
            } else if (sb && inl[0] && multi_proj) { // 2-8 tokens: the same matrices in one launch, inputs in lane order
                MultiJobs mj;
                const W *ws[8] = {&l.wq, &l.wk, &l.wv, swa ? nullptr : &l.k_conv_proj, swa ? nullptr : &l.v_conv_proj, &l.rel, &l.sink, &l.wgate};
                const float *xs[8] = {inl[0], inl[1], inl[2], inl[1], inl[2], inl[0], inl[0], inl[0]};
                float *ys[8] = {Q, Kr, Vr, dynK, dynV, R, sinks, gate};
                bool ok = true;
                for (int k = 0; k < 8; ++k) if (ws[k] && !multi_ok(ws[k]->view())) ok = false;
                if (ok) {
                    const int lx = (int)xlane_floats(E);
                    for (int k = 0; k < 8; ++k)
                        if (ws[k]) multi_add(mj, ws[k]->view(), xs[k], ys[k], ntok > 4 ? 1 : std::min(tune(*ws[k]).R, sb_r), lx, (int)ws[k]->t->rows());
                    pr("w:attn_in", gemv_multi_m(d.q, mj, ntok, true, sb_sgw));
                } else {
                    for (int k = 0; k < 8; ++k) if (ws[k]) mm(*ws[k], in[k < 3 ? k : (k < 5 ? k - 2 : 0)], ys[k], ntok);
                }
            } else {
                mm(l.wq, in[0], Q, ntok);
                mm(l.wk, in[1], Kr, ntok);
                mm(l.wv, in[2], Vr, ntok);
                if (!swa) { mm(l.k_conv_proj, in[1], dynK, ntok); mm(l.v_conv_proj, in[2], dynV, ntok); }
                mm(l.rel, in[0], R, ntok);
                mm(l.sink, in[0], sinks, ntok);
                mm(l.wgate, in[0], gate, ntok);
            }
            const bool tiles = att_tile > 0 && ntok >= att_tile && vld > 0 && nh == 3 * nkvh && h.n_rel == 16;
            {   // convolutions, clips, positions, cache store, bias table (one launch)
                fz::PrepArgs a{};
                a.ntok = ntok; a.pos0 = pos0; a.nh = nh; a.nkvh = nkvh; a.hd = hd; a.nr = h.n_rel; a.ext = h.rel_extent;
                a.full = !swa; a.tau = tau;
                a.Q = Q; a.q_clip = f32(l.q_clip); a.qk_clip = h.qk_clip;
                a.Kr = Kr; a.Vr = Vr; a.dynK = dynK; a.dynV = dynV; a.k_conv = f32(l.k_conv); a.v_conv = f32(l.v_conv);
                a.st_in = st_in; a.st_out = st_out; a.st_tok = st_tok; a.sst = sst; a.Kx = Kx; a.Vx = Vx; a.Kc = Kc[il]; a.Vc = Vc[il]; a.vld = kvl[il]; a.km = kmask[il];
                a.eps = h.eps; a.kv_scale = fz::conv_scale(!swa);
                a.R = R; a.Rc = Rc; a.rel_clip = f32(l.rel_clip); a.rel_clip_thr = h.rel_clip; a.rel_bias = f32(l.rel_bias); a.tab = tiles ? nullptr : tab;
                pr("attn_prep", fz::attn_prep(d.q, a));
            }
            dump.put(d, nm("Qcur", il), Q, hd, nh, ntok);
            dump.put(d, nm("Kcur", il), Kx, hd, nkvh, ntok);
            dump.put(d, nm("Vcur", il), Vx, hd, nkvh, ntok);
            dump.put(d, nm("Rcur", il), Rc, h.n_rel, nh, ntok);
            // attention with the relative bias and the sink (spec 4.7, banded form), then the output gate
            const int win = swa ? h.n_swa : 0;
            // writing steps (<= 16 tokens, transposed cache): scores 3 heads per key, softmax sums only (the maximum
            // from the scores' sub-group maxima), P.V normalizes as it reads; the same values as the general kernels
            const bool fast = !tiles && dec_attn && ntok <= 16 && vld > 0 && nh == 3 * nkvh;
            // steps of 2-4 tokens (checks): keys and values read once for all tokens (INK_ATT_SHARE=0 off), only in the
            // layers without a window (every token's keys start at 0; 31K checks: scores 375 -> 166 us, P.V 393 -> 212)
            // (short contexts: too few work-groups, code checks at ~400 keys P.V 7.7 -> 18.4 us; even at 3K; from 4,096)
            const bool share = fast && att_share && ntok >= 2 && ntok <= 4 && pos0 + ntok > att_share_min;
            // in chunks of prow query tokens: the score buffer P holds prow rows of the whole context (each row's
            // values do not depend on the other rows of its step)
            // windowed layers, steps of 1-8 tokens: the four kernels below in one launch (fused.hpp attn_win_fused, the same
            // values; INK_ATT_WINF=0 off). 2 work-groups per KV head split the channels for 1-2 tokens (bench_attn card 3,
            // full window: 1 token 16.0 -> 15.2 us, 4 tokens 22.3 -> 18.1; 400 keys 10.4 -> 7.5, 12.0 -> 8.4)
            const bool winf = fast && win > 0 && win <= 1024 && ntok <= SB_MAX && fz::att_win_fused_on();
            if (winf) {
                if (ntok <= 2)
                    pr("attn_win", fz::attn_win_fused<3, 3, 2>(d.q, Q, Kc[il], tab, Vc[il], kvl[il], sinks, gate, pos0, ntok, nh, nkvh, hd,
                                                              h.rel_extent, win, kscale, kmask[il], att));
                else
                    pr("attn_win", fz::attn_win_fused<3, 3, 1>(d.q, Q, Kc[il], tab, Vc[il], kvl[il], sinks, gate, pos0, ntok, nh, nkvh, hd,
                                                              h.rel_extent, win, kscale, kmask[il], att));
            }
            // baseline v4, layers without a window: steps of >= flash_min tokens in one launch (bench_attn card 3, 100K keys
            // x 256 rows: 33.5 -> 23.1 ms against scores + softmax + P.V; 128 rows 17.9 -> 14.9 with <4,3,2>)
            const bool fl = flash && win == 0, fl_tile = fl && tiles && ntok >= flash_min;
            // lean (VAR 1052; bench_attn card 3, 100K keys x 256 rows: 20.46-21.05 -> 20.06-20.12 ms, 5.86-6.21 -> 5.53-5.60
            // J, values the same): Q rows at constant offsets, the exponentials as local block loads, each sub-group the
            // block maximum of its own 3 rows (3 reductions, not 24)
            if (fl_tile && flash_lean)
                pr("attn_flash_full", fz::attn_flash_tile<8, 3, 1, 1052>(d.q, Q, Kc[il], Rc, f32(l.rel_bias), h.n_rel, sinks, Vc[il], kvl[il],
                                                                     pos0, ntok, nh, nkvh, hd, h.rel_extent, kscale, gate, att, kmask[il]));
            else if (fl_tile)
                pr("attn_flash_full", fz::attn_flash_tile<8, 3, 1, 4>(d.q, Q, Kc[il], Rc, f32(l.rel_bias), h.n_rel, sinks, Vc[il], kvl[il], pos0,
                                                                  ntok, nh, nkvh, hd, h.rel_extent, kscale, gate, att, kmask[il]));
            for (int q0 = 0; q0 < (winf || fl_tile ? 0 : ntok); q0 += prow) {
                const int nc = std::min(prow, ntok - q0), qp = pos0 + q0;
                const float *Qc = Q + (size_t)q0 * nh * hd, *gc = gate + (size_t)q0 * nh * hd, *sc = sinks + (size_t)q0 * nh;
                const float *tc = tab + (size_t)q0 * nh * h.rel_extent;
                float *ac = att + (size_t)q0 * nh * hd;
                // prompt tiles of layers without a window (INK_TILE_SM=0 off): the scores also give their maxima per 16
                // keys, the softmax keeps exponentials and 1 / total, P.V multiplies as it reads: P is read and written
                // twice instead of five times (the same values as the normalizing softmax)
                const bool tsm = tiles && tile_sm && win == 0;
                // prompt score tiles: 4 sub-groups per work-group for layers without a window, 8 for the windowed ones
                // (bench_attn card 3: full 100K x 64 3,323 -> 3,209 us, 3K x 512 856 -> 818; windowed 464 vs 558 with 4)
                // layers without a window, steps below the fused tile: scores inside attn_flash_dec (the relative-bias
                // table when the step has no tiles, else Rc and rel_bias as attn_flash_tile)
                const bool fdec = fl && flash_dec;
                if (fdec) {
                } else if (tiles && win == 0)
                    pr("attn_scores_full", fz::attn_scores_tile<8, 3, 4>(d.q, Qc, Kc[il], Rc + (size_t)q0 * nh * h.n_rel, f32(l.rel_bias),
                                                                        h.n_rel, qp, nc, nh, nkvh, hd, h.rel_extent, win, kscale, P, ldp,
                                                                        kmask[il], tsm ? wmax : nullptr, nsgmax));
                else if (tiles)
                    pr(swa ? "attn_scores" : "attn_scores_full", fz::attn_scores_tile<8, 3, 8>(d.q, Qc, Kc[il], Rc + (size_t)q0 * nh * h.n_rel,
                                                                                             f32(l.rel_bias), h.n_rel, qp, nc, nh, nkvh, hd,
                                                                                             h.rel_extent, win, kscale, P, ldp, kmask[il],
                                                                                             tsm ? wmax : nullptr, nsgmax));
                else if (share && win == 0 && q0 == 0 && nc == ntok)
                    pr("attn_scores_full", fz::attn_scores_gt<3, 4>(d.q, Qc, Kc[il], tc, qp, nc, nh, nkvh, hd, h.rel_extent, kscale, P, ldp,
                                                                    wmax, nsgmax, kmask[il]));
                else if (fast)
                    pr(swa ? "attn_scores" : "attn_scores_full", fz::attn_scores_g<3>(d.q, Qc, Kc[il], tc, qp, nc, nh, nkvh, hd, h.rel_extent,
                                                                                      win, kscale, P, ldp, wmax, nsgmax, kmask[il]));
                else
                    pr(swa ? "attn_scores" : "attn_scores_full", fz::attn_scores(d.q, Qc, Kc[il], tc, qp, nc, nh, nkvh, hd, h.rel_extent, win,
                                                                                 kscale, P, ldp, kmask[il]));
                const bool pex = tsm && pv_exp;
                if (fl) { // baseline v4: block parts (maximum, sum, P.V) then the blocks folded in order, 16 or pv_rows rows at a time
                    const int pst = fdec ? dec_rows : tiles ? pv_rows : 16;
                    for (int c0 = 0; c0 < nc; c0 += pst) {
                        const int nt = std::min(pst, nc - c0), p0 = qp + c0, nblk = (p0 + nt - 1) / fz::PVB + 1;
                        const float *Pc = P + (size_t)c0 * nh * ldp;
                        const float *Qd = Qc + (size_t)c0 * nh * hd, *td = tiles ? nullptr : tc + (size_t)c0 * nh * h.rel_extent;
                        const float *Rd = Rc + (size_t)(q0 + c0) * nh * h.n_rel;
                        if (fdec && nt == 1)
                            pr("attn_pv_full", fz::attn_flash_dec<3, 1>(d.q, Qd, Kc[il], td, Rd, f32(l.rel_bias), h.n_rel, Vc[il], kvl[il], p0, nt,
                                                                       nh, nkvh, hd, h.rel_extent, kscale, pvpart, pml, nblk, kmask[il]));
                        else if (fdec && nt <= 4) // (VAR 1: each key's exponentials computed once, the same values)
                            pr("attn_pv_full", fz::attn_flash_dec<3, 4, 1>(d.q, Qd, Kc[il], td, Rd, f32(l.rel_bias), h.n_rel, Vc[il], kvl[il], p0,
                                                                          nt, nh, nkvh, hd, h.rel_extent, kscale, pvpart, pml, nblk, kmask[il]));
                        else if (fdec)
                            pr("attn_pv_full", fz::attn_flash_dec<3, 8, 1>(d.q, Qd, Kc[il], td, Rd, f32(l.rel_bias), h.n_rel, Vc[il], kvl[il], p0,
                                                                          nt, nh, nkvh, hd, h.rel_extent, kscale, pvpart, pml, nblk, kmask[il]));
                        else if (nt == 1) pr("attn_pv_full", fz::attn_flash_part<3, 1>(d.q, Pc, ldp, Vc[il], kvl[il], p0, nt, nh, nkvh, hd, pvpart, pml,
                                                                                nblk, kmask[il]));
                        else pr("attn_pv_full", fz::attn_flash_part<3, 4>(d.q, Pc, ldp, Vc[il], kvl[il], p0, nt, nh, nkvh, hd, pvpart, pml, nblk,
                                                                        kmask[il]));
                        pr("attn_pv_sum_full", fz::attn_flash_sum(d.q, pvpart, pml, nblk, p0, nt, nh, hd, sc + (size_t)c0 * nh,
                                                                  gc + (size_t)c0 * nh * hd, ac + (size_t)c0 * nh * hd));
                    }
                    continue;
                }
                if (fast || tsm) pr(swa ? "attn_softmax" : "attn_softmax_full", fz::attn_softmax_sum(d.q, sc, wmax, nsgmax, qp, nc, nh, win, P, ldp, pinv,
                                                                                                   pex ? pmaxb : nullptr));
                else pr(swa ? "attn_softmax" : "attn_softmax_full", fz::attn_softmax_norm(d.q, sc, qp, nc, nh, win, P, ldp));
                // P.V in the block order (fused.hpp attn_pv_bo_part): the tiles for chunks of >= 64 tokens (but past 32K keys
                // only from 128, bench_attn 100K x 64 tokens: tiles 6.4 ms, split by blocks 4.6); else 16 tokens at a time,
                // through the tiles split by key blocks (prompt steps; 100K x 16: 6.6 -> 1.4 ms) or the block kernels
                // (writing steps), then the blocks' sum
                if (tiles && nc >= 64 && (nc >= 128 || win > 0 || qp + nc <= 32768)) {
                    // 4 queries x 3 heads per work-group, 2 channels per lane (bench_attn card 3, the same bits: 31K x 176
                    // 5,530 -> 3,273 us, 3K x 512 1,132 -> 802, windowed 31K x 512 497 -> 355)
                    // pv_exp: the 4 sub-groups share the exponentials (each computes 3 of the 12 rows; bench_attn BENCH_PVEX card 3,
                    // softmax + P.V at 100K x 256 rows 21,239 -> 16,058 us, 31K 6,578 -> 4,883; the same bits)
                    if (pex)
                        pr("attn_pv_full", fz::attn_pv_tile_xs<4, 3, 2>(d.q, P, ldp, Vc[il], kvl[il], qp, nc, nh, nkvh, hd, win, gc, ac, kmask[il],
                                                                        pinv, pmaxb));
                    else
                        pr(swa ? "attn_pv" : "attn_pv_full", fz::attn_pv_tile<4, 3, 2>(d.q, P, ldp, Vc[il], kvl[il], qp, nc, nh, nkvh, hd, win, gc,
                                                                                       ac, kmask[il], tsm ? pinv : nullptr));
                    continue;
                }
                const int pstep = tiles ? pv_rows : 16;
                for (int c0 = 0; c0 < nc; c0 += pstep) {
                    const int nt = std::min(pstep, nc - c0), p0 = qp + c0;
                    const int lo0 = win > 0 ? std::max(0, p0 - win + 1) : 0, nblk = (p0 + nt - 1) / fz::PVB - lo0 / fz::PVB + 1;
                    if (tiles && pex)
                        pr("attn_pv_full", fz::attn_pv_tile_part<4, 3, 4, true>(d.q, P + (size_t)c0 * nh * ldp, ldp, Vc[il], kvl[il], p0, nt, nh,
                                                                                nkvh, hd, win, pvpart, nblk, kmask[il], pinv + (size_t)c0 * nh,
                                                                                pmaxb + (size_t)c0 * nh));
                    else if (tiles)
                        // 4 channels per lane (100K x 16: 1,687 -> 1,474 us, the same bits); pv_rows rows per launch (100K: 48
                        // rows in one launch 4 x 1,474 -> 4,870 us per 64 rows)
                        pr(swa ? "attn_pv" : "attn_pv_full", fz::attn_pv_tile_part<4, 3, 4>(d.q, P + (size_t)c0 * nh * ldp, ldp, Vc[il], kvl[il],
                                                                                          p0, nt, nh, nkvh, hd, win, pvpart, nblk, kmask[il],
                                                                                          tsm ? pinv + (size_t)c0 * nh : nullptr));
                    else if (share && nt >= 2 && win == 0) // windowed: too few blocks per launch (31K checks 15 -> 29 us)
                        pr(swa ? "attn_pv" : "attn_pv_full", fz::attn_pv_bo_part_t<3, 4>(d.q, P + (size_t)c0 * nh * ldp, ldp, Vc[il], kvl[il], p0,
                                                                                       nt, nh, nkvh, hd, win, pvpart, nblk,
                                                                                       pinv + (size_t)c0 * nh, kmask[il]));
                    else
                        pr(swa ? "attn_pv" : "attn_pv_full", fz::attn_pv_bo_part<3>(d.q, P + (size_t)c0 * nh * ldp, ldp, Vc[il], kvl[il], p0,
                                                                                  nt, nh, nkvh, hd, win, pvpart, nblk, fast ? pinv : nullptr,
                                                                                  kmask[il]));
                    pr(swa ? "attn_pv_sum" : "attn_pv_sum_full", fz::attn_pv_bo_sum(d.q, pvpart, nblk, p0, nt, nh, hd, win,
                                                                                    gc + (size_t)c0 * nh * hd, ac + (size_t)c0 * nh * hd));
                }
            }
            // wo, post conv (inkling2.cpp:595-597), then block start or residual (inkling2.cpp:600-605)
            mm(l.wo, att, ob, ntok);
            const bool bstart = ip % h.res_block == 0;
            pr("attn_tail", fz::attn_tail(d.q, ob, st_in, st_out, 2 * kd, f32(l.attn_post_conv), fz::conv_scale(false),
                                          attn_out, bstart ? nullptr : inpSA, ffn_inp, E, ntok, st_tok, sst));
            const float *fi;
            if (bstart) { blocks.push_back(inpSA); fi = attn_out; }
            else {
                dump.put(d, nm("attn_out", il), attn_out, E, ntok);
                fi = ffn_inp;
            }
            dump.put(d, nm("ffn_inp", il), fi, E, ntok);
            // MoE (inkling2.cpp:609-634)
            // one token: the norm writes the input only in lane order (fxl), which the router and gate|up read
            float *fxl1 = ntok == 1 && xl_on ? fxl : nullptr;
            // 2-8 tokens: the norm writes the input in lane order too (fxls), for the small-step expert kernels
            const bool sbm = sb_on && sb_moe && ntok >= 2 && ntok <= SB_MAX;
            float *fyl = fxl1 ? fxl1 : (sbm ? fxls : nullptr);
            if (mg[3]) {
                mix(blocks, fi, f32(l.ffn_res_query), 1, fx, E, qi_ffn.empty() ? -1 : qi_ffn[ip]);
                static constexpr int m3[1] = {3};
                const float *fx1[1] = {fx}, *mg3[1] = {mg[3]};
                float *cy1[1] = {ctl_y};
                if (!(ntok > 1 && ctl_batch && control_multi(1, m3, fx1, mg3, cy1, l))) control(fx, mg[3], l, 3, ctl_y);
                dump.put(d, nm("loop_ffn_inp", il), ctl_y, E, ntok);
                pr("rms_norm", ops::rms_norm(d.q, ctl_y, fxl1 ? nullptr : fx, f32(l.ffn_norm), E, ntok, h.eps, -1, -1, fyl));
            } else {
                fz::NormOut no{};
                no.y[0] = fxl1 ? nullptr : fx; no.w[0] = f32(l.ffn_norm); no.yl[0] = fyl;
                mix_norm(blocks, fi, f32(l.ffn_res_query), 1, no, E, qi_ffn.empty() ? -1 : qi_ffn[ip]);
            }
            if (fxl1) pr(wlabel(l.gate_inp), gemv_v(d.q, l.gate_inp.view(), fxl1, E, rlog, (int)l.gate_inp.t->rows(), 1, tune(l.gate_inp), true));
            else mm(l.gate_inp, fx, rlog, ntok);
            const int K = ntok * h.n_used;
            pr("moe_route", (route_sg ? ops::moe_route_sg : ops::moe_route)(d.q, rlog, f32(l.exp_probs_b), h.n_expert, h.n_used,
                                                                              h.expert_scale, eids, wts, ntok));
            if (route_stats && ntok > 1) { // INK_ROUTE_STATS=1: distinct experts of the step's tokens per layer (stderr)
                std::vector<int32_t> hv(K);
                d.q.wait();
                d.get(hv.data(), eids, K);
                std::sort(hv.begin(), hv.end());
                std::fprintf(stderr, "[route] ntok %d app %d distinct %ld\n", ntok, il, (long)(std::unique(hv.begin(), hv.end()) - hv.begin()));
            }
            {   // gate and up rows of each chosen expert in one sub-group, then SITU (gate rows 0..nff-1, up nff..2nff-1)
                const W &gw = l.gate_up;
                const SituOp so{f32(l.gate_up_s), eids, h.situ_beta, h.situ_linear_beta, hb, h.n_ff};
                const WView &gv = gu_dec[ip], &dv = dn_dec[ip];
                const size_t gs = gv.rb * (size_t)gw.t->ne[1];
                if (ntok == 1 && xl_on) { // SITU writes the down product's inputs in lane order (gemv2.hpp xlane_at)
                    SituOp sl = so;
                    sl.ldo = (int)xlane_floats(h.n_ff);
                    pr("moe_gate_up", gemv_pair(d.q, gv, gv.p + (size_t)h.n_ff * gv.rb, gs, h.n_ff, eids, K, fxl, (int)xlane_floats(E),
                                                h.n_used, sl, gu_sgw, true));
                    pr("moe_down", gemv_routed_v(d.q, dv, eids, K, hb, sl.ldo, 1, yk, E, Tune{1, dn_sgw}, true));
                } else if (ntok == 1) {
                    pr("moe_gate_up", gemv_pair(d.q, gv, gv.p + (size_t)h.n_ff * gv.rb, gs, h.n_ff, eids, K, fx, E, h.n_used, so, gu_sgw));
                    pr("moe_down", gemv_routed_v(d.q, dv, eids, K, hb, h.n_ff, 1, yk, E, tune_routed(dv)));
                } else if (sbm) { // 2-8 tokens (5-8: passes of 4 slots): each chosen expert decoded once for its slots, inputs in lane order
                    const int amax = std::min(h.n_expert, K);
                    SituOp sl = so;
                    sl.ldo = (int)xlane_floats(h.n_ff);
                    pr("moe_group", moe_group(d.q, eids, K, h.n_expert, grp));
                    if (gv.kind == K_NVFP4P && sb_np > 0) // several rows per sub-group, 8 values decoded at a time
                        pr("moe_gate_up", grouped_pair_t(d.q, gv, gv.p + (size_t)h.n_ff * gv.rb, gs, h.n_ff, grp, amax, fxls,
                                                         (int)xlane_floats(E), h.n_used, sl, ntok, sb_np, gu_sgw));
                    else
                        pr("moe_gate_up", grouped_pair_s(d.q, gv, gv.p + (size_t)h.n_ff * gv.rb, gs, h.n_ff, grp, amax, fxls,
                                                         (int)xlane_floats(E), h.n_used, sl, ntok, gu_sgw));
                    if (dv.kind == K_NVFP4P && sb_dr > 0)
                        pr("moe_down", grouped_rows_t(d.q, dv, grp, amax, hb, sl.ldo, yk, E, ntok, sb_dr, dn_sgw));
                    else
                        pr("moe_down", grouped_rows_s(d.q, dv, grp, amax, hb, sl.ldo, yk, E, ntok, dn_sgw));
                } else if (ntok >= tile_min && Xt) {
                    // many tokens: tiles of 16 slots of one expert, one slot per lane, weights decoded once per tile
                    // (tok_tiles.hpp, any expert format; bench_moe 512 tokens: NVFP4 gate|up 18.7 -> 8.8 ms, down
                    // 10.4 -> 4.3; layers 20-23 on their decode copies (the only copy when ink_run skips the file
                    // layout) gate|up 25-42 -> 8.2-8.9, down 17-19 -> 3.9-4.1)
                    const int tiles = MoeGroups::max_tiles(h.n_expert, K);
                    pr("moe_group", moe_group(d.q, eids, K, h.n_expert, grp));
                    pr("moe_tiles", tile_gather(d.q, grp, tiles, fx, E, h.n_used, E, Xt));
                    // NVFP4 (INK_TILE_V2, default on; the same values): 32 sub-groups per work-group (tile_sgw2), so the
                    // lookup tables are filled once per 32 sub-groups; gate|up 4 rows and down 4 rows (through the tables
                    // too) per sub-group, two tiles one after another (bench_moe 1,024 tokens, card 3: gate|up 11,730 ->
                    // 7,594 us, down 6,448 -> 3,989; 512 tokens 6,369 -> 4,194 and 3,526 -> 2,195)
                    if (tile_v2 && gv.kind == K_NVFP4P && tile_lut)
                        pr("moe_gate_up", slot_pair_g2(d.q, gv, gv.p + (size_t)h.n_ff * gv.rb, gs, h.n_ff, grp, tiles, Xt, so, Ht, 2, false, false));
                    else
                        pr("moe_gate_up", slot_pair_g(d.q, gv, gv.p + (size_t)h.n_ff * gv.rb, gs, h.n_ff, grp, tiles, Xt, so, Ht, 2));
                    if (tile_v2 && dv.kind == K_NVFP4P)
                        pr("moe_down", slot_rows_g2(d.q, dv, grp, tiles, Ht, yk, E, 4, false, false, tile_lut));
                    else pr("moe_down", slot_rows_g(d.q, dv, grp, tiles, Ht, yk, E, 2));
                } else { // several tokens: each chosen expert decoded once per 8 slots
                    const int amax = std::min(h.n_expert, K);
                    pr("moe_group", moe_group(d.q, eids, K, h.n_expert, grp));
                    pr("moe_gate_up", grouped_pair(d.q, gv, gv.p + (size_t)h.n_ff * gv.rb, gs, h.n_ff, grp, amax, fx, E, h.n_used, so, 2));
                    pr("moe_down", grouped_rows(d.q, dv, grp, amax, hb, h.n_ff, yk, E, 2));
                }
            }
            float *lo = lbuf[il + 1];
            pr("ffn_tail", fz::ffn_tail(d.q, yk, f32(l.down_s), eids, wts, h.n_used, st_in, st_out, 2 * kd + E,
                                        f32(l.ffn_post_conv), fz::conv_scale(false), ffn_out, fi, lo, E, ntok, st_tok, sst));
            dump.put(d, nm("ffn_out", il), ffn_out, E, ntok);
            dump.put(d, nm("l_out", il), lo, E, ntok);
            cur = lo;
        }
        // output (inkling2.cpp:643-669); steps of 1-4 tokens: lane-order rows for the output kernels (bench_gemv card 3:
        // one row 676 -> 655 us, 3 rows multi_m 777 us, the interleaved blocks took ~1290 in the engine at 4)
        const bool ol = out_lane && ntok <= SB_MAX && multi_ok(m.output.view());
        {
            fz::NormOut no{};
            no.y[0] = fin; no.w[0] = f32(m.output_norm);
            if (ol) no.yl[0] = finl;
            mix_norm(blocks, cur, f32(m.output_res_query), 1, no, E, qi_out);
        }
        dump.put(d, "result_norm", fin, E, ntok);
        const int nl = all_logits ? ntok : 1;
        const float *xl = all_logits ? fin : fin + (size_t)(ntok - 1) * E;
        if (ol) {
            const int lx = (int)xlane_floats(E);
            const float *x1 = finl + (all_logits ? 0 : (size_t)(ntok - 1) * lx);
            if (nl == 1) pr(wlabel(m.output), gemv_v(d.q, m.output.view(), x1, lx, lg, h.vocab_padded, 1, Tune{1, 1}, true));
            else {
                MultiJobs mj;
                multi_add(mj, m.output.view(), x1, lg, 1, lx, h.vocab_padded);
                pr(wlabel(m.output), gemv_multi_m(d.q, mj, nl, true, 1));
            }
        } else
            mm(m.output, xl, lg, nl);
        pr("softcap", ops::softcap(d.q, lg, (size_t)nl * h.vocab_padded, h.softcap));
        if (feat) d.q.memcpy(feat + (size_t)3 * T * E, fin, sizeof(float) * (size_t)ntok * E);
        if (on_step) on_step(pos0, ntok);
        n_logit_rows = nl;
        if (!host_logits && !dump.want("result_output")) {
            n_past += ntok;
            cpar ^= 1;
            return;
        }
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
        cpar ^= 1;
    }

    // feed tokens (any number) in steps of T; returns the logits of the last token (or of every token of the last
    // step when all_logits)
    const std::vector<float> &feed(const std::vector<int32_t> &tok) {
        for (size_t p = 0; p < tok.size(); p += T) step(tok.data() + p, (int)std::min<size_t>(T, tok.size() - p));
        return logits;
    }
    // greedy choice on the card from the last step's last logits row (the first index of the largest value, as
    // argmax_last()); it becomes ids[0] for step(nullptr, 1) and is returned to the host
    int next_token() {
        const float *row = lg + (size_t)(n_logit_rows - 1) * m.hp.vocab_padded;
        pr("argmax", ops::argmax_rows2(d.q, row, m.hp.vocab_padded, m.hp.vocab, 1, ids, amx_v, amx_i));
        int32_t v;
        d.get(&v, ids, 1);
        last_tok = v;
        return v;
    }
    void step_next() { step(nullptr, 1); }
    // checking guesses: one step of tok[0..n) (the last chosen token, then n - 1 guesses; n <= SB_MAX) that scores
    // every row and keeps every token's convolution states. Returns the greedy choice after each token (row i: the
    // token that follows tok[i]); steps of 1-8 tokens give each row the one-token values, so the choices are the
    // one-token text's. Then accept(a).
    std::vector<int32_t> check(const int32_t *tok, int n) {
        if (n < 1 || n > SB_MAX || n > T) throw std::runtime_error("check: 1 to " + std::to_string(SB_MAX) + " tokens");
        const bool al = all_logits, hl = host_logits;
        all_logits = true; host_logits = false; keep_states = true;
        step(tok, n);
        all_logits = al; host_logits = hl; keep_states = false;
        pr("argmax", ops::argmax_rows2(d.q, lg, m.hp.vocab_padded, m.hp.vocab, n, cids, amx_v, amx_i));
        std::vector<int32_t> r(n);
        d.get(r.data(), cids, n);
        chk_n = n;
        return r;
    }
    // keep the first a tokens of the last check (1 <= a <= n): the next step writes the later positions again, and
    // the convolution states become those after token a - 1
    void accept(int a) {
        if (a < 1 || a > chk_n) throw std::runtime_error("accept: 1 to " + std::to_string(chk_n) + " tokens");
        if (a < chk_n) {
            n_past -= chk_n - a;
            const size_t ns = (size_t)m.hp.n_app * conv_n;
            d.q.memcpy(conv + (size_t)cpar * ns, cst + (size_t)(a - 1) * ns, sizeof(float) * ns);
        }
        chk_n = 0;
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
