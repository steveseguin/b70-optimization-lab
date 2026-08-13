#include <sycl/sycl.hpp>
#include <oneapi/dnnl/dnnl.hpp>
#include <oneapi/dnnl/dnnl_sycl.hpp>

#include <algorithm>
#include <chrono>
#include <cstdint>
#include <cstring>
#include <iomanip>
#include <iostream>
#include <optional>
#include <stdexcept>
#include <unordered_map>
#include <vector>

using bf16 = sycl::ext::oneapi::bfloat16;

namespace {

uint32_t xorshift32(uint32_t & state) {
    state ^= state << 13;
    state ^= state >> 17;
    state ^= state << 5;
    return state;
}

float signed_unit(uint32_t & state) {
    return float(int(xorshift32(state) & 0xffffu) - 32768) / 32768.0f;
}

uint32_t bits(float value) {
    uint32_t result;
    std::memcpy(&result, &value, sizeof(result));
    return result;
}

uint64_t output_hash(const std::vector<float> & values) {
    uint64_t hash = 1469598103934665603ull;
    for (const float value : values) {
        const uint32_t word = bits(value);
        for (int shift = 0; shift < 32; shift += 8) {
            hash ^= (word >> shift) & 0xffu;
            hash *= 1099511628211ull;
        }
    }
    return hash;
}

struct MatmulPath {
    dnnl::matmul primitive;
    std::unordered_map<int, dnnl::memory> args;
    void * scratch = nullptr;
};

MatmulPath make_path(
        const dnnl::engine & engine,
        void * src,
        const dnnl::memory::desc & src_md,
        void * weights,
        const dnnl::memory::desc & weights_md,
        void * dst,
        const dnnl::memory::desc & dst_md,
        sycl::queue & queue) {
    dnnl::primitive_attr attr;
    attr.set_scratchpad_mode(dnnl::scratchpad_mode::user);
    auto pd = dnnl::matmul::primitive_desc(engine, src_md, weights_md, dst_md, attr);
    void * scratch = nullptr;
    if (pd.scratchpad_desc().get_size() != 0) {
        scratch = sycl::malloc_device<uint8_t>(pd.scratchpad_desc().get_size(), queue);
        if (!scratch) {
            throw std::runtime_error("scratchpad allocation failed");
        }
    }
    return {
        dnnl::matmul(pd),
        {
            {DNNL_ARG_SRC, dnnl::memory(src_md, engine, src)},
            {DNNL_ARG_WEIGHTS, dnnl::memory(weights_md, engine, weights)},
            {DNNL_ARG_DST, dnnl::memory(pd.dst_desc(), engine, dst)},
            {DNNL_ARG_SCRATCHPAD, dnnl::memory(pd.scratchpad_desc(), engine, scratch)},
        },
        scratch,
    };
}

sycl::event execute(
        const MatmulPath & path,
        const dnnl::stream & stream,
        const std::vector<sycl::event> & deps = {}) {
    return dnnl::sycl_interop::execute(path.primitive, stream, path.args, deps);
}

struct TimedResult {
    double before_ms;
    double candidate_ms;
    double after_ms;
};

} // namespace

