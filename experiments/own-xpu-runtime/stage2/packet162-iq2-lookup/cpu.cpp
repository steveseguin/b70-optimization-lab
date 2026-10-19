// Full K2560, 640 rows, ten routed experts, both independent streams.
// Calls the frozen E1 production implementation, not a handwritten FP oracle.
#include "p90_expert.hpp"
#include "candidate.hpp"
#include "enum_candidate.hpp"
#include <chrono>
#include <iostream>
#include <iomanip>
#include <cstring>
#include <bit>

using Clock=std::chrono::steady_clock;
static uint32_t seed=162;
static uint32_t next(){seed=seed*1664525u+1013904223u;return seed;}
static void require(bool v,const char*s){if(!v)throw std::runtime_error(s);}
template<unsigned Candidate> auto chains(const uint8_t*w,const uint16_t*x,unsigned physical){
 if constexpr(Candidate==2)return p162enumexp::wide_chains<iq3::Type::IQ2_S,2560,8>(w,x,physical);
 else if constexpr(Candidate==1)return p162exp::wide_chains<iq3::Type::IQ2_S,2560,8>(w,x,physical);
 else return p90exp::wide_chains<iq3::Type::IQ2_S,2560,8>(w,x,physical);
}
// Store all 32 original FP32 chains and final BF16, preserving the adjacent tree.
template<unsigned Candidate> double run(const std::vector<uint8_t>&w,const std::vector<uint16_t>&x,
 std::vector<float>&raw,std::vector<uint16_t>&out){
 auto start=Clock::now();
 for(unsigned row=0;row<12800;++row){
  float partial[4];
  for(unsigned p=0;p<4;++p){auto c=chains<Candidate>(w.data()+size_t(row)*(Candidate==2?880:840),x.data(),p);
   std::memcpy(raw.data()+size_t(row)*32+8*p,c.data(),32);
   partial[p]=p49dvirtual::local_tree<8>(c);
  }
  for(unsigned width=1;width<4;width*=2)for(unsigned p=0;p<4;p+=2*width)partial[p]=partial[p]+partial[p+width];
  out[row]=iq3::bf16_bits(partial[0]);
 }
 return std::chrono::duration<double,std::milli>(Clock::now()-start).count();
}
struct NativeOutput {std::vector<uint16_t> bytes=std::vector<uint16_t>(12800,0xa5a5);std::array<uint32_t,21> status{};};
template<unsigned Candidate> NativeOutput native(const std::vector<uint8_t>&w,
 const std::vector<uint16_t>&x,bool invalid=false){
 NativeOutput out;out.status.fill(0xa5a5a5a5);out.status[20]=0;
 std::array<iq3::Route,10> routes;for(unsigned i=0;i<10;++i)routes[i]={i,0,640};
 if(invalid){routes[3]={512,0,640};routes[7]={7,3,637};}
 uint32_t active=1;std::array<void*,19> p{};
 p[0]=const_cast<uint8_t*>(w.data());p[1]=const_cast<uint8_t*>(w.data()+6400*(Candidate==2?880:840));
 p[2]=const_cast<uint16_t*>(x.data());p[3]=out.bytes.data();p[4]=out.bytes.data()+6400;
 p[5]=routes.data();p[6]=out.status.data();p[7]=out.status.data()+10;p[16]=out.status.data()+20;p[17]=&active;
 if constexpr(Candidate==0){p90exp::Kernel<iq3::Type::IQ2_S,2560,64,false,true> k;k.run(p);}
 if constexpr(Candidate==1){p162exp::Kernel<iq3::Type::IQ2_S,2560,64,false,true> k;k.run(p);}
 if constexpr(Candidate==2){p162enumexp::Kernel<iq3::Type::IQ2_S,2560,64,false,true> k;k.run(p);}
 return out;
}
template<class T> void diff(const std::vector<T>&a,const std::vector<T>&b,const char*label,unsigned fixture){
 size_t count=0,first=0;uint32_t av=0,bv=0;
 for(size_t i=0;i<a.size();++i)if(std::memcmp(&a[i],&b[i],sizeof(T))){if(!count){first=i;std::memcpy(&av,&a[i],sizeof(T));std::memcpy(&bv,&b[i],sizeof(T));}++count;}
 std::cout<<"{\"kind\":\"difference\",\"fixture\":"<<fixture<<",\"field\":\""<<label<<"\",\"mismatch_count\":"<<count<<",\"first_index\":"<<first<<",\"production_bits\":"<<av<<",\"candidate_bits\":"<<bv<<"}\n";
}
int main(){try{
 constexpr unsigned K=2560,Rows=640,Count=10;
 static_assert(p90::expert_stride(K)==840);
 for(unsigned i=0;i<1024;++i){uint64_t w=uint64_t(p42expert::iq2_words[2*i])|(uint64_t(p42expert::iq2_words[2*i+1])<<32);
  require(p162::logic_grid(i)==w,"all grid entries");
  require(p162enum::grid(p162enum::encode[i])==w,"all enumerative entries");}
 // Finite, signed-zero, subnormal, and largest finite half scales. Nonfinite
 // weights are outside repacker admission; activation infinities/NaNs below.
 const uint16_t halves[]={0,0x8000,1,0x8001,0x03ff,0x0400,0x1400,0x9400,0x3c00,0xbc00,0x7bff,0xfbff};
 uint64_t scalar_checks=0;
 for(unsigned i=0;i<1024;++i)for(unsigned s=0;s<256;++s){
  p65::RawTile t;t.a=(i&255)|(s<<8);t.high=i>>8;
  t.scale=((i+s)&15)|(((i+3*s)&15)<<4);
  float a[8],b[8];float d=iq3::half(halves[(i+s)%12]);
  p90exp::decode_tile<iq3::Type::IQ2_S>(t,0,a,d);
  p162exp::decode_tile<iq3::Type::IQ2_S>(t,0,b,d);
  require(!std::memcmp(a,b,sizeof(a)),"decode bytes");
  unsigned code=p162enum::encode[i];t.a=(code&255)|(s<<8);t.high=(code>>8)&3;t.b=code>>10;
  p162enumexp::decode_tile<iq3::Type::IQ2_S>(t,0,b,d);
  require(!std::memcmp(a,b,sizeof(a)),"enumerative decode bytes");scalar_checks+=8;
 }
 std::vector<uint8_t>w(size_t(2)*Count*Rows*840),source(820);
 for(unsigned row=0;row<2*Count*Rows;++row){
  for(auto&b:source)b=uint8_t(next()>>24);
  for(unsigned block=0;block<10;++block){uint16_t h=halves[next()%12];std::memcpy(source.data()+82*block,&h,2);}
  p90::expert_repack(K,source.data(),w.data()+size_t(row)*840);
 }
 std::vector<uint8_t>expanded(size_t(12800)*880);
 for(unsigned row=0;row<12800;++row){
  const auto*src=w.data()+size_t(row)*840;auto*dst=expanded.data()+size_t(row)*880;
  std::memcpy(dst,src,840);
  for(unsigned block=0;block<10;++block)for(unsigned q=0;q<32;++q){
   unsigned hi=640+block*8+q/4,shift=2*(q%4);
   unsigned index=src[block*64+q*2]|(((src[hi]>>shift)&3)<<8);
   unsigned code=p162enum::encode[index];dst[block*64+q*2]=code&255;
   dst[hi]=uint8_t((dst[hi]&~(3u<<shift))|(((code>>8)&3)<<shift));
   dst[840+block*4+q/8]|=uint8_t((code>>10)<<(q%8));
  }
 }
 std::vector<uint16_t>x(K),a(12800),b(12800),c(12800);
 std::vector<float>ra(size_t(12800)*32),rb(ra.size());
 std::vector<float>rc(ra.size());bool passed=true;
 const uint16_t special[]={0,0x8000,1,0x8001,0x7f80,0xff80,0x7fc1,0xffc2};
 std::cout<<std::setprecision(17);
 for(unsigned fixture=0;fixture<3;++fixture){
  for(unsigned i=0;i<K;++i)x[i]=fixture==2&&i%17==0?special[(i/17)%8]:iq3::bf16_bits(float(int(next()%255)-127)/128.f);
  double prod,cand,enumerated;
  if(fixture%2){cand=run<1>(w,x,rb,b);enumerated=run<2>(expanded,x,rc,c);prod=run<0>(w,x,ra,a);}
  else {prod=run<0>(w,x,ra,a);enumerated=run<2>(expanded,x,rc,c);cand=run<1>(w,x,rb,b);}
  bool exact_b=!std::memcmp(ra.data(),rb.data(),ra.size()*4),exact_c=!std::memcmp(ra.data(),rc.data(),ra.size()*4);
  auto na=native<0>(w,x),nb=native<1>(w,x),nc=native<2>(expanded,x);
  auto ia=native<0>(w,x,true),ib=native<1>(w,x,true),ic=native<2>(expanded,x,true);
  bool native_b=na.bytes==nb.bytes&&na.status==nb.status&&ia.bytes==ib.bytes&&ia.status==ib.status;
  bool native_c=na.bytes==nc.bytes&&na.status==nc.status&&ia.bytes==ic.bytes&&ia.status==ic.status;
  passed=passed&&exact_b&&exact_c&&a==b&&a==c&&native_b&&native_c;
  diff(ra,rb,"logic-chains",fixture);diff(ra,rc,"enum-chains",fixture);
  diff(a,b,"logic-tree",fixture);diff(a,c,"enum-tree",fixture);
  diff(na.bytes,nb.bytes,"logic-native",fixture);diff(na.bytes,nc.bytes,"enum-native",fixture);
  std::cout<<std::boolalpha<<"{\"kind\":\"native\",\"fixture\":"<<fixture<<",\"logic_exact\":"<<native_b<<",\"enum_exact\":"<<native_c<<",\"invalid_routes_and_tail_checked\":true}\n";
  std::cout<<std::boolalpha<<"{\"fixture\":"<<fixture<<",\"columns\":2560,\"rows_per_expert\":640,\"selected_experts\":10,\"streams\":2,\"logic_chain_bytes_equal\":"<<exact_b<<",\"logic_bf16_bytes_equal\":"<<(a==b)<<",\"enum_chain_bytes_equal\":"<<exact_c<<",\"enum_bf16_bytes_equal\":"<<(a==c)<<",\"production_cpu_ms\":"<<prod<<",\"logic_cpu_ms\":"<<cand<<",\"enum_cpu_ms\":"<<enumerated<<",\"logic_cpu_ratio_diagnostic_only\":"<<cand/prod<<",\"enum_cpu_ratio_diagnostic_only\":"<<enumerated/prod<<"}\n"<<std::flush;
 }
 std::cout<<"{\"passed\":"<<passed<<",\"grid_entries\":1024,\"signed_decoded_float_checks_per_candidate\":"<<scalar_checks<<",\"device_executed\":false,\"scope\":\"synthetic real-shape chains and output; no routing or model qualification\"}\n";
 return passed?0:2;
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
