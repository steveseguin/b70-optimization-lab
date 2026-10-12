#include "route.hpp"
#if !defined(OWN_RT_HOST_ONLY) && !defined(HOST_ONLY)
namespace p30::route {
struct Capture {ng::Shape s;ng::Args a;float* scratch;};
static_assert(sizeof(Capture)<=1024,"kernel argument guard");
inline int error(ng::Args a){return sycl::atomic_ref<int32_t,sycl::memory_order::relaxed,sycl::memory_scope::device,sycl::access::address_space::global_space>(*a.i(15)).load();}
inline void fail(ng::Args a){sycl::atomic_ref<int32_t,sycl::memory_order::relaxed,sycl::memory_scope::device,sycl::access::address_space::global_space>(*a.i(15)).store(1);}
// Each aligned 32-leaf block performs precisely its original tree levels 1..5.
// For odd fixture widths, do not add +0 above the original tree height.
inline float chunk_tree(sycl::sub_group sg,float v,int n,int base){
 int lane=sg.get_local_linear_id();
 for(int d=1;d<32&&d<n;d*=2){float right=sycl::select_from_group(sg,v,sycl::id<1>((lane+d)%32));if(lane%(2*d)==0&&base+lane<n)v=v+(base+lane+d<n?right:0.f);}
 return sycl::select_from_group(sg,v,sycl::id<1>(0));
}
inline bool probabilities(Capture c,sycl::sub_group sg,float (&p)[16]){
 int lane=sg.get_local_linear_id(),n=c.s.width,bad=0;float m=-INFINITY;
 for(int z=0;z<16;++z){int j=z*32+lane;float v=j<n?read(c.s,c.a,j):-INFINITY;if(j<n&&!sycl::isfinite(v))bad=1;if(v>m)m=v;}
 for(int d=16;d;d/=2){float v=sycl::select_from_group(sg,m,sycl::id<1>(lane^d));int b=sycl::select_from_group(sg,bad,sycl::id<1>(lane^d));if(v>m)m=v;bad|=b;}
 if(bad){if(lane==0)fail(c.a);return false;}
 float partial[16];int chunks=(n+31)/32;
 for(int z=0;z<chunks;++z){int j=z*32+lane;p[z]=j<n?detmath::exp(read(c.s,c.a,j)-m):0.f;float v=chunk_tree(sg,p[z],n,z*32);if(lane==0)partial[z]=v;}
 float den=0.f;if(lane==0)den=tree(partial,chunks);den=sycl::select_from_group(sg,den,sycl::id<1>(0));
 for(int z=0;z<chunks;++z)if(z*32+lane<n)p[z]=p[z]/den;
 return true;
}
// All selected values are reconstructed independently in each subgroup. No
// cross-workgroup write/read dependency or spin rendezvous is used.
inline float selected_denominator(Capture c,sycl::sub_group sg,const float (&p)[16]){
 int lane=sg.get_local_linear_id(),prev=-1;float prev_value=INFINITY,selected[10];
 for(int rank=0;rank<c.s.extra;++rank){int id=512;float value=-INFINITY;
  for(int z=0;z<16;++z){int j=z*32+lane;if(j>=c.s.width)break;float v=p[z];if((rank==0||before(prev_value,prev,v,j))&&before(v,j,value,id)){value=v;id=j;}}
  for(int d=16;d;d/=2){float other=sycl::select_from_group(sg,value,sycl::id<1>(lane^d));int oi=sycl::select_from_group(sg,id,sycl::id<1>(lane^d));if(before(other,oi,value,id)){value=other;id=oi;}}
  prev=id;prev_value=value;selected[rank]=value;
 }
 float den=0.f;if(lane==0)den=tree(selected,c.s.extra);return sycl::select_from_group(sg,den,sycl::id<1>(0));
}
template<bool Single> inline void finish(Capture c,sycl::sub_group sg,const float (&p)[16],int partition,int partitions){
 int lane=sg.get_local_linear_id();float den=selected_denominator(c,sg,p);
 // All lanes execute each shuffle even when their prospective output is absent.
 for(int block=partition;block<(c.s.width+31)/32;block+=partitions){int j=block*32+lane;float v=j<c.s.width?p[block]:0.f;int rank=0;
  for(int k=0;k<c.s.width;++k){float other;
   if constexpr(Single)other=sycl::select_from_group(sg,p[k/32],sycl::id<1>(k%32));else other=c.scratch[k];
   rank+=before(other,k,v,j);
  }
  if(j<c.s.width&&rank<c.s.extra)write(c.a,rank,j,v/den);
 }
}
template<int Groups,int WG>std::vector<sycl::event> two(sycl::queue& q,Capture c,const std::vector<sycl::event>& deps){
 auto first=q.submit([&](sycl::handler& h){h.depends_on(deps);h.parallel_for(sycl::nd_range<1>(32,32),[=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{auto sg=it.get_sub_group();int lane=sg.get_local_linear_id();if(!*c.a.i(18)||error(c.a))return;float p[16];if(!probabilities(c,sg,p))return;for(int z=0;z<16;++z)if(z*32+lane<c.s.width)c.scratch[z*32+lane]=p[z];});});
 auto last=q.submit([&](sycl::handler& h){h.depends_on(first);h.parallel_for(sycl::nd_range<1>(Groups*WG,WG),[=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{auto sg=it.get_sub_group();int lane=sg.get_local_linear_id();if(!*c.a.i(18)||error(c.a))return;float p[16];for(int z=0;z<16;++z)p[z]=z*32+lane<c.s.width?c.scratch[z*32+lane]:0.f;int part=it.get_group_linear_id()*(WG/32)+sg.get_group_linear_id();finish<false>(c,sg,p,part,Groups*(WG/32));});});
 return {first,last};
}
std::vector<sycl::event> submit(sycl::queue& q,ng::Shape s,ng::Args a,float* scratch,std::string_view variant,const std::vector<sycl::event>& deps){
 Capture c{s,a,scratch};
 if(variant==variants[0])return two<1,32>(q,c,deps);
 if(variant==variants[1])return two<16,32>(q,c,deps);
 if(variant==variants[2])return two<16,64>(q,c,deps);
 if(variant!=variants[3])throw std::invalid_argument("route candidate");
 return {q.submit([&](sycl::handler& h){h.depends_on(deps);h.parallel_for(sycl::nd_range<1>(32,32),[=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{auto sg=it.get_sub_group();if(!*c.a.i(18)||error(c.a))return;float p[16];if(probabilities(c,sg,p))finish<true>(c,sg,p,0,1);});})};
}
}
#endif
