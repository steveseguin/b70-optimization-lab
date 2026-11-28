// bench_qkx: prototype of exact attention scores on the matrix engines (fp16 products), against attn_scores_tile.
//   Keys are fp16 in the cache, so one exact fp16 operand. A query row (128 fp32) becomes fp16 parts with their own
//   power-of-two scales: h_p = fp16(x_p), x_{p+1} = (x_p - h_p) 2^e_{p+1}, until nothing is left (3 parts in practice;
//   all 4 kept here are counted). Score = ((C_1 f_1 + C_2 f_2) + C_3 f_3 + ...) x scale, C_p = one DPAS chain over the
//   8 steps of 16 channels from 0, f_p = 2^-(e_1 + .. + e_p). Every product is exact; only the sums round.
//   Shape: a work-group = 8 queries x the 3 heads of one KV head (24 rows = 3 tiles of 8) x NSG sub-groups, each
//   sub-group takes groups of 16 keys (B = 16 channels x 16 keys, loaded column-major straight from the cache).
//   bench_qkx <card> [pos] [ntok]   (BENCH_ITERS; scores written to P as attn_scores_tile does, keys <= position)
#include <cmath>
#include "../../src/engine.hpp"
#include "../../src/attn_tiles.hpp"
#include <sycl/ext/oneapi/matrix/matrix.hpp>
#include <random>

using namespace ink;
namespace jm = sycl::ext::oneapi::experimental::matrix;
using hf = sycl::half;

constexpr int NPM = 4;

// fp32 -> fp16 bits, round to nearest even, for |x| < 65520 (integer operations: no compiler or hardware conversion)
inline uint16_t f2h_rn(float x) {
    const uint32_t u = sycl::bit_cast<uint32_t>(x), sgn = (u >> 16) & 0x8000u, a = u & 0x7fffffffu;
    if (a >= 0x38800000u) { // normal fp16 (>= 2^-14)
        uint32_t e = (a >> 23) - 112u, r = (a >> 13) & 0x3ffu;
        const uint32_t rem = a & 0x1fffu;
        if (rem > 0x1000u || (rem == 0x1000u && (r & 1u))) ++r;
        if (r == 0x400u) { r = 0; ++e; }
        return (uint16_t)(sgn | (e << 10) | r);
    }
    // subnormal or zero: the value in units of 2^-24, rounded to the nearest even integer (exact scaling by 2^24)
    const float v = sycl::bit_cast<float>(a) * 16777216.0f;
    const uint32_t m = (uint32_t)v;
    const float fr = v - (float)m;
    uint32_t r = m + ((fr > 0.5f || (fr == 0.5f && (m & 1u))) ? 1u : 0u);
    return (uint16_t)(sgn | r); // r == 0x400 is the smallest normal, as it should be
}
inline float h2f(uint16_t h) {
    const uint32_t e = (h >> 10) & 0x1fu, m = h & 0x3ffu;
    const float v = e == 0 ? (float)m * 0x1p-24f : sycl::ldexp((float)(1024u + m), (int)e - 25);
    return (h & 0x8000u) ? -v : v;
}

// Q [ntok][nh][128] -> Qp[p][kvh][tp][G][128] (fp16), fsc[p][t nh + h] = 2^-(e_1..e_p) (0 past the row's last part),
// np[t nh + h] = parts used (NPM + 1: not exact in NPM parts)
static sycl::event qsplit(sycl::queue &q, const float *Q, int ntok, int tp, int nh, int nkvh, uint16_t *Qp, float *fsc, int *np) {
    const int G = nh / nkvh;
    return q.parallel_for(sycl::nd_range<1>((size_t)ntok * nh * 16, 16), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(16)]] {
        auto sg = it.get_sub_group();
        const int row = (int)it.get_group(0), lane = (int)sg.get_local_linear_id();
        const int t = row / nh, h = row % nh, kvh = h / G, gi = h % G;
        float x[8];
#pragma unroll
        for (int i = 0; i < 8; ++i) x[i] = Q[(size_t)row * 128 + lane * 8 + i];
        int E = 0, used = 0;
        for (int p = 0; p < NPM; ++p) {
            float m = 0.0f;
#pragma unroll
            for (int i = 0; i < 8; ++i) m = sycl::fmax(m, sycl::fabs(x[i]));
            m = sycl::reduce_over_group(sg, m, sycl::maximum<float>());
            uint16_t *dst = Qp + ((((size_t)p * nkvh + kvh) * tp + t) * G + gi) * 128 + lane * 8;
            if (m == 0.0f) {
#pragma unroll
                for (int i = 0; i < 8; ++i) dst[i] = 0;
                if (lane == 0) fsc[(size_t)p * ntok * nh + row] = 0.0f;
                continue;
            }
            const int e = 14 - sycl::ilogb(m);
            E += e;
            used = p + 1;
#pragma unroll
            for (int i = 0; i < 8; ++i) {
                const float xs = sycl::ldexp(x[i], e);
                const uint16_t b = f2h_rn(xs);
                dst[i] = b;
                x[i] = xs - h2f(b);
            }
            if (lane == 0) fsc[(size_t)p * ntok * nh + row] = sycl::ldexp(1.0f, -E);
        }
        float rest = 0.0f;
#pragma unroll
        for (int i = 0; i < 8; ++i) rest = sycl::fmax(rest, sycl::fabs(x[i]));
        rest = sycl::reduce_over_group(sg, rest, sycl::maximum<float>());
        if (lane == 0) np[row] = rest != 0.0f ? NPM + 1 : used;
    });
}

