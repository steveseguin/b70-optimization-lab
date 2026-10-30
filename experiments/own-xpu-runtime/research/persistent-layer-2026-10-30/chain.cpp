// Persistent-layer study (2026-10-30), question 2: one real glue chain, as separate kernels and as one persistent
// kernel with bounded device-wide barriers between its phases.
//
// The chain is SC117's hyper-connection block at the real shapes (recurrent-f32 plan.hpp `hc()`): H = 2560, 4 streams
// (K = 10240), low rank 320, BF16 weights, F32 activations:
//   norm   per-stream RMS norm of the 4x2560 streams (partial sums by 32-element chunk, then scale), 2 kernels
//   low    GEMV 320 x 10240 (+ the 4 inject rows of the same input), K split in 4 fixed quarters
//   act    silu_div4 on the 320 low values
//   gate   GEMV 10240 x 320
//   mix    mix[k] = sum_h sigmoid(gate[h*H+k]) * norm[h*H+k] / 4
// Versions (every per-element operation and every reduction order is the same function in all of them):
//   A   six launches per block, like the engine (norm x2, low+inject, act, gate, mix)
//   A2  four launches: act in the low epilogue, mix in a column-grouped gate epilogue
//   B   one persistent launch for 8 blocks, phases as A, 5 bounded barriers per block
//   C   one persistent launch for 8 blocks, phases as A2, 3 bounded barriers per block
// A pass runs 8 blocks, each with its own weights and input (8 x 13.3 MB, so weights come from memory as in the
// engine, where every layer's weights differ); intermediates reuse fixed buffers across blocks. Outputs (per-block
// mix and inject, plus the final intermediates) are compared bitwise against A; A is also checked against a
// double-precision host reference for block 0 (tolerance), so a trivially equal wrong answer cannot pass.
#include <sycl/sycl.hpp>
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <random>
#include <string>
#include <vector>
#include "gbar.hpp"
#include "stage2/packet194-expert-diet-engine/detmath.hpp"

using namespace pl;
using u16 = std::uint16_t;

constexpr u32 H = 2560, S = 4, K = H * S, L = 320, NI = 4, LR = L + NI, NSET = 8, WG = 128, CH = K / 32;
constexpr u32 LIMIT = 1u << 16;

struct P {
  const float* x;     // [NSET][K]
  const float* gain;  // [NSET][K]
  const u16* wl;      // [NSET][LR][K]   low rows then inject rows
  const u16* wg;      // [NSET][K][L]    gate
  float *part, *norm, *low, *act, *gate;  // working buffers (fixed addresses)
  float *mix_out, *inj_out;               // [NSET][H], [NSET][NI]
};

inline float bf(u16 u) { return sycl::bit_cast<float>(u32(u) << 16); }
inline float sigm(float x) { return 1.f / (1.f + detmath::exp(-x)); }
inline float bfly(const sycl::sub_group& sg, float v) {  // xor butterfly: every lane gets the same bits
  for (u32 o = 16; o >= 1; o >>= 1) v = v + sycl::permute_group_by_xor(sg, v, o);
  return v;
}

