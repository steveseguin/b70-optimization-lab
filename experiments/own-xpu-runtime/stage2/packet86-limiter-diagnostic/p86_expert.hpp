#pragma once
// NON-EXACT diagnostic kernels. No promotion or output-quality claim.
#include "p65_expert.hpp"
namespace p86exp {
using iq3::Type;using p65::RawTile;using p65::p73_deep_chains;using p65::p73_down_chains;using p65::pipelined_chains;
inline uint32_t load32(const uint8_t*p){return *reinterpret_cast<const volatile uint32_t*>(p);}
inline uint16_t load16(const uint8_t*p){return *reinterpret_cast<const volatile uint16_t*>(p);}
template<Type T,unsigned Mode>inline void decode(const RawTile&t,unsigned k,float(&v)[8]){
 if constexpr(Mode==1){
  // Consume all same raw weight bytes, including metadata, without grid/half decode.
  if constexpr(T==Type::IQ2_S){const unsigned raw[8]={t.a&255,t.a>>8,t.high,t.scale,unsigned(t.half)&255,unsigned(t.half)>>8,t.a&255,t.a>>8};for(unsigned j=0;j<8;++j)v[j]=float(raw[j]);}
  else {for(unsigned j=0;j<8;++j)v[j]=float(((j<4?t.a:t.b)>>(8*(j%4)))&255)+float(j%2?t.half>>8:t.half&255);}
 }else if constexpr(Mode==2&&T==Type::IQ2_S){
  float d=iq3::half(t.half);unsigned i=k%256;
  float scale=(d*(0.5f+float((t.scale>>(4*((i/16)%2)))&15)))*0.25f;
  // Register grid/sign constants, preserving scale math and multiply/add chains.
  constexpr int grid[8]={1,-3,5,-7,9,-11,13,-15};
  for(unsigned j=0;j<8;++j)v[j]=scale*float(grid[j]);
 }else p65::decode_tile<T>(t,k,v);
}
template<Type T,unsigned K,unsigned V,unsigned Mode>inline std::array<float,V> diagnostic_chains(const uint8_t*w,const uint16_t*x,unsigned physical){
 if constexpr(Mode==3)return p65::wide_chains<T,K,V>(w,x,physical);
 constexpr auto l=p49bgemv::layout(T,K);std::array<float,V> sums{};
 for(unsigned step=0;step<(K+255)/256;++step){
  if constexpr(T==Type::IQ2_S){
   static_assert(V==8);unsigned first=step*256+8*physical*V;
   uint32_t codes[4];
#if 0
   sycl::vec<uint32_t,4> words;words.load(0,sycl::address_space_cast<sycl::access::address_space::global_space,sycl::access::decorated::no>(reinterpret_cast<const uint32_t*>(w+step*64+physical*16)));
   #pragma unroll
   for(unsigned i=0;i<4;++i)codes[i]=words[i];
#else
   for(unsigned i=0;i<4;++i)codes[i]=load32(w+step*64+physical*16+4*i);
#endif
   uint16_t high=load16(w+l.high+step*8+physical*2);
   uint16_t scales=load16(w+l.scales+step*8+physical*2);
   uint16_t half=load16(w+l.halves+2*step);
   #pragma unroll
   for(unsigned chain=0;chain<V;++chain){unsigned k=first+chain*8;RawTile t;t.a=(codes[chain/2]>>(16*(chain%2)))&65535;t.high=(high>>(8*(chain/4)))&255;t.scale=(scales>>(8*(chain/4)))&255;t.half=half;
    float values[8];decode<T,Mode>(t,k,values);
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
    for(unsigned i=0;i<4;++i)codes[i]=load32(w+block*16+4*i);
#endif
    uint16_t half=load16(w+l.halves+2*block);
    #pragma unroll
    for(unsigned c=0;c<4;++c){unsigned chain=block_in_lane*4+c,k=first+8*c;RawTile t;t.a=codes[(c%2)*2];t.b=codes[(c%2)*2+1];t.half=half;
     float values[8];decode<T,Mode>(t,k,values);
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
template<Type T,unsigned K,unsigned WG,bool Prefetch,bool Wide=false,unsigned Followup=0,unsigned Mode=0>struct Kernel final:p49b::Base {
 static constexpr bool paired=T==Type::IQ2_S;
 static constexpr unsigned V=paired?8:16,P=32/V,SG=WG/32,RowsPerGroup=(paired?SG/2:SG)*V;
 static_assert(WG==64||WG==128);static_assert((paired&&K==2560)||(!paired&&K==640));
 unsigned rows=paired?640:2560,count=10,experts=512;
 p39::Bound bind(std::span<void*const>p)const{
  p49dvirtual::Kernel<T,K,paired?2:3> base;base.rows=rows;base.count=count;base.experts=experts;return base.bind(p);
 }
 static unsigned logical_row(unsigned group,unsigned sub,unsigned lane){return (group*(paired?SG/2:SG)+(paired?sub/2:sub))*V+lane/P;}
 static std::array<float,V> chains(const uint8_t*w,const uint16_t*x,unsigned lane){
  if constexpr(Followup==1&&T==Type::IQ2_S)return p73_deep_chains<T,K,V>(w,x,lane);
  else if constexpr(Followup==2&&T==Type::IQ4_NL)return p73_down_chains<T,K,V>(w,x,lane);
  else if constexpr(Wide)return diagnostic_chains<T,K,V,Mode>(w,x,lane);
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
   float values[P]{};if(valid){size_t source=size_t(Mode==3?0:route.expert_id)*rows+route.row_begin+row;
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
  return q.submit([&](sycl::handler&h){h.depends_on(deps);
   h.parallel_for(sycl::nd_range<1>(size_t(groups)*WG,WG),[=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
    auto sg=it.get_sub_group();unsigned lane=sg.get_local_linear_id(),sub=it.get_local_linear_id()/32,physical=lane%P,stream=paired?sub%2:0;
    unsigned logical=logical_row(it.get_group_linear_id(),sub,lane),row=logical%b.rows,slot=logical/b.rows;bool in_range=logical<total;
    iq3::Route route{};if(in_range)route=b.routes[slot];bool ok=in_range&&iq3::valid_route(route,b.experts,b.rows,b.rows),valid=ok&&row<route.row_count;
    float value=0;if(valid){size_t source=size_t(Mode==3?0:route.expert_id)*b.rows+route.row_begin+row;
     value=p49dvirtual::local_tree<V>(chains((stream?b.peer:b.w)+source*b.rb,b.x+(paired?0:slot*K),physical));
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
