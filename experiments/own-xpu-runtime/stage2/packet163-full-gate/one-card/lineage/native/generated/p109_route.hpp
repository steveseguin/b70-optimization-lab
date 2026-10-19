#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet103-record-bundle/p78_route.hpp"
#ifndef OWN_RT_HOST_ONLY
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58aj-onecard-resident/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/build/checked/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/prepared_submission.hpp"
#endif
#line 1
#pragma once
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58aj-onecard-resident/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/build/checked/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/p49d_route.hpp"
// One workgroup owns every global dependency. Rank the rounded probabilities,
// never raw logits: exp/division can introduce ties. No floating-point reorder.
namespace p109route {
inline bool better(float a,unsigned ai,float b,unsigned bi){return a>b||(a==b&&ai<bi);}
inline void host(route42::Args a) {
  for(unsigned c=0;c<32;++c)route42::phase<0,512,10>(a,c);
  if(!*a.active||a.failed())return;
  p49c::route_exp_host(a);
  float den=route42::subtree<256>(32,0,[&](int j){return a.scratch[32+j];});
  float probabilities[512];unsigned indices[512];
  for(unsigned j=0;j<512;++j){probabilities[j]=a.scratch[64+j]/den;indices[j]=j;}
  for(unsigned size=2;size<=512;size*=2)for(unsigned distance=size/2;distance;distance/=2){
    float old[512];unsigned old_indices[512];
    for(unsigned j=0;j<512;++j){old[j]=probabilities[j];old_indices[j]=indices[j];}
    for(unsigned j=0;j<512;++j){unsigned k=j^distance;
      bool want_best=((j&size)==0)==((j&distance)==0);
      bool take=want_best?better(old[k],old_indices[k],old[j],old_indices[j]):better(old[j],old_indices[j],old[k],old_indices[k]);
      if(take){probabilities[j]=old[k];indices[j]=old_indices[k];}
    }
  }
  for(unsigned rank=0;rank<10;++rank)route42::output<512,10>(a,indices[rank],rank);
  route42::phase<4,512,10>(a,0);
}

inline void activation(route42::Args a,void* const* p,unsigned i,const uint32_t* pos,unsigned capacity){
 if(!*a.active||a.failed())return;
 const int32_t position=std::bit_cast<int32_t>(*pos);
 if(position<0||unsigned(position)>=capacity){if(!i)a.fail();return;}
 auto gate=static_cast<const uint16_t*>(p[0]);auto up=static_cast<const uint16_t*>(p[1]);
 auto out=static_cast<uint16_t*>(p[2]);
 out[i]=iq3::bf16_bits(ng::silu(iq3::bits_float(uint32_t(gate[i])<<16))*iq3::bits_float(uint32_t(up[i])<<16));
}
struct Kernel final:p49c::Base {
  integrated::Spec spec;
#ifdef OWN_RT_HOST_ONLY
  void run(std::span<void*const> p)const override{p109route::host(route42::bind(spec,p.first(p.size()-3)));
    auto a=route42::bind(spec,p.first(p.size()-3));
    auto pos=static_cast<const uint32_t*>(p[spec.ni+spec.no+spec.nw+2]);
    for(unsigned i=0;i<640;++i)activation(a,p.data()+p.size()-3,i,pos,spec.g.context);}
#else
  sycl::event submit(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&deps)const override{
    auto a=route42::bind(spec,p.first(p.size()-3));
    auto pos=static_cast<const uint32_t*>(p[spec.ni+spec.no+spec.nw+2]);unsigned capacity=spec.g.context;
    std::array<void*,3> activation_args{p[p.size()-3],p[p.size()-2],p[p.size()-1]};
    return ownrt::prepared_submit(q,[=,p35_range0=sycl::nd_range<1>(512,512)](sycl::handler& h){
      
      sycl::local_accessor<float,1> cache(513,h);
      sycl::local_accessor<unsigned,1> ids(512,h);
      sycl::local_accessor<uint32_t,1> control(1,h);
      h.parallel_for(p35_range0,packet26::checked([=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
        unsigned tid=it.get_local_linear_id(),lane=tid%32;auto sg=it.get_sub_group();
        if(!tid)control[0]=uint32_t(*a.active&&!a.failed());
        it.barrier(sycl::access::fence_space::local_space);if(!control[0])return;
        if(tid<32)route42::phase<0,512,10>(a,tid);
        it.barrier(sycl::access::fence_space::global_and_local);
        if(!tid)control[0]=!a.failed();
        it.barrier(sycl::access::fence_space::local_space);if(!control[0])return;
        if(!tid){float m=-INFINITY;for(unsigned c=0;c<32;++c)m=std::max(m,a.scratch[c]);cache[512]=m;}
        it.barrier(sycl::access::fence_space::local_space);
        float maximum=cache[512];
        for(unsigned offset=0;offset<512;offset+=512){
          unsigned j=offset+tid;float v=detmath::exp(a.in().get(j)-maximum);a.scratch[64+j]=v;
          for(unsigned width=1;width<16;width*=2){float r=sycl::select_from_group(sg,v,(lane+width)%32);if(lane%(2*width)==0)v=v+r;}
          if(lane%16==0)a.scratch[32+j/16]=v;
        }
        it.barrier(sycl::access::fence_space::global_and_local);
        if(!tid)cache[512]=route42::subtree<256>(32,0,[&](int j){return a.scratch[32+j];});
        it.barrier(sycl::access::fence_space::local_space);
        float den=cache[512];
        float value=a.scratch[64+tid]/den;unsigned index=tid;
        // 45 compare-exchange rounds, 35 within SG32. Only ten exchange
        // rounds cross subgroup boundaries; those use bounded WG barriers.
        for(unsigned size=2;size<=512;size*=2)for(unsigned distance=size/2;distance;distance/=2){
          float other;unsigned other_index;
          if(distance<32){other=sycl::select_from_group(sg,value,lane^distance);other_index=sycl::select_from_group(sg,index,lane^distance);}
          else{
            cache[tid]=value;ids[tid]=index;it.barrier(sycl::access::fence_space::local_space);
            other=cache[tid^distance];other_index=ids[tid^distance];
            it.barrier(sycl::access::fence_space::local_space);
          }
          bool want_best=((tid&size)==0)==((tid&distance)==0);
          bool take=want_best?better(other,other_index,value,index):better(value,index,other,other_index);
          if(take){value=other;index=other_index;}
        }
        if(tid<10)route42::output<512,10>(a,index,tid);
        it.barrier(sycl::access::fence_space::global_and_local);
        if(!tid)route42::phase<4,512,10>(a,0);
        it.barrier(sycl::access::fence_space::global_and_local);
        for(unsigned i=tid;i<640;i+=512)activation(a,activation_args.data(),i,pos,capacity);
      }));
    });
  }
#endif
};
}
