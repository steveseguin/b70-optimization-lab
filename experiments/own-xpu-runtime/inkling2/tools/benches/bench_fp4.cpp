// bench_fp4: variants of the NVFP4 expert gate|up + SITU kernel (gemv2.hpp GemvPair<NVFP4P, SituOp>) that decode the
// 4-bit values differently but give the same floats; each is checked bit for bit against the engine's kernel.
//   bench_fp4 <model.gguf> <card> [layer]
// Timing cycles through 16 sets of 8 experts (all 128 of the layer), so the weights come from memory.
#include "../../src/gemv2.hpp"
#include <random>

namespace ink {

// the 16 E2M1 values (kvalues_mxfp4 as floats: 0 1 2 3 4 6 8 12, then the negatives; -0 as +0)
inline float fp4_f(int n) {
    int m = (int)((pl::FP4_MAG >> ((n & 7) * 4)) & 0xF);
    return (float)((n & 8) ? -m : m);
}

// V1: float bits built directly: |v| = 0, 1 or (m << 22) + bits(1.0) for m >= 2; sign from bit 3 (-0 -> +0)
struct DecBits {
    static void decode32(const uint8_t *row, int cols, int c, float *o, float, const float *) {
        uint8_t q[16];
        pl::load_bytes<8>(row + 16 * c, q);
        pl::load_bytes<8>(row + 16 * c + 8, q + 8);
        uint16_t dd;
        std::memcpy(&dd, row + cols / 2 + 2 * c, 2);
        for (int k = 0; k < 2; ++k) {
            float d = pl::ue4m3_bits((uint8_t)(dd >> (8 * k)));
            float *ob = o + 16 * k;
            for (int j = 0; j < 16; ++j) {
                uint32_t b = q[8 * k + (j & 7)];
                uint32_t n = j < 8 ? (b & 0xF) : (b >> 4);
                uint32_t m = n & 7;
                uint32_t u = m < 2 ? m * 0x3F800000u : (m << 22) + 0x3F800000u;
                u |= (m ? (n & 8) : 0u) << 28;
                float f;
                std::memcpy(&f, &u, 4);
                ob[j] = f * d;
            }
        }
    }
};
// V2: lane j of the sub-group holds fp4_f(j); each value is a shuffle from the lane of its nibble
struct DecShuf {
    static void decode32(const uint8_t *row, int cols, int c, float *o, float lut, const float *) {
        auto sg = sycl::ext::oneapi::this_work_item::get_sub_group();
        uint8_t q[16];
        pl::load_bytes<8>(row + 16 * c, q);
        pl::load_bytes<8>(row + 16 * c + 8, q + 8);
        uint16_t dd;
        std::memcpy(&dd, row + cols / 2 + 2 * c, 2);
        for (int k = 0; k < 2; ++k) {
            float d = pl::ue4m3_bits((uint8_t)(dd >> (8 * k)));
            float *ob = o + 16 * k;
            for (int j = 0; j < 8; ++j) {
                uint32_t b = q[8 * k + j];
                ob[j] = sycl::select_from_group(sg, lut, b & 0xF) * d;
                ob[j + 8] = sycl::select_from_group(sg, lut, b >> 4) * d;
            }
        }
    }
};
// V3: a 256-entry table of value pairs (both nibbles of a byte) in global memory (cached)
struct DecPair {
    static void decode32(const uint8_t *row, int cols, int c, float *o, float, const float *tab) {
        uint8_t q[16];
        pl::load_bytes<8>(row + 16 * c, q);
        pl::load_bytes<8>(row + 16 * c + 8, q + 8);
        uint16_t dd;
        std::memcpy(&dd, row + cols / 2 + 2 * c, 2);
        for (int k = 0; k < 2; ++k) {
            float d = pl::ue4m3_bits((uint8_t)(dd >> (8 * k)));
            float *ob = o + 16 * k;
            for (int j = 0; j < 8; ++j) {
                sycl::vec<float, 2> v = *(const sycl::vec<float, 2> *)(tab + 2 * q[8 * k + j]);
                ob[j] = v[0] * d;
                ob[j + 8] = v[1] * d;
            }
        }
    }
};

// V4: an E2M1 code c moved into the exponent/mantissa bits of a half (c&7 << 9, sign c&8 << 12) is the value
// kvalues_mxfp4[c] * 2^-15 exactly (codes 0-1 land on half subnormals); converted to float and multiplied by
// d * 2^15 it gives kvalues_mxfp4[c] * d, the same float as formats.hpp. Two codes per 32-bit operation.
struct DecHalf {
    static inline void pair(uint32_t w, int sh, float d, float &a, float &b) {
        uint32_t bits = ((sh >= 0 ? (w << sh) : (w >> -sh)) & 0x0E000E00u) | ((sh + 3 >= 0 ? (w << (sh + 3)) : (w >> -(sh + 3))) & 0x80008000u);
        sycl::vec<sycl::half, 2> h = sycl::bit_cast<sycl::vec<sycl::half, 2>>(bits);
        a = (float)h[0] * d;
        b = (float)h[1] * d;
    }
    static void decode32(const uint8_t *row, int cols, int c, float *o, float, const float *) {
        sycl::vec<uint32_t, 2> qa = *(const sycl::vec<uint32_t, 2> *)(row + 16 * c);
        sycl::vec<uint32_t, 2> qb = *(const sycl::vec<uint32_t, 2> *)(row + 16 * c + 8);
        uint32_t w[4] = {qa[0], qa[1], qb[0], qb[1]};
        uint16_t dd;
        std::memcpy(&dd, row + cols / 2 + 2 * c, 2);
        for (int k = 0; k < 2; ++k) {
            float d = pl::ue4m3_bits((uint8_t)(dd >> (8 * k))) * 32768.0f;
            float *ob = o + 16 * k;
            for (int h = 0; h < 2; ++h) {
                uint32_t x = w[2 * k + h];
                int j0 = 4 * h;
                // bytes j0..j0+3 of the block: low codes -> ob[j0 + byte], high codes -> ob[8 + j0 + byte]
                pair(x, 9, d, ob[j0 + 0], ob[j0 + 2]);      // low codes of bytes 0, 2
                pair(x, 5, d, ob[8 + j0 + 0], ob[8 + j0 + 2]); // high codes of bytes 0, 2
                pair(x, 1, d, ob[j0 + 1], ob[j0 + 3]);      // low codes of bytes 1, 3
                pair(x, -3, d, ob[8 + j0 + 1], ob[8 + j0 + 3]); // high codes of bytes 1, 3
            }
        }
    }
};

template <class D> struct PairV {
    const uint8_t *A, *B; size_t rb, estride; int rows, cols;
    const int32_t *ids;
    const float *x; int ldx, xdiv;
    SituOp op;
    int sgw;
    const float *tab;
    [[sycl::reqd_sub_group_size(SG)]] void operator()(sycl::nd_item<2> it) const {
        auto sg = it.get_sub_group();
        int k = (int)it.get_group(0);
        int r = (int)it.get_group(1) * sgw + (int)sg.get_group_linear_id();
        if (r >= rows) return;
        int lane = (int)sg.get_local_linear_id();
        float lut = fp4_f(lane);
        size_t eo = (size_t)ids[k] * estride;
        const uint8_t *ra = A + eo + (size_t)r * rb, *rbp = B + eo + (size_t)r * rb;
        const float *xv0 = x + (size_t)(k / xdiv) * ldx;
        float acc[2] = {0.0f, 0.0f};
        const int nc = cols / 32;
        for (int c = lane; c < nc; c += SG) {
            float xs[32];
            load_x32(xv0 + 32 * c, xs);
            for (int j = 0; j < 2; ++j) {
                float o[32];
                D::decode32(j ? rbp : ra, cols, c, o, lut, tab);
                float s = 0.0f;
                for (int i = 0; i < 32; ++i) s += o[i] * xs[i];
                acc[j] += s;
            }
        }
        float va = sg_sum(sg, acc[0]), vb = sg_sum(sg, acc[1]);
        if (lane == 0) op(k, r, va, vb);
    }
};

// rotated chunk assignment: row j's lane partials are computed by physical lane (v - rot_j) & 15 for virtual lane v
// (chunks v, v+16, ...), then moved back to lane v before the same butterfly: the same sums, better balanced lanes
template <class D> struct PairRot {
    const uint8_t *A, *B; size_t rb, estride; int rows, cols;
    const int32_t *ids;
    const float *x; int ldx, xdiv;
    SituOp op;
    int sgw;
    [[sycl::reqd_sub_group_size(SG)]] void operator()(sycl::nd_item<2> it) const {
        auto sg = it.get_sub_group();
        int k = (int)it.get_group(0);
        int r = (int)it.get_group(1) * sgw + (int)sg.get_group_linear_id();
        if (r >= rows) return;
        int lane = (int)sg.get_local_linear_id();
        size_t eo = (size_t)ids[k] * estride;
        const float *xv0 = x + (size_t)(k / xdiv) * ldx;
        const int nc = cols / 32;
        float out[2];
        for (int j = 0; j < 2; ++j) {
            const uint8_t *row = (j ? B : A) + eo + (size_t)r * rb;
            const int rot = j * 8;
            int vl = (lane + rot) & 15;
            float acc = 0.0f;
            for (int c = vl; c < nc; c += SG) {
                float xs[32], o[32];
                load_x32(xv0 + 32 * c, xs);
                pl::NVFP4P::decode32(row, cols, c, o);
                float s = 0.0f;
                for (int i = 0; i < 32; ++i) s += o[i] * xs[i];
                acc += s;
            }
            float canon = sycl::select_from_group(sg, acc, (uint32_t)((lane - rot) & 15));
            out[j] = sg_sum(sg, canon);
        }
        if (lane == 0) op(k, r, out[0], out[1]);
    }
};
template <class D, int R> struct RoutedRot {
    const uint8_t *W; size_t rb, estride; int rows, cols;
    const int32_t *ids;
    const float *x; int ldx;
    float *y; int ldy;
    int sgw;
    [[sycl::reqd_sub_group_size(SG)]] void operator()(sycl::nd_item<2> it) const {
        auto sg = it.get_sub_group();
        int k = (int)it.get_group(0);
        int r0 = ((int)it.get_group(1) * sgw + (int)sg.get_group_linear_id()) * R;
        if (r0 >= rows) return;
        int lane = (int)sg.get_local_linear_id();
        const uint8_t *base = W + (size_t)ids[k] * estride;
        const float *xv0 = x + (size_t)k * ldx;
        const int nc = cols / 32;
        for (int j = 0; j < R; ++j) {
            if (r0 + j >= rows) break;
            const uint8_t *row = base + (size_t)(r0 + j) * rb;
            const int rot = j * (16 / R);
            int vl = (lane + rot) & 15;
            float acc = 0.0f;
            for (int c = vl; c < nc; c += SG) {
                float xs[32], o[32];
                load_x32(xv0 + 32 * c, xs);
                D::decode32(row, cols, c, o);
                float s = 0.0f;
                for (int i = 0; i < 32; ++i) s += o[i] * xs[i];
                acc += s;
            }
            float canon = sycl::select_from_group(sg, acc, (uint32_t)((lane - rot) & 15));
            float v = sg_sum(sg, canon);
            if (lane == 0) y[(size_t)k * ldy + r0 + j] = v;
        }
    }
};

} // namespace ink

