#pragma once
// Grouped routed-expert rows for small chunks (OWNRT_EXPERTS_GROUPED=1, 2026-10-30, research/multirow-verify-2026-10-30;
// default off). A chunk of M token rows has n = 10*M routed slots; the top-10 experts of one token are distinct, but
// consecutive tokens share about 4 of their 10 experts (decode-site census). The one-row decode kernels run one slot per
// row set, so a shared expert's rows are decoded once per slot. Here one subgroup owns the rows of one GROUP: the slots
// (at most S, in slot order) whose valid full route names the same expert. Each weight row value is decoded once, with
// the one-row kernel's own expression, and applied to every member slot; each member keeps its own accumulators, the
// one-row kernel's per-lane order (product, then sum = sum + product) and its own reduction tree, and the outputs and
// status words land where the one-row kernel writes them. Slots whose route is invalid or not full form groups of one
// (they run the one-row arithmetic and write its NaN and status). Bodies are standalone so CPU-device tests run them.
#include <sycl/sycl.hpp>
#include <bit>
#include <cstdint>
#include "stage2/packet2/kernels/math.hpp"
#include "stage2/packet6-kopt/reference.hpp"
#include "stage2/packet194-expert-diet-engine/dn2_kernels.hpp"
namespace xgroup2 {
inline constexpr uint32_t max_slots=64; // two 32-bit slot masks
// Attempt 1 found each subgroup's group with O(n) dependent global route loads per lane (slower than the per-slot
// kernels); attempt 2 built the grouping once per subgroup by shuffles but gave each subgroup every 8th group (too few,
// too long subgroups: also slower). Attempt 3 (this): the grouping by shuffles (Table: each lane holds slots lane,
// lane+W, ...; one route load per slot) and G = the launch's slot count, so each subgroup takes at most one group of its
// row block (subgroups past the group count exit after the table), as many subgroups as the per-slot kernels.
//
// Slot i is "full" when its route is valid with row_begin 0 and row_count rows (every route expert_gather writes). Its
// rank is the number of full slots j < i with the same expert; it leads a group when rank % S == 0, or always when it is
// not full (a group of one). A group's members are the full slots with the leader's expert and rank in [rank, rank+S).
template<unsigned W> inline constexpr unsigned per_lane=(max_slots+W-1)/W;
template<unsigned S,unsigned W> struct Table {uint32_t n=0,lo=0,hi=0;uint32_t key[per_lane<W>]{},rank[per_lane<W>]{};bool full[per_lane<W>]{};};
template<unsigned S,unsigned W,class SG> inline Table<S,W> make_table(SG sg,const iq3::Route* routes,uint32_t n,uint32_t experts,uint32_t rows,uint32_t span){
 constexpr unsigned Q=per_lane<W>;const unsigned lane=unsigned(sg.get_local_linear_id());Table<S,W> t;t.n=n;
 #pragma unroll
 for(unsigned q=0;q<Q;++q){const uint32_t i=q*W+lane;
  if(i<n){const iq3::Route r=routes[i];t.full[q]=iq3::valid_route(r,experts,rows,span)&&r.row_begin==0&&r.row_count==rows;t.key[q]=r.expert_id;}
  else{t.full[q]=false;t.key[q]=0xffffffffu;}}
 #pragma unroll
 for(unsigned qj=0;qj<Q;++qj){
  if(qj*W>=n)break;
  for(unsigned jl=0;jl<W;++jl){const uint32_t j=qj*W+jl;if(j>=n)break;
   const uint32_t kj=sycl::select_from_group(sg,t.key[qj],jl);const bool fj=sycl::select_from_group(sg,uint32_t(t.full[qj]),jl)!=0;
   #pragma unroll
   for(unsigned q=0;q<Q;++q){const uint32_t i=q*W+lane;if(fj&&j<i&&t.full[q]&&kj==t.key[q])++t.rank[q];}}}
 uint32_t lo=0,hi=0;
 #pragma unroll
 for(unsigned q=0;q<Q;++q){const uint32_t i=q*W+lane;const bool lead=i<n&&(!t.full[q]||t.rank[q]%S==0);
  if(lead){if(i<32)lo|=1u<<i;else hi|=1u<<(i-32);}}
 t.lo=sycl::reduce_over_group(sg,lo,sycl::bit_or<uint32_t>());t.hi=sycl::reduce_over_group(sg,hi,sycl::bit_or<uint32_t>());
 return t;
}
template<unsigned S> struct Group {uint32_t count=0;uint32_t slot[S]{};};
// Members of the group led by slot L (uniform in the subgroup), ascending.
template<unsigned S,unsigned W,class SG> inline Group<S> members(SG sg,const Table<S,W>& t,uint32_t L){
 constexpr unsigned Q=per_lane<W>;const unsigned lane=unsigned(sg.get_local_linear_id());
 const unsigned qL=L/W,lL=L%W;uint32_t keyL=0,rankL=0;bool fullL=false;
 #pragma unroll
 for(unsigned q=0;q<Q;++q)if(q==qL){keyL=sycl::select_from_group(sg,t.key[q],lL);rankL=sycl::select_from_group(sg,t.rank[q],lL);fullL=sycl::select_from_group(sg,uint32_t(t.full[q]),lL)!=0;}
 Group<S> g;g.slot[0]=L;g.count=1;if(!fullL)return g;
 uint32_t lo=0,hi=0;
 #pragma unroll
 for(unsigned q=0;q<Q;++q){const uint32_t i=q*W+lane;
  if(i<t.n&&i>L&&t.full[q]&&t.key[q]==keyL&&t.rank[q]>rankL&&t.rank[q]<rankL+S){if(i<32)lo|=1u<<i;else hi|=1u<<(i-32);}}
 lo=sycl::reduce_over_group(sg,lo,sycl::bit_or<uint32_t>());hi=sycl::reduce_over_group(sg,hi,sycl::bit_or<uint32_t>());
 while(lo&&g.count<S){const uint32_t b=uint32_t(std::countr_zero(lo));lo&=lo-1u;g.slot[g.count++]=b;}
 while(hi&&g.count<S){const uint32_t b=uint32_t(std::countr_zero(hi));hi&=hi-1u;g.slot[g.count++]=32u+b;}
 return g;
}
// Calls body(L, ordinal) for the leaders L of groups ordinal % G == g, in slot order (uniform).
template<unsigned S,unsigned W,class F> inline void for_groups(const Table<S,W>& t,uint32_t G,uint32_t g,F&& body){
 uint32_t ord=0;
 for(unsigned half=0;half<2;++half){uint32_t mask=half?t.hi:t.lo;
  while(mask){const uint32_t b=uint32_t(std::countr_zero(mask));mask&=mask-1u;if(ord%G==g)body(half*32u+b);++ord;}}
}
// ---- IQ3_XXS: dn2::xxs_packed<WGSG> per member ---------------------------------------------------------------------
// The same decomposition of a group's rows (four rows per 32-lane subgroup, item t = lane%8 owns logical lanes 4t..4t+3),
// the same grid word, sign code, factor and value per lane (computed once per group), then per member x (vec4), product
// and add, the ((l0+l1)+(l2+l3)) register levels and three shuffle levels; NaN and status as xxs_packed.
template<unsigned WGSG,unsigned S> inline void xxs_grouped(const dn2::XxsView v,uint32_t G,sycl::nd_item<1> it){
 constexpr unsigned SG=32,RPS=SG/8;
 uint32_t* grid=*sycl::ext::oneapi::group_local_memory_for_overwrite<uint32_t[256]>(it.get_group());
 for(unsigned li=unsigned(it.get_local_linear_id());li<256;li+=SG*WGSG)grid[li]=iq3::iq3_grid[li];
 sycl::group_barrier(it.get_group());
 const uint32_t blocks=(v.rows+RPS-1)/RPS,total=blocks*G;
 const auto sg=it.get_sub_group();const unsigned lane=sg.get_local_linear_id(),set=lane/8,t=lane%8;
 const uint32_t logical=uint32_t(it.get_group_linear_id())*WGSG+uint32_t(sg.get_group_linear_id());if(logical>=total)return;
 const uint32_t blk=logical/G,gi=logical%G,row=blk*RPS+set;
 const auto tab=make_table<S,SG>(sg,v.routes,v.count,v.experts,v.rows,v.rows);
 for_groups(tab,G,gi,[&](uint32_t L){
  const Group<S> g=members<S,SG>(sg,tab,L);
  const iq3::Route r=v.routes[L];const bool valid=iq3::valid_route(r,v.experts,v.rows,v.rows);
  const bool live=valid&&row<v.rows&&row<r.row_count;
  const uint8_t* w=live?v.w+(size_t(r.expert_id)*v.rows+r.row_begin+row)*v.row_bytes:v.w;
  float acc[S][4];
  #pragma unroll
  for(unsigned m=0;m<S;++m)
   #pragma unroll
   for(unsigned j=0;j<4;++j)acc[m][j]=0.f;
  if(live){
   const uint32_t nblocks=v.columns/256;const unsigned cshift=7*(t/2),sbase=4*(t%2);
   for(uint32_t block=0;block<nblocks;++block){
    const uint8_t* packed=w+block*98u;const float d=iq3::half(iq3::u16(packed));
    #pragma unroll
    for(unsigned group=0;group<8;++group){
     const auto*half_words=reinterpret_cast<const uint16_t*>(packed+66+4*group);const uint32_t word=uint32_t(half_words[0])|uint32_t(half_words[1])<<16;
     const uint32_t code=(word>>cshift)&127,mask=code|((std::popcount(code)%2)<<7);
     const float scale=(d*(0.5f+float(word>>28)))*0.5f;
     const uint32_t entry=grid[packed[2+group*8+t]];
     float weight[4];
     #pragma unroll
     for(unsigned j=0;j<4;++j){const uint32_t mag=(entry>>(8*j))&255;const int sign=(mask>>(sbase+j))&1?-1:1;weight[j]=(scale*float(mag))*float(sign);}
     #pragma unroll
     for(unsigned m=0;m<S;++m)if(m<g.count){
      const sycl::vec<float,4> xv=*reinterpret_cast<const sycl::vec<float,4>*>(v.x+size_t(g.slot[m])*v.columns+block*256u+group*32u+4u*t);
      #pragma unroll
      for(unsigned j=0;j<4;++j){const float product=weight[j]*xv[j];acc[m][j]=acc[m][j]+product;}
     }
    }
   }
  }
  #pragma unroll
  for(unsigned m=0;m<S;++m)if(m<g.count){
   const float a01=acc[m][0]+acc[m][1],a23=acc[m][2]+acc[m][3];float sum=a01+a23;
   #pragma unroll
   for(unsigned width=1;width<8;width*=2){const float rhs=sycl::select_from_group(sg,sum,(lane+width)%SG);if(t%(2*width)==0)sum=sum+rhs;}
   if(t==0&&row<v.rows)v.y[size_t(g.slot[m])*v.rows+row]=live?sum:iq3::bits_float(0x7fc00000);
   if(lane==0&&blk==0&&v.status)v.status[g.slot[m]]=!valid;
  }
 });
}
// ---- kopt decode8 rows (IQ2_S / IQ3_S): kopt::MultiplyBlockRows<R> per member --------------------------------------
// R consecutive rows of a group per subgroup; lane l owns columns l*8+256*i; per chunk the member inputs are loaded,
// each row's 8 decode8 values decoded once and applied to every member (product, then add); the 32-lane adjacent-pair
// tree per (member, row); NaN for inactive rows; status by the row-0 subgroup, as MultiplyBlockRows.
struct RowsView {const uint8_t* w;const float* x;float* y;const iq3::Route* routes;uint32_t* status;uint32_t rows,k,rb,count,experts,span;};
template<iq3::Type T,unsigned R,unsigned S,unsigned WGSG> inline void rows_grouped(const RowsView d,uint32_t G,sycl::nd_item<1> it){
 constexpr unsigned SG=32;
 auto sg=it.get_sub_group();const unsigned lane=sg.get_local_linear_id();
 const uint32_t blocks=(d.span+R-1)/R,total=blocks*G;
 const uint32_t logical=uint32_t(it.get_group_linear_id())*WGSG+uint32_t(sg.get_group_linear_id());if(logical>=total)return;
 const uint32_t blk=logical/G,gi=logical%G,first=blk*R;
 const auto tab=make_table<S,SG>(sg,d.routes,d.count,d.experts,d.rows,d.span);
 for_groups(tab,G,gi,[&](uint32_t L){
  const Group<S> g=members<S,SG>(sg,tab,L);
  const iq3::Route r=d.routes[L];const bool valid=iq3::valid_route(r,d.experts,d.rows,d.span);
  if(first==0&&lane==0)
   #pragma unroll
   for(unsigned m=0;m<S;++m)if(m<g.count)d.status[g.slot[m]]=valid?0:1;
  float acc[S][R];const uint8_t* rows[R];bool live[R];
  #pragma unroll
  for(unsigned i=0;i<R;++i){
   #pragma unroll
   for(unsigned m=0;m<S;++m)acc[m][i]=0;
   const uint32_t row=first+i;live[i]=valid&&row<d.span&&row<r.row_count;
   rows[i]=live[i]?d.w+(size_t(r.expert_id)*d.rows+r.row_begin+row)*d.rb:d.w;}
  const uint32_t k32=d.k;uint32_t k=lane*8u;
  for(;k+8u<=k32;k+=SG*8u){
   float input[S][8];
   #pragma unroll
   for(unsigned m=0;m<S;++m)if(m<g.count){const float* x=d.x+size_t(g.slot[m])*d.k;
    #pragma unroll
    for(unsigned j=0;j<8;++j)input[m][j]=x[k+j];}
   #pragma unroll
   for(unsigned i=0;i<R;++i){
    if(!live[i])continue;float values[8];iq3::kopt::decode8<T>(rows[i],k,values);
    #pragma unroll
    for(unsigned m=0;m<S;++m)if(m<g.count)
     #pragma unroll
     for(unsigned j=0;j<8;++j){const float product=values[j]*input[m][j];acc[m][i]=acc[m][i]+product;}
   }
  }
  if(k<k32){
   float input[S][8];
   #pragma unroll
   for(unsigned m=0;m<S;++m)if(m<g.count){const float* x=d.x+size_t(g.slot[m])*d.k;for(unsigned j=0;k+j<k32;++j)input[m][j]=x[k+j];}
   #pragma unroll
   for(unsigned i=0;i<R;++i){
    if(!live[i])continue;float values[8];for(uint32_t j=0;k+j<k32;++j)values[j]=iq3::element(T,rows[i],k+j);
    #pragma unroll
    for(unsigned m=0;m<S;++m)if(m<g.count)for(unsigned j=0;k+j<k32;++j){const float product=values[j]*input[m][j];acc[m][i]=acc[m][i]+product;}
   }
  }
  #pragma unroll
  for(unsigned m=0;m<S;++m)if(m<g.count)
   #pragma unroll
   for(unsigned i=0;i<R;++i){
    float sum=acc[m][i];
    for(unsigned width=1;width<SG;width*=2){float rhs=sycl::select_from_group(sg,sum,(lane+width)%SG);if(lane%(2*width)==0)sum=sum+rhs;}
    const uint32_t row=first+i;
    if(lane==0&&row<d.span)d.y[size_t(g.slot[m])*d.span+row]=valid&&row<r.row_count?sum:iq3::bits_float(0x7fc00000);
   }
 });
}
// ---- IQ4_NL: kopt::MultiplyIQ4NLPacked<SG,RI,WGSG,MODE> per member ----------------------------------------------
// Work-item t of a row owns logical lanes 4t..4t+3 (IQ4_NL block 8i+t of each 256-column chunk, read once as 5 words,
// scale converted once); the 32 values of a block are decoded once per group (the same scale*level) and applied per
// member to its 32 inputs in the original (j, jj) order; ((l0+l1)+(l2+l3)) and three shuffle levels per member.
template<unsigned SG,unsigned RI,unsigned WGSG,int MODE,unsigned S> inline void iq4nl_grouped(const RowsView d,uint32_t G,sycl::nd_item<1> it){
 constexpr unsigned SETS=SG/8,RPS=SETS*RI;
 float* glut=nullptr;
 if constexpr(MODE==2){glut=*sycl::ext::oneapi::group_local_memory_for_overwrite<float[16]>(it.get_group());const unsigned li=unsigned(it.get_local_linear_id());if(li<16)glut[li]=float(iq3::iq4_level(li));sycl::group_barrier(it.get_group());}
 auto sg=it.get_sub_group();const unsigned lane=sg.get_local_linear_id(),set=lane/8,t=lane%8;
 const uint32_t blocks=(d.span+RPS-1)/RPS,total=blocks*G;
 const uint32_t logical=uint32_t(it.get_group_linear_id())*WGSG+uint32_t(sg.get_group_linear_id());if(logical>=total)return;
 const uint32_t blk=logical/G,gi=logical%G,first=blk*RPS+set*RI;
 const auto tab=make_table<S,SG>(sg,d.routes,d.count,d.experts,d.rows,d.span);
 for_groups(tab,G,gi,[&](uint32_t L){
  const Group<S> g=members<S,SG>(sg,tab,L);
  const iq3::Route r=d.routes[L];const bool valid=iq3::valid_route(r,d.experts,d.rows,d.span);
  if(first==0&&lane==0)
   #pragma unroll
   for(unsigned m=0;m<S;++m)if(m<g.count)d.status[g.slot[m]]=valid?0:1;
  float acc[S][RI][4];const uint8_t* rp[RI];bool live[RI];
  #pragma unroll
  for(unsigned i=0;i<RI;++i){
   #pragma unroll
   for(unsigned m=0;m<S;++m)
    #pragma unroll
    for(unsigned j=0;j<4;++j)acc[m][i][j]=0;
   const uint32_t row=first+i;live[i]=valid&&row<d.span&&row<r.row_count;
   rp[i]=live[i]?d.w+(size_t(r.expert_id)*d.rows+r.row_begin+row)*d.rb:d.w;}
  const bool odd=t&1;
  for(uint32_t b=t;b*32u<d.k;b+=8u){
   #pragma unroll
   for(unsigned i=0;i<RI;++i){
    if(!live[i])continue;
    const uint32_t* wp=reinterpret_cast<const uint32_t*>(rp[i]+b*18u-(odd?2u:0u));
    const uint32_t w0=wp[0],w1=wp[1],w2=wp[2],w3=wp[3],w4=wp[4];
    const uint32_t sbits=odd?(w0>>16):(w0&0xffffu);
    uint32_t qw[4];
    qw[0]=odd?w1:(w0>>16)|(w1<<16);qw[1]=odd?w2:(w1>>16)|(w2<<16);qw[2]=odd?w3:(w2>>16)|(w3<<16);qw[3]=odd?w4:(w3>>16)|(w4<<16);
    const float scale=iq3::kopt::half_scale(sbits);
    float value[32];
    #pragma unroll
    for(unsigned j=0;j<4;++j)
     #pragma unroll
     for(unsigned jj=0;jj<8;++jj){
      const unsigned bi=(8*j+jj)%16;const uint32_t n=(qw[bi/4]>>(8*(bi%4)+4*(j/2)))&15u;
      float level;
      if constexpr(MODE==2)level=glut[n];else level=float(iq3::iq4_level(n));
      value[8*j+jj]=scale*level;
     }
    #pragma unroll
    for(unsigned m=0;m<S;++m)if(m<g.count){
     const sycl::vec<float,4>* xp=reinterpret_cast<const sycl::vec<float,4>*>(d.x+size_t(g.slot[m])*d.k+b*32u);
     #pragma unroll
     for(unsigned j=0;j<4;++j){
      const auto lo=xp[2*j],hi=xp[2*j+1];const float xs[8]{lo[0],lo[1],lo[2],lo[3],hi[0],hi[1],hi[2],hi[3]};
      #pragma unroll
      for(unsigned jj=0;jj<8;++jj){const float product=value[8*j+jj]*xs[jj];acc[m][i][j]=acc[m][i][j]+product;}
     }
    }
   }
  }
  #pragma unroll
  for(unsigned m=0;m<S;++m)if(m<g.count)
   #pragma unroll
   for(unsigned i=0;i<RI;++i){
    const float a01=acc[m][i][0]+acc[m][i][1],a23=acc[m][i][2]+acc[m][i][3];float sum=a01+a23;
    #pragma unroll
    for(unsigned width=1;width<8;width*=2){float rhs=sycl::select_from_group(sg,sum,(lane+width)%SG);if(t%(2*width)==0)sum=sum+rhs;}
    const uint32_t row=first+i;
    if(t==0&&row<d.span)d.y[size_t(g.slot[m])*d.span+row]=live[i]?sum:iq3::bits_float(0x7fc00000);
   }
 });
}
// Switch: OWNRT_EXPERTS_GROUPED=1 (default off) for routed F32 sites with 11..64 slots.
inline bool enabled(){static const bool on=[]{const char* e=std::getenv("OWNRT_EXPERTS_GROUPED");return e&&e[0]=='1';}();return on;}
inline bool applies(uint32_t count){return enabled()&&count>10&&count<=max_slots;}
}
