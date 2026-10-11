#include "reference.hpp"
#include "mock_device.hpp"
#include <array>
#include <iostream>
#include <cstring>
using namespace ownrt;
void check(bool v){if(!v)throw std::runtime_error("host test failed");}
class Host:public MockDevice {
public:Event copy(void* d,const void* s,size_t n,std::span<const Event> deps)override{
 auto e=MockDevice::copy(d,s,n,deps);finish(e);return e;
}
};
int main(){
 unsigned checks=0;
 for(unsigned n:{2,3,16,640,2560,248320}){auto a=tp2::rows(n,0),b=tp2::rows(n,1);check(a.first==0 && a.second==b.first && b.second==n);++checks;}
 for(unsigned e=0;e<512;++e){check(tp2::expert_owner(e)==int(e>=256));++checks;}
 bool threw=false;try{tp2::expert_owner(512);}catch(...){threw=true;}check(threw);++checks;
 // FP32 cancellation witnesses the rejected two-local-sums identity.
 volatile float huge=16777216.f,minus=-16777216.f,one=1.f;
 float serial=((huge+minus)+one),local=(huge+one)+minus;
 check(serial!=local);++checks;
 // Cover all-A, all-B, alternating, reversed, duplicate IDs and boundary IDs.
 for(unsigned pattern=0;pattern<6;++pattern)for(unsigned row=0;row<17;++row) {
  std::array<uint16_t,170> down{},gathered{};std::array<float,10> probability{};std::array<unsigned,10> ids{};
  for(unsigned slot=0;slot<10;++slot){ids[slot]=pattern==0?slot:pattern==1?256+slot:pattern==2?(slot%2?256:0)+slot:pattern==3?(slot%2?0:256)+9-slot:pattern==4?511:(slot%2?255:256);probability[slot]=float(slot+1)/64;
    for(unsigned col=0;col<17;++col)down[slot*17+col]=iq3::bf16_bits(float(int((slot*7+col)%31)-15)/8);}
  for(int rank=0;rank<2;++rank)for(unsigned slot=0;slot<10;++slot)if(tp2::expert_owner(ids[slot])==rank)
    for(unsigned col=0;col<17;++col)gathered[slot*17+col]=down[slot*17+col];
  check(std::bit_cast<uint32_t>(tp2::ordered_slots(gathered.data(),probability.data(),17,row,10))==std::bit_cast<uint32_t>(iq3::kopt4::combine(down.data(),probability.data(),17,row)));++checks;
 }
 Device a(std::make_unique<Host>()),b(std::make_unique<Host>());
 auto alloc=[](Device& d,const char* name){return d.arena.allocate(name,64,Memory::device,Category::scratch,Lifetime::transaction);};
 auto aa=alloc(a,"A"),bb=alloc(b,"B");
 for(int round=0;round<60;++round){auto p=static_cast<unsigned char*>(a.arena.row(aa).pointer);for(int j=0;j<64;++j)p[j]=round+j;
   b.peer_from(a,bb,7,aa,3,29);b.retire_completed_events();
   check(!std::memcmp(static_cast<char*>(b.arena.row(bb).pointer)+7,p+3,29));++checks;
   a.peer_from(b,aa,32,bb,7,29);a.retire_completed_events();
   check(!std::memcmp(p+32,p+3,29));++checks;
 }
 threw=false;try{b.peer_from(a,bb,40,aa,0,25);}catch(...){threw=true;}check(threw);++checks;
 auto ar=a.shutdown(std::chrono::seconds(1)),br=b.shutdown(std::chrono::seconds(1));
 check(ar.safe_to_exit && br.safe_to_exit && !ar.live_bytes && !br.live_bytes);++checks;
 std::cout<<"{\"passed\":true,\"checks\":"<<checks<<",\"device_executed\":false}\n";
}
