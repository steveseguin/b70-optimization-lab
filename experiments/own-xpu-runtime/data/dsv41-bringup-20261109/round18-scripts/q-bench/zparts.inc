// parts of TopKSelR<false> alone (plain select, no mask), for timing only
//   ZP<A>  the four radix passes only (A = 0: the local adds replaced by a register sum; 1: as R), T -> out[0]
//   ZW     R's walk by ranges only, with T and rem given (contiguous positions per item: uncoalesced loads)
//   ZC     a walk with coalesced loads: sub-group s takes positions [s 32 c, (s + 1) 32 c), lane l reads
//          s 32 c + 32 m + l at step m; sub-group scans place the entries (position order = (m, lane) order),
//          one work-group scan of the sub-groups' totals; the same list as R's walk
template <int A> struct ZP {
    using KP = TopKSelP<false>;
    static constexpr int WG = KP::WG, NSG = KP::NSG;
    KP p;
    void operator()(sycl::nd_item<1> it, const float *sc, int32_t *out, float *lm) const {
        auto g = it.get_group();
        const int lid = (int)it.get_local_linear_id();
        const int sgi = (int)it.get_sub_group().get_group_linear_id();
        uint32_t *hist = reinterpret_cast<uint32_t *>(lm), *misc = hist + NSG * 256;
        const int n = p.n;
        uint32_t prefix = 0, pmask = 0, rem = (uint32_t)p.k, acc = 0;
        for (int pass = 0; pass < 4; ++pass) {
            const int shift = 24 - 8 * pass;
            for (int i = lid; i < NSG * 256; i += WG) hist[i] = 0;
            sycl::group_barrier(g);
            for (int j = lid; j < n; j += WG) {
                const uint32_t kk = KP::okey(sc[j]);
                if ((kk & pmask) == prefix) {
                    if constexpr (A)
                        sycl::atomic_ref<uint32_t, sycl::memory_order::relaxed, sycl::memory_scope::work_group,
                                         sycl::access::address_space::local_space>(hist[sgi * 256 + ((kk >> shift) & 255u)])
                            .fetch_add(1u);
                    else acc += (kk >> shift) & 255u;
                }
            }
            if constexpr (!A) hist[sgi * 256 + (acc & 255u)] += 1u + (acc >> 30); // keep the loads
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
        if (lid == 0) { out[0] = (int32_t)prefix; out[1] = (int32_t)rem; }
    }
};
struct ZW {
    using KP = TopKSelP<false>;
    static constexpr int WG = KP::WG;
    KP p;
    uint32_t T, rem;
    void operator()(sycl::nd_item<1> it, const float *sc, int32_t *out, float *) const {
        auto g = it.get_group();
        const int lid = (int)it.get_local_linear_id();
        const int n = p.n;
        const int c = (n + WG - 1) / WG, j0 = sycl::min(n, lid * c), j1 = sycl::min(n, j0 + c);
        uint32_t ngt = 0, neq = 0;
        for (int j = j0; j < j1; ++j) {
            const uint32_t kk = KP::okey(sc[j]);
            ngt += kk > T ? 1u : 0u;
            neq += kk == T ? 1u : 0u;
        }
        const uint32_t gtb = sycl::exclusive_scan_over_group(g, ngt, sycl::plus<uint32_t>());
        const uint32_t eqb = sycl::exclusive_scan_over_group(g, neq, sycl::plus<uint32_t>());
        uint32_t base = gtb + sycl::min(eqb, rem), eqs = eqb;
        for (int j = j0; j < j1; ++j) {
            const uint32_t kk = KP::okey(sc[j]);
            const bool gt = kk > T, eq = kk == T;
            const bool sel = gt || (eq && eqs < rem);
            if (eq) ++eqs;
            if (sel) {
                if (base < (uint32_t)p.outn) out[base] = j + p.add;
                ++base;
            }
        }
        const uint32_t tot = sycl::reduce_over_group(g, ngt, sycl::plus<uint32_t>()) +
                             sycl::min(sycl::reduce_over_group(g, neq, sycl::plus<uint32_t>()), rem);
        for (int i = (int)tot + lid; i < p.outn; i += WG) out[i] = -1;
    }
};
struct ZC {
    using KP = TopKSelP<false>;
    static constexpr int WG = KP::WG, NSG = KP::NSG;
    KP p;
    uint32_t T, rem;
    void operator()(sycl::nd_item<1> it, const float *sc, int32_t *out, float *) const {
        auto g = it.get_group();
        sycl::sub_group sg = it.get_sub_group();
        const int lid = (int)it.get_local_linear_id();
        const int sgi = (int)sg.get_group_linear_id(), lane = (int)sg.get_local_linear_id();
        const int n = p.n;
        const int c = (n + WG - 1) / WG, s0 = sgi * 32 * c;
        uint32_t ngt = 0, neq = 0;
        for (int m = 0; m < c; ++m) {
            const int j = s0 + 32 * m + lane;
            if (j < n) {
                const uint32_t kk = KP::okey(sc[j]);
                ngt += kk > T ? 1u : 0u;
                neq += kk == T ? 1u : 0u;
            }
        }
        // the sub-group's totals, then their places among the sub-groups (one work-group scan, lane 0 carries them)
        const uint32_t sgt = sycl::reduce_over_group(sg, ngt, sycl::plus<uint32_t>());
        const uint32_t seq = sycl::reduce_over_group(sg, neq, sycl::plus<uint32_t>());
        const uint32_t gtb = sycl::exclusive_scan_over_group(g, lane == 0 ? sgt : 0u, sycl::plus<uint32_t>());
        const uint32_t eqb = sycl::exclusive_scan_over_group(g, lane == 0 ? seq : 0u, sycl::plus<uint32_t>());
        const uint32_t gtb0 = sycl::select_from_group(sg, gtb, 0), eqb0 = sycl::select_from_group(sg, eqb, 0);
        uint32_t gts = gtb0, eqs = eqb0; // entries above T / equal to T before step m in this sub-group's range
        for (int m = 0; m < c; ++m) {
            const int j = s0 + 32 * m + lane;
            const bool in = j < n;
            const uint32_t kk = in ? KP::okey(sc[j]) : 0u;
            const bool gt = in && kk > T, eq = in && kk == T;
            const uint32_t ge = sycl::exclusive_scan_over_group(sg, gt ? 1u : 0u, sycl::plus<uint32_t>());
            const uint32_t ee = sycl::exclusive_scan_over_group(sg, eq ? 1u : 0u, sycl::plus<uint32_t>());
            const uint32_t er = eqs + ee; // equal entries before this position
            const bool sel = gt || (eq && er < rem);
            // place: entries above T before it + the equal ones kept before it
            const uint32_t pos = gts + ge + sycl::min(er, rem);
            if (sel && pos < (uint32_t)p.outn) out[pos] = j + p.add;
            gts += sycl::reduce_over_group(sg, gt ? 1u : 0u, sycl::plus<uint32_t>());
            eqs += sycl::reduce_over_group(sg, eq ? 1u : 0u, sycl::plus<uint32_t>());
        }
        const uint32_t tot = sycl::reduce_over_group(g, ngt, sycl::plus<uint32_t>()) +
                             sycl::min(sycl::reduce_over_group(g, neq, sycl::plus<uint32_t>()), rem);
        for (int i = (int)tot + lid; i < p.outn; i += WG) out[i] = -1;
    }
};