// ---- per-unit device functions, shared by every version ----
inline void unit_chunk(const sycl::sub_group& sg, const P& p, u32 set, u32 c) {
  const u32 lane = sg.get_local_linear_id();
  const float v = p.x[set * K + c * 32 + lane];
  const float t = bfly(sg, v * v);
  if (lane == 0) p.part[c] = t;
}
inline float stream_inv(const sycl::sub_group& sg, const P& p, u32 s) {
  const u32 lane = sg.get_local_linear_id();
  const float* q = p.part + s * (H / 32);
  float t = q[lane];
  t = t + q[lane + 32];
  if (lane < 16) t = t + q[lane + 64];
  const float total = bfly(sg, t);
  return detmath::rsqrt(total / float(H) + 1e-6f);
}
inline void unit_normout(const sycl::nd_item<1>& it, const sycl::sub_group& sg, const P& p, u32 set, u32 blk) {
  const u32 i = blk * u32(it.get_local_range(0)) + u32(it.get_local_linear_id()), s = i / H;  // a sub-group never straddles streams
  const float inv = stream_inv(sg, p, s);
  p.norm[i] = (p.x[set * K + i] * inv) * (p.gain[set * K + i] + 0.f);
}
inline float act_of(float low) { return detmath::silu_div4(low); }
// low row r (one virtual group of four sub-groups): quarter j = sub-group index inside the virtual group, 10 steps
// of 8 BF16 per lane. The group barriers span the whole work-group, so every virtual group calls this, active or not.
inline void unit_low(const sycl::nd_item<1>& it, const sycl::sub_group& sg, const P& p, u32 set, u32 r, bool active,
                     float* slm, bool fuse_act, u32 layer) {
  const u32 lane = sg.get_local_linear_id(), sgi = sg.get_group_linear_id(), j = sgi % 4u, vg = sgi / 4u;
  if (active) {
    const u16* w = p.wl + (size_t(set) * LR + r) * K + j * (K / 4);
    const float* xv = p.norm + j * (K / 4);
    float acc = 0.f;
    for (u32 t = 0; t < K / 4 / 256; ++t) {
      const u32 o = (t * 32 + lane) * 8;
      const sycl::vec<u16, 8> wv = *reinterpret_cast<const sycl::vec<u16, 8>*>(w + o);
      const sycl::float4 x0 = *reinterpret_cast<const sycl::float4*>(xv + o);
      const sycl::float4 x1 = *reinterpret_cast<const sycl::float4*>(xv + o + 4);
      acc = acc + bf(wv[0]) * x0[0];
      acc = acc + bf(wv[1]) * x0[1];
      acc = acc + bf(wv[2]) * x0[2];
      acc = acc + bf(wv[3]) * x0[3];
      acc = acc + bf(wv[4]) * x1[0];
      acc = acc + bf(wv[5]) * x1[1];
      acc = acc + bf(wv[6]) * x1[2];
      acc = acc + bf(wv[7]) * x1[3];
    }
    const float part = bfly(sg, acc);
    if (lane == 0) slm[vg * 8 + j] = part;
  }
  sycl::group_barrier(it.get_group());
  if (active && j == 0 && lane == 0) {
    const float* q = slm + vg * 8;
    const float y = (q[0] + q[1]) + (q[2] + q[3]);
    if (r < L) {
      p.low[r] = y;
      if (fuse_act) p.act[r] = act_of(y);
    } else {
      p.inj_out[layer * NI + (r - L)] = y;
    }
  }
  sycl::group_barrier(it.get_group());
}
inline void unit_act(const sycl::nd_item<1>& it, const P& p, u32 blk) {
  const u32 r = blk * u32(it.get_local_range(0)) + u32(it.get_local_linear_id());
  if (r < L) p.act[r] = act_of(p.low[r]);
}
// gate row (one sub-group): 5 steps of 2 BF16 per lane
inline float gate_row(const sycl::sub_group& sg, const P& p, u32 set, u32 row) {
  const u32 lane = sg.get_local_linear_id();
  const u16* w = p.wg + (size_t(set) * K + row) * L;
  float acc = 0.f;
  for (u32 t = 0; t < L / 64; ++t) {
    const u32 o = (t * 32 + lane) * 2;
    const sycl::vec<u16, 2> wv = *reinterpret_cast<const sycl::vec<u16, 2>*>(w + o);
    acc = acc + bf(wv[0]) * p.act[o];
    acc = acc + bf(wv[1]) * p.act[o + 1];
  }
  return bfly(sg, acc);
}
inline void unit_gate4(const sycl::sub_group& sg, const P& p, u32 set, u32 row) {
  const float g = gate_row(sg, p, set, row);
  if (sg.get_local_linear_id() == 0) p.gate[row] = g;
}
inline float mix_of(const float* g4, const P& p, u32 k) {
  float sum = 0.f;
  for (u32 h = 0; h < S; ++h) sum = sum + sigm(g4[h]) * p.norm[h * H + k];
  return sum / 4.f;
}
inline void unit_mix(const sycl::nd_item<1>& it, const P& p, u32 blk, u32 layer) {
  const u32 k = blk * u32(it.get_local_range(0)) + u32(it.get_local_linear_id());
  if (k >= H) return;
  const float g4[4] = {p.gate[k], p.gate[H + k], p.gate[2 * H + k], p.gate[3 * H + k]};
  p.mix_out[layer * H + k] = mix_of(g4, p, k);
}
// column k (one virtual group): sub-group h computes gate row h*H+k; then the virtual group's first item computes mix[k]
inline void unit_gate_mix(const sycl::nd_item<1>& it, const sycl::sub_group& sg, const P& p, u32 set, u32 k,
                          bool active, float* slm, u32 layer) {
  const u32 sgi = sg.get_group_linear_id(), h = sgi % 4u, vg = sgi / 4u;
  if (active) {
    const float g = gate_row(sg, p, set, h * H + k);
    if (sg.get_local_linear_id() == 0) {
      p.gate[h * H + k] = g;
      slm[vg * 8 + 4 + h] = g;
    }
  }
  sycl::group_barrier(it.get_group());
  if (active && h == 0 && sg.get_local_linear_id() == 0) {
    const float* q = slm + vg * 8 + 4;
    const float g4[4] = {q[0], q[1], q[2], q[3]};
    p.mix_out[layer * H + k] = mix_of(g4, p, k);
  }
  sycl::group_barrier(it.get_group());
}

