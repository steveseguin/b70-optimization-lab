// Metadata-only tests. Synthetic integer addresses are never dereferenced.
#include "../packet181-session-swap-v3/one-card/native-source/repo/experiments/own-xpu-runtime/stage2/packet58aj-onecard-resident/native/cache_protocol.hpp"
#include <iostream>
#include <string>

static void require(bool condition, const char* message) {
  if (!condition) throw std::runtime_error(message);
}
template<class Function> static bool refuses(Function action) {
  try { action(); } catch (const std::logic_error&) { return true; }
  return false;
}
static std::vector<p58::Expert> experts() {
  std::vector<p58::Expert> result;
  for (uint64_t i = 0; i < 4; ++i) {
    const auto address = 0x100000 + i * 0x1000;
    result.push_back({address, address + 64, address + 128, 64, 64, 64});
  }
  return result;
}
static bool same(const std::vector<p58::Entry>& a, const std::vector<p58::Entry>& b) {
  if (a.size() != b.size()) return false;
  for (size_t i = 0; i < a.size(); ++i)
    if (a[i].gate != b[i].gate || a[i].up != b[i].up ||
        a[i].down != b[i].down || a[i].generation != b[i].generation) return false;
  return true;
}
static void direct_chunk() {
  p58::Cache cache(experts(), 0x200000, 512);
  const auto before = cache.table();
  const auto epoch = cache.begin_position();
  require(refuses([&] { cache.prepare({0, 2, 1, 3}); }), "prepare during read ownership");
  require(refuses([&] { cache.reset_capacity(256); }), "reset during read ownership");
  require(refuses([&] { cache.finish_position(epoch + 1, true); }), "wrong epoch admitted");
  require(refuses([&] { cache.finish_position(epoch, false); }), "false compute completion admitted");
  require(same(before, cache.table()), "published table changed during read ownership");
  cache.finish_position(epoch, true); // Simulated completion, never a device fact.
  require(refuses([&] { cache.observe({0}); }), "observe incorrectly accepted ready phase");
  const auto plan = cache.prepare({0, 2, 1, 3});
  require(same(before, cache.table()), "unpublished plan changed live table");
  require(refuses([&] { cache.begin_position(); }), "new reader during direct update");
  require(refuses([&] { cache.commit(plan.epoch, false, true); }), "unfinished copy committed");
  require(refuses([&] { cache.commit(plan.epoch, true, false); }), "unfinished publication committed");
  cache.commit(plan.epoch, true, true);
  require(!same(before, cache.table()), "publication did not change table");
  require(!cache.matches(1, before[1]), "stale pointer generation still matches");
  require(cache.resident(1) && cache.resident(3) && !cache.resident(0) && !cache.resident(2),
          "chronological routes chose unexpected victims");
  cache.close();
}
static void route_order_matters() {
  p58::Cache chronological(experts(), 0x200000, 512);
  p58::Cache layer_major(experts(), 0x200000, 512);
  // Two rows, two layers, one route each. Row-major capture is 0,2 then 1,3.
  const auto a = chronological.prepare({0, 2, 1, 3});
  const auto b = layer_major.prepare({0, 1, 2, 3});
  chronological.commit(a.epoch, true, true);
  layer_major.commit(b.epoch, true, true);
  require(chronological.resident(1) && !chronological.resident(2), "row-major fixture vacuous");
  require(layer_major.resident(2) && !layer_major.resident(1), "layer-major negative did not differ");
  require(!same(chronological.table(), layer_major.table()), "route ordering was invisible");
  chronological.close(); layer_major.close();
}
static void failed_update_retained() {
  p58::Cache cache(experts(), 0x200000, 512);
  cache.prepare({0, 1});
  require(refuses([&] { cache.close_failed(false); }), "failed update freed outstanding work");
  require(refuses([&] { cache.close(); }), "normal close hid unfinished update");
  require(refuses([&] { cache.begin_position(); }), "failed update automatically retried");
  cache.close_failed(true);
  require(refuses([&] { cache.table(); }), "failed closed table remains available");
}
static void overlap_is_distinct() {
  const auto e = experts();
  p58::Cache cache(e, 0x200000, 256);
  const auto initial = cache.prepare({0}); cache.commit(initial.epoch, true, true);
  const auto live = cache.table();
  p58v::Protocol protocol;
  protocol.begin();
  // Cache remains idle here: Protocol has separate read ownership.
  protocol.prepare(cache, {1});
  require(same(live, cache.table()), "overlap planning published a table");
  require(refuses([&] { protocol.revoked(cache); }), "victim revoked while readers own it");
  require(refuses([&] { protocol.end(false); }), "incomplete reader ended");
  protocol.end(true);
  const auto safe = protocol.revoked(cache);
  require(safe[0].gate == e[0].host_gate && safe[1].gate == e[1].host_gate,
          "revoked victim/new fill do not have safe host pointers");
  require(refuses([&] { protocol.submitted(false, 7); }), "fill before safe publication");
  protocol.submitted(true, 7);
  require(!protocol.may_publish(false), "incomplete fill publishable");
  require(refuses([&] { protocol.commit(cache, false, true); }), "unfinished fill committed");
  protocol.begin(); // A subsequent reader can use the already-published safe view.
  require(refuses([&] { protocol.commit(cache, true, true); }), "published during subsequent reader");
  protocol.end(true);
  require(refuses([&] { protocol.commit(cache, true, false); }), "missing publication fence admitted");
  protocol.commit(cache, true, true);
  require(cache.resident(1) && !cache.resident(0), "overlap fixture did not replace victim");
  cache.close();
}
int main() {
  try {
    direct_chunk(); route_order_matters(); failed_update_retained(); overlap_is_distinct();
    std::cout << "{\"passed\":true,\"groups\":4,\"completion_facts\":\"simulated\","
                 "\"device_executed\":false,\"production_policy_implemented\":false}\n";
  } catch (const std::exception& error) {
    std::cerr << error.what() << '\n'; return 1;
  }
}
