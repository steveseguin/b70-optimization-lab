#include <algorithm>
#include <chrono>
#include <cstdint>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <numeric>
#include <stdexcept>
#include <string>
#include <sstream>
#include <unordered_map>
#include <vector>

#include "example_utils.hpp"
#include "oneapi/dnnl/dnnl.hpp"

using namespace dnnl;

namespace {

struct Meta {
    std::string name;
    int64_t num_experts = 0;
    int64_t total_tokens = 0;
    int64_t k = 0;
    int64_t n = 0;
    std::string dst_dtype = "bf16";
    std::string weight_format = "abc";
    std::unordered_map<std::string, std::string> paths;
};

struct Stats {
    double mean_us = 0.0;
    double min_us = 0.0;
    double p50_us = 0.0;
    double p90_us = 0.0;
    double max_us = 0.0;
};

std::string env_string(const char *name, const std::string &fallback = "") {
    const char *value = std::getenv(name);
    if (!value || !*value) return fallback;
    return std::string(value);
}

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

memory::data_type parse_dst_dtype(const std::string &value) {
    if (value == "bf16") return memory::data_type::bf16;
    if (value == "fp16" || value == "f16") return memory::data_type::f16;
    if (value == "f32") return memory::data_type::f32;
    throw std::runtime_error("unsupported dst_dtype: " + value);
}

memory::format_tag parse_weight_format(const std::string &value) {
    if (value == "abc") return memory::format_tag::abc;
    if (value == "acb") return memory::format_tag::acb;
    throw std::runtime_error("unsupported weight_format: " + value);
}

size_t dtype_size(memory::data_type dt) {
    switch (dt) {
    case memory::data_type::f32: return 4;
    case memory::data_type::bf16:
    case memory::data_type::f16: return 2;
    case memory::data_type::s8: return 1;
    default: throw std::runtime_error("unsupported dtype size");
    }
}

std::vector<uint8_t> read_file(const std::filesystem::path &path) {
    std::ifstream in(path, std::ios::binary);
    if (!in) throw std::runtime_error("failed to open " + path.string());
    in.seekg(0, std::ios::end);
    const auto size = in.tellg();
    if (size < 0) throw std::runtime_error("failed to size " + path.string());
    in.seekg(0, std::ios::beg);
    std::vector<uint8_t> data(static_cast<size_t>(size));
    if (!data.empty()) {
        in.read(reinterpret_cast<char *>(data.data()), size);
        if (!in) throw std::runtime_error("failed to read " + path.string());
    }
    return data;
}

void expect_size(const std::string &name, const std::vector<uint8_t> &data,
        size_t expected) {
    if (data.size() != expected) {
        throw std::runtime_error(name + " size " + std::to_string(data.size())
                + " expected " + std::to_string(expected));
    }
}

Meta read_meta(const std::filesystem::path &path) {
    std::ifstream in(path);
    if (!in) throw std::runtime_error("failed to open meta: " + path.string());
    Meta meta;
    std::string line;
    while (std::getline(in, line)) {
        if (line.empty()) continue;
        const auto pos = line.find('=');
        if (pos == std::string::npos) continue;
        const std::string key = line.substr(0, pos);
        const std::string value = line.substr(pos + 1);
        if (key == "name") meta.name = value;
        else if (key == "num_experts") meta.num_experts = std::stoll(value);
        else if (key == "total_tokens") meta.total_tokens = std::stoll(value);
        else if (key == "k") meta.k = std::stoll(value);
        else if (key == "n") meta.n = std::stoll(value);
        else if (key == "dst_dtype") meta.dst_dtype = value;
        else if (key == "weight_format") meta.weight_format = value;
        else meta.paths[key] = value;
    }
    if (meta.name.empty() || meta.num_experts <= 0 || meta.total_tokens <= 0
            || meta.k <= 0 || meta.n <= 0) {
        throw std::runtime_error("incomplete meta: " + path.string());
    }
    return meta;
}

std::vector<int32_t> cumulative_offsets(const std::vector<uint8_t> &rows_data,
        int64_t num_experts, int64_t expected_total) {
    expect_size("rows", rows_data, static_cast<size_t>(num_experts) * sizeof(int32_t));
    const auto *rows = reinterpret_cast<const int32_t *>(rows_data.data());
    std::vector<int32_t> offsets(static_cast<size_t>(num_experts), 0);
    int64_t total = 0;
    for (int64_t i = 0; i < num_experts; ++i) {
        total += rows[i];
        offsets[static_cast<size_t>(i)] = static_cast<int32_t>(total);
    }
    if (total != expected_total) {
        throw std::runtime_error("rows total " + std::to_string(total)
                + " expected " + std::to_string(expected_total));
    }
    return offsets;
}

std::vector<std::vector<int32_t>> load_count_windows(
        const std::string &path, int64_t expected_experts, int64_t expected_total) {
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
        if (static_cast<int64_t>(counts.size()) != expected_experts) {
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

double raw_checksum(const std::vector<uint8_t> &data, memory::data_type dt) {
    const size_t elements = data.size() / dtype_size(dt);
    double sum = 0.0;
    if (dt == memory::data_type::f32) {
        const auto *ptr = reinterpret_cast<const float *>(data.data());
        for (size_t i = 0; i < elements; ++i) sum += double(ptr[i]);
    } else if (dt == memory::data_type::bf16 || dt == memory::data_type::f16) {
        const auto *ptr = reinterpret_cast<const uint16_t *>(data.data());
        for (size_t i = 0; i < elements; ++i) sum += double(ptr[i]);
    } else {
        const auto *ptr = reinterpret_cast<const int8_t *>(data.data());
        for (size_t i = 0; i < elements; ++i) sum += double(ptr[i]);
    }
    return sum;
}

uint64_t raw_diff_count(const std::vector<uint8_t> &a, const std::vector<uint8_t> &b) {
    if (a.size() != b.size()) {
        throw std::runtime_error("raw diff size mismatch");
    }
    uint64_t diff = 0;
    for (size_t i = 0; i < a.size(); ++i) {
        if (a[i] != b[i]) ++diff;
    }
    return diff;
}

Stats summarize(const std::vector<double> &samples) {
    if (samples.empty()) throw std::runtime_error("no samples");
    std::vector<double> sorted = samples;
    std::sort(sorted.begin(), sorted.end());
    const double sum = std::accumulate(samples.begin(), samples.end(), 0.0);
    auto pct = [&](double p) {
        const size_t idx = std::min(sorted.size() - 1,
                static_cast<size_t>((sorted.size() - 1) * p + 0.5));
        return sorted[idx];
    };
    return {
        sum / double(samples.size()),
        sorted.front(),
        pct(0.50),
        pct(0.90),
        sorted.back(),
    };
}

class ResidentCase {
  public:
    ResidentCase(engine &eng, const std::filesystem::path &meta_path,
            const std::string &weight_format_name)
        : meta_path_(meta_path),
          meta_(read_meta(meta_path)),
          base_(meta_path.parent_path()),
          dst_dt_(parse_dst_dtype(meta_.dst_dtype)),
          weight_format_name_(weight_format_name.empty() ? meta_.weight_format
                                                         : weight_format_name),
          weight_format_(parse_weight_format(weight_format_name_)) {
        auto path_for = [&](const std::string &key) {
            auto it = meta_.paths.find(key);
            if (it == meta_.paths.end()) {
                throw std::runtime_error("missing path key: " + key);
            }
            return base_ / it->second;
        };

        a_data_ = read_file(path_for("a_path"));
        a_scales_data_ = read_file(path_for("a_scales_path"));
        std::string b_path_key = env_string("ONEDNN_B_PATH_KEY");
        if (b_path_key.empty()) {
            b_path_key = (weight_format_name_ == "acb"
                            && meta_.paths.find("b_acb_path") != meta_.paths.end())
                    ? "b_acb_path"
                    : "b_path";
        }
        b_path_key_ = b_path_key;
        b_data_ = read_file(path_for(b_path_key_));
        b_scales_data_ = read_file(path_for("b_scales_path"));
        rows_data_ = read_file(path_for("rows_path"));
        expected_output_ = read_file(path_for("xpu_out_path"));
        offsets_ = cumulative_offsets(rows_data_, meta_.num_experts, meta_.total_tokens);

        expect_size("A", a_data_, static_cast<size_t>(meta_.total_tokens * meta_.k));
        expect_size("A scales", a_scales_data_,
                static_cast<size_t>(meta_.total_tokens) * sizeof(float));
        expect_size("B", b_data_,
                static_cast<size_t>(meta_.num_experts * meta_.k * meta_.n));
        expect_size("B scales", b_scales_data_,
                static_cast<size_t>(meta_.num_experts * meta_.n) * sizeof(float));
        expect_size("expected output", expected_output_,
                static_cast<size_t>(meta_.total_tokens * meta_.n) * dtype_size(dst_dt_));

        const memory::dims src_dims = {meta_.total_tokens, meta_.k};
        const memory::dims weights_dims = {meta_.num_experts, meta_.k, meta_.n};
        const memory::dims dst_dims = {meta_.total_tokens, meta_.n};

        src_md_ = memory::desc::grouped(
                src_dims, memory::data_type::s8, 0, meta_.num_experts);
        dst_md_ = memory::desc::grouped(dst_dims, dst_dt_, 0, meta_.num_experts);
        weights_md_ = memory::desc(weights_dims, memory::data_type::s8,
                weight_format_);

        primitive_attr attr;
        attr.set_scales_mask(DNNL_ARG_SRC, 1 << 0);
        attr.set_scales_mask(DNNL_ARG_WEIGHTS, (1 << 0) | (1 << 2));

        const auto start = std::chrono::steady_clock::now();
        pd_ = matmul::primitive_desc(eng, src_md_, weights_md_, dst_md_, attr);
        prim_ = matmul(pd_);
        src_mem_ = memory(src_md_, eng);
        dst_mem_ = memory(dst_md_, eng);
        weights_mem_ = memory(weights_md_, eng);
        src_scales_mem_ = memory(
                memory::desc({meta_.total_tokens}, memory::data_type::f32,
                        memory::format_tag::a),
                eng);
        weights_scales_mem_ = memory(
                memory::desc({meta_.num_experts, meta_.n}, memory::data_type::f32,
                        memory::format_tag::ab),
                eng);
        const auto end = std::chrono::steady_clock::now();
        construct_us_ = std::chrono::duration_cast<std::chrono::microseconds>(
                end - start).count();

        output_.assign(
                static_cast<size_t>(meta_.total_tokens * meta_.n) * dtype_size(dst_dt_),
                0);
        write_to_dnnl_memory(a_data_.data(), src_mem_);
        write_to_dnnl_memory(b_data_.data(), weights_mem_);
        write_to_dnnl_memory(output_.data(), dst_mem_);
        write_to_dnnl_memory(offsets_.data(), src_mem_, 1);
        write_to_dnnl_memory(offsets_.data(), dst_mem_, 1);
        write_to_dnnl_memory(a_scales_data_.data(), src_scales_mem_);
        write_to_dnnl_memory(b_scales_data_.data(), weights_scales_mem_);

        args_ = {
                {DNNL_ARG_SRC, src_mem_},
                {DNNL_ARG_WEIGHTS, weights_mem_},
                {DNNL_ARG_DST, dst_mem_},
                {DNNL_ARG_ATTR_SCALES | DNNL_ARG_SRC, src_scales_mem_},
                {DNNL_ARG_ATTR_SCALES | DNNL_ARG_WEIGHTS, weights_scales_mem_},
        };
    }

    void execute(stream &engine_stream) { prim_.execute(engine_stream, args_); }

    void read_output() { read_from_dnnl_memory(output_.data(), dst_mem_); }

    void update_counts(const std::vector<int32_t> &tokens_per_expert) {
        if (static_cast<int64_t>(tokens_per_expert.size()) != meta_.num_experts) {
            throw std::runtime_error(meta_.name + " count window expert mismatch");
        }
        const int total = std::accumulate(
                tokens_per_expert.begin(), tokens_per_expert.end(), 0);
        if (total != meta_.total_tokens) {
            throw std::runtime_error(meta_.name + " count window token total mismatch");
        }
        int64_t cumulative = 0;
        for (int64_t i = 0; i < meta_.num_experts; ++i) {
            cumulative += tokens_per_expert[static_cast<size_t>(i)];
            offsets_[static_cast<size_t>(i)] = static_cast<int32_t>(cumulative);
        }
        write_to_dnnl_memory(offsets_.data(), src_mem_, 1);
        write_to_dnnl_memory(offsets_.data(), dst_mem_, 1);
    }

    const Meta &meta() const { return meta_; }
    const std::string &b_path_key() const { return b_path_key_; }
    const std::string &weight_format_name() const { return weight_format_name_; }
    int64_t construct_us() const { return construct_us_; }
    memory::data_type dst_dtype() const { return dst_dt_; }
    const std::vector<uint8_t> &output() const { return output_; }
    const std::vector<uint8_t> &expected_output() const { return expected_output_; }

  private:
    std::filesystem::path meta_path_;
    Meta meta_;
    std::filesystem::path base_;
    memory::data_type dst_dt_;
    std::string weight_format_name_;
    memory::format_tag weight_format_;
    std::string b_path_key_;
    int64_t construct_us_ = 0;

    std::vector<uint8_t> a_data_;
    std::vector<uint8_t> a_scales_data_;
    std::vector<uint8_t> b_data_;
    std::vector<uint8_t> b_scales_data_;
    std::vector<uint8_t> rows_data_;
    std::vector<uint8_t> expected_output_;
    std::vector<uint8_t> output_;
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
    memory weights_scales_mem_;
    std::unordered_map<int, memory> args_;
};

void write_case_json(std::ofstream &json, const char *prefix,
        const ResidentCase &item, const std::vector<uint8_t> &output) {
    const uint64_t diff_count = raw_diff_count(output, item.expected_output());
    json << "  \"" << prefix << "\": {\n";
    json << "    \"name\": \"" << json_escape(item.meta().name) << "\",\n";
    json << "    \"num_experts\": " << item.meta().num_experts << ",\n";
    json << "    \"total_tokens\": " << item.meta().total_tokens << ",\n";
    json << "    \"k\": " << item.meta().k << ",\n";
    json << "    \"n\": " << item.meta().n << ",\n";
    json << "    \"dst_dtype\": \"" << json_escape(item.meta().dst_dtype) << "\",\n";
    json << "    \"weight_format\": \"" << json_escape(item.weight_format_name()) << "\",\n";
    json << "    \"b_path_key\": \"" << json_escape(item.b_path_key()) << "\",\n";
    json << "    \"construct_us\": " << item.construct_us() << ",\n";
    json << "    \"raw_checksum\": " << raw_checksum(output, item.dst_dtype()) << ",\n";
    json << "    \"expected_raw_checksum\": "
         << raw_checksum(item.expected_output(), item.dst_dtype()) << ",\n";
    json << "    \"raw_equal\": " << (diff_count == 0 ? "true" : "false") << ",\n";
    json << "    \"raw_diff_count\": " << diff_count << "\n";
    json << "  }";
}

void write_stats_json(std::ofstream &json, const char *prefix, const Stats &stats) {
    json << "  \"" << prefix << "\": {\n";
    json << "    \"mean_us\": " << stats.mean_us << ",\n";
    json << "    \"min_us\": " << stats.min_us << ",\n";
    json << "    \"p50_us\": " << stats.p50_us << ",\n";
    json << "    \"p90_us\": " << stats.p90_us << ",\n";
    json << "    \"max_us\": " << stats.max_us << "\n";
    json << "  }";
}

void run_pair(engine::kind engine_kind) {
    const std::filesystem::path gemm1_meta = env_string("ONEDNN_GEMM1_META");
    const std::filesystem::path gemm2_meta = env_string("ONEDNN_GEMM2_META");
    if (gemm1_meta.empty() || gemm2_meta.empty()) {
        throw std::runtime_error("ONEDNN_GEMM1_META and ONEDNN_GEMM2_META are required");
    }
    const int warmup = env_int("ONEDNN_PAIR_WARMUP", 20);
    const int iterations = env_int("ONEDNN_PAIR_ITERATIONS", 200);
    const std::string weight_format = env_string("ONEDNN_WEIGHT_FORMAT", "acb");
    const std::filesystem::path json_path = env_string(
            "ONEDNN_PAIR_JSON",
            (gemm1_meta.parent_path() / "resident_pair_result.json").string());
    const std::string route_counts_csv = env_string("ONEDNN_ROUTE_COUNTS_CSV");

    engine eng(engine_kind, 0);
    stream engine_stream(eng);

    ResidentCase gemm1(eng, gemm1_meta, weight_format);
    ResidentCase gemm2(eng, gemm2_meta, weight_format);

    for (int i = 0; i < warmup; ++i) {
        gemm1.execute(engine_stream);
        gemm2.execute(engine_stream);
        engine_stream.wait();
    }

    std::vector<double> pair_samples;
    pair_samples.reserve(iterations);
    for (int i = 0; i < iterations; ++i) {
        const auto start = std::chrono::steady_clock::now();
        gemm1.execute(engine_stream);
        gemm2.execute(engine_stream);
        engine_stream.wait();
        const auto end = std::chrono::steady_clock::now();
        pair_samples.push_back(std::chrono::duration<double, std::micro>(
                end - start).count());
    }

    gemm1.read_output();
    gemm2.read_output();
    const std::vector<uint8_t> base_gemm1_output = gemm1.output();
    const std::vector<uint8_t> base_gemm2_output = gemm2.output();
    const bool base_gemm1_equal =
            raw_diff_count(base_gemm1_output, gemm1.expected_output()) == 0;
    const bool base_gemm2_equal =
            raw_diff_count(base_gemm2_output, gemm2.expected_output()) == 0;
    const Stats pair_stats = summarize(pair_samples);

    std::vector<std::vector<int32_t>> route_windows;
    if (!route_counts_csv.empty()) {
        if (gemm1.meta().num_experts != gemm2.meta().num_experts
                || gemm1.meta().total_tokens != gemm2.meta().total_tokens) {
            throw std::runtime_error(
                    "route-window mode requires matching expert/token counts");
        }
        route_windows = load_count_windows(route_counts_csv, gemm1.meta().num_experts,
                gemm1.meta().total_tokens);
    }

    Stats route_pair_stats;
    double route_gemm1_checksum = 0.0;
    double route_gemm2_checksum = 0.0;
    uint64_t route_gemm1_diff_count = 0;
    uint64_t route_gemm2_diff_count = 0;
    bool have_route_stats = false;
    if (!route_windows.empty()) {
        for (int i = 0; i < warmup; ++i) {
            const auto &counts = route_windows[static_cast<size_t>(i) % route_windows.size()];
            gemm1.update_counts(counts);
            gemm2.update_counts(counts);
            gemm1.execute(engine_stream);
            gemm2.execute(engine_stream);
            engine_stream.wait();
        }

        std::vector<double> route_pair_samples;
        route_pair_samples.reserve(iterations);
        for (int i = 0; i < iterations; ++i) {
            const auto &counts = route_windows[static_cast<size_t>(i) % route_windows.size()];
            const auto start = std::chrono::steady_clock::now();
            gemm1.update_counts(counts);
            gemm2.update_counts(counts);
            gemm1.execute(engine_stream);
            gemm2.execute(engine_stream);
            engine_stream.wait();
            const auto end = std::chrono::steady_clock::now();
            route_pair_samples.push_back(std::chrono::duration<double, std::micro>(
                    end - start).count());
        }
        gemm1.read_output();
        gemm2.read_output();
        route_pair_stats = summarize(route_pair_samples);
        route_gemm1_checksum = raw_checksum(gemm1.output(), gemm1.dst_dtype());
        route_gemm2_checksum = raw_checksum(gemm2.output(), gemm2.dst_dtype());
        route_gemm1_diff_count = raw_diff_count(gemm1.output(), gemm1.expected_output());
        route_gemm2_diff_count = raw_diff_count(gemm2.output(), gemm2.expected_output());
        have_route_stats = true;
    }

    std::ofstream json(json_path);
    if (!json) throw std::runtime_error("failed to open json: " + json_path.string());
    json << std::fixed << std::setprecision(6);
    json << "{\n";
    json << "  \"kind\": \"resident_onednn_two_gemm_pair\",\n";
    json << "  \"warmup\": " << warmup << ",\n";
    json << "  \"iterations\": " << iterations << ",\n";
    json << "  \"pair_mean_us\": " << pair_stats.mean_us << ",\n";
    json << "  \"pair_min_us\": " << pair_stats.min_us << ",\n";
    json << "  \"pair_p50_us\": " << pair_stats.p50_us << ",\n";
    json << "  \"pair_p90_us\": " << pair_stats.p90_us << ",\n";
    json << "  \"pair_max_us\": " << pair_stats.max_us << ",\n";
    json << "  \"pair_construct_us\": "
         << (gemm1.construct_us() + gemm2.construct_us()) << ",\n";
    json << "  \"route_counts_csv\": \"" << json_escape(route_counts_csv) << "\",\n";
    json << "  \"route_window_count\": " << route_windows.size() << ",\n";
    write_case_json(json, "gemm1", gemm1, base_gemm1_output);
    json << ",\n";
    write_case_json(json, "gemm2", gemm2, base_gemm2_output);
    if (have_route_stats) {
        json << ",\n";
        write_stats_json(json, "route_pair", route_pair_stats);
        json << ",\n";
        json << "  \"route_outputs\": {\n";
        json << "    \"gemm1_raw_checksum\": " << route_gemm1_checksum << ",\n";
        json << "    \"gemm2_raw_checksum\": " << route_gemm2_checksum << ",\n";
        json << "    \"gemm1_diff_vs_base_expected_count\": "
             << route_gemm1_diff_count << ",\n";
        json << "    \"gemm2_diff_vs_base_expected_count\": "
             << route_gemm2_diff_count << "\n";
        json << "  }";
    }
    json << "\n}\n";

    std::cout << "ONEDNN_RESIDENT_PAIR p50_us=" << pair_stats.p50_us
              << " mean_us=" << pair_stats.mean_us
              << " gemm1_equal=" << base_gemm1_equal
              << " gemm2_equal=" << base_gemm2_equal
              << " route_windows=" << route_windows.size();
    if (have_route_stats) {
        std::cout << " route_pair_p50_us=" << route_pair_stats.p50_us
                  << " route_pair_mean_us=" << route_pair_stats.mean_us;
    }
    std::cout << " json=" << json_path << std::endl;
}

} // namespace

int main(int argc, char **argv) {
    engine::kind engine_kind = parse_engine_kind(argc, argv);
    return handle_example_errors(run_pair, engine_kind);
}
