#pragma once
// Packet39: original row epilogues; best measured bodies imported read-only.
#include "../packet33-codegen/candidates.hpp"
#include "../packet29-merged/kernels.hpp"
namespace p39 {
using iq3::Type;
enum class Kind { expert_act, down_status, silu_div4, shared_act, attention_combine, shared_combine, gdn_conv, expert_checks };
struct Bound {
 const uint8_t *w=nullptr,*peer=nullptr;
 const uint16_t *x=nullptr,*other=nullptr,*mixture=nullptr,*shared_gate=nullptr,*inject=nullptr;
 const float* one=nullptr;
 const float* conv_weights=nullptr;
 uint16_t* history=nullptr;
 const uint32_t* position=nullptr;
 float* scratch=nullptr;
 uint16_t *y=nullptr,*py=nullptr,*out=nullptr,*streams=nullptr;
 const iq3::Route* routes=nullptr;
 uint32_t *status=nullptr,*peer_status=nullptr,*error=nullptr;
 const uint32_t* active=nullptr;
 unsigned rb=0,rows=0,count=1,experts=1,capacity=128;
};
static_assert(sizeof(Bound)<=1024);
// Coordinator boundary validation only: no device access or discovery.
// In-place streams are intentional; all other writable buffers are disjoint
// from each other and every read operand. This prevents epilogue writes racing
// another row's GEMV read. Allocation ownership/extent remains caller-owned.
template<Type T,unsigned K,Kind E,unsigned Split=1> inline void validate(Bound b){
 constexpr bool routed=E==Kind::expert_act||E==Kind::expert_checks||E==Kind::down_status;
 if(!b.rows||b.rows>248320||!b.count||b.count>10||!b.experts||b.experts>512||(!routed&&(b.count!=1||b.experts!=1)))throw std::invalid_argument("p39 shape");
 if constexpr(E==Kind::expert_act||E==Kind::expert_checks)static_assert((T==Type::IQ2_S||T==Type::IQ3_S)&&K==2560&&Split==1);
 if constexpr(E==Kind::down_status)static_assert(T==Type::IQ4_NL&&K==640&&Split==1);
 // Expanded rows retain their original block metadata after codes/FP32 scales.
 // Split count changes arithmetic, never the row layout; x/y remain BF16.
 const size_t expected=(T==Type::Q6_K||T==Type::Q8_0)?iq3::expanded::row_bytes(T,K):K/iq3::layout(T).elements*iq3::layout(T).bytes;
 if(b.rb!=expected||uint64_t(b.experts)*b.rows*b.rb>UINT32_MAX)throw std::invalid_argument("p39 row stride/offset");
 struct Range {uintptr_t lo,hi;bool write;};std::vector<Range> ranges;
 auto add=[&](const void* p,size_t n,bool write,unsigned align){if(!p||uintptr_t(p)%align||uintptr_t(p)+n<uintptr_t(p))throw std::invalid_argument("p39 null/alignment/extent");ranges.push_back({uintptr_t(p),uintptr_t(p)+n,write});};
 size_t n=size_t(b.rows)*b.count;
 add(b.w,size_t(b.experts)*b.rows*b.rb,false,1);add(b.x,size_t(K)*(E==Kind::down_status?b.count:1)*2,false,2);add(b.y,n*2,true,2);add(b.error,4,true,4);add(b.active,4,false,4);add(b.position,4,false,4);if(!b.capacity||b.capacity>INT32_MAX)throw std::invalid_argument("p39 context capacity");
 if constexpr(Split==4)add(b.scratch,n*8*4,true,4);
 if constexpr(routed){add(b.routes,b.count*sizeof(iq3::Route),false,4);add(b.status,b.count*4,true,4);}
 if constexpr(E==Kind::expert_act||E==Kind::expert_checks){add(b.peer,size_t(b.experts)*b.rows*b.rb,false,1);add(b.py,n*2,true,2);add(b.peer_status,b.count*4,true,4);}
 if constexpr(E==Kind::expert_act||E==Kind::shared_act||E==Kind::silu_div4||E==Kind::shared_combine||E==Kind::gdn_conv)add(b.out,n*2,true,2);
 if constexpr(E==Kind::shared_act)add(b.other,n*2,false,2);
 if constexpr(E==Kind::attention_combine||E==Kind::shared_combine){add(b.streams,n*4*2,true,2);add(b.inject,4*2,false,2);}
 if constexpr(E==Kind::shared_combine){add(b.one,4,false,4);add(b.mixture,n*2,false,2);add(b.shared_gate,2,false,2);}
 if constexpr(E==Kind::gdn_conv){add(b.conv_weights,n*4*4,false,4);add(b.history,n*3*2,true,2);}
 for(size_t i=0;i<ranges.size();++i)for(size_t j=0;j<i;++j)if((ranges[i].write||ranges[j].write)&&ranges[i].lo<ranges[j].hi&&ranges[j].lo<ranges[i].hi)throw std::invalid_argument("p39 read/write alias");
}
template<Kind E> inline bool position_valid(Bound b){
 if constexpr(E==Kind::attention_combine||E==Kind::down_status||E==Kind::expert_checks)return true;
 else {int32_t pos=std::bit_cast<int32_t>(*b.position);return pos>=0&&uint32_t(pos)<b.capacity;}
}
inline float widen(uint16_t x){return iq3::bits_float(uint32_t(x)<<16);}
inline float round(float x){return widen(iq3::bf16_bits(x));}
// Public scalar API for the copied host-token-plan adapter. Inputs are finished
// GEMV BF16 bytes (not unrounded accumulators). No model math is approximated.
inline uint16_t activation(uint16_t gate,uint16_t up){return iq3::bf16_bits(ng::silu(widen(gate))*widen(up));}
inline uint16_t hc_activation(uint16_t low){return iq3::bf16_bits(ng::silu(widen(low)/4.f));}
inline uint16_t combine(uint16_t residual,uint16_t branch,uint16_t inject){return iq3::bf16_bits(widen(residual)+widen(branch)*(2.f*ng::sigmoid(widen(inject)/4.f)));}
inline uint16_t shared_blend(uint16_t mixture,uint16_t down,uint16_t gate){
 // Packet29's mixture already stores BF16, then moe uses extra=1 and one=1.f.
 // Preserve its +0, *1, first BF16 round, and rounded shared contribution.
 float sum=0;sum=sum+widen(mixture)*1.f;
 return iq3::bf16_bits(round(sum)+round(widen(down)*ng::sigmoid(widen(gate))));
}
inline bool routes_valid(Bound b){for(unsigned slot=0;slot<b.count;++slot)if(!iq3::valid_route(b.routes[slot],b.experts,b.rows,b.rows))return false;return true;}
template<Kind E> inline void row_tail(Bound b,unsigned logical,uint16_t first,uint16_t second){
 if constexpr(E==Kind::gdn_conv){
  float acc=0;for(unsigned tap=0;tap<4;++tap){float value=tap==3?widen(first):widen(b.history[logical*3+tap]);acc=acc+value*b.conv_weights[logical*4+tap];}
  b.out[logical]=iq3::bf16_bits(ng::silu(acc));
  b.history[logical*3]=b.history[logical*3+1];b.history[logical*3+1]=b.history[logical*3+2];b.history[logical*3+2]=first;
 }
 if constexpr(E==Kind::expert_act)b.out[logical]=activation(first,second);
 if constexpr(E==Kind::silu_div4)b.out[logical]=hc_activation(first);
 if constexpr(E==Kind::shared_act)b.out[logical]=activation(b.other[logical],first);
 if constexpr(E==Kind::attention_combine || E==Kind::shared_combine){
  uint16_t branch=first;
  if constexpr(E==Kind::shared_combine){branch=shared_blend(b.mixture[logical],first,b.shared_gate[0]);b.out[logical]=branch;}
  for(unsigned stream=0;stream<4;++stream){unsigned j=stream*b.rows+logical;b.streams[j]=combine(b.streams[j],branch,b.inject[stream]);}
 }
}
template<Type T,unsigned K,Kind E> inline std::array<float,2> lanes(Bound b,unsigned source,unsigned slot,unsigned lane,unsigned begin=0,unsigned end=K){
 if constexpr(E==Kind::expert_act||E==Kind::expert_checks)return p28::expert_lane<T,K,false,true>(b.w+source,b.peer+source,b.x,begin,end,lane,p28::ExpertByteTables{},iq3::kopt3::HostShare{});
 else if constexpr(E==Kind::down_status)return {p33::down_lane<1,K>(b.w+source,b.x+slot*K,lane),0};
 else if constexpr((T==Type::Q6_K||T==Type::Q8_0)&&K==2560&&E!=Kind::shared_act)return {p33::dense_lane<T,K>(b.w+source,b.x,begin,end,lane),0};
 else return {p28::dense_lane<T,K>(b.w+source,b.x,begin,end,lane),0};
}
// Pure host implementation, same reduction and BF16 boundary as SG32 device.
// Fused=false writes GEMV outputs only; host_tail models separate tiny launches.
template<Type T,unsigned K,Kind E,bool Fused,unsigned Split=1> inline void host_gemv(Bound b){
 constexpr bool routed=E==Kind::expert_act||E==Kind::expert_checks||E==Kind::down_status;
 bool valid_all=true;if constexpr(routed)valid_all=routes_valid(b);
 const bool enabled=*b.active && !*b.error;const bool position_ok=position_valid<E>(b);
 for(unsigned slot=0;slot<b.count;++slot){iq3::Route route{0,0,b.rows};if constexpr(routed)route=b.routes[slot];bool ok=iq3::valid_route(route,b.experts,b.rows,b.rows);
  if constexpr(routed){b.status[slot]=!ok;if constexpr(E==Kind::expert_act||E==Kind::expert_checks)b.peer_status[slot]=!ok;}
  for(unsigned row=0;row<b.rows;++row){float partial[2][4]{};bool valid=ok&&row<route.row_count;
   if(valid)for(unsigned part=0;part<Split;++part){auto bounds=iq3::kopt2::bounds(K,part,Split);float values[2][32]{};
    for(unsigned lane=0;lane<32;++lane){auto x=lanes<T,K,E>(b,(route.expert_id*b.rows+route.row_begin+row)*b.rb,slot,lane,unsigned(bounds.first),unsigned(bounds.second));values[0][lane]=x[0];values[1][lane]=x[1];}
    partial[0][part]=iq3::tree32(values[0]);partial[1][part]=iq3::tree32(values[1]);
   }
   float values[2];for(unsigned j=0;j<2;++j)values[j]=Split==1?partial[j][0]:(partial[j][0]+partial[j][1])+(partial[j][2]+partial[j][3]);
   uint16_t a=iq3::bf16_bits(valid?values[0]:iq3::bits_float(0x7fc00000));uint16_t c=iq3::bf16_bits(valid?values[1]:iq3::bits_float(0x7fc00000));unsigned logical=slot*b.rows+row;b.y[logical]=a;
   if constexpr(E==Kind::expert_act||E==Kind::expert_checks)b.py[logical]=c;
   if constexpr(Fused)if(enabled&&valid_all&&position_ok)row_tail<E>(b,logical,a,c);
  }
 }
 if constexpr(Fused)if(enabled&&(!valid_all||!position_ok))*b.error=1;
}
template<Kind E> inline void host_tail(Bound b){
 if(!*b.active||*b.error)return;
 if(!position_valid<E>(b)){*b.error=1;return;}
 if constexpr(E==Kind::expert_act||E==Kind::expert_checks||E==Kind::down_status){for(unsigned i=0;i<b.count;++i)if(b.status[i]){*b.error=1;return;}}
 for(unsigned i=0;i<b.rows*b.count;++i)row_tail<E>(b,i,b.y[i],E==Kind::expert_act?b.py[i]:0);
}
} // namespace p39
