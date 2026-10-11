#include "capture_events.hpp"
#include "owner.hpp"
#include <algorithm>
#include <array>
#include <atomic>
#include <condition_variable>
#include <cstdio>
#include <cstring>
#include <limits>
#include <mutex>
#include <map>
#include <sstream>
#include <stdexcept>

namespace ownrt {
namespace {
std::map<Event,int> event_queue;
std::map<const Device*,Event> completed_tail;
int queue_of(const Row& r) {
  if(r.memory!=Memory::device)return -1;
  return r.label.starts_with("card1:")?1:0;
}
void assert_local_dependencies(std::span<const Event> deps,int queue) {
  for(auto e:deps)if(event_queue.at(e)!=queue)
    throw std::logic_error("foreign-queue dependency rejected by owner");
}
}

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
struct Diagnostics {std::vector<Event> events;std::vector<std::string> borrowers;};
static std::map<std::string,Diagnostics> diagnostics;
static std::map<const Device*,Receipt> retained_receipts;
static thread_local Device* submitting_owner=nullptr;
static thread_local int submitting_card=0;
void* submission_parameters(const void* data,size_t n){if(!submitting_owner)throw std::logic_error("parameters outside owned submission");auto id=parameters(*submitting_owner,data,n,submitting_card);return submitting_owner->arena.row(id).pointer;}
static std::map<Device*,std::map<std::vector<unsigned char>,Allocation>> parameter_tables;
void unregister_borrower(Device& d,const std::string& name){auto& b=diagnostics[d.identity()].borrowers;auto it=std::find(b.begin(),b.end(),name);if(it!=b.end())b.erase(it);}
void register_borrower(Device& d,std::string name){diagnostics[d.identity()].borrowers.push_back(std::move(name));}
Receipt snapshot(Device& d,std::string error){if(auto it=retained_receipts.find(&d);it!=retained_receipts.end()){auto r=it->second;r.error=error;return r;}Receipt r;r.backend=d.identity();r.error=error;r.in_flight=d.in_flight();for(auto m:{Memory::device,Memory::pinned,Memory::shadow})r.live_bytes+=d.arena.total(m);return r;}
std::string Receipt::json() const {
  std::ostringstream o;
  o << "{\"schema\":\"own-xpu-runtime.teardown.v1\",\"backend\":" << quote(backend)
    << ",\"status\":" << quote(status) << ",\"exit_code\":" << exit_code
    << ",\"safe_to_exit\":" << (safe_to_exit?"true":"false")
    << ",\"idle_marker_complete\":" << (idle_marker_complete?"true":"false")
    << ",\"in_flight\":" << in_flight << ",\"live_bytes\":" << live_bytes
    << ",\"error\":" << quote(error) << ",\"sequence\":[";
  for(std::size_t i=0;i<sequence.size();++i) o << (i?",":"") << quote(sequence[i]);
  const auto& in_flight_event_ids=diagnostics[backend].events;const auto& registered_borrowers=diagnostics[backend].borrowers;
  o << "],\"in_flight_event_ids\":[";
  for(size_t i=0;i<in_flight_event_ids.size();++i)o<<(i?",":"")<<in_flight_event_ids[i];
  o << "],\"registered_borrowers\":[";
  for(size_t i=0;i<registered_borrowers.size();++i)o<<(i?",":"")<<quote(registered_borrowers[i]);
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
void forget_event_queues(std::span<const Event> events) {for(auto e:events)event_queue.erase(e);}
Device::~Device() {
  completed_tail.erase(this);parameter_tables.erase(this);
  if(closed_) return;
  try { auto r=shutdown(std::chrono::seconds(60));if(r.safe_to_exit)return;std::fputs(r.json().c_str(),stderr);if(!r.in_flight){backend_.release();return;} }
  catch(...) {}
  hold_for_supervisor();
}
std::string Device::identity() const {return backend_?backend_->identity():retained_receipts.at(this).backend;}
void Device::admit() const {
  if(quiescing_ || !fault_.empty()) throw std::logic_error("admission closed");
  if(events_.size() >= 16384) throw std::length_error("event ledger full; end this bounded smoke");
}
void Device::validate(std::span<const Event> deps) const {
  for(auto e:deps) if(!std::binary_search(events_.begin(),events_.end(),e))
    throw std::invalid_argument("foreign dependency");
}
std::size_t Device::in_flight() {
  if(closed_ && !backend_)return 0;
  auto& pending=diagnostics[identity()].events;pending.clear();
  if(events_.empty() || completed_tail[this]==events_.back())return 0;
  for(auto e:events_){try{if(!backend_->complete(e))pending.push_back(e);}catch(...){pending.push_back(e);}}
  return pending.size();
}
bool Device::wait(Event e,std::chrono::milliseconds timeout) {
  validate(std::span(&e,1));
  bool ok=backend_->wait(e,std::chrono::steady_clock::now()+timeout);
  if(ok && !events_.empty() && e==events_.back())completed_tail[this]=e;
  return ok;
}
EventTiming Device::timing(Event e) {
  validate(std::span(&e,1));
  if(!backend_->complete(e)) throw std::logic_error("profiling before completion");
  return backend_->timing(e);
}
Event Device::compute(const Operation& op, std::span<const Allocation> buffers, std::span<const Event> deps) {
  admit(); validate(deps);
  if(buffers.empty()) throw std::invalid_argument("empty compute bindings");
  std::array<void*,64> pointer_array;
  std::vector<void*> large_pointers;
  if(buffers.size()>pointer_array.size())large_pointers.resize(buffers.size());
  std::span<void*> pointers(buffers.size()>pointer_array.size()?large_pointers.data():pointer_array.data(),buffers.size());
  size_t pointer_index=0;
  int queue=queue_of(arena.row(buffers.front()));
  for(auto id:buffers) {
    const auto& r=arena.row(id);
    if(!r.live || r.memory!=Memory::device) throw std::logic_error("compute requires live device allocation");
    if(queue_of(r)!=queue)throw std::logic_error("foreign compute allocation");
    pointers[pointer_index++]=r.pointer;
  }
  std::array<Event,16> local_chain;
  std::vector<Event> large_chain;
  size_t n=deps.size()+(!events_.empty());
  if(n>local_chain.size())large_chain.resize(n);
  std::span<Event> chain(n>local_chain.size()?large_chain.data():local_chain.data(),n);
  std::copy(deps.begin(),deps.end(),chain.begin());
  if(!events_.empty())chain.back()=events_.back();
  assert_local_dependencies(chain,queue);
  if(events_.size()==events_.capacity())events_.reserve(std::max(size_t(64),events_.size()*2));
  try {
    submitting_owner=this;submitting_card=queue;
    auto e=backend_->compute(op,pointers,chain); event_queue[e]=queue; events_.push_back(e); if(packet24::submitted_events)packet24::submitted_events->push_back(e); return e;
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
  r.sequence=sequence_; r.error=std::move(error);diagnostics[r.backend].events.clear();
  if(r.in_flight)for(auto e:events_) {try {if(!backend_->complete(e))diagnostics[r.backend].events.push_back(e);}catch(...){diagnostics[r.backend].events.push_back(e);}}
  for(auto m:{Memory::device,Memory::pinned,Memory::shadow}) r.live_bytes+=arena.total(m);
  return r;
}
Receipt Device::shutdown(std::chrono::milliseconds timeout) {
  if(closed_) {auto it=retained_receipts.find(this);return it==retained_receipts.end()?receipt():it->second;}
  // A synchronous build error with no submitted work must permit normal cleanup.

  if(!quiescing_) { quiescing_=true; sequence_.push_back("quiesce"); }
  auto end=timeout==std::chrono::milliseconds::max()?Deadline::max():std::chrono::steady_clock::now()+timeout;
  try {
    if(!drain(end)) return receipt("in-flight work; no release or exit allowed");
    sequence_.push_back("drain");
    if(!diagnostics[identity()].borrowers.empty()) {auto r=receipt("registered borrowers remain; drained backend retained until process exit");r.safe_to_exit=true;r.exit_code=1;closed_=true;retained_receipts[this]=r;backend_.release();return r;}
    while(!graphs_.empty()) {
      graphs_.back().destroy(); sequence_.push_back("graph:"+graphs_.back().label); graphs_.pop_back();
    }
    sequence_.push_back("graphs-released");
    for(int g=0;g<4;++g) arena.release_group(g);
    if(!final_marker_) { if(events_.size()==events_.capacity())events_.reserve(std::max(size_t(64),events_.size()*2)); final_marker_=backend_->marker({}); events_.push_back(final_marker_); }
    if(!backend_->wait(final_marker_,end)) return receipt("final idle marker pending; queue/context retained");
    backend_->synchronize(); idle_=true; sequence_.push_back("idle-marker-complete");
    backend_->clear_events(); forget_event_queues(events_); events_.clear(); sequence_.push_back("events-released");
    backend_->close_queue(); sequence_.push_back("queue-released");
    backend_->close_context(); sequence_.push_back("context-released"); closed_=true;
    auto r=receipt(fault_);if(!fault_.empty()){r.status="failed-drained";r.exit_code=1;}return r;
  } catch(const std::exception& e) {fault_=e.what(); auto r=receipt(fault_);if(!r.in_flight){r.safe_to_exit=true;r.exit_code=1;closed_=true;retained_receipts[this]=r;backend_.release();}return r;}
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
  auto it=std::lower_bound(rows_.begin(),rows_.end(),id,[](const Row& r,Allocation x){return r.id<x;});
  if(it==rows_.end() || it->id!=id)throw std::out_of_range("foreign allocation id");
  return *it;
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
  // All copies are explicitly chained; pinned-slab reuse is bounded by caller waits.
  const auto& d=owner_.arena.row(dst); const auto& s=owner_.arena.row(src);
  if(!n || n>limit_ || !d.live || !s.live || off>d.bytes || n>d.bytes-off || soff>s.bytes || n>s.bytes-soff)
    throw std::out_of_range("copy extent/lifetime");
  if(dst==src) throw std::invalid_argument("aliased copy unsupported");
  int dq=queue_of(d),sq=queue_of(s),queue=dq>=0?dq:sq>=0?sq:0;
  if(dq>=0&&sq>=0&&dq!=sq&&owner_.in_flight())
    throw std::logic_error("peer copy requires both queues drained on host");
  // All submissions on this card are serialized with explicit dependencies.
  std::vector<Event> chain(deps.begin(),deps.end());
  if(!owner_.events_.empty()) chain.push_back(owner_.events_.back());
  assert_local_dependencies(chain,queue);
  if(owner_.events_.size()==owner_.events_.capacity())owner_.events_.reserve(std::max(size_t(64),owner_.events_.size()*2));
  try {
    auto e=owner_.backend_->copy(static_cast<std::byte*>(d.pointer)+off,static_cast<const std::byte*>(s.pointer)+soff,n,chain);
    event_queue[e]=queue; owner_.events_.push_back(e); if(packet24::submitted_events)packet24::submitted_events->push_back(e); return e;
  } catch(const std::exception& e) {owner_.fault_=e.what(); throw;}
}
}

namespace ownrt {
Allocation parameters(Device& d,const void* data,size_t n,int card) {
 auto& parameters_=parameter_tables[&d];auto& arena=d.arena;
 std::vector<unsigned char> key(static_cast<const unsigned char*>(data),static_cast<const unsigned char*>(data)+n);
 if(auto it=parameters_.find(key);it!=parameters_.end())return it->second;
 auto label="card"+std::to_string(card)+":kernel-parameters-"+std::to_string(next_handle());
 auto host=arena.allocate(label+"-host",n,Memory::pinned,Category::pinned_slab,Lifetime::transfer);
 auto device=arena.allocate(label,n,Memory::device,Category::weights,Lifetime::process);
 std::memcpy(arena.row(host).pointer,data,n);CopyEngine copy(d);auto e=copy.copy(device,0,host,0,n,{});
 if(!d.wait(e,std::chrono::seconds(60)))throw std::runtime_error("parameter upload incomplete");
 arena.release(host);parameters_.emplace(std::move(key),device);return device;
}
}
