#pragma once
#include "candidates.hpp"
#include <algorithm>
#include <vector>
namespace p25 {
struct Shape {const char* label;const char* klass;Type type;unsigned rows,k,count,split,frequency;bool paired;};
inline constexpr Shape shapes[]={
 {"expsgate.iq2","expsgate",Type::IQ2_S,640,2560,10,1,47,true},
 {"expsgate.iq3","expsgate",Type::IQ3_S,640,2560,10,1,1,true},
 {"expsdown","expsdown",Type::IQ4_NL,2560,640,10,1,48,false},
 {"gdn.qkv.q6","gdn.qkv",Type::Q6_K,10240,2560,1,1,35,false},
 {"gdn.qkv.q8","gdn.qkv",Type::Q8_0,10240,2560,1,1,1,false},
 {"gdn.z.q6","gdn.z",Type::Q6_K,6144,2560,1,1,35,false},
 {"gdn.z.q8","gdn.z",Type::Q8_0,6144,2560,1,1,1,false},
 {"qsa.qgate","qsa.qgate",Type::Q6_K,12288,2560,1,1,12,false},
 {"qsa.k","qsa.k",Type::Q6_K,512,2560,1,4,12,false},
 {"qsa.v","qsa.v",Type::Q6_K,512,2560,1,4,12,false},
 {"attention.gdn","attention",Type::Q6_K,2560,6144,1,4,36,false},
 {"attention.qsa","attention",Type::Q6_K,2560,6144,1,4,12,false},
 {"logits","logits",Type::Q6_K,248320,2560,1,1,1,false}
};
inline uint32_t rng(uint32_t& state){state^=state<<13;state^=state>>17;state^=state<<5;return state;}
inline std::vector<uint8_t> seed_weights(Type t,unsigned k,unsigned salt,unsigned special=0){
 auto f=layout(t);std::vector<uint8_t> out(8*(k/f.elements)*f.bytes);uint32_t state=0x23456789u+salt;
 for(auto& b:out)b=rng(state);
 for(size_t off=0;off<out.size();off+=f.bytes){size_t at=off+(t==Type::Q6_K?208:0);uint16_t h=uint16_t(0x1800+(rng(state)%0x1000));
  if(special){constexpr uint16_t hs[]={0,0x8000,1,0x8001,0x7c00,0xfc00,0x7c01,0xfc01,0x7e00,0xfe00};h=hs[(off/f.bytes+special-1)%10];}
  out[at]=h&255;out[at+1]=h>>8;
 }
 return out;
}
inline std::vector<uint16_t> inputs(unsigned k,unsigned count,unsigned mode){
 std::vector<uint16_t> x(size_t(k)*count);constexpr uint16_t special[]={0,0x8000,1,0x8001,0x007f,0x807f,0x7f80,0xff80,0x7fc0,0xffc0,0x7f81,0xff81};
 for(size_t i=0;i<x.size();++i){x[i]=bf16_bits(float(int(i*17%127)-63)/128.f);
 if(mode==1)x[i]=(i%2?0x8000:0);if(mode==2)x[i]=special[i%6];if(mode==3)x[i]=special[i%12];}
 return x;
}
inline std::vector<float> half_scales(Type t,const std::vector<uint8_t>& packed){auto f=layout(t);std::vector<float> out(packed.size()/f.bytes);for(size_t i=0;i<out.size();++i)out[i]=half(u16(packed.data()+i*f.bytes));return out;}
inline constexpr unsigned routes[10]={1,1,7,3,3,0,9,2,5,4}; // ties retain their supplied slot order
inline unsigned source_row(const Shape& s,unsigned slot,unsigned row){return (s.count>1?routes[slot]*s.rows:0)+row;}
inline unsigned frozen_variant(const Shape& s){return expert(s.type)?2:(s.split==4?7:6);}
inline void verify_dispatch(){for(auto s:shapes){auto v=integrated::arithmetic::r5_variant(s.type,s.rows,s.k,s.count>1?512:1,false);if(v!=frozen_variant(s))throw std::runtime_error(std::string("frozen dispatch differs: ")+s.label);}}
struct Result {uint32_t fp[2]{};uint16_t bf[2]{};};
inline Result result(std::array<float,2> values){Result r;for(unsigned p=0;p<2;++p){r.fp[p]=std::bit_cast<uint32_t>(values[p]);r.bf[p]=bf16_bits(values[p]);}return r;}

inline bool equal(const Result&a,const Result&b){return a.fp[0]==b.fp[0]&&a.fp[1]==b.fp[1]&&a.bf[0]==b.bf[0]&&a.bf[1]==b.bf[1];}
inline std::vector<Result> expected(const Shape& s,const std::vector<uint8_t>& seed,const std::vector<uint8_t>& peer,const std::vector<uint16_t>& x){
 size_t rb=s.k/layout(s.type).elements*layout(s.type).bytes;std::vector<Result> out(size_t(s.rows)*s.count);
 for(unsigned slot=0;slot<s.count;++slot){Result cache[8];for(unsigned r=0;r<8;++r){std::array<float,2> a{};a[0]=reference(s.type,seed.data()+r*rb,x.data()+slot*s.k,s.k,s.split);if(s.paired)a[1]=reference(s.type,peer.data()+r*rb,x.data()+slot*s.k,s.k,s.split);cache[r]=result(a);}
 for(unsigned r=0;r<s.rows;++r)out[size_t(slot)*s.rows+r]=cache[source_row(s,slot,r)%8];}
 return out;
}
}
