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
#include "xmx_moe.hpp"
#include "xmx_esimd.hpp"
#include "xmx_q.hpp"
#include <unordered_map>
#include <set>
#include <array>
#include <condition_variable>
#include <exception>
#include <mutex>
#include <thread>
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
    // the applications this engine runs: a0 .. a1 - 1 of the 48 (one engine: all of them). A split over two engines
    // (tools/ink_pipe.cpp): the first ends at a1 < 48 and has no output; the second starts at a0 > 0 and takes the rows
    // it reads from the first's applications through carry_out() / carry_in(). Every application computes what it
    // computes in one engine, so the logits are the same bits
    int a0 = 0, a1 = 0;
    bool split() const { return a0 > 0 || a1 < m.hp.n_app; }
    // a split in one driver (ink_run INK_SPLIT): the second engine's step() runs the first one's (prev) and takes its
    // rows first, its accept() and reset() the first one's too; the driver uses the second engine only. pull = false:
    // the caller moves the rows itself (feed's pipeline on two cards)
    Engine *prev = nullptr;
    bool pull = true;
    // cache sharing (INK_SHARD=<S>, a chain of two engines; notes/2026-11-26-two-card-1m-plan.md): positions 0 .. S - 1 of
    // every full-context application are also held by the other engine (shard_Kp / shard_Vp there, keys [S][kd], values
    // transposed [kd][S]), which reads those blocks for a writing step's rows and folds them into the attention state
    // (attn_flash_sum to = 1); the owner folds its blocks from S on from that state. The same values: blocks of 128 keys
    // folded in order, the state carried at a boundary of 128-block groups (S a multiple of 16,384), as the chunked fold
    // at long contexts. Only rows at S + rel_extent or later (no bias term on the other engine's keys)
    Engine *next = nullptr;
    int shard_S = 0;
    std::vector<sycl::half *> shard_Kp, shard_Vp;
    float *shard_q = nullptr, *shard_sink = nullptr;
    std::vector<float> shard_h; // (rows on their way between two cards)
    Engine *partner() const { return next ? next : prev; }
    std::vector<float> chost; // (the rows on their way, host memory)
    // the physical layers applications lo .. hi - 1 run
    static std::vector<bool> layers_of(const HParams &h, int lo, int hi) {
        std::vector<bool> r(h.n_phys, false);
        for (int il = lo; il < hi; ++il) r[h.phys(il)] = true;
        return r;
    }
    // a tensor the engine for applications lo .. hi - 1 leaves off the card: those of the physical layers it does not
    // run (but their mix query rows: a block's saved mix scores, mix_tab, cover every query of the model), the output
    // matrix when it ends early, the token embedding when it starts late
    static bool unused_tensor(const HParams &h, int lo, int hi, const Tensor &t) {
        if (hi < h.n_app && t.name == "output.weight") return true;
        if (lo > 0 && t.name == "token_embd.weight") return true;
        if (t.name.compare(0, 4, "blk.") != 0 || (lo == 0 && hi == h.n_app)) return false;
        const int ip = std::atoi(t.name.c_str() + 4);
        const auto need = layers_of(h, lo, hi);
        if (ip < 0 || ip >= h.n_phys || need[ip]) return false;
        return t.name.find("_res_query.") == std::string::npos;
    }
    // the lbuf slots applications a .. 47 and the output read from applications 0 .. a - 1: the block bookkeeping of
    // step() replayed (blocks, the prelude's, the previous pass's bank, the current rows)
    static std::vector<int> carry_slots(const HParams &h, int a) {
        std::vector<int> blocks, pre, bank;
        int cur = 0, pcur = -1, blast = -1;
        const int nloop = h.passes > 1 ? h.loop_len() : 0;
        for (int il = 0; il < a; ++il) {
            const int ip = h.phys(il);
            if (nloop > 0 && ip == h.core_start) {
                if ((il - h.core_start) / nloop == 0) { pre = blocks; pcur = cur; }
                else {
                    bank.assign(blocks.begin() + pre.size() + 1, blocks.end());
                    blast = cur;
                    blocks = pre;
                    cur = pcur;
                }
            }
            if (ip % h.res_block == 0) blocks.push_back(cur);
            cur = il + 1;
        }
        std::set<int> s(blocks.begin(), blocks.end());
        s.insert(pre.begin(), pre.end());
        s.insert(bank.begin(), bank.end());
        for (int k : {cur, pcur, blast}) if (k >= 0) s.insert(k);
        return std::vector<int>(s.begin(), s.end());
    }

    // persistent state
    std::vector<sycl::half *> Kc, Vc; // per application [cap][n_kv_head*head_dim]; Vc transposed when vld > 0
    int vld = 0;                      // V cache [n_kv_head*head_dim][vld] (INK_VT=0: [cap][n_kv_head*head_dim])
    static constexpr int PVB_RING_MIN = 128;
    int ring_w = 0;                   // windowed applications' ring size (positions)
    std::vector<int> kvl, kmask;      // per application: V cache stride, cache slot mask
    float *conv = nullptr;            // two copies (previous call, this call) of [n_app][6656*3], channel-major
    int conv_n = 0;                   // floats per application
    int cpar = 0;                     // which copy holds the state of the previous call
    // several sequences on one card (INK_SEQS, at most SB_MAX): the members above (Kc, Vc, conv, cpar) with n_past,
    // last_tok, samp and samp_seed are the bound sequence's; seqs[s] holds sequence s's while another is bound (bind()).
    // step_rows() runs one token of each of several sequences in one step (notes in README: several conversations)
    struct SeqState {
        std::vector<sycl::half *> Kc, Vc;
        float *conv = nullptr;
        int cpar = 0, n_past = 0;
        int32_t last_tok = -1;
        ops::SampleArgs samp;
        uint64_t samp_seed = 0;
    };
    std::vector<SeqState> seqs;
    int bound = 0;
    fz::SeqRow *mrow_dev = nullptr;   // step_rows: [n_app][rows] on the card
    std::vector<fz::SeqRow> mrow_host;
    bool mrows = false;               // the step's rows are of different sequences (mrow_host / mrow_dev)
    bool mr_batch = !std::getenv("INK_MR_BATCH") || std::atoi(std::getenv("INK_MR_BATCH")); // their attention in one launch
    // per-step buffers
    int32_t *ids = nullptr;
    std::vector<float *> lbuf;        // lbuf[0] = normed embedding, lbuf[il+1] = l_out of application il
    float *mixb = nullptr, *inp[3] = {}, *msg[4] = {}, *mm2[2] = {};
    float *Q = nullptr, *Kr = nullptr, *Vr = nullptr, *Kx = nullptr, *Vx = nullptr, *dynK = nullptr, *dynV = nullptr;
    float *R = nullptr, *Rc = nullptr, *sinks = nullptr, *tab = nullptr, *P = nullptr, *att = nullptr, *gate = nullptr;
    float *ob = nullptr, *attn_out = nullptr, *ffn_inp = nullptr, *fx = nullptr, *ctl_h = nullptr, *ctl_z = nullptr;
    float *ctl_g = nullptr, *ctl_f = nullptr, *ctl_y = nullptr, *rlog = nullptr, *wts = nullptr;
    float *hb = nullptr, *yk = nullptr, *moe = nullptr, *ffn_out = nullptr, *tau = nullptr, *fin = nullptr, *lg = nullptr;
    int32_t *eids = nullptr;
    int ldp = 0;
    size_t p_floats = 0; // P's size (the score rows, or attn_win_tile's slices if more)
    int prow = 0; // score rows (tokens) P holds; a step's attention runs in chunks of prow tokens
    float *mix_inv = nullptr, *mix_sc = nullptr;
    // the loop mixes of a whole pass at its start (their states are fixed for the pass): INK_LOOP_PRE=0 one per layer
    bool loop_pre = true;
    // steps of up to this many tokens compute the pass's loop mixes in two launches (writing steps and checks: fewer
    // launches); longer steps mix per layer into mm2 (the same values), so lmix_out holds 48 x lp_tok tokens, not 48 x T
    // (216 MiB at 512-token steps; INK_LOOP_PRE_TOK)
    int lp_tok = 16;
    // longer steps: the pass's loop mix scores still in one launch at its start (mix_scores_many: the bank is read once
    // for all 48 queries instead of once per layer call; the same scores), each layer's outputs from them
    // (ops::mix_out with the table's stride); INK_LOOP_SC=0: mix() per layer call (before)
    bool loop_sc = true;
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
    int dec_rows = 16;     // rows per attn_flash_dec launch, i.e. per read of the keys and values
    int dec_mem = 16;      // rows of the whole context the parts buffer holds (more rows go through it in chunks)
    size_t dec_cap = 0;    // the parts buffer's (row, block) entries per head
    float *fst = nullptr;  // the fold's state between chunks (dec_rows x heads x (head_dim + 2))
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
    // INK_XMX (default on; 0 = off): the NVFP4 layers' experts on the matrix engines with exact products for every step size (xmx_moe.hpp,
    // README "Matrix engines with exact products"): inputs in parts (xP), activations in parts (xHp, Xt / Ht share
    // their memory), segment sums of steps of 1-8 tokens (xS), super-tiles (xst), the one-token tiles (x1)
    bool xmx = true;
    uint16_t *xP = nullptr, *xHp = nullptr;
    float *xS = nullptr;
    size_t xpp = 0, xhpp = 0; // part strides of xP / xHp for steps of 1-8 tokens (rows by sorted position + 8)
    // prompt steps' expert products in passes of up to xch tokens (default T; INK_XMX_CHUNK=<tokens>): a row's products do
    // not depend on the other rows of its tile, so the same bits (passes of 256 in steps of 512: 1,095 -> 888 tok/s)
    int xch = 0;
    size_t xnp = 0, xnh = 0; // xP / xHp sizes (uint16 values); both live in P's memory (see the P allocation)
    xm::Super xst;
    MoeGroups x1;
    int tile_bound = 0;
    int tile_min = 128;        // steps of at least this many tokens use the token-parallel kernels (INK_TILE_MIN)
    float *Xd = nullptr;       // transposed tiles of the dense token-parallel kernels (tok_tiles.hpp)
    // INK_XD_KEEP (default 1): products of one input in a row gather it into Xd once (the attention inputs of a prompt
    // step: 8 products of 3 inputs, or of 1 in the windowed layers); xd_src is the input Xd holds while xd_keep is set
    // Q6_KU prompt copies of the dense Q6_K matrices (not the output layer), read only by the prompt tiles: the codes
    // as bytes and the 16-value scales as floats, so a lane decodes them like Q8_0 (INK_Q6KU=0 off; none past
    // INK_Q6KU_CAP positions, default 500,000: ~97 MB)
    std::map<const Tensor *, WView> q6u;
    bool xd_keep_on = true, xd_keep = false;
    const float *xd_src = nullptr; int xd_n = 0, xd_cols = 0;
    // xdense (default since 2026-11-26, baseline v6; INK_XMX_DENSE=0: the FP32 kernels, baseline v5): the Q8_0 attention
    // matrices (q, k, v, gate, rel, output) and the bf16 ones (sink, k / v conv projections) on the matrix engines with
    // exact products, the same arithmetic for every step size (README "Q8_0 attention matrices on the matrix engines"):
    // the Q8_0 weights rewritten in place at load into the Q8E layout (kind K_Q8_0E), the bf16 ones copied into BFE
    // (K_BF16E), both read only by these kernels; steps of 9+ tokens: xd::dense on the input parts xdP (in P's memory:
    // no score is live during these products); 1-8: the ESIMD kernels (xd::dgroupej), one token on the fp32 input
    // (split inside), 2-8 on parts in xdPe (4 slots: the three attention inputs and one for mm).
    // xe_keep: the attention inputs of a prompt step are split once each
    static constexpr int XE_COLS = 3072;
    bool xdense = false;
    // xq6 (with xdense; default since 2026-11-26, baseline v7; INK_XMX_Q6=0: the FP32 kernels, baseline v6): the Q6_K
    // attention matrices in the Q6E layout (a float scale per 16 inputs, a chain per step), made at load from their
    // Q6_KU rows; their planar copies are freed and no Q6_KU prompt copy is kept for them
    bool xq6 = false;
    // xq (with xmx; default since 2026-11-26, baseline v8; INK_XMX_Q=0: the FP32 kernels, baseline v7): the experts of layers 20-23 (Q5_K / Q4_K / IQ4_XS gate|up, Q5_0 / IQ4_NL down) on the
    // matrix engines (xmx_q.hpp, K_XQ: their decode copies in the XQ layout, in place); xqX: block sums of the inputs by
    // token (Q4_K / Q5_K), xqXG: by tile for the prompt kernel
    bool xq = false;
    float *xqX = nullptr, *xqXG = nullptr;
    static bool q6e_fits(const W &w) {
        return w && w.kind == K_Q6_KP && w.t->ne[0] % 256 == 0 && w.t->ne[0] <= XE_COLS && w.t->rows() % 128 == 0;
    }
    uint16_t *xdP = nullptr, *xdPe = nullptr;
    bool xe_keep = false; const float *xe_src = nullptr; int xe_n = 0, xe_cols = 0;
    size_t xe_slot() const { return (size_t)3 * SB_MAX * XE_COLS; }
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
    // 2-8 tokens, the large register file for the attention inputs and the output layer (multi.hpp GemvMultiM BIG):
    // rows per sub-group INK_MM_R (attention inputs, 5-8 tokens), INK_MM_R4 (2-4 tokens), INK_MM_OUT_R (output layer);
    // INK_MM_BIG=0 = before (the same values)
    int mm_big = 1; // 2: only steps of 5-8 tokens
    int mm_r = 2, mm_r4 = 2, mm_out_r = 2;
    // INK_MM_MULTI=<rows per sub-group>: mm() of 2-8 tokens through gemv_multi_m (one job, plain inputs) for matrices of
    // >= INK_MM_MULTI_MINROWS (256) rows instead of gemv_v's blocks of vectors (0 = before; the same values)
    int mm_multi = 0, mm_multi_minrows = 256;
    // INK_MM_WO=<rows per sub-group>: the attention output product of 2-8 tokens from a lane-order copy of its input
    // (attl, one small relayout launch) through gemv_multi_m (0 = gemv_v's blocks of vectors as before; the same values)
    int mm_wo = 2;
    float *attl = nullptr;
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
           const std::map<std::string, WView> *views = nullptr, int app_lo = 0, int app_hi = -1)
        : d(dev), g(gg), T(ubatch), cap(capacity), all_logits(every_logit) {
        m.bind(g, wt, views);
        const HParams &h = m.hp;
        a0 = app_lo;
        a1 = app_hi < 0 ? h.n_app : app_hi;
        if (a0 < 0 || a1 > h.n_app || a0 >= a1) throw std::runtime_error("engine: applications " + std::to_string(a0) + " to " + std::to_string(a1));
        if (split()) { // the layers it does not run lose their weights (the upload left them off: unused_tensor)
            if (!views) throw std::runtime_error("engine: a split needs the planar layout");
            const auto need = layers_of(h, a0, a1);
            for (int ip = 0; ip < h.n_phys; ++ip) {
                if (need[ip]) continue;
                const W aq = m.L[ip].attn_res_query, fq = m.L[ip].ffn_res_query;
                m.L[ip] = Layer{};
                m.L[ip].attn_res_query = aq;
                m.L[ip].ffn_res_query = fq;
            }
            if (a1 < h.n_app) m.output = W{};
        }
        if (a0 == 0 && !m.tok_embd.p) { // the embedding table stays in host memory (embed())
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
            if (a < a0 || a >= a1) { Kc[a] = Vc[a] = nullptr; continue; } // (the other engine's application)
            Kc[a] = d.alloc<sycl::half>((size_t)(r ? ring_w : cap) * kd);
            Vc[a] = d.alloc<sycl::half>((size_t)(r ? ring_w : (vld ? vld : cap)) * kd);
        }
        conv_n = (2 * kd + 2 * h.n_embd) * (h.n_conv - 1);
        conv = d.alloc_zero<float>((size_t)2 * conv_n * h.n_app);
        {   // the other sequences' state (INK_SEQS), sized as the engine's own, before the buffers that take what is left
            const int ns = std::getenv("INK_SEQS") ? std::max(1, std::atoi(std::getenv("INK_SEQS"))) : 1;
            if (ns > SB_MAX) throw std::runtime_error("engine: INK_SEQS is at most " + std::to_string(SB_MAX));
            if (ns > 1 && split()) throw std::runtime_error("engine: INK_SEQS with a split");
            seqs.resize(ns);
            for (int s = 1; s < ns; ++s) {
                SeqState &q = seqs[s];
                q.Kc.resize(h.n_app); q.Vc.resize(h.n_app);
                for (int a = 0; a < h.n_app; ++a) {
                    const bool r = kmask[a] != 0x7fffffff;
                    q.Kc[a] = d.alloc<sycl::half>((size_t)(r ? ring_w : cap) * kd);
                    q.Vc[a] = d.alloc<sycl::half>((size_t)(r ? ring_w : (vld ? vld : cap)) * kd);
                }
                q.conv = d.alloc_zero<float>((size_t)2 * conv_n * h.n_app);
            }
            if (ns > 1) {
                mrow_dev = d.alloc<fz::SeqRow>((size_t)h.n_app * SB_MAX);
                mrow_host.resize((size_t)h.n_app * SB_MAX);
            }
        }
        ids = d.alloc<int32_t>(T);
        lbuf.assign(h.n_app + 1, nullptr);
        {   // a split's engine: only the rows it writes and the ones it reads from the other engine's applications
            std::vector<bool> use(h.n_app + 1, !split());
            if (split()) {
                for (int k = a0; k <= a1; ++k) use[k] = true;
                for (int k : carry_slots(h, a0)) use[k] = true;
                if (a0 == 0) use[0] = true;
            }
            for (size_t k = 0; k < lbuf.size(); ++k) if (use[k]) lbuf[k] = d.alloc<float>(E);
        }
        mixb = d.alloc<float>(3 * E);
        for (auto &p : inp) p = d.alloc<float>(E);
        for (auto &p : msg) p = d.alloc<float>(E);
        for (auto &p : mm2) p = d.alloc<float>(2 * E);
        Q = d.alloc<float>(QD); att = d.alloc<float>(QD); gate = d.alloc<float>(QD);
        Kr = d.alloc<float>(KD); Vr = d.alloc<float>(KD); Kx = d.alloc<float>(KD); Vx = d.alloc<float>(KD);
        dynK = d.alloc<float>((size_t)T * h.n_head_kv * h.n_conv); dynV = d.alloc<float>((size_t)T * h.n_head_kv * h.n_conv);
        R = d.alloc<float>((size_t)h.n_rel * h.n_head * T); Rc = d.alloc<float>((size_t)h.n_rel * h.n_head * T);
        sinks = d.alloc<float>((size_t)h.n_head * T);
        // the relative-bias table: only steps below the attention tiles (att_tile) write and read it (the tiles compute
        // the bias in place), so it holds att_tile - 1 tokens (at least SB_MAX) when the tiles can run (48 MiB less at
        // 512-token steps)
        if (const char *e = std::getenv("INK_ATT_TILE")) att_tile = std::atoi(e);
        const bool tile_shape = att_tile > 0 && vld > 0 && h.n_head == 3 * h.n_head_kv && h.n_rel == 16;
        const size_t tab_tok = tile_shape ? (size_t)std::min(T, std::max(att_tile - 1, SB_MAX)) : (size_t)T;
        tab = d.alloc<float>((size_t)h.rel_extent * h.n_head * tab_tok);
        if (const char *e = std::getenv("INK_FLASH")) flash = std::atoi(e) != 0;
        if (const char *e = std::getenv("INK_FLASH_MIN")) flash_min = std::atoi(e);
        if (const char *e = std::getenv("INK_FLASH_DEC")) flash_dec = std::atoi(e) != 0;
        if (const char *e = std::getenv("INK_FLASH_LEAN")) flash_lean = std::atoi(e) != 0;
        // long contexts: 8 rows (a check of 5-8 tokens reads the keys and values once; 0.75 KB per position), past 480K
        // positions 4 (0.4 KB; a 5-8 token check takes two launches)
        dec_rows = cap <= 131072 ? 16 : cap <= 491520 ? 8 : 4;
        if (const char *e = std::getenv("INK_DEC_ROWS")) dec_rows = std::max(1, std::min(16, std::atoi(e)));
        // past 491,520 positions the buffer holds one row of the context (INK_DEC_MEM rows; 0.1 KB per position), but a
        // check of 2-8 tokens still reads the keys and values once: it goes through the buffer in chunks of whole
        // 128-block groups, the fold's state carried between them (attn_flash_sum b0 / st), the same values
        // (INK_DEC_CHUNK=0: 4 rows of the context, a 5-8 token check in two launches of 4 rows, as before)
        dec_mem = dec_rows;
        if (dec_rows < 8 && (!std::getenv("INK_DEC_CHUNK") || std::atoi(std::getenv("INK_DEC_CHUNK")))) {
            dec_rows = 8;
            if (!std::getenv("INK_DEC_ROWS")) dec_mem = 1;
            if (const char *e = std::getenv("INK_DEC_MEM")) dec_mem = std::max(1, std::min(8, std::atoi(e)));
        }
        // P's row stride: the window (the windowed kernels store column j - lo of each row) when the layers without a
        // window keep their scores in local memory, else the context (their rows store column j)
        const bool p_win = flash && flash_dec && h.n_swa > 0;
        ldp = p_win ? (h.n_swa + 15) / 16 * 16 : cap;
        xmx = true; // default since 2026-11-25 (baseline v5); INK_XMX=0: the FP32 expert kernels (baseline v4)
        if (const char *e = std::getenv("INK_XMX")) xmx = std::atoi(e) != 0;
        xdense = true; // default since 2026-11-26 (baseline v6); INK_XMX_DENSE=0: the FP32 dense kernels (baseline v5)
        if (const char *e = std::getenv("INK_XMX_DENSE")) xdense = std::atoi(e) != 0;
        xq6 = xdense;
        if (const char *e = std::getenv("INK_XMX_Q6")) xq6 = xdense && std::atoi(e) != 0;
        xq = xmx; // default since 2026-11-26 (baseline v8); INK_XMX_Q=0: the FP32 kernels for layers 20-23's experts (baseline v7)
        if (const char *e = std::getenv("INK_XMX_Q")) xq = xmx && std::atoi(e) != 0;
        if (const char *e = std::getenv("INK_TILE_MIN")) tile_min = std::atoi(e);
        if (xmx) { // the matrix-engine experts' input and activation parts; Xt / Ht (the other experts' tiles, floats) share them
            xch = T;
            if (const char *e = std::getenv("INK_XMX_CHUNK")) xch = std::max(SB_MAX + 1, std::atoi(e));
            const int tx = std::max(std::min(xch, T), SB_MAX), tb = MoeGroups::max_tiles(h.n_expert, tx * h.n_used);
            const size_t tbo = T >= tile_min ? (size_t)MoeGroups::max_tiles(h.n_expert, T * h.n_used) : 0;
            xnp = (std::max((size_t)tb * 3 * MOE_TS * h.n_embd, tbo * MOE_TS * h.n_embd * 2) + 127) / 128 * 128;
            xnh = (std::max((size_t)tb * 3 * MOE_TS * h.n_ff, tbo * MOE_TS * h.n_ff * 2) + 127) / 128 * 128;
        }
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
        p_floats = (size_t)ldp * h.n_head * prow;
        if (h.n_swa > 0 && T >= 16 && fz::win_tile_mt() > 0) { // attn_win_tile's slices: one launch per step
            const int mt = fz::win_tile_mt(), span = (h.n_swa + mt + 14 + 15) / 16 * 16;
            p_floats = std::max(p_floats, (size_t)((T + mt - 1) / mt) * mt * h.n_head * span);
        }
        // P holds the attention scores; the expert part of a layer (after the attention, in the same queue) uses the same
        // memory for xP / xHp when INK_XMX is on (no kernel of one part runs during the other): its size is the larger
        // and so do the dense matrices' input parts (INK_XMX_DENSE; before the scores and after them in each layer)
        // (and INK_XMX_Q's block sums past xP / xHp: no memory of their own when the scores are larger, as at long context)
        size_t xqx = 0, xqg = 0;
        if (xq) {
            const int tx = std::max(std::min(xch, T), SB_MAX);
            xqx = ((size_t)std::max(T, 1) * (h.n_embd / 32) + 63) / 64 * 64;
            xqg = ((size_t)MoeGroups::max_tiles(h.n_expert, tx * h.n_used) * (h.n_embd / 32) * 16 + 63) / 64 * 64;
        }
        P = d.alloc<float>(std::max({p_floats, (xnp + xnh) / 2 + xqx + xqg, xdense ? (size_t)((T + 63) / 64 * 64) * 3 * XE_COLS / 2 : (size_t)0}));
        if (xq) { xqX = P + (xnp + xnh) / 2; xqXG = xqX + xqx; }
        if (xdense) xdP = reinterpret_cast<uint16_t *>(P); // (xdPe and the Q8E / BFE work: last, see the end of the constructor)
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
            // chunked checks: the buffer rounded up to whole pieces of dec_rows rows x 128 blocks, so a check of
            // dec_rows tokens takes ceil(context / piece) pieces (515K, 8 tokens: 8 pieces of 512 blocks, not 11 of 384)
            size_t dm_b = (size_t)dec_mem * ctx_b;
            if (dec_rows > dec_mem) dm_b = (dm_b + (size_t)dec_rows * 128 - 1) / ((size_t)dec_rows * 128) * ((size_t)dec_rows * 128);
            const size_t pr_n = p_win ? std::max(dm_b, r16 * ((ldp + r16) / fz::PVB + 3)) : r16 * ctx_b;
            const size_t ml_n = p_win ? dm_b : r16 * ctx_b;
            pvpart = d.alloc<float>(pr_n * h.n_head * h.head_dim);
            pml = d.alloc<float>(ml_n * h.n_head * 2);
            dec_cap = std::min(pr_n, ml_n);
            if (dec_rows > dec_mem) fst = d.alloc<float>((size_t)dec_rows * h.n_head * (h.head_dim + 2));
        }
        if (vld == 0 || h.n_head != 3 * h.n_head_kv) // the block-order P.V reads the transposed cache, 3 heads per KV head
            throw std::runtime_error("engine: INK_VT=0 and head groups other than 3 are not supported");
        ob = d.alloc<float>(E); attn_out = d.alloc<float>(E); ffn_inp = d.alloc<float>(E); fx = d.alloc<float>(E);
        ctl_h = d.alloc<float>(2 * E); ctl_z = d.alloc<float>((size_t)h.gate_rank * T);
        ctl_g = d.alloc<float>(E); ctl_f = d.alloc<float>(E); ctl_y = d.alloc<float>(E);
        rlog = d.alloc<float>((size_t)h.n_expert * T);
        eids = d.alloc<int32_t>((size_t)h.n_used * T); wts = d.alloc<float>((size_t)h.n_used * T);
        // the SITU outputs of steps below the expert tiles (the tiles keep theirs in Ht): tile_min - 1 tokens (at least
        // SB_MAX) when the tiles can run (18 MiB less at 512-token steps)
        if (const char *e = std::getenv("INK_TILE_MIN")) tile_min = std::atoi(e);
        const size_t hb_tok = T >= tile_min ? (size_t)std::min(T, std::max(tile_min - 1, SB_MAX)) : (size_t)T;
        hb = d.alloc<float>((size_t)h.n_used * hb_tok * std::max((size_t)h.n_ff, xlane_floats(h.n_ff)));
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
        if (xmx) {
            const int tx = std::max(std::min(xch, T), SB_MAX);
            const size_t np = xnp;
            xP = reinterpret_cast<uint16_t *>(P);
            xHp = xP + xnp;
            const int km = SB_MAX * h.n_used, ngu = (h.n_embd / 16 + xm::SEG - 1) / xm::SEG, ndn = (h.n_ff / 16 + xm::SEG - 1) / xm::SEG;
            xpp = (size_t)(km + 8) * h.n_embd; xhpp = (size_t)(km + 8) * h.n_ff;
            // the segment sums (steps of 2-8 tokens) in xP past those steps' input parts, which leave the rest unused
            const size_t nsf = std::max((size_t)km * ngu * SB_MAX * 2 * h.n_ff, (size_t)km * ndn * SB_MAX * h.n_embd);
            const size_t soff = (3 * xpp + 127) / 128 * 128;
            xS = np > soff && (np - soff) * 2 >= nsf * 4 ? reinterpret_cast<float *>(xP + soff) : d.alloc<float>(nsf);
            grp.sloc = d.alloc<int32_t>((size_t)T * h.n_used);
            xst.alloc(d, h.n_expert, tx * h.n_used, 4);
            std::vector<int32_t> iota(h.n_used), ones(h.n_used, 1), loc(h.n_used);
            for (int i = 0; i < h.n_used; ++i) { iota[i] = i; loc[i] = i << 4; }
            x1.slots = d.alloc<int32_t>(h.n_used); x1.tile_s0 = d.alloc<int32_t>(h.n_used); x1.tile_n = d.alloc<int32_t>(h.n_used);
            x1.ntiles = d.alloc<int32_t>(1); x1.sloc = d.alloc<int32_t>(h.n_used);
            d.put(x1.slots, iota.data(), h.n_used); d.put(x1.tile_s0, iota.data(), h.n_used); d.put(x1.tile_n, ones.data(), h.n_used);
            d.put(x1.sloc, loc.data(), h.n_used);
            d.put(x1.ntiles, &h.n_used, 1);
        }
        if (T >= tile_min) {
            tile_bound = MoeGroups::max_tiles(h.n_expert, T * h.n_used);
            if (xmx) { Xt = reinterpret_cast<float *>(xP); Ht = reinterpret_cast<float *>(xHp); } // 6 bytes per value there
            else {
                Xt = d.alloc<float>((size_t)tile_bound * h.n_embd * MOE_TS);
                Ht = d.alloc<float>((size_t)tile_bound * h.n_ff * MOE_TS);
            }
        }
        if (const char *e = std::getenv("INK_DENSE_MIN")) dense_min = std::atoi(e);
        if (const char *e = std::getenv("INK_MULTI")) multi_proj = std::atoi(e) != 0;
        if (T >= dense_min) Xd = d.alloc<float>((size_t)((T + MOE_TS - 1) / MOE_TS) * XD_COLS * MOE_TS);
        mix_inv = d.alloc<float>((size_t)T * ops::MIX_MAX); mix_sc = d.alloc<float>((size_t)T * 3 * ops::MIX_MAX);
        if (const char *e = std::getenv("INK_LOOP_PRE")) loop_pre = std::atoi(e) != 0;
        if (const char *e = std::getenv("INK_CTL_BATCH")) ctl_batch = std::atoi(e) != 0;
        if (const char *e = std::getenv("INK_ROUTE_SG")) route_sg = std::atoi(e) != 0;
        if (const char *e = std::getenv("INK_PV_U")) pv_u = std::atoi(e);
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
        if (xmx) { // the NVFP4 expert tensors in the tile layout (xmx_moe.hpp), once each
            std::set<const uint8_t *> done;
            uint8_t *tmp = nullptr;
            int nrep = 0;
            for (size_t i = 0; i < gu_dec.size(); ++i) {
                const WView &g = gu_dec[i], &dn = dn_dec[i];
                if (g.kind != K_NVFP4P || dn.kind != K_NVFP4P) continue;
                if (!tmp) tmp = d.alloc<uint8_t>(std::max(g.rb * (size_t)g.t->ne[1], dn.rb * (size_t)dn.t->ne[1]));
                if (done.insert(g.p).second) { xm::repack_tiles(d.q, const_cast<uint8_t *>(g.p), g.rb, 2 * h.n_ff, h.n_embd, h.n_expert, tmp); ++nrep; }
                if (done.insert(dn.p).second) { xm::repack_tiles(d.q, const_cast<uint8_t *>(dn.p), dn.rb, h.n_embd, h.n_ff, h.n_expert, tmp); ++nrep; }
            }
            if (tmp) d.release(tmp); // (not sycl::free: the device frees what it owns again at exit)
            std::fprintf(stderr, "[xmx] %d NVFP4 expert tensors in the tile layout\n", nrep);
        }
        if (xq) { // the decode copies of layers 20-23's experts in the XQ layout (xmx_q.hpp), in place, once each
            std::set<const uint8_t *> done;
            uint8_t *tmp = nullptr;
            size_t tmpb = 0;
            // (the kernels: gate|up Q5_K / Q4_K / IQ4_XS on whole 256-input groups, down Q5_0 / IQ4_NL)
            auto ok = [](const WView &v, bool down) {
                const int f = v.kind >= K_Q5_0P && v.kind <= K_Q5_KP ? xq::fmt_of(v.t->type) : -1;
                return down ? f == xq::F_Q5_0 || f == xq::F_IQ4_NL : (f == xq::F_Q5_K || f == xq::F_Q4_K || f == xq::F_IQ4_XS) && v.t->ne[0] % 256 == 0;
            };
            for (size_t i = 0; i < gu_dec.size(); ++i) {
                const WView &g = gu_dec[i], &dn = dn_dec[i];
                if (!ok(g, false) || !ok(dn, true)) continue;
                const size_t need = std::max(g.rb * (size_t)g.t->ne[1], dn.rb * (size_t)dn.t->ne[1]);
                if (need > tmpb) { if (tmp) d.release(tmp); tmp = d.alloc<uint8_t>(need); tmpb = need; }
                if (done.insert(g.p).second) xq::repack(d.q, xq::fmt_of(g.t->type), const_cast<uint8_t *>(g.p), g.rb, 2 * h.n_ff, h.n_embd, h.n_expert, tmp);
                if (done.insert(dn.p).second) xq::repack(d.q, xq::fmt_of(dn.t->type), const_cast<uint8_t *>(dn.p), dn.rb, h.n_embd, h.n_ff, h.n_expert, tmp);
            }
            for (auto *v : {&gu_dec, &dn_dec})
                for (WView &w : *v) if (done.count(w.p)) w.kind = K_XQ;
            if (tmp) d.release(tmp);
            std::fprintf(stderr, "[xmx] %zu expert tensors of layers 20-23 in the XQ layout\n", done.size());
        }
        {
            const bool on = !std::getenv("INK_Q6KU") || std::atoi(std::getenv("INK_Q6KU"));
            const long ucap = std::getenv("INK_Q6KU_CAP") ? std::atol(std::getenv("INK_Q6KU_CAP")) : 500000L;
            if (on && T >= dense_min && cap <= ucap) {
                size_t bytes = 0;
                for (const Layer &l : m.L)
                    for (const W *w : {&l.wq, &l.wk, &l.wv, &l.wo, &l.wgate, &l.rel}) {
                        if (!*w || w->kind != K_Q6_KP || q6u.count(w->t) || w->t->ne[0] > XD_COLS || w->t->rows() < 64) continue;
                        if (xq6 && q6e_fits(*w)) continue; // becomes Q6E below
                        const int cols = (int)w->t->ne[0];
                        const size_t rb = pl::Q6_KU::stride(cols), nr = (size_t)w->t->rows();
                        uint8_t *b = d.alloc<uint8_t>(rb * nr);
                        pl::q6ku_from_p(d.q, w->p, w->rb, b, rb, cols, nr).wait();
                        q6u[w->t] = WView{w->t, b, rb, K_Q6_KU};
                        bytes += rb * nr;
                    }
                if (!q6u.empty()) std::fprintf(stderr, "[ink] Q6_K prompt copies: %zu matrices, %.1f MB\n", q6u.size(), bytes / 1e6);
            }
        }
        if (h.passes > 1 && m.loop_res_query && m.loop_kv_res_query) {
            const int nr = (int)m.loop_res_query.t->rows();
            if (nr != 2 * h.loop_len() || (int)m.loop_kv_res_query.t->rows() != nr) loop_pre = false;
            if (loop_pre) {
                loop_nq = 2 * nr;
                if (const char *e = std::getenv("INK_LOOP_PRE_TOK")) lp_tok = std::atoi(e);
                lp_tok = std::max(1, std::min(T, lp_tok));
                if (const char *e = std::getenv("INK_LOOP_SC")) loop_sc = std::atoi(e) != 0;
                const size_t sct = loop_sc ? (size_t)T : (size_t)lp_tok;
                lmix_inv = d.alloc<float>(sct * ops::MIX_MAX);
                lmix_sc = d.alloc<float>(sct * loop_nq * ops::MIX_MAX);
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
        if (const char *e = std::getenv("INK_MM_BIG")) mm_big = std::atoi(e);
        if (const char *e = std::getenv("INK_MM_R")) mm_r = std::atoi(e);
        if (const char *e = std::getenv("INK_MM_R4")) mm_r4 = std::atoi(e);
        if (const char *e = std::getenv("INK_MM_OUT_R")) mm_out_r = std::atoi(e);
        if (const char *e = std::getenv("INK_MM_MULTI")) mm_multi = std::atoi(e);
        if (const char *e = std::getenv("INK_MM_MULTI_MINROWS")) mm_multi_minrows = std::atoi(e);
        if (const char *e = std::getenv("INK_MM_WO")) mm_wo = std::atoi(e);
        attl = d.alloc<float>(SB_MAX * xlane_floats(h.n_head * h.head_dim));
        ainl = d.alloc<float>(3 * SB_MAX * xlane_floats(h.n_embd));
        fxls = d.alloc<float>(SB_MAX * xlane_floats(h.n_embd));
        cst = d.alloc<float>((size_t)(SB_MAX - 1) * h.n_app * conv_n);
        cids = d.alloc<int32_t>(SB_MAX);
        finl = d.alloc<float>(SB_MAX * xlane_floats(h.n_embd));
        amx_v = d.alloc<float>((size_t)SB_MAX * ops::ARGMAX_G); amx_i = d.alloc<int32_t>((size_t)SB_MAX * ops::ARGMAX_G);
        if (const char *e = std::getenv("INK_OUT_LANE")) out_lane = std::atoi(e) != 0;
        if (const char *e = std::getenv("INK_ATT_SHARE")) att_share = std::atoi(e) != 0;
        if (const char *e = std::getenv("INK_TILE_SM")) tile_sm = std::atoi(e) != 0;
        if (const char *e = std::getenv("INK_XD_KEEP")) xd_keep_on = std::atoi(e) != 0;
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
        // INK_XMX_DENSE's buffers and copies come last: made earlier they moved the buffers after them, and the expert
        // kernels ran ~2 % slower there (2026-11-26)
        if (xdense) { // the Q8_0 attention matrices in the Q8E layout (xmx_esimd.hpp), in place, once each
            xdPe = d.alloc<uint16_t>(4 * xe_slot());
            std::set<const uint8_t *> done;
            size_t mx = 0;
            auto fits = [](const W &w) {
                return w && w.kind == K_Q8_0P && w.t->ne[0] % 256 == 0 && w.t->ne[0] <= XE_COLS && w.t->rows() % 128 == 0;
            };
            for (Layer &l : m.L)
                for (W *w : {&l.wq, &l.wk, &l.wv, &l.wo, &l.wgate, &l.rel}) if (fits(*w)) mx = std::max(mx, w->rb * (size_t)w->t->rows());
            uint8_t *tmp = mx ? d.alloc<uint8_t>(mx) : nullptr;
            int nrep = 0;
            for (Layer &l : m.L)
                for (W *w : {&l.wq, &l.wk, &l.wv, &l.wo, &l.wgate, &l.rel}) {
                    if (!fits(*w)) continue;
                    if (done.insert(w->p).second) {
                        d.q.memcpy(tmp, w->p, w->rb * (size_t)w->t->rows()).wait();
                        xd::repack_q8e(d.q, tmp, w->rb, (int)w->t->rows(), (int)w->t->ne[0], const_cast<uint8_t *>(w->p));
                        ++nrep;
                    }
                    w->kind = K_Q8_0E;
                }
            if (tmp) d.release(tmp); // (not sycl::free: the device frees what it owns again at exit)
            // the bf16 attention-input matrices (sink, k / v conv projections): BFE copies, rows padded to 32
            std::map<const uint8_t *, const uint8_t *> cp;
            int nbf = 0;
            for (Layer &l : m.L)
                for (W *w : {&l.sink, &l.k_conv_proj, &l.v_conv_proj}) {
                    if (!*w || w->kind != K_RAW || w->t->type != G_BF16 || w->t->ne[0] % 256 || w->t->ne[0] > XE_COLS || w->t->rows() % 8) continue;
                    auto it = cp.find(w->p);
                    if (it == cp.end()) {
                        const int rows = (int)w->t->rows(), cols = (int)w->t->ne[0], rp = (rows + 31) / 32 * 32;
                        uint16_t *c = d.alloc<uint16_t>((size_t)rp * cols);
                        xd::repack_bfe(d.q, reinterpret_cast<const uint16_t *>(w->p), rows, cols, rp, c);
                        it = cp.emplace(w->p, reinterpret_cast<const uint8_t *>(c)).first;
                        ++nbf;
                    }
                    w->p = it->second;
                    w->kind = K_BF16E;
                }
            // the Q6_K ones (xq6): Q6E copies from their Q6_KU rows, the planar copies freed
            int nq6 = 0;
            if (xq6) {
                std::map<const uint8_t *, const uint8_t *> c6;
                for (Layer &l : m.L)
                    for (W *w : {&l.wq, &l.wk, &l.wv, &l.wo, &l.wgate, &l.rel}) {
                        if (!q6e_fits(*w)) continue;
                        auto it = c6.find(w->p);
                        if (it == c6.end()) {
                            const int rows = (int)w->t->rows(), cols = (int)w->t->ne[0];
                            const size_t urb = pl::Q6_KU::stride(cols);
                            uint8_t *u = d.alloc<uint8_t>(urb * rows);
                            pl::q6ku_from_p(d.q, w->p, w->rb, u, urb, cols, rows).wait();
                            // the planar copy (planarize's own buffer) freed before the Q6E one is made: a lower peak
                            // (530K positions failed here by 8 MiB)
                            d.release(const_cast<uint8_t *>(w->p));
                            uint8_t *e6 = d.alloc<uint8_t>((size_t)(rows / 16) * (cols / 256) * xd::TG6);
                            xd::repack_q6e(d.q, u, urb, rows, cols, e6); // (waits)
                            d.release(u);
                            it = c6.emplace(w->p, e6).first;
                            ++nq6;
                        }
                        w->p = it->second;
                        w->kind = K_Q6_KE;
                    }
            }
            std::fprintf(stderr, "[xmx] %d Q8_0 attention matrices in the Q8E layout, %d bf16 ones in BFE copies, %d Q6_K ones in Q6E\n", nrep, nbf, nq6);
        }
    }

    void reset() {
        if (prev) prev->reset();
        n_past = 0;
        shard_S = 0; // (the copies are of positions the next conversation writes again)
        d.q.memset(conv, 0, sizeof(float) * (size_t)2 * conv_n * m.hp.n_app).wait();
        cpar = 0;
    }

    // sequence s becomes the bound one (its state in the members; the one bound before goes to seqs[]): step(), feed(),
    // next_token() and reset() then work on it
    void swap_state(SeqState &s) {
        std::swap(Kc, s.Kc); std::swap(Vc, s.Vc); std::swap(conv, s.conv); std::swap(cpar, s.cpar);
        std::swap(n_past, s.n_past); std::swap(last_tok, s.last_tok); std::swap(samp, s.samp); std::swap(samp_seed, s.samp_seed);
    }
    void bind(int s) {
        if (s < 0 || s >= (int)seqs.size()) throw std::runtime_error("engine: no sequence " + std::to_string(s));
        if (s == bound) return;
        swap_state(seqs[bound]); // the bound state goes home; the members hold seqs[bound]'s empty one
        swap_state(seqs[s]);
        bound = s;
    }
    int seq_past(int s) const { return s == bound ? n_past : seqs[s].n_past; }
    // one token of each of n distinct sequences in one step: row t = tok[t] at the next position of sequence seq[t]. The
    // row-wise parts run as for n tokens (steps of 2-8 tokens give every row its one-token values, as the checks); the
    // convolutions and cache stores take each row's own state (fz::SeqRow tables), and each row's attention runs the
    // one-token kernels against its own caches. So every row gets the values of a one-token step of its sequence.
    // Logits of all rows stay on the card (next_rows()).
    void step_rows(const int32_t *tok, const int *seq, int n) {
        const HParams &h = m.hp;
        if (n < 1 || n > SB_MAX || n > T || !mrow_dev) throw std::runtime_error("step_rows: 1 to " + std::to_string(SB_MAX) + " rows with INK_SEQS > 1");
        if (!(flash && flash_dec && dec_attn && fz::att_win_fused_on()))
            throw std::runtime_error("step_rows: needs the default attention paths (INK_FLASH, INK_FLASH_DEC, INK_DEC_ATTN, INK_ATT_WINF)");
        for (int t = 0; t < n; ++t) {
            if (seq[t] < 0 || seq[t] >= (int)seqs.size()) throw std::runtime_error("step_rows: no sequence " + std::to_string(seq[t]));
            for (int u = 0; u < t; ++u) if (seq[u] == seq[t]) throw std::runtime_error("step_rows: a sequence twice");
            if (seq_past(seq[t]) + 1 > cap) throw std::runtime_error("engine: context full");
        }
        for (int il = 0; il < h.n_app; ++il)
            for (int t = 0; t < n; ++t) {
                const int s = seq[t];
                float *cv = s == bound ? conv : seqs[s].conv;
                const int cp = s == bound ? cpar : seqs[s].cpar, pos = seq_past(s);
                fz::SeqRow &r = mrow_host[(size_t)il * n + t];
                r.st_in = cv + ((size_t)cp * h.n_app + il) * conv_n;
                r.st_out = cv + ((size_t)(cp ^ 1) * h.n_app + il) * conv_n;
                r.Kc = (s == bound ? Kc : seqs[s].Kc)[il];
                r.Vc = (s == bound ? Vc : seqs[s].Vc)[il];
                r.tau = tau_all + pos;
                r.pos = pos;
                r.pad = 0;
            }
        // (no wait: the queue runs in order, and mrow_host is not written again before next_rows() has waited)
        d.q.memcpy(mrow_dev, mrow_host.data(), sizeof(fz::SeqRow) * (size_t)h.n_app * n);
        float *ft = feat;
        auto os = std::move(on_step);
        const bool al = all_logits, hl = host_logits, ks = keep_states;
        feat = nullptr; on_step = nullptr; all_logits = true; host_logits = false; keep_states = false; mrows = true;
        try { step(tok, n); } catch (...) { feat = ft; on_step = std::move(os); all_logits = al; host_logits = hl; keep_states = ks; mrows = false; throw; }
        feat = ft; on_step = std::move(os); all_logits = al; host_logits = hl; keep_states = ks; mrows = false;
        for (int t = 0; t < n; ++t) {
            const int s = seq[t];
            if (s == bound) { n_past += 1; cpar ^= 1; }
            else { seqs[s].n_past += 1; seqs[s].cpar ^= 1; }
        }
    }
    // the next token of each row of the last step_rows (each sequence's sampling, else greedy), as next_token() would
    // choose it for that sequence alone; out[t] for row t, which also becomes the sequence's last_tok
    void next_rows(const int *seq, int n, int32_t *out) {
        const HParams &h = m.hp;
        for (int t = 0; t < n; ++t) {
            const int s = seq[t];
            const ops::SampleArgs &sa = s == bound ? samp : seqs[s].samp;
            const float *row = lg + (size_t)t * h.vocab_padded;
            if (sa.T > 0.0f) {
                ops::SampleArgs a = sa;
                a.u[0] = ops::sample_u(s == bound ? samp_seed : seqs[s].samp_seed, seq_past(s));
                pr("sample", ops::sample_rows(d.q, row, h.vocab_padded, h.vocab, 1, a, ids + t));
            } else
                pr("argmax", ops::argmax_rows2(d.q, row, h.vocab_padded, h.vocab, 1, ids + t, amx_v, amx_i));
        }
        d.get(out, ids, n);
        for (int t = 0; t < n; ++t) (seq[t] == bound ? last_tok : seqs[seq[t]].last_tok) = out[t];
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
        // INK_DENSE_MINROWS (default 64): fewer rows go to the generic kernels; F32 / BF16 from INK_DENSE_MINROWS_F
        // (default 16: the 24-row sink product 61.7 -> 22.5 us per 1,024 tokens, INK_PROF card 3; 64 = before)
        static const int mrows = std::getenv("INK_DENSE_MINROWS") ? std::atoi(std::getenv("INK_DENSE_MINROWS")) : 64;
        static const int mrows_f = std::getenv("INK_DENSE_MINROWS_F") ? std::atoi(std::getenv("INK_DENSE_MINROWS_F")) : 16;
        const bool fb = w.kind == K_RAW && (w.t->type == G_F32 || w.t->type == G_BF16);
        if (!Xd || ntok < dense_min || w.t->ne[0] > XD_COLS || w.t->rows() < (fb ? mrows_f : mrows)) return false;
        // INK_DENSE_R / INK_DENSE_SGW: rows and sub-groups per work-group of the Q8_0 / Q6_K tiles from 64 tokens
        // (default 4 rows, 32 sub-groups; the same values. INK_PROF 3K prompt, card 3: attn_output 1,323 -> 935 us per
        // launch; rows are the independent sums a lane keeps going, 2 = before)
        static const int dr = std::getenv("INK_DENSE_R") ? std::atoi(std::getenv("INK_DENSE_R")) : 4;
        static const int dsg = std::getenv("INK_DENSE_SGW") ? std::max(1, std::atoi(std::getenv("INK_DENSE_SGW"))) : 32;
        switch (w.kind) {
        case K_Q8_0P: dt = ntok >= 64 ? DTune{dr, dsg} : DTune{1, 1}; return true;
        case K_Q6_KP: dt = ntok >= 64 ? DTune{dr, dsg} : DTune{1, 1}; return true;
        case K_RAW:
            // INK_DENSE_RF=<rows>,<sub-groups> (F32 / BF16 tiles from 64 tokens, the same values; default 4 rows, 32
            // sub-groups. INK_PROF 3K prompt, card 3: loop down products 137-140 -> 66-69 us, router 86.9 -> 34.0; 1,1 = before)
            if (w.t->type == G_F32 || w.t->type == G_BF16) {
                static const DTune rf = [] {
                    DTune t{4, 32};
                    if (const char *e = std::getenv("INK_DENSE_RF")) std::sscanf(e, "%d,%d", &t.R, &t.sgw);
                    return t;
                }();
                static const DTune rs = [] { // fewer than 64 rows (INK_DENSE_RFS; 2,4 22.6 us, 1,4 24.6, 1,8 24.5)
                    DTune t{2, 4};
                    if (const char *e = std::getenv("INK_DENSE_RFS")) std::sscanf(e, "%d,%d", &t.R, &t.sgw);
                    return t;
                }();
                dt = ntok < 64 ? DTune{1, 1} : w.t->rows() < 64 ? rs : rf;
                return w.t->ne[0] <= 64 || ntok >= 128;
            }
            // Q5_K (attn_q of layer 22, file layout): ran the generic multi-vector kernel in prompt steps
            if (w.t->type == G_Q5_K && q5k_tiles) { dt = ntok >= 64 ? DTune{dr, dsg} : DTune{1, 1}; return true; }
            return false;
        default: return false;
        }
    }
    // the parts of a step of n <= SB_MAX tokens (rows padded to 1, 2, 4 or 8) for the ESIMD kernels
    template <class F> static void with_mp(int n, F &&f) {
        if (n == 1) f.template operator()<1>();
        else if (n == 2) f.template operator()<2>();
        else if (n <= 4) f.template operator()<4>();
        else f.template operator()<8>();
    }
    void split_e(const float *x, int cols, int ntok, uint16_t *pe) {
        with_mp(ntok, [&]<int MP>() { pr("xe_split", xd::splite<MP>(d.q, x, cols, ntok, cols, pe)); });
    }
    // one token: the jobs' P are the fp32 inputs (split inside the kernel); 2-8: PE parts from split_e
    bool xe_inside(int ntok) const { return ntok == 1; }
    void run_ej(const std::string &lab, const xd::EJobs &jb, int cols, int ntok) {
        if (ntok == 1) { pr(lab, xd::dgroupej<1, 128, true, true>(d.q, jb, cols, 1)); return; }
        with_mp(ntok, [&]<int MP>() { pr(lab, xd::dgroupej<MP>(d.q, jb, cols, ntok)); });
    }
    static int ekind(int kind) { return kind == K_BF16E ? xd::EK_BF : kind == K_Q6_KE ? xd::EK_Q6 : xd::EK_Q8; }
    static bool is_xe(int kind) { return kind == K_Q8_0E || kind == K_BF16E || kind == K_Q6_KE; }
    // a Q8E, BFE or Q6E matrix (INK_XMX_DENSE, INK_XMX_Q6) on n tokens
    void mm_xe(const W &w, const float *x, float *y, int ntok) {
        const int cols = (int)w.t->ne[0], rows = (int)w.t->rows();
        const bool bfm = w.kind == K_BF16E;
        if (ntok <= SB_MAX) {
            uint16_t *pe = xe_inside(ntok) ? (uint16_t *)x : xdPe + 3 * xe_slot();
            if (!xe_inside(ntok)) split_e(x, cols, ntok, pe);
            xd::EJobs jb;
            xd::ejob_add(jb, w.p, rows, pe, y, rows, ekind(w.kind));
            run_ej(wlabel(w), jb, cols, ntok);
            return;
        }
        const int Mpad = (ntok + 63) / 64 * 64;
        if (ntok > T) throw std::runtime_error("engine: mm_xe: step larger than the engine's");
        if (!(xe_keep && x == xe_src && ntok == xe_n && cols == xe_cols)) {
            pr("xd_split", xd::split(d.q, x, cols, ntok, Mpad, cols, xdP, (size_t)Mpad * cols));
            xe_src = xe_keep ? x : nullptr; xe_n = ntok; xe_cols = cols;
        }
        if (bfm)
            pr(wlabel(w), xd::dense<4, 1, 2, 2, 4, false, 8, false, false, true>(d.q, w.p, (rows + 31) / 32 * 32, cols, xdP, (size_t)Mpad * cols, Mpad, ntok, y,
                                                                              rows, nullptr, 0, rows));
        else if (w.kind == K_Q6_KE)
            pr(wlabel(w), xd::dense<4, 4, 2, 2, 4, false, 8, false, true, false, true>(d.q, w.p, rows, cols, xdP, (size_t)Mpad * cols, Mpad, ntok, y, rows));
        else pr(wlabel(w), xd::dense<4, 4, 2, 2, 4, false, 8, false, true>(d.q, w.p, rows, cols, xdP, (size_t)Mpad * cols, Mpad, ntok, y, rows));
    }
    void mm(const W &w, const float *x, float *y, int ntok) {
        if (is_xe(w.kind)) { mm_xe(w, x, y, ntok); return; }
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
            if (!(xd_keep && x == xd_src && ntok == xd_n && cols == xd_cols)) {
                pr("dense_gather", dense_gather(d.q, x, cols, ntok, cols, Xd));
                xd_src = xd_keep ? x : nullptr; xd_n = ntok; xd_cols = cols;
            }
            WView v = w.view();
            if (v.kind == K_Q6_KP && !q6u.empty()) { auto it = q6u.find(w.t); if (it != q6u.end()) v = it->second; }
            pr(wlabel(w), dense_t(d.q, v, ntok, Xd, y, rows, dt));
            return;
        }
        if (mm_multi > 0 && ntok <= 8 && rows >= mm_multi_minrows && multi_ok(w.view())) {
            MultiJobs mj;
            multi_add(mj, w.view(), x, y, mm_multi, cols, rows);
            pr(wlabel(w), gemv_multi_m(d.q, mj, ntok, false, 2, true));
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
    // picture rows (src/vision.hpp) by their ids: ids from XID0 up stand for rows the caller registered here (2304
    // floats in host memory each), read in place of a token's embedding and without the token norm
    // (notes/inkling2-vision.md 4.2)
    static constexpr int32_t XID0 = 1 << 30;
    std::unordered_map<int32_t, const float *> xrow;
    void embed(const int32_t *tok, int ntok, float *dst) {
        const Tensor &t = *m.tok_embd.t;
        const int n = (int)t.ne[0], nc = n / 32;
        const size_t rb = t.row_bytes();
        const int64_t rows = (int64_t)t.rows();
        // (a split's later engines have no table of their own: the first one's, in host memory too; the drafter's anchor)
        const Engine *te = this;
        while (te->embd_tab.empty() && te->prev) te = te->prev;
        const std::vector<uint8_t> &tab = te->embd_tab;
        if (tab.size() < (size_t)rows * rb) throw std::runtime_error("engine: no embedding table in host memory");
        std::vector<float> &st = embd_stage[embd_k];
        embd_ev[embd_k].wait(); // the copy that last read this buffer
        st.resize((size_t)ntok * n);
        fmt::dispatch(t.type, [&]<class FT>() {
            for (int i = 0; i < ntok; ++i) {
                if (tok[i] >= XID0) {
                    auto it = xrow.find(tok[i]);
                    if (it == xrow.end()) throw std::runtime_error("engine: picture row " + std::to_string(tok[i]) + " is not loaded");
                    std::memcpy(st.data() + (size_t)i * n, it->second, sizeof(float) * n);
                    continue;
                }
                if (tok[i] < 0 || tok[i] >= rows) throw std::runtime_error("engine: token id " + std::to_string(tok[i]) + " out of range");
                const uint8_t *row = tab.data() + (size_t)tok[i] * rb;
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
    // an expert kernel's profile label, with the weight format under INK_PROF_TYPES
    static std::string mlabel(const char *b, const WView &v) {
        static const bool types = std::getenv("INK_PROF_TYPES") != nullptr;
        return types ? std::string(b) + ":" + type_name(v.t->type) : std::string(b);
    }

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
        DTune dd;
        const W &ld = l.loop_down[mod];
        if (n > 1 && ctl_nt_on() && E == 2304 && (int)ld.t->ne[0] == 2 * E && dense_tiles(ld, n, dd)) {
            // the norms straight into the tiles' input layout (ctl_norm_tiles: rms_norm_multi + dense_gather's values)
            pr("ctl_norm", ctl_norm_tiles(d.q, cur, mg, E, n, 1e-6f, Xd));
            xd_src = nullptr;
            WView v = ld.view();
            if (v.kind == K_Q6_KP && !q6u.empty()) { auto it = q6u.find(ld.t); if (it != q6u.end()) v = it->second; }
            pr(wlabel(ld), dense_t(d.q, v, n, Xd, ctl_z, (int)ld.t->rows(), dd));
        } else {
            const fz::NormJob jobs[2] = {{cur, ctl_h, nullptr, E, 2 * E}, {mg, ctl_h + E, nullptr, E, 2 * E}};
            pr("ctl_norm", fz::rms_norm_multi(d.q, jobs, 2, E, n, 1e-6f));
            mm(ld, ctl_h, ctl_z, n);
        }
        const W &ga = l.loop_gain[mod], &fo = l.loop_forget[mod];
        if (ga.t->type != fo.t->type || ga.rb != fo.rb || ga.kind != fo.kind) throw std::runtime_error("engine: gain/forget layouts differ");
        DTune dt;
        if (n > 1 && dense_tiles(ga, n, dt)) {
            // 64-column F32 rows: ctl_out_r64 reads ctl_z as it is (the same values; INK_CTL64=0: the tiles below)
            if (ctl64_on() && h.gate_rank == 64 && ga.kind == K_RAW && ga.t->type == G_F32 && ga.rb == 256 && fo.rb == 256 && E % 16 == 0) {
                pr("ctl_out", ctl_out_r64(d.q, (const float *)ga.p, (const float *)fo.p, E, ctl_z, n, CtlOp{cur, mg, y, E}));
                return;
            }
            pr("dense_gather", dense_gather(d.q, ctl_z, h.gate_rank, n, h.gate_rank, Xd));
            // INK_CTL_T=<row pairs>,<sub-groups> (default 1,8): the op after a local-memory transpose (DensePairTS:
            // the op's reads and writes 16 consecutive rows per sub-group; the same values; INK_PROF 3K prompt, card 3:
            // 199.2 -> 146.5 us per launch, 1,16 150.9, 1,32 159.1, 2,16 215.9); 0,0 = DensePairT, 1 x 1 (before)
            static const DTune ct = [] {
                DTune t{1, 8};
                if (const char *e = std::getenv("INK_CTL_T")) std::sscanf(e, "%d,%d", &t.R, &t.sgw);
                return t;
            }();
            if (ct.R > 0) pr("ctl_out", dense_pair_ts(d.q, ga.view(), fo.p, E, n, Xd, CtlOp{cur, mg, y, E}, ct));
            else pr("ctl_out", dense_pair_t(d.q, ga.view(), fo.p, E, n, Xd, CtlOp{cur, mg, y, E}, DTune{1, 1}));
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
        const int pos0 = n_past; // (rows of different sequences: their own positions, mrow_host)
        n_tok = ntok;
        if (!mrows && pos0 + ntok > cap) throw std::runtime_error("engine: context full");
        if (ntok < 1 || ntok > T) // the buffers hold T tokens: a bigger step writes past them (a card page fault)
            throw std::runtime_error("engine: step of " + std::to_string(ntok) + " tokens, buffers hold " + std::to_string(T));
        tau = tau_all + pos0;
        if (prev && pull) {
            if (!tok && (ntok != 1 || last_tok < 0)) throw std::runtime_error("engine: step(nullptr) needs next_token() first");
            pull_rows(tok ? tok : &last_tok, ntok);
        }
        if (a0 == 0) {
        if (tok) d.put(ids, tok, ntok); // else ids[0..ntok) are on the card already (next_token())
        // embedding and token norm (inkling2.cpp:347-352)
        bool pics = false;
        if (tok) for (int i = 0; i < ntok; ++i) pics |= tok[i] >= XID0;
        if (m.tok_embd.p) {
            if (pics) throw std::runtime_error("engine: picture rows need the host embedding table (INK_EMBD_HOST)");
            pr("get_rows", ops::get_rows(d.q, *m.tok_embd.t, m.tok_embd.p, ids, lbuf[0], ntok));
        } else {
            if (!tok && (ntok != 1 || last_tok < 0)) throw std::runtime_error("engine: step(nullptr) needs next_token() first");
            embed(tok ? tok : &last_tok, ntok, lbuf[0]);
        }
        if (!pics) pr("rms_norm", ops::rms_norm(d.q, lbuf[0], lbuf[0], f32(m.tok_norm), E, ntok, h.eps));
        else // the token rows' norm, run by run (a row's norm does not depend on the others); picture rows stay as they are
            for (int i = 0; i < ntok;) {
                if (tok[i] >= XID0) { ++i; continue; }
                int j = i;
                while (j < ntok && tok[j] < XID0) ++j;
                pr("rms_norm", ops::rms_norm(d.q, lbuf[0] + (size_t)i * E, lbuf[0] + (size_t)i * E, f32(m.tok_norm), E, j - i, h.eps));
                i = j;
            }
        } // (a0 > 0: the rows of applications before a0 came by carry_in)

        std::vector<const float *> blocks, prelude_blocks, bank;
        const float *cur = lbuf[0], *prelude_cur = nullptr, *bank_last = nullptr;
        const int nloop = h.passes > 1 ? h.loop_len() : 0;
        const float kscale = 1.0f / std::sqrt((float)hd);
        // every loop mix of a pass (12 layers x 2 calls x 2 queries) in two launches, from the previous pass's bank
        const auto loop_mix_pre = [&]() {
            if (!(loop_pre && (ntok <= lp_tok || loop_sc))) return;
            ops::MixArgs a;
            const int nb = (int)bank.size();
            if (nb + 1 > ops::MIX_MAX) throw std::runtime_error("engine: too many blocks");
            for (int s = 0; s < nb; ++s) a.st[s] = bank[nb - 1 - s];
            a.st[nb] = bank_last;
            a.ns = nb + 1;
            const int nr = loop_nq / 2;
            pr("loop_mix_scores", fz::mix_scores_many(d.q, a, E, f32(m.loop_res_query), nr, f32(m.loop_kv_res_query), nr,
                                                      lmix_inv, lmix_sc, E, ntok));
            if (ntok <= lp_tok) pr("loop_mix_out", ops::mix_out(d.q, a, E, loop_nq, lmix_inv, lmix_sc, lmix_out, E, ntok));
        };

        for (int il = 0; il < a1; ++il) {
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
                        if (il >= a0) loop_mix_pre();
                    }
                } else if (pass > 0 && il == a0) loop_mix_pre(); // a split's second engine starting inside a pass
                if (pass > 0 && il >= a0) {
                    const int row = 2 * (ip - h.core_start);
                    const size_t S = (size_t)ntok * E;
                    if (loop_pre && ntok <= lp_tok) {
                        const float *res = lmix_out + (size_t)row * S, *kv = lmix_out + (size_t)(loop_nq / 2 + row) * S;
                        mg[0] = res; mg[3] = res + S; mg[1] = kv; mg[2] = kv + S;
                    } else {
                        if (loop_pre && loop_sc) {
                            ops::MixArgs a;
                            const int nb = (int)bank.size();
                            for (int s = 0; s < nb; ++s) a.st[s] = bank[nb - 1 - s];
                            a.st[nb] = bank_last;
                            a.ns = nb + 1;
                            if (fz::mix_out4_on()) // both mixes in one pass over the bank (INK_MIX4=0: two ops::mix_out)
                                pr("loop_mix_out", fz::mix_out4(d.q, a, E, lmix_inv, lmix_sc, loop_nq,
                                                                sycl::int4{row, row + 1, loop_nq / 2 + row, loop_nq / 2 + row + 1},
                                                                mm2[0], mm2[1], E, ntok));
                            else {
                                pr("mix_out", ops::mix_out(d.q, a, E, 2, lmix_inv, lmix_sc, mm2[0], E, ntok, loop_nq, row));
                                pr("mix_out", ops::mix_out(d.q, a, E, 2, lmix_inv, lmix_sc, mm2[1], E, ntok, loop_nq, loop_nq / 2 + row));
                            }
                        } else {
                            mix(bank, bank_last, f32(m.loop_res_query) + (size_t)row * E, 2, mm2[0], E);
                            mix(bank, bank_last, f32(m.loop_kv_res_query) + (size_t)row * E, 2, mm2[1], E);
                        }
                        mg[0] = mm2[0]; mg[3] = mm2[0] + S; mg[1] = mm2[1]; mg[2] = mm2[1] + S;
                    }
                }
            }
            if (il < a0) { // the other engine's application: its block bookkeeping only (carry_slots replays the same)
                if (feat) // (the drafter's feature rows of visits before a0 came with the rows, carry_set)
                    for (int j = 0; j < 3; ++j)
                        if (il == feat_vis[j]) d.q.memcpy(feat + (size_t)j * T * E, cur, sizeof(float) * (size_t)ntok * E);
                if (ip % h.res_block == 0) blocks.push_back(cur);
                cur = lbuf[il + 1];
                continue;
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
            // INK_XMX_DENSE, steps of 1-8 tokens: the Q8E / BFE / Q6E matrices among the attention inputs in one ESIMD launch (each input
            // split once into its slot of xdPe), the others below as before
            bool xe_done[8] = {false, false, false, false, false, false, false, false};
            if (xdense && ntok <= SB_MAX && multi_proj) {
                const W *ws[8] = {&l.wq, &l.wk, &l.wv, swa ? nullptr : &l.k_conv_proj, swa ? nullptr : &l.v_conv_proj, &l.rel, &l.sink, &l.wgate};
                const float *xs[8] = {in[0], in[1], in[2], in[1], in[2], in[0], in[0], in[0]};
                float *ys[8] = {Q, Kr, Vr, dynK, dynV, R, sinks, gate};
                xd::EJobs jb;
                const float *src[3] = {nullptr, nullptr, nullptr};
                int ns = 0;
                for (int k = 0; k < 8; ++k) {
                    if (!ws[k] || !*ws[k] || !is_xe(ws[k]->kind) || (int)ws[k]->t->ne[0] != E) continue;
                    int sl = 0;
                    while (sl < ns && src[sl] != xs[k]) ++sl;
                    if (sl == ns) { src[ns++] = xs[k]; if (!xe_inside(ntok)) split_e(xs[k], E, ntok, xdPe + sl * xe_slot()); }
                    xd::ejob_add(jb, ws[k]->p, (int)ws[k]->t->rows(), xe_inside(ntok) ? (const uint16_t *)xs[k] : xdPe + sl * xe_slot(), ys[k], (int)ws[k]->t->rows(),
                                 ekind(ws[k]->kind));
                    xe_done[k] = true;
                }
                if (jb.nj) run_ej("w:attn_in_xe", jb, E, ntok);
            }
            if (ntok == 1 && multi_proj) { // one launch for the matrices that read the attention inputs (multi.hpp)
                MultiJobs mj;
                const W *ws[8] = {&l.wq, &l.wk, &l.wv, swa ? nullptr : &l.k_conv_proj, swa ? nullptr : &l.v_conv_proj, &l.rel, &l.sink, &l.wgate};
                const float *xs[8] = {in[0], in[1], in[2], in[1], in[2], in[0], in[0], in[0]};
                float *ys[8] = {Q, Kr, Vr, dynK, dynV, R, sinks, gate};
                bool ok = true;
                for (int k = 0; k < 8; ++k) if (ws[k] && !xe_done[k] && !multi_ok(ws[k]->view())) ok = false;
                if (ok) {
                    for (int k = 0; k < 8; ++k) if (ws[k] && !xe_done[k]) multi_add(mj, ws[k]->view(), xs[k], ys[k], std::min(tune(*ws[k]).R, 2));
                    if (mj.nj) pr("w:attn_in", gemv_multi(d.q, mj, 2));
                } else {
                    for (int k = 0; k < 8; ++k) if (ws[k] && !xe_done[k]) mm(*ws[k], xs[k], ys[k], ntok);
                }
            } else if (sb && inl[0] && multi_proj) { // 2-8 tokens: the same matrices in one launch, inputs in lane order
                MultiJobs mj;
                const W *ws[8] = {&l.wq, &l.wk, &l.wv, swa ? nullptr : &l.k_conv_proj, swa ? nullptr : &l.v_conv_proj, &l.rel, &l.sink, &l.wgate};
                const float *xs[8] = {inl[0], inl[1], inl[2], inl[1], inl[2], inl[0], inl[0], inl[0]};
                float *ys[8] = {Q, Kr, Vr, dynK, dynV, R, sinks, gate};
                bool ok = true;
                for (int k = 0; k < 8; ++k) if (ws[k] && !xe_done[k] && !multi_ok(ws[k]->view())) ok = false;
                if (ok) {
                    const int lx = (int)xlane_floats(E);
                    const bool big = mm_big == 1 || (mm_big == 2 && ntok > 4);
                    for (int k = 0; k < 8; ++k)
                        if (ws[k] && !xe_done[k]) multi_add(mj, ws[k]->view(), xs[k], ys[k],
                                             big ? (ntok > 4 ? mm_r : mm_r4) : ntok > 4 ? 1 : std::min(tune(*ws[k]).R, sb_r), lx,
                                             (int)ws[k]->t->rows());
                    if (mj.nj) pr("w:attn_in", gemv_multi_m(d.q, mj, ntok, true, sb_sgw, big));
                } else {
                    for (int k = 0; k < 8; ++k) if (ws[k] && !xe_done[k]) mm(*ws[k], in[k < 3 ? k : (k < 5 ? k - 2 : 0)], ys[k], ntok);
                }
            } else {
                // grouped by input, each gathered once for the dense tiles (xd_keep; the inputs do not change here)
                xd_keep = xd_keep_on; xd_src = nullptr;
                xe_keep = true; xe_src = nullptr;
                mm(l.wq, in[0], Q, ntok);
                mm(l.rel, in[0], R, ntok);
                mm(l.sink, in[0], sinks, ntok);
                mm(l.wgate, in[0], gate, ntok);
                mm(l.wk, in[1], Kr, ntok);
                if (!swa) mm(l.k_conv_proj, in[1], dynK, ntok);
                mm(l.wv, in[2], Vr, ntok);
                if (!swa) mm(l.v_conv_proj, in[2], dynV, ntok);
                xd_keep = false; xd_src = nullptr;
                xe_keep = false; xe_src = nullptr;
            }
            const bool tiles = !mrows && att_tile > 0 && ntok >= att_tile && vld > 0 && nh == 3 * nkvh && h.n_rel == 16;
            {   // convolutions, clips, positions, cache store, bias table (one launch)
                fz::PrepArgs a{};
                a.ntok = ntok; a.pos0 = pos0; a.nh = nh; a.nkvh = nkvh; a.hd = hd; a.nr = h.n_rel; a.ext = h.rel_extent;
                a.full = !swa; a.tau = tau;
                a.Q = Q; a.q_clip = f32(l.q_clip); a.qk_clip = h.qk_clip;
                a.Kr = Kr; a.Vr = Vr; a.dynK = dynK; a.dynV = dynV; a.k_conv = f32(l.k_conv); a.v_conv = f32(l.v_conv);
                a.st_in = st_in; a.st_out = st_out; a.st_tok = st_tok; a.sst = sst; a.Kx = Kx; a.Vx = Vx; a.Kc = Kc[il]; a.Vc = Vc[il]; a.vld = kvl[il]; a.km = kmask[il];
                a.eps = h.eps; a.kv_scale = fz::conv_scale(!swa);
                a.R = R; a.Rc = Rc; a.rel_clip = f32(l.rel_clip); a.rel_clip_thr = h.rel_clip; a.rel_bias = f32(l.rel_bias); a.tab = tiles ? nullptr : tab;
                if (mrows) a.mr = mrow_dev + (size_t)il * ntok;
                if (!a.tab && a.nr == SG && fz::prep_sg_sgw() > 0) pr("attn_prep", fz::attn_prep_sg(d.q, a, fz::prep_sg_sgw()));
                else pr("attn_prep", fz::attn_prep(d.q, a));
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
            const bool winf = !mrows && fast && win > 0 && win <= 1024 && ntok <= SB_MAX && fz::att_win_fused_on();
            // rows of different sequences: every row's attention in one launch with the per-row table (the one-token
            // kernels' values: windowed attn_win_fused<3, 3, 2>, else attn_flash_dec<3, 1> over the most blocks of any row
            // + attn_flash_sum); rows past the parts buffer (very long contexts) one by one as one-token steps
            int mr_nblk = 0;
            if (mrows && win == 0)
                for (int t = 0; t < ntok; ++t) mr_nblk = std::max(mr_nblk, mrow_host[(size_t)il * ntok + t].pos / fz::PVB + 1);
            const bool mr_one = mrows && mr_batch && (win > 0 || (size_t)ntok * mr_nblk <= dec_cap);
            if (mr_one) {
                const fz::SeqRow *mr = mrow_dev + (size_t)il * ntok;
                if (win > 0)
                    pr("attn_win", fz::attn_win_fused<3, 3, 2>(d.q, Q, nullptr, tab, nullptr, kvl[il], sinks, gate, 0, ntok, nh, nkvh, hd,
                                                              h.rel_extent, win, kscale, kmask[il], att, 0, mr));
                else {
                    pr("attn_pv_full", fz::attn_flash_dec<3, 1>(d.q, Q, nullptr, tab, Rc, f32(l.rel_bias), h.n_rel, nullptr, kvl[il], 0, ntok,
                                                               nh, nkvh, hd, h.rel_extent, kscale, pvpart, pml, mr_nblk, kmask[il], 0, mr));
                    pr("attn_pv_sum_full", fz::attn_flash_sum(d.q, pvpart, pml, mr_nblk, 0, ntok, nh, hd, sinks, gate, att, 0, nullptr, 0, 0, mr));
                }
            } else if (mrows) // (INK_MR_BATCH=0, or past the parts buffer) each row's attention as a one-token step of its sequence
                for (int t = 0; t < ntok; ++t) {
                    const fz::SeqRow &sr = mrow_host[(size_t)il * ntok + t];
                    const int p = sr.pos;
                    const float *Qt = Q + (size_t)t * nh * hd, *tt = tab + (size_t)t * nh * h.rel_extent, *sct = sinks + (size_t)t * nh;
                    const float *gt = gate + (size_t)t * nh * hd, *Rt = Rc + (size_t)t * nh * h.n_rel;
                    float *at = att + (size_t)t * nh * hd;
                    if (win > 0) {
                        pr("attn_win", fz::attn_win_fused<3, 3, 2>(d.q, Qt, sr.Kc, tt, sr.Vc, kvl[il], sct, gt, p, 1, nh, nkvh, hd,
                                                                  h.rel_extent, win, kscale, kmask[il], at));
                        continue;
                    }
                    const int nblk = p / fz::PVB + 1;
                    if ((size_t)nblk > dec_cap) { // as a one-token step past the parts buffer: whole 128-block groups
                        const int cb = (int)(dec_cap / 128 * 128);
                        if (cb < 128) throw std::runtime_error("engine: the parts buffer holds less than 128 blocks a row");
                        for (int b0 = 0; b0 < nblk; b0 += cb) {
                            const int nbc = std::min(cb, nblk - b0);
                            pr("attn_pv_full", fz::attn_flash_dec<3, 4, 1>(d.q, Qt, sr.Kc, tt, Rt, f32(l.rel_bias), h.n_rel, sr.Vc, kvl[il],
                                                                          p, 1, nh, nkvh, hd, h.rel_extent, kscale, pvpart, pml, nbc,
                                                                          kmask[il], b0));
                            pr("attn_pv_sum_full", fz::attn_flash_sum(d.q, pvpart, pml, nbc, p, 1, nh, hd, sct, gt, at, b0, fst, b0 > 0,
                                                                      b0 + nbc < nblk));
                        }
                        continue;
                    }
                    pr("attn_pv_full", fz::attn_flash_dec<3, 1>(d.q, Qt, sr.Kc, tt, Rt, f32(l.rel_bias), h.n_rel, sr.Vc, kvl[il], p, 1,
                                                               nh, nkvh, hd, h.rel_extent, kscale, pvpart, pml, nblk, kmask[il]));
                    pr("attn_pv_sum_full", fz::attn_flash_sum(d.q, pvpart, pml, nblk, p, 1, nh, hd, sct, gt, at));
                }
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
            const bool fl = flash && win == 0, fl_tile = !mrows && fl && tiles && ntok >= flash_min;
            // lean (VAR 1052; bench_attn card 3, 100K keys x 256 rows: 20.46-21.05 -> 20.06-20.12 ms, 5.86-6.21 -> 5.53-5.60
            // J, values the same): Q rows at constant offsets, the exponentials as local block loads, each sub-group the
            // block maximum of its own 3 rows (3 reductions, not 24)
            if (fl_tile && flash_lean)
                pr("attn_flash_full", fz::attn_flash_tile<8, 3, 1, 1052>(d.q, Q, Kc[il], Rc, f32(l.rel_bias), h.n_rel, sinks, Vc[il], kvl[il],
                                                                     pos0, ntok, nh, nkvh, hd, h.rel_extent, kscale, gate, att, kmask[il]));
            else if (fl_tile)
                pr("attn_flash_full", fz::attn_flash_tile<8, 3, 1, 4>(d.q, Q, Kc[il], Rc, f32(l.rel_bias), h.n_rel, sinks, Vc[il], kvl[il], pos0,
                                                                  ntok, nh, nkvh, hd, h.rel_extent, kscale, gate, att, kmask[il]));
            // windowed layers, prompt tiles: scores, softmax and P.V in one launch, the scores in local memory (attn_win_tile,
            // the three kernels' values; INK_WIN_TILE=0: those kernels)
            const bool wtile = !mrows && tiles && win > 0 && !winf && fz::win_tile_mt() > 0;
            if (wtile) {
                const int mt = fz::win_tile_mt(), span = (win + mt + 14 + 15) / 16 * 16;
                auto go = [&]<int MT>() {
                    // the scores in P: as many query blocks per launch as P holds slices for
                    const int nqb = (ntok + MT - 1) / MT;
                    const size_t slice = (size_t)MT * 3 * span * nkvh, pfl = p_floats;
                    const int per = (int)std::max<size_t>(1, pfl / slice);
                    if (pfl < slice) throw std::runtime_error("engine: P too small for attn_win_tile");
                    for (int qb0 = 0; qb0 < nqb; qb0 += per)
                        pr("attn_win_tile", fz::attn_win_tile<MT, 3>(d.q, Q, Kc[il], Rc, f32(l.rel_bias), h.n_rel, sinks, Vc[il],
                                                                           kvl[il], pos0, ntok, nh, nkvh, hd, h.rel_extent, win, kscale,
                                                                           gate, att, kmask[il], span, P, qb0, std::min(per, nqb - qb0)));
                };
                if (mt == 8) go.template operator()<8>();
                else go.template operator()<4>();
            }
            for (int q0 = 0; q0 < (mrows || winf || fl_tile || wtile ? 0 : ntok); q0 += prow) {
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
                        if (fdec && shard_S > 0 && !h.swa[il] && p0 >= shard_S + h.rel_extent) { // (cache sharing, above)
                            shard_attn(il, l, Qd, td, Rd, sc + (size_t)c0 * nh, gc + (size_t)c0 * nh * hd, ac + (size_t)c0 * nh * hd,
                                       p0, nt, nblk, kscale);
                            continue;
                        }
                        if (fdec && (size_t)nt * nblk > dec_cap) { // chunks of whole 128-block groups (dec_mem above)
                            const int cb = (int)(dec_cap / nt / 128 * 128);
                            if (cb < 128) throw std::runtime_error("engine: the parts buffer holds less than 128 blocks a row");
                            for (int b0 = 0; b0 < nblk; b0 += cb) {
                                const int nbc = std::min(cb, nblk - b0);
                                if (nt <= 4)
                                    pr("attn_pv_full", fz::attn_flash_dec<3, 4, 1>(d.q, Qd, Kc[il], td, Rd, f32(l.rel_bias), h.n_rel, Vc[il], kvl[il],
                                                                                  p0, nt, nh, nkvh, hd, h.rel_extent, kscale, pvpart, pml, nbc,
                                                                                  kmask[il], b0));
                                else
                                    pr("attn_pv_full", fz::attn_flash_dec<3, 8, 1>(d.q, Qd, Kc[il], td, Rd, f32(l.rel_bias), h.n_rel, Vc[il], kvl[il],
                                                                                  p0, nt, nh, nkvh, hd, h.rel_extent, kscale, pvpart, pml, nbc,
                                                                                  kmask[il], b0));
                                pr("attn_pv_sum_full", fz::attn_flash_sum(d.q, pvpart, pml, nbc, p0, nt, nh, hd, sc + (size_t)c0 * nh,
                                                                          gc + (size_t)c0 * nh * hd, ac + (size_t)c0 * nh * hd, b0, fst, b0 > 0,
                                                                          b0 + nbc < nblk));
                            }
                            continue;
                        }
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
            if (mm_wo > 0 && ntok >= 2 && ntok <= SB_MAX && multi_ok(l.wo.view()) && (int)l.wo.t->ne[0] == h.n_head * h.head_dim) {
                const int cols = (int)l.wo.t->ne[0], rows = (int)l.wo.t->rows(), lx = (int)xlane_floats(cols);
                float *al = attl;
                const float *as = att;
                pr("wo_lane", d.q.parallel_for(sycl::range<2>((size_t)ntok, (size_t)cols), [=](sycl::id<2> i) {
                    al[i[0] * lx + xlane_at((int)i[1])] = as[i[0] * cols + i[1]];
                }));
                MultiJobs mj;
                multi_add(mj, l.wo.view(), attl, ob, mm_wo, lx, rows);
                pr(wlabel(l.wo), gemv_multi_m(d.q, mj, ntok, true, 2, true));
            } else mm(l.wo, att, ob, ntok);
            const bool bstart = ip % h.res_block == 0;
            const fz::SeqRow *mr = mrows ? mrow_dev + (size_t)il * ntok : nullptr;
            pr("attn_tail", fz::attn_tail(d.q, ob, st_in, st_out, 2 * kd, f32(l.attn_post_conv), fz::conv_scale(false),
                                          attn_out, bstart ? nullptr : inpSA, ffn_inp, E, ntok, st_tok, sst, mr));
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
            fz::YSeg yseg{}; // set when the expert outputs are left as segment sums (INK_XMX, steps of 1-8 tokens)
            // INK_XMX, one token: the norm writes the experts' input parts too (xP, part stride E)
            uint16_t *xp1 = xmx && ntok == 1 && ((gu_dec[ip].kind == K_NVFP4P && dn_dec[ip].kind == K_NVFP4P) ||
                                                 (gu_dec[ip].kind == K_XQ && dn_dec[ip].kind == K_XQ)) ? xP : nullptr;
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
                pr("rms_norm", ops::rms_norm(d.q, ctl_y, fxl1 ? nullptr : fx, f32(l.ffn_norm), E, ntok, h.eps, -1, -1, fyl, xp1));
            } else {
                fz::NormOut no{};
                no.y[0] = fxl1 ? nullptr : fx; no.w[0] = f32(l.ffn_norm); no.yl[0] = fyl; no.yp[0] = xp1;
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
                if (xmx && gv.kind == K_NVFP4P && dv.kind == K_NVFP4P) { // matrix engines, every step size the same bits
                    const xm::ActOp aop{f32(l.gate_up_s), h.situ_beta, h.situ_linear_beta};
                    const int nff = h.n_ff, ngu = (E / 16 + xm::SEG - 1) / xm::SEG, ndn = (nff / 16 + xm::SEG - 1) / xm::SEG;
                    const size_t ds = dv.rb * (size_t)l.down.t->ne[1];
                    if (ntok <= SB_MAX) { // a sub-group per (tile, 16 rows, segment); segments added in order by the folds
                        const bool one1 = ntok == 1;
                        MoeGroups gg = grp;
                        if (one1) { // tile k = slot k, its input row split once
                            gg = x1;
                            gg.tile_exp = eids;
                            if (!xp1) pr("moe_tiles", fxl1 ? xm::split_row_l(d.q, fxl1, E, xP) : xm::split_row(d.q, fx, E, xP));
                        } else {
                            pr("moe_group", moe_group(d.q, eids, K, h.n_expert, grp));
                            pr("moe_tiles", xm::split_gather_c(d.q, grp, K, fx, E, h.n_used, E, xP, xpp));
                        }
                        const int tl = one1 ? h.n_used : K, mm = one1 ? 1 : SB_MAX;
                        if (one1) { // a sub-group per (expert, 16 rows) over all inputs (1,152 sub-groups: one wave), L1 prefetch 8 steps ahead
                            pr("moe_gate_up", xm::full_prod<1, 0, 4, 2, 128, 8, 1>(d.q, gv.p, gs, E, nff, 2 * nff, gg, tl, xP, (size_t)E, true, aop, xHp, xhpp, nullptr, 0));
                            pr("moe_down", xm::full_prod<1, 1, 4, 2, 128, 8, 1>(d.q, dv.p, ds, nff, nff, E, gg, tl, xHp, xhpp, false, aop, nullptr, 0, yk, E));
                        } else { // segments in parallel, added in order by the fold and by ffn_tail
                            pr("moe_gate_up", xm::small3<SB_MAX, 0, 4, 1, 0, 2>(d.q, gv.p, gs, E, nff, 2 * nff, nff / 16, gg, tl, xP, xpp, false, xS));
                            pr("moe_fold", xm::small_fold_act_c(d.q, gg, tl, ngu, mm, xS, nff, aop, xHp, xhpp));
                            pr("moe_down", xm::small3<SB_MAX, 1, 4, 1, 0, 2>(d.q, dv.p, ds, nff, nff, E, E / 32, gg, tl, xHp, xhpp, false, xS));
                            yseg = fz::YSeg{xS, gg.sloc, ndn, mm}; // ffn_tail adds the down product's segments
                        }
                    } else { // super-tiles of up to 4 tiles of 16 slots x 4 blocks of 16 rows per work-group, passes of xch tokens
                        for (int c0 = 0; c0 < ntok; c0 += xch) {
                            const int kc = std::min(xch, ntok - c0) * h.n_used;
                            const int tiles = MoeGroups::max_tiles(h.n_expert, kc), stb = xm::Super::bound(h.n_expert, kc, 4);
                            pr("moe_group", moe_group(d.q, eids + (size_t)c0 * h.n_used, kc, h.n_expert, grp));
                            pr("moe_group", xm::super_tiles(d.q, grp, h.n_expert, xst));
                            pr("moe_tiles", xm::split_gather8(d.q, grp, tiles, fx + (size_t)c0 * E, E, h.n_used, E, xP));
                            pr("moe_gate_up", xm::prod2<4, 4, 4, 0>(d.q, gv.p, gs, E, nff, nff / 16, grp, xst, stb, xP, aop, xHp, nullptr, 0));
                            pr("moe_down", xm::prod2<4, 4, 4, 1>(d.q, dv.p, ds, nff, nff, E / 32, grp, xst, stb, xHp, aop, nullptr,
                                                                 yk + (size_t)c0 * h.n_used * E, E));
                        }
                    }
                } else if (xq && gv.kind == K_XQ && dv.kind == K_XQ) { // layers 20-23 on the matrix engines (xmx_q.hpp), every step size the same bits
                    const xm::ActOp aop{f32(l.gate_up_s), h.situ_beta, h.situ_linear_beta};
                    const int nff = h.n_ff, fg = xq::fmt_of(gw.t->type), fd = xq::fmt_of(l.down.t->type), nb = E / 32;
                    const size_t ds = dv.rb * (size_t)l.down.t->ne[1];
                    const bool kq = fg == xq::F_Q4_K || fg == xq::F_Q5_K;
                    if (ntok <= SB_MAX) { // a sub-group per (tile, 16 rows) over all inputs
                        const bool one1 = ntok == 1;
                        MoeGroups gg = grp;
                        if (one1) { // tile k = slot k, its input row split once (by the norm: xp1)
                            gg = x1;
                            gg.tile_exp = eids;
                            if (!xp1) pr("moe_tiles", fxl1 ? xm::split_row_l(d.q, fxl1, E, xP) : xm::split_row(d.q, fx, E, xP));
                            if (kq) pr("moe_xsum", xq::xsum(d.q, nullptr, 0, xP, (size_t)E, 1, E, xqX));
                        } else {
                            pr("moe_group", moe_group(d.q, eids, K, h.n_expert, grp));
                            pr("moe_tiles", xm::split_gather_c(d.q, grp, K, fx, E, h.n_used, E, xP, xpp));
                            if (kq) pr("moe_xsum", xq::xsum(d.q, fx, E, nullptr, 0, ntok, E, xqX));
                        }
                        if (one1) {
                            pr("moe_gate_up", xq::full<1, 0>(d.q, fg, gv.p, gs, E, nff, 2 * nff, gg, h.n_used, xP, (size_t)E, true, xqX, h.n_used, aop, xHp, xhpp, nullptr, 0));
                            pr("moe_down", xq::full<1, 1>(d.q, fd, dv.p, ds, nff, nff, E, gg, h.n_used, xHp, xhpp, false, nullptr, h.n_used, aop, nullptr, 0, yk, E));
                        } else {
                            pr("moe_gate_up", xq::full<SB_MAX, 0>(d.q, fg, gv.p, gs, E, nff, 2 * nff, gg, K, xP, xpp, false, xqX, h.n_used, aop, xHp, xhpp, nullptr, 0));
                            pr("moe_down", xq::full<SB_MAX, 1>(d.q, fd, dv.p, ds, nff, nff, E, gg, K, xHp, xhpp, false, nullptr, h.n_used, aop, nullptr, 0, yk, E));
                        }
                    } else { // xmx_moe's super-tiles and passes, the XQ prompt kernel
                        for (int c0 = 0; c0 < ntok; c0 += xch) {
                            const int nt = std::min(xch, ntok - c0), kc = nt * h.n_used;
                            const int tiles = MoeGroups::max_tiles(h.n_expert, kc), stb = xm::Super::bound(h.n_expert, kc, 4);
                            pr("moe_group", moe_group(d.q, eids + (size_t)c0 * h.n_used, kc, h.n_expert, grp));
                            pr("moe_group", xm::super_tiles(d.q, grp, h.n_expert, xst));
                            pr("moe_tiles", xm::split_gather8(d.q, grp, tiles, fx + (size_t)c0 * E, E, h.n_used, E, xP));
                            if (kq) {
                                pr("moe_xsum", xq::xsum(d.q, fx + (size_t)c0 * E, E, nullptr, 0, nt, E, xqX));
                                pr("moe_xsum", xq::xgather(d.q, grp, tiles, xqX, h.n_used, nb, xqXG));
                            }
                            pr("moe_gate_up", xq::prod<0>(d.q, fg, gv.p, gs, E, nff, nff / 16, grp, xst, stb, xP, xqXG, aop, xHp, nullptr, 0));
                            pr("moe_down", xq::prod<1>(d.q, fd, dv.p, ds, nff, nff, E / 32, grp, xst, stb, xHp, nullptr, aop, nullptr,
                                                       yk + (size_t)c0 * h.n_used * E, E));
                        }
                    }
                } else if (ntok == 1 && xl_on) { // SITU writes the down product's inputs in lane order (gemv2.hpp xlane_at)
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
                    if (tile_gather_sgw() > 0 && E % 128 == 0 && E % 4 == 0)
                        pr("moe_tiles", tile_gather_l(d.q, grp, tiles, fx, E, h.n_used, E, Xt, tile_gather_sgw()));
                    else pr("moe_tiles", tile_gather(d.q, grp, tiles, fx, E, h.n_used, E, Xt));
                    // NVFP4 (INK_TILE_V2, default on; the same values): 32 sub-groups per work-group (tile_sgw2), so the
                    // lookup tables are filled once per 32 sub-groups; gate|up 4 rows and down 4 rows (through the tables
                    // too) per sub-group, two tiles one after another (bench_moe 1,024 tokens, card 3: gate|up 11,730 ->
                    // 7,594 us, down 6,448 -> 3,989; 512 tokens 6,369 -> 4,194 and 3,526 -> 2,195)
                    if (tile_v2 && gv.kind == K_NVFP4P && tile_lut)
                        pr(mlabel("moe_gate_up", gv), slot_pair_g2(d.q, gv, gv.p + (size_t)h.n_ff * gv.rb, gs, h.n_ff, grp, tiles, Xt, so, Ht, 2, false, false));
                    else if (tile_x2().ng > 0 && exp_x2_kind(gv))
                        pr(mlabel("moe_gate_up", gv), slot_pair_x2(d.q, gv, gv.p + (size_t)h.n_ff * gv.rb, gs, h.n_ff, grp, tiles, Xt, so, Ht,
                                                                   tile_x2().ng, tile_x2().pair != 0, tile_x2().sgw));
                    else
                        pr(mlabel("moe_gate_up", gv), slot_pair_g(d.q, gv, gv.p + (size_t)h.n_ff * gv.rb, gs, h.n_ff, grp, tiles, Xt, so, Ht, 2));
                    if (tile_v2 && dv.kind == K_NVFP4P)
                        pr(mlabel("moe_down", dv), slot_rows_g2(d.q, dv, grp, tiles, Ht, yk, E, 4, false, false, tile_lut));
                    else if (tile_x2().r > 0 && exp_x2_kind(dv))
                        pr(mlabel("moe_down", dv), slot_rows_x2(d.q, dv, grp, tiles, Ht, yk, E, tile_x2().r, tile_x2().pair != 0, tile_x2().sgw));
                    else pr(mlabel("moe_down", dv), slot_rows_g(d.q, dv, grp, tiles, Ht, yk, E, 2));
                } else { // several tokens: each chosen expert decoded once per 8 slots
                    const int amax = std::min(h.n_expert, K);
                    pr("moe_group", moe_group(d.q, eids, K, h.n_expert, grp));
                    pr("moe_gate_up", grouped_pair(d.q, gv, gv.p + (size_t)h.n_ff * gv.rb, gs, h.n_ff, grp, amax, fx, E, h.n_used, so, 2));
                    pr("moe_down", grouped_rows(d.q, dv, grp, amax, hb, h.n_ff, yk, E, 2));
                }
            }
            float *lo = lbuf[il + 1];
            if (!mrows && ntok >= 64 && fz::ffn_tail_tt() > 0)
                pr("ffn_tail", fz::ffn_tail_s(d.q, yk, f32(l.down_s), eids, wts, h.n_used, st_in, st_out, 2 * kd + E,
                                              f32(l.ffn_post_conv), fz::conv_scale(false), ffn_out, fi, lo, E, ntok, fz::ffn_tail_tt(),
                                              st_tok, sst));
            else
                pr("ffn_tail", fz::ffn_tail(d.q, yk, f32(l.down_s), eids, wts, h.n_used, st_in, st_out, 2 * kd + E,
                                            f32(l.ffn_post_conv), fz::conv_scale(false), ffn_out, fi, lo, E, ntok, st_tok, sst, mr, yseg));
            dump.put(d, nm("ffn_out", il), ffn_out, E, ntok);
            dump.put(d, nm("l_out", il), lo, E, ntok);
            cur = lo;
        }
        if (a1 < h.n_app) { // a split's first engine: no output (its rows go on by carry_out)
            n_logit_rows = 0;
            n_past += ntok;
            cpar ^= 1;
            return;
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
                const bool big = mm_big == 1 || (mm_big == 2 && nl > 4);
                multi_add(mj, m.output.view(), x1, lg, big ? mm_out_r : 1, lx, h.vocab_padded);
                pr(wlabel(m.output), gemv_multi_m(d.q, mj, nl, true, 1, big));
            }
        } else
            mm(m.output, xl, lg, nl);
        pr("softcap", ops::softcap(d.q, lg, (size_t)nl * h.vocab_padded, h.softcap));
        if (feat) d.q.memcpy(feat + (size_t)3 * T * E, fin, sizeof(float) * (size_t)ntok * E);
        if (on_step) on_step(pos0, ntok);
        n_logit_rows = nl;
        if (mrows) return; // (step_rows moves each sequence on)
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
    // a prompt in steps of T tokens and the rest; when the rest would be under 512 tokens, in steps of one size (a
    // multiple of 16) instead: 4,150 tokens with T 4,096 as 2,080 + 2,070, not 4,096 + 54 (a short step leaves the
    // expert tiles mostly empty). The step size does not change any value. Card 2, 2026-11-25: 4,150 tokens 937.6-941.4
    // -> 955.5-958.3 tok/s; 5,000 (rest 904) and 31,270 (rest 2,598) level either way, so only a short rest is spread.
    // INK_FEED_EVEN=0: steps of T and the rest always
    const std::vector<float> &feed(const std::vector<int32_t> &tok) {
        static const bool even = !std::getenv("INK_FEED_EVEN") || std::atoi(std::getenv("INK_FEED_EVEN"));
        const size_t N = tok.size(), ns = (N + T - 1) / T;
        size_t s = (size_t)T;
        if (even && ns > 1 && N - (ns - 1) * (size_t)T < 512) s = std::min<size_t>((size_t)T, ((N + ns - 1) / ns + 15) / 16 * 16);
        // a split over cards (each engine of the chain on its own card; INK_PIPE=0: one after the other): a pipeline, each
        // engine before this one on a host thread, up to two steps ahead of the next (two host buffers per link)
        static const bool pipe = !std::getenv("INK_PIPE") || std::atoi(std::getenv("INK_PIPE"));
        std::vector<Engine *> ch;
        for (Engine *e = this; e; e = e->prev) ch.insert(ch.begin(), e);
        bool distinct = ch.size() > 1;
        for (size_t i = 0; i < ch.size() && distinct; ++i)
            for (size_t j = i + 1; j < ch.size(); ++j) distinct &= &ch[i]->d != &ch[j]->d;
        if (distinct && pull && pipe && N > s) {
            const size_t ne = ch.size(), nl = ne - 1;
            std::vector<std::pair<size_t, int>> st;
            for (size_t p = 0; p < N; p += s) st.push_back({p, (int)std::min<size_t>(s, N - p)});
            std::vector<std::vector<int>> cs(nl);            // link k: the rows engine k + 1 takes
            std::vector<std::array<std::vector<float>, 2>> hb(nl);
            for (size_t k = 0; k < nl; ++k) {
                cs[k] = ch[k + 1]->carry_set();
                for (auto &b : hb[k]) b.resize(carry_floats((int)s, cs[k].size()));
            }
            std::mutex mu;
            std::condition_variable cv;
            std::vector<size_t> made(nl, 0), taken(nl, 0);
            std::exception_ptr err;
            auto wait_for = [&](auto pred) {
                std::unique_lock<std::mutex> lk(mu);
                cv.wait(lk, [&] { return pred() || err; });
                return !err;
            };
            auto mark = [&](size_t &c, size_t v) {
                std::lock_guard<std::mutex> lk(mu);
                c = v;
                cv.notify_all();
            };
            auto fail = [&] {
                std::lock_guard<std::mutex> lk(mu);
                if (!err) err = std::current_exception();
                cv.notify_all();
            };
            for (Engine *e : ch) { e->pull = false; e->keep_states = keep_states; }
            // engine k: take step j's rows from link k - 1, run it, leave its rows in link k
            auto run = [&](size_t k) {
                try {
                    for (size_t j = 0; j < st.size(); ++j) {
                        const int n = st[j].second;
                        if (k > 0) {
                            if (!wait_for([&] { return made[k - 1] > j; })) return;
                            ch[k]->carry_copy(hb[k - 1][j % 2].data(), n, false, cs[k - 1]);
                            mark(taken[k - 1], j + 1);
                        }
                        ch[k]->step(tok.data() + st[j].first, n);
                        if (k < nl) {
                            if (!wait_for([&] { return j < taken[k] + 2; })) return;
                            ch[k]->carry_copy(hb[k][j % 2].data(), n, true, cs[k]);
                            mark(made[k], j + 1);
                        }
                    }
                } catch (...) { fail(); }
            };
            std::vector<std::thread> th;
            for (size_t k = 0; k < nl; ++k) th.emplace_back(run, k);
            run(nl);
            for (auto &t : th) t.join();
            for (Engine *e : ch) e->pull = true;
            if (err) std::rethrow_exception(err);
            return logits;
        }
        for (size_t p = 0; p < N; p += s) step(tok.data() + p, (int)std::min<size_t>(s, N - p));
        return logits;
    }
    // greedy choice on the card from the last step's last logits row (the first index of the largest value, as
    // argmax_last()); it becomes ids[0] for step(nullptr, 1) and is returned to the host
    // sampling instead (serving: ops::sample_rows) while samp.T > 0; the token at position p takes the uniform number
    // ops::sample_u(samp_seed, p), so a text depends on the seed and the conversation only (not on guessing)
    ops::SampleArgs samp;
    uint64_t samp_seed = 0;
    int next_token() {
        const float *row = lg + (size_t)(n_logit_rows - 1) * m.hp.vocab_padded;
        if (samp.T > 0.0f) {
            ops::SampleArgs a = samp;
            a.u[0] = ops::sample_u(samp_seed, n_past); // (the chosen token goes at position n_past)
            pr("sample", ops::sample_rows(d.q, row, m.hp.vocab_padded, m.hp.vocab, 1, a, ids));
        } else
            pr("argmax", ops::argmax_rows2(d.q, row, m.hp.vocab_padded, m.hp.vocab, 1, ids, amx_v, amx_i));
        int32_t v;
        d.get(&v, ids, 1);
        last_tok = v;
        return v;
    }
    void step_next() { step(nullptr, 1); }
    // a split (tools/ink_pipe.cpp): the rows and the saved mix scores (mix_tab) of carry_slots(a) for the last step's
    // ntok tokens, a = where the first engine ends and the second starts. carry_out (the first) copies them into host
    // memory, carry_in (the second) from it, carry_floats long; both wait
    // the slots the second engine takes: carry_slots, and with the drafter (feat) its feature rows of earlier visits
    // (extra_rows: rows a later engine of a chain reads, the drafter's feature rows; each engine takes those before a0)
    std::vector<int> extra_rows;
    // bytes from (sp, on xs's card) to (dp, on xd's card): one copy on one card, else through host memory in pieces
    static void xcopy(Engine &xd, void *dp, Engine &xs, const void *sp, size_t bytes) {
        if (&xd.d == &xs.d) { xd.d.q.memcpy(dp, sp, bytes); return; }
        const size_t piece = (size_t)64 << 20;
        auto &hb = xs.shard_h;
        hb.resize(std::min(bytes, piece) / sizeof(float) + 1);
        for (size_t o = 0; o < bytes; o += piece) {
            const size_t n = std::min(piece, bytes - o);
            xs.d.q.memcpy(hb.data(), (const char *)sp + o, n).wait();
            xd.d.q.memcpy((char *)dp + o, hb.data(), n).wait();
        }
    }
    // rows x cols halves from (src, row stride sld) to (dst, stride dld) on one card
    static sycl::event copy_rows(sycl::queue &q, sycl::half *dst, size_t dld, const sycl::half *src, size_t sld, int rows, int cols) {
        return q.parallel_for(sycl::range<2>((size_t)rows, (size_t)cols), [=](sycl::item<2> it) {
            dst[it[0] * dld + it[1]] = src[it[0] * sld + it[1]];
        });
    }
    // INK_SHARD: the other engine of a two-engine chain takes a copy of positions 0 .. S - 1 of this chain's full-context
    // applications (both directions), called on the last engine after a prompt of at least S + rel_extent positions
    void shard_start(int S) {
        const HParams &h = m.hp;
        if (!prev || prev->prev || prev->next != this) throw std::runtime_error("INK_SHARD: a chain of two engines");
        if (S <= 0 || S % (128 * fz::PVB) || S + h.rel_extent > n_past) throw std::runtime_error("INK_SHARD: a multiple of 16384 below the context");
        const int kd = h.n_head_kv * h.head_dim, nh = h.n_head, hd = h.head_dim;
        for (Engine *x : {prev, this}) {
            Engine &y = *x->partner();
            y.shard_Kp.resize(h.n_app, nullptr); y.shard_Vp.resize(h.n_app, nullptr);
            for (int a = x->a0; a < x->a1; ++a) {
                if (h.swa[a]) continue;
                if (!y.shard_Kp[a]) { y.shard_Kp[a] = y.d.alloc<sycl::half>((size_t)S * kd); y.shard_Vp[a] = y.d.alloc<sycl::half>((size_t)S * kd); }
                xcopy(y, y.shard_Kp[a], *x, x->Kc[a], (size_t)S * kd * sizeof(sycl::half));
                // the values, transposed (kd rows of the cache's vld positions): packed to rows of S in x's P (in pieces), then over
                const int per = (int)std::max<size_t>(1, std::min<size_t>(kd, x->p_floats * sizeof(float) / ((size_t)S * sizeof(sycl::half))));
                for (int c0 = 0; c0 < kd; c0 += per) {
                    const int nr = std::min(per, kd - c0);
                    sycl::half *tmp = &x->d == &y.d ? y.shard_Vp[a] + (size_t)c0 * S : (sycl::half *)x->P;
                    copy_rows(x->d.q, tmp, S, x->Vc[a] + (size_t)c0 * x->kvl[a], x->kvl[a], nr, S);
                    if (&x->d != &y.d) xcopy(y, y.shard_Vp[a] + (size_t)c0 * S, *x, tmp, (size_t)nr * S * sizeof(sycl::half));
                }
            }
            if (!x->fst) x->fst = x->d.alloc<float>((size_t)x->dec_rows * nh * (hd + 2));
            if (!x->shard_q) { x->shard_q = x->d.alloc<float>((size_t)x->dec_rows * nh * hd); x->shard_sink = x->d.alloc<float>((size_t)x->dec_rows * nh); }
        }
        prev->d.q.wait(); d.q.wait();
        prev->shard_S = shard_S = S;
    }
    // a writing step's attention of full-context application il for nt rows at p0.. (p0 >= shard_S + rel_extent): the other
    // engine folds blocks 0 .. SB - 1 into the state, this one SB .. from it (the chunked path's values)
    void shard_attn(int il, const Layer &l, const float *Qd, const float *td, const float *Rd, const float *sc, const float *gc, float *ac,
                    int p0, int nt, int nblk, float kscale) {
        const HParams &h = m.hp;
        const int nh = h.n_head, nkvh = h.n_head_kv, hd = h.head_dim, SB = shard_S / fz::PVB;
        Engine &y = *partner();
        if (nt > dec_rows || nt > y.dec_rows) throw std::runtime_error("engine: shard rows past the state buffer");
        xcopy(y, y.shard_q, *this, Qd, (size_t)nt * nh * hd * sizeof(float));
        xcopy(y, y.shard_sink, *this, sc, (size_t)nt * nh * sizeof(float));
        // (tab: any buffer; no key of the other engine is within the bias distances of these rows, so none is read)
        auto dec = [&](Engine &x, const float *q, const sycl::half *K, const float *tb, const float *rc, const float *rb, const sycl::half *Vt,
                       int vld, int km, int nbc, int b0) {
            if (nt <= 4) x.pr("attn_pv_full", fz::attn_flash_dec<3, 4, 1>(x.d.q, q, K, tb, rc, rb, h.n_rel, Vt, vld, p0, nt, nh, nkvh, hd,
                                                                         h.rel_extent, kscale, x.pvpart, x.pml, nbc, km, b0));
            else x.pr("attn_pv_full", fz::attn_flash_dec<3, 8, 1>(x.d.q, q, K, tb, rc, rb, h.n_rel, Vt, vld, p0, nt, nh, nkvh, hd,
                                                                 h.rel_extent, kscale, x.pvpart, x.pml, nbc, km, b0));
        };
        const int cby = (int)(y.dec_cap / nt / 128 * 128), cb = (int)(dec_cap / nt / 128 * 128);
        if (cby < 128 || cb < 128) throw std::runtime_error("engine: the parts buffer holds less than 128 blocks a row");
        for (int b0 = 0; b0 < SB; b0 += cby) {
            const int nbc = std::min(cby, SB - b0);
            dec(y, y.shard_q, y.shard_Kp[il], y.shard_q, nullptr, nullptr, y.shard_Vp[il], shard_S, 0x7fffffff, nbc, b0);
            y.pr("attn_pv_sum_full", fz::attn_flash_sum(y.d.q, y.pvpart, y.pml, nbc, p0, nt, nh, hd, y.shard_sink, nullptr, nullptr, b0, y.fst,
                                                        b0 > 0, 1));
        }
        // this engine's first piece is read while the other one works (its own parts buffer), then the state comes over
        const int nb1 = std::min(cb, nblk - SB);
        dec(*this, Qd, Kc[il], td, Rd, f32(l.rel_bias), Vc[il], kvl[il], kmask[il], nb1, SB);
        xcopy(*this, fst, y, y.fst, (size_t)nt * nh * (hd + 2) * sizeof(float));
        for (int b0 = SB; b0 < nblk; b0 += cb) {
            const int nbc = std::min(cb, nblk - b0);
            if (b0 > SB) dec(*this, Qd, Kc[il], td, Rd, f32(l.rel_bias), Vc[il], kvl[il], kmask[il], nbc, b0);
            pr("attn_pv_sum_full", fz::attn_flash_sum(d.q, pvpart, pml, nbc, p0, nt, nh, hd, sc, gc, ac, b0, fst, 1, b0 + nbc < nblk));
        }
    }

    std::vector<int> carry_set() const {
        std::vector<int> v = carry_slots(m.hp, a0);
        auto add = [&](int x) { if (x >= 0 && x < a0) v.push_back(x); };
        for (int x : extra_rows) add(x);
        if (feat)
            for (int j = 0; j < 3; ++j) add(feat_vis[j]);
        std::sort(v.begin(), v.end());
        v.erase(std::unique(v.begin(), v.end()), v.end());
        return v;
    }
    size_t carry_floats(int ntok, size_t nslots) const { return nslots * (size_t)ntok * (m.hp.n_embd + (mix_tab ? 1 + mix_nqa : 0)); }
    size_t carry_floats(int ntok) const { return carry_floats(ntok, carry_slots(m.hp, a1 < m.hp.n_app ? a1 : a0).size()); }
    void carry_copy(float *host, int ntok, bool out, const std::vector<int> &slots) {
        if (out ? a1 == m.hp.n_app : a0 == 0) throw std::runtime_error("engine: carry without a split");
        const size_t E = m.hp.n_embd, n = (size_t)ntok, nq = (size_t)mix_nqa;
        float *hp = host;
        auto cp = [&](float *dev, size_t cnt) {
            if (out) d.q.memcpy(hp, dev, sizeof(float) * cnt);
            else d.q.memcpy(dev, hp, sizeof(float) * cnt);
            hp += cnt;
        };
        for (int s : slots) {
            if (!lbuf[s]) {
                if (out) throw std::runtime_error("engine: carry of rows " + std::to_string(s) + " this engine does not keep");
                lbuf[s] = d.alloc<float>((size_t)m.hp.n_embd * T); // (the drafter's feature rows: allocated on first use)
            }
            cp(lbuf[s], n * E);
            if (mix_tab) { cp(tab_inv + (size_t)s * T, n); cp(tab_sc + (size_t)s * T * nq, n * nq); }
        }
        d.q.wait();
    }
    void carry_out(float *host, int ntok) { carry_copy(host, ntok, true, carry_slots(m.hp, a1)); }
    void carry_in(const float *host, int ntok) { carry_copy(const_cast<float *>(host), ntok, false, carry_slots(m.hp, a0)); }
    // the first engine's part of a step, its rows into this one's (prev; pull)
    void pull_rows(const int32_t *tok, int ntok) {
        prev->keep_states = keep_states;
        prev->step(tok, ntok);
        if (keep_states) prev->chk_n = ntok;
        const auto cs = carry_set();
        const size_t nf = carry_floats(ntok, cs.size());
        if (chost.size() < nf) chost.resize(nf);
        prev->carry_copy(chost.data(), ntok, true, cs);
        carry_copy(chost.data(), ntok, false, cs);
    }
    // checking guesses: one step of tok[0..n) (the last chosen token, then n - 1 guesses; n <= SB_MAX) that scores
    // every row and keeps every token's convolution states. Returns the greedy choice after each token (row i: the
    // token that follows tok[i]); steps of 1-8 tokens give each row the one-token values, so the choices are the
    // one-token text's. Then accept(a).
    std::vector<int32_t> check(const int32_t *tok, int n) {
        if (n < 1 || n > SB_MAX || n > T) throw std::runtime_error("check: 1 to " + std::to_string(SB_MAX) + " tokens");
        const bool al = all_logits, hl = host_logits;
        all_logits = true; host_logits = false; keep_states = true;
        const int p0 = n_past; // tok[0] goes at p0; row i chooses the token at p0 + 1 + i
        step(tok, n);
        all_logits = al; host_logits = hl; keep_states = false;
        if (samp.T > 0.0f) {
            ops::SampleArgs a = samp;
            for (int i = 0; i < n; ++i) a.u[i] = ops::sample_u(samp_seed, p0 + 1 + i);
            pr("sample", ops::sample_rows(d.q, lg, m.hp.vocab_padded, m.hp.vocab, n, a, cids));
        } else
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
        if (prev) prev->accept(a);
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
