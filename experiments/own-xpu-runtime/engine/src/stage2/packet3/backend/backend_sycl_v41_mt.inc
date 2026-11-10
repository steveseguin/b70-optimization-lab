// ---- multi-token tensor-parallel step (prompt blocks) ----------------------
// Included inside Backend41 (f32-activation build, OWN_TP > 1, threaded).
// A block of mt_n tokens at positions pos .. pos + mt_n - 1 runs layer by layer
// on every card. Weight rows run once for all tokens (the kernels' rowm: each
// token's operations, order and reduction unchanged); every per-token piece
// runs the one-token code on that token's own buffers (tok_set) in token order.
// So every value is the one-token step's value, bit for bit. The attention runs
// token by token: token t's window append follows token t-1's attention, so the
// 128-row ring never runs ahead of a reader.

int mt_n = 0;                    // tokens in the running block (0: one-token steps)
const int32_t *mt_toks = nullptr;
Scratch scm[TILES][MTX] = {};    // per-token views of the block's buffers
Scratch sc_keep[TILES] = {};
act_t *strm[TILES] = {}, *streams_keep[TILES] = {};
act_t *tengm[TILES][2] = {};
std::vector<act_t> h_engm[TILES][2];
int32_t *cidxm[TILES][8] = {};   // one 512-row list per token per index slot
uint32_t *egrp[TILES] = {};      // the layer's expert groups (RUGrp layout, mt_eu)
long mlen[TILES][4][MTX] = {};   // rows of each kv source after token t's publish
unsigned xoaM = 0, xobM = 0, xactM = 0, xengM = 0;
uint32_t eng_seqm[TILES] = {};
float *pkv[TILES][3] = {}, *psc[TILES][3] = {}; // the block's ratio-2 states per source (row 0: the carried even one)
// the head for every token of a block (draft checking): logits rows of this card, argmax candidates
bool mt_heads = false;
float *tlogm[TILES] = {}, *tamvm[TILES] = {};
int32_t *tamim[TILES] = {};
std::vector<float> h_amvm[TILES];
std::vector<int32_t> h_amim[TILES];
long vpos0 = -1; // the position of a checked block's first token until commit_block
bool pend[TILES] = {};             // commit_block's card work not yet run on card c (commit_pending)
long pend_p0 = 0;
int pend_n = 0;
bool pend_state = false;
void commit_pending(int c) {
    if (!pend[c]) return;
    pend[c] = false;
    if (pend_state)
        for (int si = 0; si < 3; ++si) {
            const size_t so = (size_t)si * 2 * g.hd;
            qs[c].memcpy(sc[c].kv_state + so, pkv[c][si] + (size_t)pend_n * g.hd, (size_t)g.hd * 4);
            qs[c].memcpy(sc[c].score_state + so, psc[c][si] + (size_t)pend_n * g.hd, (size_t)g.hd * 4);
        }
    for (int L = o.layer_begin; L < o.layer_end; ++L) // the kept tokens' window rows (left in the block area)
        launch(c, (size_t)pend_n * g.hd, 64, ops41sycl::RingCommitM{128, g.hd, (int)pend_p0, pend_n}, ring[c][L]);
    if (o.dspark) // the draft's rows of the kept tokens (staged by the checking step; a dropped one's row would
        for (int s = 0; s < DR_STAGES; ++s) // overwrite position - 128, which the next draft still reads)
            launch(c, (size_t)pend_n * g.hd, 64, ops41sycl::RingCommitM{128, g.hd, (int)pend_p0, pend_n}, dring[c][s]);
}
bool mx_ready[TILES] = {};
static constexpr float k_pm1[4] = {1, 0, 0, 0};
public:
bool mt_small = true; // the per-token small launches as one launch per block (OWN_MT_SMALL=0: one per token)
private:
// rows of R for every token of the block, token t's pointers moved by t * the strides (TokRows)
template <typename R> ops41sycl::TokRows<R> tokr(R r, size_t s0, size_t s1 = 0, size_t s2 = 0, size_t s3 = 0) const {
    return {r, (unsigned)mt_n, {s0, s1, s2, s3}};
}
// small row launches (norms, mix finishes, rope of a few tokens) as one sub-group per work-group when there
// are at most mt_rwg rows (OWN_MT_RWG): 16 rows in one 512-wide group all ran on one core
template <typename R> void rows_launch(int c, R r) {
    if (r.n() <= mt_rwg) launch_rows<0, 32>(c, r.n(), 0, ops41sycl::RowsP<R>{r});
    else launch_rows<0>(c, r.n(), 0, ops41sycl::RowsP<R>{r});
}
public:
int mt_xpush = 1;      // block exchanges: 0 XchgP's one group, 1 XchgPushM, 2 XchgPushD (a group per peer)
unsigned mt_xgpp = 4;  // XchgPushD: work-groups per peer
unsigned mt_tg = 0;      // OWN_MT_TG=1/2/4: dense rows run token groups of that many on separate sub-groups (0: off)
unsigned mt_tg_max = 8;  // ... for blocks of at most this many tokens (OWN_MT_TG_MAX)
unsigned mt_tgm[MTX + 1] = {}; // OWN_MT_TGM="m:g,...": dense token groups g (1-4) for blocks of exactly m tokens
                               // (overrides OWN_MT_TG for that m; 9 = all tokens in one sub-group, DenseRowsM)
unsigned mt_tgu = 0;     // OWN_MT_TGU=1/2/3: the unpacked rows (GemvTM) in token groups over sub-groups (0: all 16 at once)
bool mt_ride = false;    // OWN_MT_RIDE=1: the stream mix's dot rows ride in q_a's and the router's launches
unsigned mt_rwg = 0;     // OWN_MT_RWG=n: row launches of at most n rows use one sub-group per work-group (rows_launch)
unsigned mt_eu = 0;      // OWN_MT_EU=6: routed rows expert-major (RoutedU, groups of at most 6 slots; 0: slot-major)
bool mt_idstat = false; // OWN_MT_IDSTAT=1: count distinct experts per block and layer on card 0 (diagnostic, waits)
long ids_picks = 0, ids_unique = 0, ids_blocks = 0; // block exchanges: the push over many work-groups (OWN_MT_XPUSH=0: XchgP's one group)
private:
// xchg for a block: the stores by XchgPushM, then XchgP without slots for the release, flags and wait
uint32_t xchg_m(int c, unsigned off, unsigned stride, unsigned nslot, unsigned r0, unsigned r1, int mode, int part) {
    if (!mt_xpush || use_pull(part, nslot)) return xchg(c, off, stride, nslot, r0, r1, mode, 0, part);
    if ((r1 - r0) % 4) throw std::runtime_error("multi-token exchange: rows not a multiple of 4");
    const size_t nv = (size_t)nslot * ((r1 - r0) / 4);
    const size_t nwg = std::max<size_t>(1, std::min<size_t>(64, (nv + 2047) / 2048));
    float *P[6] = {};
    for (int d = 0; d < o.tp; ++d) P[d] = (float *)xpeer[c][d];
    if (mt_xpush == 2) {
        const unsigned gpp = std::max(1u, std::min<unsigned>(mt_xgpp, (unsigned)((nv + 255) / 256)));
        launch(c, (size_t)gpp * (o.tp - 1) * 256, 256, ops41sycl::XchgPushD{o.tp, c, off, stride, nslot, r0, r1, gpp},
               P[0], P[1], P[2], P[3], P[4], P[5]);
    } else
        launch(c, nwg * 256, 256, ops41sycl::XchgPushM{o.tp, c, off, stride, nslot, r0, r1}, P[0], P[1], P[2], P[3],
               P[4], P[5]);
    return xchg(c, off, stride, 0, r0, r1, mode);
}
// ngr work-groups of wg items with SLM floats of local memory each (RoutePM)
template <size_t SLM, typename K, typename... A> void launch_wgs(int c, size_t ngr, size_t wg, K k, A... args) {
    auto e = qs[c].submit([&](sycl::handler &hh) {
        sycl::local_accessor<float, 1> lt(SLM, hh);
        hh.parallel_for(sycl::nd_range<1>(ngr * wg, wg), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] {
            k(it, args..., &lt[0]);
        });
    });
    kev(c, kname<K>(), e);
}

