#pragma once
// Bench-only: verbatim copy of the reference select kernels from canonical specialised_submit.cpp.
#include "stage2/packet194-expert-diet-engine/specialised.hpp"
#include <sycl/sycl.hpp>
namespace specialised {
struct Guard {
 int error(ng::Args a)const{return sycl::atomic_ref<int32_t,sycl::memory_order::relaxed,sycl::memory_scope::device,sycl::access::address_space::global_space>(a.i(15)[0]).load();}
 void fail(ng::Args a)const{sycl::atomic_ref<int32_t,sycl::memory_order::relaxed,sycl::memory_scope::device,sycl::access::address_space::global_space>(a.i(15)[0]).store(1);}
};
// QSA select with one 32-lane subgroup per block item (body<select,Stage>'s values; work items -> subgroups).
// Stage 0: the 128-leaf adjacent tree of each head's score with lane l holding leaves 4l..4l+3 (in-lane levels 1-2,
// shuffles for 3-7), heads accumulated in order. Stage 1: the finiteness test and the rank count split across lanes
// and combined with all-of and an integer sum, both independent of order.
template<int Stage,class Guard> inline void select_rows(ng::Shape s,ng::Args a,sycl::nd_item<1> it,float* scratch,Guard guard){
 s.op=ng::select;auto sg=it.get_sub_group();const int lane=int(sg.get_local_linear_id());const size_t index=it.get_global_linear_id()/32;
 if(index>=work_items(s,Stage)||!a.i(18)[0]||guard.error(a))return;
 const int pos=a.i(17)[0];if(pos<0||pos>ng::position_limit(s)-s.tokens){if(index==0&&lane==0)guard.fail(a);return;}
 const int cap=ceildiv(s.capacity,4),L=ceildiv(ng::launch_extent(s),4),S=slots(s),per=Stage==0?std::max(L,S):L;
 const int r=int(index)/per,b=int(index)%per,n=(pos+r+1)/4,count=std::min(n,s.budget/4);
 auto tree32=[&](float x){for(int width=1;width<32;width*=2){const float rhs=sycl::select_from_group(sg,x,(lane+width)%32);if(lane%(2*width)==0)x=x+rhs;}return sycl::group_broadcast(sg,x,0);};
 if constexpr(Stage==0){
  if(b<S&&lane==0)a.i(2)[r*S+b]=-1;
  if(b<n){float score=0.f;
   for(int h=0;h<4;++h){float v[4];
    #pragma unroll
    for(int i=0;i<4;++i){const int k=4*lane+i;v[i]=a.b(0,(r*4+h)*128+k)*a.b(1,b*128+k);}
    const float d=tree32((v[0]+v[1])+(v[2]+v[3]));score=score+std::max(0.f,d);}
   if(lane==0)scratch[r*cap+b]=score/detmath::sqrt(float(128));}
 }else{
  if(b>=n&&b!=0)return;bool finite=true;int rank=0;const float v=b<n?scratch[r*cap+b]:0.f;
  for(int k=lane;k<n;k+=32){const float other=scratch[r*cap+k];finite=finite&&std::isfinite(other);rank+=other>v||(other==v&&k<b);}
  if(!sycl::all_of_group(sg,finite)){if(b==0&&lane==0)guard.fail(a);return;}
  rank=sycl::reduce_over_group(sg,rank,sycl::plus<int>());
  if(lane==0){if(b<n&&rank<count)for(int j=0;j<4;++j)a.i(2)[r*S+rank*4+j]=b*4+j;
   if(b==0)for(int j=0;j<pos+r+1-n*4;++j)a.i(2)[r*S+count*4+j]=n*4+j;}
 }
}
inline bool select_subgroups(){static const bool on=[]{const char* e=std::getenv("OWNRT_SELECT_SG");return !e||e[0]!='0';}();return on;}
// OWNRT_SELECT_TOPK=1: QSA select stage 1 by threshold instead of an all-pairs rank count (O(n) instead of O(n^2) per
// row). One 1024-lane work-group per row. Scores are >= +0 (ReLU sum / sqrt) and finite (checked first, as before), so
// their bit patterns order like their values. The count-th largest bit pattern T is found by binary search; the
// selected set is every block above T plus the lowest-index blocks equal to T, compacted in index order by
// deterministic group scans; each selected block's rank is then counted against the selected set only, with the same
// float comparisons (score greater, or equal with a lower index). Every block that outranks a selected block is itself
// selected, so the ranks, and therefore the written ids, equal the all-pairs version exactly.
// OWNRT_SELECT_TOPK=1, stage 0: one work item per block (and per output slot for the -1 fill), each head's 128-leaf
// adjacent pairwise tree computed in registers: groups of four leaves ((p0+p1)+(p2+p3)) then strides 1..16 over the 32
// group sums, exactly private_tree<128>'s and the subgroup tree's additions in the same order; heads accumulated in
// order with the same ReLU, then the same division by sqrt(128).
template<class Guard> inline void select_scores_item(ng::Shape s,ng::Args a,size_t index,float* scratch,Guard guard){
 s.op=ng::select;if(index>=work_items(s,0)||!a.i(18)[0]||guard.error(a))return;
 const int pos=a.i(17)[0];if(pos<0||pos>ng::position_limit(s)-s.tokens){if(index==0)guard.fail(a);return;}
 const int cap=ceildiv(s.capacity,4),L=ceildiv(ng::launch_extent(s),4),S=slots(s),per=std::max(L,S);
 const int r=int(index)/per,b=int(index)%per,n=(pos+r+1)/4;
 if(b<S)a.i(2)[r*S+b]=-1;
 if(b>=n)return;
 float score=0.f;
 for(int h=0;h<4;++h){float g[32];
  #pragma unroll
  for(int j=0;j<32;++j){const int k=4*j,q=(r*4+h)*128+k,kb=b*128+k;
   const float p0=a.b(0,q)*a.b(1,kb),p1=a.b(0,q+1)*a.b(1,kb+1),p2=a.b(0,q+2)*a.b(1,kb+2),p3=a.b(0,q+3)*a.b(1,kb+3);g[j]=(p0+p1)+(p2+p3);}
  #pragma unroll
  for(int stride=1;stride<32;stride*=2){
   #pragma unroll
   for(int j=0;j<32;j+=2*stride)g[j]=g[j]+g[j+stride];}
  score=score+std::max(0.f,g[0]);}
 scratch[r*cap+b]=score/detmath::sqrt(float(128));
}
inline bool select_topk(){static const bool on=[]{const char* e=std::getenv("OWNRT_SELECT_TOPK");return e&&e[0]=='1';}();return on;}
template<class Guard> inline void select_topk_row(ng::Shape s,ng::Args a,sycl::nd_item<1> it,const float* scratch,int* sel_idx,float* sel_val,int* hist,int* found,Guard guard){
 auto g=it.get_group();const int lid=int(it.get_local_linear_id());const int r=int(g.get_group_linear_id());constexpr int W=1024;
 if(r>=s.tokens)return;
 const bool active=sycl::group_broadcast(g,lid==0?(a.i(18)[0]!=0&&!guard.error(a)):false,0);if(!active)return;
 const int pos=a.i(17)[0];if(pos<0||pos>ng::position_limit(s)-s.tokens){if(r==0&&lid==0)guard.fail(a);return;}
 const int cap=ceildiv(s.capacity,4),S=slots(s),n=(pos+r+1)/4,count=std::min(n,s.budget/4);
 const float* sc=scratch+size_t(r)*cap;
 bool finite=true;for(int k=lid;k<n;k+=W)finite=finite&&std::isfinite(sc[k]);
 if(!sycl::all_of_group(g,finite)){if(lid==0)guard.fail(a);return;}
 if(count>0){
  auto bits=[](float x){return sycl::bit_cast<uint32_t>(x);};
  // T = the count-th largest bit pattern (scores >= +0: bits 30..0 order like values), by a three-pass radix select
  // over digits 30..20, 19..9 and 8..0: histogram the elements that share the prefix found so far, then take the digit
  // where the descending running count reaches the number still wanted. Integer counts only: order-independent.
  uint32_t prefix=0,prefix_mask=0;int remaining=count;
  for(int pass=0;pass<3;++pass){const int shift=pass==0?20:pass==1?9:0,width=pass==2?9:11,bins=1<<width;const uint32_t mask=uint32_t(bins-1);
   for(int i=lid;i<bins;i+=W)hist[i]=0;sycl::group_barrier(g);
   for(int k=lid;k<n;k+=W){const uint32_t b=bits(sc[k]);if((b&prefix_mask)==prefix)
     sycl::atomic_ref<int,sycl::memory_order::relaxed,sycl::memory_scope::work_group,sycl::access::address_space::local_space>(hist[(b>>shift)&mask]).fetch_add(1);}
   sycl::group_barrier(g);
   // Lane l owns bins bins-1-2l and bins-2-2l (descending); an exclusive scan gives the count above them.
   const int hi_bin=bins-1-2*lid,lo_bin=bins-2-2*lid;const int h_hi=hi_bin>=0?hist[hi_bin]:0,h_lo=lo_bin>=0?hist[lo_bin]:0;
   const int above=sycl::exclusive_scan_over_group(g,h_hi+h_lo,sycl::plus<int>());
   if(hi_bin>=0&&above<remaining&&remaining<=above+h_hi){found[0]=hi_bin;found[1]=above;}
   else if(lo_bin>=0&&above+h_hi<remaining&&remaining<=above+h_hi+h_lo){found[0]=lo_bin;found[1]=above+h_hi;}
   sycl::group_barrier(g);
   const int digit=found[0],skipped=found[1];sycl::group_barrier(g);
   remaining-=skipped;prefix|=uint32_t(digit)<<shift;prefix_mask|=mask<<shift;}
  const uint32_t T=prefix;const int need=remaining,greater=count-need;
  // Compaction in index order with two group scans: lane l owns the contiguous indices [l*C, l*C+C).
  const int C=(n+W-1)/W,k0=lid*C,k1=std::min(n,k0+C);int my_ties=0;
  for(int k=k0;k<k1;++k)my_ties+=bits(sc[k])==T;
  int tie_before=sycl::exclusive_scan_over_group(g,my_ties,sycl::plus<int>());int my_sel=0;
  {int t=tie_before;for(int k=k0;k<k1;++k){const uint32_t b=bits(sc[k]);if(b>T)++my_sel;else if(b==T){if(t<need)++my_sel;++t;}}}
  int at=sycl::exclusive_scan_over_group(g,my_sel,sycl::plus<int>());
  {int t=tie_before;for(int k=k0;k<k1;++k){const uint32_t b=bits(sc[k]);bool sel=b>T;if(b==T){sel=t<need;++t;}if(sel){sel_idx[at]=k;sel_val[at]=sc[k];++at;}}}
  const int taken=sycl::reduce_over_group(g,my_sel,sycl::plus<int>());
  sycl::group_barrier(g);
  if(taken!=count){if(lid==0)guard.fail(a);return;} // cannot happen; refuse rather than write a short list
  for(int i=lid;i<count;i+=W){const float v=sel_val[i];const int b=sel_idx[i];int rank=0;
   for(int j=0;j<count;++j){const float other=sel_val[j];rank+=other>v||(other==v&&sel_idx[j]<b);}
   for(int j=0;j<4;++j)a.i(2)[r*S+rank*4+j]=b*4+j;}
 }
 if(lid==0)for(int j=0;j<pos+r+1-n*4;++j)a.i(2)[r*S+count*4+j]=n*4+j;
}
}
