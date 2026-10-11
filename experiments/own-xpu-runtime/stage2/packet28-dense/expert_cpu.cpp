#include "expert.hpp"
#include <iostream>
#include <vector>
#include <string>
#include <cmath>
#include <cstdlib>

namespace {
using namespace iq3;
uint64_t checks=0,validation_checks=0,nan_payload_differences=0,digest=1469598103934665603ULL;
uint32_t random_word(uint32_t& s){s^=s<<13;s^=s>>17;s^=s<<5;return s;}
void compare(float got,float current,float reference) {
 ++checks;
 const auto a=std::bit_cast<uint32_t>(got),b=std::bit_cast<uint32_t>(current),c=std::bit_cast<uint32_t>(reference);
 if((a!=b && !(std::isnan(got)&&std::isnan(current))) || (b!=c && !(std::isnan(current)&&std::isnan(reference)))) {
  std::cerr<<"expert equality failure at "<<checks<<" got/current/ref "<<std::hex<<a<<"/"<<b<<"/"<<c<<std::dec<<"\n";
  throw std::runtime_error("expert fixture mismatch");
 }
 if(a!=b)++nan_payload_differences;
 digest^=std::isnan(got)?0x7fc00000u:a;digest*=1099511628211ULL;
 if(bf16_bits(got)!=bf16_bits(current) && !(std::isnan(got)&&std::isnan(current)))throw std::runtime_error("expert BF16 mismatch");
 ++checks;
}
std::vector<uint8_t> weights(Type t,unsigned k,unsigned rows,unsigned mode,unsigned salt) {
 auto l=layout(t);std::vector<uint8_t> out(size_t(rows)*(k/l.elements)*l.bytes);
 uint32_t state=0x12345678u+salt;
 for(auto& b:out)b=uint8_t(random_word(state));
 constexpr uint16_t scales[]={0,0x8000,1,0x8001,0x03ff,0x83ff,0x0400,0x8400,0x7bff,0xfbff,0x7c00,0xfc00,0x7c01,0xfc01,0x7e00,0xfe00};
 for(size_t b=0;b<out.size();b+=l.bytes) {
  uint16_t scale=mode?scales[(b/l.bytes+mode-1)%16]:uint16_t(0x1800+random_word(state)%0x2000);
  out[b]=uint8_t(scale);out[b+1]=uint8_t(scale>>8);
 }
 return out;
}
template<Type A>std::vector<uint16_t> inputs(unsigned k,unsigned mode) {
 std::vector<uint16_t> x(k);
 constexpr uint16_t bf[]={0,0x8000,1,0x8001,0x007f,0x807f,0x0080,0x8080,0x7f80,0xff80,0x7fc0,0xffc0,0x7f81,0xff81};
 constexpr uint16_t hf[]={0,0x8000,1,0x8001,0x03ff,0x83ff,0x0400,0x8400,0x7c00,0xfc00,0x7e00,0xfe00,0x7c01,0xfc01};
 for(unsigned i=0;i<k;++i) {
  float f=float(int(i*17%127)-63)/128.f;x[i]=A==Type::BF16?bf16_bits(f):half_bits(f);
  if(mode==1)x[i]=i%2?0x8000:0;
  if(mode==2)x[i]=(A==Type::BF16?bf:hf)[i%8];
  if(mode==3)x[i]=(A==Type::BF16?bf:hf)[i%14];
 }
 return x;
}
template<Type T,unsigned K,bool Shared,bool Paired,Type A>
void check_shape(unsigned rows,unsigned scale_mode,unsigned input_mode,unsigned split) {
 auto w=weights(T,K,rows,scale_mode,1),p=weights(T,K,rows,scale_mode,91);auto x=inputs<A>(K,input_mode);
 unsigned rb=K/layout(T).elements*layout(T).bytes;
 for(unsigned r=0;r<rows;++r) {
  std::array<float,4> result[2]{},current_result[2]{},reference_result[2]{};
  for(unsigned part=0;part<split;++part) {
   auto [begin,end]=kopt2::bounds(K,part,split);
   float sums[2][32]{},currents[2][32]{},refs[2][32]{};
   for(unsigned lane=0;lane<32;++lane) {
    p28::validate_expert_range(T,K,unsigned(begin),unsigned(end),lane);++validation_checks;
    auto s=p28::expert_lane<T,K,Shared,Paired,A>(w.data()+r*rb,Paired?p.data()+r*rb:nullptr,x.data(),begin,end,lane,p28::ExpertByteTables{},kopt3::HostShare{});
    for(unsigned m=0;m<(Paired?2u:1u);++m) {
     const uint8_t* row=(m?p:w).data()+r*rb;
     auto current=kopt3::dot<T>(row,x.data(),A,begin,end,lane,kopt3::ConstantTables{},kopt3::HostShare{});
     // Reference: scalar original-format element, exact 8-weight lane order.
     float ref=0;
     for(unsigned k=unsigned(begin)+lane*8;k<end;k+=256)for(unsigned j=0;j<8 && k+j<end;++j) {
      float input=A==Type::BF16?bits_float(uint32_t(x[k+j])<<16):half(x[k+j]);
      float product=element(T,row,k+j)*input;ref=ref+product;
     }
     try {compare(s[m],current,ref);} catch(...) { std::cerr<<"type="<<unsigned(T)<<" K="<<K<<" shared="<<Shared<<" paired="<<Paired<<" activation="<<unsigned(A)<<" rows="<<rows<<" scale_mode="<<scale_mode<<" input_mode="<<input_mode<<" split="<<split<<" row="<<r<<" lane="<<lane<<" matrix="<<m<<" part="<<part<<"\n";throw; }sums[m][lane]=s[m];currents[m][lane]=current;refs[m][lane]=ref;
    }
   }
   for(unsigned m=0;m<(Paired?2u:1u);++m) {
    result[m][part]=tree32(sums[m]);current_result[m][part]=tree32(currents[m]);reference_result[m][part]=tree32(refs[m]);
    compare(result[m][part],current_result[m][part],reference_result[m][part]);
   }
  }
  for(unsigned m=0;m<(Paired?2u:1u);++m) {
   for(unsigned width=1;width<split;width*=2)for(unsigned p0=0;p0<split;p0+=2*width) {
    result[m][p0]+=result[m][p0+width];current_result[m][p0]+=current_result[m][p0+width];reference_result[m][p0]+=reference_result[m][p0+width];
   }
   compare(result[m][0],current_result[m][0],reference_result[m][0]);
  }
 }
}
template<Type T,unsigned K>void exercise() {
 for(unsigned rows:{1u,3u,5u})for(unsigned sc:{0u,1u,9u})for(unsigned input:{0u,1u,2u,3u})for(unsigned split:{1u,4u}) {
#define RUN(S,P,A) check_shape<T,K,S,P,Type::A>(rows,sc,input,split)
  RUN(false,false,BF16);RUN(true,false,BF16);RUN(false,true,BF16);RUN(true,true,BF16);
  RUN(false,false,F16);RUN(true,true,F16);
#undef RUN
 }
}
void rejects() {
 auto reject=[](Type t,unsigned k,unsigned b,unsigned e,unsigned l){bool rejected=false;try{p28::validate_expert_range(t,k,b,e,l);}catch(const std::invalid_argument&){rejected=true;}if(!rejected)throw std::runtime_error("accepted invalid expert range");++validation_checks;};
 reject(Type::Q6_K,256,0,256,0);reject(Type::IQ4_NL,0,0,0,0);reject(Type::IQ4_NL,641,0,641,0);
 reject(Type::IQ2_S,256,8,256,0);reject(Type::IQ3_S,256,0,128,0);reject(Type::IQ3_XXS,256,0,512,0);
 reject(Type::IQ4_NL,640,0,640,32);reject(Type::IQ4_NL,17664,0,17664,0);reject(Type::IQ4_NL,640,512,256,0);
}
}
int main() {
 try {
  exercise<Type::IQ2_S,256>();exercise<Type::IQ2_S,512>();exercise<Type::IQ2_S,2560>();
  exercise<Type::IQ3_S,256>();exercise<Type::IQ3_S,768>();exercise<Type::IQ3_S,2560>();
  exercise<Type::IQ3_XXS,256>();exercise<Type::IQ3_XXS,768>();exercise<Type::IQ3_XXS,2560>();
  exercise<Type::IQ4_NL,32>();exercise<Type::IQ4_NL,64>();exercise<Type::IQ4_NL,256>();exercise<Type::IQ4_NL,640>();exercise<Type::IQ4_NL,672>();
  rejects();
  std::cout<<"{\"suite\":\"expert\",\"checks\":"<<checks<<",\"validation_checks\":"<<validation_checks<<",\"nan_payload_differences\":"<<nan_payload_differences<<",\"digest\":\""<<std::hex<<digest<<"\",\"finite_and_nan_category_passed\":true,\"strict_nan_payload_passed\":"<<(nan_payload_differences?"false":"true")<<"}\n";
  return EXIT_SUCCESS;
 } catch(const std::exception& e){std::cerr<<e.what()<<"\n";return EXIT_FAILURE;}
}
