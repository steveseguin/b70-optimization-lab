#pragma once
#include "exchange.hpp"
#include <cstring>
#include <iomanip>
#include <sstream>

namespace peer {
using ownrt::Allocation;
using Clock=std::chrono::steady_clock;
inline double elapsed(Clock::time_point t) {return std::chrono::duration<double,std::nano>(Clock::now()-t).count();}
inline std::string sample(ownrt::Device& d,const Exchange& ex,double wall) {
  std::ostringstream s;s<<std::setprecision(17)<<"{\"wall_ns\":"<<wall<<",\"events\":[";
  bool comma=false;
  for(auto e:ex.events) {auto t=d.timing(e);s<<(comma?",":"")<<"["<<t.start_ns<<","<<t.end_ns<<"]";comma=true;}
  return s.str()+"]}";
}
// Exactly this case setup, exchange order and byte validation run on CPU mocks.
// Device arithmetic itself is compile-only until the separately admitted run.
inline void cases(ownrt::Device& d,bool direct,std::function<void(int)> select,
                  std::function<void()> guard,std::function<void(std::string)> save) {
  auto alloc=[&](const char* name,std::size_t n,int card) {
    guard();select(card<0?0:card);
    return d.arena.allocate(name,n,card<0?ownrt::Memory::pinned:ownrt::Memory::device,
      card<0?ownrt::Category::pinned_slab:ownrt::Category::scratch,
      card<0?ownrt::Lifetime::transfer:ownrt::Lifetime::transaction);
  };
  constexpr auto maximum=sizes.back();
  auto a=alloc("A.payload",maximum,0),b=alloc("B.payload",maximum,1);
  auto stage=alloc("shared.pinned",maximum,-1),verify=alloc("readback.pinned",maximum,-1);
  auto remote=alloc("A.remote",vector_bytes,0),result=alloc("A.result",vector_bytes,0);
  auto mirror=alloc("B.mirror",vector_bytes,1);
  auto data=static_cast<unsigned char*>(d.arena.row(stage).pointer);
  auto readback=static_cast<unsigned char*>(d.arena.row(verify).pointer);
  auto local=[&](Allocation dst,Allocation src,std::size_t n) {
    guard();ownrt::CopyEngine c(d);auto e=c.copy(dst,0,src,0,n,{});
    if(!d.wait(e,std::chrono::milliseconds(5000)))throw std::runtime_error("setup/readback deadline");
  };
  // A supported peer arm plus a pinned bounce control; no peer error retry.
  std::vector<bool> modes=direct?std::vector<bool>{false,true}:std::vector<bool>{true};
  for(bool bounce:modes)for(auto n:sizes)for(int direction=0;direction<2;++direction) {
    std::ostringstream row;row<<"{\"kind\":\"copy\",\"mode\":"<<ownrt::quote(bounce?"host-bounce":"peer")
      <<",\"bytes\":"<<n<<",\"direction\":"<<ownrt::quote(direction?"B->A":"A->B")<<",\"samples\":[";
    for(int rep=0;rep<20;++rep) {
      guard();for(std::size_t i=0;i<n;++i)data[i]=static_cast<unsigned char>((i*131+(i>>8)+rep*17+direction*29)&255);
      local(direction?b:a,stage,n);
      Exchange ex(d,guard);auto start=Clock::now();
      ex.finish(ex.transfer(direction?a:b,direction?b:a,stage,n,bounce));
      auto wall=elapsed(start);row<<(rep?",":"")<<sample(d,ex,wall);
      local(verify,direction?a:b,n);
      for(std::size_t i=0;i<n;++i)if(readback[i]!=static_cast<unsigned char>((i*131+(i>>8)+rep*17+direction*29)&255))
        throw std::runtime_error("copy byte mismatch");
      d.retire_completed_events();
    }
    row<<"],\"exact\":true}";save(row.str());
  }
  for(bool bounce:modes) {
    std::ostringstream row;row<<"{\"kind\":\"exchange\",\"mode\":"<<ownrt::quote(bounce?"host-bounce":"peer")
      <<",\"bytes\":"<<vector_bytes<<",\"rounds\":60,\"samples\":[";
    for(int rep=0;rep<5;++rep) {
      std::array<float,hidden> expected{},increment{};
      for(std::size_t i=0;i<hidden;++i) {
        expected[i]=float(int(i%97)-48)*0.03125f+float(rep)*0.001f;
        increment[i]=float(int(i%13)-6)*0.000123f;
      }
      std::memcpy(data,expected.data(),vector_bytes);local(a,stage,vector_bytes);
      std::memcpy(data,increment.data(),vector_bytes);local(b,stage,vector_bytes);
      Exchange ex(d,guard);auto start=Clock::now();
      for(int round=0;round<60;++round) {ex.round(a,b,remote,result,mirror,stage,bounce);std::swap(a,result);}
      auto wall=elapsed(start);row<<(rep?",":"")<<sample(d,ex,wall);
      for(int round=0;round<60;++round)for(std::size_t i=0;i<hidden;++i)expected[i]=combine(expected[i],increment[i]);
      for(auto endpoint:{a,mirror}) {
        local(verify,endpoint,vector_bytes);
        if(std::memcmp(readback,expected.data(),vector_bytes))throw std::runtime_error("A+B exchange byte mismatch");
      }
      d.retire_completed_events();
    }
    row<<"],\"exact\":true}";save(row.str());
  }
}
}
