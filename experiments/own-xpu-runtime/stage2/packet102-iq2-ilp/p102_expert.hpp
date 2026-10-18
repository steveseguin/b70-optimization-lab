#pragma once
// Packet102: batch dependent grid reads, never reassociate FP32 sums.
// All weights, half-cache bytes, sign handling and trees come from packet97.
#include "p95_expert.hpp"
#include "p90_expert.hpp"
namespace p102 {
using iq3::Type;
template<unsigned Batch,bool Shared>inline std::array<std::array<float,Shared?4:8>,Shared?2:1> chains(const uint8_t*w,const uint8_t*peer,const uint16_t*x,unsigned physical){
 static_assert(Batch==1||Batch==2||Batch==4);constexpr unsigned Streams=Shared?2:1,V=Shared?4:8;
 constexpr auto l=p49bgemv::layout(Type::IQ2_S,2560);
 std::array<std::array<float,V>,Streams> sums{};
 for(unsigned step=0;step<10;++step){
  uint32_t codes[Streams][V/2];uint16_t highs[Streams],scales[Streams];float decoded[Streams];
  #pragma unroll
  for(unsigned s=0;s<Streams;++s){const auto*src=s?peer:w;
#if defined(__SYCL_DEVICE_ONLY__)
   sycl::vec<uint32_t,V/2> words;words.load(0,sycl::address_space_cast<sycl::access::address_space::global_space,sycl::access::decorated::no>(reinterpret_cast<const uint32_t*>(src+step*64+physical*(2*V))));
   #pragma unroll
   for(unsigned i=0;i<V/2;++i)codes[s][i]=words[i];
#else
   for(unsigned i=0;i<V/2;++i)codes[s][i]=p49bgemv::load32(src+step*64+physical*(2*V)+4*i);
#endif
   if constexpr(Shared)highs[s]=src[l.high+step*8+physical];else highs[s]=p49bgemv::load16(src+l.high+step*8+physical*2);
   if constexpr(Shared)scales[s]=src[l.scales+step*8+physical];else scales[s]=p49bgemv::load16(src+l.scales+step*8+physical*2);
   decoded[s]=iq3::bits_float(p49bgemv::load32(src+l.halves+4*step));
  }
  #pragma unroll
  for(unsigned base=0;base<V;base+=Batch){
   p65::RawTile tiles[Streams][Batch];p95exp::GridWord grids[Streams][Batch];
   // Issue every independent grid read in this batch before any decode/product.
   #pragma unroll
   for(unsigned s=0;s<Streams;++s){
    #pragma unroll
    for(unsigned i=0;i<Batch;++i){unsigned chain=base+i;auto&t=tiles[s][i];
     t.a=(codes[s][chain/2]>>(16*(chain%2)))&65535;t.high=(highs[s]>>(8*(chain/4)))&255;t.scale=(scales[s]>>(8*(chain/4)))&255;
     unsigned index=(t.a&255)|(((t.high>>(2*(chain%4)))&3)<<8);
     grids[s][i]={p42expert::iq2_words[2*index],p42expert::iq2_words[2*index+1]};
    }
   }
   #pragma unroll
   for(unsigned i=0;i<Batch;++i){unsigned chain=base+i,k=step*256+physical*(8*V)+chain*8;
#if defined(__SYCL_DEVICE_ONLY__)
    sycl::vec<uint16_t,8> inputs;inputs.load(0,sycl::address_space_cast<sycl::access::address_space::global_space,sycl::access::decorated::no>(x+k));
#else
    const auto*inputs=x+k;
#endif
    #pragma unroll
    for(unsigned s=0;s<Streams;++s){float values[8];p95exp::decode_grid(tiles[s][i],k,grids[s][i],values,decoded[s]);
     #pragma unroll
     for(unsigned j=0;j<8;++j){float product=values[j]*iq3::bits_float(uint32_t(inputs[j])<<16);sums[s][chain]=sums[s][chain]+product;}
    }
   }
  }
 }
 return sums;
}
template<unsigned Batch,bool Shared>struct Kernel final:p49b::Base {
 static constexpr unsigned WG=64,V=Shared?4:8,P=32/V,SG=2,RowsPerGroup=Shared?2*V:V;
 unsigned rows=640,count=10,experts=512;
 p39::Bound bind(std::span<void*const>p)const{p90exp::Kernel<Type::IQ2_S,2560,64,false,true> base;base.rows=rows;base.count=count;base.experts=experts;return base.bind(p);}
 static unsigned logical_row(unsigned group,unsigned sub,unsigned lane){return (group*(Shared?2:1)+(Shared?sub:0))*V+lane/P;}
#ifdef OWN_RT_HOST_ONLY
 void run(std::span<void*const>p)const override{
  auto b=bind(p);unsigned total=rows*count,groups=(total+RowsPerGroup-1)/RowsPerGroup;
  for(unsigned group=0;group<groups;++group)for(unsigned sub=0;sub<SG;++sub)for(unsigned rr=0;rr<V;++rr){
   unsigned logical=logical_row(group,sub,rr*P);if(logical>=total)continue;unsigned row=logical%rows,slot=logical/rows,stream=Shared?0:sub;
   auto route=b.routes[slot];bool ok=iq3::valid_route(route,experts,rows,rows),valid=ok&&row<route.row_count;
   float values[Shared?2:1][P]{};if(valid){size_t source=size_t(route.expert_id)*rows+route.row_begin+row;
    for(unsigned lane=0;lane<P;++lane){auto c=chains<Batch,Shared>((stream?b.peer:b.w)+source*b.rb,b.peer+source*b.rb,b.x,lane);
     for(unsigned s=0;s<(Shared?2:1);++s)values[s][lane]=p49dvirtual::local_tree<V>(c[s]);}
   }
   for(unsigned s=0;s<(Shared?2:1);++s){for(unsigned width=1;width<P;width*=2)for(unsigned lane=0;lane<P;lane+=2*width)values[s][lane]=values[s][lane]+values[s][lane+width];
    ((stream||s)?b.py:b.y)[logical]=iq3::bf16_bits(valid?values[s][0]:iq3::bits_float(0x7fc00000));
    if(!row){((stream||s)?b.peer_status:b.status)[slot]=!ok;if(!ok&&*b.active&&!*b.error)*b.error=1;}
   }
  }
 }
#else
 sycl::event submit(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&deps)const override{
  auto b=bind(p);unsigned total=rows*count,groups=(total+RowsPerGroup-1)/RowsPerGroup;
  return q.submit([&](sycl::handler&h){h.depends_on(deps);
   h.parallel_for(sycl::nd_range<1>(size_t(groups)*WG,WG),[=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
    auto sg=it.get_sub_group();unsigned lane=sg.get_local_linear_id(),sub=it.get_local_linear_id()/32,physical=lane%P,stream=Shared?0:sub;
    unsigned logical=logical_row(it.get_group_linear_id(),sub,lane),row=logical%b.rows,slot=logical/b.rows;bool in_range=logical<total;
    iq3::Route route{};if(in_range)route=b.routes[slot];bool ok=in_range&&iq3::valid_route(route,b.experts,b.rows,b.rows),valid=ok&&row<route.row_count;
    float values[Shared?2:1]{};if(valid){size_t source=size_t(route.expert_id)*b.rows+route.row_begin+row;auto c=chains<Batch,Shared>((stream?b.peer:b.w)+source*b.rb,b.peer+source*b.rb,b.x,physical);
     #pragma unroll
     for(unsigned s=0;s<(Shared?2:1);++s)values[s]=p49dvirtual::local_tree<V>(c[s]);
    }
    #pragma unroll
    for(unsigned s=0;s<(Shared?2:1);++s){
     for(unsigned width=1;width<P;width*=2){float rhs=sycl::select_from_group(sg,values[s],(lane+width)%32);if(physical%(2*width)==0)values[s]=values[s]+rhs;}
    }
    // One common epilogue: do not keep duplicate divergent status/atomic
    // paths alive for the two independent arithmetic streams.
    if(in_range&&!physical){
     (stream?b.py:b.y)[logical]=iq3::bf16_bits(valid?values[0]:iq3::bits_float(0x7fc00000));
     if constexpr(Shared)b.py[logical]=iq3::bf16_bits(valid?values[1]:iq3::bits_float(0x7fc00000));
     if(!row){
      (stream?b.peer_status:b.status)[slot]=!ok;
      if constexpr(Shared)b.peer_status[slot]=!ok;
      if(!ok&&*b.active){uint32_t expected=0;sycl::atomic_ref<uint32_t,sycl::memory_order::relaxed,sycl::memory_scope::device,sycl::access::address_space::global_space>(*b.error).compare_exchange_strong(expected,1);}
     }
    }

   });
  });
 }
#endif
};
}