size_t mt_arena_floats() const { // the block's exchange regions, after the one-token ones
    return (size_t)MTX * ((size_t)g.ototal + (size_t)g.h + 7 * (size_t)g.mid + 10 * (size_t)g.h) + dr_arena_floats();
}
void mt_offsets(size_t base) {
    xoaM = (unsigned)base;
    xobM = xoaM + MTX * (unsigned)g.ototal;
    xactM = xobM + MTX * (unsigned)g.h;
    xengM = xactM + MTX * 7 * (unsigned)g.mid; // [token][engram layer] rows of 5 * h
    xdrM = xengM + MTX * 10 * (unsigned)g.h;   // the draft's argmax rows (backend_sycl_v41_draft.inc)
}
void mt_alloc(int c) {
    auto md = [&](size_t n) { return dalloc<act_t>(c, n * MTX); };
    auto mf = [&](size_t n) { return dalloc<float>(c, n * MTX); };
    const size_t H = g.h, Q = (size_t)g.qh * g.hd, nm = (size_t)(tm1[c] - tm0[c]), nd = (size_t)(td1[c] - td0[c]);
    act_t *x = md(H), *xn = md(H), *qa = md(g.qrank), *qn = md(g.qrank), *q = md(Q), *kv = md(g.hd), *kvn = md(g.hd);
    act_t *qi = md(32 * 128), *wv = md(32);
    float *score = mf((size_t)max_seq + 64);
    int64_t *lens = dalloc<int64_t>(c, MTX);
    float *router = mf(g.experts), *prob = mf(6);
    uint32_t *ids = dalloc<uint32_t>(c, 6 * MTX);
    act_t *expg = md(6 * nm), *expu = md(6 * nm), *expd = md(6 * nd), *shg = md(g.mid), *shu = md(g.mid), *shd = md(H);
    float *of = mf(Q), *attn_w = mf((size_t)g.qh * 640);
    act_t *obuf = md(Q), *cw = md(g.hd), *scg = md(g.hd), *latent = md(g.hd), *kk = md(128);
    float *pa = mf(4), *qa4 = mf(4), *ca = mf(16), *pf = mf(4), *qf = mf(4), *cf = mf(16), *cur = mf(4);
    double *d25 = dalloc<double>(c, (size_t)25 * HC_SEG * MTX);
    float *rs = mf(g.experts), *rsb = mf(g.experts);
    int32_t *cat = dalloc<int32_t>(c, (size_t)640 * MTX), *widx = dalloc<int32_t>(c, (size_t)128 * MTX);
    act_t *old = md(4 * H);
    uint8_t *cand = dalloc<uint8_t>(c, ((size_t)max_seq + 64) * MTX);
    strm[c] = md(4 * H);
    for (int t = 0; t < MTX; ++t) {
        Scratch s = sc[c]; // kv_state, score_state, warm, eng_rows, kvbuf stay the card's own
        s.x = x + t * H; s.xn = xn + t * H;
        s.qa = qa + (size_t)t * g.qrank; s.qn = qn + (size_t)t * g.qrank; s.q = q + t * Q;
        s.kv = kv + (size_t)t * g.hd; s.kvn = kvn + (size_t)t * g.hd;
        s.qi = qi + (size_t)t * 4096; s.wv = wv + (size_t)t * 32;
        s.score = score + (size_t)t * ((size_t)max_seq + 64); s.lens = lens + t;
        s.router = router + (size_t)t * g.experts; s.ids = ids + 6 * t; s.prob = prob + 6 * t;
        s.expg = expg + t * 6 * nm; s.expu = expu + t * 6 * nm; s.expd = expd + t * 6 * nd;
        s.shg = shg + (size_t)t * g.mid; s.shu = shu + (size_t)t * g.mid; s.shd = shd + t * H;
        s.of = of + t * Q; s.attn_w = attn_w + (size_t)t * g.qh * 640; s.obuf = obuf + t * Q;
        s.cw = cw + (size_t)t * g.hd; s.scg = scg + (size_t)t * g.hd; s.latent = latent + (size_t)t * g.hd;
        s.kk = kk + (size_t)t * 128;
        s.pre_a = pa + 4 * t; s.post_a = qa4 + 4 * t; s.comb_a = ca + 16 * t;
        s.pre_f = pf + 4 * t; s.post_f = qf + 4 * t; s.comb_f = cf + 16 * t; s.cur_pre = cur + 4 * t;
        s.d25 = d25 + (size_t)t * 25 * HC_SEG;
        s.rs = rs + (size_t)t * g.experts; s.rsb = rsb + (size_t)t * g.experts;
        s.idxs_cat = cat + (size_t)t * 640; s.widx = widx + (size_t)t * 128;
        s.old = old + t * 4 * H;
        s.cand = cand + (size_t)t * ((size_t)max_seq + 64);
        s.oa = xarena[c] + xoaM + (size_t)t * g.ototal;
        s.ob = xarena[c] + xobM + (size_t)t * H;
        s.act = xarena[c] + xactM + (size_t)t * 7 * g.mid;
        s.sha = s.act + (size_t)6 * g.mid;
        scm[c][t] = s;
    }
    for (int li = 0; li < 2; ++li) {
        tengm[c][li] = dalloc<act_t>(c, (size_t)24 * g.engram_dim * MTX);
        h_engm[c][li].resize((size_t)24 * g.engram_dim * MTX);
    }
    for (int k = 0; k < 8; ++k) cidxm[c][k] = dalloc<int32_t>(c, (size_t)512 * MTX);
    egrp[c] = dalloc<uint32_t>(c, ops41sycl::RUGrp::WORDS);
    if (o.dspark) dr_alloc(c);
    for (int k = 0; k < 3; ++k) {
        pkv[c][k] = dalloc<float>(c, (size_t)(MTX + 1) * g.hd);
        psc[c][k] = dalloc<float>(c, (size_t)(MTX + 1) * g.hd);
    }
    if (o.head) {
        const int nl = tv1[c] - tv0[c], G = (nl + AM_CH - 1) / AM_CH;
        tlogm[c] = dalloc<float>(c, (size_t)nl * MTX);
        tamvm[c] = dalloc<float>(c, (size_t)G * MTX);
        tamim[c] = dalloc<int32_t>(c, (size_t)G * MTX);
        h_amvm[c].resize((size_t)G * MTX);
        h_amim[c].resize((size_t)G * MTX);
    }
}
void tok_set(int c, int t) {
    sc[c] = scm[c][t];
    streams[c] = strm[c] + (size_t)t * 4 * g.h;
    tokoff[c] = t;
}
void tok_end(int c) {
    sc[c] = sc_keep[c];
    streams[c] = streams_keep[c];
    tokoff[c] = 0;
}

