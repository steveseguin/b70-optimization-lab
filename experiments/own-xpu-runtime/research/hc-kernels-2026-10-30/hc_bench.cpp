// HC kernel bench (2026-10-30): the engine's current HC kernels against exact candidates, on one B70, with the real
// SC117 HC weights (GGUF) and real activations (finish state dumps of the stage-overhead runs, both ranks).
//
// 1. Exactness, every HC block of both ranks (97: blk.0-47 hc.a / hc.f, rank 1's final):
//    - the engine kernel run here reproduces the engine's dumped outputs bit for bit (low, inject, gate);
//    - every candidate equals the engine kernel bit for bit (low + inject, final low, gate; norm outputs and the
//      norm's scratch partials, on two real inputs per block: the rank's streams and the block's norm vector).
// 2. Timing: per block the chain norm -> low(+inject) -> act -> gate in layer order with that block's own weights
//    (13.2 MB per block, cold), queued behind a busy kernel so the host is ahead; one configuration swaps one family's
//    kernel; configurations interleaved over rounds. Device event time per kernel, medians per site kind.
// Output: one JSON object on stdout.
#include <sycl/sycl.hpp>
#include <algorithm>
#include <chrono>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <functional>
#include <map>
#include <sstream>
#include <string>
#include <vector>
#include "hc_kernels.hpp"
#include "stage2/packet194-expert-diet-engine/hc_kernels.hpp"  // the shipped engine kernels (OWNRT_HC_KERNELS)

using u16 = std::uint16_t;
using u32 = std::uint32_t;
namespace dv2 = iq3::kopt::dense_v2;
#define SG32 [[sycl::reqd_sub_group_size(32)]]
#define SG16 [[sycl::reqd_sub_group_size(16)]]

// Engine guards, verbatim from specialised_submit.cpp (namespace specialised, device build)
struct Guard {
  int error(ng::Args a) const { return sycl::atomic_ref<int32_t, sycl::memory_order::relaxed, sycl::memory_scope::device, sycl::access::address_space::global_space>(a.i(15)[0]).load(); }
  void fail(ng::Args a) const { sycl::atomic_ref<int32_t, sycl::memory_order::relaxed, sycl::memory_scope::device, sycl::access::address_space::global_space>(a.i(15)[0]).store(1); }
};
struct CachedGuard {
  int value;
  int error(ng::Args) const { return value; }
  void fail(ng::Args a) const { Guard{}.fail(a); }
};

struct Block {
  int rank; std::string tag; bool inject;
  const uint8_t *low, *inj, *gate; const float *gain, *x_low, *x_gate, *ref_low, *ref_inj, *ref_gate, *streams, *branch, *cinj;
};
constexpr u32 H = 2560, K = 10240, L = 320, NI = 4;

