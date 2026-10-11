#include "state.hpp"
#ifndef OWN_RT_HOST_ONLY
#include "sycl_operation.hpp"
#endif
namespace tp2 {
#ifdef OWN_RT_HOST_ONLY
struct Step final : integrated::HostOperation {
  integrated::Spec spec;
  int rank;
  explicit Step(integrated::Spec s,int r) : spec(s),rank(r) {}
  void run(std::span<void *const> p) const override {
    evaluate_state(spec, p.data(),rank);
  }
};
#else
struct Step final : ownrt::SyclOperation {
  integrated::Spec spec;
  int rank;
  explicit Step(integrated::Spec s,int r) : spec(s),rank(r) {}
  sycl::event submit(sycl::queue &q, std::span<void *const> p,
                     const std::vector<sycl::event> &deps) const override {
    std::array<void *, 32> ptr{};
    std::copy(p.begin(), p.end(), ptr.begin());
    auto s = spec;auto r=rank;
    return q.submit([&](sycl::handler &h) {
      h.depends_on(deps);
      h.single_task([=] { evaluate_state(s, ptr.data(),r); });
    });
  }
};
#endif
ownrt::Event state_operator(ownrt::Device &d, const integrated::Spec &s,
                           std::span<const ownrt::Allocation> a,int rank) {
  if (a.size() > 32 || s.ni > 10 || s.no > 6 || s.nw > 4)
    throw std::invalid_argument("kernel bindings");
  Step op(s,rank);
  return d.compute(op, a, {});
}
} // namespace iq3
