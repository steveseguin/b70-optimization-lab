#include "owner.hpp"
#include <algorithm>
#include <atomic>
#include <condition_variable>
#include <cstdio>
#include <limits>
#include <mutex>
#include <sstream>
#include <stdexcept>

namespace ownrt {
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
}
[[noreturn]] void hold_for_supervisor() {
  std::fputs("Teardown incomplete; ownership retained; supervisor action required.\n", stderr);
  std::mutex m; std::unique_lock lock(m); std::condition_variable cv;
  cv.wait(lock, []{return false;}); std::abort(); // unreachable
}
Device::~Device() {
  if(closed_) return;
  try { if(shutdown(std::chrono::milliseconds::max()).safe_to_exit) return; }
  catch(...) {}
  hold_for_supervisor();
}
std::string Device::identity() const {return backend_->identity();}
void Device::admit() const {
  if(quiescing_ || !fault_.empty()) throw std::logic_error("admission closed");
  if(events_.size() >= 4096) throw std::length_error("event ledger full; end this bounded smoke");
}
void Device::validate(std::span<const Event> deps) const {
  for(auto e:deps) if(std::find(events_.begin(),events_.end(),e)==events_.end())
    throw std::invalid_argument("foreign dependency");
}
std::size_t Device::in_flight() {
  return std::count_if(events_.begin(),events_.end(),[&](auto e){return !backend_->complete(e);});
}
bool Device::wait(Event e,std::chrono::milliseconds timeout) {
  validate(std::span(&e,1));
  return backend_->wait(e,std::chrono::steady_clock::now()+timeout);
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
  if(closed_) return receipt();
  if(!fault_.empty()) return receipt(fault_); // native error: no cleanup retry
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
    if(!final_marker_) { events_.reserve(events_.size()+1); final_marker_=backend_->marker(events_); events_.push_back(final_marker_); }
    if(!backend_->wait(final_marker_,end)) return receipt("final idle marker pending; queue/context retained");
    backend_->synchronize(); idle_=true; sequence_.push_back("idle-marker-complete");
    backend_->clear_events(); events_.clear(); sequence_.push_back("events-released");
    backend_->close_queue(); sequence_.push_back("queue-released");
    backend_->close_context(); sequence_.push_back("context-released"); closed_=true;
    return receipt();
  } catch(const std::exception& e) {fault_=e.what(); return receipt(fault_);}
}
Allocation Arena::allocate(std::string label,std::size_t bytes,Memory m,Category c,Lifetime l) {
  owner_.admit(); name(m); name(c); name(l);
  if(label.empty() || !bytes) throw std::invalid_argument("empty allocation");
  if(planned(c)!=l) throw std::logic_error("category lifetime violation");
  if((c==Category::pinned_slab && m!=Memory::pinned) || (c==Category::host_shadow && m!=Memory::shadow))
    throw std::logic_error("category memory violation");
  for(const auto& r:rows_) if(r.live && r.label==label) throw std::logic_error("duplicate allocation label");
  if(bytes>std::numeric_limits<std::size_t>::max()-total(m)) throw std::overflow_error("census overflow");
  rows_.reserve(rows_.size()+1); // reserve before allocating native storage
  void* ptr=owner_.backend_->allocate(bytes,m); if(!ptr) throw std::bad_alloc();
  Allocation id=next_handle();
  rows_.push_back({id,std::move(label),c,l,m,bytes,ptr,true}); return id;
}
const Row& Arena::row(Allocation id) const {
  for(const auto& r:rows_) if(r.id==id) return r;
  throw std::out_of_range("foreign allocation id");
}
void Arena::release(Allocation id) {
  const auto& r=row(id); if(!r.live) throw std::logic_error("double release");
  if(owner_.in_flight()) throw std::logic_error("buffer release with work in flight");
  for(const auto& g:owner_.graphs_) if(std::find(g.buffers.begin(),g.buffers.end(),id)!=g.buffers.end())
    throw std::logic_error("buffer still referenced by graph");
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
  if(owner_.in_flight()>=depth_) throw std::length_error("copy backpressure");
  const auto& d=owner_.arena.row(dst); const auto& s=owner_.arena.row(src);
  if(!n || n>limit_ || !d.live || !s.live || off>d.bytes || n>d.bytes-off || soff>s.bytes || n>s.bytes-soff)
    throw std::out_of_range("copy extent/lifetime");
  if(dst==src) throw std::invalid_argument("aliased copy unsupported");
  // All submissions on this card are serialized with explicit dependencies.
  std::vector<Event> chain(deps.begin(),deps.end());
  if(!owner_.events_.empty()) chain.push_back(owner_.events_.back());
  owner_.events_.reserve(owner_.events_.size()+1);
  try {
    auto e=owner_.backend_->copy(static_cast<std::byte*>(d.pointer)+off,static_cast<const std::byte*>(s.pointer)+soff,n,chain);
    owner_.events_.push_back(e); return e;
  } catch(const std::exception& e) {owner_.fault_=e.what(); throw;}
}
}
