#pragma once
namespace specialised {
template<int Phase,class Guard> inline void select_topk_row2_diag(ng::Shape s,ng::Args a,sycl::nd_item<1> it,const float* scratch,int* sel_idx,float* sel_val,int* hist,int* found,int* part,Guard guard){ // hist: select_hist_ints, found: select_found_ints
 auto g=it.get_group();const int lid=int(it.get_local_linear_id());const int r=int(g.get_group_linear_id());constexpr int W=1024,CM=16;
 if(r>=s.tokens)return;
 const bool active=sycl::group_broadcast(g,lid==0?(a.i(18)[0]!=0&&!guard.error(a)):false,0);if(!active)return;
 const int pos=a.i(17)[0];if(pos<0||pos>ng::position_limit(s)-s.tokens){if(r==0&&lid==0)guard.fail(a);return;}
 const int cap=ceildiv(s.capacity,4),S=slots(s),n=(pos+r+1)/4,count=std::min(n,s.budget/4);
 const float* sc=scratch+size_t(r)*cap;
 auto bits=[](float x){return sycl::bit_cast<uint32_t>(x);};
 const int C=(n+W-1)/W,k0=lid*C;
 uint32_t v[CM];bool finite=true;
 #pragma unroll
 for(int c=0;c<CM;++c){v[c]=0;const int k=k0+c;if(c<C&&k<n){const float x=sc[k];finite=finite&&std::isfinite(x);v[c]=bits(x);}}
 if(!sycl::all_of_group(g,finite)){if(lid==0)guard.fail(a);return;}
 if constexpr(Phase==1)return;
 if(count>0){
  // Three radix passes (digits 30..20, 19..9, 8..0) as select_topk_row, each with its own histogram (cleared once,
  // up front) and its own found slot, so a pass needs two barriers instead of four. Integer counts only.
  // Pass 0 (where scores share a few exponents) counts into NH0 histogram copies chosen by subgroup, summed per bin
  // below, to spread same-address local atomics; passes 1-2 use one copy.
  constexpr int NH0=SELECT_NH0;const int sgid=lid/32;
  for(int i=lid;i<select_hist_ints;i+=W)hist[i]=0;
  sycl::group_barrier(g);
  uint32_t prefix=0,prefix_mask=0;int remaining=count;
  for(int pass=0;pass<3;++pass){const int shift=pass==0?20:pass==1?9:0,width=pass==2?9:11,bins=1<<width;const uint32_t mask=uint32_t(bins-1);
   int* hp=hist+(pass==0?0:pass==1?NH0*2048:NH0*2048+2048);
   int* hw=hp+(pass==0?(sgid%NH0)*2048:0);
   #pragma unroll
   for(int c=0;c<CM;++c){const int k=k0+c;const uint32_t b=v[c];if(c<C&&k<n&&(b&prefix_mask)==prefix)
     sycl::atomic_ref<int,sycl::memory_order::relaxed,sycl::memory_scope::work_group,sycl::access::address_space::local_space>(hw[(b>>shift)&mask]).fetch_add(1);}
   sycl::group_barrier(g);
   const int hi_bin=bins-1-2*lid,lo_bin=bins-2-2*lid;int h_hi=0,h_lo=0;
   const int copies=pass==0?NH0:1;
   for(int cp=0;cp<copies;++cp){if(hi_bin>=0)h_hi+=hp[cp*2048+hi_bin];if(lo_bin>=0)h_lo+=hp[cp*2048+lo_bin];}
   const int above=sycl::exclusive_scan_over_group(g,h_hi+h_lo,sycl::plus<int>());
   if(hi_bin>=0&&above<remaining&&remaining<=above+h_hi){found[2*pass]=hi_bin;found[2*pass+1]=above;}
   else if(lo_bin>=0&&above+h_hi<remaining&&remaining<=above+h_hi+h_lo){found[2*pass]=lo_bin;found[2*pass+1]=above+h_hi;}
   sycl::group_barrier(g);
   const int digit=found[2*pass],skipped=found[2*pass+1];
   remaining-=skipped;prefix|=uint32_t(digit)<<shift;prefix_mask|=mask<<shift;if constexpr(Phase==2)return;}
  if constexpr(Phase==3)return;
  const uint32_t T=prefix;const int need=remaining;
  // Compaction in index order with one packed scan: lane l owns [l*C, l*C+C); gt = its elements above T, ties = its
  // elements equal to T. Selected before lane l = (gt before l) + min(ties before l, need), and inside the lane the
  // ties are taken while the running tie count is below need: select_topk_row's two scans, same positions.
  int my_gt=0,my_ties=0;
  #pragma unroll
  for(int c=0;c<CM;++c){const int k=k0+c;if(c<C&&k<n){my_gt+=v[c]>T;my_ties+=v[c]==T;}}
  const int packed=sycl::exclusive_scan_over_group(g,(my_gt<<16)|my_ties,sycl::plus<int>());
  const int tie_before=packed&0xffff;int at=(packed>>16)+sycl::min(tie_before,need);int my_sel=0;
  {int t=tie_before;
   #pragma unroll
   for(int c=0;c<CM;++c){const int k=k0+c;if(c<C&&k<n){const uint32_t b=v[c];bool sel=b>T;if(b==T){sel=t<need;++t;}if(sel){if(at<count){sel_idx[at]=k;sel_val[at]=sycl::bit_cast<float>(b);}++at;++my_sel;}}}}
  if(lid==W-1)found[6]=at; // at = selected count through the last lane (the incumbent's reduce of my_sel)
  sycl::group_barrier(g);
  const int taken=found[6];
  if(taken!=count){if(lid==0)guard.fail(a);return;} // cannot happen; refuse rather than write a short list
  if constexpr(Phase==4)return;
  // Rank among the selected set. Selected scores are finite and >= +0, never -0 (0.f plus ReLU terms, std::max(0.f,d)
  // returns +0 for d = -0 or NaN, divided by a positive constant), so for them a > b <=> bits(a) > bits(b) and
  // a == b <=> bits(a) == bits(b); positions in the compacted set increase with block index. select_topk_row's
  // "other > v || (other == v && index < mine)" is therefore key_j >= key_i + (j >= i ? 1 : 0) (j == i never counts).
  // Lane L counts element i = L&511 against half L>>9 of the set, 32 keys per local-memory load, broadcast.
  auto sg=it.get_sub_group();const int lane=int(sg.get_local_linear_id());
  const int i=lid&511,half=lid>>9,base=i&~31;
  uint32_t ki=0;int bi=0;if(i<count){ki=sycl::bit_cast<uint32_t>(sel_val[i]);bi=sel_idx[i];}
  int cnt=0;const int jb0=half*256,je=sycl::min(count,jb0+256);
  for(int jb=jb0;jb<je;jb+=32){
   const int jj=jb+lane;const uint32_t kj=jj<je?sycl::bit_cast<uint32_t>(sel_val[jj]):0u;
   if(jb+32<=je&&jb!=base){const uint32_t thr=jb<base?ki:ki+1u;
    #pragma unroll
    for(int t=0;t<32;++t)cnt+=sycl::select_from_group(sg,kj,t)>=thr;}
   else{
    #pragma unroll
    for(int t=0;t<32;++t)if(jb+t<je)cnt+=sycl::select_from_group(sg,kj,t)>=ki+uint32_t(jb+t>=i);}}
  part[lid]=cnt;
  if constexpr(Phase==5)return;
  sycl::group_barrier(g);
  if(lid<count){const int rank=part[lid]+part[lid+512];
   for(int j=0;j<4;++j)a.i(2)[r*S+rank*4+j]=bi*4+j;}
 }
 if(lid==0)for(int j=0;j<pos+r+1-n*4;++j)a.i(2)[r*S+count*4+j]=n*4+j;
}
}