// ---- weight rows for all tokens (rowm) ------------------------------------
// y + t * ys = rows of the matrix (this card's slice when split) . (x + t * xs), t < mt_n
// rider: other rows in the same launch, first (OWN_MT_RIDE: the stream mix's double dot rows behind a matrix)
template <typename DK, typename RD = ops41sycl::NoRows>
void dense_m(int c, DK dk, const void *w, const act_t *x, size_t xs, act_t *y, size_t ys, unsigned mt = 0,
             const RD &rider = {}) {
    if (!mt) mt = (unsigned)mt_n;
    auto go = [&](const auto &d) {
        using D = std::decay_t<decltype(d)>;
        if constexpr (std::is_same_v<RD, ops41sycl::NoRows>) launch_rows<0>(c, d.n(), 0, ops41sycl::RowsP<D>{d});
        else {
            const ops41sycl::RowsPair<RD, D> rp{rider, d};
            launch_rows<0>(c, rp.n(), 0, ops41sycl::RowsP<ops41sycl::RowsPair<RD, D>>{rp});
        }
    };
    auto split = [&](auto gc) { // token groups of G over sub-groups (DenseRowsG)
        constexpr unsigned G = decltype(gc)::value;
        go(ops41sycl::DenseRowsG<DK, G>{dk, (const uint8_t *)w, x, xs, y, ys, mt, (mt + G - 1) / G});
    };
    const unsigned tg = mt <= MTX && mt_tgm[mt] ? mt_tgm[mt] : mt <= mt_tg_max && mt > mt_tg ? mt_tg : 0;
    if (tg == 1) return split(std::integral_constant<unsigned, 1>{});
    if (tg == 2) return split(std::integral_constant<unsigned, 2>{});
    if (tg == 3) return split(std::integral_constant<unsigned, 3>{});
    if (tg == 4) return split(std::integral_constant<unsigned, 4>{});
    go(ops41sycl::DenseRowsM<DK, MTX>{dk, (const uint8_t *)w, x, xs, y, ys, mt});
}
// (mt: tokens, default the block's; the publish runs its pooled rows only; rider: see dense_m, packed rows only)
template <typename RD = ops41sycl::NoRows>
void gemv_m(int c, const std::string &wn, const act_t *x, size_t xs, act_t *y, size_t ys, unsigned xn = 0,
            unsigned mt = 0, const RD &rider = {}) {
    if (!mt) mt = (unsigned)mt_n;
    const auto &e = we(wn);
    const auto &dp = wgt[c].at(wn);
    if (!dp.packed) { // the generic per-format rows (GemvT's rowm), whole matrix
        if (xn) throw std::runtime_error("multi-token step: grouped unpacked rows " + wn);
        if constexpr (!std::is_same_v<RD, ops41sycl::NoRows>) rows_launch(c, rider);
        const unsigned rows = (unsigned)e.rows, cols = (unsigned)e.cols;
        if (o.packed && e.type == iq3::Type::F32 && cols == 5120) // gemv's block-read F32 rows
            return dense_m(c, ops41sycl::GemvF32P<160, Act>{rows}, wp(c, wn), x, xs, y, ys, mt, ops41sycl::NoRows{});
        auto tgu = [&](auto ty, auto gc) { // OWN_MT_TGU: tokens in groups over sub-groups
            constexpr iq3::Type TY = decltype(ty)::value;
            constexpr unsigned G = decltype(gc)::value;
            const unsigned ng = (mt + G - 1) / G;
            launch_sg(c, (size_t)rows * ng, ops41sycl::GemvTMG<TY, Act, G>{{rows, cols, false}, xs, ys, mt, ng},
                      (const uint8_t *)wp(c, wn), x, (void *)y);
        };
        switch (e.type) {
#define X(TY)                                                                                            \
    case iq3::Type::TY:                                                                                    \
        if (mt_tgu == 1) return tgu(std::integral_constant<iq3::Type, iq3::Type::TY>{}, std::integral_constant<unsigned, 1>{}); \
        if (mt_tgu == 2) return tgu(std::integral_constant<iq3::Type, iq3::Type::TY>{}, std::integral_constant<unsigned, 2>{}); \
        if (mt_tgu == 3) return tgu(std::integral_constant<iq3::Type, iq3::Type::TY>{}, std::integral_constant<unsigned, 3>{}); \
        launch_sg(c, rows, ops41sycl::GemvTM<iq3::Type::TY, Act, MTX>{{rows, cols, false}, xs, ys, mt}, \
                  (const uint8_t *)wp(c, wn), x, (void *)y);                                               \
        return;
            X(F32) X(BF16) X(Q8_0)
#undef X
        default: throw std::runtime_error("multi-token step: no unpacked rows form for " + wn);
        }
    }
    const unsigned rows = dp.nrows, cols = (unsigned)e.cols;
#define XQ(COLS)                                                                                           \
    if (cols == COLS) return dense_m(c, ops41sycl::GemvQ8P<COLS / 32, Act>{rows, xn}, dp.p, x, xs, y, ys, mt, rider);
#define X(KERN, NB)                                                                                        \
    if (cols == NB * 256) return dense_m(c, ops41sycl::KERN<NB, Act>{rows, xn}, dp.p, x, xs, y, ys, mt, rider);
    if (e.type == iq3::Type::Q8_0) { XQ(1280) XQ(2304) XQ(4096) XQ(5120) XQ(8192) XQ(15360) }
    if (e.type == iq3::Type::Q6_K) { X(GemvQ6KP, 5) X(GemvQ6KP, 16) X(GemvQ6KP, 20) X(GemvQ6KP, 24) X(GemvQ6KP, 32) }
    if (e.type == iq3::Type::Q5_K) { X(GemvQ5KP, 9) X(GemvQ5KP, 20) }
    if (e.type == iq3::Type::F32 && cols == 5120 && !xn)
        return dense_m(c, ops41sycl::GemvH16P<160, Act>{rows}, dp.p, x, xs, y, ys, mt, rider);
#undef X
#undef XQ
    throw std::runtime_error("multi-token step: no packed kernel for " + wn);
}
// the stream-mix dot rows of every token (HcMixDotsP rows, fn values read once)
void hc_dots_m(int c, const std::string &prefix) {
    using R = ops41sycl::HcDotsRowsM<5120, HC_SEG, MTX>;
    const R r{(const float *)strm[c], (size_t)4 * g.h, wp<float>(c, prefix + "fn.weight"), scm[c][0].d25,
              (size_t)25 * HC_SEG, (unsigned)mt_n};
    launch_rows<0>(c, r.n(), 0, ops41sycl::RowsP<R>{r});
}
// routed gate + up (and down) for 6 * mt_n slots: slot s is token s / 6's choice s % 6
template <typename EX = ops41sycl::NoRows>
void routed_m(int c, const std::string &wn, const std::string &wn2, const act_t *x, size_t xtok, const uint32_t *ids,
              act_t *y, act_t *y2, bool per_slot) {
    const auto &e = we(wn);
    const auto &dp = wgt[c].at(wn);
    const unsigned nsl0 = 6u * (unsigned)mt_n;
    if (!dp.packed) { // the generic per-format kernel (layer 0's Q2_K down rows)
        if (!wn2.empty()) throw std::runtime_error("multi-token step: unpacked expert pair " + wn);
        const unsigned rows = dp.nrows, cols = (unsigned)e.cols;
        switch (e.type) {
#define X(TY)                                                                                              \
    case iq3::Type::TY:                                                                                    \
        launch_sg(c, (size_t)nsl0 * rows,                                                                  \
                  ops41sycl::RoutedGemvT<iq3::Type::TY, Act>{rows, cols, per_slot, nsl0, (unsigned)xtok},  \
                  wp(c, wn), x, ids, y);                                                                     \
        return;
            OWN41_WEIGHT_TYPES(X)
#undef X
        default: throw std::runtime_error("unsupported weight format: " + wn);
        }
    }
    const uint8_t *w2 = nullptr;
    if (!wn2.empty()) {
        const auto &e2 = we(wn2);
        const auto &dp2 = wgt[c].at(wn2);
        if (!dp2.packed || e2.type != e.type || e2.cols != e.cols || dp2.nrows != dp.nrows)
            throw std::runtime_error("multi-token step: expert pair shape " + wn);
        w2 = (const uint8_t *)dp2.p;
    }
    const unsigned rows = dp.nrows, nsl = 6u * (unsigned)mt_n;
    const size_t npos = (size_t)(w2 ? 2 : 1) * nsl * rows;
    const size_t maxwg = per_slot ? (size_t)o.down_wg : (size_t)o.pair_wg;
    auto go = [&](auto kt) {
        using K = typename decltype(kt)::type;
        K k{rows, per_slot};
        k.w2 = w2;
        k.out2 = y2;
        k.nsl = nsl;
        k.xtok = (unsigned)xtok;
        launch_rows<K::TAB>(c, npos, maxwg, k, (const uint8_t *)dp.p, x, ids, y);
    };
    using namespace ops41sycl;
    const unsigned cols = (unsigned)e.cols;
    if (mt_eu) { // expert-major: the layer's groups (ExpertGroupM, tpm_layer) in place of the ids; grid for nu = nsl
        if (mt_eu > 6) throw std::runtime_error("OWN_MT_EU: groups of at most 6 slots (the kernels' MT)");
        auto gu = [&](auto kt) {
            using K = typename decltype(kt)::type;
            K k{rows, per_slot};
            k.w2 = w2;
            k.out2 = y2;
            k.nsl = nsl;
            k.xtok = (unsigned)xtok;
            launch_rows<K::TAB>(c, npos, maxwg, k, (const uint8_t *)dp.p, x, (const uint32_t *)egrp[c], y);
        };
#define XU(TY, KERN, NB) \
    if (e.type == iq3::Type::TY && cols == NB * 256) return gu(std::type_identity<KERN<NB, 6>>{});
        XU(IQ2_XXS, RoutedIQ2XXSU, 20) XU(IQ2_S, RoutedIQ2SU, 20) XU(IQ3_XXS, RoutedIQ3XXSU, 20) XU(IQ2_XS, RoutedIQ2XSU, 20)
        XU(IQ1_S, RoutedIQ1SU, 20) XU(IQ2_XXS, RoutedIQ2XXSU, 9) XU(IQ2_S, RoutedIQ2SU, 9) XU(IQ3_XXS, RoutedIQ3XXSU, 9)
        XU(IQ2_XS, RoutedIQ2XSU, 9) XU(IQ1_S, RoutedIQ1SU, 9)
#undef XU
        throw std::runtime_error("multi-token step: no expert-major routed kernel for " + wn);
    }
#define X(TY, KERN, NB)                                                                                    \
    if (e.type == iq3::Type::TY && cols == NB * 256) return go(std::type_identity<KERN<NB, Act>>{});
#define X1(NB)                                                                                             \
    if (e.type == iq3::Type::IQ1_S && cols == NB * 256) return go(std::type_identity<RoutedIQ1SP<NB, Act, true>>{});
    X(IQ2_XXS, RoutedIQ2XXSP, 20) X(IQ2_S, RoutedIQ2SP, 20) X(IQ3_XXS, RoutedIQ3XXSP, 20) X(IQ2_XS, RoutedIQ2XSP, 20) X1(20)
    X(IQ2_XXS, RoutedIQ2XXSP, 9) X(IQ2_S, RoutedIQ2SP, 9) X(IQ3_XXS, RoutedIQ3XXSP, 9) X(IQ2_XS, RoutedIQ2XSP, 9) X1(9)
#undef X1
#undef X
    throw std::runtime_error("multi-token step: no packed routed kernel for " + wn);
}

