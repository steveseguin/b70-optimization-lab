#pragma once
#include "owner.hpp"
#include <array>
#include <functional>

namespace peer {
constexpr std::size_t hidden = 2560, vector_bytes = hidden * sizeof(float);
constexpr std::array<std::size_t,4> sizes{10240,65536,1048576,16777216};
struct Combine : ownrt::Operation { std::size_t count = hidden; };
// Shared by CPU mock and native test: all transfers go through the one owner.
// The shared context owns both queues and both endpoints; no foreign handles.
class Exchange {
  ownrt::Device& owner;
  ownrt::CopyEngine copy;
  std::function<void()> admit;
 public:
  std::vector<ownrt::Event> events;
  Exchange(ownrt::Device& d, std::function<void()> guard):owner(d),copy(d),admit(guard){}
  ownrt::Event transfer(ownrt::Allocation dst, ownrt::Allocation src,
                       ownrt::Allocation slab, std::size_t n, bool bounce) {
    admit();
    if (bounce) {
      auto first=copy.copy(slab,0,src,0,n,{}); events.push_back(first);
      // Explicit host completion makes pinned staging visible before H2D.
      if(!owner.wait(first,std::chrono::milliseconds(5000)))
        throw std::runtime_error("D2H completion deadline");
      admit();
      auto last=copy.copy(dst,0,slab,0,n,std::span(&first,1));
      events.push_back(last); return last;
    }
    auto last=copy.copy(dst,0,src,0,n,{}); events.push_back(last); return last;
  }
  void finish(ownrt::Event e) {
    if(!owner.wait(e,std::chrono::milliseconds(5000)))
      throw std::runtime_error("exchange completion deadline");
  }
  void round(ownrt::Allocation a, ownrt::Allocation b, ownrt::Allocation remote,
             ownrt::Allocation result, ownrt::Allocation mirror,
             ownrt::Allocation slab, bool bounce) {
    finish(transfer(remote,b,slab,vector_bytes,bounce));
    admit(); Combine op; std::array bindings{a,remote,result};
    auto e=owner.compute(op,bindings,{});events.push_back(e);finish(e);
    finish(transfer(mirror,result,slab,vector_bytes,bounce));
  }
};
inline float combine(float a,float b) { return a+b; } // A left, B right; no FMA
}
