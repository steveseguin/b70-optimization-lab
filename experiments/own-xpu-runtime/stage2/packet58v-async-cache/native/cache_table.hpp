#pragma once
// Lab-authored immutable-weight cache. Idea credit: Niko1221 / Strata's
// hot-expert cache description; no implementation code was imported.
#include <algorithm>
#include <cstdint>
#include <limits>
#include <stdexcept>
#include <vector>

namespace p58 {
struct Entry { uint64_t gate{}, up{}, down{}, generation{}; };
static_assert(sizeof(Entry) == 32);
struct Expert {
  uint64_t host_gate{}, host_up{}, host_down{};
  uint64_t gate_bytes{}, up_bytes{}, down_bytes{};
};
struct Fill {
  uint32_t expert{};
  uint64_t offset{}, bytes{};
  // Immutable pinned sources; destination = arena+offset, then +gate/up bytes.
  uint64_t gate{}, up{}, down{};
};
struct Plan {
  uint64_t epoch{};
  std::vector<Fill> fills;
  std::vector<Entry> table;
  uint64_t fill_bytes{}, evictions{};
};

// Single coordinator thread. No hardware calls or allocations of weight memory.
// The native adapter MUST fence compute before finish_position, order every
// copy in fills, wait for every copy before publishing the new table, then fence
// table publication before commit. False completion is rejected by this mock;
// true completion is a claim made by the native event adapter, not a GPU probe.
class Cache {
  struct Block { uint64_t offset{}, bytes{}; };
  struct Resident { bool present{}; uint64_t offset{}, bytes{}, recent{}; };
  enum class Phase { idle, running, ready, updating, closed };
  std::vector<Expert> experts_;
  std::vector<Resident> live_, staged_;
  std::vector<Entry> table_, pending_;
  std::vector<Block> free_, staged_free_;
  uint64_t base_{}, capacity_{}, epoch_{}, clock_{}, staged_clock_{};
  Phase phase_{Phase::idle};
  static uint64_t add(uint64_t a, uint64_t b) {
    if (b > std::numeric_limits<uint64_t>::max()-a) throw std::overflow_error("cache integer overflow");
    return a+b;
  }
  static uint64_t aligned(uint64_t n) { return add(n,255)&~uint64_t(255); }
  static void require(bool good, const char* why) { if(!good) throw std::logic_error(why); }
  uint64_t bytes(uint32_t id) const {
    auto& e=experts_.at(id); return add(add(e.gate_bytes,e.up_bytes),e.down_bytes);
  }
  Entry host(uint32_t id,uint64_t generation) const {
    auto& e=experts_.at(id); return {e.host_gate,e.host_up,e.host_down,generation};
  }
  static void release(std::vector<Block>& free, Block block) {
    free.push_back(block);
    std::sort(free.begin(),free.end(),[](auto a,auto b){return a.offset<b.offset;});
    std::vector<Block> merged;
    for(auto b:free) {
      if(!merged.empty() && add(merged.back().offset,merged.back().bytes)==b.offset)
        merged.back().bytes=add(merged.back().bytes,b.bytes);
      else merged.push_back(b);
    }
    free.swap(merged);
  }
public:
  Cache(std::vector<Expert> experts,uint64_t device_base,uint64_t capacity)
    :experts_(std::move(experts)),live_(experts_.size()),base_(device_base),capacity_(capacity) {
    require(experts_.size()<=std::numeric_limits<uint32_t>::max(),"expert ID overflow");
    require(capacity==0 || (base_!=0 && base_%256==0),"arena must be 256-byte aligned");
    add(base_,capacity_);
    for(uint32_t i=0;i<experts_.size();++i) {
      auto& e=experts_[i];
      require(e.host_gate&&e.host_up&&e.host_down,"missing pinned expert projection");
      require(e.gate_bytes&&e.up_bytes&&e.down_bytes,"empty expert projection");
      add(e.host_gate,e.gate_bytes);add(e.host_up,e.up_bytes);add(e.host_down,e.down_bytes);
      aligned(bytes(i));table_.push_back(host(i,1));
    }
    if(capacity_)free_.push_back({0,capacity_});
  }
  Cache(const Cache&)=delete;
  Cache& operator=(const Cache&)=delete;
  const std::vector<Entry>& table() const { require(phase_!=Phase::closed,"closed cache"); return table_; }
  const std::vector<Expert>& experts() const { return experts_; }
  uint64_t capacity() const { return capacity_; }
  // Observe every position, even while an unpublished transaction owns slots.
  // This touches CPU recency only; it never publishes pointers or starts DMA.
  void observe(const std::vector<uint32_t>& routes) {
    require(phase_==Phase::idle||phase_==Phase::updating,"route observation phase");
    auto& rows=phase_==Phase::updating?staged_:live_;
    auto& clock=phase_==Phase::updating?staged_clock_:clock_;
    for(auto id:routes){require(id<experts_.size(),"route outside expert table");rows[id].recent=clock=add(clock,1);}
  }
  uint64_t resident_bytes() const { uint64_t n=0;for(auto r:live_)if(r.present)n=add(n,r.bytes);return n; }
  bool resident(uint32_t id) const { return live_.at(id).present; }
  bool matches(uint32_t id, const Entry& entry) const {
    if(phase_==Phase::closed || id>=table_.size())return false;
    auto& t=table_[id];return entry.generation==t.generation && entry.gate==t.gate && entry.up==t.up && entry.down==t.down;
  }
  uint64_t begin_position() {
    require(phase_==Phase::idle,"position requires published table and completed fills");
    epoch_=add(epoch_,1);phase_=Phase::running;return epoch_;
  }
  void finish_position(uint64_t epoch,bool compute_complete) {
    require(phase_==Phase::running&&epoch==epoch_,"wrong compute epoch/state");
    require(compute_complete,"compute still owns cache slots/pinned sources");phase_=Phase::ready;
  }
  // Empty cache is the content-independent initial policy. Optional initial
  // fills may call prepare before first begin_position; caller must record IDs.
  Plan prepare(const std::vector<uint32_t>& routes) {
    require(phase_==Phase::idle||phase_==Phase::ready,"cache mutation during compute/update");
    for(auto id:routes)require(id<experts_.size(),"route outside expert table");
    auto next=live_;auto free=free_;auto table=table_;uint64_t clock=clock_;
    Plan p;p.epoch=epoch_;
    // Touch every route before eviction so earlier-layer residents cannot be
    // evicted merely because the CPU visits later-layer admissions first.
    for(auto id:routes)next[id].recent=clock=add(clock,1);
    for(auto id:routes) {
      if(next[id].present)continue;
      auto n=aligned(bytes(id));if(n>capacity_)continue; // exact host miss stays valid
      auto fitting=[&](){return std::find_if(free.begin(),free.end(),[&](auto b){return b.bytes>=n;});};
      auto fit=fitting();
      while(fit==free.end()) {
        size_t victim=next.size();
        for(size_t i=0;i<next.size();++i)
          if(next[i].present&&(victim==next.size()||next[i].recent<next[victim].recent))victim=i;
        require(victim!=next.size(),"arena accounting lost a free extent");
        auto old=next[victim];release(free,{old.offset,old.bytes});next[victim].present=false;
        table[victim]=host(uint32_t(victim),add(table[victim].generation,1));++p.evictions;
        fit=fitting();
      }
      uint64_t off=fit->offset;fit->offset=add(off,n);fit->bytes-=n;if(!fit->bytes)free.erase(fit);
      next[id]={true,off,n,next[id].recent};auto& e=experts_[id];
      uint64_t gate=add(base_,off),up=add(gate,e.gate_bytes),down=add(up,e.up_bytes);
      table[id]={gate,up,down,add(table[id].generation,1)};
      p.fills.push_back({id,off,bytes(id),e.host_gate,e.host_up,e.host_down});p.fill_bytes=add(p.fill_bytes,bytes(id));
    }
    p.table=table;staged_=std::move(next);staged_free_=std::move(free);pending_=std::move(table);staged_clock_=clock;
    phase_=Phase::updating;return p;
  }
  void commit(uint64_t epoch,bool copies_complete,bool table_publication_complete) {
    require(phase_==Phase::updating&&epoch==epoch_,"wrong update epoch/state");
    require(copies_complete,"copy engine still owns victim slots/pinned sources");
    require(table_publication_complete,"new device table has not passed its publication fence");
    live_.swap(staged_);free_.swap(staged_free_);table_.swap(pending_);clock_=staged_clock_;
    staged_.clear();staged_free_.clear();pending_.clear();phase_=Phase::idle;
  }
  // After a failed copy/publication, no rollback to the old table is safe: its
  // victims may have been overwritten. Keep updating and drain/close_failed.
  void close_failed(bool all_queues_drained) {
    require(phase_==Phase::updating,"failed-close requires an unfinished update");
    require(all_queues_drained,"cannot free pinned/cache memory with outstanding work");phase_=Phase::closed;
  }
  void close() {
    require(phase_==Phase::idle||phase_==Phase::ready,"cannot close with outstanding work");phase_=Phase::closed;
  }
};
} // namespace p58
