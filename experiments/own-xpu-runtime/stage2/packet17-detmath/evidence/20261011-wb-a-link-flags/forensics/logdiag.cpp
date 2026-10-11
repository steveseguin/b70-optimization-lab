// Coordinator diagnostic, 2026-10-11: localize the W-B log-v2 host/device mismatch.
// One tiny kernel per range on one card; bounded wait; no retry.
#include <sycl/sycl.hpp>
#include "detmath.hpp"
#include <chrono>
#include <cstdio>
#include <thread>
#include <vector>
struct Row { uint32_t y, zhi, zlo, qa, qb; };
static Row eval(uint32_t u) {
  using namespace detmath;
  float x = value(u);
  Row r{};
  r.y = bits(detmath::log(x));
  uint32_t a = u & 0x7fffffff;
  float m = value((a & 0x7fffff) | 0x3f800000);
  if (m > 0x1.6a09e6p+0f) m = m * 0.5f;
  Pair den = sum(m, 1.f);
  Pair z = quotient({m - 1.f, 0}, den);
  r.zhi = bits(z.hi); r.zlo = bits(z.lo);
  r.qa = bits(div(m - 1.f, den.hi));           // first quotient only
  r.qb = bits(fma(m - 1.f, 2.f, -(m - 1.f)));  // an fma with a negated addend
  return r;
}
struct Z { uint32_t v[8]; };
static Z zeros(float pz, float nz, float two) {  // runtime +0, -0, 2 so nothing folds
  using namespace detmath;
  Z z{};
  z.v[0] = bits(pz + nz);            // +0
  z.v[1] = bits(fma(pz, two, nz));   // +0
  z.v[2] = bits(-pz);                // -0
  z.v[3] = bits(nz - pz);            // -0
  z.v[4] = bits(fma(pz, -two, pz));  // (-0)+(+0) = +0
  z.v[5] = bits(pz / two);           // +0
  z.v[6] = bits(nz + nz);            // -0
  z.v[7] = bits(pz - pz);            // +0
  return z;
}
int main(int argc, char** argv) {
  int card = argc > 1 ? std::atoi(argv[1]) : 3;
  std::vector<sycl::device> devices;
  for (const auto& p : sycl::platform::get_platforms())
    if (p.get_backend() == sycl::backend::ext_oneapi_level_zero)
      for (const auto& d : p.get_devices(sycl::info::device_type::gpu)) devices.push_back(d);
  if (card < 0 || size_t(card) >= devices.size()) { std::puts("card index"); return 2; }
  sycl::queue q(devices[card]);
  std::printf("device %s card %d\n", devices[card].get_info<sycl::info::device::name>().c_str(), card);
  auto wait = [&](sycl::event e) {
    auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(20);
    while (e.get_info<sycl::info::event::command_execution_status>() != sycl::info::event_command_status::complete) {
      if (std::chrono::steady_clock::now() > deadline) { std::puts("deadline"); std::quick_exit(3); }
      std::this_thread::sleep_for(std::chrono::milliseconds(1));
    }
  };
  const uint32_t n = 262144;
  Row* out = sycl::malloc_shared<Row>(n, q);
  float* in = sycl::malloc_shared<float>(3, q);
  Z* zo = sycl::malloc_shared<Z>(1, q);
  in[0] = 0.f; in[1] = -0.f; in[2] = 2.f;
  wait(q.single_task([=] { zo[0] = zeros(in[0], in[1], in[2]); }));
  volatile float pz = 0.f, nz = -0.f, two = 2.f;
  Z hz = zeros(pz, nz, two);
  for (int i = 0; i < 8; ++i) std::printf("zero-probe %d host %08x device %08x%s\n", i, hz.v[i], zo->v[i], hz.v[i] == zo->v[i] ? "" : "  <-- differs");
  for (uint32_t start : {0x3f7c0000u, 0x3f800000u, 0x3f840000u, 0x3eb00000u, 0x00000000u, 0x00800000u}) {
    wait(q.parallel_for(sycl::range<1>(n), [=](sycl::id<1> i) { out[i[0]] = eval(start + uint32_t(i[0])); }));
    uint32_t bad = 0, shown = 0, badz = 0, badq = 0, badf = 0;
    for (uint32_t i = 0; i < n; ++i) {
      Row h = eval(start + i), d = out[i];
      if (h.zhi != d.zhi || h.zlo != d.zlo) ++badz;
      if (h.qa != d.qa) ++badq;
      if (h.qb != d.qb) ++badf;
      if (h.y != d.y) {
        ++bad;
        if (shown++ < 6) std::printf("  x=%08x host y=%08x device y=%08x | z host %08x:%08x device %08x:%08x | q host %08x device %08x\n", start + i, h.y, d.y, h.zhi, h.zlo, d.zhi, d.zlo, h.qa, d.qa);
      }
    }
    std::printf("range %08x +%u: log differs %u, z differs %u, first-quotient differs %u, fma-probe differs %u\n", start, n, bad, badz, badq, badf);
  }
  sycl::free(out, q); sycl::free(in, q); sycl::free(zo, q);
  return 0;
}
