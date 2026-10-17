#pragma once
#include "row_expert.hpp"
#include "../../packet49c-round2/p49b_gemv.hpp"

namespace p55cpu {
// Existing packet46 G4 fixture definition, independently addressed by the LCG
// jump. These are synthetic bytes, never model weights or benchmark prompts.
inline uint32_t advance(uint32_t state,uint64_t n){
 uint32_t a=1664525u,b=1013904223u,m=1,c=0;
 while(n){if(n&1){c=c*a+b;m*=a;}b*=a+1;a*=a;n>>=1;}return m*state+c;
}
inline std::vector<uint8_t> fixture_slice(Type type,unsigned columns,unsigned rows,unsigned id){
 const auto l=iq3::layout(type);const size_t n=size_t(columns/l.elements)*l.bytes*rows;
 std::vector<uint8_t> bytes(n);uint32_t state=advance(0x39c0ffee,uint64_t(id)*n);
 for(auto& v:bytes){state=state*1664525u+1013904223u;v=state>>24;}
 for(size_t i=0;i<n;i+=l.bytes){bytes[i]=0;bytes[i+1]=0x24;}return bytes;
}
inline Expert fixture_expert(Type type,unsigned id){
 Expert e;e.format=type;e.gate=fixture_slice(type,hidden,intermediate,id);e.up=e.gate;
 for(auto& v:e.up)v^=0x35;
 for(size_t i=0;i<e.up.size();i+=iq3::layout(type).bytes){e.up[i]=0;e.up[i+1]=0x24;}
 e.down=fixture_slice(Type::IQ4_NL,intermediate,hidden,id);e.validate();return e;
}
inline std::array<uint16_t,hidden> fixture_input(unsigned change=0){
 std::array<uint16_t,hidden> x{};for(unsigned i=0;i<hidden;++i)x[i]=iq3::bf16_bits(float(int((i+change)%17)-8)/32.f);return x;
}
template<Type T,unsigned K> inline std::array<float,32> production_lanes(const uint8_t* row,const uint16_t* x){
 std::array<float,32> out{};
 if constexpr(T==Type::IQ3_S){
  // Layer2 is not in packet49c's compact p49b dispatch. Its production path
  // remains the original p28/p39 raw-packed arithmetic.
  for(unsigned lane=0;lane<32;++lane)out[lane]=p28::expert_lane<T,K,false,false>(row,nullptr,x,0,K,lane,p28::ExpertByteTables{},iq3::kopt3::HostShare{})[0];
 }else{
  alignas(64) std::array<uint8_t,p49bgemv::layout(T,K).row_bytes> compact{};
  p49bgemv::repack_row(T,K,row,compact.data());
  for(unsigned lane=0;lane<32;++lane)out[lane]=p49bgemv::lane<T,K>(compact.data(),x,0,K,lane);
 }
 return out;
}
template<Type T> inline Output oracle(const Expert& e,const std::array<uint16_t,hidden>& x){
 Output out;
 for(unsigned row=0;row<intermediate;++row){
  auto g=production_lanes<T,hidden>(e.gate.data()+row*e.stride(),x.data());
  auto u=production_lanes<T,hidden>(e.up.data()+row*e.stride(),x.data());
  out.gate[row]=iq3::bf16_bits(iq3::tree32(g.data()));out.up[row]=iq3::bf16_bits(iq3::tree32(u.data()));
  out.activation[row]=p39::activation(out.gate[row],out.up[row]);
 }
 for(unsigned row=0;row<hidden;++row){auto d=production_lanes<Type::IQ4_NL,intermediate>(e.down.data()+row*360,out.activation.data());out.down[row]=iq3::bf16_bits(iq3::tree32(d.data()));}
 return out;
}
inline uint64_t digest(const void* data,size_t n,uint64_t hash=1469598103934665603ULL){
 auto* b=static_cast<const uint8_t*>(data);for(size_t i=0;i<n;++i){hash^=b[i];hash*=1099511628211ULL;}return hash;
}
inline uint64_t digest(const Output& o,uint64_t h=1469598103934665603ULL){
 h=digest(o.gate.data(),o.gate.size()*2,h);h=digest(o.up.data(),o.up.size()*2,h);
 h=digest(o.activation.data(),o.activation.size()*2,h);return digest(o.down.data(),o.down.size()*2,h);
}
} // namespace p55cpu