// ---------------- kernel launchers ----------------
template <int I> class KN;
// low (+inject): engine bf16_multi<R,U> with a work-group size
template <unsigned R, unsigned U, unsigned WGS, int ID, bool STATIC = false>
sycl::event low_engine_form(sycl::queue& q, const Block& b, const float* x, float* yl, float* yi) {
  std::array<dv2::Mat, 4> m{};
  m[0] = dv2::Mat{b.low, x, yl, L, K, K * 2, 0};
  u32 count = 1, subs = (L + R - 1) / R;
  if (b.inject) { m[1] = dv2::Mat{b.inj, x, yi, NI, K, K * 2, subs}; subs += (NI + R - 1) / R; count = 2; }
  const size_t global = (size_t(subs) * 32 + WGS - 1) / WGS * WGS;
  return q.parallel_for<KN<ID>>(sycl::nd_range<1>(global, WGS), [=](sycl::nd_item<1> it) SG32 {
    if constexpr (STATIC) hck::bf16_multi_static<R, U>(m, count, it); else dv2::bf16_multi<R, U>(m, count, it); });
}
template <int ID>
sycl::event low_shipped(sycl::queue& q, const Block& b, const float* x, float* yl, float* yi) {  // dense_v2::bf16_multi_static<1,10>
  std::array<dv2::Mat, 4> m{};
  m[0] = dv2::Mat{b.low, x, yl, L, K, K * 2, 0};
  u32 count = 1, subs = L;
  if (b.inject) { m[1] = dv2::Mat{b.inj, x, yi, NI, K, K * 2, subs}; subs += NI; count = 2; }
  const size_t global = (size_t(subs) * 32 + 127) / 128 * 128;
  return q.parallel_for<KN<ID>>(sycl::nd_range<1>(global, 128), [=](sycl::nd_item<1> it) SG32 { dv2::bf16_multi_static<1, 10>(m, count, it); });
}
template <unsigned U, unsigned WGR, int ID>
sycl::event low_split(sycl::queue& q, const Block& b, const float* x, float* yl, float* yi) {
  std::array<dv2::Mat, 4> m{};
  m[0] = dv2::Mat{b.low, x, yl, L, K, K * 2, 0};
  u32 count = 1, total = L;
  if (b.inject) { m[1] = dv2::Mat{b.inj, x, yi, NI, K, K * 2, total}; total += NI; count = 2; }
  const size_t global = size_t((total + WGR - 1) / WGR) * WGR * 32;
  return q.parallel_for<KN<ID>>(sycl::nd_range<1>(global, WGR * 32), [=](sycl::nd_item<1> it) SG16 {
    float* xch = *sycl::ext::oneapi::group_local_memory_for_overwrite<float[WGR]>(it.get_group());
    dv2::bf16_split<U, WGR>(m, count, it, xch);
  });
}
template <unsigned U, unsigned D, int HINT, bool ALL, unsigned WGS, int ID>
sycl::event low_pf(sycl::queue& q, const Block& b, const float* x, float* yl, float* yi) {
  hck::Mat m0{b.low, x, yl, L, K, K * 2}, m1{b.inj, x, yi, NI, K, K * 2};
  const u32 count = b.inject ? 2 : 1, subs = L + (b.inject ? NI : 0);
  const size_t global = (size_t(subs) * 32 + WGS - 1) / WGS * WGS;
  return q.parallel_for<KN<ID>>(sycl::nd_range<1>(global, WGS), [=](sycl::nd_item<1> it) SG32 { hck::low_pair<U, D, HINT, ALL>(m0, m1, count, it); });
}
// gate
template <unsigned R, unsigned U, unsigned WGS, int ID, bool STATIC = false>
sycl::event gate_engine_form(sycl::queue& q, const Block& b, const float* x, float* y) {
  std::array<dv2::Mat, 4> m{};
  m[0] = dv2::Mat{b.gate, x, y, K, L, L * 2, 0};
  const u32 subs = (K + R - 1) / R;
  const size_t global = (size_t(subs) * 32 + WGS - 1) / WGS * WGS;
  return q.parallel_for<KN<ID>>(sycl::nd_range<1>(global, WGS), [=](sycl::nd_item<1> it) SG32 {
    if constexpr (STATIC) hck::bf16_multi_static<R, U>(m, 1, it); else dv2::bf16_multi<R, U>(m, 1, it); });
}
template <unsigned NR, int HINT, unsigned WGS, int ID>
sycl::event gate_rows(sycl::queue& q, const Block& b, const float* x, float* y) {
  const uint8_t* w = b.gate;
  const u32 subs = (K + NR - 1) / NR;
  const size_t global = (size_t(subs) * 32 + WGS - 1) / WGS * WGS;
  return q.parallel_for<KN<ID>>(sycl::nd_range<1>(global, WGS), [=](sycl::nd_item<1> it) SG32 {
    auto sg = it.get_sub_group();
    const u32 gsub = u32(it.get_group_linear_id()) * u32(it.get_local_range(0) / 32) + u32(sg.get_group_linear_id());
    hck::gate_rows<NR, HINT>(w, x, y, K, L, L * 2, sg, gsub);
  });
}
// norm: the engine's two launches (CachedGuard form, OWNRT_EXPERTS_V2 guard) and the one-launch candidate
struct NormIO { const float* x; const float* gain; float* y; float* scratch; int32_t* error; int32_t* position; int32_t* active; float* rope; };
template <int Stage>
sycl::event norm_engine_stage(sycl::queue& q, const NormIO& io) {
  ng::Shape s{}; s.op = ng::norm; s.tokens = 1; s.width = 2560; s.heads = 4; s.flags = 8 | ng::f32_activations_flag;
  s.capacity = 65536; s.extent = 0; s.budget = 2048;
  ng::Args a; a.p.fill(io.rope); a.p[0] = const_cast<float*>(io.x); a.p[1] = const_cast<float*>(io.gain); a.p[2] = io.y;
  a.p[15] = io.error; a.p[16] = io.rope; a.p[17] = io.position; a.p[18] = io.active; a.f32 = true;
  float* scratch = io.scratch;
  const size_t n = specialised::work_items(s, Stage);
  return q.parallel_for<KN<900 + Stage>>(sycl::nd_range<1>((n + 127) / 128 * 128, 128), [=](sycl::nd_item<1> it) SG32 {
    auto sg = it.get_sub_group();
    const int err = sycl::group_broadcast(sg, sg.get_local_linear_id() == 0 ? Guard{}.error(a) : 0, 0);
    specialised::body<ng::norm, Stage, 2560, 4>(s, a, it.get_global_linear_id(), scratch, CachedGuard{err});
  });
}
template <unsigned WGS, int ID, int V = 1>
sycl::event norm_one(sycl::queue& q, const NormIO& io) {
  hck::NormArgs a{io.x, io.gain, io.y, io.scratch, io.error, io.position, io.active, 65536, 1, 8};
  return q.submit([&](sycl::handler& h) {
    sycl::local_accessor<float, 1> part(96, h);
    h.parallel_for<KN<ID>>(sycl::nd_range<1>(4 * WGS, WGS), [=](sycl::nd_item<1> it) SG32 {
      if constexpr (V == 1) hck::norm_one<WGS>(a, it, part.get_multi_ptr<sycl::access::decorated::no>().get());
      else if constexpr (V == 2) hck::norm_one2<WGS>(a, it, part.get_multi_ptr<sycl::access::decorated::no>().get());
      else hck::norm_one3<WGS>(a, it, part.get_multi_ptr<sycl::access::decorated::no>().get());
    });
  });
}

