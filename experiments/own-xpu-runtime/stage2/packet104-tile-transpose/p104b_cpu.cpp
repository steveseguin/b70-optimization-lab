// Gate/up and down composition: original raw chains/trees and all output bytes.
#include "p104iq2.hpp"
#include "p104iq2hc.hpp"
#include <filesystem>
#include <fstream>
#include <iostream>
using iq3::Type;
void require(bool v,const char*s){if(!v)throw std::runtime_error(s);}
uint32_t next(uint32_t&s){s=s*1664525u+1013904223u;return s;}
struct Recorder{
 std::ofstream a,b,c;size_t cases=0,chains=0,trees=0,layout_bytes=0;
 Recorder(const std::filesystem::path&p):a(p/"expected.bin",std::ios::binary),b(p/"candidate.bin",std::ios::binary),c(p/"cases.jsonl"){}
 void compare(const void*x,const void*y,size_t n){require(std::memcmp(x,y,n)==0,"raw byte mismatch");a.write((const char*)x,n);b.write((const char*)y,n);}
};
template<unsigned Mode>void test(Recorder&r,unsigned rows,unsigned count,unsigned scenario){
 constexpr unsigned experts=10,K=2560;uint32_t seed=0x104+scenario+rows;
 std::vector<uint8_t>w(size_t(rows)*experts*820),peer(w.size()),cw(size_t(rows)*experts*840),cp(cw.size()),raw(820);
 for(unsigned bank=0;bank<2;++bank)for(unsigned row=0;row<rows*experts;++row){
  for(auto&v:raw)v=next(seed)>>24;
  for(unsigned block=0;block<10;++block){uint16_t h=uint16_t((next(seed)>>16)&0xb7ff);raw[block*82]=h;raw[block*82+1]=h>>8;}
  p49bgemv::repack_row(Type::IQ2_S,K,raw.data(),(bank?peer:w).data()+size_t(row)*820);
  p90::expert_repack(K,raw.data(),(bank?cp:cw).data()+size_t(row)*840);
 }
 auto tw=p104::iq2<false>(w.data(),size_t(rows)*experts),tp=p104::iq2<false>(peer.data(),size_t(rows)*experts);
 auto tcw=p104::iq2<true>(cw.data(),size_t(rows)*experts),tcp=p104::iq2<true>(cp.data(),size_t(rows)*experts);
 for(unsigned bank=0;bank<2;++bank)for(unsigned cached=0;cached<2;++cached){
  const auto&src=cached?(bank?cp:cw):(bank?peer:w);const auto&dst=cached?(bank?tcp:tcw):(bank?tp:tw);size_t rb=cached?840:820;
  for(size_t row=0;row<size_t(rows)*experts;++row)for(auto pl:{p104::Plane{0,640,16},p104::Plane{640,80,2},p104::Plane{720,80,2},p104::Plane{800,cached?40u:20u,cached?4u:2u}})for(size_t k=0;k<pl.bytes;++k){require(src[row*rb+pl.start+k]==*p104::address(dst.data(),row,rb,pl.start,pl.chunk,k),"permutation byte");++r.layout_bytes;}
 }
 std::vector<uint16_t>x(K);for(auto&v:x)v=iq3::bf16_bits(float(int(next(seed)%33)-16)/32.f);
 if(scenario==5){x[0]=0x7fc1;x[8]=0xffd5;}if(scenario==6){x[0]=0x7f80;x[8]=0xff80;}if(scenario==7){x[0]=1;x[1]=0x8001;x[8]=0;x[9]=0x8000;}
 std::vector<iq3::Route>routes(count);for(unsigned i=0;i<count;++i)routes[i]={(i*3+1)%experts,0,rows};
 if(scenario>=1&&scenario<=3)routes[2].expert_id=experts;
 if(scenario==4){routes[0].row_count=0;routes[1].row_count=rows-2;routes[1].row_begin=1;routes[2].row_begin=rows;routes[2].row_count=1;}
 if(scenario==8){routes[0].expert_id=routes[1].expert_id;routes[count-1].expert_id=9;}
 std::vector<uint16_t>y(rows*count,0x7e31),py(y),z(y),pz(y);std::vector<uint32_t>status(count,9),ps(status),actual(status),pa(status);
 uint32_t error=scenario==3?7:0,other=error,active=scenario==2?0:1,position=0;
 std::array<void*,19>a{};a[0]=w.data();a[1]=peer.data();a[2]=x.data();a[3]=y.data();a[4]=py.data();a[5]=routes.data();a[6]=status.data();a[7]=ps.data();a[16]=&error;a[17]=&active;a[18]=&position;
 auto b=a;b[0]=Mode==1?tw.data():Mode==2?tcw.data():cw.data();b[1]=Mode==1?tp.data():Mode==2?tcp.data():cp.data();b[3]=z.data();b[4]=pz.data();b[6]=actual.data();b[7]=pa.data();b[16]=&other;
 p65::Kernel<Type::IQ2_S,K,64,false,true> control;control.rows=rows;control.count=count;control.experts=experts;control.run(a);
 std::conditional_t<Mode==1,p104iq2::Kernel<Type::IQ2_S,K,64,false,true>,std::conditional_t<Mode==2,p104iq2hc::Kernel<Type::IQ2_S,K,64,false,true>,p90exp::Kernel<Type::IQ2_S,K,64,false,true>>>k;k.rows=rows;k.count=count;k.experts=experts;k.run(b);
 r.compare(y.data(),z.data(),y.size()*2);r.compare(py.data(),pz.data(),py.size()*2);r.compare(status.data(),actual.data(),status.size()*4);r.compare(ps.data(),pa.data(),ps.size()*4);r.compare(&error,&other,4);
 for(unsigned row:{0u,1u,15u,16u,rows-1,rows*experts-1})for(unsigned bank=0;bank<2;++bank){
  float expected[32],candidate[32];for(unsigned lane=0;lane<32;++lane)expected[lane]=p49bgemv::lane<Type::IQ2_S,K>((bank?peer:w).data()+size_t(row)*820,x.data(),0,K,lane);
  for(unsigned lane=0;lane<4;++lane){auto v=[&]{if constexpr(Mode==1)return p104iq2::wide_chains<Type::IQ2_S,K,8>((bank?tp:tw).data(),row,x.data(),lane);else if constexpr(Mode==2)return p104iq2hc::wide_chains<Type::IQ2_S,K,8>((bank?tcp:tcw).data(),row,x.data(),lane);else return p90exp::wide_chains<Type::IQ2_S,K,8>((bank?cp:cw).data()+size_t(row)*840,x.data(),lane);}();std::copy(v.begin(),v.end(),candidate+lane*8);}
  r.compare(expected,candidate,sizeof(expected));r.chains+=32;float e=iq3::tree32(expected),v=iq3::tree32(candidate);r.compare(&e,&v,4);++r.trees;
 }
 r.c<<"{\"rows\":"<<rows<<",\"columns\":2560,\"count\":"<<count<<",\"scenario\":"<<scenario<<",\"passed\":true}\n";++r.cases;
}
int main(int argc,char**argv){try{require(argc==3,"view output");std::string view=argv[1];require(view=="production"||view=="target-gate-tile16"||view=="target-gate-halfcache-tile16","unknown view");Recorder r(argv[2]);
 for(unsigned rows:{32u,640u})for(unsigned count:{8u,10u})for(unsigned scenario=0;scenario<9;++scenario){if(view=="production")test<0>(r,rows,count,scenario);else if(view=="target-gate-tile16")test<1>(r,rows,count,scenario);else test<2>(r,rows,count,scenario);}
 std::vector<uint8_t>raw(820),packed(16*820),cached(16*840);
 for(unsigned h=0;h<65536;++h){for(unsigned block=0;block<10;++block){raw[block*82]=h;raw[block*82+1]=h>>8;}
  bool refused=false;try{p90::expert_repack(2560,raw.data(),cached.data());}catch(const std::invalid_argument&){refused=true;}require(refused==((h&0x7c00)==0x7c00),"nonfinite half refusal");if(refused)continue;
  p49bgemv::repack_row(Type::IQ2_S,2560,raw.data(),packed.data());for(unsigned row=1;row<16;++row){std::memcpy(packed.data()+row*820,packed.data(),820);std::memcpy(cached.data()+row*840,cached.data(),840);}
  auto a=p104::iq2<false>(packed.data(),16),b=p104::iq2<true>(cached.data(),16);
  for(unsigned row=0;row<16;++row)for(unsigned block=0;block<10;++block){float expected=iq3::half(uint16_t(h)),uncached=iq3::half(p49bgemv::load16(p104::address(a.data(),row,820,800,2,block*2))),actual=iq3::bits_float(p49bgemv::load32(p104::address(b.data(),row,840,800,4,block*4)));require(std::memcmp(&expected,&actual,4)==0&&std::memcmp(&expected,&uncached,4)==0,"all half bits");}
 }
 std::ofstream f(std::filesystem::path(argv[2])/"native.json");f<<"{\"passed\":true,\"device_executed\":false,\"cases\":"<<r.cases<<",\"raw_fp32_chain_checks\":"<<r.chains<<",\"raw_fp32_tree_checks\":"<<r.trees<<",\"layout_bytes_checked\":"<<r.layout_bytes<<",\"half_patterns\":65536}";return 0;
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
