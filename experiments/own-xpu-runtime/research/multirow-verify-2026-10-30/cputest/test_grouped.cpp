// CPU-device (OpenCL CPU, GPU blocked by nodri.so) bitwise test of the grouped routed-expert bodies (K2,
// research/multirow-verify-2026-10-30, stage2/packet194-expert-diet-engine/expert_groups.hpp) against the one-row decode
// kernels, on real expert rows of the model's GGUF (16 experts of each tensor stand in as a compact expert tensor):
//   IQ3_XXS gate (blk.30): xgroup2::xxs_grouped<4,S>  vs dn2::xxs_packed<4>      (the production one-row body, per slot)
//   IQ3_S gate (blk.25), IQ2_S gate (blk.23): xgroup2::rows_grouped<T,R,S,4> vs a verbatim replica of
//                                               kopt::MultiplyBlockRows<4> (copied from research/decode-next2/cputest)
//   IQ4_NL down (blk.0, K 640): xgroup2::iq4nl_grouped<16,1,4,2,S> vs the same replica (MultiplyBlockRows handles
//                                               IQ4_NL with decode8; MultiplyIQ4NLPacked keeps its values and tree)
// Route sets: M = 2, 3, 4 token rows x 10 distinct experts each (overlapping across rows), one invalid route, one short
// route, and a set with 6 slots on one expert (more than S = 4 members: the group splits by rank).
#include <sycl/sycl.hpp>
#include "stage2/packet194-expert-diet-engine/expert_groups.hpp"
#include <cstdio>
#include <cstring>
#include <fcntl.h>
#include <random>
#include <unistd.h>
#include <vector>
#include <algorithm>
using iq3::Type;
static const char* F1="/mnt/usb-models/llm-models/SC117-Qwen3.8-Flash-Next-GSQ-RCO-abliterated-IQ3_S-eec4e10a/Qwen3.8-Flash-Next-GSQ-RCO-abliterated-IQ3_S-00001-of-00002.gguf";
static constexpr size_t DATA=11024384; // GGUF data offset: file offset = placement offset + DATA
static std::vector<uint8_t> rd(size_t off,size_t n){std::vector<uint8_t> v(n);int fd=::open(F1,O_RDONLY);if(fd<0||::pread(fd,v.data(),n,off_t(off))!=ssize_t(n)){std::perror("read");std::exit(1);}::close(fd);return v;}
static int fails=0;
static void report(const char* what,const float* got,const float* want,size_t n){
 size_t bad=0;for(size_t i=0;i<n;++i)bad+=std::memcmp(got+i,want+i,4)!=0;
 std::printf("  %-70s outputs %7zu mismatches %zu %s\n",what,n,bad,bad?"FAIL":"ok");fails+=bad!=0;
}
template<class T> T* dev(sycl::queue& q,const std::vector<T>& h){T* p=sycl::malloc_device<T>(h.size(),q);q.memcpy(p,h.data(),h.size()*sizeof(T)).wait();return p;}
template<class T> std::vector<T> host(sycl::queue& q,const T* p,size_t n){std::vector<T> h(n);q.memcpy(h.data(),p,n*sizeof(T)).wait();return h;}
// ---- verbatim replica of kopt MultiplyBlockRows<4>::run<T,32> (kernels.cpp; copied from decode-next2/cputest) ----
template<Type T> static void ref_block_rows(sycl::queue& q,xgroup2::RowsView d){
 constexpr unsigned R=4,Subgroups=4,SG=32;const size_t blocks=(d.span+R-1)/R,total=blocks*d.count,groups=(total+Subgroups-1)/Subgroups;
 q.parallel_for(sycl::nd_range<1>(groups*SG*Subgroups,SG*Subgroups),[=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(SG)]]{
  using namespace iq3;using namespace iq3::kopt;
  auto sg=it.get_sub_group();const unsigned lane=sg.get_local_linear_id();
  const size_t logical=it.get_group_linear_id()*Subgroups+sg.get_group_linear_id();if(logical>=total)return;
  const size_t slot=logical/blocks,first=(logical%blocks)*R;
  Route r=d.routes[slot];
  const bool valid=valid_route(r,d.experts,d.rows,d.span);
  if(first==0&&lane==0)d.status[slot]=valid?0:1;
  const float* x=d.x+slot*d.k;const uint8_t* w=d.w;
  float acc[R];const uint8_t* rows[R];bool live[R];
  #pragma unroll
  for(unsigned i=0;i<R;++i){acc[i]=0;const size_t row=first+i;live[i]=valid&&row<d.span&&row<r.row_count;
    rows[i]=live[i]?w+(size_t(r.expert_id)*d.rows+r.row_begin+row)*d.rb:w;}
  const uint32_t k32=uint32_t(d.k);uint32_t k=lane*8u;
  for(;k+8u<=k32;k+=SG*8u) {
    float input[8];
    #pragma unroll
    for(unsigned j=0;j<8;++j)input[j]=x[k+j];
    #pragma unroll
    for(unsigned i=0;i<R;++i) {
      if(!live[i])continue;float values[8];decode8<T>(rows[i],k,values);
      #pragma unroll
      for(unsigned j=0;j<8;++j){float product=values[j]*input[j];acc[i]=acc[i]+product;}
    }
  }
  #pragma unroll
  for(unsigned i=0;i<R;++i) {
    float sum=acc[i];
    for(unsigned width=1;width<SG;width*=2){float rhs=sycl::select_from_group(sg,sum,(lane+width)%SG);if(lane%(2*width)==0)sum=sum+rhs;}
    const size_t row=first+i;
    if(lane==0&&row<d.span)d.y[slot*d.span+row]=valid&&row<r.row_count?sum:bits_float(0x7fc00000);
  }
 }).wait();
}
// Route sets over E experts: M rows of 10 distinct experts, rows overlapping (drawn from 16), plus edge cases.
static std::vector<iq3::Route> routes_for(unsigned M,uint32_t rows,uint32_t E,unsigned seed,bool edges,bool crowd){
 std::mt19937 g(seed);std::vector<iq3::Route> r;
 for(unsigned t=0;t<M;++t){std::vector<uint32_t> e(E);for(uint32_t i=0;i<E;++i)e[i]=i;std::shuffle(e.begin(),e.end(),g);
  for(unsigned j=0;j<10;++j)r.push_back({e[j],0,rows});}
 if(edges){r[3]={E+5,0,rows};r[r.size()-4].row_count=rows/2+1;}
 if(crowd)for(unsigned i=0;i<6&&i<r.size();++i)r[i*3%r.size()]={7,0,rows};
 return r;
}
static std::vector<float> inputs(size_t n,unsigned seed){std::mt19937 g(seed);std::normal_distribution<float> nd(0,1);std::vector<float> v(n);for(auto& x:v)x=nd(g);return v;}
static void xxs_case(sycl::queue& q,unsigned M,bool edges,bool crowd){
 const uint32_t rows=640,cols=2560,rb=980,E=16;auto wh=rd(34163303552ull+DATA,size_t(E)*rows*rb);
 auto rt=routes_for(M,rows,E,100+M,edges,crowd);const uint32_t n=uint32_t(rt.size());auto xh=inputs(size_t(n)*cols,7+M);
 uint8_t* w=dev(q,wh);float* x=dev(q,xh);iq3::Route* r=dev(q,rt);std::vector<float> sent(size_t(n)*rows+32,-777.f);std::vector<uint32_t> ss(n,77);
 float* yr=dev(q,sent);float* yn=dev(q,sent);uint32_t* sr=dev(q,ss);uint32_t* sn=dev(q,ss);
 const dn2::XxsView vr{w,x,yr,r,sr,rows,cols,rb,n,E},vn{w,x,yn,r,sn,rows,cols,rb,n,E};constexpr unsigned WGSG=4;
 const uint32_t blocks=(rows+3)/4,total=blocks*n,groups=(total+WGSG-1)/WGSG;
 q.parallel_for(sycl::nd_range<1>(size_t(groups)*32*WGSG,32*WGSG),[=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{dn2::xxs_packed<WGSG>(vr,it);}).wait();
 {const uint32_t G=n,gt=blocks*G,gg=(gt+WGSG-1)/WGSG;
 q.parallel_for(sycl::nd_range<1>(size_t(gg)*32*WGSG,32*WGSG),[=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{xgroup2::xxs_grouped<WGSG,4>(vn,G,it);}).wait();}
 auto want=host(q,yr,sent.size()),got=host(q,yn,sent.size());auto sw=host(q,sr,n),sg=host(q,sn,n);char nm[128];
 std::snprintf(nm,sizeof nm,"IQ3_XXS blk.30 gate xxs_grouped<4,4,G=n> M=%u slots %u%s%s",M,n,edges?" +invalid/short":"",crowd?" +crowd":"");report(nm,got.data(),want.data(),got.size());
 const bool st=std::memcmp(sw.data(),sg.data(),n*4)==0;std::printf("    status %s\n",st?"ok":"FAIL");fails+=!st;
 sycl::free(w,q);sycl::free(x,q);sycl::free(r,q);sycl::free(yr,q);sycl::free(yn,q);sycl::free(sr,q);sycl::free(sn,q);
}
template<Type T,unsigned R> static void rows_case(sycl::queue& q,const char* name,size_t off,uint32_t rows,uint32_t k,uint32_t rb,unsigned M,bool edges,bool crowd,bool iq4nl){
 const uint32_t E=16;auto wh=rd(off+DATA,size_t(E)*rows*rb);
 auto rt=routes_for(M,rows,E,200+M,edges,crowd);const uint32_t n=uint32_t(rt.size());auto xh=inputs(size_t(n)*k,9+M);
 uint8_t* w=dev(q,wh);float* x=dev(q,xh);iq3::Route* r=dev(q,rt);std::vector<float> sent(size_t(n)*rows+32,-777.f);std::vector<uint32_t> ss(n,77);
 float* yr=dev(q,sent);float* yn=dev(q,sent);uint32_t* sr=dev(q,ss);uint32_t* sn=dev(q,ss);
 const xgroup2::RowsView vr{w,x,yr,r,sr,rows,k,rb,n,E,rows},vn{w,x,yn,r,sn,rows,k,rb,n,E,rows};
 ref_block_rows<T>(q,vr);constexpr unsigned WGSG=4;
 if(iq4nl){constexpr unsigned SG=16,RPS=(SG/8)*1;const uint32_t G=n,blocks=(rows+RPS-1)/RPS,total=blocks*G,groups=(total+WGSG-1)/WGSG;
  q.parallel_for(sycl::nd_range<1>(size_t(groups)*SG*WGSG,SG*WGSG),[=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(16)]]{xgroup2::iq4nl_grouped<16,1,WGSG,2,4>(vn,G,it);}).wait();}
 else{const uint32_t G=n,blocks=(rows+R-1)/R,total=blocks*G,groups=(total+WGSG-1)/WGSG;
  q.parallel_for(sycl::nd_range<1>(size_t(groups)*32*WGSG,32*WGSG),[=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{xgroup2::rows_grouped<T,R,4,WGSG>(vn,G,it);}).wait();}
 auto want=host(q,yr,sent.size()),got=host(q,yn,sent.size());auto sw=host(q,sr,n),sg=host(q,sn,n);char nm[128];
 std::snprintf(nm,sizeof nm,"%s %s M=%u slots %u%s%s",name,iq4nl?"iq4nl_grouped<16,1,4,2,4,G=n>":(R==4?"rows_grouped<R4,S4,G=n>":"rows_grouped<R2,S4,G=n>"),M,n,edges?" +invalid/short":"",crowd?" +crowd":"");
 report(nm,got.data(),want.data(),got.size());
 const bool st=std::memcmp(sw.data(),sg.data(),n*4)==0;std::printf("    status %s\n",st?"ok":"FAIL");fails+=!st;
 sycl::free(w,q);sycl::free(x,q);sycl::free(r,q);sycl::free(yr,q);sycl::free(yn,q);sycl::free(sr,q);sycl::free(sn,q);
}
int main(){
 sycl::queue q{sycl::device(sycl::cpu_selector_v),sycl::property::queue::in_order()};
 std::printf("device: %s\n",q.get_device().get_info<sycl::info::device::name>().c_str());
 for(unsigned M:{2u,3u,4u})for(int c=0;c<3;++c){const bool edges=c==1,crowd=c==2;
  xxs_case(q,M,edges,crowd);
  rows_case<Type::IQ3_S,2>(q,"IQ3_S blk.25 gate",28213644416ull,640,2560,1100,M,edges,crowd,false);
  rows_case<Type::IQ3_S,4>(q,"IQ3_S blk.25 gate",28213644416ull,640,2560,1100,M,edges,crowd,false);
  rows_case<Type::IQ2_S,2>(q,"IQ2_S blk.23 gate",26039772416ull,640,2560,820,M,edges,crowd,false);
  rows_case<Type::IQ4_NL,2>(q,"IQ4_NL blk.0 down",902686720ull,2560,640,360,M,edges,crowd,true);
 }
 std::printf(fails?"FAIL (%d)\n":"PASS\n",fails);return fails?1:0;
}
