#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet157-draft-decomp/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet136-record-bundle/p95_expert.hpp"
#ifndef OWN_RT_HOST_ONLY
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet157-draft-decomp/build/checked/experiments/own-xpu-runtime/stage2/packet157-draft-decomp/prepared_submission.hpp"
#endif
#line 1
#pragma once
// E3: next-tile IQ2 table words, not raw-code lookahead or activation packing.
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet157-draft-decomp/build/checked/experiments/own-xpu-runtime/stage2/packet157-draft-decomp/p65_expert.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet157-draft-decomp/build/checked/experiments/own-xpu-runtime/stage2/packet157-draft-decomp/p90_layout.hpp"
namespace p95exp {
using iq3::Type;
// One 64-bit table word contains all eight magnitudes. No FP32 decoded bank.
struct GridWord {uint32_t a=0,b=0;};
inline GridWord lookup(unsigned code,unsigned high,unsigned q){
 unsigned index=(code&255)|(((high>>(2*(q%4)))&3)<<8);
 return {p42expert::iq2_words[2*index],p42expert::iq2_words[2*index+1]};
}
template<unsigned K>inline GridWord grid_word(const uint8_t*w,unsigned k){
 constexpr auto l=p49bgemv::layout(Type::IQ2_S,K);
 unsigned block=k/256,q=(k%256)/8;
 unsigned code=p49bgemv::load16(w+block*64+q*2);
 unsigned high=w[l.high+block*8+q/4];
 return lookup(code,high,q);
}
inline void decode_grid(const p65::RawTile&t,unsigned k,GridWord grid,float(&v)[8],float d){
 unsigned i=k%256,signs=t.a>>8;
 float scale=(d*(0.5f+float((t.scale>>(4*((i/16)%2)))&15)))*0.25f;
 bool exceptional=(std::bit_cast<uint32_t>(d)&0x7fffffff)>=0x7f800000||(std::bit_cast<uint32_t>(scale)&0x7fffffff)>0x7f800000;
 #pragma unroll
 for(unsigned j=0;j<8;++j){unsigned magnitude=((j<4?grid.a:grid.b)>>(8*(j%4)))&255;
  if(exceptional)v[j]=(scale*float(magnitude))*float((signs>>j)&1?-1:1);
  else {int signed_magnitude=(signs>>j)&1?-int(magnitude):int(magnitude);v[j]=scale*float(signed_magnitude);}
 }
}
template<unsigned K,unsigned V,bool HalfCache=false>inline std::array<float,V> grid_chains(const uint8_t*w,const uint16_t*x,unsigned physical){
 static_assert(V==8&&K==2560);
 constexpr auto l=p49bgemv::layout(Type::IQ2_S,K);std::array<float,V> sums{};
 GridWord current=grid_word<K>(w,8*physical*V);
 for(unsigned step=0;step<K/256;++step){
  unsigned first=step*256+8*physical*V;
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
  float decoded;
  if constexpr(HalfCache)decoded=iq3::bits_float(p49bgemv::load32(w+l.halves+4*step));
  else decoded=iq3::half(p49bgemv::load16(w+l.halves+2*step));
  #pragma unroll
  for(unsigned chain=0;chain<V;++chain){unsigned k=first+chain*8;p65::RawTile t;t.a=(codes[chain/2]>>(16*(chain%2)))&65535;t.scale=(scales>>(8*(chain/4)))&255;
   // Prefetch the next logical-chain tile in unchanged step/chain order.
   // At most two raw grid words total, hence at most two for any chain.
   GridWord next;
   if(chain+1<V){
    unsigned nc=chain+1,code=(codes[nc/2]>>(16*(nc%2)))&65535;
    next=lookup(code,(high>>(8*(nc/4)))&255,((k+8)%256)/8);
   }else if(step+1<K/256)next=grid_word<K>(w,(step+1)*256+8*physical*V);
   float values[8];decode_grid(t,k,current,values,decoded);
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
   current=next;
  }
 }
 return sums;
}
template<Type T,unsigned K,unsigned WG,bool Prefetch,bool Wide=false,unsigned Followup=0,bool HalfCache=false>struct Kernel final:p49b::Base {
 static constexpr bool paired=T==Type::IQ2_S;
 static constexpr unsigned V=paired?8:16,P=32/V,SG=WG/32,RowsPerGroup=(paired?SG/2:SG)*V;
 static_assert(WG==64||WG==128);static_assert((paired&&K==2560)||(!paired&&K==640));
 unsigned rows=paired?640:2560,count=10,experts=512;
 p39::Bound bind(std::span<void*const>p)const{
  p49dvirtual::Kernel<T,K,paired?2:3> base;base.rows=rows;base.count=count;base.experts=experts;auto b=base.bind(p);if constexpr(HalfCache)b.rb=p90::expert_stride(K);return b;
 }
 static unsigned logical_row(unsigned group,unsigned sub,unsigned lane){return (group*(paired?SG/2:SG)+(paired?sub/2:sub))*V+lane/P;}
 static std::array<float,V> chains(const uint8_t*w,const uint16_t*x,unsigned lane){
  static_assert(T==Type::IQ2_S);return grid_chains<K,V,HalfCache>(w,x,lane);
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
}