// ---- step pieces ------------------------------------------------------------
void tpm_engram_prefetch() {
    const long keep = pos;
    for (int t = 0; t < mt_n; ++t) {
        pos = keep + t;
        engram_prefetch();
    }
    pos = keep;
}
void tpm_engram_upload(int c) {
    auto l = iq3::layout(iq3::Type::Q5_K);
    const size_t per = (size_t)24 * g.engram_dim;
    for (int li = 0; li < 2; ++li) {
        const int L = li == 0 ? 1 : 14;
        if (L < o.layer_begin || L >= o.layer_end || !eng_base[li]) continue;
        std::vector<act_t> &rows = h_engm[c][li]; // the embed's twait below finishes the copy before any reuse
        for (int t = 0; t < mt_n; ++t) {
            const long p_ = pos + t;
            if ((long)comp_ids.size() <= p_) throw std::runtime_error("comp_ids behind position");
            int64_t ids[24];
            engram_hash((int)p_, li, ids);
            for (int k = 0; k < 24; ++k) {
                const uint8_t *row = eng_base[li] + (size_t)ids[k] * l.bytes;
                for (int i = 0; i < 256; ++i)
                    rows[t * per + k * 256 + i] = Act::wr(iq3::decode(iq3::Type::Q5_K, row, i));
            }
        }
        qs[c].memcpy(tengm[c][li], rows.data(), (size_t)mt_n * per * sizeof(act_t));
    }
}
void tpm_embed(int c) {
    const auto &te = we("token_embd.weight");
    for (int t = 0; t < mt_n; ++t) {
        tok_set(c, t);
        const uint8_t *row = (const uint8_t *)wgt[c].at("token_embd.weight").p + (size_t)mt_toks[t] * wrb(te);
        launch(c, g.h, 32, ops41sycl::EmbedRowA<Act>{te.type, g.h}, row, sc[c].x);
        launch(c, g.h, 32, ops41sycl::Broadcast4A<Act>{g.h}, (const act_t *)sc[c].x, streams[c]);
        qs[c].memcpy(sc[c].cur_pre, k_pm1, 16);
    }
    tok_end(c);
    twait(c);
}
void tpm_engram_kv(int c) {
    if (!o.eng_split) throw std::runtime_error("multi-token step needs OWN_ENG_SPLIT=1");
    bool any = false;
    for (int li = 0; li < 2; ++li) {
        const int L = li == 0 ? 1 : 14;
        if (L < o.layer_begin || L >= o.layer_end || !eng_base[li]) continue;
        gemv_m(c, "blk." + std::to_string(L) + ".engram_kv.weight", tengm[c][li], (size_t)24 * g.engram_dim,
               xarena[c] + xengM + (size_t)li * 5 * g.h + te0[c], (size_t)10 * g.h);
        any = true;
    }
    if (any) eng_seqm[c] = xchg_m(c, xengM, 5u * (unsigned)g.h, 2u * (unsigned)mt_n, te0[c], te1[c], 1, XP_ENG);
}

