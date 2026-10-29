// CPU unit test for the 2026-10-28 head split (OWNRT_TP_GDN=heads): the parameterized GDN kernels run on a card's
// compact half (8 key heads, 24 value heads {h : h%16 in [8c, 8c+8)}) must reproduce, bitwise, the full-geometry
// results of the same kernels for those heads. Host twins only (no device): the generic ng::group kernels (conv,
// recurrence, gated norm) and round2::gdn_host (the host twin of the round2 device recurrence). The device kernels
// are gated on the cards by the bitwise card-vs-one-card dump.
//   g++ -std=gnu++20 -O1 -fno-fast-math -ffp-contract=off -DOWN_RT_HOST_ONLY -I ../../../engine/src heads_unit_test.cpp
#include "stage2/packet194-expert-diet-engine/round2.hpp"
#include <cstdio>
#include <cstring>
#include <random>
#include <vector>

using Runs = std::vector<std::pair<int, int>>;
constexpr int KH = 16, VH = 48, D = 128, HK = 8, QKV = (2 * KH + VH) * D;
// Same run formulas as rank.hpp (qkv channels; value-head rows times `per`).
static Runs qkv_runs(int c) {
  Runs r{{HK * c * D, HK * D}, {KH * D + HK * c * D, HK * D}};
  for (int u = 0; u < VH / KH; ++u) r.push_back({2 * KH * D + (KH * u + HK * c) * D, HK * D});
  return r;
}
static Runs value_runs(int c, int per) {
  Runs r;
#ifdef NEGATIVE_CONTROL  // contiguous value-head halves: wrong for the interleaved key mapping, must DIFFER
  r.push_back({VH / 2 * c * per, VH / 2 * per});
  return r;
#endif
  for (int u = 0; u < VH / KH; ++u) r.push_back({(KH * u + HK * c) * per, HK * per});
  return r;
}
template <class T> static std::vector<T> gather(const std::vector<T>& full, const Runs& runs, int per = 1) {
  std::vector<T> out;
  for (auto [f, n] : runs) out.insert(out.end(), full.begin() + size_t(f) * per, full.begin() + size_t(f + n) * per);
  return out;
}
template <class T> static void scatter(std::vector<T>& full, const std::vector<T>& part, const Runs& runs, int per = 1) {
  size_t at = 0;
  for (auto [f, n] : runs) {
    std::copy(part.begin() + at, part.begin() + at + size_t(n) * per, full.begin() + size_t(f) * per);
    at += size_t(n) * per;
  }
}
static bool same(const std::vector<float>& a, const std::vector<float>& b) {
  return a.size() == b.size() && !std::memcmp(a.data(), b.data(), a.size() * 4);
}
struct Run {
  std::vector<float> qkv, a, b, decay, bias, state, y, z, gated, norm, history, conv, conv_w;
  int32_t error = 0, position = 7, active = 1;
};
static ng::Args args(Run& r, std::vector<void*> slots) {
  ng::Args x;
  for (size_t i = 0; i < slots.size(); ++i) x.p[i] = slots[i];
  x.p[15] = &r.error; x.p[17] = &r.position; x.p[18] = &r.active;
  x.f32 = true;
  return x;
}
static void run_generic(ng::Shape s, ng::Args a) {
  std::vector<float> local(1024);
  for (int g = 0; g < ng::groups(s); ++g) ng::group(s, a, g, ng::HostTeam{local.data()});
}
int main() {
  std::mt19937 rng(20261028);
  std::uniform_real_distribution<float> u(-1.f, 1.f);
  auto random = [&](size_t n) { std::vector<float> v(n); for (auto& x : v) x = u(rng); return v; };
  Run full;
  full.qkv = random(QKV); full.a = random(VH); full.b = random(VH); full.decay = random(VH); full.bias = random(VH);
  full.state = random(size_t(VH) * D * D); full.z = random(VH * D); full.norm = random(D);
  full.history = random(size_t(QKV) * 3); full.conv_w = random(size_t(QKV) * 4);
  const Run input = full;
  const int flags = ng::f32_activations_flag | 16 | 8 | 4 | 2;  // the engine's GDN flags in F32 mode (94)
  int failures = 0;
  for (int variant = 0; variant < 2; ++variant) {  // 0: generic ng::group, 1: round2::gdn_host
    // Full geometry.
    Run f = input; f.y.assign(VH * D, 0.f); f.gated.assign(VH * D, 0.f); f.conv.assign(QKV, 0.f);
    ng::Shape conv{ng::conv}; conv.width = QKV; conv.extra = 1; conv.flags = ng::f32_activations_flag | 16 | 8; conv.capacity = 4096;
    run_generic(conv, args(f, {f.qkv.data(), f.history.data(), f.conv_w.data(), f.conv.data(), f.history.data()}));
    ng::Shape gdn{ng::gdn}; gdn.flags = flags; gdn.capacity = 4096;
    auto ga = args(f, {f.conv.data(), f.a.data(), f.b.data(), f.decay.data(), f.bias.data(), f.state.data(), f.y.data(), f.state.data()});
    if (variant) round2::gdn_host(gdn, ga); else run_generic(gdn, ga);
    ng::Shape gated{ng::gated_norm}; gated.heads = 48; gated.flags = ng::f32_activations_flag | 8; gated.capacity = 4096;
    run_generic(gated, args(f, {f.y.data(), f.z.data(), f.norm.data(), f.gated.data()}));
    // Two compact halves, reassembled.
    std::vector<float> conv_out(QKV), history(size_t(QKV) * 3), y(VH * D), state(size_t(VH) * D * D), out(VH * D);
    for (int c = 0; c < 2; ++c) {
      Run h;
      const Runs qr = qkv_runs(c), vr = value_runs(c, 1);
      h.qkv = gather(input.qkv, qr); h.history = gather(input.history, qr, 3); h.conv_w = gather(input.conv_w, qr, 4);
      h.a = gather(input.a, vr); h.b = gather(input.b, vr); h.decay = gather(input.decay, vr); h.bias = gather(input.bias, vr);
      h.state = gather(input.state, vr, D * D); h.z = gather(input.z, vr, D); h.norm = input.norm;
      h.conv.assign(h.qkv.size(), 0.f); h.y.assign(size_t(VH / 2) * D, 0.f); h.gated.assign(size_t(VH / 2) * D, 0.f);
      ng::Shape hc = conv; hc.width = int(h.qkv.size());
      run_generic(hc, args(h, {h.qkv.data(), h.history.data(), h.conv_w.data(), h.conv.data(), h.history.data()}));
      ng::Shape hg = gdn; hg.extra = HK; hg.heads = VH / 2;
      ng::validate(hg);
      auto ha = args(h, {h.conv.data(), h.a.data(), h.b.data(), h.decay.data(), h.bias.data(), h.state.data(), h.y.data(), h.state.data()});
      if (variant) round2::gdn_host(hg, ha); else run_generic(hg, ha);
      ng::Shape hn = gated; hn.heads = VH / 2;
      run_generic(hn, args(h, {h.y.data(), h.z.data(), h.norm.data(), h.gated.data()}));
      if (h.error) { std::printf("card %d sticky error\n", c); ++failures; }
      scatter(conv_out, h.conv, qr); scatter(history, h.history, qr, 3); scatter(y, h.y, vr, D);
      scatter(state, h.state, vr, D * D); scatter(out, h.gated, vr, D);
    }
    const char* name = variant ? "round2::gdn_host" : "ng::group";
    const bool ok = !f.error && same(conv_out, f.conv) && same(history, f.history) && same(y, f.y) && same(state, f.state) && same(out, f.gated);
    std::printf("%s: conv %d history %d y %d state %d gated %d -> %s\n", name, same(conv_out, f.conv), same(history, f.history),
                same(y, f.y), same(state, f.state), same(out, f.gated), ok ? "bitwise equal" : "DIFFER");
    failures += !ok;
    // Sanity: the full-geometry required bytes are unchanged by the parameterization.
    auto n = ng::required_bytes(gdn);
    if (n[0] != size_t(QKV) * 4 || n[1] != 48 * 4 || n[6] != 6144 * 4 || ng::groups(gdn) != 6144 || ng::groups(gated) != 48 ||
        round2::gdn_prep_floats_for(gdn) != round2::gdn_prep_floats) { std::printf("full-geometry extents changed\n"); ++failures; }
  }
  std::printf("%s\n", failures ? "FAIL" : "PASS");
  return failures ? 1 : 0;
}