// scores, keys j <= position (others -inf); P[(t nh + h) ldp + j]. NP parts (rows that need fewer have zero parts).
template <int NP, int NSG> struct QKX {
    const uint16_t *Qp; const float *fsc; const sycl::half *K; int pos0, ntok, tp, nh, nkvh; float scale; float *P; int ldp;
    sycl::local_accessor<float, 1> st;
    [[sycl::reqd_sub_group_size(16)]] void operator()(sycl::nd_item<2> it) const {
        constexpr int G = 3, MT = 8, HD = 128;
        auto sg = it.get_sub_group();
        const int lane = (int)sg.get_local_linear_id(), sgi = (int)sg.get_group_linear_id();
        const int qb = (int)it.get_group(0) / nkvh, kvh = (int)it.get_group(0) % nkvh;
        const int t0 = qb * MT, tn = sycl::min(MT, ntok - t0), pl = pos0 + t0 + tn - 1;
        const int kd = nkvh * HD;
        using A = jm::joint_matrix<sycl::sub_group, hf, jm::use::a, 8, 16, jm::layout::row_major>;
        using B = jm::joint_matrix<sycl::sub_group, hf, jm::use::b, 16, 16, jm::layout::col_major>;
        using C = jm::joint_matrix<sycl::sub_group, float, jm::use::accumulator, 8, 16>;
        auto gp = [](const auto *p) { return sycl::address_space_cast<sycl::access::address_space::global_space, sycl::access::decorated::no>(p); };
        float *sp = &st[0] + (size_t)sgi * NP * 128;
        auto lps = [&](int off) { return st.template get_multi_ptr<sycl::access::decorated::no>() + (size_t)sgi * NP * 128 + off; };
        // this work-group's row factors: f[p][a], rows a = m G + gi
        float f[NP][MT * G];
#pragma unroll
        for (int p = 0; p < NP; ++p)
#pragma unroll
            for (int a = 0; a < MT * G; ++a) {
                const int t = t0 + sycl::min(a / G, tn - 1);
                f[p][a] = fsc[(size_t)p * ntok * nh + (size_t)t * nh + kvh * G + a % G];
            }
        for (int g = sgi; g * 16 <= pl; g += NSG) {
            const int j0 = g * 16;
            C c[3][NP];
#pragma unroll
            for (int rt = 0; rt < 3; ++rt)
#pragma unroll
                for (int p = 0; p < NP; ++p) jm::joint_matrix_fill(sg, c[rt][p], 0.0f);
#pragma unroll
            for (int d = 0; d < 8; ++d) {
                B b;
                jm::joint_matrix_load(sg, b, gp(K + (size_t)j0 * kd + kvh * HD + 16 * d), kd);
#pragma unroll
                for (int rt = 0; rt < 3; ++rt)
#pragma unroll
                    for (int p = 0; p < NP; ++p) {
                        A a;
                        jm::joint_matrix_load(sg, a, gp(reinterpret_cast<const hf *>(Qp) + ((((size_t)p * nkvh + kvh) * tp + t0) * G + rt * 8) * HD + 16 * d), HD);
                        jm::joint_matrix_mad(sg, c[rt][p], a, b, c[rt][p]);
                    }
            }
            const int j = j0 + lane;
#pragma unroll
            for (int rt = 0; rt < 3; ++rt) {
#pragma unroll
                for (int p = 0; p < NP; ++p) jm::joint_matrix_store(sg, c[rt][p], lps(p * 128), 16, jm::layout::row_major);
                sycl::group_barrier(sg);
#pragma unroll
                for (int r = 0; r < 8; ++r) {
                    const int a = rt * 8 + r, m = a / G;
                    float s = sp[r * 16 + lane] * f[0][a];
#pragma unroll
                    for (int p = 1; p < NP; ++p) s = s + sp[p * 128 + r * 16 + lane] * f[p][a];
                    s = s * scale;
                    const int t = t0 + m;
                    if (m < tn) P[((size_t)t * nh + kvh * G + a % G) * ldp + j] = j <= pos0 + t ? s : -INFINITY;
                }
                sycl::group_barrier(sg);
            }
        }
    }
};
template <int NP, int NSG>
static sycl::event qkx(sycl::queue &q, const uint16_t *Qp, const float *fsc, const sycl::half *K, int pos0, int ntok, int tp, int nh,
                       int nkvh, float scale, float *P, int ldp) {
    const int nqb = (ntok + 7) / 8;
    return q.submit([&](sycl::handler &h) {
        sycl::local_accessor<float, 1> st((size_t)NSG * NP * 128, h);
        h.parallel_for(sycl::nd_range<2>(sycl::range<2>((size_t)nqb * nkvh, (size_t)NSG * 16), sycl::range<2>(1, (size_t)NSG * 16)),
                       QKX<NP, NSG>{Qp, fsc, K, pos0, ntok, tp, nh, nkvh, scale, P, ldp, st});
    });
}