// publish_tp for every token of the block: ratio 1 (layer 20) publishes every position, ratio 2 the odd ones
// (each pooled with the even position before it: the block's own row, or the carried state at a block
// that starts odd). The same kernels' rows per published row; mlen = rows after each token.
void tpm_publish(int L, int c, int si, bool yarn) {
    const int M = mt_n;
    const Scratch &b = scm[c][0];
    const std::string p = "blk." + std::to_string(L) + ".";
    const size_t hd = (size_t)g.hd;
    if (g.hd != 512 || !o.small_fast) throw std::runtime_error("multi-token publish: form");
    const long tl0 = tlen[c][si];
    const float *ct = yarn ? cos_yarn[c] : cos_base[c], *st = yarn ? sin_yarn[c] : sin_base[c];
    unsigned np;   // rows published
    long gpos0;    // position of the first
    size_t pstep;  // positions between them
    gemv_m(c, p + "attn_compressor_kv.weight", b.xn, g.h, b.cw, hd);
    if (cr_of(L) == 1) {
        rows_launch(c, tokr(ops41sycl::NormRows<512, 2>{b.cw, wp<float>(c, p + "attn_compressor_norm.weight"), b.latent},
                            hd, hd));
        np = (unsigned)M;
        gpos0 = pos;
        pstep = 1;
        for (int t = 0; t < M; ++t) mlen[c][si][t] = tl0 + t + 1;
    } else {
        gemv_m(c, p + "attn_compressor_gate.weight", b.xn, g.h, b.scg, hd);
        const size_t so = (size_t)si * 2 * hd;
        launch(c, (size_t)(M + 1) * hd, 64, ops41sycl::StatePackM<Act>{g.hd, (unsigned)M}, (const act_t *)b.cw,
               (const act_t *)b.scg, (const float *)(sc[c].kv_state + so), (const float *)(sc[c].score_state + so),
               pkv[c][si], psc[c][si]);
        const unsigned t0 = (unsigned)(pos % 2 == 1 ? 0 : 1); // the first odd position's token
        np = t0 < (unsigned)M ? ((unsigned)M - t0 + 1) / 2 : 0;
        long n_ = tl0;
        for (int t = 0; t < M; ++t) {
            if ((pos + t) % 2 == 1) ++n_;
            mlen[c][si][t] = n_;
        }
        if ((pos + M - 1) % 2 == 0) { // the last token is even: its state carries to the next step (slot 0)
            qs[c].memcpy(sc[c].kv_state + so, pkv[c][si] + (size_t)M * hd, hd * 4);
            qs[c].memcpy(sc[c].score_state + so, psc[c][si] + (size_t)M * hd, hd * 4);
        }
        if (!np) return;
        launch_wgs<1024>(c, np, 32, ops41sycl::CompressPoolPM<Act>{{2, g.hd}, t0, np}, (const float *)pkv[c][si],
                         (const float *)psc[c][si], wp<float>(c, p + "attn_compressor_norm.weight"), b.latent);
        gpos0 = pos + t0 - 1;
        pstep = 2;
    }
    const size_t cap = si == 3 ? (size_t)max_seq + 2 : (size_t)max_seq / 2 + 2;
    if ((size_t)tl0 + np > cap) throw std::runtime_error("compressed cache full (max_seq)");
    if (gpos0 < 0 || gpos0 + (long)pstep * (np - 1) >= max_seq) throw std::runtime_error("position beyond max_seq");
    gemv_m(c, p + "indexer.attn_k.weight", b.latent, hd, b.kk, 128, 0, np);
    launch_sg(c, np, ops41sycl::RmsNormA<Act>{128}, (const act_t *)b.kk, wp<float>(c, p + "indexer.k_norm.weight"), b.kk);
    using RR = ops41sycl::TokRows<ops41sycl::RopeRows<Act>>;
    const float *cb = ct + (size_t)gpos0 * 32, *sb = st + (size_t)gpos0 * 32;
    rows_launch(c, ops41sycl::RowsPair<RR, RR>{RR{{b.kk, cb, sb, 1u, 128u, false}, np, {128, 32 * pstep, 0, 0}},
                                               RR{{b.latent, cb, sb, 1u, (unsigned)g.hd, false}, np, {hd, 32 * pstep, 0, 0}}});
    launch(c, (size_t)np * std::max(g.hd, 128), 64, ops41sycl::PubAppendAM<Act>{g.hd, 128, (int)tl0, np},
           (const act_t *)b.latent, (const act_t *)b.kk, ckv_mirror[c][si], ik_mirror[c][si]);
    tlen[c][si] = tl0 + np;
}
// every token's index list at once (dev_index's steps, one launch each for the block): tokens whose source
// has at most 512 rows take all of them in order, the others score + select on the card
void tpm_index(int L, int c, int si, bool yarn, int slot) {
    const int M = mt_n;
    const Scratch &b = scm[c][0];
    const std::string p = "blk." + std::to_string(L) + ".";
    ops41sycl::CidxFillM cf{};
    cf.m = (unsigned)M;
    int lens[16] = {}, nshort = 0, nlong = 0;
    long lmax = 0;
    for (int t = 0; t < M; ++t) {
        const long len = mlen[c][si][t];
        if (len > (long)INT32_MAX / 2) throw std::runtime_error("multi-token index: rows");
        cf.lens[t] = len <= 512 ? (int)len : -1;
        lens[t] = len > 512 ? (int)len : 0;
        (len <= 512 ? nshort : nlong)++;
        lmax = std::max(lmax, len);
    }
    if (nshort) launch(c, (size_t)M * 512, 64, cf, cidxm[c][slot]);
    if (!nlong) return;
    sync_rows(c, si);
    gemv_m(c, p + "indexer.attn_q_b.weight", b.qn, g.qrank, b.qi, 4096);
    {
        const float *cb = (yarn ? cos_yarn[c] : cos_base[c]) + (size_t)pos * 32;
        const float *sbp = (yarn ? sin_yarn[c] : sin_base[c]) + (size_t)pos * 32;
        rows_launch(c, tokr(ops41sycl::RopeRows<Act>{b.qi, cb, sbp, 32u, 128u, false}, 4096, 32));
    }
    gemv_m(c, p + "indexer.proj.weight", b.xn, g.h, b.wv, 32);
    const size_t SS = (size_t)max_seq + 64; // per-token score / candidate stride (mt_alloc)
    {
        using KS = ops41sycl::IndexerScoreBM<Act>;
        constexpr size_t WG = 128;
        const unsigned gpt = (unsigned)((((lmax + 31) / 32 * 32) + WG - 1) / WG);
        KS k{};
        for (int t = 0; t < M; ++t) k.lens[t] = lens[t];
        k.m = (unsigned)M;
        k.gpt = gpt;
        k.qs = 4096;
        k.ws = 32;
        k.ss = SS;
        const act_t *qi = b.qi, *wv = b.wv;
        const uint16_t *ik = ik_mirror[c][si];
        float *sco = b.score;
        auto e = qs[c].submit([&](sycl::handler &hh) {
            sycl::local_accessor<float, 1> lt(32 * 128 + 32, hh);
            hh.parallel_for(sycl::nd_range<1>((size_t)M * gpt * WG, WG),
                            [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(16)]] { k(it, qi, ik, wv, sco, &lt[0]); });
        });
        kev(c, kname<KS>(), e);
    }
    using KR = ops41sycl::TopKSelP<false>;
    constexpr size_t SLM = (size_t)KR::NSG * 256 + 8;
    if (L == 20) {
        ops41sycl::TopKSelM<true> kb{};
        for (int t = 0; t < M; ++t) kb.lens[t] = lens[t];
        kb.m = (unsigned)M;
        kb.ss = SS;
        kb.cs = SS;
        launch_wgs<SLM>(c, (size_t)M, KR::WG, kb, (const float *)b.score, b.cand, (int32_t *)nullptr);
    }
    ops41sycl::TopKSelM<false> kt{};
    for (int t = 0; t < M; ++t) kt.lens[t] = lens[t];
    kt.m = (unsigned)M;
    kt.mask = L > 20;
    kt.ss = SS;
    kt.cs = SS;
    launch_wgs<SLM>(c, (size_t)M, KR::WG, kt, (const float *)b.score, b.cand, cidxm[c][slot]);
}
void tpm_layer(int L, int c) {
    const int M = mt_n;
    const std::string p = "blk." + std::to_string(L) + ".";
    const int cr = cr_of(L);
    const bool yarn = cr > 0;
    const int si = src_index(L);
    const int nh = thq1[c] - thq0[c];
    const size_t qo = (size_t)thq0[c] * g.hd, H = g.h;
    const Scratch &b = scm[c][0]; // token 0's views are the bases of the block's arrays
    const size_t H4 = 4 * H, Q = (size_t)g.qh * g.hd, FS = (size_t)25 * HC_SEG;
    if (g.hd != 512) throw std::runtime_error("multi-token step: head dim");
    using NR5 = ops41sycl::NormRows<5120, 4>;
    // the mix's dot rows, one sub-group per (token, row): HcDotsRowsM's one sub-group for all tokens left the
    // card mostly idle (a serial double chain 16 times as long)
    using HD = ops41sycl::TokRows<ops41sycl::HcDotsRows<5120, HC_SEG>>;
    auto dots = [&](const std::string &prefix) {
        return tokr(ops41sycl::HcDotsRows<5120, HC_SEG>{(const float *)strm[c], wp<float>(c, prefix + "fn.weight"), b.d25},
                    H4, FS);
    };
    if (g.h != 5120 || g.qrank != 1280) throw std::runtime_error("multi-token step: model width");
    dr_capture(L, c); // the draft's input features (layers 37 .. 39; read only)
    // ---- phase 0: pre-norm, mix, query/key rows, publish, index
    if (L == 1 || L == 14) {
        const int li = L == 1 ? 0 : 1;
        if (use_pull(XP_ENG, 2u * (unsigned)M) || xseq[c] == eng_seqm[c])
            xchg(c, xengM, 5u * (unsigned)g.h, 2u * (unsigned)M, te0[c], te1[c], 2, eng_seqm[c], XP_ENG);
        if (mt_small) {
            launch_sg(c, (size_t)4 * M, ops41sycl::EngramGatePM{ops41sycl::EngramGateP{g.h}, (unsigned)M, H4, 10 * H},
                      strm[c], (const float *)(xarena[c] + xengM + (size_t)li * 5 * H),
                      wp<float>(c, p + "engram_gate.weight"));
        } else {
            for (int t = 0; t < M; ++t) {
                tok_set(c, t);
                launch_sg(c, 4, ops41sycl::EngramGateP{g.h}, streams[c],
                          (const float *)(xarena[c] + xengM + ((size_t)t * 2 + li) * 5 * H),
                          wp<float>(c, p + "engram_gate.weight"));
            }
        }
    }
    if (mt_small) { // collapse (unless the last phase 5 did) + norm, with the mix's dot rows in the norm's launch
        if (!mx_ready[c])
            launch(c, (size_t)M * H, 32, ops41sycl::HcPreAM<Act>{g.h, (unsigned)M, H4, 4, H}, (const act_t *)strm[c],
                   (const float *)b.cur_pre, b.x);
        if (mt_ride) // the dot rows ride in q_a's launch below
            rows_launch(c, tokr(NR5{b.x, wp<float>(c, p + "attn_norm.weight"), b.xn}, H, H));
        else
            rows_launch(c, ops41sycl::RowsPair<ops41sycl::TokRows<NR5>, HD>{
                               tokr(NR5{b.x, wp<float>(c, p + "attn_norm.weight"), b.xn}, H, H), dots(p + "hc_attn_")});
    } else {
        for (int t = 0; t < M; ++t) {
            tok_set(c, t);
            if (mx_ready[c]) rmsnorm(c, sc[c].x, p + "attn_norm.weight", g.h, sc[c].xn);
            else pre_norm(c, (const float *)sc[c].cur_pre, p + "attn_norm.weight");
        }
        hc_dots_m(c, p + "hc_attn_");
        for (int t = 0; t < M; ++t) {
            tok_set(c, t);
            auto &s = sc[c];
            launch_rows<0>(c, 1, 0, ops41sycl::RowsP<ops41sycl::HcFinishRows>{hc_finish(c, p + "hc_attn_", s.pre_a, s.post_a, s.comb_a)});
        }
    }
    mx_ready[c] = false;
    if (mt_small && mt_ride) gemv_m(c, p + "attn_q_a.weight", b.xn, H, b.qa, g.qrank, 0, 0, dots(p + "hc_attn_"));
    else gemv_m(c, p + "attn_q_a.weight", b.xn, H, b.qa, g.qrank);
    gemv_m(c, p + "attn_kv.weight", b.xn, H, b.kv, g.hd);
    using N1 = ops41sycl::NormRows<1280, 4>;
    using N2 = ops41sycl::NormRows<512, 2>;
    if (mt_small) { // the mix's finish + both norms
        tok_set(c, 0);
        using FR = ops41sycl::TokRows<ops41sycl::HcFinishRows>;
        using R = ops41sycl::RowsPair<FR, ops41sycl::RowsPair<ops41sycl::TokRows<N1>, ops41sycl::TokRows<N2>>>;
        rows_launch(c, R{tokr(hc_finish(c, p + "hc_attn_", b.pre_a, b.post_a, b.comb_a), FS, 4, 4, 16),
                         {tokr(N1{b.qa, wp<float>(c, p + "attn_q_a_norm.weight"), b.qn}, g.qrank, g.qrank),
                          tokr(N2{b.kv, wp<float>(c, p + "attn_kv_a_norm.weight"), b.kvn}, g.hd, g.hd)}});
    } else {
        using NR = ops41sycl::RowsPair<N1, N2>;
        for (int t = 0; t < M; ++t) {
            tok_set(c, t);
            auto &s = sc[c];
            const NR nr{{s.qa, wp<float>(c, p + "attn_q_a_norm.weight"), s.qn},
                        {s.kv, wp<float>(c, p + "attn_kv_a_norm.weight"), s.kvn}};
            launch_rows<0>(c, nr.n(), 0, ops41sycl::RowsP<NR>{nr});
        }
    }
    gemv_m(c, p + "attn_q_b.weight", b.qn, g.qrank, b.q + qo, Q);
    if (pos < 0 || pos + M > max_seq) throw std::runtime_error("position beyond max_seq");
    if (mt_small) { // key and query rope, every token (positions pos .. pos + M - 1: 32 table entries apart)
        const float *cb = (yarn ? cos_yarn[c] : cos_base[c]) + (size_t)pos * 32;
        const float *sbp = (yarn ? sin_yarn[c] : sin_base[c]) + (size_t)pos * 32;
        using RR = ops41sycl::TokRows<ops41sycl::RopeRows<Act>>;
        rows_launch(c, ops41sycl::RowsPair<RR, RR>{
                           tokr(ops41sycl::RopeRows<Act>{b.kvn, cb, sbp, 1u, (unsigned)g.hd, false}, g.hd, 32),
                           tokr(ops41sycl::RopeRows<Act>{b.q + qo, cb, sbp, (unsigned)nh, (unsigned)g.hd, false}, Q, 32)});
    } else {
        for (int t = 0; t < M; ++t) {
            tok_set(c, t);
            auto &s = sc[c];
            const float *cb = (yarn ? cos_yarn[c] : cos_base[c]) + (size_t)cpos(c) * 32;
            const float *sbp = (yarn ? sin_yarn[c] : sin_base[c]) + (size_t)cpos(c) * 32;
            launch_rows<0>(c, 1, 0, ops41sycl::RowsP<ops41sycl::RopeRows<Act>>{{s.kvn, cb, sbp, 1u, (unsigned)g.hd, false}});
            launch_rows<0>(c, (size_t)nh, 0,
                           ops41sycl::RowsP<ops41sycl::RopeRows<Act>>{{s.q + qo, cb, sbp, (unsigned)nh, (unsigned)g.hd, false}});
        }
    }
    if (cr && is_kv_source(L) && mt_small)
        tpm_publish(L, c, si, yarn);
    else if (cr && is_kv_source(L))
        for (int t = 0; t < M; ++t) {
            tok_set(c, t);
            publish_tp(L, c, si, yarn);
            mlen[c][si][t] = tlen[c][si];
        }
    if (cr && index_slot(L) >= 0 && mt_small && !o.dev_index_check) {
        tpm_index(L, c, si, yarn, index_slot(L));
    } else if (cr && index_slot(L) >= 0) {
        const int slot = index_slot(L);
        for (int t = 0; t < M; ++t) {
            tok_set(c, t);
            const long len = mlen[c][si][t];
            int32_t *out = cidxm[c][slot] + (size_t)t * 512;
            if (len <= 512) launch(c, 512, 64, ops41sycl::CidxFill{(int)len, 512}, out);
            else dev_index(L, c, si, yarn, len, out);
        }
    }
    // ---- phase 1: attention; output-a rows for all tokens
    if (mt_small) { // every token at once: the block's key rows wait in the ring's block area until all have read
        const int nc = cr ? 512 : 0, n_idx = 128 + nc, W = 128 + MTX;
        launch(c, (size_t)M * std::max(g.hd, n_idx), 64,
               ops41sycl::WindowAppendM<Act>{128, g.hd, (int)pos, nc, M, MTX, (size_t)g.hd, 512, 640}, ring[c][L],
               (const act_t *)b.kvn, b.idxs_cat, (const int32_t *)(cr ? cidxm[c][isrc_for(L)] : nullptr));
        const uint16_t *kvw = ring[c][L], *kvc = cr ? ckv_mirror[c][si] : ring[c][L];
        if (!al16(kvw) || !al16(kvc)) throw std::runtime_error("multi-token step: kv alignment");
        const float *sinks = wp<float>(c, p + "attn_sinks.weight") + thq0[c];
        const size_t WS = (size_t)g.qh * 640;
        const int32_t *ix = (const int32_t *)b.idxs_cat;
        if (n_idx == 128) {
            const unsigned gpt = (unsigned)(nh * n_idx / 32);
            launch_sg(c, (size_t)M * gpt,
                      ops41sycl::ScoreM<ops41sycl::SparseScoreP<512>>{{n_idx, nh, W, g.hd}, gpt, (unsigned)M, Q, 640, WS},
                      (const act_t *)(b.q + qo), kvw, kvc, ix, b.attn_w);
            launch_sg(c, (size_t)M * nh,
                      ops41sycl::SoftmaxM<ops41sycl::SparseSoftmaxP<128>>{{nh}, (unsigned)nh, (unsigned)M, 640, WS}, sinks,
                      ix, b.attn_w);
        } else {
            const unsigned gpt = (unsigned)((nh / 4) * (n_idx / 32));
            launch_sg(c, (size_t)M * gpt,
                      ops41sycl::ScoreM<ops41sycl::SparseScoreHG<512, 4>>{{n_idx, nh, W, g.hd}, gpt, (unsigned)M, Q, 640, WS},
                      (const act_t *)(b.q + qo), kvw, kvc, ix, b.attn_w);
            launch_sg(c, (size_t)M * nh,
                      ops41sycl::SoftmaxM<ops41sycl::SparseSoftmaxP<640>>{{nh}, (unsigned)nh, (unsigned)M, 640, WS}, sinks,
                      ix, b.attn_w);
        }
        using SO = ops41sycl::SparseOutJB<512, 1, 16>;
        SO so{n_idx, nh, W};
        so.ry = (float *)(b.obuf + qo);
        so.cosb = (yarn ? cos_yarn[c] : cos_base[c]) + (size_t)pos * 32;
        so.sinb = (yarn ? sin_yarn[c] : sin_base[c]) + (size_t)pos * 32;
        const unsigned gpo = (unsigned)(nh * g.hd / 64);
        launch_sg(c, (size_t)M * gpo, ops41sycl::OutM<SO>{so, gpo, (unsigned)M, 640, WS, Q, Q}, kvw, kvc, ix,
                  (const float *)b.attn_w, b.of + qo);
        // draft checking: the rows move into the ring at commit_block, kept tokens only (a dropped token's row
        // would overwrite position - 128, which the next tokens' windows still read)
        if (!mt_heads) launch(c, (size_t)M * g.hd, 64, ops41sycl::RingCommitM{128, g.hd, (int)pos, M}, ring[c][L]);
    } else
    for (int t = 0; t < M; ++t) {
        tok_set(c, t);
        auto &s = sc[c];
        int n_idx = 128;
        if (cr) {
            launch(c, (size_t)std::max(g.hd, 512), 64, ops41sycl::WindowAppendP<Act>{128, g.hd, (int)cpos(c), 512},
                   ring[c][L], (const act_t *)s.kvn, s.widx, s.idxs_cat,
                   (const int32_t *)(cidxm[c][isrc_for(L)] + (size_t)t * 512));
            n_idx += 512;
        } else {
            launch(c, (size_t)std::max(g.hd, 128), 64, ops41sycl::WindowAppendP<Act>{128, g.hd, (int)cpos(c), 0},
                   ring[c][L], (const act_t *)s.kvn, s.widx, s.idxs_cat, (const int32_t *)nullptr);
        }
        const uint16_t *kvw = ring[c][L], *kvc = cr ? ckv_mirror[c][si] : ring[c][L];
        if (!al16(kvw) || !al16(kvc)) throw std::runtime_error("multi-token step: kv alignment");
        const float *sinks = wp<float>(c, p + "attn_sinks.weight") + thq0[c];
        const int32_t *ix = (const int32_t *)s.idxs_cat;
        if (n_idx == 128) {
            launch_sg(c, (size_t)nh * n_idx / 32, ops41sycl::SparseScoreP<512>{n_idx, nh, 128, g.hd},
                      (const act_t *)(s.q + qo), kvw, kvc, ix, s.attn_w);
            launch_sg(c, nh, ops41sycl::SparseSoftmaxP<128>{nh}, sinks, ix, s.attn_w);
        } else {
            launch_sg(c, (size_t)(nh / 4) * (n_idx / 32), ops41sycl::SparseScoreHG<512, 4>{n_idx, nh, 128, g.hd},
                      (const act_t *)(s.q + qo), kvw, kvc, ix, s.attn_w);
            launch_sg(c, nh, ops41sycl::SparseSoftmaxP<640>{nh}, sinks, ix, s.attn_w);
        }
        const float *cb = (yarn ? cos_yarn[c] : cos_base[c]) + (size_t)cpos(c) * 32;
        const float *sbp = (yarn ? sin_yarn[c] : sin_base[c]) + (size_t)cpos(c) * 32;
        ops41sycl::SparseOutJB<512, 1, 16> so{n_idx, nh, 128};
        so.ry = (float *)(s.obuf + qo);
        so.cosb = cb;
        so.sinb = sbp;
        launch_sg(c, (size_t)nh * g.hd / 64, so, kvw, kvc, ix, (const float *)s.attn_w, s.of + qo);
    }
    const unsigned per = (unsigned)g.ototal / 8;
    gemv_m(c, p + "attn_output_a.weight", b.obuf + (size_t)tog0[c] * g.oin, (size_t)g.qh * g.hd,
           xarena[c] + xoaM + (size_t)tog0[c] * per, (size_t)g.ototal, per);
    xchg_m(c, xoaM, (unsigned)g.ototal, (unsigned)M, tog0[c] * per, tog1[c] * per, 0, XP_OA);
    // ---- phase 2: output-b rows
    gemv_m(c, p + "attn_output_b.weight", xarena[c] + xoaM, (size_t)g.ototal, xarena[c] + xobM + td0[c], H);
    xchg_m(c, xobM, (unsigned)g.h, (unsigned)M, td0[c], td1[c], 0, XP_H);
    // ---- phase 3: stream post + FFN pre-norm, router, shared and routed gate/up, SwiGLU
    const float *bias = wp<float>(c, p + "exp_probs_b.bias");
    const int nm = tm1[c] - tm0[c], nd = td1[c] - td0[c];
    if (mt_small) {
        launch(c, (size_t)M * H, 64, ops41sycl::HcPostPrePM<Act>{g.h, (unsigned)M, H4, H, 4, 16, 0, 0, 4, H},
               strm[c], (const act_t *)b.ob, (const float *)b.post_a, (const float *)b.comb_a, (const float *)nullptr,
               (float *)nullptr, (const float *)b.pre_a, b.x);
        if (mt_ride) { // the dot rows ride in the router's launch
            rows_launch(c, tokr(NR5{b.x, wp<float>(c, p + "ffn_norm.weight"), b.xn}, H, H));
            gemv_m(c, p + "ffn_gate_inp.weight", b.xn, H, b.router, (size_t)g.experts, 0, 0, dots(p + "hc_ffn_"));
        } else {
            rows_launch(c, ops41sycl::RowsPair<ops41sycl::TokRows<NR5>, HD>{
                               tokr(NR5{b.x, wp<float>(c, p + "ffn_norm.weight"), b.xn}, H, H), dots(p + "hc_ffn_")});
            gemv_m(c, p + "ffn_gate_inp.weight", b.xn, H, b.router, (size_t)g.experts);
        }
        launch_wgs<2 * 1024 + 6>(c, (size_t)M, 512, ops41sycl::RoutePM{ops41sycl::RouteP{g.experts, 6}, (size_t)g.experts},
                                 (const float *)b.router, bias, b.ids, b.prob);
        tok_set(c, 0);
        rows_launch(c, tokr(hc_finish(c, p + "hc_ffn_", b.pre_f, b.post_f, b.comb_f), FS, 4, 4, 16));
    } else {
        for (int t = 0; t < M; ++t) {
            tok_set(c, t);
            auto &s = sc[c];
            launch(c, (size_t)g.h, 64, ops41sycl::HcPostPreP<Act>{g.h}, streams[c], (const act_t *)s.ob,
                   (const float *)s.post_a, (const float *)s.comb_a, (const float *)nullptr, (float *)nullptr,
                   (const float *)s.pre_a, s.x);
            rmsnorm(c, s.x, p + "ffn_norm.weight", g.h, s.xn);
        }
        hc_dots_m(c, p + "hc_ffn_");
        gemv_m(c, p + "ffn_gate_inp.weight", b.xn, H, b.router, (size_t)g.experts);
        for (int t = 0; t < M; ++t) {
            tok_set(c, t);
            auto &s = sc[c];
            launch_local<2 * 1024 + 6>(c, 512, ops41sycl::RouteP{g.experts, 6}, (const float *)s.router, bias, s.ids, s.prob);
            launch_rows<0>(c, 1, 0, ops41sycl::RowsP<ops41sycl::HcFinishRows>{hc_finish(c, p + "hc_ffn_", s.pre_f, s.post_f, s.comb_f)});
        }
    }
    if (mt_idstat && c == 0) {
        std::vector<uint32_t> hid((size_t)6 * M);
        qs[c].memcpy(hid.data(), b.ids, hid.size() * 4).wait();
        std::sort(hid.begin(), hid.end());
        ids_picks += (long)hid.size();
        ids_unique += (long)(std::unique(hid.begin(), hid.end()) - hid.begin());
        if (L == 0) ++ids_blocks;
    }
    if (mt_eu) // the slots' expert groups for the expert-major routed rows (gate / up and down share them)
        launch_local<ops41sycl::ExpertGroupM::LM>(c, ops41sycl::ExpertGroupM::WG,
                                                  ops41sycl::ExpertGroupM{6u * (unsigned)M, mt_eu},
                                                  (const uint32_t *)b.ids, egrp[c]);
    gemv_m(c, p + "ffn_gate_shexp.weight", b.xn, H, b.shg, (size_t)g.mid);
    gemv_m(c, p + "ffn_up_shexp.weight", b.xn, H, b.shu, (size_t)g.mid);
    routed_m(c, p + "ffn_gate_exps.weight", p + "ffn_up_exps.weight", b.xn, H, b.ids, b.expg, b.expu, false);
    const size_t A7 = (size_t)7 * g.mid;
    if (mt_small) {
        launch(c, (size_t)M * 7 * nm, 64,
               ops41sycl::SwigluBothSM<Act>{6, nm, 10.0f, g.mid, (unsigned)M, (size_t)6 * nm, A7, 6, (size_t)g.mid, A7},
               (const act_t *)b.expg, (const act_t *)b.expu, b.act + tm0[c], (const float *)b.prob, (const act_t *)b.shg,
               (const act_t *)b.shu, b.act + (size_t)6 * g.mid + tm0[c]);
    } else {
        for (int t = 0; t < M; ++t) {
            tok_set(c, t);
            auto &s = sc[c];
            launch(c, (size_t)7 * nm, 64, ops41sycl::SwigluBothS<Act>{6, nm, 10.0f, g.mid}, (const act_t *)s.expg,
                   (const act_t *)s.expu, s.act + tm0[c], (const float *)s.prob, (const act_t *)s.shg, (const act_t *)s.shu,
                   s.act + (size_t)6 * g.mid + tm0[c]);
        }
    }
    xchg_m(c, xactM, (unsigned)g.mid, 7u * (unsigned)M, tm0[c], tm1[c], 0, XP_ACT);
    // ---- phase 4: routed and shared down, combine
    routed_m(c, p + "ffn_down_exps.weight", std::string(), b.act, A7, b.ids, b.expd, nullptr, true);
    gemv_m(c, p + "ffn_down_shexp.weight", b.act + (size_t)6 * g.mid, A7, b.shd, H);
    if (mt_small) {
        launch(c, (size_t)M * nd, 32, ops41sycl::MoeCombineAM<Act>{6, nd, (unsigned)M, (size_t)6 * nd, H, H},
               (const act_t *)b.expd, (const act_t *)b.shd, b.ob + td0[c]);
    } else {
        for (int t = 0; t < M; ++t) {
            tok_set(c, t);
            auto &s = sc[c];
            launch(c, nd, 32, ops41sycl::MoeCombineA<Act>{6, nd}, (const act_t *)s.expd, (const act_t *)s.shd, s.ob + td0[c]);
        }
    }
    xchg_m(c, xobM, (unsigned)g.h, (unsigned)M, td0[c], td1[c], 0, XP_H);
    // ---- phase 5: stream post (+ the next attention's collapse)
    const int Ln = L + 1;
    const bool pp = post_pre_ok() && Ln != 1 && Ln != 14 && (Ln < o.layer_end || o.head);
    if (mt_small) {
        if (pp)
            launch(c, (size_t)M * H, 64, ops41sycl::HcPostPrePM<Act>{g.h, (unsigned)M, H4, H, 4, 16, 4, 4, 4, H},
                   strm[c], (const act_t *)b.ob, (const float *)b.post_f, (const float *)b.comb_f,
                   (const float *)b.pre_f, b.cur_pre, (const float *)b.pre_f, b.x);
        else
            launch(c, (size_t)M * H, 64, ops41sycl::HcPostPM<Act>{g.h, (unsigned)M, H4, H, 4, 16, 4, 4}, strm[c],
                   (const act_t *)b.ob, (const float *)b.post_f, (const float *)b.comb_f, (const float *)b.pre_f,
                   b.cur_pre);
    } else {
        for (int t = 0; t < M; ++t) {
            tok_set(c, t);
            auto &s = sc[c];
            if (pp)
                launch(c, (size_t)g.h, 64, ops41sycl::HcPostPreP<Act>{g.h}, streams[c], (const act_t *)s.ob,
                       (const float *)s.post_f, (const float *)s.comb_f, (const float *)s.pre_f, s.cur_pre,
                       (const float *)s.pre_f, s.x);
            else
                hc_post(c, s.post_f, s.comb_f, s.pre_f, s.cur_pre);
        }
    }
    mx_ready[c] = pp;
}
// tp_head for every token of the block: collapse (unless phase 5 did) + norm, this card's logits rows, the
// argmax candidates of each token to the host
void tpm_head_all(int c) {
    const int M = mt_n;
    const Scratch &b = scm[c][0];
    const size_t H = g.h, H4 = 4 * H;
    if (!mx_ready[c])
        launch(c, (size_t)M * H, 32, ops41sycl::HcPreAM<Act>{g.h, (unsigned)M, H4, 4, H}, (const act_t *)strm[c],
               (const float *)b.cur_pre, b.x);
    rows_launch(c, tokr(ops41sycl::NormRows<5120, 4>{b.x, wp<float>(c, "output_norm.weight"), b.xn}, H, H));
    const int nl = tv1[c] - tv0[c], G = (nl + AM_CH - 1) / AM_CH;
    gemv_m(c, "output.weight", b.xn, H, tlogm[c], (size_t)nl);
    launch_sg(c, (size_t)M * G, ops41sycl::ArgmaxP1OM{{nl, AM_CH, tv0[c], g.vocab}, (unsigned)G, (unsigned)M, (size_t)nl},
              (const float *)tlogm[c], tamvm[c], tamim[c]);
    qs[c].memcpy(h_amvm[c].data(), tamvm[c], (size_t)M * G * 4);
    qs[c].memcpy(h_amim[c].data(), tamim[c], (size_t)M * G * 4);
    twait(c);
}
void tpm_card_step(int c) {
    sc_keep[c] = sc[c];
    streams_keep[c] = streams[c];
    try {
        commit_pending(c);
        x_ready[c] = false;
        fin_attn[c] = false;
        xt[c].on = xt[c].pending = false;
        mx_ready[c] = false;
        tpm_engram_upload(c);
        if (o.layer_begin != 0) throw std::runtime_error("multi-token step needs every layer");
        tpm_embed(c);
        tpm_engram_kv(c);
        for (int L = o.layer_begin; L < o.layer_end; ++L) tpm_layer(L, c);
        if (o.head && mt_heads) {
            tok_end(c);
            tpm_head_all(c);
        } else if (o.head && !skip_head) {
            tok_set(c, mt_n - 1);
            x_ready[c] = mx_ready[c];
            tp_head(c);
            x_ready[c] = false;
        } else {
            twait(c);
        }
        if (o.dspark && !mt_heads) { // a prompt block: every position is kept, into the draft's windows now
            dr_inject(c, mt_n, pos);
            twait(c);
        } else if (o.dspark) // a checked block: staged in the block area, after the head (the host does not wait
            dr_inject(c, mt_n, pos, true); // for it; this queue runs it before the next step's work)
    } catch (...) {
        tok_end(c);
        throw;
    }
    tok_end(c);
}
public:
// mt tokens in one step (prompt reading); returns the next token after the last one (-1 without the head)
int32_t decode_block_tp(const int32_t *toks, int mt) {
    if (o.tp < 2 || tp_th.empty()) throw std::runtime_error("multi-token step needs OWN_TP > 1 with card threads");
    if (mt < 1 || mt > MTX) throw std::runtime_error("multi-token step: 1..16 tokens");
    if (pos + mt > max_seq) throw std::runtime_error("position beyond max_seq");
    if (!o.diet || !o.small_fast || o.hc_legacy || !o.hc_ride || !o.rope_out || o.fin_move || o.xtail)
        throw std::runtime_error("multi-token step is written for the default options");
    mt_n = mt;
    mt_toks = toks;
    tpm_engram_prefetch();
    ++tp_stepn;
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
    if (!tp_err.empty()) throw std::runtime_error("tensor-parallel block: " + tp_err);
    for (int c = 0; c < o.tp; ++c)
        if (xerr[c][0])
            throw std::runtime_error("card " + pci[c] + ": card-to-card exchange timed out waiting for card " +
                                     std::to_string((int)xerr[c][0] - 1));
    const int32_t next = o.head && !skip_head ? tp_argmax() : -1;
    pos += mt;
    return next;
}
// Draft checking: the block toks[0..mt) at pos .. pos + mt - 1 with the head for every token; next[t] = the
// greedy token after toks[0..t] (each bit for bit the one-token step's). The block stays provisional until
// commit_block(n) keeps its first n tokens (1..mt) and rolls back the rest: compressed rows (tlen), the
// ratio-2 carried state, the position. The block's window key rows stay in the ring's block area until
// commit_block moves the kept ones into the ring (moving a dropped one would overwrite position - 128, which
// the next tokens still read). Needs the block forms (OWN_MT_SMALL, the default).
void decode_verify_tp(const int32_t *toks, int mt, int32_t *next) {
    if (!mt_small || !o.head) throw std::runtime_error("draft checking needs OWN_MT_SMALL=1 and the head");
    if (vpos0 >= 0) throw std::runtime_error("draft checking: the previous block is not committed");
    const long p0 = pos;
    const bool sh = skip_head;
    skip_head = true; // decode_block_tp's last-token head is replaced by every token's
    mt_heads = true;
    try {
        decode_block_tp(toks, mt);
    } catch (...) {
        mt_heads = false;
        skip_head = sh;
        throw;
    }
    mt_heads = false;
    skip_head = sh;
    const int G = (tv1[0] - tv0[0] + AM_CH - 1) / AM_CH;
    for (int t = 0; t < mt; ++t) { // tp_argmax's order-free comparison, per token
        float bv = -INFINITY;
        int bi = 0x7fffffff;
        for (int c = 0; c < o.tp; ++c) {
            const int Gc = (tv1[c] - tv0[c] + AM_CH - 1) / AM_CH;
            for (int k = 0; k < Gc; ++k) {
                const float ov = h_amvm[c][(size_t)t * Gc + k];
                const int oi = h_amim[c][(size_t)t * Gc + k];
                if (ov > bv || (ov == bv && oi < bi)) { bv = ov; bi = oi; }
            }
        }
        next[t] = bi;
    }
    (void)G;
    vpos0 = p0;
}
// Keeps the first n tokens (1..mt) of the checked block. The cards' part (the ratio-2 carried state, the kept
// tokens' window rows of the target and of the draft) runs on each card at the start of its next step
// (commit_pending), all cards at once, instead of from this thread card by card.
void commit_block(int n) {
    if (vpos0 < 0) throw std::runtime_error("commit_block without a checked block");
    const int mt = (int)(pos - vpos0);
    if (n < 1 || n > mt) throw std::runtime_error("commit_block: 1..block tokens");
    const long pa = vpos0 + n - 1; // the last kept position
    for (int c = 0; c < o.tp; ++c) {
        for (int si = 0; si < 4; ++si) tlen[c][si] = mlen[c][si][n - 1];
        pend[c] = true;
    }
    pend_state = pa % 2 == 0 && n < mt; // its ratio-2 state is the carried one (the block may have carried a later one)
    pend_p0 = vpos0;
    pend_n = n;
    pos = vpos0 + n;
    vpos0 = -1;
}
private:
