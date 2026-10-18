#pragma once
#include "p49d_expert.hpp"
#include "p49c_kernel.hpp"
#include "p104_layout.hpp"
#include "p49d_small.hpp"
namespace p104small {
using namespace p49dvirtual;

template<Type T,unsigned K,bool Tiled>inline const uint8_t* address(const uint8_t*w,size_t row,size_t rb,size_t byte){
 if constexpr(!Tiled)return w+row*rb+byte;
 else if constexpr(T==Type::F32)return p104::address(w,row,rb,0,32,byte);
 else {static_assert(T==Type::Q6_K);return byte<K?p104::address(w,row,rb,0,8,byte):p104::address(w,row,rb,K,4,byte-K);}
}

// Original dense chains, including each split's independent K origin. V chains
// share a physical lane; no reassociation or extra partial sum is introduced.
template<Type T,unsigned K,unsigned V,bool Tiled>
inline std::array<float,V> dense_chains(const uint8_t*w,const uint16_t*x,unsigned begin,unsigned end,unsigned physical,size_t source,size_t rb){
 std::array<float,V> sums{};
 for(unsigned step=begin;step<end;step+=256){
  #pragma unroll
  for(unsigned c=0;c<V;++c){unsigned k=step+8*(physical*V+c);if(k>=end)continue;
   float scale=0;uint32_t lo=0,hi=0;
   if constexpr(T!=Type::F32){constexpr unsigned G=T==Type::Q6_K?16:32;scale=iq3::bits_float(p49bgemv::load32(address<T,K,Tiled>(w,source,rb,K+4*(k/G))));lo=p49bgemv::load32(address<T,K,Tiled>(w,source,rb,k));hi=p49bgemv::load32(address<T,K,Tiled>(w,source,rb,k+4));}
#if defined(__SYCL_DEVICE_ONLY__)
   sycl::vec<uint16_t,8> inputs;inputs.load(0,sycl::address_space_cast<sycl::access::address_space::global_space,sycl::access::decorated::no>(x+k));
#endif
   #pragma unroll
   for(unsigned j=0;j<8;++j){float value;
    if constexpr(T==Type::F32)value=iq3::bits_float(p49bgemv::load32(address<T,K,Tiled>(w,source,rb,4*(k+j))));
    else value=scale*float(iq3::signed8(uint8_t(((j<4?lo:hi)>>(8*(j%4)))&255)));
#if defined(__SYCL_DEVICE_ONLY__)
    uint16_t bits=inputs[j];
#else
    uint16_t bits=x[k+j];
#endif
    float product=value*iq3::bits_float(uint32_t(bits)<<16);sums[c]=sums[c]+product;
   }
  }
 }
 return sums;
}
template<Type T,unsigned K,unsigned Split,unsigned V,bool Tiled>inline uint16_t dense_host(const uint8_t*w,const uint16_t*x,size_t source,size_t rb){
 float partial[Split]{};
 for(unsigned part=0;part<Split;++part){auto bounds=iq3::kopt2::bounds(K,part,Split);float lanes[32/V];
  for(unsigned p=0;p<32/V;++p)lanes[p]=local_tree<V>(dense_chains<T,K,V,Tiled>(w,x,bounds.first,bounds.second,p,source,rb));
  for(unsigned width=1;width<32/V;width*=2)for(unsigned p=0;p<32/V;p+=2*width)lanes[p]=lanes[p]+lanes[p+width];partial[part]=lanes[0];}
 return iq3::bf16_bits(Split==1?partial[0]:(partial[0]+partial[1])+(partial[2]+partial[3]));
}
#ifndef OWN_RT_HOST_ONLY
// Split4: four SGs cooperate on V rows, with the original four partials per
// row. Split1: four SGs each own V rows. Every work-item reaches the barrier.
template<Type T,unsigned K,unsigned Split,unsigned V,p39::Kind E,bool Tiled>
inline void dense_device(p39::Bound b,unsigned group,sycl::nd_item<1>it,float* scratch){
 constexpr unsigned P=32/V;auto sg=it.get_sub_group();unsigned lane=sg.get_local_linear_id(),sub=it.get_local_linear_id()/32;
 unsigned within=lane/P,physical=lane%P,part=Split==4?sub:0;
 unsigned row=Split==4?group*V+within:(group*4+sub)*V+within;
 float value=0;auto bounds=iq3::kopt2::bounds(K,part,Split);
 if(row<b.rows)value=local_tree<V>(dense_chains<T,K,V,Tiled>(b.w,b.x,bounds.first,bounds.second,physical,row,b.rb));
 for(unsigned width=1;width<P;width*=2){float rhs=sycl::select_from_group(sg,value,(lane+width)%32);if(physical%(2*width)==0)value=value+rhs;}
 if constexpr(Split==4){if(!physical)scratch[within*4+part]=value;it.barrier(sycl::access::fence_space::local_space);if(!part&&!physical){auto s=scratch+within*4;value=(s[0]+s[1])+(s[2]+s[3]);}}
 if(row<b.rows&&!physical&&!part){auto y=iq3::bf16_bits(value);b.y[row]=y;p49c::dense_tail_device<E>(b,row,y);}
}
#endif

// One tuple launch, preserving independent router, shared gate/up and scalar
// shared-router outputs. F32 and expanded Q6 both retain Split4 arithmetic.
template<unsigned V,bool Q6,bool Router>struct SmallKernel final:p49b::Base {
 std::array<p39::Bound,4> shapes;
 static constexpr unsigned groups(unsigned rows){return (rows+V-1)/V;}
 std::array<p39::Bound,4> bind(std::span<void*const>p)const{auto b=shapes;for(unsigned j=0;j<4;++j){b[j].w=static_cast<const uint8_t*>(p[j*3]);b[j].x=static_cast<const uint16_t*>(p[j*3+1]);b[j].y=static_cast<uint16_t*>(p[j*3+2]);}return b;}
#ifdef OWN_RT_HOST_ONLY
 void run(std::span<void*const>p)const override{auto bs=bind(p);for(unsigned j=0;j<4;++j){auto b=bs[j];for(unsigned row=0;row<b.rows;++row){
 if(j==0)b.y[row]=dense_host<Type::F32,2560,4,V,Router>(b.w,b.x,row,b.rb);
 else if(j==3)b.y[row]=dense_host<Type::F32,2560,4,V,false>(b.w,b.x,row,b.rb);
 else b.y[row]=dense_host<Type::Q6_K,2560,4,V,Q6>(b.w,b.x,row,b.rb);
 }}}

#else
 sycl::event submit(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&deps)const override{
  auto b=bind(p);unsigned g0=groups(b[0].rows),g1=groups(b[1].rows),g2=groups(b[2].rows),total=g0+g1+g2+groups(b[3].rows);
  return q.submit([&](sycl::handler&h){h.depends_on(deps);sycl::local_accessor<float,1>scratch(4*V,h);
   h.parallel_for(sycl::nd_range<1>(size_t(total)*128,128),[=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
    unsigned group=it.get_group_linear_id();auto s=scratch.template get_multi_ptr<sycl::access::decorated::no>().get();
    if(group<g0)dense_device<Type::F32,2560,4,V,p39::Kind::expert_checks,Router>(b[0],group,it,s);
    else if(group<g0+g1)dense_device<Type::Q6_K,2560,4,V,p39::Kind::expert_checks,Q6>(b[1],group-g0,it,s);
    else if(group<g0+g1+g2)dense_device<Type::Q6_K,2560,4,V,p39::Kind::expert_checks,Q6>(b[2],group-g0-g1,it,s);
    else dense_device<Type::F32,2560,4,V,p39::Kind::expert_checks,false>(b[3],group-g0-g1-g2,it,s);
   });});
 }
#endif
};
}
