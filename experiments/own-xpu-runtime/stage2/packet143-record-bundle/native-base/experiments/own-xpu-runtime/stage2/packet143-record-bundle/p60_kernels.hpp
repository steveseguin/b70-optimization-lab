#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet143-record-bundle/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet136-record-bundle/p60_kernels.hpp"
#ifndef OWN_RT_HOST_ONLY
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet143-record-bundle/build/checked/experiments/own-xpu-runtime/stage2/packet143-record-bundle/prepared_submission.hpp"
#endif
#line 1
#pragma once
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet143-record-bundle/build/checked/experiments/own-xpu-runtime/stage2/packet143-record-bundle/p60_math.hpp"
#ifndef OWN_RT_HOST_ONLY
namespace p60 {
inline uint32_t failed(Bound b){return sycl::atomic_ref<uint32_t,sycl::memory_order::relaxed,sycl::memory_scope::device,sycl::access::address_space::global_space>(*b.error).load();}
inline void fail(Bound b){sycl::atomic_ref<uint32_t,sycl::memory_order::relaxed,sycl::memory_scope::device,sycl::access::address_space::global_space>(*b.error).store(1);}
inline float tree(sycl::sub_group sg,float value){unsigned lane=sg.get_local_linear_id();for(unsigned s=1;s<32;s*=2){float rhs=sycl::select_from_group(sg,value,(lane+s)%32);if(lane%(2*s)==0)value=value+rhs;}return value;}
// Ten output tiles per stream: forty workgroups, not packet46's four.
// Recompute only the small RMS reduction per output tile. All output elements
// have a unique writer; tile zero retains the original 80 global partials.
inline sycl::event norm_kernel(sycl::queue&q,Bound b,const std::vector<sycl::event>&deps){
 return ownrt::prepared_submit(q,[=,p35_range0=sycl::nd_range<1>(40*256,256)](sycl::handler& h){sycl::local_accessor<float,1> partial(132,h);sycl::local_accessor<uint32_t,1> control(1,h);
  h.parallel_for(p35_range0,packet26::checked(packet26::checked([=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
   unsigned local=it.get_local_linear_id(),stream=it.get_group_linear_id()/10,tile=it.get_group_linear_id()%10;auto sg=it.get_sub_group();unsigned lane=local%32,group=local/32;
   if(!local)control[0]=uint32_t(*b.active&&!failed(b));it.barrier(sycl::access::fence_space::local_space);if(!control[0])return;
   if(*b.position>=b.capacity){if(!local&&!stream&&!tile)fail(b);return;}
   // Each subgroup computes a complete aligned original 32-leaf subtree.
   for(unsigned c=group;c<80;c+=8){float x=get(b.x,stream*H+c*32+lane);float sum=tree(sg,x*x);if(!lane){partial[c]=sum;if(!tile)b.scratch[stream*80+c]=sum;}}
   if(local>=80&&local<128)partial[local]=0.f;
   it.barrier(sycl::access::fence_space::local_space);
   float upper=local<128?partial[local]:0.f;upper=tree(sg,upper);
   if(!lane&&group<4)partial[128+group]=upper;
   it.barrier(sycl::access::fence_space::local_space);
   float total=(partial[128]+partial[129])+(partial[130]+partial[131]);
   float inv=detmath::rsqrt(total/float(H)+1e-6f);
   norm_output(b,stream,tile*256+local,inv);
  })));
 });
}
inline sycl::event low_inject_kernel(sycl::queue&q,Bound b,const std::vector<sycl::event>&deps){
 const size_t rb=iq3::expanded::row_bytes(Type::Q8_0,K);
 return ownrt::prepared_submit(q,[=,p35_range0=sycl::nd_range<1>((L+S)*128,128)](sycl::handler& h){sycl::local_accessor<float,1> partial(4,h);
  h.parallel_for(p35_range0,packet26::checked(packet26::checked([=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
   unsigned row=it.get_group_linear_id(),part=it.get_local_linear_id()/32,lane=it.get_local_linear_id()%32;auto bounds=iq3::kopt2::bounds(K,part,4);float value;
   if(row<L)value=p49c::dense_lane<Type::Q8_0,K>(b.low_w+row*rb,b.norm,bounds.first,bounds.second,lane);
   else value=p49c::dense_lane<Type::F32,K>(b.inject_w+(row-L)*K*4,b.norm,bounds.first,bounds.second,lane);
   value=tree(it.get_sub_group(),value);if(!lane){partial[part]=value;if(row>=L)b.workspace[(row-L)*8+part]=value;}
   it.barrier(sycl::access::fence_space::local_space);
   if(!it.get_local_linear_id()){uint16_t y=iq3::bf16_bits((partial[0]+partial[1])+(partial[2]+partial[3]));
    if(row<L){b.low[row]=y;if(*b.active&&!failed(b)&&*b.position<b.capacity)b.act[row]=p39::hc_activation(y);}else b.inject[row-L]=y;
   }
  })));
 });
}
inline sycl::event gate_mix_kernel(sycl::queue&q,Bound b,const std::vector<sycl::event>&deps){
 const size_t rb=iq3::expanded::row_bytes(Type::Q8_0,L);
 return ownrt::prepared_submit(q,[=,p35_range0=sycl::nd_range<1>((H/2)*256,256)](sycl::handler& h){sycl::local_accessor<uint16_t,1> gates(8,h);
  h.parallel_for(p35_range0,packet26::checked(packet26::checked([=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
   unsigned local=it.get_local_linear_id(),sub=local/32,lane=local%32,k=it.get_group_linear_id()*2+sub/4,stream=sub%4,row=stream*H+k;
   float value=p49c::dense_lane<Type::Q8_0,L>(b.gate_w+row*rb,b.act,0,L,lane);value=tree(it.get_sub_group(),value);
   if(!lane){uint16_t y=iq3::bf16_bits(value);b.gate[row]=y;gates[sub]=y;}
   it.barrier(sycl::access::fence_space::local_space);
   if(local<2&&*b.active&&!failed(b)&&*b.position<b.capacity){unsigned out=it.get_group_linear_id()*2+local;float sum=0.f;for(unsigned s=0;s<S;++s)sum=sum+ng::sigmoid(p39::widen(gates[local*4+s]))*get(b.norm,s*H+out);b.mix[out]=iq3::bf16_bits(sum/4.f);}
  })));
 });
}
} // namespace p60
#endif
