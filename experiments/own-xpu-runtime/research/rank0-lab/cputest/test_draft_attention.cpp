// CPU-device bitwise test (OpenCL CPU, GPU blocked by nodri.so) of OWNRT_DRAFT_ATTN (rank0-lab, 2026-10-26): the BF16
// instantiations p47::tiles_heads<false> + p47::combine_blocked<false> against the BF16 production pair
// p47::tiles<true> + p47::combine<true> (the draft's QSA decode attention), following the qsa-attention lab's bench
// cases: slot counts 1..2051, multi-row launches, +0/-0 values and repeated ids (exact score ties). Compared: the BF16
// outputs and every valid partial (258 floats per tile), bitwise.
#include <sycl/sycl.hpp>
#include "stage2/packet194-expert-diet-engine/p49_qsa_kernel.hpp"
#include <algorithm>
#include <cstdio>
#include <random>
#include <vector>
#include <atomic>
namespace ownrt { std::uint64_t next_handle(){static std::atomic<std::uint64_t> n{1};return n.fetch_add(1);} } // as the qsa-attention bench
int main(){
 sycl::queue q{sycl::device{sycl::cpu_selector_v},sycl::property::queue::in_order{}};
 std::printf("device: %s\n",q.get_device().get_info<sycl::info::device::name>().c_str());
 const int CAP=4096,TMAX=4,S=2051;
 ng::Shape base{ng::attention_score,1,2560,4,0,0,CAP,2048,0}; // flags 0: BF16 activations and KV
 const int C=p47::splits(base);
 auto dmalloc=[&](size_t bytes){void* p=sycl::malloc_device(bytes,q);q.memset(p,0,bytes).wait();return p;};
 auto* Q=(uint16_t*)dmalloc(size_t(TMAX)*24*256*2);auto* G=(uint16_t*)dmalloc(size_t(TMAX)*24*256*2);
 auto* K=(uint16_t*)dmalloc(size_t(CAP)*512*2);auto* V=(uint16_t*)dmalloc(size_t(CAP)*512*2);
 int* ids=(int*)dmalloc(size_t(TMAX)*S*4);int* err=(int*)dmalloc(64);int* pos=(int*)dmalloc(64);int* act=(int*)dmalloc(64);
 auto* outR=(uint16_t*)dmalloc(size_t(TMAX)*24*256*2);auto* outC=(uint16_t*)dmalloc(size_t(TMAX)*24*256*2);int* counts=(int*)dmalloc(64);
 const size_t PF=size_t(TMAX)*24*C*258;float* partR=(float*)dmalloc(PF*4);float* partC=(float*)dmalloc(PF*4);
 std::mt19937 rng(4321);
 auto fill=[&](uint16_t* d,size_t n,float scale,int mode){std::vector<uint16_t> h(n);std::normal_distribution<float> nd(0.f,scale);
  for(size_t i=0;i<n;++i){float v=nd(rng);if(mode==1&&(i%97==0))v=0.f;if(mode==1&&(i%89==0))v=-0.f;h[i]=ng::Args::bits(v);}q.memcpy(d,h.data(),n*2).wait();};
 auto make_args=[&](uint16_t* out){ng::Args a;a.f32=false;a.p[0]=Q;a.p[1]=G;a.p[2]=K;a.p[3]=V;a.p[4]=ids;a.p[5]=out;a.p[15]=err;a.p[17]=pos;a.p[18]=act;return a;};
 struct Case{int T;std::vector<int> n;int mode;};
 std::vector<Case> cases={{1,{2051},0},{1,{2050},0},{1,{2049},0},{1,{2048},0},{1,{2047},0},{1,{1},0},{1,{2},0},{1,{31},0},{1,{32},0},{1,{33},0},
  {1,{300},0},{1,{513},0},{1,{1025},0},{1,{64},0},{1,{65},0},{1,{1056},0},{2,{2051,2051},0},{2,{300,301},0},{4,{5,100,2000,2051},0},
  {1,{2051},1},{1,{700},1},{2,{2051,17},1}};
 int failures=0;
 for(size_t ci=0;ci<cases.size();++ci){auto& cs=cases[ci];
  fill(Q,size_t(TMAX)*24*256,1.f,cs.mode);fill(G,size_t(TMAX)*24*256,1.f,0);fill(K,size_t(CAP)*512,cs.mode?0.05f:1.f,cs.mode);fill(V,size_t(CAP)*512,1.f,cs.mode);
  const int position=CAP-1-TMAX;std::vector<int> hid(size_t(TMAX)*S,-1);
  for(int r=0;r<cs.T;++r){std::vector<int> perm(position+1);for(int i=0;i<=position;++i)perm[i]=i;std::shuffle(perm.begin(),perm.end(),rng);for(int j=0;j<cs.n[r];++j)hid[size_t(r)*S+j]=perm[j];}
  if(cs.mode==1)for(int r=0;r<cs.T;++r)for(int j=0;j<std::min(cs.n[r],64);j+=3)hid[size_t(r)*S+j]=hid[size_t(r)*S];
  q.memcpy(ids,hid.data(),hid.size()*4).wait();int one=1,zero=0;q.memcpy(err,&zero,4).wait();q.memcpy(pos,&position,4).wait();q.memcpy(act,&one,4).wait();
  ng::Shape s=base;s.tokens=cs.T;
  p47::admit_fast(q,s,make_args(outR),counts).wait();
  std::vector<int> hc(cs.T);q.memcpy(hc.data(),counts,cs.T*4).wait();for(int r=0;r<cs.T;++r)if(hc[r]!=cs.n[r]){std::printf("admit mismatch\n");return 3;}
  q.memset(partR,0xff,PF*4).wait();q.memset(outR,0xff,size_t(TMAX)*24*256*2).wait();
  p47::tiles<true>(q,s,make_args(outR),counts,partR,{});p47::combine<true>(q,s,make_args(outR),counts,partR,{});q.wait();
  q.memset(partC,0xff,PF*4).wait();q.memset(outC,0xff,size_t(TMAX)*24*256*2).wait();
  p47::tiles_heads<false>(q,s,make_args(outC),counts,partC,{});p47::combine_blocked<false>(q,s,make_args(outC),counts,partC,{});q.wait();
  std::vector<uint16_t> oR(size_t(cs.T)*24*256),oC(oR.size());std::vector<uint32_t> pR(PF),pC(PF);
  q.memcpy(oR.data(),outR,oR.size()*2).wait();q.memcpy(oC.data(),outC,oC.size()*2).wait();q.memcpy(pR.data(),partR,PF*4).wait();q.memcpy(pC.data(),partC,PF*4).wait();
  size_t od=0,pd=0,unwritten=0;for(size_t i=0;i<oR.size();++i){od+=oR[i]!=oC[i];unwritten+=oR[i]==0xffff;}
  for(int r=0;r<cs.T;++r){int cnt=(cs.n[r]+31)/32;for(int h=0;h<24;++h)for(int c=0;c<cnt;++c){size_t b=(size_t(r*24+h)*C+c)*258;for(int k=0;k<258;++k)pd+=pR[b+k]!=pC[b+k];}}
  int err_h=0;q.memcpy(&err_h,err,4).wait();
  std::printf("  case %2zu T=%d n0=%4d mode=%d: output diff %zu, partial diff %zu, error %d, reference outputs unwritten %zu\n",ci,cs.T,cs.n[0],cs.mode,od,pd,err_h,unwritten);
  if(od||pd||err_h||unwritten)++failures;
 }
 std::printf("%s (%d failing of %zu cases)\n",failures?"FAILED":"ALL PASSED",failures,cases.size());return failures?1:0;
}
