// Interleaved cold/warm timing with a clock warm-up, bitwise check against the first (reference) variant.
#pragma once
#include <sycl/sycl.hpp>
#include <algorithm>
#include <chrono>
#include <cstdio>
#include <cstring>
#include <functional>
#include <string>
#include <vector>
struct Bench {
  sycl::queue& q;float* y;size_t n;float* junk;
  std::vector<std::pair<std::string,std::function<sycl::event()>>> v;
  Bench(sycl::queue& q_,float* y_,size_t n_):q(q_),y(y_),n(n_){junk=sycl::malloc_device<float>(64*1024*1024,q);}
  ~Bench(){sycl::free(junk,q);}
  void add(const char* label,std::function<sycl::event()> f){v.push_back({label,f});}
  static double us(const sycl::event& ev){return (ev.get_profiling_info<sycl::info::event_profiling::command_end>()-ev.get_profiling_info<sycl::info::event_profiling::command_start>())/1e3;}
  void run(int rounds=6,int per=8){
    std::vector<float> ref(n),out(n);std::vector<bool> same(v.size());
    for(size_t i=0;i<v.size();++i){q.fill(y,0.f,n).wait();v[i].second().wait();q.memcpy(i?out.data():ref.data(),y,n*4).wait();same[i]=i==0||!std::memcmp(out.data(),ref.data(),n*4);}
    // clock warm-up: ~1.5 s of continuous work
    auto t0=std::chrono::steady_clock::now();while(std::chrono::steady_clock::now()-t0<std::chrono::milliseconds(1500)){for(auto& f:v)f.second();q.fill(junk,1.f,64*1024*1024);q.wait();}
    std::vector<std::vector<double>> cold(v.size()),warm(v.size());
    for(int r=0;r<rounds;++r)for(size_t i=0;i<v.size();++i){
      for(int k=0;k<per;++k){q.fill(junk,float(k),64*1024*1024);auto ev=v[i].second();ev.wait();cold[i].push_back(us(ev));}
      for(int k=0;k<per;++k){auto ev=v[i].second();ev.wait();warm[i].push_back(us(ev));}
    }
    for(size_t i=0;i<v.size();++i){auto& c=cold[i];auto& w=warm[i];std::sort(c.begin(),c.end());std::sort(w.begin(),w.end());
      std::printf("  %-46s warm %7.1f us  cold %7.1f us (p25 %6.1f p75 %6.1f)  %s\n",v[i].first.c_str(),w[w.size()/2],c[c.size()/2],c[c.size()/4],c[3*c.size()/4],same[i]?"bitwise-equal":"DIFFERS");}
    std::fflush(stdout);
  }
};
