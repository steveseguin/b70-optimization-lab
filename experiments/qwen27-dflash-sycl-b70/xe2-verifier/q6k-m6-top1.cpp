#define GGML_COMMON_DECL_CPP
#include "ggml-common.h"

#include <sycl/sycl.hpp>

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <fcntl.h>
#include <iostream>
#include <random>
#include <string>
#include <sys/mman.h>
#include <sys/stat.h>
#include <type_traits>
#include <unistd.h>
#include <vector>

constexpr int K = 5120;
constexpr int N = 248320;
constexpr int M = 6;
constexpr int QK = 256;
constexpr int SG = 32;
constexpr int SG_PER_WG = 32;

struct top1_pair {
    float value;
    int32_t id;
};

class quant_kernel;
class logits_kernel;
class fused_top1_kernel;
class logits_partial_kernel;
class top1_reduce_kernel;

static double event_us(const sycl::event & e) {
    return double(e.get_profiling_info<sycl::info::event_profiling::command_end>() -
                  e.get_profiling_info<sycl::info::event_profiling::command_start>()) / 1000.0;
}

static double median(std::vector<double> v) {
    std::sort(v.begin(), v.end());
    return v[v.size()/2];
}

static top1_pair better(top1_pair a, top1_pair b) {
    return b.value > a.value || (b.value == a.value && b.id < a.id) ? b : a;
}

static inline int byte_sub_4(int a, int b) {
    const uint32_t ua = uint32_t(a);
    const uint32_t ub = uint32_t(b);
    return int(((ua | 0x80808080u) - ub) ^ 0x80808080u);
}

static inline int dot4_i8(int a, int b) {
    const uint32_t ua = uint32_t(a);
    const uint32_t ub = uint32_t(b);
    int sum = 0;
#pragma unroll
    for (int j = 0; j < 4; ++j) {
        sum += int(int8_t(ua >> (8*j)))*int(int8_t(ub >> (8*j)));
    }
    return sum;
}

struct mapped_file {
    int fd = -1;
    size_t size = 0;
    const uint8_t * data = nullptr;

    explicit mapped_file(const char * path) {
        fd = open(path, O_RDONLY);
        if (fd < 0) throw std::runtime_error("open failed");
        struct stat st {};
        if (fstat(fd, &st) != 0) throw std::runtime_error("fstat failed");
        size = size_t(st.st_size);
        void * p = mmap(nullptr, size, PROT_READ, MAP_PRIVATE, fd, 0);
        if (p == MAP_FAILED) throw std::runtime_error("mmap failed");
        data = static_cast<const uint8_t *>(p);
    }

    ~mapped_file() {
        if (data) munmap(const_cast<uint8_t *>(data), size);
        if (fd >= 0) close(fd);
    }
};

static void expand_q6k(const block_q6_K * src, int8_t * q, int8_t * scales, uint16_t * d) {
    constexpr int blocks_per_row = K/QK;
    for (int row = 0; row < N; ++row) {
        for (int ib = 0; ib < blocks_per_row; ++ib) {
            const block_q6_K & b = src[size_t(row)*blocks_per_row + ib];
            std::memcpy(scales + size_t(row)*(K/16) + ib*16, b.scales, 16);
            std::memcpy(d + size_t(row)*blocks_per_row + ib, &b.d, sizeof(uint16_t));
            int8_t * dst = q + size_t(row)*K + ib*QK;
            for (int half = 0; half < 2; ++half) {
                for (int l = 0; l < 32; ++l) {
                    dst[half*128 + l + 0] = int8_t((b.ql[half*64 + l] & 15) | (((b.qh[half*32 + l] >> 0) & 3) << 4)) - 32;
                    dst[half*128 + l + 32] = int8_t((b.ql[half*64 + l + 32] & 15) | (((b.qh[half*32 + l] >> 2) & 3) << 4)) - 32;
                    dst[half*128 + l + 64] = int8_t((b.ql[half*64 + l] >> 4) | (((b.qh[half*32 + l] >> 4) & 3) << 4)) - 32;
                    dst[half*128 + l + 96] = int8_t((b.ql[half*64 + l + 32] >> 4) | (((b.qh[half*32 + l] >> 6) & 3) << 4)) - 32;
                }
            }
        }
    }
}

