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
std::vector<uint8_t> h_engrm[TILES][2]; // OWN_ENG_DEV: raw rows (ordinary host memory, like h_engm)
uint8_t *tengrm[TILES][2] = {};         // OWN_ENG_DEV: raw rows on the card
int eng_t0 = 0;                   // OWN_ENG_EARLY: the block's first token whose rows the card threads ask for
bool eng_anchor_asked = false;    // OWN_ENG_EARLY: draft_tp asked for the anchor's rows (position pos)
unsigned eng_sink[TILES] = {};
int32_t *cidxm[TILES][8] = {};   // one 512-row list per token per index slot
int32_t *blm[TILES] = {};        // OWN_IDX_CAND: per token the layer-20 block list (2048 + 64 ints each)
float *score2m[TILES] = {};      // OWN_IDX_CAND=2: the full scores per token (stride max_seq + 64)
int32_t *list2m[TILES] = {};     // OWN_IDX_CAND=2: the full select's lists (512 per token)
uint32_t *egrp[TILES] = {};      // the layer's expert groups (RUGrp layout, mt_eu)
long mlen[TILES][4][MTX] = {};   // rows of each kv source after token t's publish
unsigned xoaM = 0, xobM = 0, xactM = 0, xengM = 0, xfcM = 0; // xfcM: the draft's dsp.fc rows (dr_inject)
uint32_t eng_seqm[TILES] = {};
float *pkv[TILES][3] = {}, *psc[TILES][3] = {}; // the block's ratio-2 states per source (row 0: the carried even one)
// the head for every token of a block (draft checking): logits rows of this card, argmax candidates
bool mt_heads = false;
float *tlogm[TILES] = {}, *tamvm[TILES] = {};
int32_t *tamim[TILES] = {};
sycl::event head_ev[TILES]; // OWN_HEAD_CQ: a checked block's argmax launch (its readback waits for it on the copy queue)
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
// (the tables below: entries past MTF tokens take the MTF entry unless set; own_run_v41.cpp's option parsing)
unsigned mt_tgm[MTX + 1] = {}; // OWN_MT_TGM="m:g,...": dense token groups g (1-4) for blocks of exactly m tokens
                               // (overrides OWN_MT_TG for that m; 9 = all tokens in one sub-group, DenseRowsM)
unsigned mt_tgr[MTX + 1] = {}; // OWN_MT_TGR="m:r,...": blocks of m tokens run the token-group dense rows (OWN_MT_TGM)
                               // r = 2 or 4 rows per sub-group where the kernel has rowgr (Q8_0): activations read once per r rows
unsigned mt_tgr_rows = 2048; // ... only for matrices of at least this many rows on the card (OWN_MT_TGR_ROWS)
unsigned mt_tgr_fmt = 3;      // ... for these formats (OWN_MT_TGR_FMT: 1 Q8_0, 2 Q6_K, 3 both)
bool mt_tgr_draft = true;     // ... also in the draft's steps (OWN_MT_TGR_DRAFT)
bool mt_w16 = false;          // OWN_MT_W16: blocks of 9 or more tokens pick token groups and row blocks per matrix shape
                              // (w16_g / w16_r below; overrides OWN_MT_TG / OWN_MT_TGR for those matrices)
unsigned mt_tgw_rows = 0;     // OWN_MT_TGW_ROWS=n: packed matrices of at least n rows on the card (the vocabulary head)
                              // run their own token groups (mt_tgwm) with NO row blocks; 0: off. Same sums (rowg is
                              // per token). bench_q6k_rows, the head's 21,547 Q6_K rows, 6 tokens: 4-row blocks in
                              // groups of 3 651 us, groups of 3 305, one group of 6 457 -- but OFF: with 16384 the
                              // four 230 W cards run every kernel at ~2,600 instead of 2,800 MHz (round18 e67/e68)
unsigned mt_tgwm[MTX + 1] = {0, 0, 2, 3, 2, 3, 3}; // OWN_MT_TGWM="m:g,...": token group g (1-6) for blocks of m tokens
unsigned mt_tgu = 0;     // OWN_MT_TGU=1/2/3: the unpacked rows (GemvTM) in token groups over sub-groups (0: all 16 at once)
bool mt_ride = false;    // OWN_MT_RIDE=1: the stream mix's dot rows ride in q_a's and the router's launches
unsigned mt_rwg = 0;     // OWN_MT_RWG=n: row launches of at most n rows use one sub-group per work-group (rows_launch)
bool mt_rfuse = false;   // OWN_MT_RFUSE=1: router top-k + FFN mix finish + shared gate/up rows in one launch
unsigned mt_eu = 0;      // OWN_MT_EU=6: routed rows expert-major (RoutedU, groups of at most 6 slots; 0: slot-major)
// with OWN_MT_EU, blocks of at least OWN_MT_EU_BIG_M tokens (128): groups of at most OWN_MT_EU_BIG slots (16; 0: as
// OWN_MT_EU; 8 at most in layers whose gate / up rows are IQ2_S at 5,120 columns, where RoutedU<.., 16> spills), the
// heaviest groups first unless OWN_MT_EU_HEAVY=0. The same sums: a slot's output does not depend on its group.
unsigned mt_eu_big = 16, mt_eu_big_m = 128;
bool mt_eu_heavy = true;
unsigned eu_cap_c[TILES] = {}; // the cap card c's current layer was grouped with (tpm_layer's ExpertGroupM; routed_m)
bool mt_idstat = false; // OWN_MT_IDSTAT=1: count distinct experts per block and layer on card 0 (diagnostic, waits)
FILE *mt_iddump = nullptr; // OWN_MT_IDDUMP=<file> (with OWN_MT_IDSTAT=1): write each block's ids per layer
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

