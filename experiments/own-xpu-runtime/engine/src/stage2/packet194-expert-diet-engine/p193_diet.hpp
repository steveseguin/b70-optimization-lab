#pragma once
// Packet193: EXACT instruction-diet candidates for the two record expert kernels, written beside the pinned
// production sources (never edited):
//   production gate/up  p90exp::Kernel<IQ2_S,2560,WG64,Prefetch=false,Wide=true>   (p90_expert.hpp 17c976c4...)
//   production down     p100::Kernel<2>                                             (p100_down.hpp  329ff3d0...)
//   production routed activation ("expsact"): the record engine's separate silu_product launch
//     out[k] = bf16( silu(widen(y[k])) * widen(py[k]) ),  silu(x)=x*(1/(1+detmath::exp(-x)))  (ng::silu, kernels.hpp)
// Candidates:
//   exp-diet          GateUp     : diet_chains  (i) sign applied after the scale multiply, (ii) byte-regioned code
//                                  extraction, (iii) per-step hoisted `exceptional` branch, (iv) hoisted effective scales
//   down-diet         Down       : diet_tile_chains  hoisted d*float(level) products (pure CSE) + nibble extraction
//   exp-act-epilogue  GateUpAct  : exp-diet + the routed activation as an SLM gate<->up epilogue inside the WG64
// Exact-identity invariants (README section 2): identical loads and load widths; per chain the identical FP32
// sequence v = scale*float(q), product = v*input, sum = sum+product in the same order; no contraction, no
// reassociation; outputs, status, peer_status and error words written as production writes them.
#include "stage2/packet194-expert-diet-engine/p90_expert.hpp"
#include "stage2/packet194-expert-diet-engine/p100_down.hpp"
#include "stage2/packet194-expert-diet-engine/kernels.hpp"
#include <bit>
namespace p193diet {
using iq3::Type;
inline constexpr char version[]="p193-diet-v1";

// ---------------------------------------------------------------------------------------------------------
// (A) gate/up IQ2_S E1 rows: exact diet of p90exp::wide_chains<IQ2_S,K,8>.
//  Production per tile (p90exp::decode_tile): index=(t.a&255)|(((t.high>>(2*(q%4)))&3)<<8), signs=t.a>>8,
//   scale=(d*(0.5f+float((t.scale>>(4*((i/16)%2)))&15)))*0.25f,
//   exceptional=(bits(d)&0x7fffffff)>=0x7f800000 || (bits(scale)&0x7fffffff)>0x7f800000,
//   per weight: m=((j<4?a:b)>>(8*(j%4)))&255; exceptional ? v=(scale*float(m))*float(sign?-1:1)
//                                                        : v=scale*float(sign?-int(m):int(m))
//  Here, with k=first+chain*8, i=k%256=8*(physical*8+chain): q%4==chain%4, (i/16)%2==(chain/2)%2,
//   t.scale byte==chain/4, t.high byte==chain/4 (all compile-time after unrolling).
//  (iii) exceptional depends on d only: d finite => d*(0.5+s) is finite or +-Inf, never NaN, and *0.25f keeps it
//        so; d non-finite => first clause. Hence exceptional <=> d non-finite, uniform over the 256-weight step.
//  (i)   every IQ2_S grid magnitude is in {8,25,43} (p28::iq2_bytes), so m != 0 and float(-m) == -float(m);
//        IEEE-754 RN multiplication is sign-symmetric: scale*(-float(m)) == -(scale*float(m)) bit for bit,
//        including scale = +-0 and +-Inf; scale cannot be NaN on the normal path (d finite). The negation is
//        applied to v (the decoded weight) before the input multiply, so product = v*input is unchanged.
//  (ii)  byte extraction keeps production's shift/mask spelling (IGC emits :ub regions for it; the explicit
//        std::bit_cast byte-array form was rejected by the ISA gate: ~10 moves per byte, evidence/isa-rejected/).
//  (iv)  the four effective scales of a step are computed once each (same inputs, same ops: pure CSE).
// ---------------------------------------------------------------------------------------------------------
template<unsigned K,unsigned V,bool Packed=false>inline std::array<float,V> diet_chains(const uint8_t*w,const uint16_t*x,unsigned physical){
 static_assert(V==8&&K%256==0);constexpr auto l=p49bgemv::layout(Type::IQ2_S,K);std::array<float,V> sums{};
 for(unsigned step=0;step<K/256;++step){
  const unsigned first=step*256+8*physical*V;
  std::array<uint32_t,4> codes;
#if defined(__SYCL_DEVICE_ONLY__)
  sycl::vec<uint32_t,4> words;words.load(0,sycl::address_space_cast<sycl::access::address_space::global_space,sycl::access::decorated::no>(reinterpret_cast<const uint32_t*>(w+step*64+physical*16)));
  #pragma unroll
  for(unsigned i=0;i<4;++i)codes[i]=words[i];
#else
  for(unsigned i=0;i<4;++i)codes[i]=p49bgemv::load32(w+step*64+physical*16+4*i);
#endif
  const uint16_t high=p49bgemv::load16(w+l.high+step*8+physical*2);
  const uint16_t scales=p49bgemv::load16(w+l.scales+step*8+physical*2);
  const float d=iq3::bits_float(p49bgemv::load32(w+l.halves+4*step));
  const bool exceptional=(std::bit_cast<uint32_t>(d)&0x7fffffffu)>=0x7f800000u;           // (iii) hoisted, uniform per step
  float eff[2][2];                                                                             // (iv) [scale byte][nibble]
  #pragma unroll
  for(unsigned b=0;b<2;++b){
   #pragma unroll
   for(unsigned n=0;n<2;++n)eff[b][n]=(d*(0.5f+float((scales>>(8*b+4*n))&15)))*0.25f;}
  // (ii) extraction keeps production's shift/mask spelling: IGC already lowers it to :ub byte regions, while a
  // std::bit_cast byte array made it materialise the array (~10 moves per byte; evidence/isa-rejected/).
  // Per chain the eight decoded values are consumed immediately (eight live floats, as production); the
  // exceptional branch is uniform per step and both arms carry the identical product/sum loop.
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
    p65::RawTile t;t.a=(codes[chain/2]>>(16*(chain%2)))&65535;t.high=uint8_t((high>>(8*(chain/4)))&255);t.scale=uint8_t((scales>>(8*(chain/4)))&255);
    float values[8];p90exp::decode_tile<Type::IQ2_S>(t,first+chain*8,values,d);accumulate(chain,values);
   }
  }
 }
 return sums;
}