static sycl::event quantize(sycl::queue & queue, const float * x, int8_t * qx, sycl::half * dx, int rows) {
    const int blocks = K/32;
    return queue.submit([&](sycl::handler & h) {
        h.parallel_for<quant_kernel>(sycl::nd_range<1>(size_t(rows)*blocks*SG, SG), [=](sycl::nd_item<1> it)
                [[sycl::reqd_sub_group_size(SG)]] {
            const int block = int(it.get_group(0));
            const int row = block/blocks;
            const int kb = block%blocks;
            const int lane = int(it.get_local_id(0));
            const float v = x[size_t(row)*K + kb*32 + lane];
            const auto sg = it.get_sub_group();
            const float amax = sycl::reduce_over_group(sg, sycl::fabs(v), sycl::maximum<float>());
            const float scale = amax == 0.0f ? 0.0f : amax/127.0f;
            qx[size_t(row)*K + kb*32 + lane] = scale == 0.0f ? 0 : int8_t(sycl::round(v/scale));
            if (lane == 0) dx[size_t(row)*blocks + kb] = sycl::half(scale);
        });
    });
}

template<bool Fused>
static sycl::event dot_kernel(sycl::queue & queue, const int8_t * wq, const int8_t * ws, const uint16_t * wd,
                              const int8_t * xq, const sycl::half * xd, float * logits, top1_pair * partial) {
    constexpr int rows = Fused ? 5 : 6;
    const int groups = (N + SG_PER_WG - 1)/SG_PER_WG;
    using kernel_name = std::conditional_t<Fused, fused_top1_kernel, logits_kernel>;
    return queue.submit([&](sycl::handler & h) {
        sycl::local_accessor<float, 1> local(rows*SG_PER_WG, h);
        h.parallel_for<kernel_name>(
            sycl::nd_range<1>(size_t(groups)*SG_PER_WG*SG, SG_PER_WG*SG), [=](sycl::nd_item<1> it)
            [[sycl::reqd_sub_group_size(SG)]] {
                const int lane = int(it.get_local_id(0)) & (SG - 1);
                const int sgi = int(it.get_local_id(0))/SG;
                const int out = int(it.get_group(0))*SG_PER_WG + sgi;
                const auto sg = it.get_sub_group();
                float acc[rows] = {};
                if (out < N) {
                    for (int ib = 0; ib < K/QK; ++ib) {
                        const sycl::half dh = sycl::bit_cast<sycl::half>(wd[size_t(out)*(K/QK) + ib]);
                        const float sw = float(dh)*float(ws[size_t(out)*(K/16) + ib*16 + lane/2]);
                        const int k0 = ib*QK + lane*8;
                        const int v0 = *reinterpret_cast<const int *>(wq + size_t(out)*K + k0);
                        const int v1 = *reinterpret_cast<const int *>(wq + size_t(out)*K + k0 + 4);
                        for (int r = 0; r < rows; ++r) {
                            const int xr = Fused ? r + 1 : r;
                            const int u0 = *reinterpret_cast<const int *>(xq + size_t(xr)*K + k0);
                            const int u1 = *reinterpret_cast<const int *>(xq + size_t(xr)*K + k0 + 4);
                            const int dot = dot4_i8(v0, u0) + dot4_i8(v1, u1);
                            acc[r] += float(dot)*sw*float(xd[size_t(xr)*(K/32) + ib*8 + lane/4]);
                        }
                    }
                }
                for (int r = 0; r < rows; ++r) {
                    const float sum = sycl::reduce_over_group(sg, acc[r], sycl::plus<float>());
                    if (lane == 0) {
                        if constexpr(Fused) local[sgi*rows + r] = out < N ? sum : -INFINITY;
                        else if (out < N) logits[size_t(r)*N + out] = sum;
                    }
                }
                if constexpr(Fused) {
                    it.barrier(sycl::access::fence_space::local_space);
                    if (int(it.get_local_id(0)) < rows) {
                        const int r = int(it.get_local_id(0));
                        top1_pair best{-INFINITY, int32_t(it.get_group(0)*SG_PER_WG)};
                        for (int s = 0; s < SG_PER_WG; ++s) {
                            const int id = int(it.get_group(0))*SG_PER_WG + s;
                            if (id < N) best = better(best, {local[s*rows + r], id});
                        }
                        partial[size_t(r)*groups + it.get_group(0)] = best;
                    }
                }
            });
    });
}

