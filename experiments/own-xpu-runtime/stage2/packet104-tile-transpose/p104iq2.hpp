#pragma once
#include "p104_layout.hpp"
#include "p90_expert.hpp"
namespace p104iq2 {
using iq3::Type;using p65::RawTile;using p65::decode_tile;
template<Type T,unsigned K,unsigned V,bool Packed=false>inline std::array<float,V> wide_chains(const uint8_t*w,size_t source,const uint16_t*x,unsigned physical){
 constexpr auto l=p49bgemv::layout(T,K);std::array<float,V> sums{};
 for(unsigned step=0;step<(K+255)/256;++step){
  if constexpr(T==Type::IQ2_S){
   static_assert(V==8);unsigned first=step*256+8*physical*V;
   uint32_t codes[4];
#if defined(__SYCL_DEVICE_ONLY__)
   sycl::vec<uint32_t,4> words;words.load(0,sycl::address_space_cast<sycl::access::address_space::global_space,sycl::access::decorated::no>(reinterpret_cast<const uint32_t*>(p104::address(w,source,820,0,16,step*64+physical*16))));
   #pragma unroll
   for(unsigned i=0;i<4;++i)codes[i]=words[i];
#else
   for(unsigned i=0;i<4;++i)codes[i]=p49bgemv::load32(p104::address(w,source,820,0,16,step*64+physical*16)+4*i);
#endif
   uint16_t high=p49bgemv::load16(p104::address(w,source,820,640,2,step*8+physical*2));
   uint16_t scales=p49bgemv::load16(p104::address(w,source,820,720,2,step*8+physical*2));
   uint16_t half=p49bgemv::load16(p104::address(w,source,820,800,2,2*step));
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
  }else{static_assert(T==Type::IQ2_S);}
 }return sums;
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
 static std::array<float,V> chains(const uint8_t*w,size_t source,const uint16_t*x,unsigned lane){return wide_chains<T,K,V>(w,source,x,lane);}
#ifdef OWN_RT_HOST_ONLY
 void run(std::span<void*const>p)const override{
  auto b=bind(p);unsigned total=rows*count,groups=(total+RowsPerGroup-1)/RowsPerGroup;
  for(unsigned group=0;group<groups;++group)for(unsigned sub=0;sub<SG;++sub)for(unsigned rr=0;rr<V;++rr){
   unsigned logical=logical_row(group,sub,rr*P);if(logical>=total)continue;
   unsigned row=logical%rows,slot=logical/rows,stream=paired?sub%2:0;
   auto route=b.routes[slot];bool ok=iq3::valid_route(route,experts,rows,rows),valid=ok&&row<route.row_count;
   float values[P]{};if(valid){size_t source=size_t(route.expert_id)*rows+route.row_begin+row;
    for(unsigned lane=0;lane<P;++lane)values[lane]=p49dvirtual::local_tree<V>(chains((stream?b.peer:b.w),source,b.x+(paired?0:slot*K),lane));
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
    float value=0;if(valid){size_t source=size_t(route.expert_id)*b.rows+route.row_begin+row;
     value=p49dvirtual::local_tree<V>(chains((stream?b.peer:b.w),source,b.x+(paired?0:slot*K),physical));
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
