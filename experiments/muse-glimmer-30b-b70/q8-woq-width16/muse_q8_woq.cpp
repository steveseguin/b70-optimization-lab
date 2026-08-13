// Isolated oneDNN 3.11 SYCL weight-only quantized matmul microbenchmark.
//
// This intentionally has no llama.cpp dependency.  It models a ggml Q8_0
// matrix as output-major rows of {f16 scale, 32 x s8}, pre-packs the weights
// once for oneDNN, and measures only fixed Muse verifier shapes.

#include <oneapi/dnnl/dnnl.hpp>
#include <oneapi/dnnl/dnnl_debug.h>
#include <oneapi/dnnl/dnnl_sycl.hpp>
#include <sycl/sycl.hpp>

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <functional>
#include <iomanip>
#include <iostream>
#include <limits>
#include <numeric>
#include <sstream>
#include <stdexcept>
#include <string>
#include <thread>
#include <unordered_map>
#include <utility>
#include <vector>

namespace {

using bf16 = sycl::ext::oneapi::bfloat16;
using f16 = sycl::half;
using clock_type = std::chrono::steady_clock;

constexpr int64_t kTokens = 16;
constexpr int64_t kInput = 6656;
constexpr int64_t kGroup = 32;
constexpr int64_t kOutputs[] = {4992, 6656};

struct q8_0_block {
    f16 d;
    int8_t qs[kGroup];
};
static_assert(sizeof(q8_0_block) == 34, "ggml Q8_0 block must be 34 bytes");

struct options {
    bool run = false;
    int warmup = 4;
    int repeats = 11;
    int inner = 8;
    std::string json_path;
};

[[noreturn]] void fail(const std::string &message) {
    throw std::runtime_error(message);
}

int parse_positive(const char *value, const char *name) {
    char *end = nullptr;
    const long parsed = std::strtol(value, &end, 10);
    if (!value[0] || (end && *end) || parsed <= 0 || parsed > 100000) {
        fail(std::string("invalid ") + name + ": " + value);
    }
    return static_cast<int>(parsed);
}

options parse_options(int argc, char **argv) {
    options opts;
    for (int i = 1; i < argc; ++i) {
        const std::string arg = argv[i];
        if (arg == "--run") {
            opts.run = true;
        } else if (arg == "--warmup" && i + 1 < argc) {
            opts.warmup = parse_positive(argv[++i], "warmup");
        } else if (arg == "--repeats" && i + 1 < argc) {
            opts.repeats = parse_positive(argv[++i], "repeats");
        } else if (arg == "--inner" && i + 1 < argc) {
            opts.inner = parse_positive(argv[++i], "inner");
        } else if (arg == "--json" && i + 1 < argc) {
            opts.json_path = argv[++i];
        } else if (arg == "--help" || arg == "-h") {
            std::cout
                    << "usage: muse_q8_woq --run [--warmup N] [--repeats N]"
                       " [--inner N] [--json PATH]\n\n"
                    << "Safety: --run is mandatory and ONEAPI_DEVICE_SELECTOR must be"
                       " exactly level_zero:0.\n";
            std::exit(0);
        } else {
            fail("unknown or incomplete argument: " + arg);
        }
    }
    return opts;
}

uint64_t splitmix64(uint64_t x) {
    x += 0x9e3779b97f4a7c15ULL;
    x = (x ^ (x >> 30)) * 0xbf58476d1ce4e5b9ULL;
    x = (x ^ (x >> 27)) * 0x94d049bb133111ebULL;
    return x ^ (x >> 31);
}

float deterministic_float(uint64_t index, float lo, float hi) {
    const uint64_t bits = splitmix64(index);
    const float unit = static_cast<float>((bits >> 40) * (1.0 / 16777216.0));
    return lo + (hi - lo) * unit;
}

struct host_problem {
    int64_t output;
    std::vector<q8_0_block> q8;
    std::vector<int8_t> s8_k_o;
    std::vector<f16> scales_group_o;
    std::vector<float> src_f32;

    explicit host_problem(int64_t output_) : output(output_) {
        const int64_t groups = kInput / kGroup;
        q8.resize(static_cast<size_t>(output * groups));
        s8_k_o.resize(static_cast<size_t>(kInput * output));
        scales_group_o.resize(static_cast<size_t>(groups * output));
        src_f32.resize(static_cast<size_t>(kTokens * kInput));

        for (int64_t o = 0; o < output; ++o) {
            for (int64_t g = 0; g < groups; ++g) {
                q8_0_block &block = q8[static_cast<size_t>(o * groups + g)];
                // A range representative of Q8 block scales, rounded exactly as
                // the ggml f16 scale stored in Q8_0.
                block.d = f16(deterministic_float(
                        0x100000000ULL + static_cast<uint64_t>(o * groups + g),
                        0.0015f, 0.018f));
                scales_group_o[static_cast<size_t>(g * output + o)] = block.d;
                for (int64_t i = 0; i < kGroup; ++i) {
                    const uint64_t r = splitmix64(
                            0x200000000ULL
                            + static_cast<uint64_t>((o * groups + g) * kGroup + i));
                    const int8_t q = static_cast<int8_t>(static_cast<int>(r % 255) - 127);
                    block.qs[i] = q;
                    s8_k_o[static_cast<size_t>((g * kGroup + i) * output + o)] = q;
                }
            }
        }

        for (size_t i = 0; i < src_f32.size(); ++i) {
            src_f32[i] = deterministic_float(0x300000000ULL + i, -0.75f, 0.75f);
        }
    }
};

class usm_device_buffer {
public:
    usm_device_buffer() = default;

    usm_device_buffer(sycl::queue &queue, size_t bytes)
        : context_(queue.get_context()), bytes_(std::max<size_t>(bytes, 1)) {
        ptr_ = sycl::malloc_device(bytes_, queue);
        if (!ptr_) fail("sycl::malloc_device failed for " + std::to_string(bytes_) + " bytes");
    }

    usm_device_buffer(const usm_device_buffer &) = delete;
    usm_device_buffer &operator=(const usm_device_buffer &) = delete;

    usm_device_buffer(usm_device_buffer &&other) noexcept
        : ptr_(std::exchange(other.ptr_, nullptr)), context_(other.context_),
          bytes_(std::exchange(other.bytes_, 0)) {}

    usm_device_buffer &operator=(usm_device_buffer &&other) noexcept {
        if (this != &other) {
            reset();
            ptr_ = std::exchange(other.ptr_, nullptr);
            context_ = other.context_;
            bytes_ = std::exchange(other.bytes_, 0);
        }
        return *this;
    }

    ~usm_device_buffer() { reset(); }

    void *get() const { return ptr_; }
    size_t bytes() const { return bytes_; }

    template <typename T> T *as() const { return static_cast<T *>(ptr_); }

private:
    void reset() noexcept {
        if (ptr_) {
            sycl::free(ptr_, context_);
            ptr_ = nullptr;
        }
    }

    void *ptr_ = nullptr;
    sycl::context context_;
    size_t bytes_ = 0;
};

dnnl::memory usm_memory(const dnnl::memory::desc &md, const dnnl::engine &engine,
        usm_device_buffer &buffer) {
    if (md.get_size() > buffer.bytes()) fail("USM allocation is smaller than memory descriptor");
    return dnnl::sycl_interop::make_memory(
            md, engine, dnnl::sycl_interop::memory_kind::usm, buffer.get());
}

struct stats {
    double median_us = 0;
    double p10_us = 0;
    double p90_us = 0;
    double min_us = 0;
    double mean_us = 0;
};

double percentile(const std::vector<double> &sorted, double p) {
    if (sorted.empty()) return 0;
    const double pos = p * static_cast<double>(sorted.size() - 1);
    const size_t lo = static_cast<size_t>(std::floor(pos));
    const size_t hi = static_cast<size_t>(std::ceil(pos));
    const double frac = pos - static_cast<double>(lo);
    return sorted[lo] * (1.0 - frac) + sorted[hi] * frac;
}

stats summarize(std::vector<double> samples) {
    stats result;
    result.mean_us = std::accumulate(samples.begin(), samples.end(), 0.0)
            / static_cast<double>(samples.size());
    std::sort(samples.begin(), samples.end());
    result.min_us = samples.front();
    result.p10_us = percentile(samples, 0.10);
    result.median_us = percentile(samples, 0.50);
    result.p90_us = percentile(samples, 0.90);
    return result;
}

struct error_metrics {
    double max_abs = 0;
    double max_rel = 0;
    double rmse = 0;
    double nrmse = 0;
    double cosine = 0;
};

error_metrics compare_vectors(const std::vector<float> &actual,
        const std::vector<float> &reference) {
    if (actual.size() != reference.size()) fail("comparison size mismatch");
    long double sq_error = 0;
    long double sq_ref = 0;
    long double sq_actual = 0;
    long double dot = 0;
    error_metrics result;
    for (size_t i = 0; i < actual.size(); ++i) {
        const double a = actual[i];
        const double r = reference[i];
        const double abs_error = std::abs(a - r);
        const double rel_error = abs_error / std::max(std::abs(r), 1e-6);
        result.max_abs = std::max(result.max_abs, abs_error);
        result.max_rel = std::max(result.max_rel, rel_error);
        sq_error += static_cast<long double>(a - r) * (a - r);
        sq_ref += static_cast<long double>(r) * r;
        sq_actual += static_cast<long double>(a) * a;
        dot += static_cast<long double>(a) * r;
    }
    result.rmse = std::sqrt(static_cast<double>(sq_error / actual.size()));
    const double ref_rms = std::sqrt(static_cast<double>(sq_ref / actual.size()));
    result.nrmse = result.rmse / std::max(ref_rms, 1e-30);
    result.cosine = static_cast<double>(dot / std::sqrt(sq_ref * sq_actual));
    return result;
}

std::vector<float> cpu_reference(const host_problem &problem) {
    const int64_t groups = kInput / kGroup;
    const int64_t count = kTokens * problem.output;
    std::vector<float> output(static_cast<size_t>(count));
    unsigned threads = std::thread::hardware_concurrency();
    threads = std::max(1u, std::min(threads, 32u));
    threads = std::min<unsigned>(threads, static_cast<unsigned>(count));
    std::vector<std::thread> workers;
    workers.reserve(threads);
    for (unsigned tid = 0; tid < threads; ++tid) {
        const int64_t begin = count * tid / threads;
        const int64_t end = count * (tid + 1) / threads;
        workers.emplace_back([&, begin, end] {
            for (int64_t linear = begin; linear < end; ++linear) {
                const int64_t token = linear / problem.output;
                const int64_t o = linear % problem.output;
                const float *src = problem.src_f32.data() + token * kInput;
                double sum = 0;
                for (int64_t g = 0; g < groups; ++g) {
                    const q8_0_block &block =
                            problem.q8[static_cast<size_t>(o * groups + g)];
                    const double scale = static_cast<float>(block.d);
                    for (int64_t i = 0; i < kGroup; ++i) {
                        sum += scale * static_cast<double>(block.qs[i])
                                * static_cast<double>(src[g * kGroup + i]);
                    }
                }
                output[static_cast<size_t>(linear)] = static_cast<float>(sum);
            }
        });
    }
    for (auto &worker : workers) worker.join();
    return output;
}

struct arm_result {
    std::string name;
    stats timing;
    double gflops = 0;
    double modeled_bytes = 0;
    double modeled_gbps = 0;
    error_metrics vs_q8_f32;
    error_metrics vs_baseline;
};

struct shape_result {
    int64_t output = 0;
    double woq_pack_ms_f32 = 0;
    double woq_pack_ms_bf16 = 0;
    size_t woq_packed_bytes_f32 = 0;
    size_t woq_packed_bytes_bf16 = 0;
    std::string woq_f32_impl;
    std::string woq_bf16_impl;
    std::string bf16_impl;
    bool woq_scale_exec_md_query_available = false;
    std::vector<arm_result> arms;
};

struct primitive_bundle {
    dnnl::matmul primitive;
    dnnl::memory::desc src_md;
    dnnl::memory::desc weights_md;
    dnnl::memory::desc dst_md;
    dnnl::memory::desc scales_md;
    dnnl::memory::desc queried_scales_md;
    dnnl::memory::desc scratch_md;
    std::string impl_info;
};

primitive_bundle make_woq_bundle(const dnnl::engine &engine,
        dnnl::memory::data_type src_type, int64_t output) {
    using dt = dnnl::memory::data_type;
    using tag = dnnl::memory::format_tag;
    const dnnl::memory::desc src_md({kTokens, kInput}, src_type, tag::ab);
    const dnnl::memory::desc weights_any_md({kInput, output}, dt::s8, tag::any);
    const dnnl::memory::desc dst_md({kTokens, output}, dt::f32, tag::ab);
    dnnl::primitive_attr attr;
    attr.set_scratchpad_mode(dnnl::scratchpad_mode::user);
    attr.set_scales(DNNL_ARG_WEIGHTS, (1 << 0) | (1 << 1), {kGroup, 1}, dt::f16);
    attr.set_fpmath_mode(dnnl::fpmath_mode::bf16, true);
    const dnnl::matmul::primitive_desc pd(engine, src_md, weights_any_md, dst_md, attr);
    // oneDNN 3.11's public exec_arg_md query returns a zero descriptor for
    // attribute scales. Reconstruct the execution contract in the same way as
    // quant_entry_t::get_md and benchdnn: apply the mask and {32,1} groups to
    // logical weights [K,O], producing contiguous scales [K/32,O]. Retain the
    // public query result too, so a nonzero future result is cross-checked.
    const dnnl::memory::desc scales_md(
            {kInput / kGroup, output}, dt::f16, tag::ab);
    return {dnnl::matmul(pd), src_md, pd.weights_desc(), pd.dst_desc(),
            scales_md,
            pd.query_md(dnnl::query::exec_arg_md,
                    DNNL_ARG_ATTR_SCALES | DNNL_ARG_WEIGHTS),
            pd.scratchpad_desc(), pd.impl_info_str()};
}

primitive_bundle make_bf16_bundle(const dnnl::engine &engine, int64_t output) {
    using dt = dnnl::memory::data_type;
    // Match DnnlGemmWrapper::row_gemm rather than giving the baseline WOQ's
    // transposed operand orientation: model weights are oneDNN SRC [O,K],
    // activations are WEIGHTS [K,T] over token-major physical [T,K], and the
    // output is [O,T] over token-major physical [T,O].
    const dnnl::memory::desc src_md({output, kInput}, dt::bf16, {kInput, 1});
    const dnnl::memory::desc weights_md({kInput, kTokens}, dt::bf16, {1, kInput});
    const dnnl::memory::desc dst_md({output, kTokens}, dt::f32, {1, output});
    dnnl::primitive_attr attr;
    attr.set_scratchpad_mode(dnnl::scratchpad_mode::user);
    const dnnl::matmul::primitive_desc pd(engine, src_md, weights_md, dst_md, attr);
    return {dnnl::matmul(pd), src_md, pd.weights_desc(), pd.dst_desc(), {}, {},
            pd.scratchpad_desc(), pd.impl_info_str()};
}

shape_result benchmark_shape(const options &opts, sycl::queue &queue,
        const dnnl::engine &engine, const dnnl::stream &stream, int64_t output) {
    using dt = dnnl::memory::data_type;
    using tag = dnnl::memory::format_tag;

    std::cerr << "preparing O=" << output << " K=" << kInput
              << " tokens=" << kTokens << "\n";
    host_problem host(output);
    const int64_t groups = kInput / kGroup;
    const size_t weight_elements = static_cast<size_t>(output * kInput);
    const size_t src_elements = static_cast<size_t>(kTokens * kInput);
    const size_t dst_elements = static_cast<size_t>(kTokens * output);

    usm_device_buffer q8_device(queue, host.q8.size() * sizeof(q8_0_block));
    usm_device_buffer s8_plain_device(queue, host.s8_k_o.size() * sizeof(int8_t));
    usm_device_buffer scales_device(queue, host.scales_group_o.size() * sizeof(f16));
    usm_device_buffer src_f32_device(queue, src_elements * sizeof(float));
    usm_device_buffer src_bf16_device(queue, src_elements * sizeof(bf16));
    usm_device_buffer weights_bf16_device(queue, weight_elements * sizeof(bf16));
    usm_device_buffer dst_woq_f32_device(queue, dst_elements * sizeof(float));
    usm_device_buffer dst_woq_bf16_device(queue, dst_elements * sizeof(float));
    usm_device_buffer dst_bf16_device(queue, dst_elements * sizeof(float));

    queue.memcpy(q8_device.get(), host.q8.data(), host.q8.size() * sizeof(q8_0_block));
    queue.memcpy(s8_plain_device.get(), host.s8_k_o.data(), host.s8_k_o.size());
    queue.memcpy(scales_device.get(), host.scales_group_o.data(),
            host.scales_group_o.size() * sizeof(f16));
    queue.memcpy(src_f32_device.get(), host.src_f32.data(),
            host.src_f32.size() * sizeof(float));
    queue.wait_and_throw();

    const primitive_bundle woq_f32 = make_woq_bundle(engine, dt::f32, output);
    const primitive_bundle woq_bf16 = make_woq_bundle(engine, dt::bf16, output);
    const primitive_bundle bf16_matmul = make_bf16_bundle(engine, output);
    std::cerr << "O=" << output << " implementations: woq_f32="
              << woq_f32.impl_info << " woq_bf16=" << woq_bf16.impl_info
              << " bf16=" << bf16_matmul.impl_info << '\n';
    const auto reject_reference = [](const std::string &implementation,
                                          const char *label) {
        if (implementation.find("ref") != std::string::npos) {
            fail(std::string(label) + " selected reference implementation: "
                    + implementation);
        }
    };
    reject_reference(woq_f32.impl_info, "F32-source WOQ");
    reject_reference(woq_bf16.impl_info, "BF16-source WOQ");
    reject_reference(bf16_matmul.impl_info, "BF16 matmul");

    usm_device_buffer packed_f32_device(queue, woq_f32.weights_md.get_size());
    usm_device_buffer packed_bf16_device(queue, woq_bf16.weights_md.get_size());
    usm_device_buffer scratch_woq_f32_device(queue, woq_f32.scratch_md.get_size());
    usm_device_buffer scratch_woq_bf16_device(queue, woq_bf16.scratch_md.get_size());
    usm_device_buffer scratch_bf16_device(queue, bf16_matmul.scratch_md.get_size());

    const dnnl::memory::desc s8_plain_md({kInput, output}, dt::s8, tag::ab);
    // oneDNN's internal scale descriptor is logical [group_k,O], contiguous.
    // The official tutorial spells the same physical offsets as logical
    // [O,group_k] with strides [1,O]. Use the internal form here so validation
    // is exact rather than merely byte-layout equivalent.
    const dnnl::memory::desc expected_scale_md({groups, output}, dt::f16, tag::ab);
    const auto check_scale_md = [&](const primitive_bundle &bundle, const char *label) {
        if (bundle.scales_md.get_dims() != expected_scale_md.get_dims()
                || bundle.scales_md.get_strides() != expected_scale_md.get_strides()
                || bundle.scales_md.get_data_type() != dt::f16
                || bundle.scales_md.get_size() != expected_scale_md.get_size()
                || bundle.scales_md.get_size()
                        != host.scales_group_o.size() * sizeof(f16)) {
            std::ostringstream message;
            message << label << " weight-scale descriptor differs from"
                       " contiguous [group_k,O] contract";
            fail(message.str());
        }
        if (!bundle.queried_scales_md.is_zero()
                && (bundle.queried_scales_md.get_dims() != bundle.scales_md.get_dims()
                        || bundle.queried_scales_md.get_strides()
                                != bundle.scales_md.get_strides()
                        || bundle.queried_scales_md.get_data_type() != dt::f16
                        || bundle.queried_scales_md.get_size()
                                != bundle.scales_md.get_size())) {
            fail(std::string(label)
                    + " queried weight-scale execution descriptor differs from"
                      " supplied scale memory");
        }
    };
    check_scale_md(woq_f32, "F32-source WOQ");
    check_scale_md(woq_bf16, "BF16-source WOQ");
    if (woq_f32.queried_scales_md.is_zero()
            != woq_bf16.queried_scales_md.is_zero()) {
        fail("WOQ source types disagree on scale execution descriptor availability");
    }

    dnnl::memory s8_plain_mem = usm_memory(s8_plain_md, engine, s8_plain_device);
    dnnl::memory packed_f32_mem = usm_memory(woq_f32.weights_md, engine, packed_f32_device);
    dnnl::memory packed_bf16_mem = usm_memory(woq_bf16.weights_md, engine, packed_bf16_device);
    dnnl::memory scales_mem = usm_memory(woq_f32.scales_md, engine, scales_device);
    dnnl::memory src_f32_mem = usm_memory(woq_f32.src_md, engine, src_f32_device);
    dnnl::memory src_bf16_woq_mem = usm_memory(woq_bf16.src_md, engine, src_bf16_device);
    dnnl::memory src_bf16_mem =
            usm_memory(bf16_matmul.weights_md, engine, src_bf16_device);
    dnnl::memory weights_bf16_mem =
            usm_memory(bf16_matmul.src_md, engine, weights_bf16_device);
    dnnl::memory dst_woq_f32_mem =
            usm_memory(woq_f32.dst_md, engine, dst_woq_f32_device);
    dnnl::memory dst_woq_bf16_mem =
            usm_memory(woq_bf16.dst_md, engine, dst_woq_bf16_device);
    dnnl::memory dst_bf16_mem =
            usm_memory(bf16_matmul.dst_md, engine, dst_bf16_device);
    dnnl::memory scratch_woq_f32_mem =
            usm_memory(woq_f32.scratch_md, engine, scratch_woq_f32_device);
    dnnl::memory scratch_woq_bf16_mem =
            usm_memory(woq_bf16.scratch_md, engine, scratch_woq_bf16_device);
    dnnl::memory scratch_bf16_mem =
            usm_memory(bf16_matmul.scratch_md, engine, scratch_bf16_device);

    auto pack_once = [&](dnnl::memory &destination) {
        const auto start = clock_type::now();
        dnnl::reorder(s8_plain_mem, destination).execute(
                stream, s8_plain_mem, destination);
        queue.wait_and_throw();
        return std::chrono::duration<double, std::milli>(clock_type::now() - start).count();
    };

    shape_result result;
    result.output = output;
    result.woq_pack_ms_f32 = pack_once(packed_f32_mem);
    result.woq_pack_ms_bf16 = pack_once(packed_bf16_mem);
    result.woq_packed_bytes_f32 = woq_f32.weights_md.get_size();
    result.woq_packed_bytes_bf16 = woq_bf16.weights_md.get_size();
    result.woq_f32_impl = woq_f32.impl_info;
    result.woq_bf16_impl = woq_bf16.impl_info;
    result.bf16_impl = bf16_matmul.impl_info;
    result.woq_scale_exec_md_query_available = !woq_f32.queried_scales_md.is_zero();

    const std::unordered_map<int, dnnl::memory> woq_f32_args = {
            {DNNL_ARG_SRC, src_f32_mem},
            {DNNL_ARG_WEIGHTS, packed_f32_mem},
            {DNNL_ARG_DST, dst_woq_f32_mem},
            {DNNL_ARG_ATTR_SCALES | DNNL_ARG_WEIGHTS, scales_mem},
            {DNNL_ARG_SCRATCHPAD, scratch_woq_f32_mem},
    };
    const std::unordered_map<int, dnnl::memory> woq_bf16_args = {
            {DNNL_ARG_SRC, src_bf16_woq_mem},
            {DNNL_ARG_WEIGHTS, packed_bf16_mem},
            {DNNL_ARG_DST, dst_woq_bf16_mem},
            {DNNL_ARG_ATTR_SCALES | DNNL_ARG_WEIGHTS, scales_mem},
            {DNNL_ARG_SCRATCHPAD, scratch_woq_bf16_mem},
    };
    const std::unordered_map<int, dnnl::memory> bf16_args = {
            {DNNL_ARG_SRC, weights_bf16_mem},
            {DNNL_ARG_WEIGHTS, src_bf16_mem},
            {DNNL_ARG_DST, dst_bf16_mem},
            {DNNL_ARG_SCRATCHPAD, scratch_bf16_mem},
    };

    auto submit_src_conversion = [&] {
        const float *src = src_f32_device.as<float>();
        bf16 *dst = src_bf16_device.as<bf16>();
        return queue.parallel_for(sycl::range<1>(src_elements), [=](sycl::id<1> id) {
            dst[id[0]] = bf16(src[id[0]]);
        });
    };

    auto submit_weight_dequant = [&] {
        const q8_0_block *src = q8_device.as<q8_0_block>();
        bf16 *dst = weights_bf16_device.as<bf16>();
        return queue.parallel_for(sycl::range<1>(weight_elements), [=](sycl::id<1> id) {
            const size_t linear = id[0];
            const int64_t o = static_cast<int64_t>(linear / kInput);
            const int64_t k = static_cast<int64_t>(linear - static_cast<size_t>(o * kInput));
            const q8_0_block &block = src[o * groups + k / kGroup];
            dst[linear] = bf16(static_cast<float>(block.d)
                    * static_cast<float>(block.qs[k % kGroup]));
        });
    };

    // Materialize the resident-BF16 ceiling outside timing.
    submit_src_conversion();
    submit_weight_dequant();
    queue.wait_and_throw();

    struct arm {
        std::string name;
        std::function<void()> submit_one;
        std::vector<double> samples;
    };

    std::vector<arm> arms;
    arms.push_back({"onednn_woq_f32_src", [&] {
        dnnl::sycl_interop::execute(woq_f32.primitive, stream, woq_f32_args);
    }, {}});
    arms.push_back({"onednn_woq_bf16_src", [&] {
        dnnl::sycl_interop::execute(woq_bf16.primitive, stream, woq_bf16_args);
    }, {}});
    arms.push_back({"q8_dequant_bf16_plus_onednn", [&] {
        submit_src_conversion();
        submit_weight_dequant();
        dnnl::sycl_interop::execute(bf16_matmul.primitive, stream, bf16_args);
    }, {}});
    arms.push_back({"resident_bf16_onednn_ceiling", [&] {
        dnnl::sycl_interop::execute(bf16_matmul.primitive, stream, bf16_args);
    }, {}});

    for (arm &candidate : arms) {
        for (int i = 0; i < opts.warmup; ++i) candidate.submit_one();
        queue.wait_and_throw();
    }

    // Rotate the arm order each repeat to bound temperature/order bias.
    for (int repeat = 0; repeat < opts.repeats; ++repeat) {
        for (size_t step = 0; step < arms.size(); ++step) {
            arm &candidate = arms[(step + static_cast<size_t>(repeat)) % arms.size()];
            const auto start = clock_type::now();
            for (int inner = 0; inner < opts.inner; ++inner) candidate.submit_one();
            queue.wait_and_throw();
            const double elapsed_us =
                    std::chrono::duration<double, std::micro>(clock_type::now() - start).count();
            candidate.samples.push_back(elapsed_us / opts.inner);
        }
    }

    // Capture one output for each arm.  The in-order queue makes each copy
    // depend on the immediately preceding execution without cross-queue edges.
    std::vector<std::vector<float>> outputs(arms.size(), std::vector<float>(dst_elements));
    for (size_t i = 0; i < arms.size(); ++i) {
        arms[i].submit_one();
        void *device_output = nullptr;
        if (i == 0) device_output = dst_woq_f32_device.get();
        else if (i == 1) device_output = dst_woq_bf16_device.get();
        else device_output = dst_bf16_device.get();
        queue.memcpy(outputs[i].data(), device_output, dst_elements * sizeof(float));
        queue.wait_and_throw();
    }

    std::cerr << "computing direct Q8_0 x F32 CPU reference for O=" << output << "\n";
    const std::vector<float> reference = cpu_reference(host);
    const std::vector<float> &baseline = outputs[2];
    const double operations = 2.0 * static_cast<double>(kTokens) * kInput * output;
    for (size_t i = 0; i < arms.size(); ++i) {
        arm_result arm_out;
        arm_out.name = arms[i].name;
        arm_out.timing = summarize(std::move(arms[i].samples));
        arm_out.gflops = operations / (arm_out.timing.median_us * 1e3);
        if (i == 0) {
            arm_out.modeled_bytes = static_cast<double>(packed_f32_device.bytes()
                    + scales_device.bytes() + src_elements * sizeof(float)
                    + dst_elements * sizeof(float));
        } else if (i == 1) {
            arm_out.modeled_bytes = static_cast<double>(packed_bf16_device.bytes()
                    + scales_device.bytes() + src_elements * sizeof(bf16)
                    + dst_elements * sizeof(float));
        } else if (i == 2) {
            arm_out.modeled_bytes = static_cast<double>(q8_device.bytes()
                    + 2 * weights_bf16_device.bytes()
                    + src_elements * (sizeof(float) + 2 * sizeof(bf16))
                    + dst_elements * sizeof(float));
        } else {
            arm_out.modeled_bytes = static_cast<double>(weights_bf16_device.bytes()
                    + src_elements * sizeof(bf16) + dst_elements * sizeof(float));
        }
        arm_out.modeled_gbps = arm_out.modeled_bytes / (arm_out.timing.median_us * 1e3);
        arm_out.vs_q8_f32 = compare_vectors(outputs[i], reference);
        arm_out.vs_baseline = compare_vectors(outputs[i], baseline);
        result.arms.push_back(std::move(arm_out));
    }

    return result;
}

std::string json_escape(const std::string &value) {
    std::ostringstream out;
    for (unsigned char c : value) {
        switch (c) {
            case '\\': out << "\\\\"; break;
            case '"': out << "\\\""; break;
            case '\n': out << "\\n"; break;
            case '\r': out << "\\r"; break;
            case '\t': out << "\\t"; break;
            default:
                if (c < 0x20) {
                    out << "\\u" << std::hex << std::setw(4) << std::setfill('0')
                        << static_cast<int>(c) << std::dec;
                } else {
                    out << c;
                }
        }
    }
    return out.str();
}

void emit_error_metrics(std::ostream &out, const error_metrics &m) {
    out << "{\"max_abs\":" << m.max_abs
        << ",\"max_rel\":" << m.max_rel
        << ",\"rmse\":" << m.rmse
        << ",\"nrmse\":" << m.nrmse
        << ",\"cosine\":" << m.cosine << '}';
}

std::string make_json(const options &opts, const sycl::device &device,
        const std::vector<shape_result> &results) {
    const dnnl_version_t *version = dnnl_version();
    std::ostringstream out;
    out << std::setprecision(10);
    out << "{\n"
        << "  \"benchmark\":\"muse_q8_0_onednn_woq_width16\",\n"
        << "  \"onednn_version\":\"" << version->major << '.' << version->minor
        << '.' << version->patch << "\",\n"
        << "  \"device\":\""
        << json_escape(device.get_info<sycl::info::device::name>()) << "\",\n"
        << "  \"driver\":\""
        << json_escape(device.get_info<sycl::info::device::driver_version>()) << "\",\n"
        << "  \"tokens\":" << kTokens << ",\n"
        << "  \"input\":" << kInput << ",\n"
        << "  \"q8_group\":" << kGroup << ",\n"
        << "  \"warmup\":" << opts.warmup << ",\n"
        << "  \"repeats\":" << opts.repeats << ",\n"
        << "  \"inner\":" << opts.inner << ",\n"
        << "  \"timing_note\":\"host wall time per op; queue wait once per inner batch;"
           " rotated arm order\",\n"
        << "  \"shapes\":[\n";
    for (size_t si = 0; si < results.size(); ++si) {
        const shape_result &shape = results[si];
        out << "    {\"output\":" << shape.output
            << ",\"woq_pack_ms_f32\":" << shape.woq_pack_ms_f32
            << ",\"woq_pack_ms_bf16\":" << shape.woq_pack_ms_bf16
            << ",\"woq_packed_bytes_f32\":" << shape.woq_packed_bytes_f32
            << ",\"woq_packed_bytes_bf16\":" << shape.woq_packed_bytes_bf16
            << ",\"woq_f32_impl\":\"" << json_escape(shape.woq_f32_impl) << "\""
            << ",\"woq_bf16_impl\":\"" << json_escape(shape.woq_bf16_impl) << "\""
            << ",\"bf16_impl\":\"" << json_escape(shape.bf16_impl) << "\""
            << ",\"woq_scale_exec_md_query_available\":"
            << (shape.woq_scale_exec_md_query_available ? "true" : "false")
            << ",\"woq_scale_md\":{\"dims\":[" << kInput / kGroup << ','
            << shape.output << "],\"strides\":[" << shape.output
            << ",1],\"data_type\":\"f16\"}"
            << ",\"arms\":[\n";
        for (size_t ai = 0; ai < shape.arms.size(); ++ai) {
            const arm_result &arm = shape.arms[ai];
            out << "      {\"name\":\"" << json_escape(arm.name) << "\""
                << ",\"median_us\":" << arm.timing.median_us
                << ",\"p10_us\":" << arm.timing.p10_us
                << ",\"p90_us\":" << arm.timing.p90_us
                << ",\"min_us\":" << arm.timing.min_us
                << ",\"mean_us\":" << arm.timing.mean_us
                << ",\"gflops\":" << arm.gflops
                << ",\"modeled_bytes\":" << arm.modeled_bytes
                << ",\"modeled_gbps\":" << arm.modeled_gbps
                << ",\"vs_direct_q8_f32\":";
            emit_error_metrics(out, arm.vs_q8_f32);
            out << ",\"vs_dequant_bf16_baseline\":";
            emit_error_metrics(out, arm.vs_baseline);
            out << '}' << (ai + 1 == shape.arms.size() ? "\n" : ",\n");
        }
        out << "    ]}" << (si + 1 == results.size() ? "\n" : ",\n");
    }
    out << "  ]\n}\n";
    return out.str();
}

} // namespace