static sycl::event logits_to_partial(sycl::queue & queue, const float * logits, top1_pair * partial) {
    constexpr int tile = 256;
    const int groups = (N + tile - 1)/tile;
    return queue.submit([&](sycl::handler & h) {
        sycl::local_accessor<float, 1> lv(tile, h);
        sycl::local_accessor<int32_t, 1> li(tile, h);
        h.parallel_for<logits_partial_kernel>(sycl::nd_range<1>(size_t(5)*groups*tile, tile), [=](sycl::nd_item<1> it) {
            const int group = int(it.get_group(0));
            const int r = group/groups;
            const int g = group%groups;
            const int lane = int(it.get_local_id(0));
            const int id = g*tile + lane;
            lv[lane] = id < N ? logits[size_t(r + 1)*N + id] : -INFINITY;
            li[lane] = id;
            it.barrier(sycl::access::fence_space::local_space);
            for (int step = tile/2; step > 0; step /= 2) {
                if (lane < step && (lv[lane + step] > lv[lane] ||
                        (lv[lane + step] == lv[lane] && li[lane + step] < li[lane]))) {
                    lv[lane] = lv[lane + step]; li[lane] = li[lane + step];
                }
                it.barrier(sycl::access::fence_space::local_space);
            }
            if (lane == 0) partial[size_t(r)*groups + g] = {lv[0], li[0]};
        });
    });
}

static sycl::event reduce_top1(sycl::queue & queue, const top1_pair * partial, top1_pair * result, int groups) {
    constexpr int wg = 256;
    return queue.submit([&](sycl::handler & h) {
        sycl::local_accessor<float, 1> lv(wg, h);
        sycl::local_accessor<int32_t, 1> li(wg, h);
        h.parallel_for<top1_reduce_kernel>(sycl::nd_range<1>(5*wg, wg), [=](sycl::nd_item<1> it) {
            const int r = int(it.get_group(0));
            const int lane = int(it.get_local_id(0));
            top1_pair best{-INFINITY, INT32_MAX};
            for (int g = lane; g < groups; g += wg) best = better(best, partial[size_t(r)*groups + g]);
            lv[lane] = best.value; li[lane] = best.id;
            it.barrier(sycl::access::fence_space::local_space);
            for (int step = wg/2; step > 0; step /= 2) {
                if (lane < step && (lv[lane + step] > lv[lane] ||
                        (lv[lane + step] == lv[lane] && li[lane + step] < li[lane]))) {
                    lv[lane] = lv[lane + step]; li[lane] = li[lane + step];
                }
                it.barrier(sycl::access::fence_space::local_space);
            }
            if (lane == 0) result[r] = {lv[0], li[0]};
        });
    });
}

