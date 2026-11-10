// ---- DSpark draft on the cards (2026-11-10) ---------------------------------
// Included inside Backend41 after the multi-token step (f32 activations, OWN_TP > 1, threaded).
// The official DSpark draft of DeepSeek V4.1 Flash (Unsloth Q8_0 GGUF, dflash; tensors "dsp." in the weight
// table, split across the cards as the target's layers: backend tp_rows). Semantics: llama.cpp
// src/models/dflash.cpp graph_dsv41 + build_dspark_markov_head (read for semantics; credited in
// notes/2026-11-09-dsv41-multitoken-and-dspark-plan.md).
//
// The draft only proposes tokens: every guess is checked by the target (decode_verify_tp), which keeps only
// what it would have produced itself, so these steps need to be right, not bit-identical to anything.
//
// Per committed position p the draft keeps, in each of its 3 stages' 128-row window rings, the key row
// rope(norm_kv(wkv_s(norm_enc(fc(f_p))))) with f_p = the mean of the 4 streams at the input of target layers
// 37, 38, 39 (15360 values; captured in tpm_layer, injected for kept positions only: tpm_card_step after a
// prompt block, commit_block after a checked one). A draft step runs the block [anchor, MASK x 4] at
// positions pos .. pos + 4 through the 3 stages: every row attends (non-causally) to the window rows of
// positions pos - 128 .. pos - 1 plus the 5 block rows; single-pass stream mixing (a stage's attention input
// is the previous stage's FFN pre-mix, stage 0 takes stream 0; the FFN input uses the stage's attention
// pre-mix; the output collapses with the last FFN pre-mix); 128 MXFP4 experts, top 3. The head: output_norm,
// the target's output rows, then the Markov chain: row i's logits + markov_w2 . markov_w1[prev], prev = the
// anchor for row 0, else row i - 1's argmax; the 5 argmaxes are the guesses.

public:
static constexpr int DR_STAGES = 3, DR_BLOCK = 5, DR_MASK = 128799, DR_WIN = 128, DR_NIDX = 160;
bool dr_mxn = true; // OWN_DR_MXN=0: the draft's experts by the run-time-loop RoutedMXFP4 (same outputs)
private:
uint16_t *dring[TILES][DR_STAGES] = {}; // per stage: window rows (position p at row p % 128), block rows 128 ..
float *dfeat[TILES] = {};               // the block's target features [MTX][3 h] (layers 37 .. 39 inputs)
act_t *dmain[TILES] = {}, *dmainn[TILES] = {}, *dkv[TILES] = {}, *dkvn[TILES] = {}; // injection rows
int32_t *dprev[TILES] = {};             // [0] the anchor, [1 .. 5] the drafted tokens
int32_t h_dprev[8] = {};
float *dconf[TILES] = {};               // the draft's probability of each guess (DraftPick)
float h_dconf[8] = {};
int32_t dr_toks[MTX] = {};
bool dr_step = false;                   // the card threads run a draft step (tp_worker)
int dr_rows = DR_BLOCK;                 // head rows of this draft step (draft_tp's nrows)
unsigned xdrM = 0;                      // the Markov chain's argmax rows: DR_BLOCK rows of 6 cards x 4 floats

