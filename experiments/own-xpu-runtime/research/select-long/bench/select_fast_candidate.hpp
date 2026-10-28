#include "stage2/packet194-expert-diet-engine/kernel_guard.hpp"
#pragma once
// QSA select, lab 2026-10-26 (OWNRT_SELECT_FAST=1 with OWNRT_SELECT_TOPK=1; default off). Same values and ids as
// select_scores_item + select_topk_row (specialised_submit.cpp); only the mapping of work to lanes changes.
#include "stage2/packet194-expert-diet-engine/specialised.hpp"
#include <sycl/sycl.hpp>
#ifndef SELECT_NH0
#define SELECT_NH0 4
#endif
namespace specialised {
// Stage 0: one 32-lane subgroup per BPS consecutive blocks of a row. Lane l loads keys 4l..4l+3 of each block (the
// subgroup reads the block's 512-byte key row in one coalesced access) and forms select_scores_item's group sum
// ((p0+p1)+(p2+p3)), p = q*key, for each head. The 32 group sums of a (block, head) are then reduced by the same
// balanced tree (node = lower lane block + upper lane block, strides 1..16) with a transposing butterfly: at the
// first log2(BPS) levels lanes l and l^z exchange the half of their pending blocks the other keeps, at the remaining
// levels both hold the same block and add (lower + upper). Lane l ends with block b0+(l&(BPS-1)): ReLU sum over heads
// in order from 0.f, divided by sqrt(128), exactly select_scores_item's expression. Subgroup gi of a row also writes
// the -1 fill for slots 32gi..32gi+31 (< S), select_scores_item's other duty. The guard is read once per subgroup.
// BPS 4 for extents up to 8192 positions (more subgroups for few blocks), 8 above: measured on the bench.
inline bool select_bps4(ng::Shape s){return ng::launch_extent(s)<=8192;}
template<int BPS> inline int select_groups(ng::Shape s){return std::max(ceildiv(ceildiv(ng::launch_extent(s),4),BPS),ceildiv(slots(s),32));}
template<int BPS,class Guard> inline void select_scores_sg(ng::Shape s,ng::Args a,sycl::nd_item<1> it,float* scratch,Guard guard){
 static_assert(BPS==4||BPS==8||BPS==16||BPS==32);
 constexpr int LB=BPS==4?2:BPS==8?3:BPS==16?4:5;
 s.op=ng::select;auto sg=it.get_sub_group();const int lane=int(sg.get_local_linear_id());const int gsub=int(it.get_global_linear_id()/32);
 if(sycl::group_broadcast(sg,lane==0?int(!a.i(18)[0]||guard.error(a)):0,0)!=0)return;
 const int pos=a.i(17)[0];if(pos<0||pos>ng::position_limit(s)-s.tokens){if(gsub==0&&lane==0)guard.fail(a);return;}
 const int cap=ceildiv(s.capacity,4),S=slots(s),NG=select_groups<BPS>(s);
 const int r=gsub/NG,gi=gsub%NG;if(r>=s.tokens)return;
 const int n=(pos+r+1)/4;
 {const int slot=gi*32+lane;if(slot<S)a.i(2)[r*S+slot]=-1;}
 const int b0=gi*BPS;if(b0>=n)return;
 float qv[4][4];
 #pragma unroll
 for(int h=0;h<4;++h){
  #pragma unroll
  for(int i=0;i<4;++i)qv[h][i]=a.b(0,(r*4+h)*128+4*lane+i);}
 float st[4][LB];float dres[4];
 #pragma unroll
 for(int j=0;j<BPS;++j){
  const int b=b0+j;float g[4];
  if(b<n){float kk[4];
   #pragma unroll
   for(int i=0;i<4;++i)kk[i]=a.b(1,b*128+4*lane+i);
   #pragma unroll
   for(int h=0;h<4;++h){const float p0=qv[h][0]*kk[0],p1=qv[h][1]*kk[1],p2=qv[h][2]*kk[2],p3=qv[h][3]*kk[3];g[h]=(p0+p1)+(p2+p3);}}
  else{
   #pragma unroll
   for(int h=0;h<4;++h)g[h]=0.f;}
  #pragma unroll
  for(int h=0;h<4;++h){float cur=g[h];int k=0;
   #pragma unroll
   for(;k<LB;++k){if(((j>>k)&1)==0)break;const bool hi_lane=((lane>>k)&1)!=0;const float lo=st[h][k],hi=cur;
    const float send=hi_lane?lo:hi,mine=hi_lane?hi:lo;const float recv=sycl::permute_group_by_xor(sg,send,1<<k);cur=hi_lane?recv+mine:mine+recv;}
   if(k<LB)st[h][k]=cur;else dres[h]=cur;}
 }
 #pragma unroll
 for(int h=0;h<4;++h){
  #pragma unroll
  for(int k=LB;k<5;++k){const float o=sycl::permute_group_by_xor(sg,dres[h],1<<k);dres[h]=((lane>>k)&1)?o+dres[h]:dres[h]+o;}}
 const int b=b0+(lane&(BPS-1));
 if(lane<BPS&&b<n){float score=0.f;
  #pragma unroll
  for(int h=0;h<4;++h)score=score+std::max(0.f,dres[h]);
  scratch[r*cap+b]=score/detmath::sqrt(float(128));}
}
// Stage 1: select_topk_row's algorithm and results with the row's scores held in registers (lane l owns the
// contiguous blocks [l*C, l*C+C), C = ceil(n/1024) <= 16, the ownership the compaction already used) and the final
// rank count spread over all 1024 lanes: lane L counts element i = L&511 against half (L>>9) of the selected set,
// 32 others per local-memory load (broadcast across the subgroup), with select_topk_row's comparisons (score greater,
// or equal with a lower block index). Ranks are integer sums of the same terms: order-independent, so identical.
// Requires ceil(cap/1024) <= 16 and budget/4 <= 512 (checked on the host; otherwise select_topk_row runs).
// Local memory of select_topk_row2 (one definition for every launch): histograms of the three passes (pass 0 in
// SELECT_NH0 copies) and the found slots (digit and skipped count per pass, then the taken count).
inline constexpr int select_hist_ints=SELECT_NH0*2048+2048+512,select_found_ints=8;
inline bool select_topk_row2_ok(ng::Shape s){return ceildiv(ceildiv(s.capacity,4),1024)<=16&&s.budget/4<=512;}
template<int CM,class Guard> inline void select_topk_row_cached(ng::Shape s,ng::Args a,sycl::nd_item<1> it,const float* scratch,int* sel_idx,float* sel_val,int* hist,int* found,int* part,Guard guard){ // hist: select_hist_ints, found: select_found_ints
 auto g=it.get_group();const int lid=int(it.get_local_linear_id());const int r=int(g.get_group_linear_id());constexpr int W=1024;static_assert(CM==16||CM==32||CM==64);
 if(r>=s.tokens)return;
 const bool active=sycl::group_broadcast(g,lid==0?(a.i(18)[0]!=0&&!guard.error(a)):false,0);if(!active)return;
 const int pos=a.i(17)[0];if(pos<0||pos>ng::position_limit(s)-s.tokens){if(r==0&&lid==0)guard.fail(a);return;}
 const int cap=ceildiv(s.capacity,4),S=slots(s),n=(pos+r+1)/4,count=std::min(n,s.budget/4);
 const float* sc=scratch+size_t(r)*cap;
 auto bits=[](float x){return sycl::bit_cast<uint32_t>(x);};
 const int C=(n+W-1)/W,k0=lid*C;
 if(C>CM){if(lid==0)guard.fail(a);return;} // uniform row refusal, never truncate scores
 uint32_t v[CM];bool finite=true;
 #pragma unroll
 for(int c=0;c<CM;++c){v[c]=0;const int k=k0+c;if(c<C&&k<n){const float x=sc[k];finite=finite&&std::isfinite(x);v[c]=bits(x);}}
 if(!sycl::all_of_group(g,finite)){if(lid==0)guard.fail(a);return;}
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
   remaining-=skipped;prefix|=uint32_t(digit)<<shift;prefix_mask|=mask<<shift;}
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
  sycl::group_barrier(g);
  if(lid<count){const int rank=part[lid]+part[lid+512];
   for(int j=0;j<4;++j)a.i(2)[r*S+rank*4+j]=bi*4+j;}
 }
 if(lid==0)for(int j=0;j<pos+r+1-n*4;++j)a.i(2)[r*S+count*4+j]=n*4+j;
}
// Preserve the existing CM16 entry point and its default dispatch unchanged.
template<class Guard> inline void select_topk_row2(ng::Shape s,ng::Args a,sycl::nd_item<1> it,const float* scratch,int* sel_idx,float* sel_val,int* hist,int* found,int* part,Guard guard){
 select_topk_row_cached<16>(s,a,it,scratch,sel_idx,sel_val,hist,found,part,guard);
}
// Opt-in long-context intake: only integer selection/cache placement changes.
// Use actual admitted launch extent to choose register capacity; the device
// refuses C>CM before any cached-score access. Scratch strides stay capacity.
inline bool select_long(){static const bool on=[]{const char* e=std::getenv("OWNRT_SELECT_LONG");return e&&e[0]=='1';}();return on;}
inline bool select_topk_long_ok(ng::Shape s){return ceildiv(ceildiv(s.capacity,4),1024)<=64&&s.budget/4<=512;}
inline int select_topk_cache(ng::Shape s){const int c=ceildiv(ceildiv(ng::launch_extent(s),4),1024);return c<=16?16:c<=32?32:64;}
inline bool select_fast(){static const bool on=[]{const char* e=std::getenv("OWNRT_SELECT_FAST");return e&&e[0]=='1';}();return on;}
}