int main(int argc, char ** argv) {
    const char * path = argc > 1 ? argv[1] : nullptr;
    const int iters = argc > 2 ? std::atoi(argv[2]) : 10;
    const uint32_t seed = argc > 3 ? uint32_t(std::strtoul(argv[3], nullptr, 0)) : 0xb70d6u;
    if (!path) return 64;
    constexpr size_t data_offset = 10994816;
    constexpr size_t weight_bytes = size_t(N)*(K/QK)*sizeof(block_q6_K);
    mapped_file model(path);
    if (model.size < data_offset + weight_bytes) throw std::runtime_error("model is too small");
    const auto * source = reinterpret_cast<const block_q6_K *>(model.data + data_offset);

    std::cout << "expanding real output.weight q6_K bytes=" << weight_bytes << std::endl;
    std::vector<int8_t> hq(size_t(N)*K);
    std::vector<int8_t> hs(size_t(N)*(K/16));
    std::vector<uint16_t> hd(size_t(N)*(K/QK));
    expand_q6k(source, hq.data(), hs.data(), hd.data());
    std::vector<float> hx(size_t(M)*K);
    std::mt19937 rng(seed);
    std::normal_distribution<float> dist(0.0f, 0.7f);
    for (float & v : hx) v = dist(rng);

    sycl::queue queue{sycl::gpu_selector_v, sycl::property_list{sycl::property::queue::in_order{},
                                                               sycl::property::queue::enable_profiling{}}};
    auto alloc = [&](size_t bytes) { auto * p = sycl::malloc_device<uint8_t>(bytes, queue); if (!p) throw std::bad_alloc(); return p; };
    auto * wq = reinterpret_cast<int8_t *>(alloc(hq.size()));
    auto * ws = reinterpret_cast<int8_t *>(alloc(hs.size()));
    auto * wd = reinterpret_cast<uint16_t *>(alloc(hd.size()*2));
    auto * x = reinterpret_cast<float *>(alloc(hx.size()*4));
    auto * xq = reinterpret_cast<int8_t *>(alloc(size_t(M)*K));
    auto * xd = reinterpret_cast<sycl::half *>(alloc(size_t(M)*(K/32)*2));
    auto * logits = reinterpret_cast<float *>(alloc(size_t(M)*N*4));
    const int fused_groups = (N + SG_PER_WG - 1)/SG_PER_WG;
    const int prod_groups = (N + 255)/256;
    auto * pf = reinterpret_cast<top1_pair *>(alloc(size_t(5)*fused_groups*sizeof(top1_pair)));
    auto * pp = reinterpret_cast<top1_pair *>(alloc(size_t(5)*prod_groups*sizeof(top1_pair)));
    auto * rf = reinterpret_cast<top1_pair *>(alloc(5*sizeof(top1_pair)));
    auto * rp = reinterpret_cast<top1_pair *>(alloc(5*sizeof(top1_pair)));
    queue.memcpy(wq, hq.data(), hq.size()); queue.memcpy(ws, hs.data(), hs.size());
    queue.memcpy(wd, hd.data(), hd.size()*2); queue.memcpy(x, hx.data(), hx.size()*4).wait();
    hq.clear(); hq.shrink_to_fit(); hs.clear(); hs.shrink_to_fit(); hd.clear(); hd.shrink_to_fit();

    quantize(queue, x, xq, xd, M).wait();
    dot_kernel<false>(queue, wq, ws, wd, xq, xd, logits, nullptr).wait();
    logits_to_partial(queue, logits, pp).wait(); reduce_top1(queue, pp, rp, prod_groups).wait();
    dot_kernel<true>(queue, wq, ws, wd, xq, xd, nullptr, pf).wait(); reduce_top1(queue, pf, rf, fused_groups).wait();
    std::vector<top1_pair> hp(5), hf(5); queue.memcpy(hp.data(), rp, sizeof(top1_pair)*5);
    queue.memcpy(hf.data(), rf, sizeof(top1_pair)*5).wait();
    bool exact = true;
    for (int r = 0; r < 5; ++r) {
        exact &= hp[r].id == hf[r].id;
        std::cout << "row=" << r + 1 << " reference_id=" << hp[r].id << " fused_id=" << hf[r].id
                  << " reference_logit=" << hp[r].value << " fused_logit=" << hf[r].value << std::endl;
    }

    std::vector<double> prod, fused, prod_dot, fused_dot;
    for (int i = 0; i < iters; ++i) {
        auto q0 = quantize(queue, x, xq, xd, M);
        auto k0 = dot_kernel<false>(queue, wq, ws, wd, xq, xd, logits, nullptr);
        auto p0 = logits_to_partial(queue, logits, pp);
        auto r0 = reduce_top1(queue, pp, rp, prod_groups); r0.wait();
        prod.push_back(event_us(q0) + event_us(k0) + event_us(p0) + event_us(r0)); prod_dot.push_back(event_us(k0));
        auto q1 = quantize(queue, x + K, xq + K, xd + K/32, 5);
        auto k1 = dot_kernel<true>(queue, wq, ws, wd, xq, xd, nullptr, pf);
        auto r1 = reduce_top1(queue, pf, rf, fused_groups); r1.wait();
        fused.push_back(event_us(q1) + event_us(k1) + event_us(r1)); fused_dot.push_back(event_us(k1));
    }
    const double pt = median(prod), ft = median(fused);
    std::cout << "seed=" << seed
              << " reference_dot_us=" << median(prod_dot) << " fused_dot_us=" << median(fused_dot)
              << " reference_boundary_us=" << pt << " fused_boundary_us=" << ft
              << " speedup=" << pt/ft << " exact_ids=" << exact
              << " gate=" << (exact && (ft < 2500.0 || pt/ft >= 1.25) ? "PASS" : "FAIL") << std::endl;

    for (void * p : {(void*)wq,(void*)ws,(void*)wd,(void*)x,(void*)xq,(void*)xd,(void*)logits,(void*)pf,(void*)pp,(void*)rf,(void*)rp}) sycl::free(p, queue);
    return exact && (ft < 2500.0 || pt/ft >= 1.25) ? 0 : 3;
}
