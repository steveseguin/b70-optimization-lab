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
// The guard read once per group instead of once per lane: a relaxed device-scope atomic load by every lane of the same
// address serializes (lab 2026-10-26: 50K lanes = 36 us; tiles<true,true> issues 200K per layer). Nothing writes the
// flag during the attention passes (admit runs before them), so every lane sees the same value either way.
inline bool blocked_wg(sycl::nd_item<1> it,ng::Args a){return sycl::group_broadcast(it.get_group(),it.get_local_linear_id()==0?int(blocked(a)):0,0)!=0;}
inline bool blocked_sg(sycl::sub_group sg,ng::Args a){return sycl::group_broadcast(sg,sg.get_local_linear_id()==0?int(blocked(a)):0,0)!=0;}
inline bool attention_guard_once(){static const bool on=[]{const char* e=std::getenv("OWNRT_ATTN_GUARD");return e&&e[0]=='1';}();return on;}
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
template<bool SplitSoftmax,bool F32=false,bool Guard=false>inline sycl::event tiles(sycl::queue&q,ng::Shape s,ng::Args a,const int*counts,float*partial,const std::vector<sycl::event>&deps){
 int C=splits(s);return ownrt::prepared_submit(q,[=,p35_range0=sycl::nd_range<1>(size_t(s.tokens)*24*C*128,128)](sycl::handler& handler){sycl::local_accessor<float,1>local(66,handler);
 handler.parallel_for(p35_range0,packet26::checked([=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
 int g=it.get_group_linear_id(),c=g%C,h=(g/C)%24,r=g/(C*24),lid=it.get_local_linear_id(),n=counts[r],S=s.budget+3;
 if(n<=0||(Guard?blocked_wg(it,a):blocked(a)))return;int start=c*32;if(start>=n)return;auto sg=it.get_sub_group();int lane=sg.get_local_linear_id(),sub=it.get_local_linear_id()/32;
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
// Split-softmax tiles, wide: 256 lanes per (row, head, tile). Each of the 8 subgroups forms 4 of the tile's 32 scores
// (score<F32>() unchanged), and in the value phase each lane owns one of the 256 dimensions instead of two. Max,
// exponentials, denominator tree and every dimension's 32-token tree are tiles<true,F32>'s; partial slots unchanged.
template<bool F32=false>inline sycl::event tiles_wide(sycl::queue&q,ng::Shape s,ng::Args a,const int*counts,float*partial,const std::vector<sycl::event>&deps){
 int C=splits(s);return ownrt::prepared_submit(q,[=,p35_range0=sycl::nd_range<1>(size_t(s.tokens)*24*C*256,256)](sycl::handler& handler){sycl::local_accessor<float,1>local(66,handler);
 handler.parallel_for(p35_range0,packet26::checked([=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
 int g=it.get_group_linear_id(),c=g%C,h=(g/C)%24,r=g/(C*24),lid=it.get_local_linear_id(),n=counts[r],S=s.budget+3;
 if(n<=0||blocked(a))return;int start=c*32;if(start>=n)return;auto sg=it.get_sub_group();int lane=sg.get_local_linear_id(),sub=it.get_local_linear_id()/32;
 float* p=partial+size_t(g)*258;
 for(int j=sub;j<32;j+=8){float x=-INFINITY;if(start+j<n)x=score<F32>(sg,a,r,h,a.i(4)[r*S+start+j]);if(lane==0)local[j]=x;}
 it.barrier(sycl::access::fence_space::local_space);
 if(lid==0){float m=-INFINITY;for(int j=0;j<32&&start+j<n;++j)m=std::max(m,local[j]);local[64]=m;p[256]=m;}
 it.barrier(sycl::access::fence_space::local_space);
 if(lid<32){float x=start+lid<n?detmath::exp(local[lid]-local[64]):0.f;local[32+lid]=x;float den=lane_tree(sg,x);if(lid==0)p[257]=den;}
 it.barrier(sycl::access::fence_space::local_space);
 float vals[32];
 #pragma unroll
 for(int j=0;j<32;++j){vals[j]=0.f;if(start+j<n){int id=a.i(4)[r*S+start+j];
  if constexpr(F32)vals[j]=local[32+j]*static_cast<const float*>(a.p[3])[(id*2+h/12)*256+lid];
  else vals[j]=local[32+j]*bf(static_cast<const uint16_t*>(a.p[3])[(id*2+h/12)*256+lid]);}}
 for(int z=1;z<32;z*=2)for(int j=0;j<32;j+=2*z)vals[j]=vals[j]+vals[j+z];
 p[lid]=vals[0];
 }));});
}
// Measured slower (3K context, rank 0 tiles pass 914 -> 1597 us per step); OWNRT_ATTN_WIDE=1 opts in.
inline bool tiles_wide_on(){static const bool on=[]{const char* e=std::getenv("OWNRT_ATTN_WIDE");return e&&e[0]=='1';}();return on;}
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
template<bool SplitSoftmax,bool F32=false,bool Guard=false>inline sycl::event combine(sycl::queue&q,ng::Shape s,ng::Args a,const int*counts,const float*partial,const std::vector<sycl::event>&deps){int C=splits(s);return ownrt::prepared_submit(q,[=,p35_range0=sycl::nd_range<1>(size_t(s.tokens)*24*128,128)](sycl::handler& handler){sycl::local_accessor<float,1>factors(131,handler);handler.parallel_for(p35_range0,packet26::checked([=](sycl::nd_item<1>it){int h=it.get_group_linear_id(),r=h/24,lid=it.get_local_linear_id(),n=counts[r];if(n<=0||(Guard?blocked_wg(it,a):blocked(a)))return;int count=(n+31)/32;const float*p=partial+size_t(h)*C*258;float den=1.f;
 if constexpr(SplitSoftmax){if(lid==0){float m=-INFINITY;for(int c=0;c<count;++c)m=std::max(m,p[c*258+256]);factors[130]=m;}it.barrier(sycl::access::fence_space::local_space);if(lid<count){float f=detmath::exp(p[lid*258+256]-factors[130]);factors[lid]=f;factors[65+lid]=p[lid*258+257]*f;}it.barrier(sycl::access::fence_space::local_space);
 // One shared denominator tree, not 128 duplicate private65 trees.
 for(int z=1;z<count;z*=2){if(lid%(2*z)==0&&lid<count)factors[65+lid]=factors[65+lid]+(lid+z<count?factors[65+lid+z]:0.f);it.barrier(sycl::access::fence_space::local_space);}den=factors[65];}
 for(int d=0;d<2;++d){float x[65];for(int c=0;c<count;++c){float v=p[c*258+lid*2+d];if constexpr(SplitSoftmax)v=v*factors[c];x[c]=v;}float v=p30::attention::tree(x,count);if constexpr(SplitSoftmax)v=v/den;a.put(5,h*256+lid*2+d,(F32?v:ng::Args::bf(v))*ng::sigmoid(a.b(1,h*256+lid*2+d)));}
 }));});}

// ---- QSA decode attention, lab 2026-10-26 (default off; exact against tiles<true,true>/combine<true,true>) ----
// first_max(l,r): l covers the lower indices. The serial scan `m=-INFINITY; m=std::max(m,x)` keeps the FIRST of equal
// maxima (so +0/-0 by position) and skips NaN (m<NaN is false). first_max returns exactly that element for any
// concatenation (it is a homomorphism over ordered sequences), so an order-preserving tree followed by
// first_max(-INFINITY, .) reproduces the scan's bits. No reliance on the max being order-independent.
inline float first_max(float l,float r){return sycl::isnan(r)?l:(sycl::isnan(l)?r:(l<r?r:l));}
inline float sg_first_max(sycl::sub_group sg,float v){const int lane=sg.get_local_linear_id();
 for(int z=1;z<32;z*=2){const float o=sycl::permute_group_by_xor(sg,v,z);v=(lane&z)?first_max(o,v):first_max(v,o);}return v;}
// p30::attention::tree(x,n) equals the balanced tree over 2^L leaves (L = levels run = ceil(log2 n)) with leaves at
// index >= n set to +0.f: its "+0.f" for a missing right child is exactly a zero-padded subtree (0+0=+0), and nodes
// at index >= n are only ever right children. Both kernels below evaluate that padded balanced tree, stopping at the
// root of level L, with every node formed as (lower block) + (upper block).
//
// Combine, blocked: one 128-lane work-group per (row, head, 32-dimension block): 8x the work-groups of combine<>.
// Phase A (all 4 subgroups, lane = tile): tile max by first_max tree, factors exp(m_c - m), denominator leaves
// d_c*f_c and their level-1..5 nodes by subgroup butterflies (lower+upper). Phase B (subgroup s = tiles 16s..16s+15,
// lane = dimension): leaves p_c[dim]*f_c, levels 1..4 in registers. Phase C (subgroup 0): levels 5..7 from local
// memory, tile 64's padded right subtree (six +0.f), v/den, output * sigmoid(gate). Requires C <= 65 (budget 2048).
// Every global read is issued before the guard. Lab 2026-10-26, n=2051: 44 -> 7 us (bench), 44.5 -> 7.9 us per layer
// (rank-1 device profile).
inline sycl::event combine_blocked(sycl::queue&q,ng::Shape s,ng::Args a,const int*counts,const float*partial,const std::vector<sycl::event>&deps){
 const int C=splits(s);if(C>65)throw std::invalid_argument("combine_blocked tile count");
 return ownrt::prepared_submit(q,[=,p35_range0=sycl::nd_range<1>(size_t(s.tokens)*24*8*128,128)](sycl::handler& handler){
 sycl::local_accessor<float,1>fac(128,handler);sycl::local_accessor<float,1>part(8+4*32,handler);
 handler.parallel_for(p35_range0,packet26::checked([=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
  const int g=int(it.get_group_linear_id()),blk=g%8,hh=g/8,r=hh/24,lid=int(it.get_local_linear_id());
  auto sg=it.get_sub_group();const int lane=int(sg.get_local_linear_id()),sub=lid/32,dim=blk*32+lane;
  const float*p=partial+size_t(hh)*C*258;
  // Every global read is issued before the guard: tiles c < C of this head always exist in the scratch (values of
  // tiles >= count are never used), the gate row exists, so one memory round trip covers the whole pass.
  float raw[16];
  #pragma unroll
  for(int k=0;k<16;++k){const int c=sub*16+k;raw[k]=c<C?p[c*258+dim]:0.f;}
  const float raw64=(sub==0&&C>64)?p[64*258+dim]:0.f;
  const float pm0=lid<C?p[lid*258+256]:NAN,pd0=lid<C?p[lid*258+257]:0.f;
  const float gate=sub==0?ng::sigmoid(a.b(1,hh*256+dim)):0.f;
  const int n=counts[r];
  if(n<=0||blocked_wg(it,a))return;
  const int count=(n+31)/32;
  const bool valid=lid<count;
  const float pm=valid?pm0:NAN;
  const float fm=sg_first_max(sg,pm);
  if(lane==0)part[sub]=fm;
  it.barrier(sycl::access::fence_space::local_space);
  const float m=first_max(first_max(first_max(first_max(-INFINITY,part[0]),part[1]),part[2]),part[3]);
  const float f=valid?detmath::exp(pm-m):0.f;
  fac[lid]=f;
  float d=valid?pd0*f:0.f;
  for(int z=1;z<32&&z<count;z*=2){const float o=sycl::permute_group_by_xor(sg,d,z);d=(lane&z)?o+d:d+o;}
  if(lane==0)part[4+sub]=d;
  it.barrier(sycl::access::fence_space::local_space);
  float lv[16];
  #pragma unroll
  for(int k=0;k<16;++k){const int c=sub*16+k;lv[k]=c<count?raw[k]*fac[c]:0.f;}
  #pragma unroll
  for(int z=1;z<16;z*=2)if(z<count){
   #pragma unroll
   for(int k=0;k<16;k+=2*z)lv[k]=lv[k]+lv[k+z];}
  part[8+sub*32+lane]=lv[0];
  it.barrier(sycl::access::fence_space::local_space);
  if(sub==0){
   const float den=count<=32?part[4]:(count<=64?part[4]+part[5]:(part[4]+part[5])+(part[6]+part[7]));
   float v;
   if(count<=16)v=lv[0];
   else if(count<=32)v=part[8+lane]+part[8+32+lane];
   else if(count<=64)v=(part[8+lane]+part[8+32+lane])+(part[8+64+lane]+part[8+96+lane]);
   else{float t=raw64*fac[64];for(int k=0;k<6;++k)t=t+0.f;v=((part[8+lane]+part[8+32+lane])+(part[8+64+lane]+part[8+96+lane]))+t;}
   v=v/den;
   a.put(5,hh*256+dim,v*gate);
  }
 }));});
}
inline bool combine_blocked_on(){static const bool on=[]{const char* e=std::getenv("OWNRT_ATTN_COMBINE2");return e&&e[0]=='1';}();return on;}
// Tiles, query heads in parallel: one 512-lane work-group (16 subgroups) per (row, KV head, tile), so the 12 query
// heads that read the same 32 K and V rows share every load. Per-head arithmetic is tiles<true,true>'s:
// - scores: subgroup (dq = sub&3, hg = sub>>2), lane = slot, query heads kv*12+hg*3+{0,1,2}, dims 64dq..64dq+63 in
//   natural order through a streaming balanced 64-leaf tree; score = ((Q0+Q1)+(Q2+Q3))/sqrt(256). score<true>()'s
//   8-leaf in-lane tree followed by lane_tree is the balanced 256-leaf tree over the dims in natural order, so this
//   is the same set of products and additions.
// - softmax: subgroup = local head, lane = slot: tile max by first_max (the serial scan's bits), exp and the
//   denominator by lane_tree, exactly as tiles<true,true>.
// - values: lane = (dimension, head half), 6 heads per lane, weight*V leaves in slot order through a balanced 32-leaf
//   tree (binary counter, left + right); weights held in registers (lane = slot) and broadcast.
// Loads that do not depend on the slot count (the row's slot ids, q) are issued before the guard; full tiles run a
// body without per-slot conditionals. Partial layout unchanged. Lab 2026-10-26, n=2051: 184 -> 31 us L2-cold, 178 -> 20
// us hot (bench); 192.8 -> 32.3 us per layer (rank-1 device profile).
inline sycl::event tiles_heads(sycl::queue&q,ng::Shape s,ng::Args a,const int*counts,float*partial,const std::vector<sycl::event>&deps){
 const int C=splits(s);
 return ownrt::prepared_submit(q,[=,p35_range0=sycl::nd_range<1>(size_t(s.tokens)*2*C*512,512)](sycl::handler& handler){
 sycl::local_accessor<float,1>P(4*12*32,handler);sycl::local_accessor<float,1>W(12*32,handler);
 handler.parallel_for(p35_range0,packet26::checked([=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
  const int G=int(it.get_group_linear_id()),c=G%C,kv=(G/C)%2,r=G/(C*2),S=s.budget+3,start=c*32;
  auto sg=it.get_sub_group();const int lane=int(sg.get_local_linear_id()),sub=int(sg.get_group_linear_id());
  const int dq=sub&3,hg=sub>>2,hh=sub>>3,d=(sub&7)*32+lane;
  const float*K=static_cast<const float*>(a.p[2]);const float*V=static_cast<const float*>(a.p[3]);const float*Q=static_cast<const float*>(a.p[0]);
  const int rawid=start+lane<S?a.i(4)[r*S+start+lane]:0;
  float qa[3][2];
  #pragma unroll
  for(int hl=0;hl<3;++hl){const float*qp=Q+(r*24+kv*12+hg*3+hl)*256+64*dq+2*lane;qa[hl][0]=qp[0];qa[hl][1]=qp[1];}
  const int n=counts[r];
  if(n<=0||blocked_wg(it,a))return;
  if(start>=n)return;
  const int valid=sycl::min(32,n-start);
  const int myid=lane<valid?rawid:0;
  auto scores=[&]<bool Full>(){
   float st[3][6];float res[3];
   const float*krow=K+(myid*2+kv)*256+64*dq;
   #pragma unroll
   for(int ch=0;ch<8;++ch){
    sycl::vec<float,8> kk;
    if constexpr(Full)kk.load(0,sycl::address_space_cast<sycl::access::address_space::global_space,sycl::access::decorated::no>(krow+ch*8));
    else{kk=sycl::vec<float,8>(0.f);if(lane<valid)kk.load(0,sycl::address_space_cast<sycl::access::address_space::global_space,sycl::access::decorated::no>(krow+ch*8));}
    #pragma unroll
    for(int e=0;e<8;++e){const int dd=ch*8+e;
     #pragma unroll
     for(int hl=0;hl<3;++hl){const float qd=sycl::select_from_group(sg,qa[hl][dd&1],dd>>1);float cur=kk[e]*qd;
      int k=0;
      #pragma unroll
      for(;k<6;++k){if(((dd>>k)&1)==0)break;cur=st[hl][k]+cur;}
      if(k<6)st[hl][k]=cur;else res[hl]=cur;}}}
   #pragma unroll
   for(int hl=0;hl<3;++hl)P[(dq*12+hg*3+hl)*32+lane]=res[hl];};
  if(valid==32)scores.template operator()<true>();else scores.template operator()<false>();
  it.barrier(sycl::access::fence_space::local_space);
  if(sub<12){
   const int h=kv*12+sub;
   const float x=lane<valid?((P[(0*12+sub)*32+lane]+P[(1*12+sub)*32+lane])+(P[(2*12+sub)*32+lane]+P[(3*12+sub)*32+lane]))/detmath::sqrt(256.f):-INFINITY;
   const float m=first_max(-INFINITY,sg_first_max(sg,x));
   const float w=lane<valid?detmath::exp(x-m):0.f;
   const float den=lane_tree(sg,w);
   float*p=partial+size_t((r*24+h)*C+c)*258;
   if(lane==0){p[256]=m;p[257]=den;}
   W[sub*32+lane]=w;
  }
  it.barrier(sycl::access::fence_space::local_space);
  float wr[6];
  #pragma unroll
  for(int hl=0;hl<6;++hl)wr[hl]=W[(hh*6+hl)*32+lane];
  const float*vcol=V+kv*256+d;
  auto values=[&]<bool Full>(){
   float acc[6][5];float root[6];
   #pragma unroll
   for(int j=0;j<32;++j){
    const int id=sycl::select_from_group(sg,myid,j);
    float vv;
    if constexpr(Full)vv=vcol[id*512];else vv=j<valid?vcol[id*512]:0.f;
    #pragma unroll
    for(int hl=0;hl<6;++hl){const float wj=sycl::select_from_group(sg,wr[hl],j);float leaf;
     if constexpr(Full)leaf=wj*vv;else leaf=j<valid?wj*vv:0.f;
     int k=0;
     #pragma unroll
     for(;k<5;++k){if(((j>>k)&1)==0)break;leaf=acc[hl][k]+leaf;}
     if(k<5)acc[hl][k]=leaf;else root[hl]=leaf;}}
   #pragma unroll
   for(int hl=0;hl<6;++hl)partial[size_t((r*24+kv*12+hh*6+hl)*C+c)*258+d]=root[hl];};
  if(valid==32)values.template operator()<true>();else values.template operator()<false>();
 }));});
}
inline bool tiles_heads_on(){static const bool on=[]{const char* e=std::getenv("OWNRT_ATTN_HEADS");return e&&e[0]=='1';}();return on;}
inline std::vector<sycl::event> candidate(sycl::queue&q,ng::Shape s,ng::Args a,int*counts,float*scratch,bool split){ng::validate(s);std::vector<sycl::event>e{admit(q,s,a,counts)};if(split){e.push_back(tiles<true>(q,s,a,counts,scratch,{e.back()}));e.push_back(combine<true>(q,s,a,counts,scratch,{e.back()}));}else{e.push_back(scores(q,s,a,counts,{e.back()}));e.push_back(softmax(q,s,a,counts,{e.back()}));e.push_back(tiles<false>(q,s,a,counts,scratch,{e.back()}));e.push_back(combine<false>(q,s,a,counts,scratch,{e.back()}));}return e;}
}