static constexpr size_t dr_arena_floats() { return (size_t)8 * 24; }
void dr_alloc(int c) {
    for (int s = 0; s < DR_STAGES; ++s) {
        dring[c][s] = dalloc<uint16_t>(c, (size_t)(DR_WIN + MTX) * g.hd);
        qs[c].memset(dring[c][s], 0, (size_t)(DR_WIN + MTX) * g.hd * 2);
    }
    dfeat[c] = dalloc<float>(c, (size_t)MTX * 3 * g.h);
    dmain[c] = dalloc<act_t>(c, (size_t)MTX * g.h);
    dmainn[c] = dalloc<act_t>(c, (size_t)MTX * g.h);
    dkv[c] = dalloc<act_t>(c, (size_t)MTX * g.hd);
    dkvn[c] = dalloc<act_t>(c, (size_t)MTX * g.hd);
    dprev[c] = dalloc<int32_t>(c, 8);
    dconf[c] = dalloc<float>(c, 8);
    qs[c].wait();
}
// the target's block features at layer L's input (tpm_layer, before the layer touches the streams)
void dr_capture(int L, int c) {
    if (!o.dspark || L < 37 || L > 39) return;
    const size_t H = g.h;
    launch(c, (size_t)mt_n * H, 64, ops41draft::StreamMeanM{(unsigned)g.h, (unsigned)mt_n, (unsigned)(L - 37), 4 * H, 3 * H},
           (const float *)strm[c], dfeat[c]);
}
// rows 0 .. n - 1 of the block's features into every stage's window ring at positions p0 .. p0 + n - 1 (card
// c's queue; needs mt_n == n for the token-row launches). staged: into the ring's block area (rows 128 + t)
// instead, for a checked block: commit_pending moves the kept ones to their window rows.
void dr_inject(int c, int n, long p0, bool staged = false) {
    if (n < 1 || n > MTX || mt_n != n) throw std::runtime_error("draft injection: rows");
    if (p0 < 0 || p0 + n > max_seq) throw std::runtime_error("draft injection: position beyond max_seq");
    const size_t H = g.h, hd = g.hd;
    gemv_m(c, "dsp.fc.weight", (const act_t *)dfeat[c], 3 * H, dmain[c], H, 0, (unsigned)n);
    rows_launch(c, tokr(ops41sycl::NormRows<5120, 4>{dmain[c], wp<float>(c, "dsp.enc.output_norm.weight"), dmainn[c]}, H, H));
    for (int s = 0; s < DR_STAGES; ++s) {
        const std::string p = "dsp.blk." + std::to_string(s) + ".";
        gemv_m(c, p + "attn_kv.weight", dmainn[c], H, dkv[c], hd, 0, (unsigned)n);
        rows_launch(c, tokr(ops41sycl::NormRows<512, 2>{dkv[c], wp<float>(c, p + "attn_kv_a_norm.weight"), dkvn[c]}, hd, hd));
        rows_launch(c, tokr(ops41sycl::RopeRows<Act>{dkvn[c], cos_base[c] + (size_t)p0 * 32, sin_base[c] + (size_t)p0 * 32,
                                                     1u, (unsigned)g.hd, false},
                            hd, 32));
        launch(c, (size_t)n * hd, 64, ops41draft::DraftKvRows<Act>{(unsigned)g.hd, (unsigned)n, (int)p0, staged},
               (const act_t *)dkvn[c], dring[c][s]);
    }
}
// routed rows of the draft's MXFP4 experts (3 slots per token), gate + up or down
void dr_routed(int c, const std::string &wn, const std::string &wn2, const act_t *x, size_t xtok, bool per_slot,
               act_t *y, act_t *y2) {
    const auto &e = we(wn);
    const auto &dp = wgt[c].at(wn);
    if (e.type != iq3::Type::MXFP4 || dp.packed || e.cols % 32) throw std::runtime_error("draft experts: form " + wn);
    const unsigned rows = dp.nrows, nsl = 3u * (unsigned)mt_n;
    const uint8_t *w2 = nullptr;
    if (!wn2.empty()) {
        const auto &dp2 = wgt[c].at(wn2);
        if (we(wn2).type != e.type || dp2.nrows != rows) throw std::runtime_error("draft experts: pair " + wn);
        w2 = (const uint8_t *)dp2.p;
    }
    const size_t np = (size_t)(w2 ? 2 : 1) * nsl * rows;
    auto gn = [&](auto nbc) { // OWN_DR_MXN=1 (default): the unrolled form at the draft's two widths
        constexpr unsigned NB = decltype(nbc)::value;
        ops41draft::RoutedMXFP4N<NB> k{rows, nsl, 3u, (unsigned)xtok, per_slot};
        k.nexp = (unsigned)e.experts;
        k.w2 = w2;
        k.out2 = y2;
        launch_rows<0>(c, np, 1024, k, (const uint8_t *)dp.p, (const float *)x, (const uint32_t *)scm[c][0].ids, y);
    };
    if (dr_mxn && e.cols == 5120) return gn(std::integral_constant<unsigned, 160>{});
    if (dr_mxn && e.cols == 2304) return gn(std::integral_constant<unsigned, 72>{});
    ops41draft::RoutedMXFP4 k{rows, (unsigned)e.cols, nsl, 3u, (unsigned)xtok, per_slot};
    k.nexp = (unsigned)e.experts;
    k.w2 = w2;
    k.out2 = y2;
    launch_rows<0>(c, np, 1024, k, (const uint8_t *)dp.p, (const float *)x, (const uint32_t *)scm[c][0].ids, y);
}
// one draft stage for the block (tpm_layer's block forms; no engram, compressor or indexer)
void dr_stage(int s, int c) {
    const int M = mt_n;
    const std::string p = "dsp.blk." + std::to_string(s) + ".";
    const int nh = thq1[c] - thq0[c];
    const size_t qo = (size_t)thq0[c] * g.hd, H = g.h;
    const Scratch &b = scm[c][0];
    const size_t H4 = 4 * H, Q = (size_t)g.qh * g.hd, FS = (size_t)25 * HC_SEG;
    using NR5 = ops41sycl::NormRows<5120, 4>;
    using HD = ops41sycl::TokRows<ops41sycl::HcDotsRows<5120, HC_SEG>>;
    auto dots = [&](const std::string &prefix) {
        return tokr(ops41sycl::HcDotsRows<5120, HC_SEG>{(const float *)strm[c], wp<float>(c, prefix + "fn.weight"), b.d25},
                    H4, FS);
    };
    // ---- phase 0: collapse (stage 0: stream 0 by the embed's [1, 0, 0, 0]) + norm, the mix, query / key rows
    if (!mx_ready[c])
        launch(c, (size_t)M * H, 32, ops41sycl::HcPreAM<Act>{g.h, (unsigned)M, H4, 4, H}, (const act_t *)strm[c],
               (const float *)b.cur_pre, b.x);
    rows_launch(c, ops41sycl::RowsPair<ops41sycl::TokRows<NR5>, HD>{
                       tokr(NR5{b.x, wp<float>(c, p + "attn_norm.weight"), b.xn}, H, H), dots(p + "hc_attn_")});
    mx_ready[c] = false;
    gemv_m(c, p + "attn_q_a.weight", b.xn, H, b.qa, g.qrank);
    gemv_m(c, p + "attn_kv.weight", b.xn, H, b.kv, g.hd);
    using N1 = ops41sycl::NormRows<1280, 4>;
    using N2 = ops41sycl::NormRows<512, 2>;
    {
        tok_set(c, 0);
        using FR = ops41sycl::TokRows<ops41sycl::HcFinishRows>;
        using R = ops41sycl::RowsPair<FR, ops41sycl::RowsPair<ops41sycl::TokRows<N1>, ops41sycl::TokRows<N2>>>;
        rows_launch(c, R{tokr(hc_finish(c, p + "hc_attn_", b.pre_a, b.post_a, b.comb_a), FS, 4, 4, 16),
                         {tokr(N1{b.qa, wp<float>(c, p + "attn_q_a_norm.weight"), b.qn}, g.qrank, g.qrank),
                          tokr(N2{b.kv, wp<float>(c, p + "attn_kv_a_norm.weight"), b.kvn}, g.hd, g.hd)}});
    }
    gemv_m(c, p + "attn_q_b.weight", b.qn, g.qrank, b.q + qo, Q);
    const float *cb = cos_base[c] + (size_t)pos * 32, *sbp = sin_base[c] + (size_t)pos * 32;
    {
        using RR = ops41sycl::TokRows<ops41sycl::RopeRows<Act>>;
        rows_launch(c, ops41sycl::RowsPair<RR, RR>{
                           tokr(ops41sycl::RopeRows<Act>{b.kvn, cb, sbp, 1u, (unsigned)g.hd, false}, g.hd, 32),
                           tokr(ops41sycl::RopeRows<Act>{b.q + qo, cb, sbp, (unsigned)nh, (unsigned)g.hd, false}, Q, 32)});
    }
    // ---- phase 1: attention over the stage's window + the whole block; output-a rows
    launch(c, (size_t)M * g.hd, 64, ops41draft::DraftKvRows<Act>{(unsigned)g.hd, (unsigned)M, 0, true},
           (const act_t *)b.kvn, dring[c][s]);
    {
        const int n_idx = DR_NIDX, W = DR_WIN + MTX;
        const uint16_t *kv = dring[c][s];
        if (!al16(kv)) throw std::runtime_error("draft: kv alignment");
        const float *sinks = wp<float>(c, p + "attn_sinks.weight") + thq0[c];
        const size_t WS = (size_t)g.qh * 640;
        const int32_t *ix = (const int32_t *)b.idxs_cat;
        const unsigned gpt = (unsigned)(nh * n_idx / 32);
        launch_sg(c, (size_t)M * gpt,
                  ops41sycl::ScoreM<ops41sycl::SparseScoreP<512>>{{n_idx, nh, W, g.hd}, gpt, (unsigned)M, Q, 640, WS},
                  (const act_t *)(b.q + qo), kv, kv, ix, b.attn_w);
        launch_sg(c, (size_t)M * nh,
                  ops41sycl::SoftmaxM<ops41sycl::SparseSoftmaxP<DR_NIDX>>{{nh}, (unsigned)nh, (unsigned)M, 640, WS}, sinks,
                  ix, b.attn_w);
        using SO = ops41sycl::SparseOutJB<512, 1, 16>;
        SO so{n_idx, nh, W};
        so.ry = (float *)(b.obuf + qo);
        so.cosb = cb;
        so.sinb = sbp;
        const unsigned gpo = (unsigned)(nh * g.hd / 64);
        launch_sg(c, (size_t)M * gpo, ops41sycl::OutM<SO>{so, gpo, (unsigned)M, 640, WS, Q, Q}, kv, kv, ix,
                  (const float *)b.attn_w, b.of + qo);
    }
    const unsigned per = (unsigned)g.ototal / 8;
    gemv_m(c, p + "attn_output_a.weight", b.obuf + (size_t)tog0[c] * g.oin, (size_t)g.qh * g.hd,
           xarena[c] + xoaM + (size_t)tog0[c] * per, (size_t)g.ototal, per);
    xchg_m(c, xoaM, (unsigned)g.ototal, (unsigned)M, tog0[c] * per, tog1[c] * per, 0, XP_OA);
    // ---- phase 2: output-b rows
    gemv_m(c, p + "attn_output_b.weight", xarena[c] + xoaM, (size_t)g.ototal, xarena[c] + xobM + td0[c], H);
    xchg_m(c, xobM, (unsigned)g.h, (unsigned)M, td0[c], td1[c], 0, XP_H);
    // ---- phase 3: stream post + FFN pre-norm (the attention pre-mix), router (top 3), shared and routed rows
    const float *bias = wp<float>(c, p + "exp_probs_b.bias");
    const int nm = tm1[c] - tm0[c], nd = td1[c] - td0[c];
    launch(c, (size_t)M * H, 64, ops41sycl::HcPostPrePM<Act>{g.h, (unsigned)M, H4, H, 4, 16, 0, 0, 4, H}, strm[c],
           (const act_t *)b.ob, (const float *)b.post_a, (const float *)b.comb_a, (const float *)nullptr, (float *)nullptr,
           (const float *)b.pre_a, b.x);
    rows_launch(c, ops41sycl::RowsPair<ops41sycl::TokRows<NR5>, HD>{
                       tokr(NR5{b.x, wp<float>(c, p + "ffn_norm.weight"), b.xn}, H, H), dots(p + "hc_ffn_")});
    gemv_m(c, p + "ffn_gate_inp.weight", b.xn, H, b.router, (size_t)g.experts);
    launch_wgs<2 * 1024 + 6>(c, (size_t)M, 512, ops41sycl::RoutePM{ops41sycl::RouteP{g.experts, 3}, (size_t)g.experts},
                             (const float *)b.router, bias, b.ids, b.prob);
    tok_set(c, 0);
    rows_launch(c, tokr(hc_finish(c, p + "hc_ffn_", b.pre_f, b.post_f, b.comb_f), FS, 4, 4, 16));
    gemv_m(c, p + "ffn_gate_shexp.weight", b.xn, H, b.shg, (size_t)g.mid);
    gemv_m(c, p + "ffn_up_shexp.weight", b.xn, H, b.shu, (size_t)g.mid);
    dr_routed(c, p + "ffn_gate_exps.weight", p + "ffn_up_exps.weight", b.xn, H, false, b.expg, b.expu);
    const size_t A7 = (size_t)7 * g.mid;
    launch(c, (size_t)M * 4 * nm, 64,
           ops41sycl::SwigluBothSM<Act>{3, nm, 10.0f, g.mid, (unsigned)M, (size_t)3 * nm, A7, 3, (size_t)g.mid, A7},
           (const act_t *)b.expg, (const act_t *)b.expu, b.act + tm0[c], (const float *)b.prob, (const act_t *)b.shg,
           (const act_t *)b.shu, b.act + (size_t)6 * g.mid + tm0[c]);
    xchg_m(c, xactM, (unsigned)g.mid, 7u * (unsigned)M, tm0[c], tm1[c], 0, XP_ACT);
    // ---- phase 4: routed and shared down, combine
    dr_routed(c, p + "ffn_down_exps.weight", std::string(), b.act, A7, true, b.expd, nullptr);
    gemv_m(c, p + "ffn_down_shexp.weight", b.act + (size_t)6 * g.mid, A7, b.shd, H);
    launch(c, (size_t)M * nd, 32, ops41sycl::MoeCombineAM<Act>{3, nd, (unsigned)M, (size_t)3 * nd, H, H},
           (const act_t *)b.expd, (const act_t *)b.shd, b.ob + td0[c]);
    xchg_m(c, xobM, (unsigned)g.h, (unsigned)M, td0[c], td1[c], 0, XP_H);
    // ---- phase 5: stream post + the next collapse with this FFN pre-mix (the next stage's attention input,
    // or after the last stage the draft's output)
    launch(c, (size_t)M * H, 64, ops41sycl::HcPostPrePM<Act>{g.h, (unsigned)M, H4, H, 4, 16, 4, 4, 4, H}, strm[c],
           (const act_t *)b.ob, (const float *)b.post_f, (const float *)b.comb_f, (const float *)b.pre_f, b.cur_pre,
           (const float *)b.pre_f, b.x);
    mx_ready[c] = true;
}
// output norm, this card's logits rows (the target's output.weight), the Markov chain: row i's token from
// every card's best (DraftBest -> exchange -> DraftPick), the next row's bias from it
void dr_head(int c) {
    const int M = dr_rows; // the head for the rows whose guesses are used (the stages ran all mt_n block rows)
    const Scratch &b = scm[c][0];
    const size_t H = g.h;
    if (!mx_ready[c]) throw std::runtime_error("draft head: no collapse");
    rows_launch(c, tokr(ops41sycl::NormRows<5120, 4>{b.x, wp<float>(c, "dsp.output_norm.weight"), b.xn}, H, H));
    const int nl = tv1[c] - tv0[c], G = (nl + AM_CH - 1) / AM_CH;
    gemv_m(c, "output.weight", b.xn, H, tlogm[c], (size_t)nl, 0, (unsigned)M);
    qs[c].memcpy(dprev[c], dr_toks, 4);
    const uint16_t *w1 = wp<uint16_t>(c, "dsp.markov_w1.weight"), *w2 = wp<uint16_t>(c, "dsp.markov_w2.weight");
    for (int i = 0; i < M; ++i) {
        float *li = tlogm[c] + (size_t)i * nl;
        launch_sg(c, (size_t)nl, ops41draft::MarkovAdd{(unsigned)nl, (unsigned)g.vocab}, w2, w1, (const int32_t *)(dprev[c] + i), li);
        launch_sg(c, (size_t)G, ops41sycl::ArgmaxP1OM{{nl, AM_CH, tv0[c], g.vocab}, (unsigned)G, 1u, (size_t)nl},
                  (const float *)li, tamvm[c], tamim[c]);
        const unsigned off = xdrM + (unsigned)i * 24;
        launch_sg(c, 1, ops41draft::DraftBest{(unsigned)G}, (const float *)tamvm[c], (const int32_t *)tamim[c],
                  xarena[c] + off + 4 * c);
        launch_wgs<1>(c, 1, 512, ops41draft::DraftSumExp{(unsigned)nl}, (const float *)li, xarena[c] + off + 4 * c);
        xchg(c, off, 24, 1, 4u * c, 4u * c + 4, 0, 0, -1);
        launch(c, 32, 32, ops41draft::DraftPick{(unsigned)o.tp, 4}, (const float *)(xarena[c] + off), dprev[c] + i + 1,
               dconf[c] + i);
    }
    if (c == 0) {
        qs[c].memcpy(h_dprev, dprev[c], 8 * 4);
        qs[c].memcpy(h_dconf, dconf[c], 8 * 4);
    }
    twait(c);
}
void dr_card_step(int c) {
    sc_keep[c] = sc[c];
    streams_keep[c] = streams[c];
    try {
        commit_pending(c); // first: the draft's block rows below reuse the ring's block area
        mx_ready[c] = false;
        tpm_embed(c); // [anchor, MASK x 4]: x and the 4 streams per row, the collapse weights [1, 0, 0, 0]
        launch(c, (size_t)mt_n * DR_NIDX, 64, ops41draft::DraftIdx{(int)pos, mt_n, DR_NIDX, 640}, scm[c][0].idxs_cat);
        for (int s = 0; s < DR_STAGES; ++s) dr_stage(s, c);
        dr_head(c);
    } catch (...) {
        tok_end(c);
        throw;
    }
    tok_end(c);
}
public:
// The draft's guesses for the text after the committed position pos: the block [anchor, MASK x 4] at pos ..
// pos + 4 (anchor = the target's token for pos, not yet run by the target); out[0 .. 4] = the 5 guesses.
// Every position before pos must have been injected (prompt blocks, commit_block).
void draft_tp(int32_t anchor, int32_t *out, int nrows = DR_BLOCK, float *conf = nullptr) {
    if (nrows < 1 || nrows > DR_BLOCK) throw std::runtime_error("draft_tp: 1..5 guesses");
    dr_rows = nrows;
    if (!o.dspark || !mt_small || o.tp < 2 || tp_th.empty()) throw std::runtime_error("draft_tp: needs the draft, OWN_TP > 1, block forms");
    if (vpos0 >= 0) throw std::runtime_error("draft_tp: a checked block is not committed");
    if (pos + DR_BLOCK > max_seq) throw std::runtime_error("draft_tp: position beyond max_seq");
    dr_toks[0] = anchor;
    for (int i = 1; i < DR_BLOCK; ++i) dr_toks[i] = DR_MASK;
    mt_n = DR_BLOCK;
    mt_toks = dr_toks;
    dr_step = true;
    tp_abort = false;
    {
        std::lock_guard<std::mutex> lk(tp_mu);
        tp_err.clear();
        tp_left = o.tp;
        ++tp_gen;
    }
    tp_cv.notify_all();
    {
        std::unique_lock<std::mutex> lk(tp_mu);
        tp_done_cv.wait(lk, [&] { return tp_left == 0; });
    }
    mt_n = 0;
    dr_step = false;
    if (!tp_err.empty()) throw std::runtime_error("draft step: " + tp_err);
    for (int c = 0; c < o.tp; ++c)
        if (xerr[c][0])
            throw std::runtime_error("card " + pci[c] + ": card-to-card exchange timed out waiting for card " +
                                     std::to_string((int)xerr[c][0] - 1));
    for (int i = 0; i < DR_BLOCK; ++i) // a token outside the vocabulary (never from a sane chain) becomes 0
        out[i] = i < nrows && h_dprev[i + 1] >= 0 && h_dprev[i + 1] < g.vocab ? h_dprev[i + 1] : 0;
    if (conf)
        for (int i = 0; i < DR_BLOCK; ++i) conf[i] = i < nrows ? h_dconf[i] : 0.0f;
}
private:
