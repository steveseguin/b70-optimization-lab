#include <algorithm>
#include <chrono>
#include <cstdlib>
#include <cstdint>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <numeric>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>

#include "example_utils.hpp"
#include "oneapi/dnnl/dnnl.hpp"

using namespace dnnl;

namespace {

struct Stats {
    double mean_us = 0.0;
    double min_us = 0.0;
    double p50_us = 0.0;
    double p90_us = 0.0;
    double max_us = 0.0;
};

struct Result {
    std::string name;
    std::string kind;
    int64_t construct_us = 0;
    int64_t total_tokens = 0;
    int64_t num_experts = 0;
    int64_t k_dim = 0;
    int64_t n_dim = 0;
    double checksum = 0.0;
    Stats stats;
};

int env_int(const char *name, int fallback) {
    const char *value = std::getenv(name);
    if (!value || !*value) return fallback;
    return std::stoi(value);
}

std::string json_escape(const std::string &value) {
    std::string out;
    out.reserve(value.size() + 8);
    for (char c : value) {
        if (c == '\\' || c == '"') out.push_back('\\');
        out.push_back(c);
    }
    return out;
}

std::string env_string(const char *name, const std::string &fallback = "") {
    const char *value = std::getenv(name);
    if (!value || !*value) return fallback;
    return std::string(value);
}

size_t dt_size(memory::data_type dt) {
    switch (dt) {
    case memory::data_type::f32: return 4;
    case memory::data_type::bf16: return 2;
    case memory::data_type::s8:
    case memory::data_type::u8: return 1;
    default: throw std::runtime_error("unsupported dtype");
    }
}

std::string dt_name(memory::data_type dt) {
    switch (dt) {
    case memory::data_type::f32: return "f32";
    case memory::data_type::bf16: return "bf16";
    case memory::data_type::s8: return "s8";
    case memory::data_type::u8: return "u8";
    default: return "other";
    }
}

std::vector<uint8_t> make_buffer(size_t elements, memory::data_type dt) {
    std::vector<uint8_t> out(elements * dt_size(dt), 0);
    if (dt == memory::data_type::f32) {
        auto *ptr = reinterpret_cast<float *>(out.data());
        for (size_t i = 0; i < elements; ++i) {
            ptr[i] = float((int(i % 23) - 11)) / 8.0f;
        }
    } else if (dt == memory::data_type::bf16) {
        auto *ptr = reinterpret_cast<uint16_t *>(out.data());
        for (size_t i = 0; i < elements; ++i) {
            ptr[i] = uint16_t(0x3f80 + (i % 7));
        }
    } else if (dt == memory::data_type::s8) {
        auto *ptr = reinterpret_cast<int8_t *>(out.data());
        for (size_t i = 0; i < elements; ++i) {
            ptr[i] = int8_t(int(i % 31) - 15);
        }
    } else if (dt == memory::data_type::u8) {
        auto *ptr = reinterpret_cast<uint8_t *>(out.data());
        for (size_t i = 0; i < elements; ++i) {
            ptr[i] = uint8_t((i % 31) + 1);
        }
    }
    return out;
}

Stats summarize(const std::vector<double> &samples) {
    if (samples.empty()) throw std::runtime_error("no samples");
    std::vector<double> sorted = samples;
    std::sort(sorted.begin(), sorted.end());
    const double sum = std::accumulate(samples.begin(), samples.end(), 0.0);
    auto percentile = [&](double p) {
        const size_t idx = std::min(sorted.size() - 1,
                static_cast<size_t>((sorted.size() - 1) * p + 0.5));
        return sorted[idx];
    };
    Stats out;
    out.mean_us = sum / double(samples.size());
    out.min_us = sorted.front();
    out.p50_us = percentile(0.50);
    out.p90_us = percentile(0.90);
    out.max_us = sorted.back();
    return out;
}

std::vector<std::vector<int32_t>> load_count_windows(
        const std::string &path, int expected_experts, int expected_total) {
    std::vector<std::vector<int32_t>> windows;
    if (path.empty()) return windows;

    std::ifstream in(path);
    if (!in) throw std::runtime_error("failed to open route counts: " + path);

    std::string line;
    int line_no = 0;
    while (std::getline(in, line)) {
        ++line_no;
        if (line.empty()) continue;
        std::vector<int32_t> counts;
        std::stringstream ss(line);
        std::string item;
        while (std::getline(ss, item, ',')) {
            if (!item.empty()) counts.push_back(std::stoi(item));
        }
        if (static_cast<int>(counts.size()) != expected_experts) {
            throw std::runtime_error("route-count line " + std::to_string(line_no)
                    + " has " + std::to_string(counts.size()) + " experts, expected "
                    + std::to_string(expected_experts));
        }
        const int total = std::accumulate(counts.begin(), counts.end(), 0);
        if (total != expected_total) {
            throw std::runtime_error("route-count line " + std::to_string(line_no)
                    + " total " + std::to_string(total) + ", expected "
                    + std::to_string(expected_total));
        }
        windows.push_back(std::move(counts));
    }
    if (windows.empty()) {
        throw std::runtime_error("route-count file had no windows: " + path);
    }
    return windows;
}

class ReusableMatmul {
  public:
    ReusableMatmul(engine &eng, const std::string &name,
            memory::data_type src_dt, memory::data_type wei_dt,
            memory::data_type dst_dt,
            const std::vector<int32_t> &tokens_per_expert, memory::dim k_dim,
            memory::dim n_dim)
        : name_(name),
          src_dt_(src_dt),
          wei_dt_(wei_dt),
          dst_dt_(dst_dt),
          num_experts_(memory::dim(tokens_per_expert.size())),
          k_dim_(k_dim),
          n_dim_(n_dim) {
        const auto construct_start = std::chrono::steady_clock::now();

        offsets_.resize(num_experts_);
        offsets_[0] = tokens_per_expert[0];
        for (memory::dim i = 1; i < num_experts_; ++i) {
            offsets_[i] = offsets_[i - 1] + tokens_per_expert[i];
        }
        total_tokens_ = std::accumulate(
                tokens_per_expert.begin(), tokens_per_expert.end(), memory::dim(0));

        const memory::dims src_dims = {total_tokens_, k_dim_};
        const memory::dims weights_dims = {num_experts_, k_dim_, n_dim_};
        const memory::dims dst_dims = {total_tokens_, n_dim_};

        src_md_ = memory::desc::grouped(src_dims, src_dt_, 0, num_experts_);
        dst_md_ = memory::desc::grouped(dst_dims, dst_dt_, 0, num_experts_);
        weights_md_ = memory::desc(weights_dims, wei_dt_, memory::format_tag::acb);

        primitive_attr attr;
        attr.set_scales_mask(DNNL_ARG_SRC, 1 << 0);
        attr.set_scales_mask(DNNL_ARG_WEIGHTS, (1 << 0) | (1 << 2));

        pd_ = matmul::primitive_desc(eng, src_md_, weights_md_, dst_md_, attr);
        prim_ = matmul(pd_);

        src_mem_ = memory(src_md_, eng);
        dst_mem_ = memory(dst_md_, eng);
        weights_mem_ = memory(weights_md_, eng);

        auto src_data = make_buffer(total_tokens_ * k_dim_, src_dt_);
        auto wei_data = make_buffer(num_experts_ * n_dim_ * k_dim_, wei_dt_);
        auto dst_data = make_buffer(total_tokens_ * n_dim_, dst_dt_);
        write_to_dnnl_memory(src_data.data(), src_mem_);
        write_to_dnnl_memory(wei_data.data(), weights_mem_);
        write_to_dnnl_memory(dst_data.data(), dst_mem_);
        write_to_dnnl_memory(offsets_.data(), src_mem_, 1);
        write_to_dnnl_memory(offsets_.data(), dst_mem_, 1);

        std::vector<float> src_scales(total_tokens_);
        for (memory::dim i = 0; i < total_tokens_; ++i) {
            src_scales[i] = 0.01f + float(i % 17) * 0.001f;
        }
        const auto src_scales_md = memory::desc(
                {total_tokens_}, memory::data_type::f32, memory::format_tag::a);
        src_scales_mem_ = memory(src_scales_md, eng);
        write_to_dnnl_memory(src_scales.data(), src_scales_mem_);

        std::vector<float> wei_scales(num_experts_ * n_dim_);
        for (memory::dim i = 0; i < num_experts_ * n_dim_; ++i) {
            wei_scales[i] = 0.02f + float(i % 31) * 0.0005f;
        }
        const auto wei_scales_md = memory::desc(
                {num_experts_, n_dim_}, memory::data_type::f32,
                memory::format_tag::ab);
        wei_scales_mem_ = memory(wei_scales_md, eng);
        write_to_dnnl_memory(wei_scales.data(), wei_scales_mem_);

        args_ = {{DNNL_ARG_SRC, src_mem_},
                {DNNL_ARG_WEIGHTS, weights_mem_},
                {DNNL_ARG_DST, dst_mem_},
                {DNNL_ARG_ATTR_SCALES | DNNL_ARG_SRC, src_scales_mem_},
                {DNNL_ARG_ATTR_SCALES | DNNL_ARG_WEIGHTS, wei_scales_mem_}};

        const auto construct_end = std::chrono::steady_clock::now();
        construct_us_ = std::chrono::duration_cast<std::chrono::microseconds>(
                construct_end - construct_start).count();
    }

    void execute(stream &engine_stream) { prim_.execute(engine_stream, args_); }

    void update_counts(const std::vector<int32_t> &tokens_per_expert) {
        if (memory::dim(tokens_per_expert.size()) != num_experts_) {
            throw std::runtime_error("count window expert count mismatch");
        }
        const int total = std::accumulate(
                tokens_per_expert.begin(), tokens_per_expert.end(), 0);
        if (total != total_tokens_) {
            throw std::runtime_error("count window token total mismatch");
        }
        offsets_[0] = tokens_per_expert[0];
        for (memory::dim i = 1; i < num_experts_; ++i) {
            offsets_[i] = offsets_[i - 1] + tokens_per_expert[i];
        }
        write_to_dnnl_memory(offsets_.data(), src_mem_, 1);
        write_to_dnnl_memory(offsets_.data(), dst_mem_, 1);
    }

    Result benchmark(stream &engine_stream, int warmup, int iterations) {
        for (int i = 0; i < warmup; ++i) {
            execute(engine_stream);
            engine_stream.wait();
        }

        std::vector<double> samples;
        samples.reserve(iterations);
        for (int i = 0; i < iterations; ++i) {
            const auto start = std::chrono::steady_clock::now();
            execute(engine_stream);
            engine_stream.wait();
            const auto end = std::chrono::steady_clock::now();
            samples.push_back(std::chrono::duration<double, std::micro>(
                    end - start).count());
        }
        return result("single_wait_each", summarize(samples), checksum());
    }