// engine CombineFast (adapter.cpp), F32 guard form, verbatim arithmetic: 4 elements per item, 128-item groups
struct CombIO { float* streams; const float* branch; const float* cinj; int32_t* error; int32_t* active; };
static sycl::event combine_engine(sycl::queue& q, const CombIO& c) {
  const size_t n = K, w = H, quads = n / 4, total = quads;
  return q.parallel_for<KN<950>>(sycl::nd_range<1>((total + 127) / 128 * 128, 128), [=](sycl::nd_item<1> it) SG32 {
    auto sg = it.get_sub_group();
    auto failed = [&] { return sycl::atomic_ref<int32_t, sycl::memory_order::relaxed, sycl::memory_scope::device, sycl::access::address_space::global_space>(*c.error).load(); };
    if (sycl::group_broadcast(sg, sg.get_local_linear_id() == 0 ? int(!*c.active || failed()) : 0, 0)) return;
    const size_t i = it.get_global_linear_id();
    if (i >= total) return;
    const size_t cc = (i % quads) * 4;
    const float* stream = c.streams; const float* branch = c.branch; const float* inject = c.cinj; float* out = c.streams;
    const float gate = 2.f * ng::sigmoid(inject[cc / w] / 4.f);
    for (int j = 0; j < 4; ++j) out[cc + j] = stream[cc + j] + branch[(cc + j) % w] * gate;
  });
}
template <unsigned WGS, int ID>
sycl::event combine_norm_fused(sycl::queue& q, const CombIO& c, const NormIO& io) {
  hck::CNArgs a{c.streams, c.branch, c.cinj, io.gain, io.y, io.scratch, io.error, io.position, io.active, 65536, 1, 8};
  return q.submit([&](sycl::handler& h) {
    sycl::local_accessor<float, 1> part(96, h);
    h.parallel_for<KN<ID>>(sycl::nd_range<1>(4 * WGS, WGS), [=](sycl::nd_item<1> it) SG32 {
      hck::combine_norm_one<WGS>(a, it, part.get_multi_ptr<sycl::access::decorated::no>().get());
    });
  });
}
template <bool COMBINE, int ID>
sycl::event shipped_norm(sycl::queue& q, const CombIO* c, const NormIO& io) {  // hc_kernels::norm_row (engine header)
  hc_kernels::NormArgs a{const_cast<float*>(COMBINE ? c->streams : io.x), COMBINE ? c->branch : nullptr, COMBINE ? c->cinj : nullptr,
                         io.gain, io.y, io.scratch, io.error, io.position, io.active, 65536, 1, 8};
  return q.submit([&](sycl::handler& h) {
    sycl::local_accessor<float, 1> part(96, h);
    h.parallel_for<KN<ID>>(sycl::nd_range<1>(4 * hc_kernels::NORM_WGS, hc_kernels::NORM_WGS), [=](sycl::nd_item<1> it) SG32 {
      hc_kernels::norm_row<COMBINE>(a, it, part.get_multi_ptr<sycl::access::decorated::no>().get());
    });
  });
}
using CNFn = std::function<std::vector<sycl::event>(sycl::queue&, const CombIO&, const NormIO&)>;
struct CNV { std::string name; CNFn f; };

using LowFn = std::function<sycl::event(sycl::queue&, const Block&, const float*, float*, float*)>;
using GateFn = std::function<sycl::event(sycl::queue&, const Block&, const float*, float*)>;
using NormFn = std::function<std::vector<sycl::event>(sycl::queue&, const NormIO&)>;
struct LowV { std::string name; LowFn f; };
struct GateV { std::string name; GateFn f; };
struct NormV { std::string name; NormFn f; };

class ActName;
class BusyName;
class AluCtx;
class StreamCtx;
// Production-like context between HC blocks: ctx 1 = ALU-bound kernel on every thread (~100 us, like the routed
// experts), ctx 2 = a 96 MB weight-stream read (other layers' weights) plus a 2 MB write.
static sycl::event alu_ctx(sycl::queue& q, float* sink, u32 iters) {
  return q.parallel_for<AluCtx>(sycl::nd_range<1>(65536, 256), [=](sycl::nd_item<1> it) {
    float x = sink[1] + float(it.get_global_linear_id() & 15u);
    for (u32 i = 0; i < iters; ++i) x = x * 1.0000001f + 1e-7f;
    if (x == 12345.f) sink[2] = x;
  });
}
static sycl::event stream_ctx(sycl::queue& q, const sycl::vec<uint32_t, 4>* src, size_t n4, float* dst) {
  return q.parallel_for<StreamCtx>(sycl::nd_range<1>(65536, 256), [=](sycl::nd_item<1> it) {
    const size_t i0 = it.get_global_linear_id();
    uint32_t acc = 0;
    for (size_t i = i0; i < n4; i += 65536) { const auto v = src[i]; acc ^= v[0] ^ v[1] ^ v[2] ^ v[3]; }
    if (i0 < 524288) dst[i0] = float(acc);
  });
}
static sycl::event act_kernel(sycl::queue& q, const float* low, float* act) {
  return q.parallel_for<ActName>(sycl::nd_range<1>(3 * 128, 128), [=](sycl::nd_item<1> it) {
    const size_t i = it.get_global_linear_id();
    if (i < L) act[i] = detmath::silu_div4(low[i]);
  });
}
static sycl::event busy(sycl::queue& q, float* sink, u32 iters) {
  return q.single_task<BusyName>([=] {
    float x = sink[1];
    for (u32 i = 0; i < iters; ++i) x = x * 1.0000001f + float(i & 7u) * 1e-7f;
    sink[0] = x;
  });
}
static double ev_us(const sycl::event& e) {
  return double(e.get_profiling_info<sycl::info::event_profiling::command_end>() - e.get_profiling_info<sycl::info::event_profiling::command_start>()) / 1e3;
}
static double t_end(const sycl::event& e) { return double(e.get_profiling_info<sycl::info::event_profiling::command_end>()); }
static double t_start(const sycl::event& e) { return double(e.get_profiling_info<sycl::info::event_profiling::command_start>()); }
static double pct(std::vector<double> v, double p) {
  if (v.empty()) return 0;
  std::sort(v.begin(), v.end());
  return v[std::min(v.size() - 1, size_t(p * double(v.size() - 1) + 0.5))];
}