int main(int argc, char **argv) {
    try {
        const options opts = parse_options(argc, argv);
        if (!opts.run) {
            std::cerr << "refusing to select a GPU without explicit --run; use --help\n";
            return 2;
        }
        const char *selector = std::getenv("ONEAPI_DEVICE_SELECTOR");
        if (!selector || std::strcmp(selector, "level_zero:0") != 0) {
            fail("ONEAPI_DEVICE_SELECTOR must be exactly level_zero:0");
        }

        sycl::queue queue(sycl::gpu_selector_v,
                sycl::property_list {sycl::property::queue::in_order {}});
        const sycl::device device = queue.get_device();
        const std::string device_name = device.get_info<sycl::info::device::name>();
        const std::string vendor = device.get_info<sycl::info::device::vendor>();
        if (vendor.find("Intel") == std::string::npos
                || device_name.find("B70") == std::string::npos) {
            fail("selected device is not an Intel Arc Pro B70: " + device_name);
        }

        const dnnl::engine engine = dnnl::sycl_interop::make_engine(
                queue.get_device(), queue.get_context());
        const dnnl::stream stream = dnnl::sycl_interop::make_stream(engine, queue);

        std::cerr << "device: " << device_name << "\n";
        std::vector<shape_result> results;
        for (int64_t output : kOutputs) {
            results.push_back(benchmark_shape(opts, queue, engine, stream, output));
        }

        const std::string json = make_json(opts, device, results);
        std::cout << json;
        if (!opts.json_path.empty()) {
            std::ofstream file(opts.json_path, std::ios::binary | std::ios::trunc);
            if (!file) fail("could not open JSON output: " + opts.json_path);
            file << json;
            if (!file) fail("failed to write JSON output: " + opts.json_path);
        }
        return 0;
    } catch (const dnnl::error &error) {
        std::cerr << "oneDNN error: status=" << dnnl_status2str(error.status)
                  << " message=" << error.what() << '\n';
        return 3;
    } catch (const sycl::exception &error) {
        std::cerr << "SYCL error: " << error.what() << '\n';
        return 4;
    } catch (const std::exception &error) {
        std::cerr << "error: " << error.what() << '\n';
        return 5;
    }
}
