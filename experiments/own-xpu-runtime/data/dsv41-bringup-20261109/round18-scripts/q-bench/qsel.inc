// TopKSelQ<MAXC>: TopKSelR<false>'s select with every key loaded once into registers. Item i takes the positions
// [i c, (i + 1) c), c = ceil(n / 1,024) rounded up to a multiple of 8 (<= MAXC), loads them 8 at a time
// (32-byte vectors), and runs the four radix passes and the walk by ranges from its registers: the same
// threshold, the same ties (the lowest positions equal to it) and the same list as TopKSelP / TopKSelR.
template <int MAXC> struct TopKSelQ {
    using KP = TopKSelP<false>;
    static constexpr int WG = KP::WG, NSG = KP::NSG, V = 8;
    KP p;
    static int span(int n) { return ((n + WG - 1) / WG + V - 1) / V * V; }
    void operator()(sycl::nd_item<1> it, const float *sc, const uint8_t *cand_in, int32_t *out, uint8_t *, float *lm) const {
        auto g = it.get_group();
        const int lid = (int)it.get_local_linear_id();
        const int sgi = (int)it.get_sub_group().get_group_linear_id();
        uint32_t *hist = reinterpret_cast<uint32_t *>(lm), *misc = hist + NSG * 256;
        const int n = p.n;
        const bool all = p.k >= n;
        const int c = span(n), j0 = sycl::min(n, lid * c), cnt = sycl::min(n, j0 + c) - j0;
        const uint32_t KNEG = KP::okey(-INFINITY);
        const bool masked = cand_in != nullptr && p.cand_n > 0;
        uint32_t kr[MAXC];
#pragma unroll
        for (int v = 0; v < MAXC / V; ++v) {
            const int m0 = v * V;
            if (m0 < cnt) {
                if (m0 + V <= cnt) {
                    const auto x = *reinterpret_cast<const sycl::vec<float, V> *>(sc + j0 + m0);
                    sycl::vec<uint8_t, V> f(1);
                    if (masked) {
                        if (j0 + m0 + V <= p.cand_n) f = *reinterpret_cast<const sycl::vec<uint8_t, V> *>(cand_in + j0 + m0);
                        else
#pragma unroll
                            for (int u = 0; u < V; ++u) f[u] = j0 + m0 + u < p.cand_n ? cand_in[j0 + m0 + u] : 1;
                    }
#pragma unroll
                    for (int u = 0; u < V; ++u) kr[m0 + u] = f[u] ? KP::okey(x[u]) : KNEG;
                } else {
#pragma unroll
                    for (int u = 0; u < V; ++u) kr[m0 + u] = m0 + u < cnt ? KP::okey(p.val(sc, cand_in, j0 + m0 + u)) : 0u;
                }
            }
        }
        uint32_t T = 0, rem = 0;
        if (!all) {
            uint32_t prefix = 0, pmask = 0;
            rem = (uint32_t)p.k;
            for (int pass = 0; pass < 4; ++pass) {
                const int shift = 24 - 8 * pass;
                for (int i = lid; i < NSG * 256; i += WG) hist[i] = 0;
                sycl::group_barrier(g);
#pragma unroll
                for (int m = 0; m < MAXC; ++m)
                    if (m < cnt && (kr[m] & pmask) == prefix)
                        sycl::atomic_ref<uint32_t, sycl::memory_order::relaxed, sycl::memory_scope::work_group,
                                         sycl::access::address_space::local_space>(hist[sgi * 256 + ((kr[m] >> shift) & 255u)])
                            .fetch_add(1u);
                sycl::group_barrier(g);
                uint32_t tot = 0;
                if (lid < 256)
                    for (int s2 = 0; s2 < NSG; ++s2) tot += hist[s2 * 256 + (255 - lid)];
                const uint32_t inc = sycl::inclusive_scan_over_group(g, tot, sycl::plus<uint32_t>());
                const uint32_t exc = inc - tot;
                if (lid < 256 && exc < rem && rem <= inc) {
                    misc[0] = 255u - (uint32_t)lid;
                    misc[1] = exc;
                }
                sycl::group_barrier(g);
                prefix |= misc[0] << shift;
                pmask |= 255u << shift;
                rem -= misc[1];
                sycl::group_barrier(g);
            }
            T = prefix;
        }
        uint32_t ngt = 0, neq = 0;
#pragma unroll
        for (int m = 0; m < MAXC; ++m)
            if (m < cnt) {
                ngt += (all || kr[m] > T) ? 1u : 0u;
                neq += (!all && kr[m] == T) ? 1u : 0u;
            }
        const uint32_t gtb = sycl::exclusive_scan_over_group(g, ngt, sycl::plus<uint32_t>());
        const uint32_t eqb = sycl::exclusive_scan_over_group(g, neq, sycl::plus<uint32_t>());
        uint32_t base = gtb + sycl::min(eqb, rem), eqs = eqb;
#pragma unroll
        for (int m = 0; m < MAXC; ++m)
            if (m < cnt) {
                const bool gt = all || kr[m] > T, eq = !all && kr[m] == T;
                const bool sel = gt || (eq && eqs < rem);
                if (eq) ++eqs;
                if (sel) {
                    if (base < (uint32_t)p.outn) out[base] = j0 + m + p.add;
                    ++base;
                }
            }
        const uint32_t tot = sycl::reduce_over_group(g, ngt, sycl::plus<uint32_t>()) +
                             sycl::min(sycl::reduce_over_group(g, neq, sycl::plus<uint32_t>()), rem);
        for (int i = (int)tot + lid; i < p.outn; i += WG) out[i] = -1;
    }
};
