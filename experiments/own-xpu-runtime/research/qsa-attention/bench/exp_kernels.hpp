#pragma once
#include <sycl/ext/oneapi/experimental/prefetch.hpp>
namespace labx {
using namespace p47;
namespace sx=sycl::ext::oneapi::experimental;
template<class T>inline auto gp(T* p){return sycl::address_space_cast<sycl::access::address_space::global_space,sycl::access::decorated::no>(p);}
// Mode 0: global loads (tiles_heads). Mode 1: + L1 prefetch of the whole K/V tile at start. Mode 2: K and V tile staged in SLM.
// Mode 3: K staged in SLM, V by global loads after an L1 prefetch issued at start.
template<int Mode>inline sycl::event tiles_heads_x(sycl::queue&q,ng::Shape s,ng::Args a,const int*counts,float*partial){
 const int C=splits(s);
 return q.submit([&](sycl::handler& handler){
 constexpr int KS=(Mode==2||Mode==3)?32*256:1,VS=Mode==2?32*256:1;
 sycl::local_accessor<float,1>Ks(KS,handler);sycl::local_accessor<float,1>Vs(VS,handler);
 handler.parallel_for(sycl::nd_range<1>(size_t(s.tokens)*2*C*384,384),[=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
  const int G=int(it.get_group_linear_id()),c=G%C,kv=(G/C)%2,r=G/(C*2),n=counts[r],S=s.budget+3;
  if(n<=0||(Mode==2||Mode==3?blocked_wg(it,a):blocked_sg(it.get_sub_group(),a)))return;
  const int start=c*32;if(start>=n)return;
  auto sg=it.get_sub_group();const int lane=int(sg.get_local_linear_id()),t=int(it.get_local_linear_id())/32,h=kv*12+t;
  const int valid=sycl::min(32,n-start);
  const int myid=lane<valid?a.i(4)[r*S+start+lane]:0;
  const float*K=static_cast<const float*>(a.p[2]);const float*V=static_cast<const float*>(a.p[3]);
  if constexpr(Mode==1||Mode==3){
   #pragma unroll
   for(int u=0;u<6;++u){const int row=t+12*u;if(row<64){const int j=row&31;const int id=sycl::select_from_group(sg,myid,j);
    if((Mode==1||row>=32)&&j<valid)sx::prefetch((void*)((row<32?K:V)+(id*2+kv)*256+lane*8),32,sx::properties{sx::prefetch_hint_L1});}}
  }
  if constexpr(Mode==2||Mode==3){
   sycl::vec<float,8> buf[6];
   #pragma unroll
   for(int u=0;u<6;++u){const int row=t+12*u;const int j=row&31;const int id=sycl::select_from_group(sg,myid,j);buf[u]=sycl::vec<float,8>(0.f);
    if(row<(Mode==2?64:32)&&j<valid)buf[u].load(0,gp((row<32?K:V)+(id*2+kv)*256+lane*8));}
   #pragma unroll
   for(int u=0;u<6;++u){const int row=t+12*u;const int j=row&31;if(row<(Mode==2?64:32)&&j<valid){
    if(row<32)buf[u].store(0,Ks.template get_multi_ptr<sycl::access::decorated::no>()+j*256+lane*8);
    else if constexpr(Mode==2)buf[u].store(0,Vs.template get_multi_ptr<sycl::access::decorated::no>()+j*256+lane*8);}}
   it.barrier(sycl::access::fence_space::local_space);
  }
  sycl::vec<float,8> qv;qv.load(0,gp(static_cast<const float*>(a.p[0])+(r*24+h)*256+lane*8));
  float st[5];float score=0.f;
  #pragma unroll
  for(int j=0;j<(Mode==11?0:32);++j){
   const int id=sycl::select_from_group(sg,myid,j);
   float cur=0.f;
   if(j<valid){sycl::vec<float,8>k;
    if constexpr(Mode==2||Mode==3)k.load(0,Ks.template get_multi_ptr<sycl::access::decorated::no>()+j*256+lane*8);else k.load(0,gp(K+(id*2+kv)*256+lane*8));
    float v[8];for(int e=0;e<8;++e)v[e]=k[e]*qv[e];for(int z=1;z<8;z*=2)for(int e=0;e<8;e+=2*z)v[e]=v[e]+v[e+z];cur=v[0];}
   if constexpr(Mode==12){score=score+cur;continue;}
   int lv=0;
   #pragma unroll
   for(int k=0;k<5;++k){if(((j>>k)&1)==0)break;const bool b=((lane>>k)&1)!=0;const float lo=st[k],hi=cur;
    const float send=b?lo:hi,mine=b?hi:lo;const float recv=sycl::permute_group_by_xor(sg,send,1<<k);cur=b?recv+mine:mine+recv;lv=k+1;}
   if(lv<5)st[lv]=cur;else score=cur;
  }
  const float x=lane<valid?score/detmath::sqrt(256.f):-INFINITY;
  const float m=first_max(-INFINITY,sg_first_max(sg,x));
  const float w=lane<valid?detmath::exp(x-m):0.f;
  const float den=lane_tree(sg,w);
  float*p=partial+size_t((r*24+h)*C+c)*258;
  if(lane==0){p[256]=m;p[257]=den;}
  float acc[5][8];float root[8];
  if constexpr(Mode==10){for(int e=0;e<8;++e)p[lane*8+e]=0.f;return;}
  #pragma unroll
  for(int j=0;j<32;++j){
   const int id=sycl::select_from_group(sg,myid,j);const float wj=sycl::select_from_group(sg,w,j);
   float leaf[8];
   if(j<valid){sycl::vec<float,8>v;
    if constexpr(Mode==2)v.load(0,Vs.template get_multi_ptr<sycl::access::decorated::no>()+j*256+lane*8);else v.load(0,gp(V+(id*2+kv)*256+lane*8));
    for(int e=0;e<8;++e)leaf[e]=wj*v[e];}
   else for(int e=0;e<8;++e)leaf[e]=0.f;
   int lv=0;
   #pragma unroll
   for(int k=0;k<5;++k){if(((j>>k)&1)==0)break;for(int e=0;e<8;++e)leaf[e]=acc[k][e]+leaf[e];lv=k+1;}
   if(lv<5){for(int e=0;e<8;++e)acc[lv][e]=leaf[e];}else{for(int e=0;e<8;++e)root[e]=leaf[e];}
  }
  for(int e=0;e<8;++e)p[lane*8+e]=root[e];
 });});
}
// combine_blocked with the raw partial values and the gate sigmoid issued before phase A (all reads in-bounds:
// tiles c < C of this head always exist; values of tiles >= count are never used).
inline sycl::event combine_blocked_early(sycl::queue&q,ng::Shape s,ng::Args a,const int*counts,const float*partial){
 const int C=splits(s);
 return q.submit([&](sycl::handler& handler){
 sycl::local_accessor<float,1>fac(128,handler);sycl::local_accessor<float,1>part(8+4*32,handler);
 handler.parallel_for(sycl::nd_range<1>(size_t(s.tokens)*24*8*128,128),[=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
  const int g=int(it.get_group_linear_id()),blk=g%8,hh=g/8,r=hh/24,lid=int(it.get_local_linear_id());
  auto sg=it.get_sub_group();const int lane=int(sg.get_local_linear_id()),sub=lid/32;
  const float*p=partial+size_t(hh)*C*258;
  const int dim=blk*32+lane;
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
 });});
}
}
namespace labx {
// Diagnostic prologue/epilogue kernels at the tiles_heads grid. Bits: 1 = blocked(a) atomic, 2 = exp, 4 = max+lane_tree,
// 8 = myid load + qv load.
template<int Bits>inline sycl::event probe(sycl::queue&q,ng::Shape s,ng::Args a,const int*counts,float*partial){
 const int C=splits(s);
 return q.parallel_for(sycl::nd_range<1>(size_t(s.tokens)*2*C*384,384),[=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
  const int G=int(it.get_group_linear_id()),c=G%C,kv=(G/C)%2,r=G/(C*2),n=counts[r],S=s.budget+3;
  if(n<=0)return;
  if constexpr((Bits&1)!=0){if(blocked(a))return;}
  const int start=c*32;if(start>=n)return;
  auto sg=it.get_sub_group();const int lane=int(sg.get_local_linear_id()),h=kv*12+int(it.get_local_linear_id())/32;
  const int valid=sycl::min(32,n-start);
  float x=float(lane)*0.01f;
  if constexpr((Bits&8)!=0){const int myid=lane<valid?a.i(4)[r*S+start+lane]:0;x=x+static_cast<const float*>(a.p[2])[(myid*2+kv)*256+lane];}
  float w=x;
  if constexpr((Bits&2)!=0)w=detmath::exp(x);
  if constexpr((Bits&4)!=0){const float m=first_max(-INFINITY,sg_first_max(sg,w));w=lane_tree(sg,w-m);}
  float*p=partial+size_t((r*24+h)*C+c)*258;
  p[lane]=w;
 });
}
}
namespace labx {
// tiles_v2: one 512-lane work-group (16 subgroups) per (row, KV head, tile).
// Scores: subgroup (dq = sub&3, hg = sub>>2): lane = slot, 3 query heads, dims 64dq..64dq+63 in natural order with a
// streaming balanced 64-leaf tree; score = ((Q0+Q1)+(Q2+Q3))/16 equals score<true>()'s balanced 256-leaf tree.
// Softmax: subgroup = local head (12), lane = slot, exactly tiles_heads. Values: lane = (dimension, head half), 6
// heads per lane, each V element read once per head half, balanced 32-leaf tree in slot order per head.
template<int PF>inline sycl::event tiles_v2(sycl::queue&q,ng::Shape s,ng::Args a,const int*counts,float*partial){
 const int C=splits(s);
 return q.submit([&](sycl::handler& handler){
 sycl::local_accessor<float,1>P(4*12*32,handler);sycl::local_accessor<float,1>W(32*12,handler);
 handler.parallel_for(sycl::nd_range<1>(size_t(s.tokens)*2*C*512,512),[=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
  const int G=int(it.get_group_linear_id()),c=G%C,kv=(G/C)%2,r=G/(C*2),n=counts[r],S=s.budget+3,lid=int(it.get_local_linear_id());
  if(n<=0||blocked_wg(it,a))return;
  const int start=c*32;if(start>=n)return;
  auto sg=it.get_sub_group();const int lane=int(sg.get_local_linear_id()),sub=lid/32;
  const int valid=sycl::min(32,n-start);
  const int myid=lane<valid?a.i(4)[r*S+start+lane]:0;
  const float*K=static_cast<const float*>(a.p[2]);const float*V=static_cast<const float*>(a.p[3]);const float*Q=static_cast<const float*>(a.p[0]);
  if constexpr(PF!=0){const int row=lid>>3,j=row&31;const int id=sycl::select_from_group(sg,myid,j);
   if(j<valid)sx::prefetch((void*)((row<32?K:V)+(id*2+kv)*256+(lid&7)*32),128,sx::properties{sx::prefetch_hint_L1});}
  {const int dq=sub&3,hg=sub>>2;
   float qa[3][2];
   #pragma unroll
   for(int hl=0;hl<3;++hl){const float*qp=Q+(r*24+kv*12+hg*3+hl)*256+64*dq+2*lane;qa[hl][0]=qp[0];qa[hl][1]=qp[1];}
   float st[3][6];float res[3];
   const float*krow=K+(myid*2+kv)*256+64*dq;
   #pragma unroll
   for(int ch=0;ch<8;++ch){
    sycl::vec<float,8> kk(0.f);if(lane<valid)kk.load(0,gp(krow+ch*8));
    #pragma unroll
    for(int e=0;e<8;++e){const int d=ch*8+e;
     #pragma unroll
     for(int hl=0;hl<3;++hl){const float qd=sycl::select_from_group(sg,qa[hl][d&1],d>>1);float cur=kk[e]*qd;
      int k=0;
      #pragma unroll
      for(;k<6;++k){if(((d>>k)&1)==0)break;cur=st[hl][k]+cur;}
      if(k<6)st[hl][k]=cur;else res[hl]=cur;}}}
   #pragma unroll
   for(int hl=0;hl<3;++hl)P[(dq*12+hg*3+hl)*32+lane]=res[hl];}
  it.barrier(sycl::access::fence_space::local_space);
  if(sub<12){
   const int h=kv*12+sub;
   const float x=lane<valid?((P[(0*12+sub)*32+lane]+P[(1*12+sub)*32+lane])+(P[(2*12+sub)*32+lane]+P[(3*12+sub)*32+lane]))/detmath::sqrt(256.f):-INFINITY;
   const float m=first_max(-INFINITY,sg_first_max(sg,x));
   const float w=lane<valid?detmath::exp(x-m):0.f;
   const float den=lane_tree(sg,w);
   float*p=partial+size_t((r*24+h)*C+c)*258;
   if(lane==0){p[256]=m;p[257]=den;}
   W[lane*12+sub]=w;
  }
  it.barrier(sycl::access::fence_space::local_space);
  {const int d=lid&255,hh=lid>>8;
   float acc[6][5];float root[6];
   #pragma unroll
   for(int j=0;j<32;++j){
    const int id=sycl::select_from_group(sg,myid,j);
    float vv=0.f;if(j<valid)vv=V[(id*2+kv)*256+d];
    #pragma unroll
    for(int hl=0;hl<6;++hl){float leaf=j<valid?W[j*12+hh*6+hl]*vv:0.f;
     int k=0;
     #pragma unroll
     for(;k<5;++k){if(((j>>k)&1)==0)break;leaf=acc[hl][k]+leaf;}
     if(k<5)acc[hl][k]=leaf;else root[hl]=leaf;}}
   #pragma unroll
   for(int hl=0;hl<6;++hl)partial[size_t((r*24+kv*12+hh*6+hl)*C+c)*258+d]=root[hl];}
 });});
}
}
namespace labx {
// tiles_v3: tiles_v2's arithmetic; n-independent loads (slot ids of the row, q) issued before the guard, a full-tile
// body without per-slot conditionals, the value-phase weights read once into registers (lane = slot) and broadcast.
template<int PF>inline sycl::event tiles_v3(sycl::queue&q,ng::Shape s,ng::Args a,const int*counts,float*partial){
 const int C=splits(s);
 return q.submit([&](sycl::handler& handler){
 sycl::local_accessor<float,1>P(4*12*32,handler);sycl::local_accessor<float,1>W(12*32,handler);
 handler.parallel_for(sycl::nd_range<1>(size_t(s.tokens)*2*C*512,512),[=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
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
  if constexpr(PF==1){const int row=int(it.get_local_linear_id())>>3,j=row&31;const int id=sycl::select_from_group(sg,myid,j);
   if(j<valid)sx::prefetch((void*)((row<32?K:V)+(id*2+kv)*256+(int(it.get_local_linear_id())&7)*32),128,sx::properties{sx::prefetch_hint_L1});}
  if constexpr(PF==2){const int row=int(it.get_local_linear_id())>>3,j=row&31;const int id=sycl::select_from_group(sg,myid,j);
   if(j<valid)sx::prefetch((void*)((row<32?K:V)+(id*2+kv)*256+(int(it.get_local_linear_id())&7)*32),128,sx::properties{sx::prefetch_hint_L2});}
  if constexpr(PF==3){const int j=int(it.get_local_linear_id())>>4;const int id=sycl::select_from_group(sg,myid,j);
   if(j<valid)sx::prefetch((void*)(V+(id*2+kv)*256+(int(it.get_local_linear_id())&15)*16),64,sx::properties{sx::prefetch_hint_L2});}
  if constexpr(PF==4){const int j=int(it.get_local_linear_id())>>4;const int id=sycl::select_from_group(sg,myid,j);
   if(j<valid)sx::prefetch((void*)(V+(id*2+kv)*256+(int(it.get_local_linear_id())&15)*16),64,sx::properties{sx::prefetch_hint_L1});}
  auto scores=[&]<bool Full>(){
   float st[3][6];float res[3];
   const float*krow=K+(myid*2+kv)*256+64*dq;
   #pragma unroll
   for(int ch=0;ch<8;++ch){
    sycl::vec<float,8> kk;
    if constexpr(Full)kk.load(0,gp(krow+ch*8));else{kk=sycl::vec<float,8>(0.f);if(lane<valid)kk.load(0,gp(krow+ch*8));}
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
 });});
}
}
namespace labx {
// tiles_v4: tiles_v3 with explicit load batching. KB: K chunks loaded KB at a time ahead of their products (KB=8 ->
// all eight); VB: V slot values loaded VB at a time before their leaves. Arithmetic unchanged.
template<int KB,int VB>inline sycl::event tiles_v4(sycl::queue&q,ng::Shape s,ng::Args a,const int*counts,float*partial){
 const int C=splits(s);
 return q.submit([&](sycl::handler& handler){
 sycl::local_accessor<float,1>P(4*12*32,handler);sycl::local_accessor<float,1>W(12*32,handler);
 handler.parallel_for(sycl::nd_range<1>(size_t(s.tokens)*2*C*512,512),[=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
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
   for(int cb=0;cb<8;cb+=KB){
    sycl::vec<float,8> kk[KB];
    #pragma unroll
    for(int u=0;u<KB;++u){
     if constexpr(Full)kk[u].load(0,gp(krow+(cb+u)*8));else{kk[u]=sycl::vec<float,8>(0.f);if(lane<valid)kk[u].load(0,gp(krow+(cb+u)*8));}}
    #pragma unroll
    for(int u=0;u<KB;++u){
    #pragma unroll
    for(int e=0;e<8;++e){const int dd=(cb+u)*8+e;
     #pragma unroll
     for(int hl=0;hl<3;++hl){const float qd=sycl::select_from_group(sg,qa[hl][dd&1],dd>>1);float cur=kk[u][e]*qd;
      int k=0;
      #pragma unroll
      for(;k<6;++k){if(((dd>>k)&1)==0)break;cur=st[hl][k]+cur;}
      if(k<6)st[hl][k]=cur;else res[hl]=cur;}}}}
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
   for(int jb=0;jb<32;jb+=VB){
    float vv[VB];
    #pragma unroll
    for(int u=0;u<VB;++u){const int j=jb+u;const int id=sycl::select_from_group(sg,myid,j);
     if constexpr(Full)vv[u]=vcol[id*512];else vv[u]=j<valid?vcol[id*512]:0.f;}
    #pragma unroll
    for(int u=0;u<VB;++u){const int j=jb+u;
    #pragma unroll
    for(int hl=0;hl<6;++hl){const float wj=sycl::select_from_group(sg,wr[hl],j);float leaf;
     if constexpr(Full)leaf=wj*vv[u];else leaf=j<valid?wj*vv[u]:0.f;
     int k=0;
     #pragma unroll
     for(;k<5;++k){if(((j>>k)&1)==0)break;leaf=acc[hl][k]+leaf;}
     if(k<5)acc[hl][k]=leaf;else root[hl]=leaf;}}}
   #pragma unroll
   for(int hl=0;hl<6;++hl)partial[size_t((r*24+kv*12+hh*6+hl)*C+c)*258+d]=root[hl];};
  if(valid==32)values.template operator()<true>();else values.template operator()<false>();
 });});
}
}
namespace labx {
// Diagnostic: tiles_v3 with phases removed (Skip bits: 1 scores, 2 softmax exp/max/den, 4 values). Not exact.
template<int Skip>inline sycl::event tiles_v3_diag(sycl::queue&q,ng::Shape s,ng::Args a,const int*counts,float*partial){
 const int C=splits(s);
 return q.submit([&](sycl::handler& handler){
 sycl::local_accessor<float,1>P(4*12*32,handler);sycl::local_accessor<float,1>W(12*32,handler);
 handler.parallel_for(sycl::nd_range<1>(size_t(s.tokens)*2*C*512,512),[=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
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
  if constexpr((Skip&1)==0){
   float st[3][6];float res[3];
   const float*krow=K+(myid*2+kv)*256+64*dq;
   #pragma unroll
   for(int ch=0;ch<8;++ch){
    sycl::vec<float,8> kk;kk.load(0,gp(krow+ch*8));
    #pragma unroll
    for(int e=0;e<8;++e){const int dd=ch*8+e;
     #pragma unroll
     for(int hl=0;hl<3;++hl){const float qd=sycl::select_from_group(sg,qa[hl][dd&1],dd>>1);float cur=kk[e]*qd;
      int k=0;
      #pragma unroll
      for(;k<6;++k){if(((dd>>k)&1)==0)break;cur=st[hl][k]+cur;}
      if(k<6)st[hl][k]=cur;else res[hl]=cur;}}}
   #pragma unroll
   for(int hl=0;hl<3;++hl)P[(dq*12+hg*3+hl)*32+lane]=res[hl];
  } else {for(int hl=0;hl<3;++hl)P[(dq*12+hg*3+hl)*32+lane]=qa[hl][0];}
  it.barrier(sycl::access::fence_space::local_space);
  if(sub<12){
   const int h=kv*12+sub;
   const float x=lane<valid?((P[(0*12+sub)*32+lane]+P[(1*12+sub)*32+lane])+(P[(2*12+sub)*32+lane]+P[(3*12+sub)*32+lane]))/detmath::sqrt(256.f):-INFINITY;
   float w,m,den;
   if constexpr((Skip&2)==0){m=first_max(-INFINITY,sg_first_max(sg,x));w=lane<valid?detmath::exp(x-m):0.f;den=lane_tree(sg,w);}
   else{m=x;w=x;den=x;}
   float*p=partial+size_t((r*24+h)*C+c)*258;
   if(lane==0){p[256]=m;p[257]=den;}
   W[sub*32+lane]=w;
  }
  it.barrier(sycl::access::fence_space::local_space);
  float wr[6];
  #pragma unroll
  for(int hl=0;hl<6;++hl)wr[hl]=W[(hh*6+hl)*32+lane];
  const float*vcol=V+kv*256+d;
  if constexpr((Skip&4)==0){
   float acc[6][5];float root[6];
   #pragma unroll
   for(int j=0;j<32;++j){
    const int id=sycl::select_from_group(sg,myid,j);
    float vv=vcol[id*512];
    #pragma unroll
    for(int hl=0;hl<6;++hl){const float wj=sycl::select_from_group(sg,wr[hl],j);float leaf=wj*vv;
     int k=0;
     #pragma unroll
     for(;k<5;++k){if(((j>>k)&1)==0)break;leaf=acc[hl][k]+leaf;}
     if(k<5)acc[hl][k]=leaf;else root[hl]=leaf;}}
   #pragma unroll
   for(int hl=0;hl<6;++hl)partial[size_t((r*24+kv*12+hh*6+hl)*C+c)*258+d]=root[hl];
  } else {for(int hl=0;hl<6;++hl)partial[size_t((r*24+kv*12+hh*6+hl)*C+c)*258+d]=wr[hl];}
 });});
}
}
namespace labx {
// tiles_v5<HW,VE>: tiles_v3 with HW query heads per work-group (12: v3; 6: two work-groups per (row, KV head, tile),
// adjacent in dispatch order) and, if VE, the 32 value-phase V loads issued before the softmax (held in registers).
template<int HW,bool VE>inline sycl::event tiles_v5(sycl::queue&q,ng::Shape s,ng::Args a,const int*counts,float*partial){
 static_assert(HW==12||HW==6);
 constexpr int NP=12/HW,SG=HW/3*4,LANES=SG*32;
 const int C=splits(s);
 return q.submit([&](sycl::handler& handler){
 sycl::local_accessor<float,1>P(4*HW*32,handler);sycl::local_accessor<float,1>W(HW*32,handler);
 handler.parallel_for(sycl::nd_range<1>(size_t(s.tokens)*2*C*NP*LANES,LANES),[=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
  const int G=int(it.get_group_linear_id()),hp=G%NP,c=(G/NP)%C,kv=(G/(NP*C))%2,r=G/(NP*C*2),S=s.budget+3,start=c*32;
  auto sg=it.get_sub_group();const int lane=int(sg.get_local_linear_id()),sub=int(sg.get_group_linear_id());
  const int dq=sub&3,hg=sub>>2,hh=sub>>3,d=(sub&7)*32+lane,hbase=kv*12+hp*HW;
  const float*K=static_cast<const float*>(a.p[2]);const float*V=static_cast<const float*>(a.p[3]);const float*Q=static_cast<const float*>(a.p[0]);
  const int rawid=start+lane<S?a.i(4)[r*S+start+lane]:0;
  float qa[3][2];
  #pragma unroll
  for(int hl=0;hl<3;++hl){const float*qp=Q+(r*24+hbase+hg*3+hl)*256+64*dq+2*lane;qa[hl][0]=qp[0];qa[hl][1]=qp[1];}
  const int n=counts[r];
  if(n<=0||blocked_wg(it,a))return;
  if(start>=n)return;
  const int valid=sycl::min(32,n-start);
  const int myid=lane<valid?rawid:0;
  const float*vcol=V+kv*256+d;
  auto scores=[&]<bool Full>(){
   float st[3][6];float res[3];
   const float*krow=K+(myid*2+kv)*256+64*dq;
   #pragma unroll
   for(int ch=0;ch<8;++ch){
    sycl::vec<float,8> kk;
    if constexpr(Full)kk.load(0,gp(krow+ch*8));else{kk=sycl::vec<float,8>(0.f);if(lane<valid)kk.load(0,gp(krow+ch*8));}
    #pragma unroll
    for(int e=0;e<8;++e){const int dd=ch*8+e;
     #pragma unroll
     for(int hl=0;hl<3;++hl){const float qd=sycl::select_from_group(sg,qa[hl][dd&1],dd>>1);float cur=kk[e]*qd;
      int k=0;
      #pragma unroll
      for(;k<6;++k){if(((dd>>k)&1)==0)break;cur=st[hl][k]+cur;}
      if(k<6)st[hl][k]=cur;else res[hl]=cur;}}}
   #pragma unroll
   for(int hl=0;hl<3;++hl)P[(dq*HW+hg*3+hl)*32+lane]=res[hl];};
  if(valid==32)scores.template operator()<true>();else scores.template operator()<false>();
  float vv[32];
  if constexpr(VE){
   #pragma unroll
   for(int j=0;j<32;++j){const int id=sycl::select_from_group(sg,myid,j);vv[j]=j<valid?vcol[id*512]:0.f;}}
  it.barrier(sycl::access::fence_space::local_space);
  if(sub<HW){
   const int h=hbase+sub;
   const float x=lane<valid?((P[(0*HW+sub)*32+lane]+P[(1*HW+sub)*32+lane])+(P[(2*HW+sub)*32+lane]+P[(3*HW+sub)*32+lane]))/detmath::sqrt(256.f):-INFINITY;
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
  auto values=[&]<bool Full>(){
   float acc[6][5];float root[6];
   #pragma unroll
   for(int j=0;j<32;++j){
    float v;
    if constexpr(VE)v=vv[j];else{const int id=sycl::select_from_group(sg,myid,j);if constexpr(Full)v=vcol[id*512];else v=j<valid?vcol[id*512]:0.f;}
    #pragma unroll
    for(int hl=0;hl<6;++hl){const float wj=sycl::select_from_group(sg,wr[hl],j);float leaf;
     if constexpr(Full)leaf=wj*v;else leaf=j<valid?wj*v:0.f;
     int k=0;
     #pragma unroll
     for(;k<5;++k){if(((j>>k)&1)==0)break;leaf=acc[hl][k]+leaf;}
     if(k<5)acc[hl][k]=leaf;else root[hl]=leaf;}}
   #pragma unroll
   for(int hl=0;hl<6;++hl)partial[size_t((r*24+hbase+hh*6+hl)*C+c)*258+d]=root[hl];};
  if(valid==32)values.template operator()<true>();else values.template operator()<false>();
 });});
}
}
namespace labx {
// combine_v2: combine_blocked without the local-memory factor exchange. Every subgroup forms the tile max (first_max
// over tiles l, 32+l, 64+l in order), the factors and the denominator itself (three exp per lane), so the only
// cross-subgroup step is the final level-5..7 merge of the four 16-tile dimension trees (one barrier).
inline sycl::event combine_v2(sycl::queue&q,ng::Shape s,ng::Args a,const int*counts,const float*partial){
 const int C=splits(s);
 return q.submit([&](sycl::handler& handler){
 sycl::local_accessor<float,1>part(4*32,handler);
 handler.parallel_for(sycl::nd_range<1>(size_t(s.tokens)*24*8*128,128),[=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
  const int g=int(it.get_group_linear_id()),blk=g%8,hh=g/8,r=hh/24;
  auto sg=it.get_sub_group();const int lane=int(sg.get_local_linear_id()),sub=int(sg.get_group_linear_id()),dim=blk*32+lane;
  const float*p=partial+size_t(hh)*C*258;
  float raw[16];
  #pragma unroll
  for(int k=0;k<16;++k){const int c=sub*16+k;raw[k]=c<C?p[c*258+dim]:0.f;}
  const float raw64=(sub==0&&C>64)?p[64*258+dim]:0.f;
  float pm[3],pd[3];
  #pragma unroll
  for(int t=0;t<3;++t){const int c=t*32+lane;pm[t]=c<C?p[c*258+256]:NAN;pd[t]=c<C?p[c*258+257]:0.f;}
  const float gate=sub==0?ng::sigmoid(a.b(1,hh*256+dim)):0.f;
  const int n=counts[r];
  if(n<=0||blocked_wg(it,a))return;
  const int count=(n+31)/32;
  float m=-INFINITY;
  #pragma unroll
  for(int t=0;t<3;++t){const bool valid=t*32+lane<count;m=first_max(m,sg_first_max(sg,valid?pm[t]:NAN));}
  float f[3],S[3];
  #pragma unroll
  for(int t=0;t<3;++t){const bool valid=t*32+lane<count;f[t]=valid?detmath::exp(pm[t]-m):0.f;float d=valid?pd[t]*f[t]:0.f;
   for(int z=1;z<32&&z<count;z*=2){const float o=sycl::permute_group_by_xor(sg,d,z);d=(lane&z)?o+d:d+o;}S[t]=d;}
  const float den=count<=32?S[0]:(count<=64?S[0]+S[1]:(S[0]+S[1])+(S[2]+0.f));
  // factors of this subgroup's tiles 16sub..16sub+15 live in row sub>>1, lanes 16(sub&1)..+15
  float frow=(sub>>1)==0?f[0]:f[1];
  float lv[16];
  #pragma unroll
  for(int k=0;k<16;++k){const int c=sub*16+k;const float fc=sycl::select_from_group(sg,frow,(sub&1)*16+k);lv[k]=c<count?raw[k]*fc:0.f;}
  #pragma unroll
  for(int z=1;z<16;z*=2)if(z<count){
   #pragma unroll
   for(int k=0;k<16;k+=2*z)lv[k]=lv[k]+lv[k+z];}
  part[sub*32+lane]=lv[0];
  const float f64=sycl::select_from_group(sg,f[2],0);
  it.barrier(sycl::access::fence_space::local_space);
  if(sub==0){
   float v;
   if(count<=16)v=lv[0];
   else if(count<=32)v=part[lane]+part[32+lane];
   else if(count<=64)v=(part[lane]+part[32+lane])+(part[64+lane]+part[96+lane]);
   else{float t=raw64*f64;for(int k=0;k<6;++k)t=t+0.f;v=((part[lane]+part[32+lane])+(part[64+lane]+part[96+lane]))+t;}
   v=v/den;
   a.put(5,hh*256+dim,v*gate);
  }
 });});
}
}
