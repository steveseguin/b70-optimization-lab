#include <sycl/sycl.hpp>
#include <sycl/ext/intel/esimd.hpp>
#include <sycl/ext/intel/esimd/xmx/dpas.hpp>
#include <oneapi/dnnl/dnnl.hpp>
#include <oneapi/dnnl/dnnl_sycl.hpp>

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>

namespace esimd = sycl::ext::intel::esimd;
namespace xmx = sycl::ext::intel::esimd::xmx;
using bf16 = sycl::ext::oneapi::bfloat16;

namespace {

constexpr int kM = 4992;
constexpr int kN = 16;
constexpr int kK = 6656;
constexpr int kMTile = 16;
constexpr int kNTile = 8;
constexpr int kKTile = 16;
#ifndef MUSE_BF16_WG
#define MUSE_BF16_WG 8
#endif
#ifndef MUSE_BF16_KBLOCK
#define MUSE_BF16_KBLOCK 128
#endif
#ifndef MUSE_BF16_ROW_TILES
#define MUSE_BF16_ROW_TILES 2
#endif
constexpr int kWG = MUSE_BF16_WG;
constexpr int kKBlock = MUSE_BF16_KBLOCK;
constexpr int kRowTiles = MUSE_BF16_ROW_TILES;

class MuseBf16DpasKernel;
class MuseBf16DpasSlmKernel;
class MuseBf16DpasMultiRowKernel;

uint32_t xorshift32(uint32_t & state) {
    state ^= state << 13;
    state ^= state >> 17;
    state ^= state << 5;
    return state;
}

float signed_unit(uint32_t & state) {
    const int value = int(xorshift32(state) & 0xffffu) - 32768;
    return float(value) / 32768.0f;
}

std::vector<bf16> pack_weight_vnni(const std::vector<bf16> & weight) {
    std::vector<bf16> packed(weight.size());
    size_t dst = 0;
    for (int mb = 0; mb < kM; mb += kMTile) {
        for (int kb = 0; kb < kK; kb += kKTile) {
            for (int pair = 0; pair < kKTile / 2; ++pair) {
                for (int col = 0; col < kMTile; ++col) {
                    packed[dst++] = weight[size_t(mb + col) * kK + kb + 2 * pair];
                    packed[dst++] = weight[size_t(mb + col) * kK + kb + 2 * pair + 1];
                }
            }
        }
    }
    if (dst != packed.size()) {
        throw std::runtime_error("internal VNNI packing size mismatch");
    }
    return packed;
}

sycl::event launch_dpas(
        sycl::queue & queue,
        const bf16 * packed_weight,
        const bf16 * activation,
        float * output) {
    return queue.submit([&](sycl::handler & cgh) {
        cgh.parallel_for<MuseBf16DpasKernel>(sycl::range<1>(kM / kMTile),
                [=](sycl::id<1> item) [[intel::sycl_explicit_simd]] {
            const int mb = int(item[0]) * kMTile;
            esimd::simd<float, kNTile * kMTile> accum0(0.0f);
            esimd::simd<float, kNTile * kMTile> accum1(0.0f);

            for (int kb = 0; kb < kK; kb += kKTile) {
                const size_t packed_offset =
                    (size_t(item[0]) * (kK / kKTile) + kb / kKTile) *
                    kKTile * kMTile;
                const auto weights =
                    esimd::block_load<bf16, kKTile * kMTile>(packed_weight + packed_offset);

                esimd::simd<bf16, kNTile * kKTile> act0;
                esimd::simd<bf16, kNTile * kKTile> act1;
#pragma unroll
                for (int token = 0; token < kNTile; ++token) {
                    act0.template select<kKTile, 1>(token * kKTile) =
                        esimd::block_load<bf16, kKTile>(
                            activation + size_t(token) * kK + kb);
                    act1.template select<kKTile, 1>(token * kKTile) =
                        esimd::block_load<bf16, kKTile>(
                            activation + size_t(token + kNTile) * kK + kb);
                }

                accum0 = xmx::dpas<8, kNTile, float, float, bf16, bf16>(
                    accum0, weights, act0);
                accum1 = xmx::dpas<8, kNTile, float, float, bf16, bf16>(
                    accum1, weights, act1);
            }

#pragma unroll
            for (int token = 0; token < kNTile; ++token) {
                esimd::block_store<float, kMTile>(
                    output + size_t(token) * kM + mb,
                    accum0.template select<kMTile, 1>(token * kMTile).read());
                esimd::block_store<float, kMTile>(
                    output + size_t(token + kNTile) * kM + mb,
                    accum1.template select<kMTile, 1>(token * kMTile).read());
            }
        });
    });
}

sycl::event launch_dpas_slm(
        sycl::queue & queue,
        const bf16 * packed_weight,
        const bf16 * activation,
        float * output) {
    static_assert(kKBlock % (kWG * kKTile) == 0);
    static_assert((kM / kMTile) % kWG == 0);
    constexpr int kSlice = kKBlock / kWG;
    constexpr int kSlmBytes = kN * kKBlock * sizeof(bf16);

    return queue.submit([&](sycl::handler & cgh) {
        cgh.parallel_for<MuseBf16DpasSlmKernel>(
                sycl::nd_range<1>(kM / kMTile, kWG),
                [=](sycl::nd_item<1> item) [[intel::sycl_explicit_simd]] {
            esimd::slm_init<kSlmBytes>();
            const int mt = int(item.get_group(0)) * kWG + int(item.get_local_id(0));
            const int lid = int(item.get_local_id(0));
            const int mb = mt * kMTile;
            esimd::simd<float, kNTile * kMTile> accum0(0.0f);
            esimd::simd<float, kNTile * kMTile> accum1(0.0f);

            for (int kb = 0; kb < kK; kb += kKBlock) {
#pragma unroll
                for (int token = 0; token < kN; ++token) {
                    const auto slice = esimd::block_load<bf16, kSlice>(
                        activation + size_t(token) * kK + kb + lid * kSlice);
                    const uint32_t slm_offset = uint32_t(
                        (size_t(token) * kKBlock + lid * kSlice) * sizeof(bf16));
                    esimd::slm_block_store<bf16, kSlice>(slm_offset, slice);
                }
                esimd::barrier();

#pragma unroll
                for (int sub = 0; sub < kKBlock / kKTile; ++sub) {
                    const int kt = kb + sub * kKTile;
                    const size_t packed_offset =
                        (size_t(mt) * (kK / kKTile) + kt / kKTile) *
                        kKTile * kMTile;
                    const auto weights =
                        esimd::block_load<bf16, kKTile * kMTile>(packed_weight + packed_offset);

                    esimd::simd<bf16, kNTile * kKTile> act0;
                    esimd::simd<bf16, kNTile * kKTile> act1;
#pragma unroll
                    for (int token = 0; token < kNTile; ++token) {
                        act0.template select<kKTile, 1>(token * kKTile) =
                            esimd::slm_block_load<bf16, kKTile>(uint32_t(
                                (size_t(token) * kKBlock + sub * kKTile) * sizeof(bf16)));
                        act1.template select<kKTile, 1>(token * kKTile) =
                            esimd::slm_block_load<bf16, kKTile>(uint32_t(
                                (size_t(token + kNTile) * kKBlock + sub * kKTile) * sizeof(bf16)));
                    }

                    accum0 = xmx::dpas<8, kNTile, float, float, bf16, bf16>(
                        accum0, weights, act0);
                    accum1 = xmx::dpas<8, kNTile, float, float, bf16, bf16>(
                        accum1, weights, act1);
                }
                esimd::barrier();
            }

#pragma unroll
            for (int token = 0; token < kNTile; ++token) {
                esimd::block_store<float, kMTile>(
                    output + size_t(token) * kM + mb,
                    accum0.template select<kMTile, 1>(token * kMTile).read());
                esimd::block_store<float, kMTile>(
                    output + size_t(token + kNTile) * kM + mb,
                    accum1.template select<kMTile, 1>(token * kMTile).read());
            }
        });
    });
}

sycl::event launch_dpas_multirow(
        sycl::queue & queue,
        const bf16 * packed_weight,
        const bf16 * activation,
        float * output) {
    static_assert((kM / kMTile) % kRowTiles == 0);
    constexpr int kAccum = kNTile * kMTile;
    return queue.submit([&](sycl::handler & cgh) {
        cgh.parallel_for<MuseBf16DpasMultiRowKernel>(
                sycl::range<1>(kM / (kMTile * kRowTiles)),
                [=](sycl::id<1> item) [[intel::sycl_explicit_simd]] {
            const int mt0 = int(item[0]) * kRowTiles;
            esimd::simd<float, kAccum * kRowTiles> accum0(0.0f);
            esimd::simd<float, kAccum * kRowTiles> accum1(0.0f);

            for (int kb = 0; kb < kK; kb += kKTile) {
                esimd::simd<bf16, kNTile * kKTile> act0;
                esimd::simd<bf16, kNTile * kKTile> act1;
#pragma unroll
                for (int token = 0; token < kNTile; ++token) {
                    act0.template select<kKTile, 1>(token * kKTile) =
                        esimd::block_load<bf16, kKTile>(activation + size_t(token) * kK + kb);
                    act1.template select<kKTile, 1>(token * kKTile) =
                        esimd::block_load<bf16, kKTile>(activation + size_t(token + kNTile) * kK + kb);
                }

#pragma unroll
                for (int rt = 0; rt < kRowTiles; ++rt) {
                    const int mt = mt0 + rt;
                    const size_t packed_offset =
                        (size_t(mt) * (kK / kKTile) + kb / kKTile) * kKTile * kMTile;
                    const auto weights =
                        esimd::block_load<bf16, kKTile * kMTile>(packed_weight + packed_offset);
                    auto a0 = accum0.template select<kAccum, 1>(rt * kAccum).read();
                    auto a1 = accum1.template select<kAccum, 1>(rt * kAccum).read();
                    accum0.template select<kAccum, 1>(rt * kAccum) =
                        xmx::dpas<8, kNTile, float, float, bf16, bf16>(a0, weights, act0);
                    accum1.template select<kAccum, 1>(rt * kAccum) =
                        xmx::dpas<8, kNTile, float, float, bf16, bf16>(a1, weights, act1);
                }
            }

#pragma unroll
            for (int rt = 0; rt < kRowTiles; ++rt) {
                const int mb = (mt0 + rt) * kMTile;
#pragma unroll
                for (int token = 0; token < kNTile; ++token) {
                    esimd::block_store<float, kMTile>(
                        output + size_t(token) * kM + mb,
                        accum0.template select<kMTile, 1>(rt * kAccum + token * kMTile).read());
                    esimd::block_store<float, kMTile>(
                        output + size_t(token + kNTile) * kM + mb,
                        accum1.template select<kMTile, 1>(rt * kAccum + token * kMTile).read());
                }
            }
        });
    });
}

template <typename Submit>
double batch_time_ms(sycl::queue & queue, int iterations, const Submit & submit) {
    queue.wait_and_throw();
    const auto begin = std::chrono::steady_clock::now();
    for (int i = 0; i < iterations; ++i) {
        submit();
    }
    queue.wait_and_throw();
    const auto end = std::chrono::steady_clock::now();
    return std::chrono::duration<double, std::milli>(end - begin).count() / iterations;
}

uint32_t bits(float value) {
    uint32_t result;
    std::memcpy(&result, &value, sizeof(result));
    return result;
}

} // namespace

