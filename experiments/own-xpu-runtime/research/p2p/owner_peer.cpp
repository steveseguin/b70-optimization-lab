// Engine owner-layer peer copy test (2026-10-25): two Devices from make_sycl_device_group (one shared Level Zero
// context, one in-order queue per card). Checks that Device::peer_copy moves bytes exactly and measures one hop with
// device-side dependencies only, against the same chain with a host wait after every hop.
// Run with ZE_ENABLE_PCI_ID_DEVICE_ORDER=1 ZE_AFFINITY_MASK=0,3 (cards 23:00.0 and 47:00.0 on steve-b70s).
#include "stage2/packet194-expert-diet-engine/owner.hpp"
#include <chrono>
#include <cstdio>
#include <cstring>
#include <vector>
using namespace ownrt;
int main() {
  auto backends=make_sycl_device_group({0,1});
  Device a(std::move(backends[0])),b(std::move(backends[1]));
  std::printf("A: %s\nB: %s\n",a.identity().c_str(),b.identity().c_str());
  for(size_t bytes:{size_t(10240),size_t(40960),size_t(163840)}) {
    auto xa=a.arena.allocate("tp:x",bytes,Memory::device,Category::scratch,Lifetime::transaction);
    auto xb=b.arena.allocate("tp:x",bytes,Memory::device,Category::scratch,Lifetime::transaction);
    auto ha=a.arena.allocate("tp:host",bytes,Memory::pinned,Category::pinned_slab,Lifetime::transfer);
    auto hb=b.arena.allocate("tp:host",bytes,Memory::pinned,Category::pinned_slab,Lifetime::transfer);
    std::vector<uint8_t> pattern(bytes);for(size_t i=0;i<bytes;++i)pattern[i]=uint8_t(i*131+7);
    std::memcpy(a.arena.row(ha).pointer,pattern.data(),bytes);
    CopyEngine ca(a),cb(b);
    auto up=ca.copy(xa,0,ha,0,bytes,{});a.wait(up,std::chrono::seconds(10));
    const int N=200;
    // 1. device-side chain: A -> B -> A ... with peer_wait guarding the source buffer each hop.
    for(int pass=0;pass<2;++pass) {
      auto t0=std::chrono::steady_clock::now();Event last=0;
      for(int i=0;i<N;++i){b.peer_copy(a,xb,0,xa,0,bytes);a.peer_wait(b);last=a.peer_copy(b,xa,0,xb,0,bytes);b.peer_wait(a);}
      a.wait(last,std::chrono::seconds(30));
      double us=std::chrono::duration<double,std::micro>(std::chrono::steady_clock::now()-t0).count()/N;
      if(pass)std::printf("%7zu B  device-side round trip (2 copies + 2 waits): %7.1f us\n",bytes,us);
    }
    // 1b. same chain: enqueue time only, and a copies-only variant (no peer_wait markers)
    for(int pass=0;pass<2;++pass) {
      auto t0=std::chrono::steady_clock::now();Event last=0;
      for(int i=0;i<N;++i){b.peer_copy(a,xb,0,xa,0,bytes);a.peer_wait(b);last=a.peer_copy(b,xa,0,xb,0,bytes);b.peer_wait(a);}
      double enq=std::chrono::duration<double,std::micro>(std::chrono::steady_clock::now()-t0).count()/N;
      a.wait(last,std::chrono::seconds(30));b.wait(b.peer_wait(a),std::chrono::seconds(30));
      auto t1=std::chrono::steady_clock::now();
      for(int i=0;i<N;++i){b.peer_copy(a,xb,0,xa,0,bytes);last=a.peer_copy(b,xa,0,xb,0,bytes);}
      double enq2=std::chrono::duration<double,std::micro>(std::chrono::steady_clock::now()-t1).count()/N;
      a.wait(last,std::chrono::seconds(30));
      double us2=std::chrono::duration<double,std::micro>(std::chrono::steady_clock::now()-t1).count()/N;
      if(pass)std::printf("%7zu B  enqueue per round trip with waits %6.1f us; copies only: enqueue %6.1f us, total %6.1f us\n",bytes,enq,enq2,us2);
    }
    // 2. host-waited chain
    for(int pass=0;pass<2;++pass) {
      auto t0=std::chrono::steady_clock::now();
      for(int i=0;i<N;++i){auto e=b.peer_copy(a,xb,0,xa,0,bytes);b.wait(e,std::chrono::seconds(10));e=a.peer_copy(b,xa,0,xb,0,bytes);a.wait(e,std::chrono::seconds(10));}
      double us=std::chrono::duration<double,std::micro>(std::chrono::steady_clock::now()-t0).count()/N;
      if(pass)std::printf("%7zu B  host-waited round trip:                    %7.1f us\n",bytes,us);
    }
    auto down=cb.copy(hb,0,xb,0,bytes,{});b.wait(down,std::chrono::seconds(10));
    const bool equal=std::memcmp(b.arena.row(hb).pointer,pattern.data(),bytes)==0;
    std::printf("%7zu B  bytes after 800 hops: %s\n",bytes,equal?"bitwise-equal":"DIFFER");
    if(!equal)return 1;
    a.arena.release(xa);b.arena.release(xb);a.arena.release(ha);b.arena.release(hb);
  }
  a.shutdown(std::chrono::seconds(30));b.shutdown(std::chrono::seconds(30));
  return 0;
}