// (every region holds MTA tokens: MTX + the token groups' spare reads, see MTA)
size_t mt_arena_floats() const { // the block's exchange regions, after the one-token ones (+ the head outputs)
    return (size_t)MTA * ((size_t)g.ototal + (size_t)g.h + 7 * (size_t)g.mid + 10 * (size_t)g.h) + dr_arena_floats() +
           (size_t)MTA * (size_t)g.h + (size_t)MTA * (size_t)g.qh * (size_t)g.hd;
}
void mt_offsets(size_t base) {
    if (base + mt_arena_floats() > (size_t)UINT32_MAX) throw std::runtime_error("multi-token step: arena offsets");
    xoaM = (unsigned)base;
    xobM = xoaM + MTA * (unsigned)g.ototal;
    xactM = xobM + MTA * (unsigned)g.h;
    xengM = xactM + MTA * 7 * (unsigned)g.mid; // [token][engram layer] rows of 5 * h
    xdrM = xengM + MTA * 10 * (unsigned)g.h;   // the draft's argmax rows (backend_sycl_v41_draft.inc)
    xfcM = xdrM + (unsigned)dr_arena_floats(); // the draft's feature rows (its own region: dr_inject can follow the
                                               // last layer's exchange on xobM with no exchange in between)
    xhoM = xfcM + MTA * (unsigned)g.h;         // the head outputs (OWN_TP_HEADS), MTA tokens of qh * hd
}
void mt_alloc(int c) {
    // per-token buffers of MTA tokens (token t at t * n; tokens >= MTX only take token groups' spare reads)
    auto md = [&](size_t n) { return dalloc<act_t>(c, n * MTA); };
    auto mf = [&](size_t n) { return dalloc<float>(c, n * MTA); };
    const size_t H = g.h, Q = (size_t)g.qh * g.hd, nm = (size_t)(tm1[c] - tm0[c]), nd = (size_t)(td1[c] - td0[c]);
    act_t *x = md(H), *xn = md(H), *qa = md(g.qrank), *qn = md(g.qrank), *q = md(Q), *kv = md(g.hd), *kvn = md(g.hd);
    act_t *qi = md(32 * 128), *wv = md(32);
    float *score = dalloc<float>(c, ((size_t)max_seq + 64) * MTX); // (index scores: only t < mt is read)
    int64_t *lens = dalloc<int64_t>(c, MTX);
    float *router = mf(g.experts), *prob = mf(6);
    uint32_t *ids = dalloc<uint32_t>(c, 6 * MTX);
    act_t *expg = md(6 * nm), *expu = md(6 * nm), *expd = md(6 * nd), *shg = md(g.mid), *shu = md(g.mid), *shd = md(H);
    float *of = mf(Q), *attn_w = mf((size_t)g.qh * 640);
    // (split attention groups: the head outputs in the arena, where the partner card reads them)
    act_t *obuf = any_split() ? (act_t *)(xarena[c] + xhoM) : md(Q), *cw = md(g.hd), *scg = md(g.hd), *latent = md(g.hd), *kk = md(128);
    float *pa = mf(4), *qa4 = mf(4), *ca = mf(16), *pf = mf(4), *qf = mf(4), *cf = mf(16), *cur = mf(4);
    double *d25 = dalloc<double>(c, (size_t)25 * HC_SEG * MTX);
    float *rs = mf(g.experts), *rsb = mf(g.experts);
    int32_t *cat = dalloc<int32_t>(c, (size_t)640 * MTX), *widx = dalloc<int32_t>(c, (size_t)128 * MTX);
    act_t *old = md(4 * H);
    uint8_t *cand = dalloc<uint8_t>(c, ((size_t)max_seq + 64) * MTX);
    if (o.idx_cand) blm[c] = dalloc<int32_t>(c, (size_t)(2048 + 64) * MTX);
    // (score2m: one row of max_seq + 64 per token, as score; it was mf(... * MTX), i.e. MTX rows per token)
    if (o.idx_cand == 2) { score2m[c] = dalloc<float>(c, ((size_t)max_seq + 64) * MTX); list2m[c] = dalloc<int32_t>(c, (size_t)512 * MTX); }
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
        tengm[c][li] = dalloc<act_t>(c, (size_t)24 * g.engram_dim * MTA); // (engram_kv rows' input: MTA)
        h_engm[c][li].resize((size_t)24 * g.engram_dim * MTX);
        if (o.eng_dev) {
            tengrm[c][li] = dalloc<uint8_t>(c, (size_t)24 * 176 * MTX);
            h_engrm[c][li].resize((size_t)24 * 176 * MTX);
        }
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
// OWN_MT_W16's forms for blocks of 9-16 tokens (and larger blocks, as 16), from tools/bench/bench_dense_m16.cpp (round18 d1/d3/d4, one 230 W
// card, 16 tokens, cold, bitwise, us per launch at a 12-head card's shapes, engine form -> this one):
//   Q8_0 5120 columns (1792 rows) G4 80.4 -> G8 R2 70.3-70.8; 8192 (output-b, 864) G4 67.0-67.6 ->
//   G8 R2 52.7-52.9; 2304 (shared down, 864) G4 26.6-26.8 -> G4 R2 23.8-24.0; 4096 (output-a, 768) G4 37.1-37.3
//   -> G2 R4 34.3-34.4; 1280 (q_b) keeps G4 R4 (from 4,096 rows).
//   Q6_K 5120 (1792 rows) G4 144.5 -> G4 R2 89.6; 4096 (768) G4 72.0 -> G4 R2 39.7; 8192 (864) G4 77.9 -> G4 R2
//   75.5; 1280 (q_b, 6144) G4 R4 114.8 -> G4 107.0.
// In the engine (p78, OWN_GPROF=2 on cards 2 and 4, the 3K document, per launch off -> on) Q8_0's 5120-column rows
// lost: q_a with the stream mix's dot rows in its launch 107.9 -> 121.4 us, kv alone 22.0 -> 24.4 (fewer rows than
// the bench's 1792: groups of 8 with 2-row blocks leave the card under-filled), and output-a's 4096 columns 28.2 ->
// 30.4 (the engine's launches hold fewer rows than the bench's 768); those keep the general rules. Kept: Q8_0
// output-b 61.0 -> 49.0, shared down 25.6 -> 24.0 (card 4), Q6_K q_a with the dot rows 140.0 -> 122.0, output-a
// 42.3 -> 30.5, output-b 71.9 -> 65.4, q_b 112.0 -> 105.8.
// Other column counts (the engram rows, 6144), formats, matrices of > 8,192 rows on the card (the head) and the
// draft's steps keep the general rules. w16_r == 1: no row blocks.
template <typename DK> static constexpr unsigned w16_g() {
    constexpr unsigned n = ops41sycl::dense_cols_v<DK>;
    if constexpr (ops41sycl::is_q6kp_v<DK>) return n == 1280 || n == 4096 || n == 5120 || n == 8192 ? 4 : 0;
    else return n == 8192 ? 8 : n == 2304 ? 4 : 0;
}
template <typename DK> static constexpr unsigned w16_r() {
    constexpr unsigned n = ops41sycl::dense_cols_v<DK>;
    if constexpr (ops41sycl::is_q6kp_v<DK>) return n == 1280 ? 1 : 2;
    else return 2;
}
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
    auto split = [&](auto gc) { // token groups of G over sub-groups (DenseRowsG; DenseRowsGR: r rows per sub-group)
        constexpr unsigned G = decltype(gc)::value;
        if constexpr (requires { &DK::template rowgr<G, 2>; }) {
            constexpr unsigned fb = ops41sycl::is_q6kp_v<DK> ? 2u : 1u; // 1: Q8_0 rows, 2: Q6_K rows
            const bool on = (mt_tgr_fmt & fb) && (!dr_step || mt_tgr_draft);
            const unsigned rr = on && mt <= MTX && dk.rows >= mt_tgr_rows ? mt_tgr[mt] : 0;
            if (rr == 2 && dk.xn % 2 == 0)
                return go(ops41sycl::DenseRowsGR<DK, G, 2>{dk, (const uint8_t *)w, x, xs, y, ys, mt, (mt + G - 1) / G});
            if (rr == 4 && dk.xn % 4 == 0)
                return go(ops41sycl::DenseRowsGR<DK, G, 4>{dk, (const uint8_t *)w, x, xs, y, ys, mt, (mt + G - 1) / G});
        }
        go(ops41sycl::DenseRowsG<DK, G>{dk, (const uint8_t *)w, x, xs, y, ys, mt, (mt + G - 1) / G});
    };
    if constexpr (requires { &DK::template rowgr<2, 2>; }) {
        constexpr unsigned WG = w16_g<DK>(), WR = w16_r<DK>();
        if constexpr (WG != 0)
            if (mt_w16 && mt >= 9 && mt <= MTX && !dr_step && dk.rows <= 8192 && (WR == 1 || dk.xn % WR == 0)) {
                if constexpr (WR == 1)
                    return go(ops41sycl::DenseRowsG<DK, WG>{dk, (const uint8_t *)w, x, xs, y, ys, mt, (mt + WG - 1) / WG});
                else
                    return go(ops41sycl::DenseRowsGR<DK, WG, WR>{dk, (const uint8_t *)w, x, xs, y, ys, mt, (mt + WG - 1) / WG});
            }
    }
    if constexpr (std::is_same_v<RD, ops41sycl::NoRows> && requires { &DK::template rowgr<2, 2>; }) {
        const unsigned gw = mt_tgw_rows && dk.rows >= mt_tgw_rows && mt <= MTX ? mt_tgwm[mt] : 0;
        if (gw) { // OWN_MT_TGW_ROWS: the head's token groups, no row blocks
            auto grp = [&](auto gc) {
                constexpr unsigned G = decltype(gc)::value;
                go(ops41sycl::DenseRowsG<DK, G>{dk, (const uint8_t *)w, x, xs, y, ys, mt, (mt + G - 1) / G});
            };
            switch (gw) {
            case 1: return grp(std::integral_constant<unsigned, 1>{});
            case 2: return grp(std::integral_constant<unsigned, 2>{});
            case 3: return grp(std::integral_constant<unsigned, 3>{});
            case 4: return grp(std::integral_constant<unsigned, 4>{});
            case 5: return grp(std::integral_constant<unsigned, 5>{});
            default: return grp(std::integral_constant<unsigned, 6>{});
            }
        }
    }
    const unsigned tg = mt_tg_of(mt);
    if (tg == 1) return split(std::integral_constant<unsigned, 1>{});
    if (tg == 2) return split(std::integral_constant<unsigned, 2>{});
    if (tg == 3) return split(std::integral_constant<unsigned, 3>{});
    if (tg == 4) return split(std::integral_constant<unsigned, 4>{});
    if (mt <= (unsigned)MTF) return go(ops41sycl::DenseRowsM<DK, MTF>{dk, (const uint8_t *)w, x, xs, y, ys, mt});
    // past MTF tokens: DenseRowsM's token groups (rowg<DK::MTG>, the same calls as its rowm chain) on their own
    // sub-groups instead of one after another on one (a DenseRowsM<DK, MTX> would unroll MTX / MTG of them)
    constexpr unsigned GM = DK::MTG;
    go(ops41sycl::DenseRowsG<DK, GM>{dk, (const uint8_t *)w, x, xs, y, ys, mt, (mt + GM - 1) / GM});
}
// the dense token-group size for a block of mt tokens (0: none): OWN_MT_TGM's entry for mt, else OWN_MT_TG for
// blocks of at most OWN_MT_TG_MAX tokens; a block of more than MTF tokens follows that rule as a block of MTF
// does (the runner gives OWN_MT_TGM / OWN_MT_TGR / OWN_MT_TGWM entries past MTF the MTF entry unless set)
unsigned mt_tg_of(unsigned mt) const {
    const unsigned mq = std::min(mt, (unsigned)MTF);
    return mt <= (unsigned)MTX && mt_tgm[mt] ? mt_tgm[mt] : mq <= mt_tg_max && mq > mt_tg ? mt_tg : 0;
}
// (mt: tokens, default the block's; the publish runs its pooled rows only; rider: see dense_m, packed rows only)
// (ra, rb: packed rows only, the card's rows [ra, rb) with y row ra's output; rb == 0: all)
template <typename RD = ops41sycl::NoRows>
void gemv_m(int c, const std::string &wn, const act_t *x, size_t xs, act_t *y, size_t ys, unsigned xn = 0,
            unsigned mt = 0, const RD &rider = {}, unsigned ra = 0, unsigned rb = 0) {
    if (!mt) mt = (unsigned)mt_n;
    const auto &e = we(wn);
    const auto &dp = wgt[c].at(wn);
    if (!dp.packed) { // the generic per-format rows (GemvT's rowm), whole matrix
        if (xn) throw std::runtime_error("multi-token step: grouped unpacked rows " + wn);
        if (rb) throw std::runtime_error("multi-token step: a row range of unpacked rows " + wn);
        if constexpr (!std::is_same_v<RD, ops41sycl::NoRows>) rows_launch(c, rider);
        const unsigned rows = (unsigned)e.rows, cols = (unsigned)e.cols;
        if (o.packed && e.type == iq3::Type::F32 && cols == 5120) // gemv's block-read F32 rows
            return dense_m(c, ops41sycl::GemvF32P<160, Act>{rows}, wp(c, wn), x, xs, y, ys, mt, ops41sycl::NoRows{});
        if (bf16_h16(e, wp(c, wn))) // gemv's block-read BF16 rows, every token in the dense token groups
            return h16_rows(cols, rows, [&](auto dk) { dense_m(c, dk, wp(c, wn), x, xs, y, ys, mt, ops41sycl::NoRows{}); });
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
        if (mt > (unsigned)MTF) /* GemvTM's rowg<MTG> groups on their own sub-groups (as dense_m) */     \
            return tgu(std::integral_constant<iq3::Type, iq3::Type::TY>{},                                 \
                       std::integral_constant<unsigned, ops41sycl::GemvT<iq3::Type::TY, Act>::MTG>{});     \
        launch_sg(c, rows, ops41sycl::GemvTM<iq3::Type::TY, Act, MTF>{{rows, cols, false}, xs, ys, mt}, \
                  (const uint8_t *)wp(c, wn), x, (void *)y);                                               \
        return;
            X(F32) X(BF16) X(Q8_0)
#undef X
        default: throw std::runtime_error("multi-token step: no unpacked rows form for " + wn);
        }
    }
    const unsigned cols = (unsigned)e.cols;
    if (!rb) rb = dp.nrows;
    if (ra >= rb || rb > dp.nrows) throw std::runtime_error("multi-token step: rows of " + wn);
    const unsigned rows = rb - ra;
    const void *wr = (const uint8_t *)dp.p + (size_t)ra * pk41::packed_row_bytes(e.type, (size_t)cols);