// ---------------------------------------------------------------------------------------------------------
// (B) down IQ4_NL tile16: exact diet of p100::tile_chains.
//  Production per tile (p65::decode_tile<IQ4_NL>): d=iq3::half(t.half); per weight code=((j<4?t.a:t.b)>>(8*(j%4)))&255,
//   q=(code>>(4*(off/16)))&15, v=d*float(p33::level_bank(q)), with t.a=codes[(c%2)*2], t.b=codes[(c%2)*2+1],
//   off=k%32=8*c (first%32==0), so off/16==c/2.
//  Diet: d computed once per 32-weight block (same input half, same pure function); the sixteen products
//   lv[i]=d*float(level_bank(i)) computed once per block and selected by q (pure CSE: v=lv[q] is the very
//   product production computes); code byte j of the block = byte 8*(c%2)+j of the 16 code bytes; q = code&15
//   for c<2, code>>4 for c>=2 (code<256 so no mask needed).
// ---------------------------------------------------------------------------------------------------------
//  HoistProducts=true is the brief's form (sixteen products per block, selected by q): IGC lowers lv[q] to a0 register-
//  indirect movs plus 512 B of spills at 128 GRF (evidence/isa-rejected/); HoistProducts=false keeps production's
//  per-weight d*float(level_bank(q)) and applies only the byte/nibble extraction and the once-per-block half decode.
template<bool HoistProducts=false>inline std::array<float,16> diet_tile_chains(const uint8_t*w,size_t source,const uint16_t*x,unsigned physical){
 constexpr unsigned K=640,V=16;constexpr bool Packed=false;std::array<float,V> sums{};
 for(unsigned step=0;step<(K+255)/256;++step){
  #pragma unroll
  for(unsigned block_in_lane=0;block_in_lane<V/4;++block_in_lane){
   const unsigned first=step*256+8*(physical*V+block_in_lane*4);if(first>=K)continue;
   const unsigned block=first/32;std::array<uint32_t,4> codes;
#if defined(__SYCL_DEVICE_ONLY__)
   sycl::vec<uint32_t,4> words;words.load(0,sycl::address_space_cast<sycl::access::address_space::global_space,sycl::access::decorated::no>(reinterpret_cast<const uint32_t*>(p100::code_address(w,source,block))));
   #pragma unroll
   for(unsigned i=0;i<4;++i)codes[i]=words[i];
#else
   for(unsigned i=0;i<4;++i)codes[i]=p49bgemv::load32(p100::code_address(w,source,block)+4*i);
#endif
   const uint16_t half=p49bgemv::load16(p100::half_address(w,source,block));
   const float d=iq3::half(half);
   float lv[16];
   if constexpr(HoistProducts){
    #pragma unroll
    for(unsigned i=0;i<16;++i)lv[i]=d*float(p33::level_bank(i));                                  // hoisted products (pure CSE)
   }
   // extraction keeps production's shift/mask spelling (IGC lowers it to byte regions; a bit_cast byte array did not)
   #pragma unroll
   for(unsigned c=0;c<4;++c){const unsigned chain=block_in_lane*4+c,k=first+8*c,base=8*(c%2);
    float values[8];
    #pragma unroll
    for(unsigned j=0;j<8;++j){const unsigned code=(codes[base/4+j/4]>>(8*(j%4)))&255u;const unsigned q=c<2?(code&15u):(code>>4);if constexpr(HoistProducts)values[j]=lv[q];else values[j]=d*float(p33::level_bank(q));}
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
    }
   }
  }
 }return sums;
}

