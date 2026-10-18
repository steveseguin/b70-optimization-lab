#pragma once
#include "../packet97-record-bundle/p78_route.hpp"
// One workgroup owns every global dependency. Rank the rounded probabilities,
// never raw logits: exp/division can introduce ties. No floating-point reorder.
namespace p112route {
inline bool better(float a,unsigned ai,float b,unsigned bi){return a>b||(a==b&&ai<bi);}
inline void host(route42::Args a) {
  for(unsigned c=0;c<32;++c)route42::phase<0,512,10>(a,c);
  if(!*a.active||a.failed())return;
  p49c::route_exp_host(a);
  float den=route42::subtree<256>(32,0,[&](int j){return a.scratch[32+j];});
  float probabilities[512];unsigned indices[512];
  for(unsigned j=0;j<512;++j){probabilities[j]=a.scratch[64+j]/den;indices[j]=j;}
  // Host mirror of the device subgroup top-16 merge, not a library sort.
  auto exchange=[&](unsigned base,unsigned size,unsigned distance,bool merge){
    float old[32];unsigned oi[32];
    for(unsigned lane=0;lane<32;++lane){old[lane]=probabilities[base+lane];oi[lane]=indices[base+lane];}
    for(unsigned lane=0;lane<32;++lane){unsigned k=lane^distance;
      bool want_best=merge?((lane&distance)==0):(((lane&size)==0)==((lane&distance)==0));
      bool take=want_best?better(old[k],oi[k],old[lane],oi[lane]):better(old[lane],oi[lane],old[k],oi[k]);
      if(take){probabilities[base+lane]=old[k];indices[base+lane]=oi[k];}
    }
  };
  for(unsigned sg=0;sg<16;++sg)for(unsigned size=2;size<=32;size*=2)
    for(unsigned distance=size/2;distance;distance/=2)exchange(sg*32,size,distance,false);
  for(unsigned stride=1;stride<16;stride*=2)for(unsigned sg=0;sg<16;sg+=2*stride){
    for(unsigned lane=16;lane<32;++lane){probabilities[sg*32+lane]=probabilities[(sg+stride)*32+31-lane];indices[sg*32+lane]=indices[(sg+stride)*32+31-lane];}
    for(unsigned distance=16;distance;distance/=2)exchange(sg*32,32,distance,true);
  }
  for(unsigned rank=0;rank<10;++rank)route42::output<512,10>(a,indices[rank],rank);
  route42::phase<4,512,10>(a,0);
}
struct Kernel final:p49c::Base {
  integrated::Spec spec;
#ifdef OWN_RT_HOST_ONLY
  void run(std::span<void*const> p)const override{p112route::host(route42::bind(spec,p));}
#else
  sycl::event submit(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&deps)const override{
    auto a=route42::bind(spec,p);
    return q.submit([&](sycl::handler&h){
      h.depends_on(deps);
      sycl::local_accessor<float,1> cache(513,h);
      sycl::local_accessor<unsigned,1> ids(512,h);
      sycl::local_accessor<uint32_t,1> control(1,h);
      h.parallel_for(sycl::nd_range<1>(512,512),[=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
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
        // Sort only within each SG32, retaining its top sixteen.
        for(unsigned size=2;size<=32;size*=2)for(unsigned distance=size/2;distance;distance/=2){
          float other=sycl::select_from_group(sg,value,lane^distance);
          unsigned oi=sycl::select_from_group(sg,index,lane^distance);
          bool best=((lane&size)==0)==((lane&distance)==0);
          bool take=best?better(other,oi,value,index):better(value,index,other,oi);
          if(take){value=other;index=oi;}
        }
        unsigned group=tid/32;
        // A discarded local rank >=16 has sixteen better keys, so cannot be
        // in the global top10. Four exact merges retain top16 at each level.
        for(unsigned stride=1;stride<16;stride*=2){
          if(group%stride==0 && lane<16){cache[group*16+lane]=value;ids[group*16+lane]=index;}
          it.barrier(sycl::access::fence_space::local_space);
          if(group%(2*stride)==0){
            unsigned src=lane<16?group*16+lane:(group+stride)*16+31-lane;
            value=cache[src];index=ids[src];
          }
          // No writer reuses local storage until all readers have finished.
          if(stride<8)it.barrier(sycl::access::fence_space::local_space);
          if(group%(2*stride)==0)for(unsigned distance=16;distance;distance/=2){
            float other=sycl::select_from_group(sg,value,lane^distance);
            unsigned oi=sycl::select_from_group(sg,index,lane^distance);
            bool take=(lane&distance)==0?better(other,oi,value,index):better(value,index,other,oi);
            if(take){value=other;index=oi;}
          }
        }
        if(tid<10)route42::output<512,10>(a,index,tid);
        it.barrier(sycl::access::fence_space::global_and_local);
        if(!tid)route42::phase<4,512,10>(a,0);
      });
    });
  }
#endif
};
inline integrated::Launch submit(ownrt::Device&d,const integrated::Spec&s,std::span<const ownrt::Allocation>a,std::span<const ownrt::Event>deps={}){
  p49droute::validate(d,s,a);Kernel k;k.spec=s;auto e=d.compute(k,a,deps);return {e,e,1};
}
}