int main(int argc, char ** argv) {
    int warmups = 8;
    int iterations = 40;
    if (argc > 1) {
        iterations = std::stoi(argv[1]);
    }

    sycl::queue queue(sycl::gpu_selector_v,
        sycl::property_list{sycl::property::queue::in_order{}});
    std::cout << "device=" << queue.get_device().get_info<sycl::info::device::name>()
              << " shape=" << kM << "x" << kN << "x" << kK
              << " iterations=" << iterations << '\n';

    uint32_t rng = 0x4d555345u;
    std::vector<bf16> host_weight(size_t(kM) * kK);
    std::vector<bf16> host_activation(size_t(kN) * kK);
    for (auto & value : host_weight) {
        value = bf16(signed_unit(rng) * 0.03125f);
    }
    for (auto & value : host_activation) {
        value = bf16(signed_unit(rng) * 0.125f);
    }
    std::vector<float> host_activation_f32(host_activation.size());
    std::transform(host_activation.begin(), host_activation.end(), host_activation_f32.begin(),
                   [](bf16 value) { return float(value); });
    const auto host_packed = pack_weight_vnni(host_weight);

    auto * weight = sycl::malloc_device<bf16>(host_weight.size(), queue);
    auto * packed = sycl::malloc_device<bf16>(host_packed.size(), queue);
    auto * activation = sycl::malloc_device<bf16>(host_activation.size(), queue);
    auto * activation_f32 = sycl::malloc_device<float>(host_activation_f32.size(), queue);
    auto * out_dnnl = sycl::malloc_device<float>(size_t(kM) * kN, queue);
    auto * out_dnnl_f32src = sycl::malloc_device<float>(size_t(kM) * kN, queue);
    auto * out_dpas = sycl::malloc_device<float>(size_t(kM) * kN, queue);
    auto * out_dpas_slm = sycl::malloc_device<float>(size_t(kM) * kN, queue);
    auto * out_dpas_multi = sycl::malloc_device<float>(size_t(kM) * kN, queue);
    if (!weight || !packed || !activation || !activation_f32 || !out_dnnl || !out_dnnl_f32src ||
        !out_dpas || !out_dpas_slm || !out_dpas_multi) {
        throw std::runtime_error("USM allocation failed");
    }
    queue.copy(host_weight.data(), weight, host_weight.size());
    queue.copy(host_packed.data(), packed, host_packed.size());
    queue.copy(host_activation.data(), activation, host_activation.size());
    queue.copy(host_activation_f32.data(), activation_f32, host_activation_f32.size());
    queue.wait_and_throw();

    auto engine = dnnl::sycl_interop::make_engine(
        queue.get_device(), queue.get_context());
    auto stream = dnnl::sycl_interop::make_stream(engine, queue);
    const auto weight_md = dnnl::memory::desc(
        {1, kM, kK}, dnnl::memory::data_type::bf16, {kM * kK, kK, 1});
    const auto activation_md = dnnl::memory::desc(
        {1, kK, kN}, dnnl::memory::data_type::bf16, {kK * kN, 1, kK});
    const auto output_md = dnnl::memory::desc(
        {1, kM, kN}, dnnl::memory::data_type::f32, {kM * kN, 1, kM});
    dnnl::primitive_attr attr;
    attr.set_scratchpad_mode(dnnl::scratchpad_mode::user);
    auto pd = dnnl::matmul::primitive_desc(
        engine, weight_md, activation_md, output_md, attr);
    auto primitive = dnnl::matmul(pd);
    auto * scratch = sycl::malloc_device<uint8_t>(pd.scratchpad_desc().get_size(), queue);
    if (!scratch && pd.scratchpad_desc().get_size() != 0) {
        throw std::runtime_error("scratchpad allocation failed");
    }
    std::unordered_map<int, dnnl::memory> args = {
        {DNNL_ARG_SRC, dnnl::memory(weight_md, engine, weight)},
        {DNNL_ARG_WEIGHTS, dnnl::memory(activation_md, engine, activation)},
        {DNNL_ARG_DST, dnnl::memory(output_md, engine, out_dnnl)},
        {DNNL_ARG_SCRATCHPAD,
            dnnl::memory(pd.scratchpad_desc(), engine, scratch)},
    };

    const auto activation_f32_md = dnnl::memory::desc(
        {1, kK, kN}, dnnl::memory::data_type::f32, {kK * kN, 1, kK});
    auto f32src_pd = dnnl::matmul::primitive_desc(
        engine, weight_md, activation_f32_md, output_md, attr);
    auto f32src_primitive = dnnl::matmul(f32src_pd);
    auto * f32src_scratch = sycl::malloc_device<uint8_t>(
        f32src_pd.scratchpad_desc().get_size(), queue);
    if (!f32src_scratch && f32src_pd.scratchpad_desc().get_size() != 0) {
        throw std::runtime_error("f32-source scratchpad allocation failed");
    }
    std::unordered_map<int, dnnl::memory> f32src_args = {
        {DNNL_ARG_SRC, dnnl::memory(weight_md, engine, weight)},
        {DNNL_ARG_WEIGHTS, dnnl::memory(activation_f32_md, engine, activation_f32)},
        {DNNL_ARG_DST, dnnl::memory(output_md, engine, out_dnnl_f32src)},
        {DNNL_ARG_SCRATCHPAD,
            dnnl::memory(f32src_pd.scratchpad_desc(), engine, f32src_scratch)},
    };

    auto submit_dnnl = [&] { primitive.execute(stream, args); };
    auto submit_dnnl_f32src = [&] { f32src_primitive.execute(stream, f32src_args); };
    auto submit_dpas = [&] { launch_dpas(queue, packed, activation, out_dpas); };
    auto submit_dpas_slm = [&] { launch_dpas_slm(queue, packed, activation, out_dpas_slm); };
    auto submit_dpas_multi = [&] { launch_dpas_multirow(queue, packed, activation, out_dpas_multi); };
    for (int i = 0; i < warmups; ++i) {
        submit_dnnl();
        submit_dnnl_f32src();
        submit_dpas();
        submit_dpas_slm();
        submit_dpas_multi();
    }
    queue.wait_and_throw();

    submit_dnnl();
    submit_dnnl_f32src();
    submit_dpas();
    submit_dpas_slm();
    submit_dpas_multi();
    queue.wait_and_throw();
    std::vector<float> host_dnnl(size_t(kM) * kN);
    std::vector<float> host_dnnl_f32src(size_t(kM) * kN);
    std::vector<float> host_dpas(size_t(kM) * kN);
    std::vector<float> host_dpas_slm(size_t(kM) * kN);
    std::vector<float> host_dpas_multi(size_t(kM) * kN);
    queue.copy(out_dnnl, host_dnnl.data(), host_dnnl.size());
    queue.copy(out_dnnl_f32src, host_dnnl_f32src.data(), host_dnnl_f32src.size());
    queue.copy(out_dpas, host_dpas.data(), host_dpas.size());
    queue.copy(out_dpas_slm, host_dpas_slm.data(), host_dpas_slm.size());
    queue.copy(out_dpas_multi, host_dpas_multi.data(), host_dpas_multi.size());
    queue.wait_and_throw();

    size_t mismatches = 0;
    size_t f32src_mismatches = 0;
    size_t slm_mismatches = 0;
    size_t multi_mismatches = 0;
    float max_abs_error = 0.0f;
    size_t first_mismatch = host_dnnl.size();
    for (size_t i = 0; i < host_dnnl.size(); ++i) {
        if (bits(host_dnnl[i]) != bits(host_dpas[i])) {
            ++mismatches;
            first_mismatch = std::min(first_mismatch, i);
            max_abs_error = std::max(max_abs_error,
                std::abs(host_dnnl[i] - host_dpas[i]));
        }
        slm_mismatches += bits(host_dnnl[i]) != bits(host_dpas_slm[i]);
        multi_mismatches += bits(host_dnnl[i]) != bits(host_dpas_multi[i]);
        f32src_mismatches += bits(host_dnnl[i]) != bits(host_dnnl_f32src[i]);
    }

    const double dnnl_ms = batch_time_ms(queue, iterations, submit_dnnl);
    const double dnnl_f32src_ms = batch_time_ms(queue, iterations, submit_dnnl_f32src);
    const double dpas_ms = batch_time_ms(queue, iterations, submit_dpas);
    const double dpas_slm_ms = batch_time_ms(queue, iterations, submit_dpas_slm);
    const double dpas_multi_ms = batch_time_ms(queue, iterations, submit_dpas_multi);
    const double ratio = dnnl_ms > 0.0 ? dpas_ms / dnnl_ms : 0.0;
    std::cout << std::fixed << std::setprecision(6)
              << "dnnl_ms=" << dnnl_ms
              << " dnnl_f32src_ms=" << dnnl_f32src_ms
              << " dnnl_f32src_over_dnnl=" << (dnnl_f32src_ms / dnnl_ms)
              << " dpas_ms=" << dpas_ms
              << " dpas_over_dnnl=" << ratio
              << " dpas_slm_ms=" << dpas_slm_ms
              << " dpas_slm_over_dnnl=" << (dpas_slm_ms / dnnl_ms)
              << " dpas_multi_ms=" << dpas_multi_ms
              << " dpas_multi_over_dnnl=" << (dpas_multi_ms / dnnl_ms)
              << " mismatches=" << mismatches
              << " f32src_mismatches=" << f32src_mismatches
              << " slm_mismatches=" << slm_mismatches
              << " multi_mismatches=" << multi_mismatches
              << " max_abs_error=" << max_abs_error << '\n';
    if (first_mismatch != host_dnnl.size()) {
        std::cout << "first_mismatch=" << first_mismatch
                  << " dnnl=0x" << std::hex << bits(host_dnnl[first_mismatch])
                  << " dpas=0x" << bits(host_dpas[first_mismatch]) << std::dec
                  << " dnnl_value=" << host_dnnl[first_mismatch]
                  << " dpas_value=" << host_dpas[first_mismatch] << '\n';
    }

    sycl::free(f32src_scratch, queue);
    sycl::free(scratch, queue);
    sycl::free(out_dpas_slm, queue);
    sycl::free(out_dpas_multi, queue);
    sycl::free(out_dpas, queue);
    sycl::free(out_dnnl, queue);
    sycl::free(out_dnnl_f32src, queue);
    sycl::free(activation_f32, queue);
    sycl::free(activation, queue);
    sycl::free(packed, queue);
    sycl::free(weight, queue);

    const bool exact = mismatches == 0;
    const bool fast_enough = dpas_ms <= 0.8 * dnnl_ms;
    std::cout << "exact_gate=" << (exact ? "PASS" : "FAIL")
              << " speed_gate=" << (fast_enough ? "PASS" : "FAIL") << '\n';
    return exact && fast_enough ? 0 : 2;
}
