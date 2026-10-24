#include "fixture_math.hpp"
#include <iostream>
#include <iomanip>
#include <vector>
#include <array>
#include <bit>
#include <cmath>
static uint64_t checks=0,mismatches=0;
static void equal(uint32_t a,uint32_t b,const char*label,size_t row){++checks;if(a!=b){if(!mismatches)std::cerr<<"first mismatch "<<label<<" row="<<row<<" control="<<std::hex<<a<<" candidate="<<b<<std::dec<<"\n";++mismatches;}}
static void setq(uint8_t*b,unsigned i,int q){unsigned v=unsigned(q+32),lo=(i/128)*64+i%64,ls=4*((i%128)/64),hi=128+(i/128)*32+i%32,hs=2*((i%128)/32);b[lo]=(b[lo]&~(15u<<ls))|((v&15)<<ls);b[hi]=(b[hi]&~(3u<<hs))|((v>>4)<<hs);}
static float candidate(const uint8_t*w,const uint16_t*x){float lanes[32];for(unsigned l=0;l<32;++l)lanes[l]=p33::dense_lane<iq3::Type::Q6_K,2560>(w,x,0,2560,l);return iq3::tree32(lanes);}
static void check_block(const uint8_t*b,size_t id){auto ex=iq3::expanded::expand(iq3::Type::Q6_K,b,210,256);equal(ex.size(),338,"expanded block extent",id);for(unsigned k=0;k<256;k+=8){float a[8];iq3::kopt::decode8<iq3::Type::Q6_K>(b,k,a);for(unsigned j=0;j<8;++j)equal(std::bit_cast<uint32_t>(a[j]),std::bit_cast<uint32_t>(iq3::expanded::value(iq3::Type::Q6_K,ex.data(),256,k+j)),"decode/expansion",id);}}
int main(){
 constexpr size_t K=2560,N=10240,rawrow=2100,expandedrow=3380;std::array<uint8_t,210>block{};
 for(unsigned h=0;h<65536;++h){block[208]=h;block[209]=h>>8;for(unsigned group=0;group<16;++group)block[192+group]=uint8_t(h+group*17);for(unsigned i=0;i<256;++i)setq(block.data(),i,int((i+h)%64)-32);check_block(block.data(),h);}
 const uint16_t edges[]={0,0x8000,1,0x8001,0x3ff,0x83ff,0x400,0x8400,0x7bff,0xfbff,0x7c00,0xfc00,0x7c01,0xfc01,0x7e11,0xfe11};
 // Explicit exceptional half x every signed scale x all64 Q6 codes. Full256
 // outputs also exercise every low/high nibble group, without a NaN waiver.
 for(unsigned h:edges)for(unsigned scale=0;scale<256;++scale){block[208]=h;block[209]=h>>8;for(unsigned g=0;g<16;++g)block[192+g]=scale;for(unsigned i=0;i<256;++i)setq(block.data(),i,int(i%64)-32);check_block(block.data(),size_t(h)*256+scale);}
 std::vector<uint8_t>raw(N*rawrow);std::vector<uint16_t>x(K);
 for(size_t i=0;i<K;++i)x[i]=uint16_t((i%3?0:0x8000)|0x3e00|(i%511));
 for(size_t r=0;r<N;++r)for(size_t b=0;b<10;++b){auto*p=raw.data()+r*rawrow+b*210;unsigned h=0x2400+((r*13+b*7)%0x2000);p[208]=h;p[209]=h>>8;for(unsigned g=0;g<16;++g)p[192+g]=uint8_t(r*11+b*7+g*29);for(unsigned i=0;i<256;++i)setq(p,i,int((r*17+b*31+i*7)%64)-32);}
 auto expanded=iq3::expanded::expand(iq3::Type::Q6_K,raw.data(),raw.size(),K);equal(expanded.size(),N*expandedrow,"full expanded extent",0);
 for(size_t r=0;r<N;++r){float a=iq3::kopt::gemv_row(iq3::Type::Q6_K,raw.data()+r*rawrow,x.data(),iq3::Type::BF16,K,32),b=candidate(expanded.data()+r*expandedrow,x.data());equal(std::bit_cast<uint32_t>(a),std::bit_cast<uint32_t>(b),"full FP32 row",r);equal(iq3::bf16_bits(a),iq3::bf16_bits(b),"full BF16 row",r);}
 for(size_t r=0;r<std::size(edges);++r){auto*p=raw.data()+r*rawrow;for(size_t b=0;b<10;++b){p[b*210+208]=edges[r];p[b*210+209]=edges[r]>>8;}
  auto ex=iq3::expanded::expand(iq3::Type::Q6_K,p,rawrow,K);float a=iq3::kopt::gemv_row(iq3::Type::Q6_K,p,x.data(),iq3::Type::BF16,K,32),b=candidate(ex.data(),x.data());equal(std::bit_cast<uint32_t>(a),std::bit_cast<uint32_t>(b),"exceptional FP32 row",r);equal(iq3::bf16_bits(a),iq3::bf16_bits(b),"exceptional BF16 row",r);}
 // Independently expected numerical non-vacuity: zero codes then one +1 code.
 for(size_t b=0;b<10;++b){auto*p=raw.data()+b*210;std::fill(p,p+210,0);p[209]=0x3c;for(unsigned g=0;g<16;++g)p[192+g]=1;for(unsigned i=0;i<256;++i)setq(p,i,0);}std::fill(x.begin(),x.end(),0x3f80);
 auto zero=iq3::expanded::expand(iq3::Type::Q6_K,raw.data(),rawrow,K);setq(raw.data(),0,1);auto one=iq3::expanded::expand(iq3::Type::Q6_K,raw.data(),rawrow,K);equal(iq3::bf16_bits(candidate(zero.data(),x.data())),0,"zero control",0);equal(iq3::bf16_bits(candidate(one.data(),x.data())),0x3f80,"changed code control",0);
 std::cout<<"{\"passed\":"<<(mismatches?"false":"true")<<",\"checks\":"<<checks<<",\"mismatches\":"<<mismatches<<",\"half_patterns\":65536,\"signed_scale_patterns\":256,\"exceptional_half_scale_cartesian_cases\":4096,\"q6_codes\":64,\"full_shape\":[10240,2560],\"full_rows\":10240,\"exceptional_rows\":16,\"native_execution\":false,\"model_payload_read\":false}\n";return mismatches?2:0;
}
