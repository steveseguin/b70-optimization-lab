#include "stage2/packet194-expert-diet-engine/kernel_guard.hpp"
#ifndef OWN_RT_HOST_ONLY
#include "stage2/packet194-expert-diet-engine/prepared_submission.hpp"
#endif
#pragma once
// Original packet47 implementation. Sealed packet45 kernels are read-only controls.
#include "stage2/packet194-expert-diet-engine/p30_attention.hpp"
#include "stage2/packet194-expert-diet-engine/round2.hpp"
#include <sycl/sycl.hpp>
namespace p47 {
constexpr int tile=32, heads=24, dim=256;
using Atomic=sycl::atomic_ref<int32_t,sycl::memory_order::relaxed,sycl::memory_scope::device,sycl::access::address_space::global_space>;
inline int splits(ng::Shape s){return (ng::launch_slots(s)+31)/32;}
inline size_t scratch_floats(ng::Shape s){return size_t(s.tokens)*24*splits(s)*258;}
inline float bf(uint16_t v){return std::bit_cast<float>(uint32_t(v)<<16);}
struct Team {
 sycl::nd_item<1> it;float* x;
 template<class F>void each(int n,F f)const{for(int j=it.get_local_linear_id();j<n;j+=it.get_local_range(0))f(j);}
 void barrier()const{it.barrier(sycl::access::fence_space::local_space);}
 int error(ng::Args a)const{return Atomic(a.i(15)[0]).load();}
 void fail(ng::Args a)const{Atomic(a.i(15)[0]).store(1);}
 float sum(int n,int base=0)const{for(int z=1;z<n;z*=2){each((n+2*z-1)/(2*z),[&](int j){int i=j*2*z;x[base+i]=x[base+i]+(i+z<n?x[base+i+z]:0.f);});barrier();}return x[base];}
};
// Validate once per row, before any attention kernel; avoid thousands of repeated
// serial index scans. Counts are device scratch, never host readback or a cache.
inline sycl::event admit(sycl::queue&q,ng::Shape s,ng::Args a,int* counts,const std::vector<sycl::event>&deps={}){
 return ownrt::prepared_submit(q,[=,p35_range0=sycl::range<1>(s.tokens)](sycl::handler& h){h.parallel_for(p35_range0,packet26::checked([=](sycl::id<1>idx){int r=idx[0];counts[r]=-1;if(!a.i(18)[0]||Atomic(a.i(15)[0]).load())return;int pos=a.i(17)[0];if(pos<0||pos>ng::launch_extent(s)-s.tokens){Atomic(a.i(15)[0]).store(1);return;}int n=0,S=s.budget+3;while(n<S&&a.i(4)[r*S+n]!=-1){int id=a.i(4)[r*S+n];if(id<0||id>=s.capacity||id>pos+r||n>=ng::launch_slots(s)){Atomic(a.i(15)[0]).store(1);return;}++n;}counts[r]=n;}));});
}
// admit with one 256-lane work-group per row: the count is the first -1 slot (minimum over lanes), and the row fails
// exactly when admit's serial scan would (an invalid id before it, or more slots than launch_slots); the result does
// not depend on which slot is found first. OWNRT_ADMIT_FAST=0 keeps the single-item scan.
inline sycl::event admit_fast(sycl::queue&q,ng::Shape s,ng::Args a,int* counts,const std::vector<sycl::event>&deps={}){
 constexpr int W=256;
 return ownrt::prepared_submit(q,[=,p35_range0=sycl::nd_range<1>(size_t(s.tokens)*W,W)](sycl::handler& h){h.parallel_for(p35_range0,packet26::checked([=](sycl::nd_item<1> it){
  const int r=int(it.get_group_linear_id()),lane=int(it.get_local_linear_id());auto g=it.get_group();
  if(lane==0)counts[r]=-1;
  const bool skip=sycl::group_broadcast(g,lane==0?int(!a.i(18)[0]||Atomic(a.i(15)[0]).load()):0,0)!=0;if(skip)return;
  const int pos=a.i(17)[0];if(pos<0||pos>ng::launch_extent(s)-s.tokens){if(lane==0)Atomic(a.i(15)[0]).store(1);return;}
  const int S=s.budget+3;const int* ids=a.i(4)+r*S;int first=S;
  for(int k=lane;k<S;k+=W)if(ids[k]==-1){first=k;break;}
  first=sycl::reduce_over_group(g,first,sycl::minimum<int>());
  bool bad=first>ng::launch_slots(s);
  for(int k=lane;k<first;k+=W){const int id=ids[k];bad=bad||id<0||id>=s.capacity||id>pos+r;}
  bad=sycl::any_of_group(g,bad);
  if(lane==0){if(bad)Atomic(a.i(15)[0]).store(1);else counts[r]=first;}
 }));});
}
inline bool admit_fast_on(){static const bool on=[]{const char* e=std::getenv("OWNRT_ADMIT_FAST");return !e||e[0]!='0';}();return on;}
inline float lane_tree(sycl::sub_group sg,float v){int lane=sg.get_local_linear_id();for(int z=1;z<32;z*=2){float rhs=sycl::select_from_group(sg,v,(lane+z)%32);if(lane%(2*z)==0)v=v+rhs;}return sycl::select_from_group(sg,v,0);}
template<bool F32=false> inline float score(sycl::sub_group sg,ng::Args a,int r,int h,int id){
 int lane=sg.get_local_linear_id();
 if constexpr(F32){ // exact mode: F32 K cache and F32 queries, same products and fixed trees
  sycl::vec<float,8> k,q;
  k.load(0,sycl::address_space_cast<sycl::access::address_space::global_space,sycl::access::decorated::no>(static_cast<const float*>(a.p[2])+(id*2+h/12)*256+lane*8));
  q.load(0,sycl::address_space_cast<sycl::access::address_space::global_space,sycl::access::decorated::no>(static_cast<const float*>(a.p[0])+(r*24+h)*256+lane*8));
  float v[8];for(int j=0;j<8;++j)v[j]=k[j]*q[j];for(int z=1;z<8;z*=2)for(int j=0;j<8;j+=2*z)v[j]=v[j]+v[j+z];return lane_tree(sg,v[0])/detmath::sqrt(256.f);
 }
 sycl::vec<uint16_t,8> k,q;
 k.load(0,sycl::address_space_cast<sycl::access::address_space::global_space,sycl::access::decorated::no>(static_cast<const uint16_t*>(a.p[2])+(id*2+h/12)*256+lane*8));
 q.load(0,sycl::address_space_cast<sycl::access::address_space::global_space,sycl::access::decorated::no>(static_cast<const uint16_t*>(a.p[0])+(r*24+h)*256+lane*8));
 float v[8];for(int j=0;j<8;++j)v[j]=bf(k[j])*bf(q[j]);for(int z=1;z<8;z*=2)for(int j=0;j<8;j+=2*z)v[j]=v[j]+v[j+z];return lane_tree(sg,v[0])/detmath::sqrt(256.f);
}
inline bool blocked(ng::Args a){return !a.i(18)[0]||Atomic(a.i(15)[0]).load();}
// Production verifies rows sequentially through the M=1 p30 path.
inline std::vector<sycl::event> current(sycl::queue&q,ng::Shape s,ng::Args a,const int*positions){
 std::vector<sycl::event> events;int rows=s.tokens,S=s.budget+3;s.tokens=1;s.extra=ng::launch_slots(s);
 for(int r=0;r<rows;++r){ng::Args row=a;for(int slot:{0,1,5})row.p[slot]=static_cast<uint16_t*>(a.p[slot])+r*6144;row.p[4]=a.i(4)+r*S;for(int slot:{6,7})row.p[slot]=a.f(slot)+r*24*S;row.p[17]=const_cast<int*>(positions+r);
 auto e=p30::attention::submit(q,s,row,nullptr,1,events.empty()?std::vector<sycl::event>{}:std::vector<sycl::event>{events.back()});events.insert(events.end(),e.begin(),e.end());}return events;
}
template<int Stage>inline sycl::event select_stage(sycl::queue&q,ng::Shape s,ng::Args a,float*scratch,const std::vector<sycl::event>&deps={}){s.op=ng::select;return ownrt::prepared_submit(q,[=,p35_range0=sycl::nd_range<1>(size_t(round2::groups(s))*32,32)](sycl::handler& h){sycl::local_accessor<float,1>local(round2::local_floats(s),h);h.parallel_for(p35_range0,packet26::checked([=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{round2::group<ng::select,Stage>(s,a,it.get_group_linear_id(),scratch,Team{it,local.get_multi_ptr<sycl::access::decorated::no>().get()});}));});}
inline std::vector<sycl::event> selection(sycl::queue&q,ng::Shape s,ng::Args a,float*scratch){auto first=select_stage<0>(q,s,a,scratch);return {first,select_stage<1>(q,s,a,scratch,{first})};}
// One tile is fixed by selected-token index. Work-group count, hardware and M
// never change the tree. 4 subgroups calculate 32 scores, each lane loads8 BF16.
template<bool SplitSoftmax,bool F32=false>inline sycl::event tiles(sycl::queue&q,ng::Shape s,ng::Args a,const int*counts,float*partial,const std::vector<sycl::event>&deps){
 int C=splits(s);return ownrt::prepared_submit(q,[=,p35_range0=sycl::nd_range<1>(size_t(s.tokens)*24*C*128,128)](sycl::handler& handler){sycl::local_accessor<float,1>local(66,handler);
 handler.parallel_for(p35_range0,packet26::checked([=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
 int g=it.get_group_linear_id(),c=g%C,h=(g/C)%24,r=g/(C*24),lid=it.get_local_linear_id(),n=counts[r],S=s.budget+3;
 if(n<=0||blocked(a))return;int start=c*32;if(start>=n)return;auto sg=it.get_sub_group();int lane=sg.get_local_linear_id(),sub=it.get_local_linear_id()/32;
 float* p=partial+size_t(g)*258;
 if constexpr(SplitSoftmax){
  for(int j=sub;j<32;j+=4){float x=-INFINITY;if(start+j<n)x=score<F32>(sg,a,r,h,a.i(4)[r*S+start+j]);if(lane==0)local[j]=x;}
  it.barrier(sycl::access::fence_space::local_space);
  if(lid==0){float m=-INFINITY;for(int j=0;j<32&&start+j<n;++j)m=std::max(m,local[j]);local[64]=m;p[256]=m;}
  it.barrier(sycl::access::fence_space::local_space);
  if(lid<32){float x=start+lid<n?detmath::exp(local[lid]-local[64]):0.f;local[32+lid]=x;float den=lane_tree(sg,x);if(lid==0)p[257]=den;}
  it.barrier(sycl::access::fence_space::local_space);
 }else {if(lid<32)local[32+lid]=start+lid<n?a.f(7)[(r*24+h)*S+start+lid]:0.f;it.barrier(sycl::access::fence_space::local_space);}
 // Two adjacent BF16 dimensions per lane: contiguous/coalesced V, 64 FP32
 // registers for the fixed32 tree, no 2051-element local array and no atomics.
 sycl::vec<float,2> vals[32];for(int j=0;j<32;++j){vals[j]=sycl::vec<float,2>(0.f);if(start+j<n){int id=a.i(4)[r*S+start+j];if constexpr(F32){sycl::vec<float,2>v;v.load(0,sycl::address_space_cast<sycl::access::address_space::global_space,sycl::access::decorated::no>(static_cast<const float*>(a.p[3])+(id*2+h/12)*256+lid*2));for(int d=0;d<2;++d)vals[j][d]=local[32+j]*v[d];}
  else{sycl::vec<uint16_t,2>v;v.load(0,sycl::address_space_cast<sycl::access::address_space::global_space,sycl::access::decorated::no>(static_cast<const uint16_t*>(a.p[3])+(id*2+h/12)*256+lid*2));for(int d=0;d<2;++d)vals[j][d]=local[32+j]*bf(v[d]);}}}
 for(int z=1;z<32&&(SplitSoftmax||z<n);z*=2)for(int j=0;j<32;j+=2*z)if(SplitSoftmax||start+j<n)vals[j]=vals[j]+(SplitSoftmax||start+j+z<n?vals[j+z]:sycl::vec<float,2>(0.f));
 p[lid*2]=vals[0][0];p[lid*2+1]=vals[0][1];
 }));});
}
// Split-softmax tiles, F32, with the tile's 32 slot ids staged once in local memory, the query row loaded once per
// subgroup, and each subgroup's 8 K rows requested before its 8 scores are formed. Every score is score<true>()'s
// products, 8-leaf tree, lane tree and division; softmax and V accumulation are tiles<true,true>'s. Exact.
inline sycl::event tiles_pipelined(sycl::queue&q,ng::Shape s,ng::Args a,const int*counts,float*partial,const std::vector<sycl::event>&deps){
 int C=splits(s);return ownrt::prepared_submit(q,[=,p35_range0=sycl::nd_range<1>(size_t(s.tokens)*24*C*128,128)](sycl::handler& handler){sycl::local_accessor<float,1>local(66,handler);sycl::local_accessor<int,1>slot(32,handler);
 handler.parallel_for(p35_range0,packet26::checked([=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
 int g=it.get_group_linear_id(),c=g%C,h=(g/C)%24,r=g/(C*24),lid=it.get_local_linear_id(),n=counts[r],S=s.budget+3;
 if(n<=0||blocked(a))return;int start=c*32;if(start>=n)return;auto sg=it.get_sub_group();int lane=sg.get_local_linear_id(),sub=it.get_local_linear_id()/32;
 float* p=partial+size_t(g)*258;
 if(lid<32)slot[lid]=start+lid<n?a.i(4)[r*S+start+lid]:-1;
 it.barrier(sycl::access::fence_space::local_space);
 const float* K=static_cast<const float*>(a.p[2]);
 sycl::vec<float,8> qv;qv.load(0,sycl::address_space_cast<sycl::access::address_space::global_space,sycl::access::decorated::no>(static_cast<const float*>(a.p[0])+(r*24+h)*256+lane*8));
 sycl::vec<float,8> kv[8];
 #pragma unroll
 for(int t=0;t<8;++t){const int j=sub+4*t;kv[t]=sycl::vec<float,8>(0.f);if(start+j<n)kv[t].load(0,sycl::address_space_cast<sycl::access::address_space::global_space,sycl::access::decorated::no>(K+(slot[j]*2+h/12)*256+lane*8));}
 #pragma unroll
 for(int t=0;t<8;++t){const int j=sub+4*t;float x=-INFINITY;
  if(start+j<n){float v[8];for(int e=0;e<8;++e)v[e]=kv[t][e]*qv[e];for(int z=1;z<8;z*=2)for(int e=0;e<8;e+=2*z)v[e]=v[e]+v[e+z];x=lane_tree(sg,v[0])/detmath::sqrt(256.f);}
  if(lane==0)local[j]=x;}
 it.barrier(sycl::access::fence_space::local_space);
 if(lid==0){float m=-INFINITY;for(int j=0;j<32&&start+j<n;++j)m=std::max(m,local[j]);local[64]=m;p[256]=m;}
 it.barrier(sycl::access::fence_space::local_space);
 if(lid<32){float x=start+lid<n?detmath::exp(local[lid]-local[64]):0.f;local[32+lid]=x;float den=lane_tree(sg,x);if(lid==0)p[257]=den;}
 it.barrier(sycl::access::fence_space::local_space);
 const float* V=static_cast<const float*>(a.p[3]);
 sycl::vec<float,2> vals[32];
 #pragma unroll
 for(int j=0;j<32;++j){vals[j]=sycl::vec<float,2>(0.f);if(start+j<n){sycl::vec<float,2>v;v.load(0,sycl::address_space_cast<sycl::access::address_space::global_space,sycl::access::decorated::no>(V+(slot[j]*2+h/12)*256+lid*2));for(int d=0;d<2;++d)vals[j][d]=local[32+j]*v[d];}}
 for(int z=1;z<32;z*=2)for(int j=0;j<32;j+=2*z)vals[j]=vals[j]+vals[j+z];
 p[lid*2]=vals[0][0];p[lid*2+1]=vals[0][1];
 }));});
}
// Measured slower (3K context, rank 0 tiles pass: 914 -> 1079 us per step; 64 K floats per lane held in registers);
// OWNRT_ATTN_PIPELINE=1 opts in.
inline bool tiles_pipelined_on(){static const bool on=[]{const char* e=std::getenv("OWNRT_ATTN_PIPELINE");return e&&e[0]=='1';}();return on;}
// Split-softmax tiles with grouped heads: one work-group per (row, KV head, tile) runs the 12 query heads that share
// the KV head in turn, each with tiles<true>'s unchanged per-head body and the same partial slot, so each K/V row
// is fetched from memory once per tile instead of once per query head (later heads hit the cache). Exact.
template<bool F32=false>inline sycl::event tiles_gqa(sycl::queue&q,ng::Shape s,ng::Args a,const int*counts,float*partial,const std::vector<sycl::event>&deps){
 int C=splits(s);return ownrt::prepared_submit(q,[=,p35_range0=sycl::nd_range<1>(size_t(s.tokens)*2*C*128,128)](sycl::handler& handler){sycl::local_accessor<float,1>local(66,handler);
 handler.parallel_for(p35_range0,packet26::checked([=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
 const int G=it.get_group_linear_id(),c=G%C,kv=(G/C)%2,r=G/(C*2),lid=it.get_local_linear_id(),n=counts[r],S=s.budget+3;
 if(n<=0||blocked(a))return;const int start=c*32;if(start>=n)return;auto sg=it.get_sub_group();const int lane=sg.get_local_linear_id(),sub=it.get_local_linear_id()/32;
 for(int t=0;t<12;++t){const int h=kv*12+t;const int g=(r*24+h)*C+c;float* p=partial+size_t(g)*258;
  for(int j=sub;j<32;j+=4){float x=-INFINITY;if(start+j<n)x=score<F32>(sg,a,r,h,a.i(4)[r*S+start+j]);if(lane==0)local[j]=x;}
  it.barrier(sycl::access::fence_space::local_space);
  if(lid==0){float m=-INFINITY;for(int j=0;j<32&&start+j<n;++j)m=std::max(m,local[j]);local[64]=m;p[256]=m;}
  it.barrier(sycl::access::fence_space::local_space);
  if(lid<32){float x=start+lid<n?detmath::exp(local[lid]-local[64]):0.f;local[32+lid]=x;float den=lane_tree(sg,x);if(lid==0)p[257]=den;}
  it.barrier(sycl::access::fence_space::local_space);
  sycl::vec<float,2> vals[32];for(int j=0;j<32;++j){vals[j]=sycl::vec<float,2>(0.f);if(start+j<n){int id=a.i(4)[r*S+start+j];if constexpr(F32){sycl::vec<float,2>v;v.load(0,sycl::address_space_cast<sycl::access::address_space::global_space,sycl::access::decorated::no>(static_cast<const float*>(a.p[3])+(id*2+h/12)*256+lid*2));for(int d=0;d<2;++d)vals[j][d]=local[32+j]*v[d];}
   else{sycl::vec<uint16_t,2>v;v.load(0,sycl::address_space_cast<sycl::access::address_space::global_space,sycl::access::decorated::no>(static_cast<const uint16_t*>(a.p[3])+(id*2+h/12)*256+lid*2));for(int d=0;d<2;++d)vals[j][d]=local[32+j]*bf(v[d]);}}}
  for(int z=1;z<32;z*=2)for(int j=0;j<32;j+=2*z)vals[j]=vals[j]+vals[j+z];
  p[lid*2]=vals[0][0];p[lid*2+1]=vals[0][1];
  it.barrier(sycl::access::fence_space::local_space); // the next head reuses the tile scratch
 }
 }));});
}
// Measured slower (3K context, rank 0: 2127 -> 2913 us per step: 12x fewer work-groups, serial heads); OWNRT_ATTN_GQA=1 opts in.
inline bool attention_gqa(){static const bool on=[]{const char* e=std::getenv("OWNRT_ATTN_GQA");return e&&e[0]=='1';}();return on;}
inline sycl::event scores(sycl::queue&q,ng::Shape s,ng::Args a,const int*counts,const std::vector<sycl::event>&deps){int L=ng::launch_slots(s),S=s.budget+3;return ownrt::prepared_submit(q,[=,p35_range0=sycl::nd_range<1>(size_t(s.tokens)*24*L*32,32)](sycl::handler& handler){handler.parallel_for(p35_range0,packet26::checked([=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{int g=it.get_group_linear_id(),j=g%L,h=(g/L)%24,r=g/(L*24),n=counts[r];if(n<0||blocked(a))return;auto sg=it.get_sub_group();float v=-INFINITY;if(j<n)v=score(sg,a,r,h,a.i(4)[r*S+j]);if(sg.get_local_linear_id()==0)a.f(6)[(r*24+h)*S+j]=v;}));});}
inline sycl::event softmax(sycl::queue&q,ng::Shape s,ng::Args a,const int*counts,const std::vector<sycl::event>&deps){int S=s.budget+3;return ownrt::prepared_submit(q,[=,p35_range0=sycl::nd_range<1>(size_t(s.tokens)*24*128,128)](sycl::handler& handler){sycl::local_accessor<float,1>local(S+1,handler);handler.parallel_for(p35_range0,packet26::checked([=](sycl::nd_item<1>it){int h=it.get_group_linear_id(),r=h/24,n=counts[r];if(n<=0||blocked(a))return;Team t{it,local.get_multi_ptr<sycl::access::decorated::no>().get()};if(it.get_local_linear_id()==0){float m=-INFINITY;for(int j=0;j<n;++j)m=std::max(m,a.f(6)[h*S+j]);local[S]=m;}t.barrier();float m=local[S];t.each(n,[&](int j){float x=detmath::exp(a.f(6)[h*S+j]-m);local[j]=x;a.f(7)[h*S+j]=x;});t.barrier();float den=t.sum(n);t.barrier();t.each(n,[&](int j){a.f(7)[h*S+j]=a.f(7)[h*S+j]/den;});}));});}
template<bool SplitSoftmax,bool F32=false>inline sycl::event combine(sycl::queue&q,ng::Shape s,ng::Args a,const int*counts,const float*partial,const std::vector<sycl::event>&deps){int C=splits(s);return ownrt::prepared_submit(q,[=,p35_range0=sycl::nd_range<1>(size_t(s.tokens)*24*128,128)](sycl::handler& handler){sycl::local_accessor<float,1>factors(131,handler);handler.parallel_for(p35_range0,packet26::checked([=](sycl::nd_item<1>it){int h=it.get_group_linear_id(),r=h/24,lid=it.get_local_linear_id(),n=counts[r];if(n<=0||blocked(a))return;int count=(n+31)/32;const float*p=partial+size_t(h)*C*258;float den=1.f;
 if constexpr(SplitSoftmax){if(lid==0){float m=-INFINITY;for(int c=0;c<count;++c)m=std::max(m,p[c*258+256]);factors[130]=m;}it.barrier(sycl::access::fence_space::local_space);if(lid<count){float f=detmath::exp(p[lid*258+256]-factors[130]);factors[lid]=f;factors[65+lid]=p[lid*258+257]*f;}it.barrier(sycl::access::fence_space::local_space);
 // One shared denominator tree, not 128 duplicate private65 trees.
 for(int z=1;z<count;z*=2){if(lid%(2*z)==0&&lid<count)factors[65+lid]=factors[65+lid]+(lid+z<count?factors[65+lid+z]:0.f);it.barrier(sycl::access::fence_space::local_space);}den=factors[65];}
 for(int d=0;d<2;++d){float x[65];for(int c=0;c<count;++c){float v=p[c*258+lid*2+d];if constexpr(SplitSoftmax)v=v*factors[c];x[c]=v;}float v=p30::attention::tree(x,count);if constexpr(SplitSoftmax)v=v/den;a.put(5,h*256+lid*2+d,(F32?v:ng::Args::bf(v))*ng::sigmoid(a.b(1,h*256+lid*2+d)));}
 }));});}

inline std::vector<sycl::event> candidate(sycl::queue&q,ng::Shape s,ng::Args a,int*counts,float*scratch,bool split){ng::validate(s);std::vector<sycl::event>e{admit(q,s,a,counts)};if(split){e.push_back(tiles<true>(q,s,a,counts,scratch,{e.back()}));e.push_back(combine<true>(q,s,a,counts,scratch,{e.back()}));}else{e.push_back(scores(q,s,a,counts,{e.back()}));e.push_back(softmax(q,s,a,counts,{e.back()}));e.push_back(tiles<false>(q,s,a,counts,scratch,{e.back()}));e.push_back(combine<false>(q,s,a,counts,scratch,{e.back()}));}return e;}
}
