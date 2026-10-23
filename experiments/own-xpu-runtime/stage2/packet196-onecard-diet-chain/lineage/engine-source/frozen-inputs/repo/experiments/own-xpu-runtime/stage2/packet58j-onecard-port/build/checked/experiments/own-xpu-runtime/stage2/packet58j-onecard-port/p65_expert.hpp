#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58-onecard-diet-engine/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58-onecard-diet-engine/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/p65_expert.hpp"
#ifndef OWN_RT_HOST_ONLY
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58-onecard-diet-engine/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/build/checked/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/prepared_submission.hpp"
#endif
#line 1
#pragma once
// Packet65 changes physical scheduling and raw-load issue order only.
// The 32 logical sums, eight products per tile, adjacent tree and BF16 stores
// are the packet64/49 arithmetic. No local table, persistent grid or new sum.
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58-onecard-diet-engine/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/build/checked/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/p49d_expert.hpp"

namespace p65 {
using iq3::Type;
// Raw operands only: staging decoded vectors would repeat p53b register spills.
struct RawTile {
 uint32_t a=0,b=0;
 uint16_t half=0;
 uint8_t high=0,scale=0;
 std::array<uint16_t,8> x{};
};
template<Type T,unsigned K>inline RawTile load_tile(const uint8_t* w,const uint16_t* x,unsigned k){
 constexpr auto l=p49bgemv::layout(T,K);RawTile t;
 if constexpr(T==Type::IQ2_S){
  unsigned block=k/256,i=k%256,q=i/8;
  t.a=p49bgemv::load16(w+block*64+q*2);
  t.high=w[l.high+block*8+q/4];t.scale=w[l.scales+block*8+i/32];
  t.half=p49bgemv::load16(w+l.halves+2*block);
 }else{
  unsigned block=k/32,off=k%32;const auto* codes=w+16*block+off%16;
  t.a=p49bgemv::load32(codes);t.b=p49bgemv::load32(codes+4);
  t.half=p49bgemv::load16(w+l.halves+2*block);
 }
#if defined(__SYCL_DEVICE_ONLY__)
 sycl::vec<uint16_t,8> inputs;inputs.load(0,sycl::address_space_cast<sycl::access::address_space::global_space,sycl::access::decorated::no>(x+k));
 #pragma unroll
 for(unsigned j=0;j<8;++j)t.x[j]=inputs[j];
#else
 for(unsigned j=0;j<8;++j)t.x[j]=x[k+j];
#endif
 return t;
}
template<Type T>inline void decode_tile(const RawTile&t,unsigned k,float(&v)[8]){
 float d=iq3::half(t.half);
 if constexpr(T==Type::IQ2_S){
  unsigned i=k%256,q=i/8,index=(t.a&255)|(((t.high>>(2*(q%4)))&3)<<8),signs=t.a>>8;
  float scale=(d*(0.5f+float((t.scale>>(4*((i/16)%2)))&15)))*0.25f;
  uint32_t a=p42expert::iq2_words[2*index],b=p42expert::iq2_words[2*index+1];
  bool exceptional=(std::bit_cast<uint32_t>(d)&0x7fffffff)>=0x7f800000||(std::bit_cast<uint32_t>(scale)&0x7fffffff)>0x7f800000;
  #pragma unroll
  for(unsigned j=0;j<8;++j){unsigned magnitude=((j<4?a:b)>>(8*(j%4)))&255;
   if(exceptional)v[j]=(scale*float(magnitude))*float((signs>>j)&1?-1:1);
   else {int signed_magnitude=(signs>>j)&1?-int(magnitude):int(magnitude);v[j]=scale*float(signed_magnitude);}
  }
 }else{
  unsigned off=k%32;
  #pragma unroll
  for(unsigned j=0;j<8;++j){unsigned code=((j<4?t.a:t.b)>>(8*(j%4)))&255,q=(code>>(4*(off/16)))&15;v[j]=d*float(p33::level_bank(q));}
 }
}
// Pipeline the next tile of this logical lane (k+256), before consuming the
// current tile. Only one raw tile lookahead; no FP32 partial-sum reassociation.
// Chain-major traversal interleaves independent sums differently, while each
// individual chain sees exactly k=8*logical_lane+256*step, j=0..7.
template<Type T,unsigned K,unsigned V>inline std::array<float,V> pipelined_chains(const uint8_t*w,const uint16_t*x,unsigned physical){
 std::array<float,V> sums{};
 #pragma unroll
 for(unsigned chain=0;chain<V;++chain){
  unsigned first=8*(physical*V+chain);
  if(first>=K)continue;
  RawTile current=load_tile<T,K>(w,x,first);
  for(unsigned k=first;k<K;k+=256){
   RawTile next;if(k+256<K)next=load_tile<T,K>(w,x,k+256);
   float values[8];decode_tile<T>(current,k,values);
   #pragma unroll
   for(unsigned j=0;j<8;++j){float product=values[j]*iq3::bits_float(uint32_t(current.x[j])<<16);sums[chain]=sums[chain]+product;}
   current=next;
  }
 }
 return sums;
}
// Fetch each contiguous code/metadata span once, then consume logical chains
// in their production step/chain/j order. IQ2: eight adjacent logical lanes
// share a half scale and two high/scale bytes; IQ4: four lanes share one
// 32-weight code block/half. No layout change and no extra decoded vector bank.
template<Type T,unsigned K,unsigned V,bool Packed=false>inline std::array<float,V> wide_chains(const uint8_t*w,const uint16_t*x,unsigned physical){
 constexpr auto l=p49bgemv::layout(T,K);std::array<float,V> sums{};
 for(unsigned step=0;step<(K+255)/256;++step){
  if constexpr(T==Type::IQ2_S){
   static_assert(V==8);unsigned first=step*256+8*physical*V;
   uint32_t codes[4];
#if defined(__SYCL_DEVICE_ONLY__)
   sycl::vec<uint32_t,4> words;words.load(0,sycl::address_space_cast<sycl::access::address_space::global_space,sycl::access::decorated::no>(reinterpret_cast<const uint32_t*>(w+step*64+physical*16)));
   #pragma unroll
   for(unsigned i=0;i<4;++i)codes[i]=words[i];
#else
   for(unsigned i=0;i<4;++i)codes[i]=p49bgemv::load32(w+step*64+physical*16+4*i);
#endif
   uint16_t high=p49bgemv::load16(w+l.high+step*8+physical*2);
   uint16_t scales=p49bgemv::load16(w+l.scales+step*8+physical*2);
   uint16_t half=p49bgemv::load16(w+l.halves+2*step);
   #pragma unroll
   for(unsigned chain=0;chain<V;++chain){unsigned k=first+chain*8;RawTile t;t.a=(codes[chain/2]>>(16*(chain%2)))&65535;t.high=(high>>(8*(chain/4)))&255;t.scale=(scales>>(8*(chain/4)))&255;t.half=half;
    float values[8];decode_tile<T>(t,k,values);
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
  }else{
   static_assert(V==16);
   #pragma unroll
   for(unsigned block_in_lane=0;block_in_lane<V/4;++block_in_lane){
    unsigned first=step*256+8*(physical*V+block_in_lane*4);if(first>=K)continue;
    unsigned block=first/32;uint32_t codes[4];
#if defined(__SYCL_DEVICE_ONLY__)
    sycl::vec<uint32_t,4> words;words.load(0,sycl::address_space_cast<sycl::access::address_space::global_space,sycl::access::decorated::no>(reinterpret_cast<const uint32_t*>(w+block*16)));
    #pragma unroll
    for(unsigned i=0;i<4;++i)codes[i]=words[i];
#else
    for(unsigned i=0;i<4;++i)codes[i]=p49bgemv::load32(w+block*16+4*i);
#endif
    uint16_t half=p49bgemv::load16(w+l.halves+2*block);
    #pragma unroll
    for(unsigned c=0;c<4;++c){unsigned chain=block_in_lane*4+c,k=first+8*c;RawTile t;t.a=codes[(c%2)*2];t.b=codes[(c%2)*2+1];t.half=half;
     float values[8];decode_tile<T>(t,k,values);
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
  }
 }
 return sums;
}
template<Type T,unsigned K,unsigned V>inline std::array<float,V> p73_deep_chains(const uint8_t*w,const uint16_t*x,unsigned physical){
 constexpr auto l=p49bgemv::layout(T,K);std::array<float,V> sums{};
 for(unsigned pair=0;pair<(K+255)/256;pair+=2){
  uint32_t raw[2][4];uint16_t highs[2],scales2[2],halves[2];
  for(unsigned t=0;t<2;++t){unsigned step=pair+t;
#if defined(__SYCL_DEVICE_ONLY__)
   sycl::vec<uint32_t,4> words;words.load(0,sycl::address_space_cast<sycl::access::address_space::global_space,sycl::access::decorated::no>(reinterpret_cast<const uint32_t*>(w+step*64+physical*16)));
   for(unsigned i=0;i<4;++i)raw[t][i]=words[i];
#else
   for(unsigned i=0;i<4;++i)raw[t][i]=p49bgemv::load32(w+step*64+physical*16+4*i);
#endif
   highs[t]=p49bgemv::load16(w+l.high+step*8+physical*2);scales2[t]=p49bgemv::load16(w+l.scales+step*8+physical*2);halves[t]=p49bgemv::load16(w+l.halves+2*step);
  }
  for(unsigned t=0;t<2;++t){unsigned step=pair+t;
  if constexpr(T==Type::IQ2_S){
   static_assert(V==8);unsigned first=step*256+8*physical*V;
   const auto& codes=raw[t];uint16_t high=highs[t],scales=scales2[t],half=halves[t];
   #pragma unroll
   for(unsigned chain=0;chain<V;++chain){unsigned k=first+chain*8;RawTile t;t.a=(codes[chain/2]>>(16*(chain%2)))&65535;t.high=(high>>(8*(chain/4)))&255;t.scale=(scales>>(8*(chain/4)))&255;t.half=half;
    float values[8];decode_tile<T>(t,k,values);
#if defined(__SYCL_DEVICE_ONLY__)
    sycl::vec<uint16_t,8> inputs;inputs.load(0,sycl::address_space_cast<sycl::access::address_space::global_space,sycl::access::decorated::no>(x+k));
#endif
    #pragma unroll
    for(unsigned j=0;j<8;++j){
#if defined(__SYCL_DEVICE_ONLY__)
     uint16_t bits=inputs[j];
#else
     uint16_t bits=x[k+j];
#endif
     float product=values[j]*iq3::bits_float(uint32_t(bits)<<16);sums[chain]=sums[chain]+product;
    }
   }
  }
  }
 }
 return sums;
}
template<Type T,unsigned K,unsigned V>inline std::array<float,V> p73_down_chains(const uint8_t*w,const uint16_t*x,unsigned physical){
 constexpr auto l=p49bgemv::layout(T,K);std::array<float,V> sums{};
 for(unsigned step=0;step<(K+255)/256;++step){
  for(unsigned pair=0;pair<2;++pair){
   static_assert(V==16);
   unsigned tilefirst=step*256+8*physical*V+pair*64;if(tilefirst>=K)continue;
   uint32_t raw[8];uint16_t halves[2];
#if defined(__SYCL_DEVICE_ONLY__)
   sycl::vec<uint32_t,8> words;words.load(0,sycl::address_space_cast<sycl::access::address_space::global_space,sycl::access::decorated::no>(reinterpret_cast<const uint32_t*>(w+(tilefirst/32)*16)));
   sycl::vec<uint16_t,2> scales;scales.load(0,sycl::address_space_cast<sycl::access::address_space::global_space,sycl::access::decorated::no>(reinterpret_cast<const uint16_t*>(w+l.halves+2*(tilefirst/32))));
   for(unsigned i=0;i<8;++i)raw[i]=words[i];for(unsigned i=0;i<2;++i)halves[i]=scales[i];
#else
   for(unsigned i=0;i<8;++i)raw[i]=p49bgemv::load32(w+(tilefirst/32)*16+4*i);for(unsigned i=0;i<2;++i)halves[i]=p49bgemv::load16(w+l.halves+2*(tilefirst/32+i));
#endif
   #pragma unroll
   for(unsigned block_in_lane=0;block_in_lane<2;++block_in_lane){
    unsigned first=step*256+8*(physical*V+pair*8+block_in_lane*4);if(first>=K)continue;
    const uint32_t* codes=raw+block_in_lane*4;uint16_t half=halves[block_in_lane];
    #pragma unroll
    for(unsigned c=0;c<4;++c){unsigned chain=pair*8+block_in_lane*4+c,k=first+8*c;RawTile t;t.a=codes[(c%2)*2];t.b=codes[(c%2)*2+1];t.half=half;
     float values[8];decode_tile<T>(t,k,values);
#if defined(__SYCL_DEVICE_ONLY__)
     sycl::vec<uint16_t,8> inputs;inputs.load(0,sycl::address_space_cast<sycl::access::address_space::global_space,sycl::access::decorated::no>(x+k));
#endif
     #pragma unroll
     for(unsigned j=0;j<8;++j){
#if defined(__SYCL_DEVICE_ONLY__)
      uint16_t bits=inputs[j];
#else
      uint16_t bits=x[k+j];
#endif
      float product=values[j]*iq3::bits_float(uint32_t(bits)<<16);sums[chain]=sums[chain]+product;
     }
    }
   }
  }
 }
 return sums;
}
template<Type T,unsigned K,unsigned WG,bool Prefetch,bool Wide=false,unsigned Followup=0>struct Kernel final:p49b::Base {
 static constexpr bool paired=T==Type::IQ2_S;
 static constexpr unsigned V=paired?8:16,P=32/V,SG=WG/32,RowsPerGroup=(paired?SG/2:SG)*V;
 static_assert(WG==64||WG==128);static_assert((paired&&K==2560)||(!paired&&K==640));
 unsigned rows=paired?640:2560,count=10,experts=512;
 p39::Bound bind(std::span<void*const>p)const{
  p49dvirtual::Kernel<T,K,paired?2:3> base;base.rows=rows;base.count=count;base.experts=experts;return base.bind(p);
 }
 static unsigned logical_row(unsigned group,unsigned sub,unsigned lane){return (group*(paired?SG/2:SG)+(paired?sub/2:sub))*V+lane/P;}
 static std::array<float,V> chains(const uint8_t*w,const uint16_t*x,unsigned lane){
  if constexpr(Followup==3||(Followup==4&&T==Type::IQ2_S)||(Followup==5&&T==Type::IQ4_NL))return wide_chains<T,K,V,true>(w,x,lane);
  else if constexpr(Followup==1&&T==Type::IQ2_S)return p73_deep_chains<T,K,V>(w,x,lane);
  else if constexpr(Followup==2&&T==Type::IQ4_NL)return p73_down_chains<T,K,V>(w,x,lane);
  else if constexpr(Wide)return wide_chains<T,K,V>(w,x,lane);
  else if constexpr(Prefetch)return pipelined_chains<T,K,V>(w,x,lane);
  else return p49dvirtual::lane_chains<T,K,V>(w,x,lane);
 }
#ifdef OWN_RT_HOST_ONLY
 void run(std::span<void*const>p)const override{
  auto b=bind(p);unsigned total=rows*count,groups=(total+RowsPerGroup-1)/RowsPerGroup;
  for(unsigned group=0;group<groups;++group)for(unsigned sub=0;sub<SG;++sub)for(unsigned rr=0;rr<V;++rr){
   unsigned logical=logical_row(group,sub,rr*P);if(logical>=total)continue;
   unsigned row=logical%rows,slot=logical/rows,stream=paired?sub%2:0;
   auto route=b.routes[slot];bool ok=iq3::valid_route(route,experts,rows,rows),valid=ok&&row<route.row_count;
   float values[P]{};if(valid){size_t source=size_t(route.expert_id)*rows+route.row_begin+row;
    for(unsigned lane=0;lane<P;++lane)values[lane]=p49dvirtual::local_tree<V>(chains((stream?b.peer:b.w)+source*b.rb,b.x+(paired?0:slot*K),lane));
   }
   for(unsigned width=1;width<P;width*=2)for(unsigned lane=0;lane<P;lane+=2*width)values[lane]=values[lane]+values[lane+width];
   (stream?b.py:b.y)[logical]=iq3::bf16_bits(valid?values[0]:iq3::bits_float(0x7fc00000));
   if(!row){(stream?b.peer_status:b.status)[slot]=!ok;if(!ok&&*b.active&&!*b.error)*b.error=1;}
  }
 }
#else
 sycl::event submit(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&deps)const override{
  auto b=bind(p);unsigned total=rows*count,groups=(total+RowsPerGroup-1)/RowsPerGroup;
  return ownrt::prepared_submit(q,[=,p35_range0=sycl::nd_range<1>(size_t(groups)*WG,WG)](sycl::handler& h){
   h.parallel_for(p35_range0,packet26::checked([=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
    auto sg=it.get_sub_group();unsigned lane=sg.get_local_linear_id(),sub=it.get_local_linear_id()/32,physical=lane%P,stream=paired?sub%2:0;
    unsigned logical=logical_row(it.get_group_linear_id(),sub,lane),row=logical%b.rows,slot=logical/b.rows;bool in_range=logical<total;
    iq3::Route route{};if(in_range)route=b.routes[slot];bool ok=in_range&&iq3::valid_route(route,b.experts,b.rows,b.rows),valid=ok&&row<route.row_count;
    float value=0;if(valid){size_t source=size_t(route.expert_id)*b.rows+route.row_begin+row;
     value=p49dvirtual::local_tree<V>(chains((stream?b.peer:b.w)+source*b.rb,b.x+(paired?0:slot*K),physical));
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
} // namespace p65