// ---- separate kernels ----
template <int I> class KName;
#define SG32 [[sycl::reqd_sub_group_size(32)]]
static sycl::event k_chunk(sycl::queue& q, P p, u32 set) {
  return q.parallel_for<KName<1>>(sycl::nd_range<1>(CH / 4 * WG, WG), [=](sycl::nd_item<1> it) SG32 {
    auto sg = it.get_sub_group();
    unit_chunk(sg, p, set, u32(it.get_group_linear_id()) * 4 + u32(sg.get_group_linear_id()));
  });
}
static sycl::event k_normout(sycl::queue& q, P p, u32 set) {
  return q.parallel_for<KName<2>>(sycl::nd_range<1>(K, WG), [=](sycl::nd_item<1> it) SG32 {
    unit_normout(it, it.get_sub_group(), p, set, u32(it.get_group_linear_id()));
  });
}
static sycl::event k_low(sycl::queue& q, P p, u32 set, bool fuse, u32 layer) {
  return q.submit([&](sycl::handler& h) {
    sycl::local_accessor<float, 1> slm(8, h);
    h.parallel_for<KName<3>>(sycl::nd_range<1>(LR * WG, WG), [=](sycl::nd_item<1> it) SG32 {
      unit_low(it, it.get_sub_group(), p, set, u32(it.get_group_linear_id()), true,
               slm.get_multi_ptr<sycl::access::decorated::no>().get(), fuse, layer);
    });
  });
}
static sycl::event k_act(sycl::queue& q, P p) {
  return q.parallel_for<KName<4>>(sycl::nd_range<1>(3 * WG, WG), [=](sycl::nd_item<1> it) SG32 {
    unit_act(it, p, u32(it.get_group_linear_id()));
  });
}
static sycl::event k_gate(sycl::queue& q, P p, u32 set) {
  return q.parallel_for<KName<5>>(sycl::nd_range<1>(K / 4 * WG, WG), [=](sycl::nd_item<1> it) SG32 {
    auto sg = it.get_sub_group();
    unit_gate4(sg, p, set, u32(it.get_group_linear_id()) * 4 + u32(sg.get_group_linear_id()));
  });
}
static sycl::event k_mix(sycl::queue& q, P p, u32 layer) {
  return q.parallel_for<KName<6>>(sycl::nd_range<1>(H, WG), [=](sycl::nd_item<1> it) SG32 {
    unit_mix(it, p, u32(it.get_group_linear_id()), layer);
  });
}
static sycl::event k_gate_mix(sycl::queue& q, P p, u32 set, u32 layer) {
  return q.submit([&](sycl::handler& h) {
    sycl::local_accessor<float, 1> slm(8, h);
    h.parallel_for<KName<7>>(sycl::nd_range<1>(H * WG, WG), [=](sycl::nd_item<1> it) SG32 {
      unit_gate_mix(it, it.get_sub_group(), p, set, u32(it.get_group_linear_id()), true,
                    slm.get_multi_ptr<sycl::access::decorated::no>().get(), layer);
    });
  });
}
// one pass (NSET blocks) of version A (mode 0), A2 (mode 1: act in the low epilogue + column-grouped gate+mix) or
// A3 (mode 2: act in the low epilogue only, 5 launches); returns first and last events
static std::pair<sycl::event, sycl::event> pass_sep(sycl::queue& q, const P& p, int mode,
                                                    std::vector<sycl::event>* all = nullptr) {
  sycl::event first, last;
  for (u32 l = 0; l < NSET; ++l) {
    sycl::event e[6];
    int n = 0;
    e[n++] = k_chunk(q, p, l);
    e[n++] = k_normout(q, p, l);
    e[n++] = k_low(q, p, l, mode != 0, l);
    if (mode == 0) e[n++] = k_act(q, p);
    if (mode != 1) {
      e[n++] = k_gate(q, p, l);
      e[n++] = k_mix(q, p, l);
    } else {
      e[n++] = k_gate_mix(q, p, l, l);
    }
    if (l == 0) first = e[0];
    last = e[n - 1];
    if (all)
      for (int i = 0; i < n; ++i) all->push_back(e[i]);
  }
  return {first, last};
}