    Result benchmark_route_windows(stream &engine_stream, int warmup,
            int iterations, const std::vector<std::vector<int32_t>> &windows) {
        if (windows.empty()) throw std::runtime_error("no route windows");
        for (int i = 0; i < warmup; ++i) {
            update_counts(windows[static_cast<size_t>(i) % windows.size()]);
            execute(engine_stream);
            engine_stream.wait();
        }

        std::vector<double> samples;
        samples.reserve(iterations);
        for (int i = 0; i < iterations; ++i) {
            const auto &counts = windows[static_cast<size_t>(i) % windows.size()];
            const auto start = std::chrono::steady_clock::now();
            update_counts(counts);
            execute(engine_stream);
            engine_stream.wait();
            const auto end = std::chrono::steady_clock::now();
            samples.push_back(std::chrono::duration<double, std::micro>(
                    end - start).count());
        }
        return result("route_windows_update_offsets_single_wait",
                summarize(samples), checksum());
    }

    Result result(const std::string &kind, Stats stats,
            double checksum_value) const {
        return Result{name_, kind, construct_us_, total_tokens_, num_experts_,
                k_dim_, n_dim_, checksum_value, stats};
    }

    const std::string &name() const { return name_; }

    double checksum() {
        const size_t elements = static_cast<size_t>(total_tokens_ * n_dim_);
        auto host = make_buffer(elements, dst_dt_);
        read_from_dnnl_memory(host.data(), dst_mem_);
        double sum = 0.0;
        if (dst_dt_ == memory::data_type::f32) {
            const auto *ptr = reinterpret_cast<const float *>(host.data());
            for (size_t i = 0; i < elements; ++i) sum += double(ptr[i]);
        } else if (dst_dt_ == memory::data_type::bf16) {
            const auto *ptr = reinterpret_cast<const uint16_t *>(host.data());
            for (size_t i = 0; i < elements; ++i) sum += double(ptr[i]);
        } else {
            const auto *ptr = reinterpret_cast<const int8_t *>(host.data());
            for (size_t i = 0; i < elements; ++i) sum += double(ptr[i]);
        }
        return sum;
    }