int main(int argc, char **argv) {
    using namespace ink;
    if (argc < 3) { std::fprintf(stderr, "usage: bench_fp4 <model.gguf> <card> [layer]\n"); return 2; }
    try {
        GGUF g(argv[1]);
        Device d(std::atoi(argv[2]));
        Weights w;
        w.upload(d, g, false);
        const int layer = argc > 3 ? std::atoi(argv[3]) : 0;
        const int iters = std::getenv("BENCH_ITERS") ? std::atoi(std::getenv("BENCH_ITERS")) : 200;
        const std::string pre = "blk." + std::to_string(layer) + ".";
        const Tensor *t = g.find(pre + "ffn_gate_up_exps.weight");
        const Tensor *ts = g.find(pre + "ffn_gate_up_exps.scale");
        if (!t || t->type != G_NVFP4) throw std::runtime_error("no NVFP4 gate_up in layer " + std::to_string(layer));
        const int cols = (int)t->ne[0], rows2 = (int)t->ne[1], ne = (int)t->ne[2], nff = rows2 / 2, K = 8, NS = 16;
        WView v{t, nullptr, planar_stride(*t), K_NVFP4P};
        uint8_t *buf = d.alloc<uint8_t>(v.rb * (size_t)t->rows());
        planar_repack(d.q, *t, w[t->name], buf).wait();
        v.p = buf;
        const size_t es = v.rb * (size_t)rows2;
        std::mt19937 rng(7);
        std::normal_distribution<float> nd(0.0f, 1.0f);
        std::vector<float> hx(cols);
        for (auto &x : hx) x = nd(rng);
        std::vector<int32_t> hid((size_t)K * NS);
        for (int s = 0; s < NS; ++s) for (int k = 0; k < K; ++k) hid[(size_t)s * K + k] = ((s * K + k) * 37 + 11) % ne;
        float *x = d.alloc<float>(cols), *h0 = d.alloc<float>((size_t)K * nff), *h1 = d.alloc<float>((size_t)K * nff);
        int32_t *ids = d.alloc<int32_t>(hid.size());
        d.put(x, hx.data(), cols);
        d.put(ids, hid.data(), hid.size());
        std::vector<float> tabh(512);
        for (int b = 0; b < 256; ++b) { tabh[2 * b] = fp4_f(b & 0xF); tabh[2 * b + 1] = fp4_f(b >> 4); }
        float *tab = d.alloc<float>(512);
        d.put(tab, tabh.data(), 512);
        const float *sc = ts ? (const float *)w[ts->name] : nullptr;
        const size_t bytes = (size_t)t->row_bytes() * rows2 * K;
        auto timeit = [&](auto &&launch) {
            for (int i = 0; i < 4; ++i) launch(i);
            d.q.wait();
            double t0 = now_s();
            for (int i = 0; i < iters; ++i) launch(i + 1);
            d.q.wait();
            double us = (now_s() - t0) / iters * 1e6;
            launch(0);
            d.q.wait();
            return us;
        };
        auto idp = [&](int i) { return ids + (size_t)(i % NS) * K; };
        std::vector<float> r0((size_t)K * nff), r1(r0.size());
        for (int sgw : {2, 4}) {
            double us0 = timeit([&](int i) {
                gemv_pair(d.q, v, v.p + (size_t)nff * v.rb, es, nff, idp(i), K, x, cols, K,
                          SituOp{sc, idp(i), 4.0f, 25.0f, h0, nff}, sgw);
            });
            d.get(r0.data(), h0, r0.size());
            std::printf("layer %d gate_up NVFP4 %d x %d x8  %.2f MB  sg%d engine kernel %8.2f us %6.1f GB/s\n", layer, rows2,
                        cols, bytes / 1e6, sgw, us0, bytes / us0 / 1e3);
            auto run = [&]<class D>(const char *name) {
                d.q.memset(h1, 0, r1.size() * 4).wait();
                double us = timeit([&](int i) {
                    int ngr = (nff + sgw - 1) / sgw;
                    sycl::nd_range<2> nr(sycl::range<2>((size_t)K, (size_t)ngr * sgw * SG), sycl::range<2>(1, (size_t)sgw * SG));
                    d.q.parallel_for(nr, PairV<D>{v.p, v.p + (size_t)nff * v.rb, v.rb, es, nff, cols, idp(i), x, cols, K,
                                                  SituOp{sc, idp(i), 4.0f, 25.0f, h1, nff}, sgw, tab});
                });
                d.get(r1.data(), h1, r1.size());
                long bad = -1;
                for (size_t i = 0; i < r1.size(); ++i) if (std::memcmp(&r0[i], &r1[i], 4)) { bad = (long)i; break; }
                std::printf("   %-28s sg%d %8.2f us %6.1f GB/s  %s\n", name, sgw, us, bytes / us / 1e3,
                            bad < 0 ? "same" : ("DIFF at " + std::to_string(bad)).c_str());
            };
            run.template operator()<DecBits>("float bits");
            run.template operator()<DecShuf>("sub-group shuffle table");
            run.template operator()<DecPair>("byte-pair table (global)");
            run.template operator()<DecHalf>("half bits");
            {
                d.q.memset(h1, 0, r1.size() * 4).wait();
                double us = timeit([&](int i) {
                    int ngr = (nff + sgw - 1) / sgw;
                    sycl::nd_range<2> nr(sycl::range<2>((size_t)K, (size_t)ngr * sgw * SG), sycl::range<2>(1, (size_t)sgw * SG));
                    d.q.parallel_for(nr, PairRot<pl::NVFP4P>{v.p, v.p + (size_t)nff * v.rb, v.rb, es, nff, cols, idp(i), x, cols, K,
                                                             SituOp{sc, idp(i), 4.0f, 25.0f, h1, nff}, sgw});
                });
                d.get(r1.data(), h1, r1.size());
                long bad = -1;
                for (size_t i = 0; i < r1.size(); ++i) if (std::memcmp(&r0[i], &r1[i], 4)) { bad = (long)i; break; }
                std::printf("   %-28s sg%d %8.2f us %6.1f GB/s  %s\n", "rotated lanes (pair)", sgw, us, bytes / us / 1e3,
                            bad < 0 ? "same" : ("DIFF at " + std::to_string(bad)).c_str());
            }
        }
        // the down product: engine kernel (R2) against rotated lanes with 2 and 4 rows
        const Tensor *td = g.find(pre + "ffn_down_exps.weight");
        if (td && td->type == G_NVFP4) {
            const int dc = (int)td->ne[0], dr = (int)td->ne[1];
            WView vd{td, nullptr, planar_stride(*td), K_NVFP4P};
            uint8_t *bd = d.alloc<uint8_t>(vd.rb * (size_t)td->rows());
            planar_repack(d.q, *td, w[td->name], bd).wait();
            vd.p = bd;
            const size_t esd = vd.rb * (size_t)dr, bytesd = (size_t)td->row_bytes() * dr * K;
            std::vector<float> hxd((size_t)K * dc);
            for (auto &q : hxd) q = nd(rng);
            float *xd = d.alloc<float>(hxd.size()), *y0 = d.alloc<float>((size_t)K * dr), *y1 = d.alloc<float>((size_t)K * dr);
            d.put(xd, hxd.data(), hxd.size());
            std::vector<float> q0((size_t)K * dr), q1(q0.size());
            for (int sgw : {2, 4}) {
                double us0 = timeit([&](int i) { gemv_routed_v(d.q, vd, idp(i), K, xd, dc, 1, y0, dr, Tune{2, sgw}); });
                d.get(q0.data(), y0, q0.size());
                std::printf("layer %d down NVFP4 %d x %d x8  %.2f MB  sg%d engine kernel %8.2f us %6.1f GB/s\n", layer, dr, dc,
                            bytesd / 1e6, sgw, us0, bytesd / us0 / 1e3);
                auto rr = [&]<int R>() {
                    d.q.memset(y1, 0, q1.size() * 4).wait();
                    double us = timeit([&](int i) {
                        int nsg = (dr + R - 1) / R, ngr = (nsg + sgw - 1) / sgw;
                        sycl::nd_range<2> nr(sycl::range<2>((size_t)K, (size_t)ngr * sgw * SG), sycl::range<2>(1, (size_t)sgw * SG));
                        d.q.parallel_for(nr, RoutedRot<pl::NVFP4P, R>{vd.p, vd.rb, esd, dr, dc, idp(i), xd, dc, y1, dr, sgw});
                    });
                    d.get(q1.data(), y1, q1.size());
                    long bad = -1;
                    for (size_t i = 0; i < q1.size(); ++i) if (std::memcmp(&q0[i], &q1[i], 4)) { bad = (long)i; break; }
                    std::printf("   rotated lanes R%d              sg%d %8.2f us %6.1f GB/s  %s\n", R, sgw, us, bytesd / us / 1e3,
                                bad < 0 ? "same" : ("DIFF at " + std::to_string(bad)).c_str());
                };
                rr.template operator()<2>();
                rr.template operator()<4>();
            }
        }
    } catch (std::exception &ex) {
        std::fprintf(stderr, "error: %s\n", ex.what());
        return 1;
    }
    return 0;
}