// ---- persistent kernel: NSET blocks in one launch ----
// V = 0: B (phases of A, 5 barriers per block), V = 1: C (phases of A2, 3 barriers per block).
// NV virtual groups (of 4 sub-groups, 128 items) per work-group: NV = 1 -> 128-item groups (up to 512 resident),
// NV = 8 -> 1024-item groups (64 fill the card, so the barrier has 8x fewer arrivals).
template <int V, int NV> class PName;
template <int V, int NV>
static sycl::event pass_persistent(sycl::queue& q, const P& p, u32* ctl, u32 nwg, u32& base) {
  const u32 b0 = base;
  constexpr u32 nbar = V == 0 ? 5 : 3, SGS = 4 * NV, WGS = WG * NV;
  base = next_base<Kind::counter>(base, nbar * NSET, nwg);
  return q.submit([&](sycl::handler& h) {
    sycl::local_accessor<float, 1> slm(8 * NV, h);
    h.parallel_for<PName<V, NV>>(sycl::nd_range<1>(size_t(nwg) * WGS, WGS), [=](sycl::nd_item<1> it) SG32 {
      auto sg = it.get_sub_group();
      float* sl = slm.get_multi_ptr<sycl::access::decorated::no>().get();
      Bar b{ctl, nwg, b0, LIMIT};
      const u32 g = u32(it.get_group_linear_id()), sgi = u32(sg.get_group_linear_id()), vg = sgi / 4u;
      for (u32 l = 0; l < NSET; ++l) {
        for (u32 u = g * SGS + sgi; u < CH; u += nwg * SGS) unit_chunk(sg, p, l, u);
        if (!gbar<Kind::counter, Fence::wg>(it, b)) break;
        for (u32 blk = g; blk < K / WGS; blk += nwg) unit_normout(it, sg, p, l, blk);
        if (!gbar<Kind::counter, Fence::wg>(it, b)) break;
        for (u32 r0 = g * NV; r0 < LR; r0 += nwg * NV) unit_low(it, sg, p, l, r0 + vg, r0 + vg < LR, sl, V == 1, l);
        if (!gbar<Kind::counter, Fence::wg>(it, b)) break;
        if constexpr (V == 0) {
          for (u32 blk = g; blk * WGS < L; blk += nwg) unit_act(it, p, blk);
          if (!gbar<Kind::counter, Fence::wg>(it, b)) break;
          for (u32 u = g * SGS + sgi; u < K; u += nwg * SGS) unit_gate4(sg, p, l, u);
          if (!gbar<Kind::counter, Fence::wg>(it, b)) break;
          for (u32 blk = g; blk * WGS < H; blk += nwg) unit_mix(it, p, blk, l);
        } else {
          for (u32 k0 = g * NV; k0 < H; k0 += nwg * NV) unit_gate_mix(it, sg, p, l, k0 + vg, k0 + vg < H, sl, l);
        }
      }
      publish_polls(it, b);
    });
  });
}

// ---- host ----
static double ev_ns(const sycl::event& e) {
  return double(e.get_profiling_info<sycl::info::event_profiling::command_end>() -
                e.get_profiling_info<sycl::info::event_profiling::command_start>());
}
static double t_start(const sycl::event& e) {
  return double(e.get_profiling_info<sycl::info::event_profiling::command_start>());
}
static double t_end(const sycl::event& e) {
  return double(e.get_profiling_info<sycl::info::event_profiling::command_end>());
}
static double pct(std::vector<double> v, double q) {
  if (v.empty()) return 0;
  std::sort(v.begin(), v.end());
  return v[std::min(v.size() - 1, size_t(q * double(v.size() - 1) + 0.5))];
}
static u16 to_bf(float f) {
  u32 u;
  std::memcpy(&u, &f, 4);
  return u16(u >> 16);  // truncation: the synthetic weight is defined as this BF16 value
}
static float from_bf(u16 h) {
  u32 u = u32(h) << 16;
  float f;
  std::memcpy(&f, &u, 4);
  return f;
}
class BusyName;
static sycl::event busy(sycl::queue& q, float* sink, u32 iters) {
  return q.single_task<BusyName>([=] {
    float x = sink[1];
    for (u32 i = 0; i < iters; ++i) x = x * 1.0000001f + float(i & 7u) * 1e-7f;
    sink[0] = x;
  });
}

