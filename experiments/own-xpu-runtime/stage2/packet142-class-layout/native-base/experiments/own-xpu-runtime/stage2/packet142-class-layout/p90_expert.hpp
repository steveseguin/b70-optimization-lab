#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet136-record-bundle/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet136-record-bundle/p90_expert.hpp"
#ifndef OWN_RT_HOST_ONLY
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet142-class-layout/build/checked/experiments/own-xpu-runtime/stage2/packet142-class-layout/prepared_submission.hpp"
#endif
#line 1
#pragma once
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet142-class-layout/build/checked/experiments/own-xpu-runtime/stage2/packet142-class-layout/p65_expert.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet142-class-layout/build/checked/experiments/own-xpu-runtime/stage2/packet142-class-layout/p90_layout.hpp"
namespace p90exp {
using iq3::Type;using p65::RawTile;using p39::Kind;using p39::Bound;
// Same p39 range/alias validation with the explicitly selected physical stride.
template<Type T,unsigned K,Kind E,unsigned Split=1> inline void validate(Bound b){
 constexpr bool routed=E==Kind::expert_act||E==Kind::expert_checks||E==Kind::down_status;
 if(!b.rows||b.rows>248320||!b.count||b.count>10||!b.experts||b.experts>512||(!routed&&(b.count!=1||b.experts!=1)))throw std::invalid_argument("p39 shape");
 if constexpr(E==Kind::expert_act||E==Kind::expert_checks)static_assert((T==Type::IQ2_S||T==Type::IQ3_S)&&K==2560&&Split==1);
 if constexpr(E==Kind::down_status)static_assert(T==Type::IQ4_NL&&K==640&&Split==1);
 // Expanded rows retain their original block metadata after codes/FP32 scales.
 // Split count changes arithmetic, never the row layout; x/y remain BF16.
 static_assert(T==Type::IQ2_S&&K==2560&&E==Kind::expert_checks&&Split==1);
 const size_t expected=p90::expert_stride(K);
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

template<Type T>inline void decode_tile(const RawTile&t,unsigned k,float(&v)[8],float d){

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
   float decoded=iq3::bits_float(p49bgemv::load32(w+l.halves+4*step));
   #pragma unroll
   for(unsigned chain=0;chain<V;++chain){unsigned k=first+chain*8;RawTile t;t.a=(codes[chain/2]>>(16*(chain%2)))&65535;t.high=(high>>(8*(chain/4)))&255;t.scale=(scales>>(8*(chain/4)))&255;
    float values[8];decode_tile<T>(t,k,values,decoded);
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
  }else{static_assert(T==Type::IQ2_S,"p90 halfcache is IQ2 only");}
 }
 return sums;
}
template<Type T,unsigned K,unsigned WG,bool Prefetch,bool Wide=false,unsigned Followup=0>struct Kernel final:p49b::Base {
 static_assert(T==Type::IQ2_S);
 static constexpr bool paired=T==Type::IQ2_S;
 static constexpr unsigned V=paired?8:16,P=32/V,SG=WG/32,RowsPerGroup=(paired?SG/2:SG)*V;
 static_assert(WG==64||WG==128);static_assert((paired&&K==2560)||(!paired&&K==640));
 unsigned rows=paired?640:2560,count=10,experts=512;
 p39::Bound bind(std::span<void*const>p)const{
  p49dvirtual::Kernel<T,K,paired?2:3> base;base.rows=rows;base.count=count;base.experts=experts;auto b=base.bind(p);b.rb=p90::expert_stride(K);return b;
 }
 static unsigned logical_row(unsigned group,unsigned sub,unsigned lane){return (group*(paired?SG/2:SG)+(paired?sub/2:sub))*V+lane/P;}
 static std::array<float,V> chains(const uint8_t*w,const uint16_t*x,unsigned lane){
  return wide_chains<T,K,V>(w,x,lane);
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
