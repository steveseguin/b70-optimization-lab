// Compare every output/status byte, packed byte and raw FP32 chain/tree.
#include "p100_down.hpp"
#include "failure.hpp"
#include <filesystem>
#include <fstream>
#include <iostream>
#include <cstring>
using iq3::Type;
void require(bool v,const char*s){if(!v)throw std::runtime_error(s);}
uint32_t next(uint32_t&s){s=s*1664525u+1013904223u;return s;}
struct Recorder{
 std::ofstream a,b,c;size_t cases=0,chains=0,trees=0,layout_bytes=0;
 Recorder(const std::filesystem::path&p):a(p/"expected.bin",std::ios::binary),b(p/"candidate.bin",std::ios::binary),c(p/"cases.jsonl"){}
 void compare(const void*x,const void*y,size_t n){require(std::memcmp(x,y,n)==0,"raw byte mismatch");a<<packet26::hash(x,n)<<"\n";b<<packet26::hash(y,n)<<"\n";}
};
template<unsigned Mode>void test(Recorder&r,unsigned rows,unsigned count,unsigned scenario){
 constexpr unsigned experts=10,K=640;size_t extent=size_t(rows)*experts*360;uint32_t seed=0x100+
 scenario+rows;std::vector<uint8_t>w(extent),raw(360);std::vector<uint16_t>x(K*count);
 for(size_t row=0;row<size_t(rows)*experts;++row){
  for(auto&v:raw)v=next(seed)>>24;
  for(unsigned block=0;block<20;++block){uint16_t h=uint16_t((next(seed)>>16)&0xb7ff);raw[block*18]=h;raw[block*18+1]=h>>8;}
  p49bgemv::repack_row(Type::IQ4_NL,K,raw.data(),w.data()+row*360);
 }
 auto tiled=p100::transpose(w.data(),size_t(rows)*experts);
 // Invert every byte at real loader granularity. Also test the last expert/tile.
 for(size_t row=0;row<size_t(rows)*experts;++row)for(unsigned block=0;block<20;++block){
  require(!std::memcmp(w.data()+row*360+block*16,p100::code_address(tiled.data(),row,block),16),"code permutation");
  require(!std::memcmp(w.data()+row*360+320+block*2,p100::half_address(tiled.data(),row,block),2),"half permutation");
  require(uintptr_t(p100::code_address(tiled.data(),row,block))%16==0,"code alignment");r.layout_bytes+=18;
 }
 for(auto&v:x)v=iq3::bf16_bits(float(int(next(seed)%33)-16)/32.f);
 if(scenario==5){x[0]=0x7fc1;x[8]=0xffd5;}
 if(scenario==6){x[0]=0x7f80;x[8]=0xff80;}
 if(scenario==7){x[0]=1;x[1]=0x8001;x[8]=0;x[9]=0x8000;}
 std::vector<iq3::Route>routes(count);for(unsigned i=0;i<count;++i)routes[i]={(i*3+1)%experts,0,rows};
 if(scenario>=1&&scenario<=3)routes[2].expert_id=experts;
 if(scenario==4){routes[0].row_count=0;routes[1].row_count=rows-2;routes[1].row_begin=1;routes[2].row_begin=rows;routes[2].row_count=1;}
 if(scenario==8){routes[0].expert_id=routes[1].expert_id;routes[count-1].expert_id=9;}
 std::vector<uint16_t>y(rows*count,0x7e31),z(y);std::vector<uint32_t>status(count,9),actual(status);
 uint32_t error=scenario==3?7:0,other=error,active=scenario==2?0:1,position=0;
 std::array<void*,19> a{};a[0]=w.data();a[1]=w.data();a[2]=x.data();a[3]=y.data();a[4]=y.data();a[5]=routes.data();a[6]=status.data();a[7]=status.data();a[16]=&error;a[17]=&active;a[18]=&position;
 auto b=a;b[0]=Mode==2?tiled.data():w.data();b[1]=b[0];b[3]=z.data();b[4]=z.data();b[6]=actual.data();b[7]=actual.data();b[16]=&other;
 p49dvirtual::DownKernel control;control.rows=rows;control.count=count;control.experts=experts;control.run(a);
 if constexpr(Mode==0)control.run(b);else{p100::Kernel<Mode>k;k.rows=rows;k.count=count;k.experts=experts;k.run(b);}
 r.compare(y.data(),z.data(),y.size()*2);r.compare(status.data(),actual.data(),status.size()*4);r.compare(&error,&other,4);
 if constexpr(Mode==2){
  // Same bytes copied into disjoint simulated cache slots. Device tables choose
  // untouched host experts, mixed hit/miss placements, then fully copied experts.
  std::vector<std::vector<uint8_t>> cache(experts);std::vector<p58::Pointer> table(experts);
  for(unsigned e=0;e<experts;++e)cache[e].assign(tiled.begin()+size_t(e)*rows*360,tiled.begin()+size_t(e+1)*rows*360);
  for(unsigned placement=0;placement<3;++placement){
   for(unsigned e=0;e<experts;++e)table[e]={uint64_t(placement==0||(placement==1&&e%2)?tiled.data()+size_t(e)*rows*360:cache[e].data()),1};
   b[0]=table.data();b[1]=table.data();std::fill(z.begin(),z.end(),0x7e31);std::fill(actual.begin(),actual.end(),9);other=scenario==3?7:0;
   p100::Kernel<2>k;k.indirect=true;k.rows=rows;k.count=count;k.experts=experts;k.run(b);
   r.compare(y.data(),z.data(),y.size()*2);r.compare(status.data(),actual.data(),status.size()*4);r.compare(&error,&other,4);
  }
 }

 for(unsigned row: {0u,1u,15u,16u,rows-1,rows*experts-1})for(unsigned slot=0;slot<count;++slot){
  float expected[32],candidate[32];
  for(unsigned lane=0;lane<32;++lane)expected[lane]=p49bgemv::lane<Type::IQ4_NL,640>(w.data()+size_t(row)*360,x.data()+slot*K,0,K,lane);
  for(unsigned physical=0;physical<2;++physical){auto v=Mode==2?p100::tile_chains(tiled.data(),row,x.data()+slot*K,physical):p65::wide_chains<Type::IQ4_NL,640,16>(w.data()+size_t(row)*360,x.data()+slot*K,physical);std::copy(v.begin(),v.end(),candidate+physical*16);}
  r.compare(expected,candidate,sizeof(expected));r.chains+=32;float e=iq3::tree32(expected),a=iq3::tree32(candidate);r.compare(&e,&a,4);++r.trees;
 }
 r.c<<"{\"rows\":"<<rows<<",\"columns\":640,\"count\":"<<count<<",\"scenario\":"<<scenario<<",\"passed\":true}\n";++r.cases;
}
int main(int argc,char**argv){try{require(argc==3,"mode output");std::string view=argv[1];unsigned mode=view=="production"?0:view.ends_with("down-tile16")?2:1;Recorder r(argv[2]);
 for(unsigned rows:{32u,2560u})for(unsigned count:{8u,10u})for(unsigned scenario=0;scenario<9;++scenario){if(mode==0)test<0>(r,rows,count,scenario);if(mode==1)test<1>(r,rows,count,scenario);if(mode==2)test<2>(r,rows,count,scenario);}
 // Every finite half bit and all packed byte patterns pass through the loader.
 std::vector<uint8_t>raw(16*360),packed(raw.size());
 for(unsigned half=0;half<65536;++half){for(unsigned row=0;row<16;++row)for(unsigned block=0;block<20;++block){auto*s=raw.data()+row*360+block*18;s[0]=half;s[1]=half>>8;for(unsigned j=0;j<16;++j)s[2+j]=row*16+j;}
  bool rejected=false;try{for(unsigned row=0;row<16;++row)p49bgemv::repack_row(Type::IQ4_NL,640,raw.data()+row*360,packed.data()+row*360);}catch(const std::invalid_argument&){rejected=true;}
  require(rejected==((half&0x7c00)==0x7c00),"finite scale refusal");if(rejected)continue;
  auto tile=p100::transpose(packed.data(),16);for(unsigned row=0;row<16;++row)for(unsigned block=0;block<20;++block){require(!std::memcmp(packed.data()+row*360+16*block,p100::code_address(tile.data(),row,block),16),"exhaustive codes");require(!std::memcmp(packed.data()+row*360+320+2*block,p100::half_address(tile.data(),row,block),2),"exhaustive half");}
 }
 std::ofstream f(std::filesystem::path(argv[2])/"native.json");f<<"{\"passed\":true,\"device_executed\":false,\"cases\":"<<r.cases<<",\"raw_fp32_chain_checks\":"<<r.chains<<",\"raw_fp32_tree_checks\":"<<r.trees<<",\"layout_bytes_checked\":"<<r.layout_bytes<<",\"half_patterns\":65536}";return 0;
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