// ---------------------------------------------------------------------------------------------------------
// (C) the routed activation: the record engine's separate silu_product launch (ng::group op=activation, extra=1:
//     a.put(2,idx, silu(a.b(0,idx))*a.b(1,idx)) after the `!active || error` early return). One source function
//     serves the production twin launch and the fused epilogue so the FP sequence is the same text.
// ---------------------------------------------------------------------------------------------------------
inline uint16_t act(uint16_t gate,uint16_t up){return ng::Args::bits(ng::silu(iq3::bits_float(uint32_t(gate)<<16))*iq3::bits_float(uint32_t(up)<<16));}
inline constexpr unsigned ACT_WG=128;   // ng::groups(activation) = (tokens*width+127)/128 groups of 128 elements

struct ActProduction final:p49b::Base {   // twin of the record's silu_product launch: p[3]=y (gate), p[4]=py (up), p[8]=out, p[16]=error, p[17]=active
 unsigned rows=640,count=10;
 struct Args{const uint16_t*y,*py;uint16_t*out;const uint32_t*error,*active;unsigned n;};
 Args bind(std::span<void*const>p)const{return Args{static_cast<const uint16_t*>(p[3]),static_cast<const uint16_t*>(p[4]),static_cast<uint16_t*>(p[8]),static_cast<const uint32_t*>(p[16]),static_cast<const uint32_t*>(p[17]),rows*count};}
#ifdef OWN_RT_HOST_ONLY
 void run(std::span<void*const>p)const override{auto a=bind(p);if(!*a.active||*a.error)return;for(unsigned k=0;k<a.n;++k)a.out[k]=act(a.y[k],a.py[k]);}
#else
 sycl::event submit(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&deps)const override{
  auto a=bind(p);const size_t groups=(a.n+ACT_WG-1)/ACT_WG;
  return ownrt::prepared_submit(q,[=,p35_range0=sycl::nd_range<1>(groups*ACT_WG,ACT_WG)](sycl::handler& h){
   h.parallel_for(p35_range0,packet26::checked([=](sycl::nd_item<1>it){
    if(!*a.active||*a.error)return;const unsigned k=unsigned(it.get_global_linear_id());if(k<a.n)a.out[k]=act(a.y[k],a.py[k]);
   }));
  });
 }
#endif
};

