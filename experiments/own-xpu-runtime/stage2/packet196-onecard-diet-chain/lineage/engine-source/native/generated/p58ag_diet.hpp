#pragma once
// Packet58-onecard-diet-micro: EXACT instruction diet of the ONE-card record gate/up kernel, written beside the
// pinned production source (native-pinned/p58ag_expert.hpp, sha 89394237..., never edited):
//   production  p58ag_exp::Kernel<IQ2_S,2560,WG64,Prefetch=false,Wide=true,Followup=0,Cached=true>
//               820-B p49bgemv rows; block scale = 16-bit half at halves+2*step decoded through the 65,536-entry
//               halfcache table (binding p[19]; the engine fills it with iq3::half(i) for every i); rows reached
//               through p58::resolve(bank, source*rb, rows*rb, indirect) over p58::Pointer expert-cache slots.
//   candidate   p58ag_diet::GateUp : diet_chains = packet193's three exact transformations applied to
//               p58ag_exp::wide_chains<IQ2_S,K,8>, keeping the half load + table decode line, the slot resolution,
//               the bindings (bind through the production Kernel) and the kernel shell VERBATIM.
// Exact-identity invariants (README section 2): identical loads and load widths (codes vec4, high/scales 16-bit,
// one 16-bit half + one table gather per step); per chain the identical FP32 sequence
//   v = scale*float(q); product = v*input; sum = sum + product   (j = 0..7 in order, chains independent)
// no contraction, no reassociation; outputs, status, peer_status and error words written as production writes them.
#include "p58ag_expert.hpp"
#include <bit>
namespace p58ag_diet {
using iq3::Type;
inline constexpr char version[]="p58dm-diet-v1";
// (i) needs q != 0 for every grid magnitude: every byte of the IQ2_S grid (p42expert::iq2_words = pack32(p28::iq2_bytes),
// 1024 entries x 8 bytes) is in {8, 25, 43}. Proved at compile time against THIS tree's table.
consteval bool grid_magnitudes_in_8_25_43(){
 for(uint32_t w:p42expert::iq2_words)for(unsigned j=0;j<4;++j){unsigned m=(w>>(8*j))&255u;if(m!=8u&&m!=25u&&m!=43u)return false;}
 return p42expert::iq2_words.size()==2048;
}
static_assert(grid_magnitudes_in_8_25_43(),"IQ2_S grid magnitude outside {8,25,43}: sign-after-multiply is not provably exact");
// ---------------------------------------------------------------------------------------------------------
// Production per step (p58ag_exp::wide_chains): codes[4] (vec4 load), high, scales (16-bit loads),
//   bits = load16(w+l.halves+2*step); decoded = halfcache ? halfcache[bits] : iq3::half(bits)     <- KEPT VERBATIM
// Production per tile (p58ag_exp::decode_tile, textually p90exp::decode_tile): index=(t.a&255)|(((t.high>>(2*(q%4)))&3)<<8),
//   signs=t.a>>8 (the sign byte of the 16-bit code pair: the table carries NO sign; the half's own sign bit lives in d),
//   scale=(d*(0.5f+float((t.scale>>(4*((i/16)%2)))&15)))*0.25f,
//   exceptional=(bits(d)&0x7fffffff)>=0x7f800000 || (bits(scale)&0x7fffffff)>0x7f800000,
//   per weight: m=((j<4?a:b)>>(8*(j%4)))&255; exceptional ? v=(scale*float(m))*float(sign?-1:1)
//                                                        : v=scale*float(sign?-int(m):int(m))
// With k=first+chain*8, i=k%256=8*(physical*8+chain): q%4==chain%4, (i/16)%2==(chain/2)%2, t.scale byte==chain/4,
// t.high byte==chain/4 (compile-time after unrolling).
// (iii) exceptional depends on d only. d is a table entry = iq3::half(bits): finite (|d| <= 65504) or +-Inf or the
//       canonical NaN. d finite => |d*(0.5+s)| <= 65504*15.5 < 2^20 is finite (not even +-Inf here), *0.25f keeps it
//       so => second clause false; d non-finite => first clause true. Hence exceptional <=> d non-finite, uniform over
//       the 256-weight step. (For an arbitrary FP32 table entry packet193's weaker argument still holds: d finite =>
//       d*(0.5+s) finite or +-Inf, never NaN.) `halfcache` null falls back to iq3::half(bits) in BOTH kernels (same line).
// (i)   q in {8,25,43} (static_assert above), so float(-q) == -float(q) exactly; IEEE-754 RN multiplication is
//       sign-symmetric: scale*(-float(q)) == -(scale*float(q)) bit for bit, including scale = +-0 (d = +-0 half) and
//       any finite scale; scale is never NaN or Inf on the normal arm (iii). The negation is applied to v (the decoded
//       weight) BEFORE the input multiply, so product = v*input and the sum are the production operations on
//       identical operands. The exceptional arm keeps production's decode_tile verbatim (NaN/Inf payloads unchanged).
// (iv)  eff[b][n] = (d*(0.5f+float((scales>>(8b+4n))&15)))*0.25f is production's expression with t.scale =
//       (scales>>(8b))&255 substituted: identical integer, identical float ops, computed once per step (pure CSE).
// (ii)  byte extraction keeps production's shift/mask spelling (IGC emits :ub regions; packet193's ISA gate rejected
//       std::bit_cast byte arrays). The table gather and the slot resolution are untouched.
// ---------------------------------------------------------------------------------------------------------
template<unsigned K,unsigned V,bool Packed=false>inline std::array<float,V> diet_chains(const uint8_t*w,const uint16_t*x,unsigned physical,const float* halfcache){
 static_assert(V==8&&K%256==0);constexpr auto l=p49bgemv::layout(Type::IQ2_S,K);std::array<float,V> sums{};
 for(unsigned step=0;step<K/256;++step){
  const unsigned first=step*256+8*physical*V;
  uint32_t codes[4];
#if defined(__SYCL_DEVICE_ONLY__)
  sycl::vec<uint32_t,4> words;words.load(0,sycl::address_space_cast<sycl::access::address_space::global_space,sycl::access::decorated::no>(reinterpret_cast<const uint32_t*>(w+step*64+physical*16)));
  #pragma unroll
  for(unsigned i=0;i<4;++i)codes[i]=words[i];
#else
  for(unsigned i=0;i<4;++i)codes[i]=p49bgemv::load32(w+step*64+physical*16+4*i);
#endif
  const uint16_t high=p49bgemv::load16(w+l.high+step*8+physical*2);
  const uint16_t scales=p49bgemv::load16(w+l.scales+step*8+physical*2);
  const auto bits=p49bgemv::load16(w+l.halves+2*step);const float d=halfcache?halfcache[bits]:iq3::half(bits);   // production's decode line, verbatim
  const bool exceptional=(std::bit_cast<uint32_t>(d)&0x7fffffffu)>=0x7f800000u;           // (iii) hoisted, uniform per step
  float eff[2][2];                                                                             // (iv) [scale byte][nibble]
  #pragma unroll
  for(unsigned b=0;b<2;++b){
   #pragma unroll
   for(unsigned n=0;n<2;++n)eff[b][n]=(d*(0.5f+float((scales>>(8*b+4*n))&15)))*0.25f;}
  auto accumulate=[&](unsigned chain,const float(&values)[8]){const unsigned k=first+chain*8;
#if defined(__SYCL_DEVICE_ONLY__)
   sycl::vec<uint16_t,8> inputs;
   if constexpr(Packed){
    sycl::vec<uint32_t,4> packed;
    packed.load(0,sycl::address_space_cast<sycl::access::address_space::global_space,sycl::access::decorated::no>(reinterpret_cast<const uint32_t*>(x+k)));
    #pragma unroll
    for(unsigned j=0;j<8;++j)inputs[j]=uint16_t(packed[j/2]>>(16*(j%2)));
   }else inputs.load(0,sycl::address_space_cast<sycl::access::address_space::global_space,sycl::access::decorated::no>(x+k));
#endif
   #pragma unroll
   for(unsigned j=0;j<8;++j){
#if defined(__SYCL_DEVICE_ONLY__)
    uint16_t bits=inputs[j];
#else
    uint16_t bits;if constexpr(Packed){uint32_t packed=p49bgemv::load32(reinterpret_cast<const uint8_t*>(x+k+2*(j/2)));bits=uint16_t(packed>>(16*(j%2)));}else bits=x[k+j];
#endif
    float product=values[j]*iq3::bits_float(uint32_t(bits)<<16);sums[chain]=sums[chain]+product;
   }};
  if(!exceptional){
   #pragma unroll
   for(unsigned chain=0;chain<V;++chain){
    const unsigned ta=(codes[chain/2]>>(16*(chain%2)))&65535u,th=(high>>(8*(chain/4)))&255u;
    const unsigned index=(ta&255u)|(((th>>(2*(chain%4)))&3u)<<8),signs=ta>>8;const float scale=eff[chain/4][(chain/2)%2];
    const uint32_t a=p42expert::iq2_words[2*index],b=p42expert::iq2_words[2*index+1];
    float values[8];
    #pragma unroll
    for(unsigned j=0;j<8;++j){const unsigned magnitude=((j<4?a:b)>>(8*(j%4)))&255u;const float v=scale*float(magnitude);values[j]=((signs>>j)&1u)?-v:v;}   // (i)
    accumulate(chain,values);
   }
  }else{
   // Production exceptional path, verbatim per tile (d non-finite): kept for exactness of the NaN/Inf payloads.
   #pragma unroll
   for(unsigned chain=0;chain<V;++chain){
    p58ag_exp::RawTile t;t.a=(codes[chain/2]>>(16*(chain%2)))&65535;t.high=(high>>(8*(chain/4)))&255;t.scale=(scales>>(8*(chain/4)))&255;
    float values[8];p58ag_exp::decode_tile<Type::IQ2_S>(t,first+chain*8,values,d);accumulate(chain,values);
   }
  }
 }
 return sums;
}
// Kernel shell: the production p58ag_exp::Kernel body (bind through the production Kernel incl. the halfcache binding
// p[19] and the indirect flag; logical_row; p58::resolve; the P-lane select tree; the status/error epilogue) with
// `chains` replaced by diet_chains. The device launch form (ownrt::prepared_submit, no packet26::checked) is production's.
struct GateUp final:p49b::Base {
 using Production=p58ag_exp::Kernel<Type::IQ2_S,2560,64,false,true,0,true>;
 static constexpr unsigned K=2560,WG=64,V=Production::V,P=Production::P,SG=Production::SG,RowsPerGroup=Production::RowsPerGroup;
 static_assert(V==8&&P==4&&SG==2&&RowsPerGroup==8&&Production::paired);
 unsigned rows=640,count=10,experts=512;bool indirect=false;
 using Bound=Production::Bound;
 Bound bind(std::span<void*const>p)const{Production base;base.rows=rows;base.count=count;base.experts=experts;base.indirect=indirect;return base.bind(p);}
 static std::array<float,V> chains(const uint8_t*w,const uint16_t*x,unsigned lane,const float* halfcache){return diet_chains<K,V>(w,x,lane,halfcache);}
#ifdef OWN_RT_HOST_ONLY
 void run(std::span<void*const>p)const override{
  auto b=bind(p);unsigned total=rows*count,groups=(total+RowsPerGroup-1)/RowsPerGroup;
  for(unsigned group=0;group<groups;++group)for(unsigned sub=0;sub<SG;++sub)for(unsigned rr=0;rr<V;++rr){
   unsigned logical=Production::logical_row(group,sub,rr*P);if(logical>=total)continue;
   unsigned row=logical%rows,slot=logical/rows,stream=sub%2;
   auto route=b.routes[slot];bool ok=iq3::valid_route(route,experts,rows,rows),valid=ok&&row<route.row_count;
   float values[P]{};if(valid){size_t source=size_t(route.expert_id)*rows+route.row_begin+row;
    for(unsigned lane=0;lane<P;++lane)values[lane]=p49dvirtual::local_tree<V>(chains(p58::resolve(stream?b.peer:b.w,source*b.rb,size_t(b.rows)*b.rb,b.indirect),b.x,lane,b.halfcache));
   }
   for(unsigned width=1;width<P;width*=2)for(unsigned lane=0;lane<P;lane+=2*width)values[lane]=values[lane]+values[lane+width];
   (stream?b.py:b.y)[logical]=iq3::bf16_bits(valid?values[0]:iq3::bits_float(0x7fc00000));
   if(!row){(stream?b.peer_status:b.status)[slot]=!ok;if(!ok&&*b.active&&!*b.error)*b.error=1;}
  }
 }
#else
 sycl::event submit(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&deps)const override{
  auto b=bind(p);unsigned total=rows*count,groups=(total+RowsPerGroup-1)/RowsPerGroup;(void)deps;
  return ownrt::prepared_submit(q,[=,p35_range0=sycl::nd_range<1>(size_t(groups)*WG,WG)](sycl::handler& h){
   h.parallel_for(p35_range0,[=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
    auto sg=it.get_sub_group();unsigned lane=sg.get_local_linear_id(),sub=it.get_local_linear_id()/32,physical=lane%P,stream=sub%2;
    unsigned logical=Production::logical_row(it.get_group_linear_id(),sub,lane),row=logical%b.rows,slot=logical/b.rows;bool in_range=logical<total;
    iq3::Route route{};if(in_range)route=b.routes[slot];bool ok=in_range&&iq3::valid_route(route,b.experts,b.rows,b.rows),valid=ok&&row<route.row_count;
    float value=0;if(valid){size_t source=size_t(route.expert_id)*b.rows+route.row_begin+row;
     value=p49dvirtual::local_tree<V>(chains(p58::resolve(stream?b.peer:b.w,source*b.rb,size_t(b.rows)*b.rb,b.indirect),b.x,physical,b.halfcache));
    }
    for(unsigned width=1;width<P;width*=2){float rhs=sycl::select_from_group(sg,value,(lane+width)%32);if(physical%(2*width)==0)value=value+rhs;}
    if(in_range&&!physical){(stream?b.py:b.y)[logical]=iq3::bf16_bits(valid?value:iq3::bits_float(0x7fc00000));
     if(!row){(stream?b.peer_status:b.status)[slot]=!ok;if(!ok&&*b.active){uint32_t expected=0;sycl::atomic_ref<uint32_t,sycl::memory_order::relaxed,sycl::memory_scope::device,sycl::access::address_space::global_space>(*b.error).compare_exchange_strong(expected,1);}}
    }
   });
  });
 }
#endif
};
}