  private:
    std::string name_;
    memory::data_type src_dt_;
    memory::data_type wei_dt_;
    memory::data_type dst_dt_;
    memory::dim num_experts_ = 0;
    memory::dim total_tokens_ = 0;
    memory::dim k_dim_ = 0;
    memory::dim n_dim_ = 0;
    int64_t construct_us_ = 0;
    std::vector<int32_t> offsets_;
    memory::desc src_md_;
    memory::desc dst_md_;
    memory::desc weights_md_;
    matmul::primitive_desc pd_;
    matmul prim_;
    memory src_mem_;
    memory dst_mem_;
    memory weights_mem_;
    memory src_scales_mem_;
    memory wei_scales_mem_;
    std::unordered_map<int, memory> args_;
};

Result benchmark_pair(ReusableMatmul &first, ReusableMatmul &second,
        stream &engine_stream, int warmup, int iterations) {
    for (int i = 0; i < warmup; ++i) {
        first.execute(engine_stream);
        second.execute(engine_stream);
        engine_stream.wait();
    }

    std::vector<double> samples;
    samples.reserve(iterations);
    for (int i = 0; i < iterations; ++i) {
        const auto start = std::chrono::steady_clock::now();
        first.execute(engine_stream);
        second.execute(engine_stream);
        engine_stream.wait();
        const auto end = std::chrono::steady_clock::now();
        samples.push_back(std::chrono::duration<double, std::micro>(
                end - start).count());
    }

    Result out = first.result("two_exec_one_wait", summarize(samples),
            first.checksum() + second.checksum());
    out.name = first.name() + "+" + second.name();
    out.k_dim = -1;
    out.n_dim = -1;
    return out;
}

Result benchmark_pair_route_windows(ReusableMatmul &first,
        ReusableMatmul &second, stream &engine_stream, int warmup,
        int iterations, const std::vector<std::vector<int32_t>> &windows) {
    if (windows.empty()) throw std::runtime_error("no route windows");
    for (int i = 0; i < warmup; ++i) {
        const auto &counts = windows[static_cast<size_t>(i) % windows.size()];
        first.update_counts(counts);
        second.update_counts(counts);
        first.execute(engine_stream);
        second.execute(engine_stream);
        engine_stream.wait();
    }

    std::vector<double> samples;
    samples.reserve(iterations);
    for (int i = 0; i < iterations; ++i) {
        const auto &counts = windows[static_cast<size_t>(i) % windows.size()];
        const auto start = std::chrono::steady_clock::now();
        first.update_counts(counts);
        second.update_counts(counts);
        first.execute(engine_stream);
        second.execute(engine_stream);
        engine_stream.wait();
        const auto end = std::chrono::steady_clock::now();
        samples.push_back(std::chrono::duration<double, std::micro>(
                end - start).count());
    }

    Result out = first.result("route_windows_update_offsets_two_exec_one_wait",
            summarize(samples), first.checksum() + second.checksum());
    out.name = first.name() + "+" + second.name();
    out.k_dim = -1;
    out.n_dim = -1;
    return out;
}

void print_result(const Result &r) {
    std::cout << "REUSE name=" << r.name << " kind=" << r.kind
              << " construct_us=" << r.construct_us
              << " tokens=" << r.total_tokens << " experts=" << r.num_experts
              << " K=" << r.k_dim << " N=" << r.n_dim
              << std::fixed << std::setprecision(3)
              << " checksum=" << r.checksum
              << " mean_us=" << r.stats.mean_us
              << " min_us=" << r.stats.min_us
              << " p50_us=" << r.stats.p50_us
              << " p90_us=" << r.stats.p90_us
              << " max_us=" << r.stats.max_us << std::endl;
}

void write_json(const std::string &path, int warmup, int iterations,
        int route_windows, const std::vector<Result> &results) {
    std::ofstream out(path);
    if (!out) throw std::runtime_error("failed to open json output: " + path);
    out << std::fixed << std::setprecision(6);
    out << "{\n";
    out << "  \"warmup\": " << warmup << ",\n";
    out << "  \"iterations\": " << iterations << ",\n";
    out << "  \"route_windows\": " << route_windows << ",\n";
    out << "  \"results\": [\n";
    for (size_t i = 0; i < results.size(); ++i) {
        const auto &r = results[i];
        out << "    {\n";
        out << "      \"name\": \"" << json_escape(r.name) << "\",\n";
        out << "      \"kind\": \"" << json_escape(r.kind) << "\",\n";
        out << "      \"construct_us\": " << r.construct_us << ",\n";
        out << "      \"total_tokens\": " << r.total_tokens << ",\n";
        out << "      \"num_experts\": " << r.num_experts << ",\n";
        out << "      \"k_dim\": " << r.k_dim << ",\n";
        out << "      \"n_dim\": " << r.n_dim << ",\n";
        out << "      \"checksum\": " << r.checksum << ",\n";
        out << "      \"mean_us\": " << r.stats.mean_us << ",\n";
        out << "      \"min_us\": " << r.stats.min_us << ",\n";
        out << "      \"p50_us\": " << r.stats.p50_us << ",\n";
        out << "      \"p90_us\": " << r.stats.p90_us << ",\n";
        out << "      \"max_us\": " << r.stats.max_us << "\n";
        out << "    }" << (i + 1 == results.size() ? "\n" : ",\n");
    }
    out << "  ]\n";
    out << "}\n";
}

void probe(engine::kind engine_kind) {
    const int warmup = env_int("REUSE_WARMUP", 20);
    const int iterations = env_int("REUSE_ITERATIONS", 200);
    const std::string route_counts_path = env_string("REUSE_ROUTE_COUNTS");
    engine eng(engine_kind, 0);
    stream engine_stream(eng);

    std::vector<int32_t> qwen_l9_counts(256, 0);
    for (int expert : {59, 2, 243, 161, 255, 170, 200, 36}) {
        qwen_l9_counts[expert] = 1;
    }
    const auto route_windows = load_count_windows(
            route_counts_path, 256, std::accumulate(qwen_l9_counts.begin(),
                                            qwen_l9_counts.end(), 0));

    ReusableMatmul gemm1_bf16(eng, "qwen_l9_gemm1_s8s8_bf16",
            memory::data_type::s8, memory::data_type::s8,
            memory::data_type::bf16, qwen_l9_counts, 2048, 256);
    ReusableMatmul gemm2_bf16(eng, "qwen_l9_gemm2_s8s8_bf16",
            memory::data_type::s8, memory::data_type::s8,
            memory::data_type::bf16, qwen_l9_counts, 128, 2048);
    ReusableMatmul gemm1_f32(eng, "qwen_l9_gemm1_s8s8_f32",
            memory::data_type::s8, memory::data_type::s8,
            memory::data_type::f32, qwen_l9_counts, 2048, 256);
    ReusableMatmul gemm2_f32(eng, "qwen_l9_gemm2_s8s8_f32",
            memory::data_type::s8, memory::data_type::s8,
            memory::data_type::f32, qwen_l9_counts, 128, 2048);

    std::vector<Result> results;
    results.push_back(gemm1_bf16.benchmark(engine_stream, warmup, iterations));
    results.push_back(gemm2_bf16.benchmark(engine_stream, warmup, iterations));
    results.push_back(benchmark_pair(gemm1_bf16, gemm2_bf16, engine_stream,
            warmup, iterations));
    results.push_back(gemm1_f32.benchmark(engine_stream, warmup, iterations));
    results.push_back(gemm2_f32.benchmark(engine_stream, warmup, iterations));
    results.push_back(benchmark_pair(gemm1_f32, gemm2_f32, engine_stream,
            warmup, iterations));
    if (!route_windows.empty()) {
        results.push_back(gemm1_bf16.benchmark_route_windows(
                engine_stream, warmup, iterations, route_windows));
        results.push_back(gemm2_bf16.benchmark_route_windows(
                engine_stream, warmup, iterations, route_windows));
        results.push_back(benchmark_pair_route_windows(gemm1_bf16, gemm2_bf16,
                engine_stream, warmup, iterations, route_windows));
        results.push_back(gemm1_f32.benchmark_route_windows(
                engine_stream, warmup, iterations, route_windows));
        results.push_back(gemm2_f32.benchmark_route_windows(
                engine_stream, warmup, iterations, route_windows));
        results.push_back(benchmark_pair_route_windows(gemm1_f32, gemm2_f32,
                engine_stream, warmup, iterations, route_windows));
    }

    for (const auto &result : results) print_result(result);

    const char *json_path = std::getenv("REUSE_JSON_OUT");
    if (json_path && *json_path) {
        write_json(json_path, warmup, iterations,
                static_cast<int>(route_windows.size()), results);
    }
}

} // namespace

int main(int argc, char **argv) {
    engine::kind engine_kind = parse_engine_kind(argc, argv);
    return handle_example_errors(probe, engine_kind);
}