// ---------------------------------------------------------------------------------------------------------
// Kernel shells: the production p90exp / p100 kernel bodies with `chains` replaced by the diet chains.
// ---------------------------------------------------------------------------------------------------------
struct GateUp final:p49b::Base {   // exp-diet
 using Production=p90exp::Kernel<Type::IQ2_S,2560,64,false,true>;
 static constexpr unsigned K=2560,WG=64,V=Production::V,P=Production::P,SG=Production::SG,RowsPerGroup=Production::RowsPerGroup;
 static_assert(V==8&&P==4&&SG==2&&RowsPerGroup==8);
 unsigned rows=640,count=10,experts=512;
 p39::Bound bind(std::span<void*const>p)const{Production base;base.rows=rows;base.count=count;base.experts=experts;return base.bind(p);}
 static std::array<float,V> chains(const uint8_t*w,const uint16_t*x,unsigned lane){return diet_chains<K,V>(w,x,lane);}
#ifdef OWN_RT_HOST_ONLY
 void run(std::span<void*const>p)const override{
  auto b=bind(p);unsigned total=rows*count,groups=(total+RowsPerGroup-1)/RowsPerGroup;
  for(unsigned group=0;group<groups;++group)for(unsigned sub=0;sub<SG;++sub)for(unsigned rr=0;rr<V;++rr){
   unsigned logical=Production::logical_row(group,sub,rr*P);if(logical>=total)continue;
   unsigned row=logical%rows,slot=logical/rows,stream=sub%2;
   auto route=b.routes[slot];bool ok=iq3::valid_route(route,experts,rows,rows),valid=ok&&row<route.row_count;
   float values[P]{};if(valid){size_t source=size_t(route.expert_id)*rows+route.row_begin+row;
    for(unsigned lane=0;lane<P;++lane)values[lane]=p49dvirtual::local_tree<V>(chains((stream?b.peer:b.w)+source*b.rb,b.x,lane));
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
   h.parallel_for(p35_range0,packet26::checked([=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
    auto sg=it.get_sub_group();unsigned lane=sg.get_local_linear_id(),sub=it.get_local_linear_id()/32,physical=lane%P,stream=sub%2;
    unsigned logical=Production::logical_row(it.get_group_linear_id(),sub,lane),row=logical%b.rows,slot=logical/b.rows;bool in_range=logical<total;
    iq3::Route route{};if(in_range)route=b.routes[slot];bool ok=in_range&&iq3::valid_route(route,b.experts,b.rows,b.rows),valid=ok&&row<route.row_count;
    float value=0;if(valid){size_t source=size_t(route.expert_id)*b.rows+route.row_begin+row;
     value=p49dvirtual::local_tree<V>(chains((stream?b.peer:b.w)+source*b.rb,b.x,physical));
    }
    for(unsigned width=1;width<P;width*=2){float rhs=sycl::select_from_group(sg,value,(lane+width)%32);if(physical%(2*width)==0)value=value+rhs;}
    if(in_range&&!physical){(stream?b.py:b.y)[logical]=iq3::bf16_bits(valid?value:iq3::bits_float(0x7fc00000));
     if(!row){(stream?b.peer_status:b.status)[slot]=!ok;if(!ok&&*b.active){uint32_t expected=0;sycl::atomic_ref<uint32_t,sycl::memory_order::relaxed,sycl::memory_scope::device,sycl::access::address_space::global_space>(*b.error).compare_exchange_strong(expected,1);}}
    }
   }));
  });
 }
#endif
};

