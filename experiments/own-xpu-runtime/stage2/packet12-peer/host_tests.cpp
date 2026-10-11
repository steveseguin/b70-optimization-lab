#include "cases.hpp"
#include "mock_device.hpp"
#include <bit>
#include <iostream>

static void require(bool yes){if(!yes)throw std::runtime_error("CPU assertion failed");}
struct Cpu : ownrt::MockDevice {
  ownrt::Event copy(void* d,const void* s,std::size_t n,std::span<const ownrt::Event> deps) override {
    auto e=MockDevice::copy(d,s,n,deps);finish(e);return e;
  }
  ownrt::Event compute(const ownrt::Operation& base,std::span<void* const> p,std::span<const ownrt::Event> deps) override {
    for(auto dep:deps)require(complete(dep));auto op=dynamic_cast<const peer::Combine&>(base);
    auto a=static_cast<float*>(p[0]),b=static_cast<float*>(p[1]),out=static_cast<float*>(p[2]);
    for(std::size_t i=0;i<op.count;++i)out[i]=peer::combine(a[i],b[i]);return marker(deps);
  }
  ownrt::EventTiming timing(ownrt::Event e) override {require(complete(e));return {1,2};}
};
int main() {
  unsigned copies=0,exchanges=0;
  for(bool direct:{false,true}) {
    ownrt::Device d(std::make_unique<Cpu>());
    peer::cases(d,direct,[](int){},[]{},[&](std::string row){
      if(row.find("\"kind\":\"copy\"")!=std::string::npos)++copies;else ++exchanges;
    });
    auto r=d.shutdown(std::chrono::milliseconds(100));
    require(r.safe_to_exit&&r.in_flight==0&&r.live_bytes==0&&r.idle_marker_complete);
  }
  require(copies==24&&exchanges==3);
  // Deterministic regrouping is NOT equality: (large+1)+(-large+1) !=
  // (((0+large)+1)-large)+1. Keep this failure as a required design gate.
  volatile float large=1e20f,one=1.0f,zero=0.0f;
  float serial=peer::combine(peer::combine(peer::combine(zero,large),one),-large);
  serial=peer::combine(serial,one);
  float regroup=peer::combine(peer::combine(large,one),peer::combine(-large,one));
  require(std::bit_cast<unsigned>(serial)!=std::bit_cast<unsigned>(regroup));
  // Early stop precedes submission; leases survive until the common teardown.
  ownrt::Device d(std::make_unique<Cpu>());bool stopped=false;
  try {peer::cases(d,true,[](int){},[]{throw std::runtime_error("STOP");},[](std::string){});}
  catch(const std::runtime_error&){stopped=true;}
  require(stopped&&d.shutdown(std::chrono::milliseconds(100)).safe_to_exit);
  // Existing owner rejects release and retirement while a copy is pending.
  auto m=std::make_unique<ownrt::MockDevice>();auto raw=m.get();ownrt::Device pending(std::move(m));
  auto alloc=[&](const char* n){return pending.arena.allocate(n,4,ownrt::Memory::device,ownrt::Category::scratch,ownrt::Lifetime::transaction);};
  auto a=alloc("a"),b=alloc("b");ownrt::CopyEngine copy(pending);auto e=copy.copy(b,0,a,0,4,{});
  int rejected=0;try{pending.arena.release(a);}catch(const std::logic_error&){++rejected;}
  try{pending.retire_completed_events();}catch(const std::logic_error&){++rejected;}
  require(rejected==2);raw->finish(e);pending.retire_completed_events();
  try{pending.wait(e,std::chrono::milliseconds(1));}catch(const std::invalid_argument&){++rejected;}
  require(rejected==3&&pending.shutdown(std::chrono::milliseconds(100)).safe_to_exit);
  std::cout<<"PASS: 24 copy cases (480 changed payloads), 3 exchange cases (900 rounds), regrouping counterexample, stop and lifetime gates\n";
}
