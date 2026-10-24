#include "fixture_math.hpp"
#include <iostream>
#include <iomanip>
#include <vector>
#include <array>
#include <bit>
#include <cmath>
static unsigned checks=0,mismatches=0;
static void equal(uint32_t a,uint32_t b,const char*label,size_t row){
 ++checks;if(a!=b){if(!mismatches)std::cerr<<"first mismatch "<<label<<" row="<<row<<" control="<<std::hex<<a<<" candidate="<<b<<std::dec<<"\n";++mismatches;}
}
static float candidate(const uint8_t*w,const uint16_t*x){float lanes[32];for(unsigned l=0;l<32;++l)lanes[l]=p33::dense_lane<iq3::Type::Q8_0,6144>(w,x,0,6144,l);return iq3::tree32(lanes);}
int main(){
 constexpr size_t K=6144,N=2560,rawrow=6528,expandedrow=7296;
 // Exhaustive binary16 scale patterns with every signed-Q8 code represented.
 std::array<uint8_t,34> block{};size_t special=0;
 for(unsigned h=0;h<65536;++h){block[0]=h;block[1]=h>>8;for(unsigned j=0;j<32;++j)block[j+2]=uint8_t(j*37+h);
  auto ex=iq3::expanded::expand(iq3::Type::Q8_0,block.data(),block.size(),32);
  equal(ex.size(),38,"expanded32 extent",h);
  if((h&0x7c00)==0x7c00)++special;
  for(unsigned k=0;k<32;k+=8){float v[8];iq3::kopt::decode8<iq3::Type::Q8_0>(block.data(),k,v);for(unsigned j=0;j<8;++j)equal(std::bit_cast<uint32_t>(v[j]),std::bit_cast<uint32_t>(iq3::expanded::value(iq3::Type::Q8_0,ex.data(),32,k+j)),"decode scale",h);}
 }
 std::vector<uint8_t> raw(N*rawrow);std::vector<uint16_t>x(K);
 for(size_t i=0;i<K;++i)x[i]=uint16_t((i%3?0:0x8000)|0x3e00|(i%511));
 for(size_t r=0;r<N;++r)for(size_t b=0;b<K/32;++b){auto*p=raw.data()+r*rawrow+b*34;unsigned h=0x2400+((r*13+b*7)%0x2000);p[0]=h;p[1]=h>>8;for(unsigned j=0;j<32;++j)p[j+2]=uint8_t(r*17+b*31+j*73);}
 auto expanded=iq3::expanded::expand(iq3::Type::Q8_0,raw.data(),raw.size(),K);
 equal(expanded.size(),N*expandedrow,"full matrix extent",0);
 for(size_t r=0;r<N;++r){float a=iq3::kopt::gemv_row(iq3::Type::Q8_0,raw.data()+r*rawrow,x.data(),iq3::Type::BF16,K,32),b=candidate(expanded.data()+r*expandedrow,x.data());equal(std::bit_cast<uint32_t>(a),std::bit_cast<uint32_t>(b),"full FP32 row",r);equal(iq3::bf16_bits(a),iq3::bf16_bits(b),"full BF16 row",r);}
 const uint16_t edges[]={0,0x8000,1,0x8001,0x3ff,0x83ff,0x400,0x8400,0x7bff,0xfbff,0x7c00,0xfc00,0x7c01,0xfc01,0x7e11,0xfe11};
 for(size_t r=0;r<std::size(edges);++r){auto*p=raw.data()+r*rawrow;for(size_t b=0;b<K/32;++b){auto h=edges[r];p[b*34]=h;p[b*34+1]=h>>8;}
  auto ex=iq3::expanded::expand(iq3::Type::Q8_0,p,rawrow,K);float a=iq3::kopt::gemv_row(iq3::Type::Q8_0,p,x.data(),iq3::Type::BF16,K,32),b=candidate(ex.data(),x.data());equal(std::bit_cast<uint32_t>(a),std::bit_cast<uint32_t>(b),"exceptional FP32 row",r);equal(iq3::bf16_bits(a),iq3::bf16_bits(b),"exceptional BF16 row",r);}
 // A real changed code must influence the output, not just a storage hash.
 std::fill(raw.begin(),raw.begin()+rawrow,0);for(size_t b=0;b<K/32;++b){raw[b*34]=0;raw[b*34+1]=0x3c;}std::fill(x.begin(),x.end(),0x3f80);
 auto zero=iq3::expanded::expand(iq3::Type::Q8_0,raw.data(),rawrow,K);raw[2]=1;auto one=iq3::expanded::expand(iq3::Type::Q8_0,raw.data(),rawrow,K);
 equal(iq3::bf16_bits(candidate(zero.data(),x.data())),0,"zero control",0);equal(iq3::bf16_bits(candidate(one.data(),x.data())),0x3f80,"changed code control",0);
 std::cout<<"{\"passed\":"<<(mismatches?"false":"true")<<",\"checks\":"<<checks<<",\"mismatches\":"<<mismatches<<",\"scale_patterns\":65536,\"nonfinite_scale_patterns\":"<<special<<",\"full_shape\":[2560,6144],\"full_rows\":2560,\"edge_rows\":16,\"native_execution\":false,\"model_payload_read\":false}\n";
 return mismatches?2:0;
}