int main(int argc, char** argv) {
  const bool quick = argc > 1 && std::string(argv[1]) == "quick";
  const std::string dir = argc > 2 ? argv[2] : "/dev/shm/hc-kernels-2026-10-30/data";
  auto devs = sycl::device::get_devices(sycl::info::device_type::gpu);
  if (devs.size() != 1) { std::printf("{\"error\":\"expected one GPU, got %zu\"}\n", devs.size()); return 2; }
  sycl::queue q(devs[0], {sycl::property::queue::in_order{}, sycl::property::queue::enable_profiling{}});
  // data
  std::ifstream pf(dir + "/pack.bin", std::ios::binary | std::ios::ate);
  const size_t bytes = size_t(pf.tellg());
  pf.seekg(0);
  std::vector<char> host(bytes);
  pf.read(host.data(), bytes);
  uint8_t* dev = sycl::malloc_device<uint8_t>(bytes, q);
  q.memcpy(dev, host.data(), bytes).wait();
  std::vector<Block> blocks;
  {
    std::ifstream t(dir + "/pack.tsv");
    std::string line;
    while (std::getline(t, line)) {
      std::istringstream s(line);
      Block b; long long st, lo, in, ga, gn, xl, xg, rl, ri, rg, br, ci;
      s >> b.rank >> b.tag >> st >> lo >> in >> ga >> gn >> xl >> xg >> rl >> ri >> rg >> br >> ci;
      b.inject = in >= 0;
      auto P = [&](long long o) { return o < 0 ? nullptr : dev + o; };
      b.low = P(lo); b.inj = P(in); b.gate = P(ga);
      b.gain = (const float*)P(gn); b.x_low = (const float*)P(xl); b.x_gate = (const float*)P(xg);
      b.ref_low = (const float*)P(rl); b.ref_inj = (const float*)P(ri); b.ref_gate = (const float*)P(rg); b.streams = (const float*)P(st); b.branch = (const float*)P(br); b.cinj = (const float*)P(ci);
      blocks.push_back(b);
    }
  }
  std::printf("{\"blocks\":%zu,\"pack_bytes\":%zu", blocks.size(), bytes);
  // work buffers
  float *nrm = sycl::malloc_device<float>(K, q), *ylow = sycl::malloc_device<float>(L, q), *yinj = sycl::malloc_device<float>(16, q),
        *act = sycl::malloc_device<float>(L, q), *ygate = sycl::malloc_device<float>(K, q), *scratch = sycl::malloc_device<float>(4096, q),
        *rope = sycl::malloc_device<float>(64, q), *sink = sycl::malloc_device<float>(16, q);
  int32_t* ctl = sycl::malloc_device<int32_t>(64, q);  // [0] error, [16] position, [32] active
  q.fill(sink, 1.f, 16).wait();
  q.memset(rope, 0, 64 * 4).wait();
  auto set_ctl = [&](int err, int pos, int active) {
    std::vector<int32_t> h(64, 0); h[0] = err; h[16] = pos; h[32] = active;
    q.memcpy(ctl, h.data(), 64 * 4).wait();
  };
  set_ctl(0, 100, 1);
  NormIO io{nullptr, nullptr, nrm, scratch, ctl, ctl + 16, ctl + 32, rope};

  // variants
  std::vector<LowV> lows = {
      {"engine bf16_multi<1,8> wg128", low_engine_form<1, 8, 128, 1>},
      {"bf16_multi<1,4> wg128", low_engine_form<1, 4, 128, 2>},
      {"bf16_multi<1,10> wg128", low_engine_form<1, 10, 128, 3>},
      {"bf16_multi<1,20> wg128", low_engine_form<1, 20, 128, 4>},
      {"bf16_multi<1,8> wg32", low_engine_form<1, 8, 32, 5>},
      {"bf16_multi<1,8> wg64", low_engine_form<1, 8, 64, 6>},
      {"bf16_multi<2,8> wg128", low_engine_form<2, 8, 128, 7>},
      {"bf16_multi<2,4> wg64", low_engine_form<2, 4, 64, 8>},
      {"bf16_split<10,4> (SIMD16 pairs)", low_split<10, 4, 9>},
      {"pf L1 batch+1 <8> wg128", low_pf<8, 1, 1, false, 128, 10>},
      {"pf L1 batch+2 <8> wg128", low_pf<8, 2, 1, false, 128, 11>},
      {"pf L1 whole row <8> wg128", low_pf<8, 0, 1, true, 128, 12>},
      {"pf L3 whole row <8> wg128", low_pf<8, 0, 3, true, 128, 13>},
      {"pf L2 whole row <8> wg128", low_pf<8, 0, 2, true, 128, 14>},
      {"pf L3 batch+1 <8> wg128", low_pf<8, 1, 3, false, 128, 15>},
      {"pf L1 whole row <8> wg32", low_pf<8, 0, 1, true, 32, 16>},
      {"pf L1 whole row <4> wg32", low_pf<4, 0, 1, true, 32, 17>},
      {"pf none <8> wg128 (bench copy of engine)", low_pf<8, 0, 0, false, 128, 18>},
      {"bf16_multi_static<1,8> wg128", low_engine_form<1, 8, 128, 19, true>},
      {"bf16_multi_static<1,10> wg128", low_engine_form<1, 10, 128, 20, true>},
      {"SHIPPED dense_v2::bf16_multi_static<1,10>", low_shipped<21>},
  };
  std::vector<GateV> gates = {
      {"engine bf16_multi<2,4> wg128", gate_engine_form<2, 4, 128, 101>},
      {"bf16_multi<1,4> wg128", gate_engine_form<1, 4, 128, 102>},
      {"bf16_multi<4,4> wg128", gate_engine_form<4, 4, 128, 103>},
      {"bf16_multi<2,4> wg256", gate_engine_form<2, 4, 256, 104>},
      {"bf16_multi<2,4> wg64", gate_engine_form<2, 4, 64, 105>},
      {"bf16_multi<1,4> wg256", gate_engine_form<1, 4, 256, 106>},
      {"rows NR1 wg128", gate_rows<1, 0, 128, 107>},
      {"rows NR2 wg128", gate_rows<2, 0, 128, 108>},
      {"rows NR4 wg128", gate_rows<4, 0, 128, 109>},
      {"rows NR8 wg128", gate_rows<8, 0, 128, 110>},
      {"rows NR4 wg256", gate_rows<4, 0, 256, 111>},
      {"rows NR2 wg256", gate_rows<2, 0, 256, 112>},
      {"rows NR16 wg128", gate_rows<16, 0, 128, 113>},
      {"bf16_multi_static<2,4> wg128", gate_engine_form<2, 4, 128, 114, true>},
      {"bf16_multi_static<1,4> wg128", gate_engine_form<1, 4, 128, 115, true>},
  };
  std::vector<NormV> norms = {
      {"engine specialised 2 launches", [](sycl::queue& q, const NormIO& io) { return std::vector<sycl::event>{norm_engine_stage<0>(q, io), norm_engine_stage<1>(q, io)}; }},
      {"one launch wg256", [](sycl::queue& q, const NormIO& io) { return std::vector<sycl::event>{norm_one<256, 201>(q, io)}; }},
      {"one launch wg320", [](sycl::queue& q, const NormIO& io) { return std::vector<sycl::event>{norm_one<320, 202>(q, io)}; }},
      {"one launch wg640", [](sycl::queue& q, const NormIO& io) { return std::vector<sycl::event>{norm_one<640, 203>(q, io)}; }},
      {"one launch v2 wg640", [](sycl::queue& q, const NormIO& io) { return std::vector<sycl::event>{norm_one<640, 204, 2>(q, io)}; }},
      {"one launch v2 wg320", [](sycl::queue& q, const NormIO& io) { return std::vector<sycl::event>{norm_one<320, 205, 2>(q, io)}; }},
      {"one launch v2 wg256", [](sycl::queue& q, const NormIO& io) { return std::vector<sycl::event>{norm_one<256, 206, 2>(q, io)}; }},
      {"one launch v3 wg640", [](sycl::queue& q, const NormIO& io) { return std::vector<sycl::event>{norm_one<640, 207, 3>(q, io)}; }},
      {"one launch v3 wg320", [](sycl::queue& q, const NormIO& io) { return std::vector<sycl::event>{norm_one<320, 208, 3>(q, io)}; }},
      {"SHIPPED hc_kernels::norm_row<false>", [](sycl::queue& q, const NormIO& io) { return std::vector<sycl::event>{shipped_norm<false, 212>(q, nullptr, io)}; }},
  };

  std::vector<CNV> cnorms = {
      {"engine CombineFast + specialised norm (3 launches)", [](sycl::queue& q, const CombIO& c, const NormIO& io) {
         return std::vector<sycl::event>{combine_engine(q, c), norm_engine_stage<0>(q, io), norm_engine_stage<1>(q, io)}; }},
      {"engine CombineFast + norm v3 wg640 (2 launches)", [](sycl::queue& q, const CombIO& c, const NormIO& io) {
         return std::vector<sycl::event>{combine_engine(q, c), norm_one<640, 209, 3>(q, io)}; }},
      {"fused combine+norm wg640 (1 launch)", [](sycl::queue& q, const CombIO& c, const NormIO& io) {
         return std::vector<sycl::event>{combine_norm_fused<640, 210>(q, c, io)}; }},
      {"fused combine+norm wg320 (1 launch)", [](sycl::queue& q, const CombIO& c, const NormIO& io) {
         return std::vector<sycl::event>{combine_norm_fused<320, 211>(q, c, io)}; }},
      {"SHIPPED hc_kernels::norm_row<true>", [](sycl::queue& q, const CombIO& c, const NormIO& io) {
         return std::vector<sycl::event>{shipped_norm<true, 213>(q, &c, io)}; }},
  };
  float* sw = sycl::malloc_device<float>(K, q);  // streams work buffer (combined in place)
  // ---------------- 1. exactness ----------------
  auto get = [&](const float* d, size_t n) { std::vector<float> v(n); q.memcpy(v.data(), d, n * 4).wait(); return v; };
  auto same = [](const std::vector<float>& a, const std::vector<float>& b) { return a.size() == b.size() && !std::memcmp(a.data(), b.data(), a.size() * 4); };
  std::vector<int> low_bad(lows.size()), gate_bad(gates.size()), norm_bad(norms.size());
  int dump_low_bad = 0, dump_gate_bad = 0, err_after = 0, guard_bad = 0;
  for (const Block& b : blocks) {
    // low + inject
    std::vector<float> e_low, e_inj;
    for (size_t v = 0; v < lows.size(); ++v) {
      q.memset(ylow, 0xff, L * 4); q.memset(yinj, 0xff, 16 * 4); q.wait();
      lows[v].f(q, b, b.x_low, ylow, yinj).wait();
      auto lo = get(ylow, L); auto in = get(yinj, NI);
      if (v == 0) {
        e_low = lo; e_inj = in;
        if (!same(lo, get(b.ref_low, L)) || (b.inject && !same(in, get(b.ref_inj, NI)))) ++dump_low_bad;
      } else if (!same(lo, e_low) || (b.inject && !same(in, e_inj))) ++low_bad[v];
    }
    std::vector<float> e_gate;
    for (size_t v = 0; v < gates.size(); ++v) {
      q.memset(ygate, 0xff, K * 4).wait();
      gates[v].f(q, b, b.x_gate, ygate).wait();
      auto g = get(ygate, K);
      if (v == 0) { e_gate = g; if (!same(g, get(b.ref_gate, K))) ++dump_gate_bad; }
      else if (!same(g, e_gate)) ++gate_bad[v];
    }
    for (const float* xin : {b.streams, b.x_low}) {
      std::vector<float> e_y, e_s;
      for (size_t v = 0; v < norms.size(); ++v) {
        set_ctl(0, 100, 1);
        q.memset(nrm, 0xff, K * 4); q.memset(scratch, 0xff, 4096 * 4); q.wait();
        NormIO in = io; in.x = xin; in.gain = b.gain;
        for (auto& e : norms[v].f(q, in)) e.wait();
        auto y = get(nrm, K); auto s = get(scratch, 320);
        if (v == 0) { e_y = y; e_s = s; }
        else if (!same(y, e_y) || !same(s, e_s)) ++norm_bad[v];
        std::vector<int32_t> c(1); q.memcpy(c.data(), ctl, 4).wait(); err_after += c[0];
      }
    }
  }
  // combine + norm: streams after the combine, norm output and scratch, every block
  std::vector<int> cn_bad(cnorms.size());
  for (const Block& b : blocks) {
    std::vector<float> es, ey, ep;
    for (size_t v = 0; v < cnorms.size(); ++v) {
      set_ctl(0, 100, 1);
      q.memcpy(sw, b.streams, K * 4); q.memset(nrm, 0xff, K * 4); q.memset(scratch, 0xff, 4096 * 4); q.wait();
      CombIO c{sw, b.branch, b.cinj, ctl, ctl + 32};
      NormIO in = io; in.x = sw; in.gain = b.gain;
      for (auto& e : cnorms[v].f(q, c, in)) e.wait();
      auto st = get(sw, K); auto y = get(nrm, K); auto p = get(scratch, 320);
      if (v == 0) { es = st; ey = y; ep = p; } else if (!same(st, es) || !same(y, ey) || !same(p, ep)) ++cn_bad[v];
      std::vector<int32_t> cc(1); q.memcpy(cc.data(), ctl, 4).wait(); err_after += cc[0];
    }
  }
  // combine + norm guard cases: inactive, error set, position out of range
  for (int mode = 0; mode < 3; ++mode)
    for (size_t v = 1; v < cnorms.size(); ++v) {
      std::vector<float> es, ey, ep; std::vector<int32_t> ec(1), vc(1);
      for (int pass = 0; pass < 2; ++pass) {
        set_ctl(mode == 1 ? 1 : 0, mode == 2 ? 70000 : 100, mode == 0 ? 0 : 1);
        q.memcpy(sw, blocks[1].streams, K * 4); q.memset(nrm, 0x7f, K * 4); q.memset(scratch, 0x7f, 4096 * 4); q.wait();
        CombIO c{sw, blocks[1].branch, blocks[1].cinj, ctl, ctl + 32};
        NormIO in = io; in.x = sw; in.gain = blocks[1].gain;
        for (auto& e : (pass == 0 ? cnorms[0] : cnorms[v]).f(q, c, in)) e.wait();
        auto st = get(sw, K); auto y = get(nrm, K); auto p = get(scratch, 320);
        if (pass == 0) { es = st; ey = y; ep = p; q.memcpy(ec.data(), ctl, 4).wait(); }
        else { q.memcpy(vc.data(), ctl, 4).wait(); if (!same(st, es) || !same(y, ey) || !same(p, ep) || ec[0] != vc[0]) ++guard_bad; }
      }
    }
  set_ctl(0, 100, 1);
  // guard semantics on one block: inactive, error set, position out of range (outputs and error word)
  for (int mode = 0; mode < 3; ++mode)
    for (size_t v = 1; v < norms.size(); ++v) {
      std::vector<float> ey, es; std::vector<int32_t> ec(1), vc(1);
      for (int pass = 0; pass < 2; ++pass) {
        set_ctl(mode == 1 ? 1 : 0, mode == 2 ? 70000 : 100, mode == 0 ? 0 : 1);
        q.memset(nrm, 0x7f, K * 4); q.memset(scratch, 0x7f, 4096 * 4); q.wait();
        NormIO in = io; in.x = blocks[0].streams; in.gain = blocks[0].gain;
        for (auto& e : (pass == 0 ? norms[0] : norms[v]).f(q, in)) e.wait();
        auto y = get(nrm, K); auto s = get(scratch, 320);
        if (pass == 0) { ey = y; es = s; q.memcpy(ec.data(), ctl, 4).wait(); }
        else { q.memcpy(vc.data(), ctl, 4).wait(); if (!same(y, ey) || !same(s, es) || ec[0] != vc[0]) ++guard_bad; }
      }
    }
  set_ctl(0, 100, 1);
  std::printf(",\"exactness\":{\"engine_kernel_vs_dump\":{\"low_inject_blocks_differ\":%d,\"gate_blocks_differ\":%d},"
              "\"norm_error_words_set\":%d,\"norm_guard_cases_differ\":%d,\"low\":[", dump_low_bad, dump_gate_bad, err_after, guard_bad);
  for (size_t v = 0; v < lows.size(); ++v) std::printf("%s{\"name\":\"%s\",\"blocks_differ\":%d}", v ? "," : "", lows[v].name.c_str(), low_bad[v]);
  std::printf("],\"gate\":[");
  for (size_t v = 0; v < gates.size(); ++v) std::printf("%s{\"name\":\"%s\",\"blocks_differ\":%d}", v ? "," : "", gates[v].name.c_str(), gate_bad[v]);
  std::printf("],\"norm\":[");
  for (size_t v = 0; v < norms.size(); ++v) std::printf("%s{\"name\":\"%s\",\"inputs_differ\":%d}", v ? "," : "", norms[v].name.c_str(), norm_bad[v]);
  std::printf("],\"combine_norm\":[");
  for (size_t v = 0; v < cnorms.size(); ++v) std::printf("%s{\"name\":\"%s\",\"blocks_differ\":%d}", v ? "," : "", cnorms[v].name.c_str(), cn_bad[v]);
  std::printf("]}");
  std::fflush(stdout);

  // ---------------- 2. timing ----------------
  auto eb = busy(q, sink, 1000000); eb.wait();
  const u32 iters = u32(std::min(2.0e7, 10.0e6 / (ev_us(eb) * 1e3 / 1e6)));
  struct Cfg { int nv, lv, gv; std::string fam; int ctx = 0; int cv = -1; };
  std::vector<Cfg> cfgs;
  cfgs.push_back({0, 0, 0, "engine"});
  for (size_t v = 1; v < lows.size(); ++v) cfgs.push_back({0, int(v), 0, "low"});
  for (size_t v = 1; v < gates.size(); ++v) cfgs.push_back({0, 0, int(v), "gate"});
  for (size_t v = 1; v < norms.size(); ++v) cfgs.push_back({int(v), 0, 0, "norm"});
  for (size_t v = 0; v < cnorms.size(); ++v) cfgs.push_back({0, 0, 0, "cnorm", 0, int(v)});
  // under production-like context: the engine set and the candidates named on the command line (indices)
  const int ctx_low = argc > 3 ? std::atoi(argv[3]) : 0, ctx_gate = argc > 4 ? std::atoi(argv[4]) : 0, ctx_norm = argc > 5 ? std::atoi(argv[5]) : 0;
  for (int cx = 1; cx <= 2; ++cx) {
    cfgs.push_back({0, 0, 0, "engine", cx});
    if (ctx_low) cfgs.push_back({0, ctx_low, 0, "low", cx});
    if (ctx_gate) cfgs.push_back({0, 0, ctx_gate, "gate", cx});
    if (ctx_norm) cfgs.push_back({ctx_norm, 0, 0, "norm", cx});
  }
  // context buffers and calibration (~100 us ALU kernel)
  const size_t ctx_bytes = size_t(96) << 20;
  auto* ctx_src = sycl::malloc_device<sycl::vec<uint32_t, 4>>(ctx_bytes / 16, q);
  float* ctx_dst = sycl::malloc_device<float>(524288, q);
  q.memset(ctx_src, 0x3c, ctx_bytes).wait();
  u32 alu_iters = 2000;
  { auto e = alu_ctx(q, sink, alu_iters); e.wait(); alu_iters = u32(std::max(100.0, alu_iters * 100.0 / ev_us(e))); }
  const int ROUNDS = quick ? 1 : 4, PASSES = quick ? 1 : 2;
  // per config, per rank: kernel durations (us) by family and site kind; and block period
  struct Acc { std::vector<double> norm, low_inj, low_final, gate, block; };
  std::vector<std::array<Acc, 2>> acc(cfgs.size());
  {  // warm-up ~1 s
    auto t0 = std::chrono::steady_clock::now();
    while (std::chrono::steady_clock::now() - t0 < std::chrono::milliseconds(quick ? 200 : 1000)) {
      for (const Block& b : blocks) { NormIO in = io; in.x = b.x_low; in.gain = b.gain; norms[0].f(q, in); lows[0].f(q, b, nrm, ylow, yinj); act_kernel(q, ylow, act); gates[0].f(q, b, act, ygate); }
      q.wait();
    }
  }
  for (int round = 0; round < ROUNDS; ++round)
    for (size_t ci = 0; ci < cfgs.size(); ++ci)
      for (int rank = 0; rank < 2; ++rank) {
        const Cfg& c = cfgs[ci];
        busy(q, sink, iters);
        struct Rec { std::vector<sycl::event> n; sycl::event l, a, g; bool inj; };
        std::vector<Rec> recs;
        for (int pass = 0; pass < PASSES; ++pass)
          for (const Block& b : blocks) {
            if (b.rank != rank) continue;
            NormIO in = io; in.x = b.x_low; in.gain = b.gain;
            if (c.ctx == 1) alu_ctx(q, sink, alu_iters);
            else if (c.ctx == 2) stream_ctx(q, ctx_src, ctx_bytes / 16, ctx_dst);
            Rec r;
            if (c.cv >= 0) { CombIO cb{sw, b.branch, b.cinj, ctl, ctl + 32}; in.x = sw; r.n = cnorms[c.cv].f(q, cb, in); }
            else r.n = norms[c.nv].f(q, in); r.l = lows[c.lv].f(q, b, nrm, ylow, yinj); r.a = act_kernel(q, ylow, act);
            r.g = gates[c.gv].f(q, b, act, ygate); r.inj = b.inject; recs.push_back(r);
          }
        q.wait();
        Acc& A = acc[ci][rank];
        for (size_t i = 1; i < recs.size(); ++i) {  // skip the first block after the busy kernel
          const Rec& r = recs[i];
          double nsum = 0; for (auto& e : r.n) nsum += ev_us(e);
          double gaps = 0; for (size_t e = 1; e < r.n.size(); ++e) gaps += (t_start(r.n[e]) - t_end(r.n[e - 1])) / 1e3;
          A.norm.push_back(nsum + gaps);
          (r.inj ? A.low_inj : A.low_final).push_back(ev_us(r.l));
          A.gate.push_back(ev_us(r.g));
          A.block.push_back(c.ctx ? (t_end(r.g) - t_start(r.n[0])) / 1e3 : (t_end(r.g) - t_end(recs[i - 1].g)) / 1e3);
        }
      }
  std::vector<int32_t> c(1); q.memcpy(c.data(), ctl, 4).wait();
  std::printf(",\"timing\":{\"rounds\":%d,\"passes\":%d,\"configs\":[", ROUNDS, PASSES);
  for (size_t ci = 0; ci < cfgs.size(); ++ci) {
    const Cfg& cf = cfgs[ci];
    std::string name = cf.fam == "engine" ? "engine" : cf.fam == "low" ? lows[cf.lv].name : cf.fam == "gate" ? gates[cf.gv].name : cf.fam == "cnorm" ? cnorms[cf.cv].name : norms[cf.nv].name;
    std::printf("%s{\"family\":\"%s\",\"name\":\"%s\",\"context\":%d", ci ? "," : "", cf.fam.c_str(), name.c_str(), cf.ctx);
    for (int rank = 0; rank < 2; ++rank) {
      const Acc& A = acc[ci][rank];
      std::printf(",\"rank%d\":{\"norm_us\":%.3f,\"low_inject_us\":%.3f,\"low_final_us\":%.3f,\"gate_us\":%.3f,\"gate_p10\":%.3f,\"gate_p90\":%.3f,"
                  "\"low_p10\":%.3f,\"low_p90\":%.3f,\"block_period_us\":%.3f,\"n\":%zu}",
                  rank, pct(A.norm, 0.5), pct(A.low_inj, 0.5), pct(A.low_final, 0.5), pct(A.gate, 0.5), pct(A.gate, 0.1), pct(A.gate, 0.9),
                  pct(A.low_inj, 0.1), pct(A.low_inj, 0.9), pct(A.block, 0.5), A.block.size());
    }
    std::printf("}");
  }
  std::printf("]},\"alu_ctx_iters\":%u,\"final_error_word\":%d}\n", alu_iters, c[0]);
  return 0;
}