#define XQ(COLS)                                                                                           \
    if (cols == COLS) return dense_m(c, ops41sycl::GemvQ8P<COLS / 32, Act>{rows, xn}, wr, x, xs, y, ys, mt, rider);
#define X(KERN, NB)                                                                                        \
    if (cols == NB * 256) return dense_m(c, ops41sycl::KERN<NB, Act>{rows, xn}, wr, x, xs, y, ys, mt, rider);
    if (e.type == iq3::Type::Q8_0) { XQ(1280) XQ(2304) XQ(4096) XQ(5120) XQ(8192) XQ(15360) }
    if (e.type == iq3::Type::Q6_K) { X(GemvQ6KP, 5) X(GemvQ6KP, 16) X(GemvQ6KP, 20) X(GemvQ6KP, 24) X(GemvQ6KP, 32) }
    if (e.type == iq3::Type::Q5_K) { X(GemvQ5KP, 9) X(GemvQ5KP, 20) }
    if (e.type == iq3::Type::F32 && cols == 5120 && !xn)
        return dense_m(c, ops41sycl::GemvH16P<160, Act>{rows}, wr, x, xs, y, ys, mt, rider);
#undef X
#undef XQ
    throw std::runtime_error("multi-token step: no packed kernel for " + wn);
}
// f(kernel, packed weights) for a packed dense matrix (the kernel gemv_m picks); false when there is none
template <typename F> bool dense_kernel(int c, const std::string &wn, F &&f) {
    const auto &e = we(wn);
    const auto &dp = wgt[c].at(wn);
    if (!dp.packed) return false;
    const unsigned rows = dp.nrows, cols = (unsigned)e.cols;
    const uint8_t *w = (const uint8_t *)dp.p;
#define XQ(COLS)                                                                                           \
    if (cols == COLS) { f(ops41sycl::GemvQ8P<COLS / 32, Act>{rows, 0}, w); return true; }
#define X(KERN, NB)                                                                                        \
    if (cols == NB * 256) { f(ops41sycl::KERN<NB, Act>{rows, 0}, w); return true; }
    if (e.type == iq3::Type::Q8_0) { XQ(1280) XQ(2304) XQ(4096) XQ(5120) XQ(8192) }
    if (e.type == iq3::Type::Q6_K) { X(GemvQ6KP, 5) X(GemvQ6KP, 16) X(GemvQ6KP, 20) X(GemvQ6KP, 24) X(GemvQ6KP, 32) }
    if (e.type == iq3::Type::Q5_K) { X(GemvQ5KP, 9) X(GemvQ5KP, 20) }
#undef X
#undef XQ
    return false;
}
// OWN_MT_RFUSE: the block's router top-k (a work-group per token), the FFN mix's finish and the shared expert's
// gate + up rows in ONE launch (the one-token path's route_with_shared). False (nothing launched) when the gate
// and up matrices are not the same packed kernel.
bool route_shared_m(int c, const std::string &p, const float *bias) {
    const std::string gn = p + "ffn_gate_shexp.weight", un = p + "ffn_up_shexp.weight";
    const auto &eg = we(gn), &eu = we(un);
    if (eg.type != eu.type || eg.cols != eu.cols || !wgt[c].at(gn).packed || !wgt[c].at(un).packed) return false;
    if (wgt[c].at(gn).nrows != wgt[c].at(un).nrows || g.experts % 32 != 0 || g.experts > 512) return false;
    const unsigned mt = (unsigned)mt_n;
    const Scratch &b = scm[c][0];
    const size_t H = g.h, FS = (size_t)25 * HC_SEG;
    const uint8_t *wu = (const uint8_t *)wgt[c].at(un).p;
    tok_set(c, 0);
    using FR = ops41sycl::TokRows<ops41sycl::HcFinishRows>;
    const FR fin = tokr(hc_finish(c, p + "hc_ffn_", b.pre_f, b.post_f, b.comb_f), FS, 4, 4, 16);
    const unsigned tg = mt_tg_of(mt);
    return dense_kernel(c, gn, [&](auto dk, const uint8_t *wg) {
        using DK = decltype(dk);
        auto go = [&](const auto &dg, const auto &du) {
            using DG = std::decay_t<decltype(dg)>;
            using RX = ops41sycl::RowsPair<FR, ops41sycl::RowsPair<DG, DG>>;
            const RX rx{fin, {dg, du}};
            const ops41sycl::RoutePMRows<RX> k{ops41sycl::RouteP{g.experts, 6}, (size_t)g.experts, mt, rx};
            launch_wgs<2 * 1024 + 6>(c, (size_t)mt + (rx.n() + 15) / 16, 512, k, (const float *)b.router, bias, b.ids,
                                     b.prob);
        };
        auto split = [&](auto gc) {
            constexpr unsigned G = decltype(gc)::value;
            using D = ops41sycl::DenseRowsG<DK, G>;
            const unsigned ng = (mt + G - 1) / G;
            go(D{dk, wg, b.xn, H, b.shg, (size_t)g.mid, mt, ng}, D{dk, wu, b.xn, H, b.shu, (size_t)g.mid, mt, ng});
        };
        if (tg == 1) return split(std::integral_constant<unsigned, 1>{});
        if (tg == 2) return split(std::integral_constant<unsigned, 2>{});
        if (tg == 3) return split(std::integral_constant<unsigned, 3>{});
        if (tg == 4) return split(std::integral_constant<unsigned, 4>{});
        if (mt > (unsigned)MTF) { // as dense_m past MTF tokens
            constexpr unsigned GM = DK::MTG;
            using D = ops41sycl::DenseRowsG<DK, GM>;
            const unsigned ng = (mt + GM - 1) / GM;
            return go(D{dk, wg, b.xn, H, b.shg, (size_t)g.mid, mt, ng}, D{dk, wu, b.xn, H, b.shu, (size_t)g.mid, mt, ng});
        }
        using D = ops41sycl::DenseRowsM<DK, MTF>;
        go(D{dk, wg, b.xn, H, b.shg, (size_t)g.mid, mt}, D{dk, wu, b.xn, H, b.shu, (size_t)g.mid, mt});
    });
}
// the stream-mix dot rows of every token (HcMixDotsP rows, fn values read once)
// (OWN_MT_SMALL=0 only; one launch per MTF tokens, token t's rows on its own streams and partials as before)
void hc_dots_m(int c, const std::string &prefix) {
    using R = ops41sycl::HcDotsRowsM<5120, HC_SEG, MTF>;
    for (int t0 = 0; t0 < mt_n; t0 += MTF) {
        const R r{(const float *)(strm[c] + (size_t)t0 * 4 * g.h), (size_t)4 * g.h, wp<float>(c, prefix + "fn.weight"),
                  scm[c][0].d25 + (size_t)t0 * 25 * HC_SEG, (size_t)25 * HC_SEG, (unsigned)std::min(MTF, mt_n - t0)};
        launch_rows<0>(c, r.n(), 0, ops41sycl::RowsP<R>{r});
    }
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
#ifndef OWN41_ACT_BF16
        if (o.q2k_fast && e.type == iq3::Type::Q2_K && (cols == 9 * 256 || cols == 20 * 256)) { // as routed_gemv
            if (cols == 9 * 256)
                launch_sg(c, (size_t)nsl0 * rows, ops41sycl::RoutedQ2KF<9>{rows, cols, per_slot, nsl0, (unsigned)xtok},
                          wp(c, wn), x, ids, y);
            else
                launch_sg(c, (size_t)nsl0 * rows, ops41sycl::RoutedQ2KF<20>{rows, cols, per_slot, nsl0, (unsigned)xtok},
                          wp(c, wn), x, ids, y);
            return;
        }
#endif
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
    const size_t maxwg = per_slot ? (size_t)o.down_wg
                                  : e.type == iq3::Type::IQ1_S && o.pair_wg_iq1 > 0 ? (size_t)o.pair_wg_iq1 : (size_t)o.pair_wg;
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
        const unsigned cap = eu_cap_c[c]; // <= 6: the MT 6 kernels; else MT 16 (MT 8 for IQ2_S at 5,120 columns)
        if (cap < 1 || cap > 16) throw std::runtime_error("OWN_MT_EU_BIG: groups of 1 .. 16 slots");
        auto gu = [&](auto kt) {
            using K = typename decltype(kt)::type;
            K k{rows, per_slot};
            k.w2 = w2;
            k.out2 = y2;
            k.nsl = nsl;
            k.xtok = (unsigned)xtok;
            launch_rows<K::TAB>(c, npos, maxwg, k, (const uint8_t *)dp.p, x, (const uint32_t *)egrp[c], y);
        };
#define XU(TY, KERN, NB, MB)                                                                                 \
    if (e.type == iq3::Type::TY && cols == NB * 256) {                                                       \
        if (cap <= 6) return gu(std::type_identity<KERN<NB, 6>>{});                                          \
        if (cap <= MB) return gu(std::type_identity<KERN<NB, MB>>{});                                        \
        throw std::runtime_error("multi-token step: expert groups of more than " #MB " slots for " + wn);   \
    }
        XU(IQ2_XXS, RoutedIQ2XXSU, 20, 16) XU(IQ2_S, RoutedIQ2SU, 20, 8) XU(IQ3_XXS, RoutedIQ3XXSU, 20, 16)
        XU(IQ2_XS, RoutedIQ2XSU, 20, 16) XU(IQ1_S, RoutedIQ1SU, 20, 16) XU(IQ2_XXS, RoutedIQ2XXSU, 9, 16)
        XU(IQ2_S, RoutedIQ2SU, 9, 16) XU(IQ3_XXS, RoutedIQ3XXSU, 9, 16) XU(IQ2_XS, RoutedIQ2XSU, 9, 16)
        XU(IQ1_S, RoutedIQ1SU, 9, 16)
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
// OWN_ENG_EARLY: this card thread's share of the block's row reads (every o.tp-th row from token eng_t0 on; the
// anchor's rows were asked for during the draft), asked for, then waited on, before it reads all the rows
void tpm_engram_share(int c) {
    static const long page = sysconf(_SC_PAGESIZE);
    auto l = iq3::layout(iq3::Type::Q5_K);
    const uint8_t *mine[2 * 24 * MTX];
    int nm = 0, r = 0;
    for (int li = 0; li < 2; ++li) {
        const int L = li == 0 ? 1 : 14;
        if (L < o.layer_begin || L >= o.layer_end || !eng_base[li]) continue;
        for (int t = eng_t0; t < mt_n; ++t) {
            const long p_ = pos + t;
            if ((long)comp_ids.size() <= p_) throw std::runtime_error("comp_ids behind position");
            int64_t ids[24];
            engram_hash((int)p_, li, ids);
            for (int k = 0; k < 24; ++k, ++r) {
                if (r % o.tp != c) continue;
                const uint8_t *row = eng_base[li] + (size_t)ids[k] * l.bytes;
                const uintptr_t a = (uintptr_t)row, a0 = a & ~(uintptr_t)(page - 1);
                madvise((void *)a0, (size_t)(a + l.bytes - a0), MADV_WILLNEED);
                mine[nm++] = row;
            }
        }
    }
    unsigned sink = 0;
    for (int i = 0; i < nm; ++i) sink += *(volatile const uint8_t *)mine[i] + *(volatile const uint8_t *)(mine[i] + l.bytes - 1);
    eng_sink[c] += sink;
}
void tpm_engram_upload(int c) {
    auto l = iq3::layout(iq3::Type::Q5_K);
    if (o.eng_early) tpm_engram_share(c);
    const size_t per = (size_t)24 * g.engram_dim;
    for (int li = 0; li < 2; ++li) {
        const int L = li == 0 ? 1 : 14;
        if (L < o.layer_begin || L >= o.layer_end || !eng_base[li]) continue;
        if (o.eng_dev) { // raw rows to the card, decoded there (same decode as the host's, EngRowsA)
            uint8_t *raw = h_engrm[c][li].data();
            for (int t = 0; t < mt_n; ++t) {
                const long p_ = pos + t;
                if ((long)comp_ids.size() <= p_) throw std::runtime_error("comp_ids behind position");
                int64_t ids[24];
                engram_hash((int)p_, li, ids);
                for (int k = 0; k < 24; ++k)
                    std::memcpy(raw + (size_t)(t * 24 + k) * l.bytes, eng_base[li] + (size_t)ids[k] * l.bytes, l.bytes);
            }
            const auto q0 = std::chrono::steady_clock::now();
            if (o.eng_cq) { // OWN_ENG_CQ: the copy on the card's copy queue, the decode launch waits for it by event
                const sycl::event ce = cqs[c].memcpy(tengrm[c][li], raw, (size_t)mt_n * 24 * l.bytes);
                const ops41sycl::EngRowsA<Act> k{(unsigned)mt_n * 24u};
                const uint8_t *src = tengrm[c][li];
                act_t *dst = tengm[c][li];
                const size_t n = (size_t)mt_n * 24 * 256;
                auto e = qs[c].submit([&](sycl::handler &hh) {
                    hh.depends_on(ce);
                    hh.parallel_for(sycl::nd_range<1>(n, 256), [=](sycl::nd_item<1> it) { k(it, src, dst); });
                });
                kev(c, kname<ops41sycl::EngRowsA<Act>>(), e);
            } else {
                qs[c].memcpy(tengrm[c][li], raw, (size_t)mt_n * 24 * l.bytes);
                launch(c, (size_t)mt_n * 24 * 256, 256, ops41sycl::EngRowsA<Act>{(unsigned)mt_n * 24u},
                       (const uint8_t *)tengrm[c][li], tengm[c][li]);
            }
            eng_tq[c] += std::chrono::duration<double>(std::chrono::steady_clock::now() - q0).count();
            continue;
        }
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
void tpm_embed(int c, bool wait = true) {
    const auto &te = we("token_embd.weight");
    for (int t = 0; t < mt_n; ++t) {
        tok_set(c, t);
        const uint8_t *row = (const uint8_t *)wgt[c].at("token_embd.weight").p + (size_t)mt_toks[t] * wrb(te);
        launch(c, g.h, 32, ops41sycl::EmbedRowA<Act>{te.type, g.h}, row, sc[c].x);
        if (o.pre_k) { // OWN_PRE_K: the pre-mix weights by the broadcast launch, no host copy
            launch(c, g.h, 32, ops41sycl::Broadcast4PA<Act>{g.h}, (const act_t *)sc[c].x, streams[c], sc[c].cur_pre);
        } else {
            launch(c, g.h, 32, ops41sycl::Broadcast4A<Act>{g.h}, (const act_t *)sc[c].x, streams[c]);
            qs[c].memcpy(sc[c].cur_pre, k_pm1, 16);
        }
    }
    tok_end(c);
    if (wait) twait(c);
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
    int lens[MTX] = {}, nshort = 0, nlong = 0;
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
    // OWN_IDX_CAND: past layer 20, when every long token has more rows than candidates, only each token's
    // layer-20 candidate rows are scored and selected (the others are -inf in the masked select)
    bool ccm = o.idx_cand && L > 20;
    for (int t = 0; t < M && ccm; ++t)
        if (lens[t] > 0 && lens[t] <= 2048 * 8) ccm = false;
    if (ccm) {
        using KS = ops41sycl::IndexerScoreBCM<Act>;
        constexpr size_t WG = 128;
        KS k{};
        for (int t = 0; t < M; ++t) k.lens[t] = lens[t];
        k.m = (unsigned)M;
        k.gpt = (unsigned)(2048 * 8 / WG);
        k.qs = 4096;
        k.ws = 32;
        k.ss = SS;
        k.bls = 2048 + 64;
        const act_t *qi = b.qi, *wv = b.wv;
        const uint16_t *ik = ik_mirror[c][si];
        const int32_t *bl = blm[c];
        float *sco = b.score;
        auto e = qs[c].submit([&](sycl::handler &hh) {
            sycl::local_accessor<float, 1> lt(32 * 128 + 32, hh);
            hh.parallel_for(sycl::nd_range<1>((size_t)M * k.gpt * WG, WG),
                            [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(16)]] { k(it, qi, ik, wv, sco, bl, &lt[0]); });
        });
        kev(c, kname<KS>(), e);
        constexpr size_t SLMC = (size_t)ops41sycl::TopKSelC::NSG * 256 + 8;
        if (qsel_ok()) { // OWN_TOPK_Q
            ops41sycl::TopKSelMCQ kq{};
            for (int t = 0; t < M; ++t) kq.lens[t] = lens[t];
            kq.m = (unsigned)M;
            kq.ss = SS;
            kq.cs = SS;
            kq.bls = 2048 + 64;
            launch_wgs<SLMC>(c, (size_t)M, ops41sycl::TopKSelC::WG, kq, (const float *)b.score, (const uint8_t *)b.cand,
                             (const int32_t *)blm[c], cidxm[c][slot]);
        } else {
            ops41sycl::TopKSelMC kt{};
            for (int t = 0; t < M; ++t) kt.lens[t] = lens[t];
            kt.m = (unsigned)M;
            kt.ss = SS;
            kt.cs = SS;
            kt.bls = 2048 + 64;
            kt.rwalk = o.topk_r;
            launch_wgs<SLMC>(c, (size_t)M, ops41sycl::TopKSelC::WG, kt, (const float *)b.score, (const uint8_t *)b.cand,
                             (const int32_t *)blm[c], cidxm[c][slot]);
        }
        if (o.idx_cand == 2) idx_cand_check_m(L, c, si, M, lens, slot);
        return;
    }
    if (o.idx_r == 2 || o.idx_r == 4) {
        long ll[MTX] = {};
        for (int t = 0; t < M; ++t) ll[t] = lens[t];
        idx_score_r(c, o.idx_r, M, ll, b.qi, b.wv, ik_mirror[c][si], b.score, 4096, 32, SS);
    } else {
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
    // OWN_TOPK_Q: the register selects (the block select past 2,048 blocks, the rows' select from 4,096 rows)
    const int qb = qsel_ok() && (lmax + 7) / 8 > 2048 ? ops41sycl::qsel_span((int)((lmax + 7) / 8)) : 0;
    const int qr = qsel_ok() && lmax >= 4096 ? ops41sycl::qsel_span((int)lmax) : 0;
    if (L == 20) {
        auto blk = [&](auto kb) {
            for (int t = 0; t < M; ++t) kb.lens[t] = lens[t];
            kb.m = (unsigned)M;
            kb.ss = SS;
            kb.cs = SS;
            kb.bls = 2048 + 64;
            launch_wgs<SLM>(c, (size_t)M, KR::WG, kb, (const float *)b.score, b.cand, blm[c]); // blm: OWN_IDX_CAND (else null)
        };
        if (qb && qb <= 16) blk(ops41sycl::TopKSelMBQ<16>{});
        else if (qb && qb <= 32) blk(ops41sycl::TopKSelMBQ<32>{});
        else blk(ops41sycl::TopKSelM<true>{});
    }
    auto rws = [&](auto kt) {
        for (int t = 0; t < M; ++t) kt.lens[t] = lens[t];
        kt.m = (unsigned)M;
        kt.mask = L > 20;
        kt.ss = SS;
        kt.cs = SS;
        launch_wgs<SLM>(c, (size_t)M, KR::WG, kt, (const float *)b.score, b.cand, cidxm[c][slot]);
    };
    if (qr && qr <= 16) rws(ops41sycl::TopKSelMQ<16>{});
    else if (qr && qr <= 32) rws(ops41sycl::TopKSelMQ<32>{});
    else if (qr && qr <= 64) rws(ops41sycl::TopKSelMQ<64>{});
    else if (qr && qr <= 96) rws(ops41sycl::TopKSelMQ<96>{});
    else {
        ops41sycl::TopKSelM<false> kt{};
        kt.rwalk = o.topk_r;
        rws(kt);
    }
}
// OWN_IDX_CAND=2, blocks (one call in 37 per card): each token's candidate-only scores and list against the full score (score2m) and the
// masked select over all its rows (list2m), bitwise; the block lists against the masks
long icc_m_n[TILES] = {};
void idx_cand_check_m(int L, int c, int si, int M, const int *lens, int slot) {
    if (icc_m_n[c]++ % 37) return; // one block layer in 37 (a prompt's blocks would copy ~9 bytes per row each)
    const Scratch &b = scm[c][0];
    const size_t SS = (size_t)max_seq + 64;
    long lmax = 0;
    for (int t = 0; t < M; ++t) lmax = std::max<long>(lmax, lens[t]);
    {
        using KS = ops41sycl::IndexerScoreBM<Act>;
        constexpr size_t WG = 128;
        KS k{};
        for (int t = 0; t < M; ++t) k.lens[t] = lens[t];
        k.m = (unsigned)M;
        k.gpt = (unsigned)((((lmax + 31) / 32 * 32) + WG - 1) / WG);
        k.qs = 4096;
        k.ws = 32;
        k.ss = SS;
        const act_t *qi = b.qi, *wv = b.wv;
        const uint16_t *ik = ik_mirror[c][si];
        float *sco = score2m[c];
        qs[c].submit([&](sycl::handler &hh) {
            sycl::local_accessor<float, 1> lt(32 * 128 + 32, hh);
            hh.parallel_for(sycl::nd_range<1>((size_t)M * k.gpt * WG, WG),
                            [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(16)]] { k(it, qi, ik, wv, sco, &lt[0]); });
        });
    }
    using KR = ops41sycl::TopKSelP<false>;
    constexpr size_t SLM = (size_t)KR::NSG * 256 + 8;
    ops41sycl::TopKSelM<false> kt{};
    for (int t = 0; t < M; ++t) kt.lens[t] = lens[t];
    kt.m = (unsigned)M;
    kt.mask = true;
    kt.ss = SS;
    kt.cs = SS;
    launch_wgs<SLM>(c, (size_t)M, KR::WG, kt, (const float *)score2m[c], b.cand, list2m[c]);
    qs[c].wait();
    for (int t = 0; t < M; ++t) {
        if (lens[t] <= 0) continue;
        const long len = lens[t];
        std::vector<float> a(len), f(len);
        std::vector<uint8_t> cm(len);
        std::vector<int32_t> la(512), lb(512), bl(2049);
        qs[c].memcpy(a.data(), b.score + t * SS, (size_t)len * 4);
        qs[c].memcpy(f.data(), score2m[c] + t * SS, (size_t)len * 4);
        qs[c].memcpy(cm.data(), b.cand + t * SS, (size_t)len);
        qs[c].memcpy(bl.data(), blm[c] + (size_t)t * (2048 + 64), 2049 * 4);
        qs[c].memcpy(la.data(), cidxm[c][slot] + (size_t)t * 512, 512 * 4);
        qs[c].memcpy(lb.data(), list2m[c] + (size_t)t * 512, 512 * 4).wait();
        long ncand = 0, sbad = 0;
        for (long j = 0; j < len; ++j)
            if (cm[j]) { ++ncand; if (std::memcmp(&a[j], &f[j], 4)) ++sbad; }
        bool lbad = la != lb, bbad = bl[0] < 0 || bl[0] > 2048;
        if (!bbad) {
            std::vector<uint8_t> m2(len, 0);
            for (int i = 0; i < bl[0]; ++i) {
                if (i && bl[1 + i] <= bl[i]) bbad = true;
                for (long j = (long)bl[1 + i] * 8; j < std::min<long>((long)bl[1 + i] * 8 + 8, len); ++j) m2[j] = 1;
            }
            if (m2 != cm) bbad = true;
        }
        const bool bad = sbad || lbad || bbad;
        const long n = ++icc_calls, nb_ = bad ? ++icc_bad : icc_bad.load();
        if (bad && nb_ <= 5)
            fprintf(stderr, "idx_cand check (blocks): MISMATCH card %d layer %d token %d len %ld: %ld of %ld candidate "
                            "scores differ, list %s, blocks %s\n", c, L, t, len, sbad, ncand, lbad ? "DIFFERS" : "same",
                    bbad ? "WRONG" : "ok");
        if ((n & (n - 1)) == 0 || n % 1024 == 0)
            fprintf(stderr, "idx_cand check: %ld lists, %ld mismatches (last: card %d layer %d len %ld, %ld candidates, block)\n",
                    n, nb_, c, L, len, ncand);
    }
}
// the block's output-a rows (layout h: oa_run) and their all-gather; wb: the first output-a row the card holds
void oa_m(int c, const std::string &p, const HeadLay &h, int part, unsigned wb) {
    const unsigned M = (unsigned)mt_n, per = (unsigned)g.ototal / 8;
    const Scratch &b = scm[c][0];
    oa_run(c, h, M, [&](unsigned r0, unsigned r1) {
        gemv_m(c, p + "attn_output_a.weight", b.obuf + (size_t)(r0 / per) * g.oin, (size_t)g.qh * g.hd,
               xarena[c] + xoaM + r0, (size_t)g.ototal, per, 0, ops41sycl::NoRows{}, r0 - wb, r1 - wb);
    });
    xchg_m(c, xoaM, (unsigned)g.ototal, M, h.oa0[c], h.oa1[c], 0, part);
}
void tpm_layer(int L, int c) {
    const int M = mt_n;
    const std::string p = "blk." + std::to_string(L) + ".";
    const int cr = cr_of(L);
    const bool yarn = cr > 0;
    const int si = src_index(L);
    const HeadLay &hla = lay_m((unsigned)M); // the block's attention layout (OWN_TP_HEADS_MIN)
    const int nh = hla.hq1[c] - hla.hq0[c];
    const size_t qo = (size_t)hla.hq0[c] * g.hd, H = g.h;
    const unsigned qbr0 = (unsigned)((hla.hq0[c] - qst0[c]) * g.hd), qbr1 = (unsigned)((hla.hq1[c] - qst0[c]) * g.hd);
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
        if (mt_small && ops41sycl::g_eng_ff) { // OWN_ENG_FF: EngramGateW per token (the same gates bit for bit)
            launch_wgl<8 * 16 + 2>(c, (size_t)4 * M, 512,
                                   ops41sycl::EngramGateWM<16>{ops41sycl::EngramGateP{g.h}, (unsigned)M, H4, 10 * H},
                                   strm[c], (const float *)(xarena[c] + xengM + (size_t)li * 5 * H),
                                   wp<float>(c, p + "engram_gate.weight"));
        } else if (mt_small) {
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
    gemv_m(c, p + "attn_q_b.weight", b.qn, g.qrank, b.q + qo, Q, 0, 0, ops41sycl::NoRows{}, qbr0, qbr1);
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
        const int nc = cr ? 512 : 0, W = 128 + MTX;
        int n_idx = 128 + nc;
        if (cr && o.att_trim) { // OWN_ATT_TRIM: every token's list below 512 rows: up to the longest, rounded up
            long lm = 0;
            for (int t = 0; t < M; ++t) lm = std::max<long>(lm, mlen[c][si][t]);
            if (lm < 512) n_idx = att_trim_n(lm);
        }
        // (items per token: WindowAppendM's max(d, win + nc), whatever slots the attention reads)
        launch(c, (size_t)M * std::max(g.hd, 128 + nc), 64,
               ops41sycl::WindowAppendM<Act>{128, g.hd, (int)pos, nc, M, MTX, (size_t)g.hd, 512, 640}, ring[c][L],
               (const act_t *)b.kvn, b.idxs_cat, (const int32_t *)(cr ? cidxm[c][isrc_for(L)] : nullptr));
        const uint16_t *kvw = ring[c][L], *kvc = cr ? ckv_mirror[c][si] : ring[c][L];
        if (!al16(kvw) || !al16(kvc)) throw std::runtime_error("multi-token step: kv alignment");
        const float *sinks = wp<float>(c, p + "attn_sinks.weight") + hla.hq0[c];
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
            // OWN_ATT_HG / OWN_ATT_PK in blocks too (OWN_ATT_M=1, 2026-11-11; the one-token forms' bit-identical
            // variants: heads per sub-group 1 / 2 / 4, the trimmed lists' softmax built per slot count)
            auto score_m = [&](auto hgc) {
                constexpr unsigned HG = decltype(hgc)::value;
                const unsigned gpt = (unsigned)((nh / HG) * (n_idx / 32));
                launch_sg(c, (size_t)M * gpt,
                          ops41sycl::ScoreM<ops41sycl::SparseScoreHG<512, HG>>{{n_idx, nh, W, g.hd}, gpt, (unsigned)M, Q, 640, WS},
                          (const act_t *)(b.q + qo), kvw, kvc, ix, b.attn_w);
            };
            if (!o.att_m || o.att_hg == 4) score_m(std::integral_constant<unsigned, 4>{}); // (nh: 8 or 16)
            else if (o.att_hg == 2 && nh % 2 == 0) score_m(std::integral_constant<unsigned, 2>{});
            else score_m(std::integral_constant<unsigned, 1>{});
            if (n_idx < 640) {
                if (!(o.att_m && o.att_pk && softmax_pk_m<160>(c, nh, n_idx, M, WS, sinks, ix, b.attn_w)))
                    launch_sg(c, (size_t)M * nh,
                              ops41sycl::SoftmaxM<ops41sycl::SparseSoftmaxPN<640>>{{nh, n_idx}, (unsigned)nh, (unsigned)M, 640, WS},
                              sinks, ix, b.attn_w);
            } else {
                launch_sg(c, (size_t)M * nh,
                          ops41sycl::SoftmaxM<ops41sycl::SparseSoftmaxP<640>>{{nh}, (unsigned)nh, (unsigned)M, 640, WS}, sinks,
                          ix, b.attn_w);
            }
        }
        const float *cbm = (yarn ? cos_yarn[c] : cos_base[c]) + (size_t)pos * 32;
        const float *sbm = (yarn ? sin_yarn[c] : sin_base[c]) + (size_t)pos * 32;
        // OWN_ATT_OUT_C: blocks of up to 8 tokens only (guess checks); from 12 tokens on (prompt reading, 16) the
        // 32 KiB of local memory per work-group leaves too few of them resident and OutM<JB> is faster (round18 s5:
        // 16 heads, 640 slots: M = 1..6 15.8-20.9 us vs 23.3-29.6, M = 8 24.3 vs 24.4, M = 16 44.9 vs 30.8)
        if (o.att_out_c && M <= 8) {
            using SC = ops41sycl::SparseOutJC<512, 16, 128>;
            SC so{n_idx, nh, W};
            so.ry = (float *)(b.obuf + qo);
            so.cosb = cbm;
            so.sinb = sbm;
            const unsigned gpo = (unsigned)SC::groups(nh);
            launch_wgl<SC::SLM>(c, (size_t)M * gpo, SC::WG, ops41sycl::OutMC<SC>{so, gpo, (unsigned)M, 640, WS, Q, Q}, kvw,
                                kvc, ix, (const float *)b.attn_w, b.of + qo);
        } else {
            using SO = ops41sycl::SparseOutJB<512, 1, 16>;
            SO so{n_idx, nh, W};
            so.ry = (float *)(b.obuf + qo);
            so.cosb = cbm;
            so.sinb = sbm;
            const unsigned gpo = (unsigned)(nh * g.hd / 64);
            launch_sg(c, (size_t)M * gpo, ops41sycl::OutM<SO>{so, gpo, (unsigned)M, 640, WS, Q, Q}, kvw, kvc, ix,
                      (const float *)b.attn_w, b.of + qo);
        }
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
        const float *sinks = wp<float>(c, p + "attn_sinks.weight") + hla.hq0[c];
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
        if (o.att_out_c) { // OWN_ATT_OUT_C
            using SC = ops41sycl::SparseOutJC<512, 16, 128>;
            SC so{n_idx, nh, 128};
            so.ry = (float *)(s.obuf + qo);
            so.cosb = cb;
            so.sinb = sbp;
            launch_wgl<SC::SLM>(c, SC::groups(nh), SC::WG, so, kvw, kvc, ix, (const float *)s.attn_w, s.of + qo);
        } else {
            ops41sycl::SparseOutJB<512, 1, 16> so{n_idx, nh, 128};
            so.ry = (float *)(s.obuf + qo);
            so.cosb = cb;
            so.sinb = sbp;
            launch_sg(c, (size_t)nh * g.hd / 64, so, kvw, kvc, ix, (const float *)s.attn_w, s.of + qo);
        }
    }
    oa_m(c, p, hla, xp_oa_m((unsigned)M), ost0[c]);
    // ---- phase 2: output-b rows
    gemv_m(c, p + "attn_output_b.weight", xarena[c] + xoaM, (size_t)g.ototal, xarena[c] + xobM + td0[c], H);
    xchg_m(c, xobM, (unsigned)g.h, (unsigned)M, td0[c], td1[c], 0, XP_H);
    // ---- phase 3: stream post + FFN pre-norm, router, shared and routed gate/up, SwiGLU
    const float *bias = wp<float>(c, p + "exp_probs_b.bias");
    const int nm = tm1[c] - tm0[c], nd = td1[c] - td0[c];
    bool shared_done = false; // the shared expert's gate + up already ran with the router (route_shared_m)
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
        shared_done = mt_rfuse && route_shared_m(c, p, bias);
        if (!shared_done) {
            launch_wgs<2 * 1024 + 6>(c, (size_t)M, 512, ops41sycl::RoutePM{ops41sycl::RouteP{g.experts, 6}, (size_t)g.experts},
                                     (const float *)b.router, bias, b.ids, b.prob);
            tok_set(c, 0);
            rows_launch(c, tokr(hc_finish(c, p + "hc_ffn_", b.pre_f, b.post_f, b.comb_f), FS, 4, 4, 16));
        }
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
        if (mt_iddump) { // OWN_MT_IDDUMP: every token's 6 ids per layer, in token order (u(M) for any block size offline)
            std::fprintf(mt_iddump, "%d %d", L, M);
            for (uint32_t v : hid) std::fprintf(mt_iddump, " %u", v);
            std::fputc('\n', mt_iddump);
        }
        std::sort(hid.begin(), hid.end());
        ids_picks += (long)hid.size();
        ids_unique += (long)(std::unique(hid.begin(), hid.end()) - hid.begin());
        if (L == 0) ++ids_blocks;
    }
    if (mt_eu) { // the slots' expert groups for the expert-major routed rows (gate / up and down share them)
        const bool big = mt_eu_big && (unsigned)M >= mt_eu_big_m;
        unsigned cap = big ? mt_eu_big : mt_eu;
        const auto &eg = we(p + "ffn_gate_exps.weight");
        if (cap > 8 && eg.type == iq3::Type::IQ2_S && eg.cols == 20 * 256) cap = 8; // RoutedU<IQ2_S, 16> spills there
        eu_cap_c[c] = cap;
        ops41sycl::ExpertGroupM k{6u * (unsigned)M, cap};
        k.heavy = big && mt_eu_heavy;
        launch_local<ops41sycl::ExpertGroupM::LM>(c, ops41sycl::ExpertGroupM::items(6u * (unsigned)M), k,
                                                  (const uint32_t *)b.ids, egrp[c]);
    }
    if (!shared_done) {
        gemv_m(c, p + "ffn_gate_shexp.weight", b.xn, H, b.shg, (size_t)g.mid);
        gemv_m(c, p + "ffn_up_shexp.weight", b.xn, H, b.shu, (size_t)g.mid);
    }
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
// defer (OWN_HEAD_CQ, a checked block with the draft): only the launches; head_readback(c) copies the argmax
// candidates to the host on the copy queue after the draft's injection is queued behind them (no idle card while
// the host reads them back; tg87 check timeline: ~59 us per check)
void tpm_head_all(int c, bool defer = false) {
    const int M = mt_n;
    const Scratch &b = scm[c][0];
    const size_t H = g.h, H4 = 4 * H;
    if (!mx_ready[c])
        launch(c, (size_t)M * H, 32, ops41sycl::HcPreAM<Act>{g.h, (unsigned)M, H4, 4, H}, (const act_t *)strm[c],
               (const float *)b.cur_pre, b.x);
    rows_launch(c, tokr(ops41sycl::NormRows<5120, 4>{b.x, wp<float>(c, "output_norm.weight"), b.xn}, H, H));
    const int nl = tv1[c] - tv0[c], G = (nl + AM_CH - 1) / AM_CH;
    gemv_m(c, "output.weight", b.xn, H, tlogm[c], (size_t)nl);
    if (defer) {
        const ops41sycl::ArgmaxP1OM ak{{nl, AM_CH, tv0[c], g.vocab}, (unsigned)G, (unsigned)M, (size_t)nl};
        const float *lg = tlogm[c];
        float *av = tamvm[c];
        int32_t *ai = tamim[c];
        head_ev[c] = qs[c].submit([&](sycl::handler &hh) {
            hh.parallel_for(sycl::nd_range<1>((size_t)M * G * 32, 32),
                            [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] { ak(it, lg, av, ai); });
        });
        kev(c, kname<ops41sycl::ArgmaxP1OM>(), head_ev[c]);
        return;
    }
    launch_sg(c, (size_t)M * G, ops41sycl::ArgmaxP1OM{{nl, AM_CH, tv0[c], g.vocab}, (unsigned)G, (unsigned)M, (size_t)nl},
              (const float *)tlogm[c], tamvm[c], tamim[c]);
    qs[c].memcpy(h_amvm[c].data(), tamvm[c], (size_t)M * G * 4);
    qs[c].memcpy(h_amim[c].data(), tamim[c], (size_t)M * G * 4);
    twait(c);
}
void head_readback(int c) {
    const int M = mt_n, G = (tv1[c] - tv0[c] + AM_CH - 1) / AM_CH;
    const sycl::event ea = head_ev[c];
    auto e1 = cqs[c].submit([&](sycl::handler &hh) { hh.depends_on(ea); hh.memcpy(h_amvm[c].data(), tamvm[c], (size_t)M * G * 4); });
    auto e2 = cqs[c].submit([&](sycl::handler &hh) { hh.depends_on(ea); hh.memcpy(h_amim[c].data(), tamim[c], (size_t)M * G * 4); });
    e1.wait();
    e2.wait();
}
void tpm_card_step(int c) {
    sc_keep[c] = sc[c];
    streams_keep[c] = streams[c];
    if (tl_path && mt_heads) tl_begin_ck(c); // OWN_TIMELINE_CHECKS
    try {
        commit_pending(c);
        x_ready[c] = false;
        fin_attn[c] = false;
        xt[c].on = xt[c].pending = false;
        mx_ready[c] = false;
        auto eng = [&] {
            const auto e0 = std::chrono::steady_clock::now();
            tpm_engram_upload(c);
            eng_t[c] += std::chrono::duration<double>(std::chrono::steady_clock::now() - e0).count();
            ++eng_n[c];
        };
        if (!o.eng_late) eng();
        if (o.layer_begin != 0) throw std::runtime_error("multi-token step needs every layer");
        tpm_embed(c, !o.eng_late); // late: the rows' copy comes after layer 0's launches; the step's end waits
        if (!o.eng_late) tpm_engram_kv(c);
        for (int L = o.layer_begin; L < o.layer_end; ++L) {
            if (o.eng_late && L == 1) { // the host reads the rows while the card runs the embed and layer 0
                eng();
                tpm_engram_kv(c);
            }
            tpm_layer(L, c);
        }
        const bool hdefer = o.head_cq && o.dspark && o.head && mt_heads;
        if (o.head && mt_heads) {
            tok_end(c);
            tpm_head_all(c, hdefer);
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
        } else if (o.dspark) { // a checked block: staged in the block area, after the head (the host does not wait
            dr_inject(c, mt_n, pos, true); // for it; this queue runs it before the next step's work)
            if (hdefer) head_readback(c);
        }
    } catch (...) {
        tok_end(c);
        throw;
    }
    tok_end(c);
    if (tl_path && mt_heads) tl_end(c);
}
// OWN_ENG_AHEAD (prompt reading, with OWN_ENG_EARLY): the engram rows of the tokens after this block (eng_ahead,
// in the engram vocabulary) asked from the disk while the cards run this block; only page-cache hints, so the
// values read later cannot change
void engram_ask_ahead() {
    static const long page = sysconf(_SC_PAGESIZE);
    auto l = iq3::layout(iq3::Type::Q5_K);
    const long p0 = (long)comp_ids.size();
    for (int li = 0; li < 2; ++li) {
        const int L = li == 0 ? 1 : 14;
        if (L < o.layer_begin || L >= o.layer_end || !eng_base[li]) continue;
        for (long q = p0; q < p0 + (long)eng_ahead.size(); ++q) {
            int64_t ids[24];
            engram_hash((int)q, li, ids, -2, &eng_ahead);
            for (int k = 0; k < 24; ++k) {
                const uintptr_t a = (uintptr_t)(eng_base[li] + (size_t)ids[k] * l.bytes), a0 = a & ~(uintptr_t)(page - 1);
                madvise((void *)a0, (size_t)(a + l.bytes - a0), MADV_WILLNEED);
            }
        }
    }
}
public:
std::vector<int64_t> eng_ahead; // the prompt's tokens after the current block (engram vocabulary; OWN_ENG_AHEAD)
// mt tokens in one step (prompt reading); returns the next token after the last one (-1 without the head)
int32_t decode_block_tp(const int32_t *toks, int mt) {
    if (o.tp < 2 || tp_th.empty()) throw std::runtime_error("multi-token step needs OWN_TP > 1 with card threads");
    if (mt < 1 || mt > MTX) throw std::runtime_error("multi-token step: 1.." + std::to_string(MTX) + " tokens (OWN41_MTX)");
    if (pos + mt > max_seq) throw std::runtime_error("position beyond max_seq");
    if (!o.diet || !o.small_fast || o.hc_legacy || !o.hc_ride || !o.rope_out || o.fin_move || o.xtail)
        throw std::runtime_error("multi-token step is written for the default options");
    mt_n = mt;
    mt_toks = toks;
    if (!o.eng_early) tpm_engram_prefetch();
    eng_t0 = o.eng_early && eng_anchor_asked ? 1 : 0;
    eng_anchor_asked = false;
    ++tp_stepn;
    tp_abort = false;
    tp_go();
    if (o.eng_early && !eng_ahead.empty() && (long)comp_ids.size() == pos + mt) engram_ask_ahead();
    tp_join();
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
    if (tl_path) tl_check_done(); // OWN_TIMELINE_CHECKS: clock pairs / the file (every card is done)
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
