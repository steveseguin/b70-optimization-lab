#pragma once
#include "expert_avx2.hpp"

namespace p46cpu {
// packet45/p39_fixture_data.hpp's exact LCG bank bytes, addressed by expert.
// Jump-ahead reproduces a slice without allocating or scanning a complete bank.
inline uint32_t advance(uint32_t state,uint64_t count){
 uint32_t multiplier=1664525u,increment=1013904223u,acc_mul=1,acc_add=0;
 while(count){if(count&1){acc_add=acc_add*multiplier+increment;acc_mul*=multiplier;}
  increment*=multiplier+1;multiplier*=multiplier;count>>=1;}
 return acc_mul*state+acc_add;
}
inline std::vector<uint8_t> fixture_slice(Type type,unsigned columns,unsigned rows,unsigned expert){
 auto layout=iq3::layout(type);size_t bytes=size_t(columns/layout.elements)*layout.bytes*rows;
 std::vector<uint8_t> out(bytes);uint32_t state=advance(0x39c0ffee,uint64_t(expert)*bytes);
 for(auto& byte:out){state=state*1664525u+1013904223u;byte=uint8_t(state>>24);}
 for(size_t i=0;i<bytes;i+=layout.bytes){out[i]=0;out[i+1]=0x24;}
 return out;
}
inline Expert fixture_expert(Type type,unsigned id){
 if(id>=512)throw std::invalid_argument("fixture expert ID outside existing bank");
 Expert out;out.format=type;out.gate=fixture_slice(type,hidden,intermediate,id);out.up=out.gate;
 for(auto& byte:out.up)byte^=0x35;
 for(size_t i=0;i<out.up.size();i+=iq3::layout(type).bytes){out.up[i]=0;out.up[i+1]=0x24;}
 out.down=fixture_slice(Type::IQ4_NL,intermediate,hidden,id);out.validate();return out;
}
inline std::array<uint16_t,hidden> fixture_input(unsigned change=0){
 std::array<uint16_t,hidden> out{};
 // change=0 is byte-identical to the existing G4 input. Later inputs rotate the
 // same fixture values; no new weights or prompt artifacts enter this test.
 for(unsigned i=0;i<hidden;++i)out[i]=iq3::bf16_bits(float(int((i+change)%17)-8)/32.f);
 return out;
}
inline std::vector<uint8_t> p28_scale_fixture(Type type,unsigned salt){
 // packet28/expert_cpu.cpp weights(T,2560,1,1,salt), exactly. Its first ten
 // scales are all finite: signed zeros, half subnormals, normals and maxima.
 auto layout=iq3::layout(type);std::vector<uint8_t> out(size_t(hidden/layout.elements)*layout.bytes);
 uint32_t state=0x12345678u+salt;
 for(auto& byte:out){state^=state<<13;state^=state>>17;state^=state<<5;byte=uint8_t(state);}
 constexpr uint16_t scales[]={0,0x8000,1,0x8001,0x03ff,0x83ff,0x0400,0x8400,0x7bff,0xfbff};
 for(unsigned i=0;i<10;++i){out[size_t(i)*layout.bytes]=uint8_t(scales[i]);out[size_t(i)*layout.bytes+1]=uint8_t(scales[i]>>8);}
 return out;
}
template<Type T> inline Output oracle(const Expert& weights,const std::array<uint16_t,hidden>& input){
 Output out;unsigned rb=weights.gate_stride();
 for(unsigned row=0;row<intermediate;++row){float gate[32],up[32];
  for(unsigned lane=0;lane<32;++lane){
   auto pair=p28::expert_lane<T,hidden,false,true>(weights.gate.data()+size_t(row)*rb,weights.up.data()+size_t(row)*rb,input.data(),0,hidden,lane,p28::ExpertByteTables{},iq3::kopt3::HostShare{});
   gate[lane]=pair[0];up[lane]=pair[1];
  }
  out.gate[row]=iq3::bf16_bits(iq3::tree32(gate));out.up[row]=iq3::bf16_bits(iq3::tree32(up));
  out.activation[row]=p39::activation(out.gate[row],out.up[row]);
 }
 for(unsigned row=0;row<hidden;++row){float down[32];
  for(unsigned lane=0;lane<32;++lane)down[lane]=p33::down_lane<1,intermediate>(weights.down.data()+size_t(row)*360,out.activation.data(),lane);
  out.down[row]=iq3::bf16_bits(iq3::tree32(down));
 }
 return out;
}
inline uint64_t digest(const void* p,size_t bytes,uint64_t hash=1469598103934665603ULL){
 const auto* b=static_cast<const uint8_t*>(p);for(size_t i=0;i<bytes;++i){hash^=b[i];hash*=1099511628211ULL;}return hash;
}
inline uint64_t digest(const Output& out,uint64_t hash=1469598103934665603ULL){
 hash=digest(out.gate.data(),out.gate.size()*2,hash);hash=digest(out.up.data(),out.up.size()*2,hash);
 hash=digest(out.activation.data(),out.activation.size()*2,hash);return digest(out.down.data(),out.down.size()*2,hash);
}
} // namespace p46cpu
