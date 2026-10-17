#pragma once
// Pair the selected p49droute<4,32> four-pass route, preserving every row's
// ordered maximum, exp subtree, rounded normalization, rank and output bytes.
#include "p49d_route.hpp"
namespace p71b {
using RouteArgs=std::array<route42::Args,2>;
inline void rank_pair_host(RouteArgs a){
 float cached[2][512];bool enabled[2];
 for(unsigned r=0;r<2;++r){enabled[r]=*a[r].active&&!a[r].failed();if(enabled[r]){float den=route42::subtree<256>(32,0,[&](int j){return a[r].scratch[32+j];});for(unsigned j=0;j<512;++j)cached[r][j]=a[r].scratch[64+j]/den;}}
 for(unsigned group=0;group<16;++group)for(unsigned sg=0;sg<8;++sg){unsigned ranks[2][4][32]{};
  for(unsigned lane=0;lane<32;++lane)for(unsigned k=lane;k<512;k+=32)for(unsigned r=0;r<2;++r)if(enabled[r])for(unsigned v=0;v<4;++v){unsigned index=group*32+v*8+sg;ranks[r][v][lane]+=cached[r][k]>cached[r][index]||(cached[r][k]==cached[r][index]&&k<index);}
  for(unsigned width=1;width<32;width*=2)for(unsigned lane=0;lane<32;lane+=2*width)for(unsigned r=0;r<2;++r)for(unsigned v=0;v<4;++v)ranks[r][v][lane]+=ranks[r][v][lane+width];
  for(unsigned r=0;r<2;++r)if(enabled[r])for(unsigned v=0;v<4;++v)route42::output<512,10>(a[r],group*32+v*8+sg,ranks[r][v][0]);
 }
}
template<unsigned Stage>struct Route final:p49c::Base {
 integrated::Spec spec;unsigned stride=0;
 RouteArgs bind(std::span<void*const>p)const{return {route42::bind(spec,p.first(stride)),route42::bind(spec,p.subspan(stride))};}
#ifdef OWN_RT_HOST_ONLY
 void run(std::span<void*const>p)const override {auto a=bind(p);if constexpr(Stage==2)rank_pair_host(a);else for(unsigned r=0;r<2;++r){if constexpr(Stage==1)p49c::route_exp_host(a[r]);else for(unsigned i=0;i<(Stage==4?1:32);++i)route42::phase<Stage,512,10>(a[r],i);}}
#else
 sycl::event submit(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&deps)const override {
  auto a=bind(p);return q.submit([&](sycl::handler&h){h.depends_on(deps);
   if constexpr(Stage==0||Stage==4){h.parallel_for(sycl::range<1>(Stage==4?1:32),[=](sycl::id<1>id){for(unsigned r=0;r<2;++r)route42::phase<Stage,512,10>(a[r],id[0]);});}
   else if constexpr(Stage==1){sycl::local_accessor<float,1>maximum(2,h);
    h.parallel_for(sycl::nd_range<1>(512,32),[=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
     unsigned j=it.get_global_linear_id(),local=it.get_local_linear_id();bool enabled[2];
     for(unsigned r=0;r<2;++r){enabled[r]=*a[r].active&&!a[r].failed();if(!local&&enabled[r]){float value=-INFINITY;for(unsigned c=0;c<32;++c)value=std::max(value,a[r].scratch[c]);maximum[r]=value;}}
     it.barrier(sycl::access::fence_space::local_space);
     for(unsigned r=0;r<2;++r)if(enabled[r]){float value=detmath::exp(a[r].in().get(j)-maximum[r]);a[r].scratch[64+j]=value;auto sg=it.get_sub_group();unsigned lane=sg.get_local_linear_id();
      for(unsigned width=1;width<16;width*=2){float rhs=sycl::select_from_group(sg,value,(lane+width)%32);if(lane%(2*width)==0)value=value+rhs;}
      if(lane%16==0)a[r].scratch[32+j/16]=value;
     }
    });
   }else{sycl::local_accessor<float,1>cached(2*513,h);
    h.parallel_for(sycl::nd_range<1>(16*256,256),[=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
     unsigned local=it.get_local_linear_id(),lane=local%32,base=it.get_group_linear_id()*32+local/32;bool enabled[2];
     for(unsigned r=0;r<2;++r){enabled[r]=*a[r].active&&!a[r].failed();if(!local&&enabled[r])cached[r*513+512]=route42::subtree<256>(32,0,[&](int j){return a[r].scratch[32+j];});}
     it.barrier(sycl::access::fence_space::local_space);
     for(unsigned r=0;r<2;++r)if(enabled[r])for(unsigned j=local;j<512;j+=256)cached[r*513+j]=a[r].scratch[64+j]/cached[r*513+512];
     it.barrier(sycl::access::fence_space::local_space);
     float values[2][4]{};unsigned ranks[2][4]{};
     for(unsigned r=0;r<2;++r)if(enabled[r])for(unsigned v=0;v<4;++v)values[r][v]=cached[r*513+base+v*8];
     for(unsigned k=lane;k<512;k+=32)for(unsigned r=0;r<2;++r)if(enabled[r]){float other=cached[r*513+k];for(unsigned v=0;v<4;++v)ranks[r][v]+=other>values[r][v]||(other==values[r][v]&&k<base+v*8);}
     auto sg=it.get_sub_group();for(unsigned width=1;width<32;width*=2)for(unsigned r=0;r<2;++r)for(unsigned v=0;v<4;++v){unsigned rhs=sycl::select_from_group(sg,ranks[r][v],(lane+width)%32);if(lane%(2*width)==0)ranks[r][v]+=rhs;}
     if(!lane)for(unsigned r=0;r<2;++r)if(enabled[r])for(unsigned v=0;v<4;++v)route42::output<512,10>(a[r],base+v*8,ranks[r][v]);
    });
   }
  });
 }
#endif
};
inline integrated::Launch route(ownrt::Device&d,const integrated::Spec&s,std::span<const ownrt::Allocation>a,std::span<const ownrt::Allocation>b){
 p49droute::validate(d,s,a);p49droute::validate(d,s,b);
 unsigned tail=s.ni+s.no+s.nw;
 for(unsigned i=0;i<a.size();++i)for(unsigned j=0;j<b.size();++j)if(a[i]==b[j]&&((i>=s.ni&&i<tail+2)||(j>=s.ni&&j<tail+2)))throw std::invalid_argument("71b route cross-row writable alias");
 std::vector<ownrt::Allocation>ids(a.begin(),a.end());ids.insert(ids.end(),b.begin(),b.end());integrated::Launch out{};
 auto issue=[&]<unsigned Stage>(){Route<Stage>op;op.spec=s;op.stride=a.size();std::array after{out.last};auto e=d.compute(op,ids,out.last?std::span<const ownrt::Event>(after):std::span<const ownrt::Event>{});if(!out.first)out.first=e;out.last=e;++out.passes;};
 issue.template operator()<0>();issue.template operator()<1>();issue.template operator()<2>();issue.template operator()<4>();return out;
}
}
