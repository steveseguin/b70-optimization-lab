#include "stage2/packet194-expert-diet-engine/kernel_guard.hpp"
#ifndef OWN_RT_HOST_ONLY
#include "stage2/packet194-expert-diet-engine/prepared_submission.hpp"
#endif
#include "stage2/packet194-expert-diet-engine/specialised_submit.hpp"
#include "stage2/packet194-expert-diet-engine/mock_order.hpp"
#ifndef OWN_RT_HOST_ONLY
#include "stage1/packet3-prep/src/sycl_operation.hpp"
#include "stage2/packet194-expert-diet-engine/select_fast.hpp"
#include "stage2/packet194-expert-diet-engine/experts_v2.hpp"
#endif
namespace specialised {
#ifdef OWN_RT_HOST_ONLY
template<ng::Op Code,int Stage,int FixedWidth=0,int FixedHeads=0> struct Kernel final:integrated::HostOperation {
 ng::Shape shape;explicit Kernel(ng::Shape s):shape(s){}
 void run(std::span<void*const> p)const override{ng::Args a;std::copy_n(p.begin(),19,a.p.begin());a.f32=(shape.flags&ng::f32_activations_flag)!=0;float* scratch=static_cast<float*>(p[19]);packet24::mock_items(work_items(shape,Stage),[&](size_t i){body<Code,Stage,FixedWidth,FixedHeads>(shape,a,i,scratch,HostGuard{});});}
};
#else
struct Guard {
 int error(ng::Args a)const{return sycl::atomic_ref<int32_t,sycl::memory_order::relaxed,sycl::memory_scope::device,sycl::access::address_space::global_space>(a.i(15)[0]).load();}
 void fail(ng::Args a)const{sycl::atomic_ref<int32_t,sycl::memory_order::relaxed,sycl::memory_scope::device,sycl::access::address_space::global_space>(a.i(15)[0]).store(1);}
};
struct CachedGuard {
 int value;
 int error(ng::Args)const{return value;}
 void fail(ng::Args a)const{Guard{}.fail(a);}
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
template<ng::Op Code,int Stage,int FixedWidth=0,int FixedHeads=0> struct Kernel final:ownrt::SyclOperation {
 ng::Shape shape;explicit Kernel(ng::Shape s):shape(s){}
 sycl::event submit(sycl::queue& q,std::span<void*const> p,const std::vector<sycl::event>& deps)const override {
  ng::Args a;std::copy_n(p.begin(),19,a.p.begin());float* scratch=static_cast<float*>(p[19]);auto s=shape;a.f32=(s.flags&ng::f32_activations_flag)!=0;auto n=work_items(s,Stage);
  // Lab 2026-10-26 (default off, exact): OWNRT_SELECT_FAST=1 with OWNRT_SELECT_TOPK=1, select_fast.hpp.
  if constexpr(Code==ng::select&&Stage==0)if(select_topk()&&select_fast()){
   auto launch=[&]<int B>(){const size_t sub=size_t(s.tokens)*select_groups<B>(s);
    return ownrt::prepared_submit(q,[=,p35_range0=sycl::nd_range<1>((sub*32+255)/256*256,256)](sycl::handler& h){h.parallel_for(p35_range0,packet26::checked([=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{select_scores_sg<B>(s,a,it,scratch,Guard{});}));});};
   return select_bps4(s)?launch.template operator()<4>():launch.template operator()<8>();}
  if constexpr(Code==ng::select&&Stage==1)if(select_topk()&&select_fast()&&select_topk_row2_ok(s))
   return ownrt::prepared_submit(q,[=,p35_range0=sycl::nd_range<1>(sycl::range<1>(size_t(s.tokens)*1024),sycl::range<1>(1024))](sycl::handler& h){
    sycl::local_accessor<int,1> idx(sycl::range<1>(size_t(s.budget/4)),h);sycl::local_accessor<float,1> val(sycl::range<1>(size_t(s.budget/4)),h);
    sycl::local_accessor<int,1> hist(sycl::range<1>(select_hist_ints),h);sycl::local_accessor<int,1> found(sycl::range<1>(select_found_ints),h);sycl::local_accessor<int,1> part(sycl::range<1>(1024),h);
    h.parallel_for(p35_range0,packet26::checked([=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{select_topk_row2(s,a,it,scratch,idx.get_multi_ptr<sycl::access::decorated::no>().get(),val.get_multi_ptr<sycl::access::decorated::no>().get(),hist.get_multi_ptr<sycl::access::decorated::no>().get(),found.get_multi_ptr<sycl::access::decorated::no>().get(),part.get_multi_ptr<sycl::access::decorated::no>().get(),Guard{});}));});
  if constexpr(Code==ng::select&&Stage==0)if(select_topk())
   return ownrt::prepared_submit(q,[=,p35_range0=sycl::range<1>(n)](sycl::handler& h){h.parallel_for(p35_range0,packet26::checked([=](sycl::id<1> i){select_scores_item(s,a,i[0],scratch,Guard{});}));});
  if constexpr(Code==ng::select&&Stage==1)if(select_topk())
   return ownrt::prepared_submit(q,[=,p35_range0=sycl::nd_range<1>(sycl::range<1>(size_t(s.tokens)*1024),sycl::range<1>(1024))](sycl::handler& h){
    sycl::local_accessor<int,1> idx(sycl::range<1>(size_t(s.budget/4)),h);sycl::local_accessor<float,1> val(sycl::range<1>(size_t(s.budget/4)),h);
    sycl::local_accessor<int,1> hist(sycl::range<1>(2048),h);sycl::local_accessor<int,1> found(sycl::range<1>(2),h);
    h.parallel_for(p35_range0,packet26::checked([=](sycl::nd_item<1> it){select_topk_row(s,a,it,scratch,idx.get_multi_ptr<sycl::access::decorated::no>().get(),val.get_multi_ptr<sycl::access::decorated::no>().get(),hist.get_multi_ptr<sycl::access::decorated::no>().get(),found.get_multi_ptr<sycl::access::decorated::no>().get(),Guard{});}));});
  if constexpr(Code==ng::select)if(select_subgroups())
   return ownrt::prepared_submit(q,[=,p35_range0=sycl::nd_range<1>(sycl::range<1>(n*32),sycl::range<1>(32))](sycl::handler& h){h.parallel_for(p35_range0,packet26::checked([=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{select_rows<Stage>(s,a,it,scratch,Guard{});}));});
  if(experts_v2::enabled("guard"))
   // The error flag read once per 32-lane subgroup (broadcast) instead of by every item: CachedGuard returns that value
   // (fail() still stores to the flag). Items past n return in body's own index check.
   return ownrt::prepared_submit(q,[=,p35_range0=sycl::nd_range<1>((n+127)/128*128,128)](sycl::handler& h){h.parallel_for(p35_range0,packet26::checked([=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{
    auto sg=it.get_sub_group();const int err=sycl::group_broadcast(sg,sg.get_local_linear_id()==0?Guard{}.error(a):0,0);
    body<Code,Stage,FixedWidth,FixedHeads>(s,a,it.get_global_linear_id(),scratch,CachedGuard{err});}));});
  return ownrt::prepared_submit(q,[=,p35_range0=sycl::range<1>(n)](sycl::handler& h){h.parallel_for(p35_range0,packet26::checked([=](sycl::id<1> i){body<Code,Stage,FixedWidth,FixedHeads>(s,a,i[0],scratch,Guard{});}));});
 }
};
#endif
template<ng::Op Code,int FixedWidth=0,int FixedHeads=0> integrated::Launch submit_class(ownrt::Device& d,ng::Shape s,std::span<const ownrt::Allocation> a,std::span<const ownrt::Event> deps){
 integrated::Launch result{};
 auto issue=[&]<int Stage>(){Kernel<Code,Stage,FixedWidth,FixedHeads> op(s);std::array<ownrt::Event,1> after{result.last};auto e=d.compute(op,a,result.last?std::span<const ownrt::Event>(after):deps);if(!result.first)result.first=e;result.last=e;++result.passes;};
 issue.template operator()<0>();if constexpr(Code!=ng::attention_score)issue.template operator()<1>();if constexpr(Code==ng::attention_softmax||Code==ng::route_gather)issue.template operator()<2>();if constexpr(Code==ng::route_gather){issue.template operator()<3>();issue.template operator()<4>();}return result;
}
integrated::Launch submit(ownrt::Device& d,ng::Shape s,std::span<const ownrt::Allocation> a,ownrt::Allocation scratch,std::span<const ownrt::Event> deps){
 ng::validate(s);if(a.size()!=19)throw std::invalid_argument("specialised requires 19 bindings");
 if(d.arena.row(scratch).bytes<scratch_floats(s)*sizeof(float))throw std::invalid_argument("specialised scratch extent");
 std::array<ownrt::Allocation,20> bound{};std::copy(a.begin(),a.end(),bound.begin());bound[19]=scratch;
 if(s.width==2560&&s.heads==4){
  if(s.op==ng::norm)return submit_class<ng::norm,2560,4>(d,s,bound,deps);
  if(s.op==ng::combine_norm)return submit_class<ng::combine_norm,2560,4>(d,s,bound,deps);
 }
 if(s.op==ng::route_gather&&s.width==512&&s.extra==10)return submit_class<ng::route_gather,512>(d,s,bound,deps);
 switch(s.op){
 case ng::route_gather:return submit_class<ng::route_gather>(d,s,bound,deps);
 case ng::norm:return submit_class<ng::norm>(d,s,bound,deps);
 case ng::combine_norm:return submit_class<ng::combine_norm>(d,s,bound,deps);
 case ng::gated_norm:return submit_class<ng::gated_norm>(d,s,bound,deps);
 case ng::gdn:return submit_class<ng::gdn>(d,s,bound,deps);
 case ng::prepare:return submit_class<ng::prepare>(d,s,bound,deps);
 case ng::pool:return submit_class<ng::pool>(d,s,bound,deps);
 case ng::select:return submit_class<ng::select>(d,s,bound,deps);
 case ng::attention_score:return submit_class<ng::attention_score>(d,s,bound,deps);
 case ng::attention_softmax:return submit_class<ng::attention_softmax>(d,s,bound,deps);
 case ng::attention_value:return submit_class<ng::attention_value>(d,s,bound,deps);
 default:throw std::invalid_argument("unsupported specialised class");}
}
}
