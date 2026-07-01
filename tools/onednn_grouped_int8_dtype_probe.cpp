#include <chrono>
#include <cstdint>
#include <iostream>
#include <numeric>
#include <string>
#include <vector>

#include "example_utils.hpp"
#include "oneapi/dnnl/dnnl.hpp"

using namespace dnnl;

namespace {

const char *dt_name(memory::data_type dt) {
    switch (dt) {
    case memory::data_type::f32: return "f32";
    case memory::data_type::bf16: return "bf16";
    case memory::data_type::s8: return "s8";
    case memory::data_type::u8: return "u8";
    default: return "other";
    }
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

std::vector<uint8_t> make_buffer(size_t elements, memory::data_type dt) {
    std::vector<uint8_t> out(elements * dt_size(dt), 0);
    if (dt == memory::data_type::f32) {
        auto *ptr = reinterpret_cast<float *>(out.data());
        for (size_t i = 0; i < elements; ++i) ptr[i] = float((i % 23) - 11) / 8.0f;
    } else if (dt == memory::data_type::bf16) {
        auto *ptr = reinterpret_cast<uint16_t *>(out.data());
        for (size_t i = 0; i < elements; ++i) ptr[i] = uint16_t(0x3f80 + (i % 7));
    } else if (dt == memory::data_type::s8) {
        auto *ptr = reinterpret_cast<int8_t *>(out.data());
        for (size_t i = 0; i < elements; ++i) ptr[i] = int8_t((int(i % 31) - 15));
    } else if (dt == memory::data_type::u8) {
        auto *ptr = reinterpret_cast<uint8_t *>(out.data());
        for (size_t i = 0; i < elements; ++i) ptr[i] = uint8_t((i % 31) + 1);
    }
    return out;
}

bool run_case(engine &eng, stream &engine_stream, const std::string &name,
        memory::data_type src_dt, memory::data_type wei_dt,
        memory::data_type dst_dt, const std::vector<int32_t> &tokens_per_expert,
        memory::dim k_dim, memory::dim n_dim) {
    const memory::dim num_experts = memory::dim(tokens_per_expert.size());
    std::vector<int32_t> offsets(num_experts);
    offsets[0] = tokens_per_expert[0];
    for (memory::dim i = 1; i < num_experts; ++i) {
        offsets[i] = offsets[i - 1] + tokens_per_expert[i];
    }
    const memory::dim total_tokens = std::accumulate(
            tokens_per_expert.begin(), tokens_per_expert.end(), memory::dim(0));

    memory::dims src_dims = {total_tokens, k_dim};
    memory::dims weights_dims = {num_experts, k_dim, n_dim};
    memory::dims dst_dims = {total_tokens, n_dim};

    auto src_md = memory::desc::grouped(src_dims, src_dt, 0, num_experts);
    auto dst_md = memory::desc::grouped(dst_dims, dst_dt, 0, num_experts);
    auto weights_md = memory::desc(weights_dims, wei_dt, memory::format_tag::acb);

    primitive_attr attr;
    attr.set_scales_mask(DNNL_ARG_SRC, 1 << 0);
    attr.set_scales_mask(DNNL_ARG_WEIGHTS, (1 << 0) | (1 << 2));

    try {
        const auto create_start = std::chrono::steady_clock::now();
        auto pd = matmul::primitive_desc(eng, src_md, weights_md, dst_md, attr);
        auto prim = matmul(pd);
        const auto create_end = std::chrono::steady_clock::now();

        auto src_mem = memory(src_md, eng);
        auto dst_mem = memory(dst_md, eng);
        auto weights_mem = memory(weights_md, eng);

        auto src_data = make_buffer(total_tokens * k_dim, src_dt);
        auto wei_data = make_buffer(num_experts * n_dim * k_dim, wei_dt);
        auto dst_data = make_buffer(total_tokens * n_dim, dst_dt);

        write_to_dnnl_memory(src_data.data(), src_mem);
        write_to_dnnl_memory(wei_data.data(), weights_mem);
        write_to_dnnl_memory(dst_data.data(), dst_mem);
        write_to_dnnl_memory(offsets.data(), src_mem, 1);
        write_to_dnnl_memory(offsets.data(), dst_mem, 1);

        std::vector<float> src_scales(total_tokens);
        for (int32_t i = 0; i < total_tokens; ++i)
            src_scales[i] = 0.01f + float(i % 17) * 0.001f;
        auto src_scales_md = memory::desc(
                {total_tokens}, memory::data_type::f32, memory::format_tag::a);
        auto src_scales_mem = memory(src_scales_md, eng);
        write_to_dnnl_memory(src_scales.data(), src_scales_mem);

        std::vector<float> wei_scales(num_experts * n_dim);
        for (int32_t i = 0; i < num_experts * n_dim; ++i)
            wei_scales[i] = 0.02f + float(i % 31) * 0.0005f;
        auto wei_scales_md = memory::desc(
                {num_experts, n_dim}, memory::data_type::f32, memory::format_tag::ab);
        auto wei_scales_mem = memory(wei_scales_md, eng);
        write_to_dnnl_memory(wei_scales.data(), wei_scales_mem);

        const auto exec_start = std::chrono::steady_clock::now();
        prim.execute(engine_stream,
                {{DNNL_ARG_SRC, src_mem},
                        {DNNL_ARG_WEIGHTS, weights_mem},
                        {DNNL_ARG_DST, dst_mem},
                        {DNNL_ARG_ATTR_SCALES | DNNL_ARG_SRC, src_scales_mem},
                        {DNNL_ARG_ATTR_SCALES | DNNL_ARG_WEIGHTS, wei_scales_mem}});
        engine_stream.wait();
        const auto exec_end = std::chrono::steady_clock::now();

        const auto create_us = std::chrono::duration_cast<std::chrono::microseconds>(
                create_end - create_start).count();
        const auto exec_us = std::chrono::duration_cast<std::chrono::microseconds>(
                exec_end - exec_start).count();
        std::cout << "PASS " << name << " src=" << dt_name(src_dt)
                  << " wei=" << dt_name(wei_dt) << " dst=" << dt_name(dst_dt)
                  << " experts=" << num_experts << " tokens=" << total_tokens
                  << " K=" << k_dim << " N=" << n_dim
                  << " create_us=" << create_us << " exec_wait_us=" << exec_us
                  << std::endl;
        return true;
    } catch (const dnnl::error &e) {
        std::cout << "FAIL " << name << " src=" << dt_name(src_dt)
                  << " wei=" << dt_name(wei_dt) << " dst=" << dt_name(dst_dt)
                  << " experts=" << num_experts << " K=" << k_dim
                  << " N=" << n_dim
                  << " status=" << dnnl_status2str(e.status)
                  << " message=" << e.what() << std::endl;
        return false;
    }
}

void probe(engine::kind engine_kind) {
    engine eng(engine_kind, 0);
    stream engine_stream(eng);

    int pass_count = 0;
    int fail_count = 0;
    auto record = [&](bool ok) {
        if (ok) ++pass_count;
        else ++fail_count;
    };

    const std::vector<int32_t> small_counts = {12, 8, 0, 10};
    std::vector<int32_t> qwen_l9_counts(256, 0);
    for (int expert : {59, 2, 243, 161, 255, 170, 200, 36})
        qwen_l9_counts[expert] = 1;

    record(run_case(eng, engine_stream, "control_f32", memory::data_type::f32,
            memory::data_type::f32, memory::data_type::f32, small_counts, 64,
            128));
    record(run_case(eng, engine_stream, "qwen_like_s8s8_f32",
            memory::data_type::s8, memory::data_type::s8,
            memory::data_type::f32, small_counts, 64, 128));
    record(run_case(eng, engine_stream, "u8s8_f32", memory::data_type::u8,
            memory::data_type::s8, memory::data_type::f32, small_counts, 64,
            128));
    record(run_case(eng, engine_stream, "s8s8_bf16", memory::data_type::s8,
            memory::data_type::s8, memory::data_type::bf16, small_counts, 64,
            128));
    record(run_case(eng, engine_stream, "qwen_l9_gemm1_s8s8_f32",
            memory::data_type::s8, memory::data_type::s8,
            memory::data_type::f32, qwen_l9_counts, 2048, 256));
    record(run_case(eng, engine_stream, "qwen_l9_gemm1_s8s8_bf16",
            memory::data_type::s8, memory::data_type::s8,
            memory::data_type::bf16, qwen_l9_counts, 2048, 256));
    record(run_case(eng, engine_stream, "qwen_l9_gemm2_s8s8_f32",
            memory::data_type::s8, memory::data_type::s8,
            memory::data_type::f32, qwen_l9_counts, 128, 2048));
    record(run_case(eng, engine_stream, "qwen_l9_gemm2_s8s8_bf16",
            memory::data_type::s8, memory::data_type::s8,
            memory::data_type::bf16, qwen_l9_counts, 128, 2048));

    std::cout << "SUMMARY pass=" << pass_count << " fail=" << fail_count
              << std::endl;
}

} // namespace

int main(int argc, char **argv) {
    engine::kind engine_kind = parse_engine_kind(argc, argv);
    return handle_example_errors(probe, engine_kind);
}
