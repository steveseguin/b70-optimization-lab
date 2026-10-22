#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet185-twocard-unsplit-head/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet136-record-bundle/p59_hc.hpp"
#ifndef OWN_RT_HOST_ONLY
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet185-twocard-unsplit-head/build/checked/experiments/own-xpu-runtime/stage2/packet185-twocard-unsplit-head/prepared_submission.hpp"
#endif
#line 1
#pragma once
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet185-twocard-unsplit-head/build/checked/experiments/own-xpu-runtime/stage2/packet185-twocard-unsplit-head/p59_draft.hpp"
namespace p59 {
// HC gate projection and four-stream mixture in one workgroup. Four columns
// per group, with four adjacent logical lanes per physical lane (p53b schedule).
template<unsigned K>struct GateMix final:Base {
 unsigned width;
#ifdef OWN_RT_HOST_ONLY
 void run(std::span<void*const>p)const override {auto w=static_cast<const uint8_t*>(p[0]);auto x=static_cast<const uint16_t*>(p[1]);auto y=static_cast<uint16_t*>(p[2]);auto n=static_cast<const uint16_t*>(p[3]);auto out=static_cast<uint16_t*>(p[4]);
  for(unsigned col=0;col<width;++col){float mix=0;for(unsigned stream=0;stream<4;++stream){unsigned row=stream*width+col;float s[8]{};for(unsigned l=0;l<8;++l)s[l]=Dense<K,false,false,4,1>::chain(w+size_t(row)*K*2,x,l,0);for(unsigned k=1;k<8;k*=2)for(unsigned l=0;l<8;l+=2*k)s[l]+=s[l+k];auto value=iq3::bf16_bits(s[0]);y[row]=value;mix+=ng::sigmoid(widen(value))*widen(n[row]);}out[col]=iq3::bf16_bits(mix/4.f);}
 }
#else
 sycl::event submit(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&deps)const override {auto w=static_cast<const uint8_t*>(p[0]);auto x=static_cast<const uint16_t*>(p[1]);auto y=static_cast<uint16_t*>(p[2]);auto n=static_cast<const uint16_t*>(p[3]);auto out=static_cast<uint16_t*>(p[4]);auto columns=width;
  return ownrt::prepared_submit(q,[=,p35_range0=sycl::nd_range<1>(((columns+3)/4)*128,128)](sycl::handler& h){sycl::local_accessor<uint16_t,1>gate(16,h);h.parallel_for(p35_range0,packet26::checked([=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
   unsigned local=it.get_local_linear_id(),stream=local/32,col=it.get_group_linear_id()*4+(local%32)/8,physical=local%8,row=stream*columns+col;float sum=0;
   if(col<columns)sum=Dense<K,false,false,4,1>::chain(w+size_t(row)*K*2,x,physical,0);
   auto sg=it.get_sub_group();unsigned base=(local%32)/8*8;
   for(unsigned k=1;k<8;k*=2){float rhs=sycl::select_from_group(sg,sum,base+(physical+k)%8);if(physical%(2*k)==0)sum+=rhs;}
   if(!physical){auto value=iq3::bf16_bits(sum);gate[stream*4+(local%32)/8]=value;if(col<columns)y[row]=value;}
   it.barrier(sycl::access::fence_space::local_space);
   if(local<4){unsigned c=it.get_group_linear_id()*4+local;if(c<columns){float mix=0;for(unsigned j=0;j<4;++j)mix+=ng::sigmoid(widen(gate[j*4+local]))*widen(n[j*columns+c]);out[c]=iq3::bf16_bits(mix/4.f);}}
  }));});
 }
#endif
};
inline integrated::Launch gate_mix(ownrt::Device&d,Allocation w,Allocation x,Allocation gate,Allocation normed,Allocation out,unsigned width,unsigned k){
 extent(d,w,size_t(width)*4*k*2);extent(d,x,k*2);extent(d,gate,width*8);extent(d,normed,width*8);extent(d,out,width*2);std::array ids{w,x,gate,normed,out};
 auto issue=[&]<unsigned K>(){GateMix<K>op;op.width=width;auto e=d.compute(op,ids,{});return integrated::Launch{e,e,1};};
 if(k==320)return issue.template operator()<320>();if(k==4)return issue.template operator()<4>();if(k==8)return issue.template operator()<8>();throw std::invalid_argument("p59 HC low width");
}
}
