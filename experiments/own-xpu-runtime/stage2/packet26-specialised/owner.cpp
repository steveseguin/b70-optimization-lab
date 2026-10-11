#include "owner.hpp"
#include <algorithm>
#include <atomic>
#include <condition_variable>
#include <cstdio>
#include <limits>
#include <mutex>
#include <map>
#include <array>
#include <unordered_map>
#include <sstream>
#include <stdexcept>

namespace ownrt {
namespace {
// Bounded handle ring. Each slot carries its full generation; collisions fail closed.
struct EventSlot { Event handle=0; int queue=-1; };
static std::array<EventSlot,65536> event_queue;
static void remember(Event e,int q) {
  auto& slot=event_queue[e%event_queue.size()];
  if(slot.handle && slot.handle!=e)throw std::length_error("active event ring collision");
  slot={e,q};
}
static int event_card(Event e) {
  const auto& slot=event_queue[e%event_queue.size()];
  if(slot.handle!=e)throw std::invalid_argument("foreign or retired event");
  return slot.queue;
}
struct Bound { std::vector<Allocation> ids; std::vector<void*> pointers; int queue; };
struct FastOwner { std::unordered_multimap<size_t,Bound> bindings; CopyAudit copies; };
static std::map<const Device*,FastOwner> fast_owners;
static std::map<const Device*,Receipt> retained_receipts;
static size_t binding_hash(std::span<const Allocation> ids) {
  size_t h=1469598103934665603ull;
  for(auto id:ids)h=(h^id)*1099511628211ull;
  return h;
}
int queue_of(const Row& r) {
  if(r.memory!=Memory::device)return -1;
  return r.label.starts_with("card1:")?1:0;
}
void assert_local_dependencies(std::span<const Event> deps,int queue) {
  for(auto e:deps)if(event_card(e)!=queue)
    throw std::logic_error("foreign-queue dependency rejected by owner");
}
}

CopyAudit copy_audit(const Device& d) {return fast_owners.at(&d).copies;}
std::uint64_t next_handle() {static std::atomic<std::uint64_t> n{1}; return n.fetch_add(1);}
std::string quote(const std::string& value) {
  std::ostringstream out; out << '"';
  for (unsigned char c : value) {
    if (c == '"' || c == '\\') out << '\\' << c;
    else if (c < 32) { char b[7]; std::snprintf(b, sizeof b, "\\u%04x", c); out << b; }
    else out << c;
  }
  return out.str() + '"';
}
const char* name(Memory m) {
  switch(m) { case Memory::device:return "device"; case Memory::pinned:return "host-pinned";
    case Memory::shadow:return "host-shadow"; } throw std::invalid_argument("memory");
}
const char* name(Category c) {
  switch(c) {
    case Category::weights:return "weights"; case Category::kv:return "KV";
    case Category::recurrent:return "recurrent-state"; case Category::scratch:return "workspace";
    case Category::graph_static:return "graph-static"; case Category::pinned_slab:return "pinned-copy-slab";
    case Category::output_ring:return "output-ring"; case Category::loader_staging:return "loader-staging";
    case Category::host_shadow:return "host-shadow"; case Category::runtime_overhead:return "runtime-overhead";
  } throw std::invalid_argument("category");
}
const char* name(Lifetime l) {
  switch(l) { case Lifetime::process:return "process"; case Lifetime::request:return "request";
    case Lifetime::transaction:return "transaction"; case Lifetime::graph:return "graph";
    case Lifetime::transfer:return "transfer"; } throw std::invalid_argument("lifetime");
}
static Lifetime planned(Category c) {
  switch(c) {
    case Category::weights: case Category::host_shadow: case Category::runtime_overhead:return Lifetime::process;
    case Category::kv: case Category::recurrent: case Category::output_ring:return Lifetime::request;
    case Category::scratch:return Lifetime::transaction;
    case Category::graph_static:return Lifetime::graph;
    case Category::pinned_slab: case Category::loader_staging:return Lifetime::transfer;
  } throw std::invalid_argument("category");
}
static int group(Category c) {
  if(c == Category::weights) return 2;
  if(c == Category::kv || c == Category::recurrent) return 1;
  if(c == Category::pinned_slab || c == Category::loader_staging || c == Category::host_shadow) return 3;
  return 0;
}
std::string Receipt::json() const {
  std::ostringstream o;
  o << "{\"schema\":\"own-xpu-runtime.teardown.v1\",\"backend\":" << quote(backend)
    << ",\"status\":" << quote(status) << ",\"exit_code\":" << exit_code
    << ",\"safe_to_exit\":" << (safe_to_exit?"true":"false")
    << ",\"idle_marker_complete\":" << (idle_marker_complete?"true":"false")
    << ",\"in_flight\":" << in_flight << ",\"live_bytes\":" << live_bytes
    << ",\"error\":" << quote(error) << ",\"sequence\":[";
  for(std::size_t i=0;i<sequence.size();++i) o << (i?",":"") << quote(sequence[i]);
  return o.str()+"]}";
}
Device::Device(std::unique_ptr<Backend> b):backend_(std::move(b)),arena(*this) {
  if(!backend_) throw std::invalid_argument("null backend");
  events_.reserve(16384);fast_owners[this].bindings.reserve(4096);
}
[[noreturn]] void hold_for_supervisor() {
  std::fputs("Teardown incomplete; ownership retained; supervisor action required.\n", stderr);
  std::mutex m; std::unique_lock lock(m); std::condition_variable cv;
  cv.wait(lock, []{return false;}); std::abort(); // unreachable
}
void forget_event_queues(std::span<const Event> events) {for(auto e:events) {auto& slot=event_queue[e%event_queue.size()];if(slot.handle==e)slot={};}}
Device::~Device() {
  if(closed_) {fast_owners.erase(this);retained_receipts.erase(this);return;}
  try { if(shutdown(std::chrono::seconds(60)).safe_to_exit) {fast_owners.erase(this);return;} }
  catch(...) {}
  hold_for_supervisor();
}
std::string Device::identity() const {return backend_->identity();}
void Device::admit() const {
  if(quiescing_ || !fault_.empty()) throw std::logic_error("admission closed");
  if(events_.size() >= 16384) throw std::length_error("event ledger full; end this bounded smoke");
}
void Device::validate(std::span<const Event> deps) const {
  for(auto e:deps) if(!std::binary_search(events_.begin(),events_.end(),e))
    throw std::invalid_argument("foreign dependency");
}
std::size_t Device::in_flight() {
  return std::count_if(events_.begin(),events_.end(),[&](auto e){return !backend_->complete(e);});
}
bool Device::wait(Event e,std::chrono::milliseconds timeout) {
  validate(std::span(&e,1));
  return backend_->wait(e,std::chrono::steady_clock::now()+timeout);
}
EventTiming Device::timing(Event e) {
  validate(std::span(&e,1));
  if(!backend_->complete(e)) throw std::logic_error("profiling before completion");
  return backend_->timing(e);
}
Event Device::compute(const Operation& op, std::span<const Allocation> buffers, std::span<const Event> deps) {
  admit(); validate(deps);
  if(buffers.empty()) throw std::invalid_argument("empty compute bindings");
  auto& cache=fast_owners.at(this).bindings;
  auto h=binding_hash(buffers);auto range=cache.equal_range(h);
  const Bound* bound=nullptr;
  for(auto it=range.first;it!=range.second;++it)
    if(it->second.ids.size()==buffers.size() && std::equal(buffers.begin(),buffers.end(),it->second.ids.begin())) {bound=&it->second;break;}
  if(!bound) {
    Bound fresh;fresh.ids.assign(buffers.begin(),buffers.end());fresh.pointers.reserve(buffers.size());
    fresh.queue=queue_of(arena.row(buffers.front()));
    for(auto id:buffers) {
      const auto& r=arena.row(id);
      if(!r.live || r.memory!=Memory::device)throw std::logic_error("compute requires live device allocation");
      if(queue_of(r)!=fresh.queue)throw std::logic_error("foreign compute allocation");
      fresh.pointers.push_back(r.pointer);
    }
    bound=&cache.emplace(h,std::move(fresh))->second;
  }
  // Stack-only dependency construction. Cross-card validation remains mandatory.
  std::array<Event,65> storage{};
  if(deps.size()>64)throw std::length_error("dependency bound");
  std::copy(deps.begin(),deps.end(),storage.begin());size_t n=deps.size();
  if(!events_.empty())storage[n++]=events_.back();
  std::span<const Event> chain(storage.data(),n);
  assert_local_dependencies(chain,bound->queue);
  try {
    auto e=backend_->compute(op,bound->pointers,chain); events_.push_back(e); remember(e,bound->queue); return e;
  } catch(const std::exception& e) {fault_=e.what(); throw;}
}
bool Device::drain(Deadline end) {
  // Visit every event, even if one fails, preserving a single total deadline.
  bool ok=true;
  for(auto e:events_) if(!backend_->wait(e,end)) ok=false;
  if(ok) backend_->synchronize();
  return ok;
}
void Device::graph(std::string label,std::vector<Allocation> buffers,std::function<void()> destroy) {
  admit(); if(!destroy) throw std::invalid_argument("missing graph destructor");
  for(auto id:buffers) {
    const auto& r=arena.row(id);
    if(!r.live || r.lifetime==Lifetime::transaction || r.lifetime==Lifetime::transfer)
      throw std::logic_error("graph would outlive buffer");
  }
  graphs_.push_back({std::move(label),std::move(buffers),std::move(destroy)});
}
Receipt Device::receipt(std::string error) {
  Receipt r; r.backend=identity(); r.safe_to_exit=closed_; r.idle_marker_complete=idle_;
  r.status=closed_?"complete":"refused"; r.exit_code=closed_?0:75;
  try {r.in_flight=in_flight();} catch(...) {r.in_flight=events_.size();}
  r.sequence=sequence_; r.error=std::move(error);
  for(auto m:{Memory::device,Memory::pinned,Memory::shadow}) r.live_bytes+=arena.total(m);
  return r;
}
Receipt Device::shutdown(std::chrono::milliseconds timeout) {
  if(closed_) {auto it=retained_receipts.find(this);return it==retained_receipts.end()?receipt():it->second;}
  // Synchronous failure before submission is not in-flight work.
  if(!quiescing_) { quiescing_=true; sequence_.push_back("quiesce"); }
  auto end=timeout==std::chrono::milliseconds::max()?Deadline::max():std::chrono::steady_clock::now()+timeout;
  try {
    if(!drain(end)) return receipt("in-flight work; no release or exit allowed");
    sequence_.push_back("drain");
    while(!graphs_.empty()) {
      graphs_.back().destroy(); sequence_.push_back("graph:"+graphs_.back().label); graphs_.pop_back();
    }
    sequence_.push_back("graphs-released");
    for(int g=0;g<4;++g) arena.release_group(g);
    if(!final_marker_) { events_.reserve(events_.size()+1); final_marker_=backend_->marker({}); events_.push_back(final_marker_); }
    if(!backend_->wait(final_marker_,end)) return receipt("final idle marker pending; queue/context retained");
    backend_->synchronize(); idle_=true; sequence_.push_back("idle-marker-complete");
    backend_->clear_events(); forget_event_queues(events_); events_.clear(); sequence_.push_back("events-released");
    backend_->close_queue(); sequence_.push_back("queue-released");
    backend_->close_context(); sequence_.push_back("context-released"); closed_=true;
    auto r=receipt(fault_);if(!fault_.empty()){r.status="failed-drained";r.exit_code=1;}return r;
  } catch(const std::exception& e) {
    fault_=e.what();auto r=receipt(fault_);
    if(!r.in_flight) {r.safe_to_exit=true;r.exit_code=1;closed_=true;retained_receipts[this]=r;backend_.release();}
    return r;
  }
}
Allocation Arena::allocate(std::string label,std::size_t bytes,Memory m,Category c,Lifetime l) {
  owner_.admit(); name(m); name(c); name(l);
  if(label.empty() || !bytes) throw std::invalid_argument("empty allocation");
  if(planned(c)!=l) throw std::logic_error("category lifetime violation");
  if((c==Category::pinned_slab && m!=Memory::pinned) || (c==Category::host_shadow && m!=Memory::shadow))
    throw std::logic_error("category memory violation");
  for(const auto& r:rows_) if(r.live && r.label==label) throw std::logic_error("duplicate allocation label");
  if(bytes>std::numeric_limits<std::size_t>::max()-total(m)) throw std::overflow_error("census overflow");
  if(rows_.size()==rows_.capacity())rows_.reserve(std::max(size_t(64),rows_.size()*2));
  void* ptr=owner_.backend_->allocate(bytes,m); if(!ptr) throw std::bad_alloc();
  Allocation id=next_handle();
  rows_.push_back({id,std::move(label),c,l,m,bytes,ptr,true}); return id;
}
const Row& Arena::row(Allocation id) const {
  auto it=std::lower_bound(rows_.begin(),rows_.end(),id,[](const Row& r,Allocation v){return r.id<v;});
  if(it!=rows_.end() && it->id==id)return *it;
  throw std::out_of_range("foreign allocation id");
}
void Arena::release(Allocation id) {
  const auto& r=row(id); if(!r.live) throw std::logic_error("double release");
  if(owner_.in_flight()) throw std::logic_error("buffer release with work in flight");
  for(const auto& g:owner_.graphs_) if(std::find(g.buffers.begin(),g.buffers.end(),id)!=g.buffers.end())
    throw std::logic_error("buffer still referenced by graph");
  fast_owners.at(&owner_).bindings.clear(); // changing bindings invalidate all cached leases
  owner_.backend_->release(r.pointer,r.memory);
  for(auto& found:rows_) if(found.id==id) found.live=false;
  owner_.sequence_.push_back("free:"+std::string(name(r.category))+":"+r.label);
}
void Arena::release_group(int g) { for(const auto& r:rows_) if(r.live && group(r.category)==g) release(r.id); }
std::size_t Arena::total(Memory m) const {
  std::size_t n=0; for(const auto& r:rows_) if(r.live && r.memory==m) n+=r.bytes; return n;
}
std::string Arena::census() const {
  std::ostringstream o; o << "{\"schema\":\"own-xpu-runtime.census.v1\",\"totals\":{";
  bool comma=false; for(auto m:{Memory::device,Memory::pinned,Memory::shadow}) {
    o << (comma?",":"") << quote(name(m)) << ':' << total(m); comma=true;
  }
  o << "},\"allocations\":["; comma=false;
  for(const auto& r:rows_) {
    o << (comma?",":"") << "{\"id\":" << r.id << ",\"label\":" << quote(r.label)
      << ",\"category\":" << quote(name(r.category)) << ",\"lifetime\":" << quote(name(r.lifetime))
      << ",\"memory\":" << quote(name(r.memory)) << ",\"bytes\":" << r.bytes
      << ",\"live\":" << (r.live?"true":"false") << '}'; comma=true;
  }
  // Driver shadows/pools cannot be inferred from our requested allocations.
  return o.str()+"],\"unmeasured_driver_shadow_bytes\":null,\"unmeasured_library_pool_bytes\":null}";
}
CopyEngine::CopyEngine(Device& d,std::size_t limit,std::size_t depth):owner_(d),limit_(limit),depth_(depth) {
  if(!limit || limit>128ull*1024*1024 || !depth || depth>2) throw std::invalid_argument("copy bound");
}
Event CopyEngine::copy(Allocation dst,std::size_t off,Allocation src,std::size_t soff,std::size_t n,std::span<const Event> deps) {
  owner_.admit(); owner_.validate(deps);
  // All copies are explicitly chained; pinned-slab reuse is bounded by caller waits.
  const auto& d=owner_.arena.row(dst); const auto& s=owner_.arena.row(src);
  if(!n || n>limit_ || !d.live || !s.live || off>d.bytes || n>d.bytes-off || soff>s.bytes || n>s.bytes-soff)
    throw std::out_of_range("copy extent/lifetime");
  if(dst==src) throw std::invalid_argument("aliased copy unsupported");
  int dq=queue_of(d),sq=queue_of(s),queue=dq>=0?dq:sq>=0?sq:0;
  if(dq>=0&&sq>=0&&dq!=sq&&owner_.in_flight())
    throw std::logic_error("peer copy requires both queues drained on host");
  // All submissions on this card are serialized with explicit dependencies.
  std::array<Event,65> storage{};
  if(deps.size()>64)throw std::length_error("dependency bound");
  std::copy(deps.begin(),deps.end(),storage.begin());size_t ndep=deps.size();
  if(!owner_.events_.empty())storage[ndep++]=owner_.events_.back();
  std::span<const Event> chain(storage.data(),ndep);
  assert_local_dependencies(chain,queue);

  try {
    auto e=owner_.backend_->copy(static_cast<std::byte*>(d.pointer)+off,static_cast<const std::byte*>(s.pointer)+soff,n,chain);
    auto& copies=fast_owners.at(&owner_).copies;
    if(dq>=0&&sq>=0) {if(dq==sq)++copies.device_local[queue];else ++copies.peer[queue];}
    else if(dq>=0)++copies.host_to_device[queue];else if(sq>=0)++copies.device_to_host[queue];
    owner_.events_.push_back(e); remember(e,queue); return e;
  } catch(const std::exception& e) {owner_.fault_=e.what(); throw;}
}
}