int main(int argc, char ** argv) {
    const int iterations = argc > 1 ? std::stoi(argv[1]) : 500;
    const int warmups = 24;
    constexpr int m = 2048;
    constexpr int mh = 1024;
    constexpr int n = 16;
    constexpr int k = 6656;
    if (iterations <= 0) {
        throw std::invalid_argument("iterations must be positive");
    }

    const auto devices = sycl::device::get_devices(sycl::info::device_type::gpu);
    if (devices.size() < 2) {
        throw std::runtime_error("two SYCL GPUs are required");
    }
    sycl::device owner_device = devices[0];
    sycl::device helper_device = devices[1];
    sycl::queue owner(owner_device,
        sycl::property_list{sycl::property::queue::in_order{}});
    sycl::queue helper(helper_device,
        sycl::property_list{sycl::property::queue::in_order{}});
    if (!owner_device.ext_oneapi_can_access_peer(
            helper_device, sycl::ext::oneapi::peer_access::access_supported) ||
        !helper_device.ext_oneapi_can_access_peer(
            owner_device, sycl::ext::oneapi::peer_access::access_supported)) {
        throw std::runtime_error("bidirectional peer access is unavailable");
    }
    owner_device.ext_oneapi_enable_peer_access(helper_device);
    helper_device.ext_oneapi_enable_peer_access(owner_device);

    std::cout << "owner=" << owner_device.get_info<sycl::info::device::name>()
              << " helper=" << helper_device.get_info<sycl::info::device::name>()
              << " shape=" << m << "x" << n << "x" << k
              << " iterations=" << iterations << '\n';

    uint32_t rng = 0x51474154u;
    std::vector<bf16> host_q(size_t(m) * k);
    std::vector<bf16> host_gate(size_t(m) * k);
    std::vector<bf16> host_activation(size_t(n) * k);
    for (auto & value : host_q) {
        value = bf16(signed_unit(rng) * 0.03125f);
    }
    for (auto & value : host_gate) {
        value = bf16(signed_unit(rng) * 0.03125f);
    }
    for (auto & value : host_activation) {
        value = bf16(signed_unit(rng) * 0.125f);
    }

    auto * q_full = sycl::malloc_device<bf16>(host_q.size(), owner);
    auto * gate_full = sycl::malloc_device<bf16>(host_gate.size(), owner);
    auto * q_owner = sycl::malloc_device<bf16>(size_t(mh) * k, owner);
    auto * gate_owner = sycl::malloc_device<bf16>(size_t(mh) * k, owner);
    auto * q_helper = sycl::malloc_device<bf16>(size_t(mh) * k, helper);
    auto * gate_helper = sycl::malloc_device<bf16>(size_t(mh) * k, helper);
    auto * activation_owner = sycl::malloc_device<bf16>(host_activation.size(), owner);
    auto * activation_helper = sycl::malloc_device<bf16>(host_activation.size(), helper);
    auto * ref_q = sycl::malloc_device<float>(size_t(m) * n, owner);
    auto * ref_gate = sycl::malloc_device<float>(size_t(m) * n, owner);
    auto * split_q = sycl::malloc_device<float>(size_t(m) * n, owner);
    auto * split_gate = sycl::malloc_device<float>(size_t(m) * n, owner);
    auto * helper_q = sycl::malloc_device<float>(size_t(mh) * n, helper);
    auto * helper_gate = sycl::malloc_device<float>(size_t(mh) * n, helper);
    if (!q_full || !gate_full || !q_owner || !gate_owner || !q_helper ||
            !gate_helper || !activation_owner || !activation_helper || !ref_q ||
            !ref_gate || !split_q || !split_gate || !helper_q || !helper_gate) {
        throw std::runtime_error("USM allocation failed");
    }

    owner.copy(host_q.data(), q_full, host_q.size());
    owner.copy(host_gate.data(), gate_full, host_gate.size());
    owner.copy(host_q.data(), q_owner, size_t(mh) * k);
    owner.copy(host_gate.data(), gate_owner, size_t(mh) * k);
    owner.copy(host_activation.data(), activation_owner, host_activation.size());
    helper.copy(host_q.data() + size_t(mh) * k, q_helper, size_t(mh) * k);
    helper.copy(host_gate.data() + size_t(mh) * k, gate_helper, size_t(mh) * k);
    helper.copy(host_activation.data(), activation_helper, host_activation.size());
    owner.wait_and_throw();
    helper.wait_and_throw();

    const auto owner_engine = dnnl::sycl_interop::make_engine(
        owner.get_device(), owner.get_context());
    const auto helper_engine = dnnl::sycl_interop::make_engine(
        helper.get_device(), helper.get_context());
    const auto owner_stream = dnnl::sycl_interop::make_stream(owner_engine, owner);
    const auto helper_stream = dnnl::sycl_interop::make_stream(helper_engine, helper);
    using dt = dnnl::memory::data_type;

    const auto full_src_md = dnnl::memory::desc(
        {1, m, k}, dt::bf16, {int64_t(m) * k, k, 1});
    const auto half_src_md = dnnl::memory::desc(
        {1, mh, k}, dt::bf16, {int64_t(mh) * k, k, 1});
    const auto activation_md = dnnl::memory::desc(
        {1, k, n}, dt::bf16, {int64_t(k) * n, 1, k});
    const auto full_dst_md = dnnl::memory::desc(
        {1, m, n}, dt::f32, {int64_t(m) * n, 1, m});
    const auto owner_half_dst_md = dnnl::memory::desc(
        {1, mh, n}, dt::f32, {int64_t(m) * n, 1, m});
    const auto packed_half_dst_md = dnnl::memory::desc(
        {1, mh, n}, dt::f32, {int64_t(mh) * n, 1, mh});

    auto ref_q_path = make_path(owner_engine, q_full, full_src_md,
        activation_owner, activation_md, ref_q, full_dst_md, owner);
    auto ref_gate_path = make_path(owner_engine, gate_full, full_src_md,
        activation_owner, activation_md, ref_gate, full_dst_md, owner);
    auto owner_q_path = make_path(owner_engine, q_owner, half_src_md,
        activation_owner, activation_md, split_q, owner_half_dst_md, owner);
    auto owner_gate_path = make_path(owner_engine, gate_owner, half_src_md,
        activation_owner, activation_md, split_gate, owner_half_dst_md, owner);
    auto helper_q_path = make_path(helper_engine, q_helper, half_src_md,
        activation_helper, activation_md, helper_q, packed_half_dst_md, helper);
    auto helper_gate_path = make_path(helper_engine, gate_helper, half_src_md,
        activation_helper, activation_md, helper_gate, packed_half_dst_md, helper);

    auto submit_ref = [&] {
        execute(ref_q_path, owner_stream);
        return execute(ref_gate_path, owner_stream);
    };
    std::optional<sycl::event> helper_release;
    auto submit_candidate = [&] {
        execute(owner_q_path, owner_stream);
        if (helper_release.has_value()) {
            execute(helper_q_path, helper_stream, {*helper_release});
        } else {
            execute(helper_q_path, helper_stream);
        }
        execute(owner_gate_path, owner_stream);
        const sycl::event helper_done = execute(helper_gate_path, helper_stream);
        const sycl::event scatter = owner.submit([&](sycl::handler & h) {
            h.depends_on(helper_done);
            h.parallel_for(sycl::range<1>(size_t(mh) * n), [=](sycl::id<1> idx) {
                const size_t linear = idx[0];
                const size_t token = linear / mh;
                const size_t row = linear - token * mh;
                split_q[token * m + mh + row] = helper_q[linear];
                split_gate[token * m + mh + row] = helper_gate[linear];
            });
        });
        // Carry the remote-read lifetime into the next helper GEMM instead of
        // appending a dedicated helper-queue barrier every layer. The next
        // helper Q cannot overwrite helper_q/helper_gate until the previous
        // owner scatter has completed both remote reads.
        helper_release = scatter;
        return scatter;
    };

    for (int i = 0; i < warmups; ++i) {
        submit_ref();
        submit_candidate();
    }
    owner.wait_and_throw();
    helper.wait_and_throw();

    submit_ref();
    owner.wait_and_throw();
    submit_candidate();
    owner.wait_and_throw();
    helper.wait_and_throw();
    std::vector<float> host_ref_q(size_t(m) * n);
    std::vector<float> host_ref_gate(size_t(m) * n);
    std::vector<float> host_split_q(size_t(m) * n);
    std::vector<float> host_split_gate(size_t(m) * n);
    owner.copy(ref_q, host_ref_q.data(), host_ref_q.size());
    owner.copy(ref_gate, host_ref_gate.data(), host_ref_gate.size());
    owner.copy(split_q, host_split_q.data(), host_split_q.size());
    owner.copy(split_gate, host_split_gate.data(), host_split_gate.size());
    owner.wait_and_throw();

    size_t q_mismatches = 0;
    size_t gate_mismatches = 0;
    for (size_t i = 0; i < host_ref_q.size(); ++i) {
        q_mismatches += bits(host_ref_q[i]) != bits(host_split_q[i]);
        gate_mismatches += bits(host_ref_gate[i]) != bits(host_split_gate[i]);
    }

    auto time_ref = [&] {
        const auto start = std::chrono::steady_clock::now();
        for (int i = 0; i < iterations; ++i) {
            submit_ref();
        }
        owner.wait_and_throw();
        const auto end = std::chrono::steady_clock::now();
        return std::chrono::duration<double, std::milli>(end - start).count() / iterations;
    };
    auto time_candidate = [&] {
        const auto start = std::chrono::steady_clock::now();
        for (int i = 0; i < iterations; ++i) {
            submit_candidate();
        }
        owner.wait_and_throw();
        helper.wait_and_throw();
        const auto end = std::chrono::steady_clock::now();
        return std::chrono::duration<double, std::milli>(end - start).count() / iterations;
    };

    const double before_ms = time_ref();
    const double candidate_ms = time_candidate();
    const double after_ms = time_ref();
    const double pooled_ref_ms = 0.5 * (before_ms + after_ms);
    const double saved_ms = pooled_ref_ms - candidate_ms;
    const bool exact = q_mismatches == 0 && gate_mismatches == 0;
    const bool speed_gate = saved_ms >= 0.040;
    std::cout << std::fixed << std::setprecision(6)
              << "ref_before_ms=" << before_ms
              << " candidate_ms=" << candidate_ms
              << " ref_after_ms=" << after_ms
              << " pooled_ref_ms=" << pooled_ref_ms
              << " saved_ms=" << saved_ms
              << " candidate_over_ref=" << (candidate_ms / pooled_ref_ms)
              << " q_mismatches=" << q_mismatches
              << " gate_mismatches=" << gate_mismatches
              << " ref_q_hash=0x" << std::hex << output_hash(host_ref_q)
              << " split_q_hash=0x" << output_hash(host_split_q)
              << " ref_gate_hash=0x" << output_hash(host_ref_gate)
              << " split_gate_hash=0x" << output_hash(host_split_gate)
              << std::dec << '\n';
    std::cout << "exact_gate=" << (exact ? "PASS" : "FAIL")
              << " speed_gate=" << (speed_gate ? "PASS" : "FAIL") << '\n';

    helper.wait_and_throw();
    owner.wait_and_throw();
    sycl::free(helper_gate_path.scratch, helper);
    sycl::free(helper_q_path.scratch, helper);
    sycl::free(owner_gate_path.scratch, owner);
    sycl::free(owner_q_path.scratch, owner);
    sycl::free(ref_gate_path.scratch, owner);
    sycl::free(ref_q_path.scratch, owner);
    sycl::free(helper_gate, helper);
    sycl::free(helper_q, helper);
    sycl::free(split_gate, owner);
    sycl::free(split_q, owner);
    sycl::free(ref_gate, owner);
    sycl::free(ref_q, owner);
    sycl::free(activation_helper, helper);
    sycl::free(activation_owner, owner);
    sycl::free(gate_helper, helper);
    sycl::free(q_helper, helper);
    sycl::free(gate_owner, owner);
    sycl::free(q_owner, owner);
    sycl::free(gate_full, owner);
    sycl::free(q_full, owner);

    return exact && speed_gate ? 0 : 2;
}