struct Out {
  std::vector<float> mix, inj, part, norm, low, act, gate;
  bool operator==(const Out& o) const {
    auto eq = [](const std::vector<float>& a, const std::vector<float>& b) {
      return a.size() == b.size() && !std::memcmp(a.data(), b.data(), a.size() * 4);
    };
    return eq(mix, o.mix) && eq(inj, o.inj) && eq(part, o.part) && eq(norm, o.norm) && eq(low, o.low) &&
           eq(act, o.act) && eq(gate, o.gate);
  }
};
static Out grab(sycl::queue& q, const P& p) {
  Out o;
  auto get = [&](std::vector<float>& v, const float* d, size_t n) {
    v.resize(n);
    q.memcpy(v.data(), d, n * 4).wait();
  };
  get(o.mix, p.mix_out, NSET * H);
  get(o.inj, p.inj_out, NSET * NI);
  get(o.part, p.part, CH);
  get(o.norm, p.norm, K);
  get(o.low, p.low, L);
  get(o.act, p.act, L);
  get(o.gate, p.gate, K);
  return o;
}
static void clear(sycl::queue& q, const P& p) {
  q.memset(p.part, 0xff, CH * 4);
  q.memset(p.norm, 0xff, K * 4);
  q.memset(p.low, 0xff, L * 4);
  q.memset(p.act, 0xff, L * 4);
  q.memset(p.gate, 0xff, K * 4);
  q.memset(p.mix_out, 0xff, NSET * H * 4);
  q.memset(p.inj_out, 0xff, NSET * NI * 4);
  q.wait();
}