struct GateUpAct final:p49b::Base {   // exp-act-epilogue: GateUp + SLM gate<->up exchange + activation; p[8]=out
 using Production=p90exp::Kernel<Type::IQ2_S,2560,64,false,true>;
 static constexpr unsigned K=2560,WG=64,V=Production::V,P=Production::P,SG=Production::SG,RowsPerGroup=Production::RowsPerGroup;
 static_assert(V==8&&P==4&&SG==2&&RowsPerGroup==8);
 unsigned rows=640,count=10,experts=512;
 p39::Bound bind(std::span<void*const>p)const{Production base;base.rows=rows;base.count=count;base.experts=experts;auto b=base.bind(p);b.out=static_cast<uint16_t*>(p[8]);return b;}
 static std::array<float,V> chains(const uint8_t*w,const uint16_t*x,unsigned lane){return diet_chains<K,V>(w,x,lane);}
 // The separate production launch writes `out` only when (active && !error) at ITS start and, because gate/up
 // sets error for any invalid route before it runs, only when every route of this launch is valid.
 static bool enabled(const p39::Bound&b,uint32_t error_at_start){
  if(!*b.active||error_at_start)return false;
  for(unsigned slot=0;slot<b.count;++slot)if(!iq3::valid_route(b.routes[slot],b.experts,b.rows,b.rows))return false;
  return true;
 }
#ifdef OWN_RT_HOST_ONLY
 void run(std::span<void*const>p)const override{
  auto b=bind(p);unsigned total=rows*count,groups=(total+RowsPerGroup-1)/RowsPerGroup;const bool write_out=enabled(b,*b.error);
  for(unsigned group=0;group<groups;++group){uint16_t gate_slm[V];
   for(unsigned sub=0;sub<SG;++sub)for(unsigned rr=0;rr<V;++rr){
    unsigned logical=Production::logical_row(group,sub,rr*P);if(logical>=total)continue;
    unsigned row=logical%rows,slot=logical/rows,stream=sub%2;
    auto route=b.routes[slot];bool ok=iq3::valid_route(route,experts,rows,rows),valid=ok&&row<route.row_count;
    float values[P]{};if(valid){size_t source=size_t(route.expert_id)*rows+route.row_begin+row;
     for(unsigned lane=0;lane<P;++lane)values[lane]=p49dvirtual::local_tree<V>(chains((stream?b.peer:b.w)+source*b.rb,b.x,lane));
    }
    for(unsigned width=1;width<P;width*=2)for(unsigned lane=0;lane<P;lane+=2*width)values[lane]=values[lane]+values[lane+width];
    uint16_t bits=iq3::bf16_bits(valid?values[0]:iq3::bits_float(0x7fc00000));(stream?b.py:b.y)[logical]=bits;
    if(stream==0)gate_slm[rr]=bits;else if(write_out)b.out[logical]=act(gate_slm[rr],bits);
    if(!row){(stream?b.peer_status:b.status)[slot]=!ok;if(!ok&&*b.active&&!*b.error)*b.error=1;}
   }
  }
 }
#else
 sycl::event submit(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&deps)const override{
  auto b=bind(p);unsigned total=rows*count,groups=(total+RowsPerGroup-1)/RowsPerGroup;(void)deps;
  return ownrt::prepared_submit(q,[=,p35_range0=sycl::nd_range<1>(size_t(groups)*WG,WG)](sycl::handler& h){
   sycl::local_accessor<uint16_t,1> gate_slm(sycl::range<1>(V),h);
   h.parallel_for(p35_range0,packet26::checked([=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
    auto sg=it.get_sub_group();unsigned lane=sg.get_local_linear_id(),sub=it.get_local_linear_id()/32,physical=lane%P,stream=sub%2;
    const uint32_t error_at_start=*b.error;
    unsigned logical=Production::logical_row(it.get_group_linear_id(),sub,lane),row=logical%b.rows,slot=logical/b.rows;bool in_range=logical<total;
    iq3::Route route{};if(in_range)route=b.routes[slot];bool ok=in_range&&iq3::valid_route(route,b.experts,b.rows,b.rows),valid=ok&&row<route.row_count;
    float value=0;if(valid){size_t source=size_t(route.expert_id)*b.rows+route.row_begin+row;
     value=p49dvirtual::local_tree<V>(chains((stream?b.peer:b.w)+source*b.rb,b.x,physical));
    }
    for(unsigned width=1;width<P;width*=2){float rhs=sycl::select_from_group(sg,value,(lane+width)%32);if(physical%(2*width)==0)value=value+rhs;}
    uint16_t bits=iq3::bf16_bits(valid?value:iq3::bits_float(0x7fc00000));
    if(in_range&&!physical){(stream?b.py:b.y)[logical]=bits;if(stream==0)gate_slm[lane/P]=bits;
     if(!row){(stream?b.peer_status:b.status)[slot]=!ok;if(!ok&&*b.active){uint32_t expected=0;sycl::atomic_ref<uint32_t,sycl::memory_order::relaxed,sycl::memory_scope::device,sycl::access::address_space::global_space>(*b.error).compare_exchange_strong(expected,1);}}
    }
    it.barrier(sycl::access::fence_space::local_space);
    if(in_range&&!physical&&stream==1&&enabled(b,error_at_start))b.out[logical]=act(gate_slm[lane/P],bits);
   }));
  });
 }
#endif
};

