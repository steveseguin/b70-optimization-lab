#pragma once
#include "owner.hpp"
#include <cstring>
#include <stdexcept>

namespace ownrt {
// Deterministic manual completion. No SYCL headers, loader or device access.
class MockDevice final : public Backend {
  struct Work { bool done; std::vector<Event> deps; std::function<void()> run; };
  std::map<Event,Work> work_;
  std::map<void*,Memory> allocations_;
 public:
  bool queue_closed=false, context_closed=false, auto_marker=true;
  std::vector<std::string> calls;
  std::string identity() const override {return "MockDevice";}
  void* allocate(std::size_t n,Memory m) override {
    if(queue_closed) throw std::logic_error("closed mock");
    auto p=::operator new(n); allocations_.emplace(p,m); return p;
  }
  void release(void* p,Memory m) override {
    if(allocations_.at(p)!=m) throw std::logic_error("wrong memory");
    ::operator delete(p); allocations_.erase(p); calls.push_back("free");
  }
  Event copy(void* dst,const void* src,std::size_t n,std::span<const Event> deps) override {
    auto e=next_handle(); work_.emplace(e,Work{false,{deps.begin(),deps.end()},[=]{std::memcpy(dst,src,n);}});
    calls.push_back("copy"); return e;
  }
  Event marker(std::span<const Event> deps) override {
    auto e=next_handle(); work_.emplace(e,Work{false,{deps.begin(),deps.end()},[]{}});
    calls.push_back("marker"); if(auto_marker) finish(e); return e;
  }
  void finish(Event e) {
    auto& w=work_.at(e);
    for(auto dep:w.deps) if(!work_.at(dep).done) throw std::logic_error("dependency pending");
    if(!w.done) {w.run(); w.done=true;}
  }
  void finish_all() {for(const auto& [e,w]:work_) finish(e);}
  bool complete(Event e) override {return work_.at(e).done;}
  bool wait(Event e,Deadline) override {calls.push_back("wait"); return complete(e);}
  void synchronize() override {
    for(const auto& [e,w]:work_) if(!w.done) throw std::logic_error("sync before drain");
    calls.push_back("synchronize");
  }
  void clear_events() override {synchronize(); work_.clear(); calls.push_back("events");}
  void close_queue() override {
    if(!work_.empty() || !allocations_.empty()) throw std::logic_error("queue still owns resources");
    queue_closed=true; calls.push_back("queue");
  }
  void close_context() override {
    if(!queue_closed) throw std::logic_error("context before queue");
    context_closed=true; calls.push_back("context");
  }
};
}