int main(int argc, char **argv) {
    if (argc < 2) { std::fprintf(stderr, "usage: bench_qkx <card> [pos] [ntok]\n"); return 2; }
    try {
        Device d(std::atoi(argv[1]));
        const int pos = argc > 2 ? std::atoi(argv[2]) : 100000, ntok = argc > 3 ? std::atoi(argv[3]) : 256;
        const int nh = 24, nkvh = 8, hd = 128, kd = nkvh * hd, cap = (pos + ntok + 64 + 15) / 16 * 16, ldp = cap, G = 3, nr = 16, ext = 1024;
        const int it2 = std::getenv("BENCH_ITERS") ? std::atoi(std::getenv("BENCH_ITERS")) : 10;
        const float scale = 1.0f / std::sqrt((float)hd);
        std::mt19937 rng(7);
        std::normal_distribution<float> nd(0.0f, 1.0f);
        const float qsc = std::getenv("BENCH_QSC") ? (float)std::atof(std::getenv("BENCH_QSC")) : 0.3f;
        std::vector<float> hq((size_t)ntok * nh * hd);
        for (auto &x : hq) x = nd(rng) * qsc;
        // BENCH_Q=<f32 file of rows of 128> (e.g. a dump's Qcur): real query rows, repeated
        if (const char *qf = std::getenv("BENCH_Q")) {
            FILE *fq = std::fopen(qf, "rb");
            if (!fq) throw std::runtime_error("bench_qkx: cannot open BENCH_Q");
            std::vector<float> r;
            float buf[128];
            while (std::fread(buf, 4, 128, fq) == 128) r.insert(r.end(), buf, buf + 128);
            std::fclose(fq);
            const size_t nrw = r.size() / 128;
            for (size_t i = 0; i < hq.size() / 128; ++i) std::memcpy(&hq[i * 128], &r[(i % nrw) * 128], 512);
            std::printf("queries: %zu real rows from %s\n", nrw, qf);
        }
        std::vector<sycl::half> hk((size_t)cap * kd);
        for (auto &x : hk) x = (sycl::half)nd(rng);
        float *Q = d.alloc<float>(hq.size());
        sycl::half *K = d.alloc<sycl::half>(hk.size());
        d.put(Q, hq.data(), hq.size()); d.put(K, hk.data(), hk.size());
        std::vector<float> zr((size_t)ntok * nh * nr, 0.0f), zb((size_t)ext * nr, 0.0f);
        float *Rc = d.alloc<float>(zr.size()), *Rb = d.alloc<float>(zb.size());
        d.put(Rc, zr.data(), zr.size()); d.put(Rb, zb.data(), zb.size());
        const int tp = (ntok + 7) / 8 * 8;
        uint16_t *Qp = d.alloc<uint16_t>((size_t)NPM * nkvh * tp * G * hd);
        d.q.memset(Qp, 0, (size_t)NPM * nkvh * tp * G * hd * 2).wait();
        float *fsc = d.alloc<float>((size_t)NPM * ntok * nh);
        int *npr = d.alloc<int>((size_t)ntok * nh);
        const size_t np = (size_t)ntok * nh * ldp;
        float *P0 = d.alloc<float>(np), *P1 = d.alloc<float>(np);
        double ej = 0.0;
        auto tm = [&](auto f) {
            f(); d.q.wait();
            const double e0 = d.energy_j(), t0 = now_s();
            for (int i = 0; i < it2; ++i) f();
            d.q.wait();
            ej = (d.energy_j() - e0) / it2;
            return (now_s() - t0) / it2 * 1e6;
        };
        const double gmac = (double)ntok * nh * (pos + ntok / 2.0) * hd / 1e9;
        std::printf("pos %d ntok %d: %.2f G multiply-adds per kernel\n", pos, ntok, gmac);
        const double us_sp = tm([&] { qsplit(d.q, Q, ntok, tp, nh, nkvh, Qp, fsc, npr); });
        std::vector<int> hn((size_t)ntok * nh);
        d.get(hn.data(), npr, hn.size());
        int cnt[NPM + 2] = {};
        for (int v : hn) cnt[v]++;
        std::printf("  split %.1f us; rows by parts used: 1 %d, 2 %d, 3 %d, 4 %d, not exact in 4: %d\n", us_sp, cnt[1], cnt[2], cnt[3], cnt[4], cnt[5]);
        d.q.memset(P0, 0x7f, np * 4).wait();
        const double u0 = tm([&] { fz::attn_scores_tile<8, 3, 4>(d.q, Q, K, Rc, Rb, nr, pos, ntok, nh, nkvh, hd, ext, 0, scale, P0, ldp); });
        const double e0 = ej;
        std::printf("  FP32 scores_tile<8,3,4>  %9.1f us %6.2f TMAC/s %7.3f J %4.0f W\n", u0, gmac / u0 * 1e3, e0, e0 / u0 * 1e6);
        auto run = [&](const char *name, auto f) {
            d.q.memset(P1, 0x7f, np * 4).wait();
            const double u = tm(f);
            std::printf("  %-24s %9.1f us %6.2f TMAC/s %7.3f J %4.0f W\n", name, u, gmac / u * 1e3, ej, ej / u * 1e6);
        };
        run("DPAS fp16 3 parts, 8 sg", [&] { qkx<3, 8>(d.q, Qp, fsc, K, pos, ntok, tp, nh, nkvh, scale, P1, ldp); });
        run("DPAS fp16 3 parts, 4 sg", [&] { qkx<3, 4>(d.q, Qp, fsc, K, pos, ntok, tp, nh, nkvh, scale, P1, ldp); });
        run("DPAS fp16 3 parts, 2 sg", [&] { qkx<3, 2>(d.q, Qp, fsc, K, pos, ntok, tp, nh, nkvh, scale, P1, ldp); });
        qkx<3, 4>(d.q, Qp, fsc, K, pos, ntok, tp, nh, nkvh, scale, P1, ldp).wait();
        // accuracy against the exact dot (double) x scale, on sampled rows and keys; units 2^-24 x sum |q k| x scale
        std::vector<float> r0((size_t)ldp), r1((size_t)ldp);
        std::uniform_int_distribution<int> rt(0, ntok - 1), rh(0, nh - 1);
        double e_old = 0, e_new = 0, mo = 0, mn = 0;
        long n = 0, eq = 0;
        for (int sidx = 0; sidx < 64; ++sidx) {
            const int t = rt(rng), h = rh(rng), kvh = h / G;
            d.get(r0.data(), P0 + ((size_t)t * nh + h) * ldp, ldp);
            d.get(r1.data(), P1 + ((size_t)t * nh + h) * ldp, ldp);
            for (int j = 0; j <= pos + t; j += 7) {
                double s = 0, sa = 0;
                for (int c = 0; c < hd; ++c) {
                    const double p = (double)hq[((size_t)t * nh + h) * hd + c] * (double)(float)hk[(size_t)j * kd + kvh * hd + c];
                    s += p; sa += std::fabs(p);
                }
                s *= (double)scale; sa *= (double)scale;
                const double u = sa * 0x1p-24;
                if (u == 0) continue;
                const double a = std::fabs(r0[j] - s) / u, b = std::fabs(r1[j] - s) / u;
                e_old += a; e_new += b; mo = std::max(mo, a); mn = std::max(mn, b); ++n;
                if (r0[j] == r1[j]) ++eq;
            }
        }
        std::printf("  error vs exact (2^-24 x sum |q k| x scale), %ld scores: FP32 tile mean %.3f max %.2f; DPAS mean %.3f max %.2f; same bits %.1f %%\n",
                    n, e_old / n, mo, e_new / n, mn, 100.0 * eq / n);
    } catch (const std::exception &ex) {
        std::fprintf(stderr, "error: %s\n", ex.what());
        return 1;
    }
    return 0;
}