struct Down final:p49b::Base {   // down-diet
 using Production=p100::Kernel<2>;
 static constexpr unsigned K=640,WG=64,V=Production::V,P=Production::P,SG=Production::SG,RowsPerGroup=Production::RowsPerGroup;
 static_assert(V==16&&P==2&&SG==2&&RowsPerGroup==32);
 unsigned rows=2560,count=10,experts=512;
 p39::Bound bind(std::span<void*const>p)const{Production base;base.rows=rows;base.count=count;base.experts=experts;return base.bind(p);}
 static std::array<float,V> chains(const uint8_t*w,size_t source,const uint16_t*x,unsigned lane){return diet_tile_chains<false>(w,source,x,lane);}
#ifdef OWN_RT_HOST_ONLY
 void run(std::span<void*const>p)const override{
  auto b=bind(p);unsigned total=rows*count,groups=(total+RowsPerGroup-1)/RowsPerGroup;
  for(unsigned group=0;group<groups;++group)for(unsigned sub=0;sub<SG;++sub)for(unsigned rr=0;rr<V;++rr){
   unsigned logical=Production::logical_row(Production::mapped_group(group,rows,count),sub,rr*P);if(logical>=total)continue;
   unsigned row=logical%rows,slot=logical/rows;
   auto route=b.routes[slot];bool ok=iq3::valid_route(route,experts,rows,rows),valid=ok&&row<route.row_count;
   float values[P]{};if(valid){size_t source=size_t(route.expert_id)*rows+route.row_begin+row;
    for(unsigned lane=0;lane<P;++lane)values[lane]=p49dvirtual::local_tree<V>(chains(b.w,source,b.x+slot*K,lane));
   }
   for(unsigned width=1;width<P;width*=2)for(unsigned lane=0;lane<P;lane+=2*width)values[lane]=values[lane]+values[lane+width];
   b.y[logical]=iq3::bf16_bits(valid?values[0]:iq3::bits_float(0x7fc00000));
   if(!row){b.status[slot]=!ok;if(!ok&&*b.active&&!*b.error)*b.error=1;}
  }
 }
#else
 sycl::event submit(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&deps)const override{
  auto b=bind(p);unsigned total=rows*count,groups=(total+RowsPerGroup-1)/RowsPerGroup;(void)deps;
  return ownrt::prepared_submit(q,[=,p35_range0=sycl::nd_range<1>(size_t(groups)*WG,WG)](sycl::handler& h){
   h.parallel_for(p35_range0,packet26::checked([=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
    auto sg=it.get_sub_group();unsigned lane=sg.get_local_linear_id(),sub=it.get_local_linear_id()/32,physical=lane%P;
    unsigned logical=Production::logical_row(Production::mapped_group(it.get_group_linear_id(),b.rows,b.count),sub,lane),row=logical%b.rows,slot=logical/b.rows;bool in_range=logical<total;
    iq3::Route route{};if(in_range)route=b.routes[slot];bool ok=in_range&&iq3::valid_route(route,b.experts,b.rows,b.rows),valid=ok&&row<route.row_count;
    float value=0;if(valid){size_t source=size_t(route.expert_id)*b.rows+route.row_begin+row;
     value=p49dvirtual::local_tree<V>(chains(b.w,source,b.x+slot*K,physical));
    }
    for(unsigned width=1;width<P;width*=2){float rhs=sycl::select_from_group(sg,value,(lane+width)%32);if(physical%(2*width)==0)value=value+rhs;}
    if(in_range&&!physical){b.y[logical]=iq3::bf16_bits(valid?value:iq3::bits_float(0x7fc00000));
     if(!row){b.status[slot]=!ok;if(!ok&&*b.active){uint32_t expected=0;sycl::atomic_ref<uint32_t,sycl::memory_order::relaxed,sycl::memory_scope::device,sycl::access::address_space::global_space>(*b.error).compare_exchange_strong(expected,1);}}
    }
   }));
  });
 }
#endif
};
}
