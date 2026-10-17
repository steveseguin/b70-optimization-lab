#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet79-draft-rank0/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet79-draft-rank0/runtime_kernels.cpp"
#ifndef OWN_RT_HOST_ONLY
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet79-draft-rank0/build/checked/experiments/own-xpu-runtime/stage2/packet79-draft-rank0/prepared_submission.hpp"
#endif
#line 1
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet79-draft-rank0/build/checked/experiments/own-xpu-runtime/stage2/packet79-draft-rank0/runtime_kernels.hpp"
#ifndef OWN_RT_HOST_ONLY
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet79-draft-rank0/build/checked/experiments/own-xpu-runtime/stage1/packet3-prep/src/sycl_operation.hpp"
#endif
namespace iq3 {
#ifdef OWN_RT_HOST_ONLY
struct Step final : integrated::HostOperation {
  integrated::Spec spec;
  explicit Step(integrated::Spec s) : spec(s) {}
  void run(std::span<void *const> p) const override {
    integrated::evaluate(spec, p.data());
  }
};
#else
struct Step final : ownrt::SyclOperation {
  integrated::Spec spec;
  explicit Step(integrated::Spec s) : spec(s) {}
  sycl::event submit(sycl::queue &q, std::span<void *const> p,
                     const std::vector<sycl::event> &deps) const override {
    std::array<void *, 32> ptr{};
    std::copy(p.begin(), p.end(), ptr.begin());
    auto s = spec;
    return ownrt::prepared_submit(q,[=](sycl::handler& h) {
      
      h.single_task(packet26::checked([=] { integrated::evaluate(s, ptr.data()); }));
    });
  }
};
#endif
ownrt::Event step_operator(ownrt::Device &d, const integrated::Spec &s,
                           std::span<const ownrt::Allocation> a) {
  if (a.size() > 32 || s.ni > 10 || s.no > 6 || s.nw > 4)
    throw std::invalid_argument("kernel bindings");
  Step op(s);
  return d.compute(op, a, {});
}
} // namespace iq3
