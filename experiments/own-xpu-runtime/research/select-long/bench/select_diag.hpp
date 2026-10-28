#pragma once
namespace specialised {
template<int Phase,class Guard> inline void select_topk_row_diag(ng::Shape s,ng::Args a,sycl::nd_item<1> it,const float* scratch,int* sel_idx,float* sel_val,int* hist,int* found,Guard guard){
 auto g=it.get_group();const int lid=int(it.get_local_linear_id());const int r=int(g.get_group_linear_id());constexpr int W=1024;
 if(r>=s.tokens)return;
 const bool active=sycl::group_broadcast(g,lid==0?(a.i(18)[0]!=0&&!guard.error(a)):false,0);if(!active)return;
 const int pos=a.i(17)[0];if(pos<0||pos>ng::position_limit(s)-s.tokens){if(r==0&&lid==0)guard.fail(a);return;}
 const int cap=ceildiv(s.capacity,4),S=slots(s),n=(pos+r+1)/4,count=std::min(n,s.budget/4);
 const float* sc=scratch+size_t(r)*cap;
 bool finite=true;for(int k=lid;k<n;k+=W)finite=finite&&std::isfinite(sc[k]);
 if(!sycl::all_of_group(g,finite)){if(lid==0)guard.fail(a);return;}
 if constexpr(Phase==1)return;
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
   remaining-=skipped;prefix|=uint32_t(digit)<<shift;prefix_mask|=mask<<shift;if constexpr(Phase==2)return;}
  if constexpr(Phase==3)return;
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
  if constexpr(Phase==4)return;
  for(int i=lid;i<count;i+=W){const float v=sel_val[i];const int b=sel_idx[i];int rank=0;
   for(int j=0;j<count;++j){const float other=sel_val[j];rank+=other>v||(other==v&&sel_idx[j]<b);}
   for(int j=0;j<4;++j)a.i(2)[r*S+rank*4+j]=b*4+j;}
 }
 if(lid==0)for(int j=0;j<pos+r+1-n*4;++j)a.i(2)[r*S+count*4+j]=n*4+j;
}
}