int main(int argc, char** argv) {
  const bool quick = argc > 1 && std::string(argv[1]) == "quick";
  auto devs = sycl::device::get_devices(sycl::info::device_type::gpu);
  if (devs.size() != 1) {
    std::printf("{\"error\":\"expected one visible GPU, got %zu\"}\n", devs.size());
    return 2;
  }
  sycl::queue q(devs[0], {sycl::property::queue::in_order{}, sycl::property::queue::enable_profiling{}});
  sycl::queue qn(q.get_context(), devs[0], {sycl::property::queue::in_order{}});
  // synthetic data, fixed seed
  std::mt19937 rng(20261030);
  std::uniform_real_distribution<float> ux(-2.f, 2.f), ug(0.5f, 1.5f), ul(-0.03f, 0.03f), uw(-0.3f, 0.3f);
  std::vector<float> hx(NSET * K), hg(NSET * K);
  std::vector<u16> hl(size_t(NSET) * LR * K), hw(size_t(NSET) * K * L);
  for (auto& v : hx) v = ux(rng);
  for (auto& v : hg) v = ug(rng);
  for (auto& v : hl) v = to_bf(ul(rng));
  for (auto& v : hw) v = to_bf(uw(rng));
  P p{};
  float* dx = sycl::malloc_device<float>(hx.size(), q);
  float* dg = sycl::malloc_device<float>(hg.size(), q);
  u16* dl = sycl::malloc_device<u16>(hl.size(), q);
  u16* dw = sycl::malloc_device<u16>(hw.size(), q);
  q.memcpy(dx, hx.data(), hx.size() * 4);
  q.memcpy(dg, hg.data(), hg.size() * 4);
  q.memcpy(dl, hl.data(), hl.size() * 2);
  q.memcpy(dw, hw.data(), hw.size() * 2);
  q.wait();
  p.x = dx;
  p.gain = dg;
  p.wl = dl;
  p.wg = dw;
  p.part = sycl::malloc_device<float>(CH, q);
  p.norm = sycl::malloc_device<float>(K, q);
  p.low = sycl::malloc_device<float>(L, q);
  p.act = sycl::malloc_device<float>(L, q);
  p.gate = sycl::malloc_device<float>(K, q);
  p.mix_out = sycl::malloc_device<float>(NSET * H, q);
  p.inj_out = sycl::malloc_device<float>(NSET * NI, q);
  u32* ctl = sycl::malloc_device<u32>(CTL_WORDS, q);
  q.memset(ctl, 0, CTL_WORDS * 4).wait();
  float* sink = sycl::malloc_device<float>(16, q);
  q.fill(sink, 1.f, 16).wait();
  u32 baseB = 0, baseC = 0;  // counter barriers: each persistent variant keeps its own nwg; reset on change
  auto read_err = [&] {
    u32 e = 0;
    q.memcpy(&e, ctl + ERR, 4).wait();
    return e;
  };
  auto reset_ctl = [&] {
    q.memset(ctl, 0, CTL_WORDS * 4).wait();
    baseB = baseC = 0;
  };
  std::printf("{\"shapes\":{\"H\":%u,\"streams\":%u,\"K\":%u,\"low\":%u,\"inject\":%u,\"blocks_per_pass\":%u,"
              "\"weight_MB_per_block\":%.3f}",
              H, S, K, L, NI, NSET, (double(LR) * K + double(K) * L) * 2 / 1e6);

  // co-residency limit of the two persistent kernels (driver query); larger launches are skipped
  size_t maxq[4] = {0, 0, 0, 0};  // B/128, C/128, B/1024, C/1024
  {
    namespace X = sycl::ext::oneapi::experimental;
    auto kb = sycl::get_kernel_bundle<sycl::bundle_state::executable>(q.get_context());
    try {
      maxq[0] = kb.get_kernel<PName<0, 1>>().ext_oneapi_get_info<X::info::kernel_queue_specific::max_num_work_groups>(
          q, sycl::range<1>(WG), 8 * sizeof(float));
      maxq[1] = kb.get_kernel<PName<1, 1>>().ext_oneapi_get_info<X::info::kernel_queue_specific::max_num_work_groups>(
          q, sycl::range<1>(WG), 8 * sizeof(float));
      maxq[2] = kb.get_kernel<PName<0, 8>>().ext_oneapi_get_info<X::info::kernel_queue_specific::max_num_work_groups>(
          q, sycl::range<1>(8 * WG), 64 * sizeof(float));
      maxq[3] = kb.get_kernel<PName<1, 8>>().ext_oneapi_get_info<X::info::kernel_queue_specific::max_num_work_groups>(
          q, sycl::range<1>(8 * WG), 64 * sizeof(float));
    } catch (const sycl::exception&) {
    }
  }
  std::printf(",\"persistent_max_num_work_groups\":{\"B128\":%zu,\"C128\":%zu,\"B1024\":%zu,\"C1024\":%zu}", maxq[0],
              maxq[1], maxq[2], maxq[3]);
  // 1. exactness: A twice, A2, B and C at several group counts; A against a host reference (block 0)
  // persistent configurations: (work-group size, groups); only co-resident ones are launched
  struct PC { u32 wgs, nwg; };
  std::vector<PC> pcs;
  for (PC c : quick ? std::vector<PC>{{128, 128}, {1024, 32}}
                    : std::vector<PC>{{128, 64}, {128, 128}, {128, 256}, {128, 324}, {128, 512}, {1024, 16},
                                      {1024, 32}, {1024, 41}, {1024, 64}})
    if (c.nwg <= (c.wgs == 128 ? std::min(maxq[0], maxq[1]) : std::min(maxq[2], maxq[3]))) pcs.push_back(c);
  auto launch_p = [&](sycl::queue& qq, int v, const PC& c) {
    if (c.wgs == 128) return v == 0 ? pass_persistent<0, 1>(qq, p, ctl, c.nwg, baseB) : pass_persistent<1, 1>(qq, p, ctl, c.nwg, baseC);
    return v == 0 ? pass_persistent<0, 8>(qq, p, ctl, c.nwg, baseB) : pass_persistent<1, 8>(qq, p, ctl, c.nwg, baseC);
  };
  clear(q, p);
  pass_sep(q, p, 0);
  q.wait();
  Out ref = grab(q, p);
  // host reference, block 0, double precision
  double maxrel_mix = 0, maxrel_inj = 0;
  {
    const float* x = hx.data();
    const float* gn = hg.data();
    std::vector<double> nrm(K), low(LR), act(L), gate(K);
    for (u32 s = 0; s < S; ++s) {
      double ss = 0;
      for (u32 k = 0; k < H; ++k) ss += double(x[s * H + k]) * x[s * H + k];
      double inv = 1.0 / std::sqrt(ss / H + 1e-6);
      for (u32 k = 0; k < H; ++k) nrm[s * H + k] = x[s * H + k] * inv * gn[s * H + k];
    }
    for (u32 r = 0; r < LR; ++r) {
      double a = 0;
      for (u32 k = 0; k < K; ++k) a += double(from_bf(hl[size_t(r) * K + k])) * nrm[k];
      low[r] = a;
    }
    for (u32 r = 0; r < L; ++r) act[r] = (low[r] / 4.0) / (1.0 + std::exp(-low[r] / 4.0));  // detmath::silu_div4
    for (u32 r = 0; r < K; ++r) {
      double a = 0;
      for (u32 k = 0; k < L; ++k) a += double(from_bf(hw[size_t(r) * L + k])) * act[k];
      gate[r] = a;
    }
    double mmax = 0;
    for (u32 k = 0; k < H; ++k) {
      double m = 0;
      for (u32 h = 0; h < S; ++h) m += nrm[h * H + k] / (1.0 + std::exp(-gate[h * H + k]));
      m /= 4.0;
      mmax = std::max(mmax, std::abs(m));
      maxrel_mix = std::max(maxrel_mix, std::abs(m - double(ref.mix[k])));
    }
    maxrel_mix /= mmax;
    double imax = 0;
    for (u32 i = 0; i < NI; ++i) imax = std::max(imax, std::abs(low[L + i]));
    for (u32 i = 0; i < NI; ++i) maxrel_inj = std::max(maxrel_inj, std::abs(low[L + i] - double(ref.inj[i])) / imax);
  }
  std::printf(",\"host_reference_block0\":{\"mix_max_abs_err_over_max\":%.3e,\"inject_max_abs_err_over_max\":%.3e,"
              "\"pass\":%d}",
              maxrel_mix, maxrel_inj, maxrel_mix < 1e-4 && maxrel_inj < 1e-4);
  std::printf(",\"exactness\":[");
  bool all_exact = true, halt = false;
  {
    clear(q, p);
    pass_sep(q, p, 0);
    q.wait();
    bool e = grab(q, p) == ref;
    all_exact &= e;
    std::printf("{\"version\":\"A repeat\",\"bitwise_equal_to_A\":%d}", e);
    clear(q, p);
    pass_sep(q, p, 1);
    q.wait();
    e = grab(q, p) == ref;
    all_exact &= e;
    std::printf(",{\"version\":\"A2\",\"bitwise_equal_to_A\":%d}", e);
    clear(q, p);
    pass_sep(q, p, 2);
    q.wait();
    e = grab(q, p) == ref;
    all_exact &= e;
    std::printf(",{\"version\":\"A3\",\"bitwise_equal_to_A\":%d}", e);
    for (const PC& pc : pcs) {
      for (int v = 0; v < 2; ++v) {
        reset_ctl();
        clear(q, p);
        sycl::event ev = launch_p(q, v, pc);
        ev.wait();
        const u32 err = read_err();
        e = err == 0 && grab(q, p) == ref;
        all_exact &= e;
        u32 mp = 0;
        q.memcpy(&mp, ctl + MAXPOLL, 4).wait();
        std::printf(",{\"version\":\"%s\",\"wg\":%u,\"nwg\":%u,\"barrier_error\":%u,\"maxpolls\":%u,"
                    "\"bitwise_equal_to_A\":%d}",
                    v ? "C" : "B", pc.wgs, pc.nwg, err, mp, e);
        if (err) halt = true;
      }
      if (halt) break;
    }
  }
  std::printf("],\"all_exact\":%d", all_exact);
  std::fflush(stdout);
  if (halt) {
    std::printf(",\"halt\":\"barrier error\"}\n");
    return 4;
  }

  // 2. timing: passes back-to-back behind a busy kernel (host ahead), versions interleaved, several rounds
  auto eb = busy(q, sink, 1000000);
  eb.wait();
  const u32 iters = u32(std::min(2.0e7, 8.0e6 / (ev_ns(eb) / 1e6)));
  const int PASSES = quick ? 6 : 24, ROUNDS = quick ? 2 : 6, SKIP = 2;
  struct Cfg { std::string name; int kind; PC pc; };  // kind 0 A, 1 A2, 2 B, 3 C, 4 A3
  std::vector<Cfg> cfgs = {{"A", 0, {128, 0}}, {"A2", 1, {128, 0}}, {"A3", 4, {128, 0}}};
  for (const PC& pc : pcs) {
    cfgs.push_back({"B", 2, pc});
    cfgs.push_back({"C", 3, pc});
  }
  std::vector<std::vector<double>> per_block(cfgs.size()), wall_block(cfgs.size());
  std::vector<std::vector<double>> kdur(7);  // A per-kernel durations (us), by kernel kind
  std::vector<double> a_gap;
  // warm-up ~1 s
  {
    auto t0 = std::chrono::steady_clock::now();
    while (std::chrono::steady_clock::now() - t0 < std::chrono::milliseconds(quick ? 200 : 1000)) {
      pass_sep(q, p, 0);
      q.wait();
    }
  }
  for (int round = 0; round < ROUNDS && !halt; ++round)
    for (size_t ci = 0; ci < cfgs.size() && !halt; ++ci) {
      const Cfg& c = cfgs[ci];
      if (c.kind == 2 || c.kind == 3) reset_ctl();
      auto one_pass = [&](sycl::queue& qq, std::vector<sycl::event>* all) -> std::pair<sycl::event, sycl::event> {
        if (c.kind == 0) return pass_sep(qq, p, 0, all);
        if (c.kind == 1) return pass_sep(qq, p, 1, all);
        if (c.kind == 4) return pass_sep(qq, p, 2, all);
        sycl::event e = launch_p(qq, c.kind - 2, c.pc);
        return {e, e};
      };
      // profiled
      busy(q, sink, iters);
      std::vector<std::pair<sycl::event, sycl::event>> ev;
      std::vector<sycl::event> all;
      for (int i = 0; i < PASSES; ++i) ev.push_back(one_pass(q, c.kind == 0 && round == ROUNDS - 1 ? &all : nullptr));
      q.wait();
      if ((c.kind == 2 || c.kind == 3) && read_err()) {
        halt = true;
        break;
      }
      const double span = t_end(ev[PASSES - 1].second) - t_end(ev[SKIP - 1].second);
      per_block[ci].push_back(span / double((PASSES - SKIP) * NSET) / 1e3);
      if (!all.empty()) {
        const int per = 6;
        for (size_t i = size_t(SKIP) * NSET * per; i < all.size(); ++i) {
          kdur[i % per].push_back(ev_ns(all[i]) / 1e3);
          if (i > 0) a_gap.push_back((t_start(all[i]) - t_end(all[i - 1])) / 1e3);
        }
      }
      // unprofiled wall: busy + passes minus busy alone
      if (c.kind == 2 || c.kind == 3) reset_ctl();
      auto w0 = std::chrono::steady_clock::now();
      busy(qn, sink, iters);
      for (int i = 0; i < PASSES; ++i) {
        if (c.kind == 0) pass_sep(qn, p, 0);
        else if (c.kind == 1) pass_sep(qn, p, 1);
        else if (c.kind == 4) pass_sep(qn, p, 2);
        else launch_p(qn, c.kind - 2, c.pc);
      }
      qn.wait();
      auto w1 = std::chrono::steady_clock::now();
      busy(qn, sink, iters);
      qn.wait();
      auto w2 = std::chrono::steady_clock::now();
      if ((c.kind == 2 || c.kind == 3) && read_err()) {
        halt = true;
        break;
      }
      const double wall = std::chrono::duration<double, std::micro>((w1 - w0) - (w2 - w1)).count();
      wall_block[ci].push_back(wall / double(PASSES * NSET));
    }
  std::printf(",\"timing\":[");
  for (size_t ci = 0; ci < cfgs.size(); ++ci)
    std::printf("%s{\"version\":\"%s\",\"wg\":%u,\"nwg\":%u,\"us_per_block\":%.3f,\"p10\":%.3f,\"p90\":%.3f,"
                "\"wall_noprof_us_per_block\":%.3f,\"wall_p10\":%.3f,\"wall_p90\":%.3f,\"rounds\":%zu}",
                ci ? "," : "", cfgs[ci].name.c_str(), cfgs[ci].pc.wgs, cfgs[ci].pc.nwg, pct(per_block[ci], 0.5), pct(per_block[ci], 0.1),
                pct(per_block[ci], 0.9), pct(wall_block[ci], 0.5), pct(wall_block[ci], 0.1), pct(wall_block[ci], 0.9),
                per_block[ci].size());
  const char* kn[6] = {"norm.partial", "norm.out", "low+inject", "act", "gate", "mix"};
  std::printf("],\"A_kernels_us\":{");
  for (int i = 0; i < 6; ++i)
    std::printf("%s\"%s\":{\"p50\":%.3f,\"p10\":%.3f,\"p90\":%.3f}", i ? "," : "", kn[i], pct(kdur[i], 0.5),
                pct(kdur[i], 0.1), pct(kdur[i], 0.9));
  std::printf("},\"A_gap_us\":{\"p50\":%.3f,\"p90\":%.3f},\"busy_iters\":%u,\"halt\":%d,\"final_err\":%u}\n",
              pct(a_gap, 0.5), pct(a_gap, 0.9), iters, halt, read_err());
  return halt ? 4 : 0;
}
