// Lab microbenchmark for p49 QSA decode attention variants (2026-10-26). Exactness: bitwise output + valid partials
// against tiles<true,true> + combine<true,true>. Timing: device event times, cold (L2 flushed) and hot.
#include "stage2/packet194-expert-diet-engine/p49_qsa_kernel.hpp"
#include "exp_kernels.hpp"
#include <atomic>
#include <cstdio>
#include <cstring>
#include <random>
#include <algorithm>
namespace ownrt { std::uint64_t next_handle(){static std::atomic<std::uint64_t> n{1};return n.fetch_add(1);} }

using Fn=std::function<sycl::event(sycl::queue&,ng::Shape,ng::Args,const int*,float*)>;
struct Variant{const char* name;Fn tiles;Fn combine;};

static double us(sycl::event e){e.wait();auto a=e.get_profiling_info<sycl::info::event_profiling::command_start>();auto b=e.get_profiling_info<sycl::info::event_profiling::command_end>();return double(b-a)/1000.0;}

int main(int argc,char**argv){
 const int timing_iters=argc>1?std::atoi(argv[1]):30;const bool rflush=std::getenv("BENCH_RFLUSH")!=nullptr;
 const char* only=argc>2?argv[2]:nullptr;
 sycl::queue q{sycl::gpu_selector_v,sycl::property_list{sycl::property::queue::in_order(),sycl::property::queue::enable_profiling()}};
 auto dev=q.get_device();
 std::printf("device %s\n",dev.get_info<sycl::info::device::name>().c_str());
 const int CAP=8192,TMAX=4,S=2051;
 ng::Shape base{ng::attention_score,1,2560,4,0,ng::f32_activations_flag,CAP,2048,0};
 const int C=p47::splits(base);
 std::printf("C=%d\n",C);
 auto dmalloc=[&](size_t bytes){void* p=sycl::malloc_device(bytes,q);if(!p){std::printf("alloc fail\n");std::exit(2);}q.memset(p,0,bytes).wait();return p;};
 float* Q=(float*)dmalloc(size_t(TMAX)*24*256*4);float* G=(float*)dmalloc(size_t(TMAX)*24*256*4);
 float* K=(float*)dmalloc(size_t(CAP)*512*4);float* V=(float*)dmalloc(size_t(CAP)*512*4);
 int* ids=(int*)dmalloc(size_t(TMAX)*S*4);int* err=(int*)dmalloc(64);int* pos=(int*)dmalloc(64);int* act=(int*)dmalloc(64);
 float* outR=(float*)dmalloc(size_t(TMAX)*24*256*4);float* outC=(float*)dmalloc(size_t(TMAX)*24*256*4);
 int* counts=(int*)dmalloc(64);
 const size_t PF=size_t(TMAX)*24*C*258;
 float* partR=(float*)dmalloc(PF*4);float* partC=(float*)dmalloc(PF*4);
 const size_t FL=size_t(64)<<20;float* flush=(float*)dmalloc(FL*4); // 256 MB
 std::mt19937 rng(1234);
 auto fill=[&](float* d,size_t n,float scale,int mode){std::vector<float> h(n);std::normal_distribution<float> nd(0.f,scale);
  for(size_t i=0;i<n;++i){float v=nd(rng);if(mode==1&&(i%97==0))v=0.f;if(mode==1&&(i%89==0))v=-0.f;h[i]=v;}q.memcpy(d,h.data(),n*4).wait();};
 auto make_args=[&](float* out){ng::Args a;a.f32=true;a.p[0]=Q;a.p[1]=G;a.p[2]=K;a.p[3]=V;a.p[4]=ids;a.p[5]=out;a.p[15]=err;a.p[17]=pos;a.p[18]=act;return a;};
 Variant ref{"ref",[](sycl::queue&q,ng::Shape s,ng::Args a,const int*c,float*p){return p47::tiles<true,true>(q,s,a,c,p,{});},[](sycl::queue&q,ng::Shape s,ng::Args a,const int*c,float*p){return p47::combine<true,true>(q,s,a,c,p,{});}};
 std::vector<Variant> vars={
  {"v3+blocked",[](sycl::queue&q,ng::Shape s,ng::Args a,const int*c,float*p){return labx::tiles_v3<0>(q,s,a,c,p);},[](sycl::queue&q,ng::Shape s,ng::Args a,const int*c,float*p){return p47::combine_blocked(q,s,a,c,p,{});}},
  {"v3+combv2",[](sycl::queue&q,ng::Shape s,ng::Args a,const int*c,float*p){return labx::tiles_v3<0>(q,s,a,c,p);},[](sycl::queue&q,ng::Shape s,ng::Args a,const int*c,float*p){return labx::combine_v2(q,s,a,c,p);}},
  {"orig+combv2",[](sycl::queue&q,ng::Shape s,ng::Args a,const int*c,float*p){return p47::tiles<true,true>(q,s,a,c,p,{});},[](sycl::queue&q,ng::Shape s,ng::Args a,const int*c,float*p){return labx::combine_v2(q,s,a,c,p);}},
 };
 if(only){std::vector<Variant> keep;for(auto&v:vars)if(std::strstr(v.name,only))keep.push_back(v);vars=keep;}
 struct Case{int T;std::vector<int> n;int mode;};
 std::vector<Case> cases={{1,{2051},0},{1,{2050},0},{1,{2049},0},{1,{2048},0},{1,{2047},0},{1,{1},0},{1,{2},0},{1,{31},0},{1,{32},0},{1,{33},0},
  {1,{300},0},{1,{513},0},{1,{1025},0},{1,{64},0},{1,{65},0},{1,{1056},0},{2,{2051,2051},0},{2,{300,301},0},{4,{2051,2051,2051,2051},0},{4,{5,100,2000,2051},0},
  {1,{2051},1},{1,{700},1},{2,{2051,17},1}};
 int failures=0;
 if(std::getenv("BENCH_SKIP_EXACT"))cases.clear();
 for(size_t ci=0;ci<cases.size();++ci){auto&cs=cases[ci];
  // Fresh data per case; mode 1 adds exact +0/-0 elements (and scaled-down K so some scores tie).
  fill(Q,size_t(TMAX)*24*256,1.f,cs.mode);fill(G,size_t(TMAX)*24*256,1.f,0);fill(K,size_t(CAP)*512,cs.mode?0.05f:1.f,cs.mode);fill(V,size_t(CAP)*512,1.f,cs.mode);
  const int position=CAP-1-TMAX;
  std::vector<int> hid(size_t(TMAX)*S,-1);
  for(int r=0;r<cs.T;++r){std::vector<int> perm(position+1);for(int i=0;i<=position;++i)perm[i]=i;std::shuffle(perm.begin(),perm.end(),rng);
   for(int j=0;j<cs.n[r];++j)hid[size_t(r)*S+j]=perm[j];}
  if(cs.mode==1)for(int r=0;r<cs.T;++r)for(int j=0;j<std::min(cs.n[r],64);j+=3)hid[size_t(r)*S+j]=hid[size_t(r)*S]; // repeated ids: exact score ties
  q.memcpy(ids,hid.data(),hid.size()*4).wait();
  int one=1,zero=0;q.memcpy(err,&zero,4).wait();q.memcpy(pos,&position,4).wait();q.memcpy(act,&one,4).wait();
  ng::Shape s=base;s.tokens=cs.T;
  p47::admit_fast(q,s,make_args(outR),counts).wait();
  std::vector<int> hc(cs.T);q.memcpy(hc.data(),counts,cs.T*4).wait();
  for(int r=0;r<cs.T;++r)if(hc[r]!=cs.n[r]){std::printf("admit count mismatch case %zu r %d: %d vs %d\n",ci,r,hc[r],cs.n[r]);return 3;}
  q.memset(partR,0xff,PF*4).wait();q.memset(outR,0xff,size_t(TMAX)*24*256*4).wait();
  ref.tiles(q,s,make_args(outR),counts,partR);ref.combine(q,s,make_args(outR),counts,partR);q.wait();
  std::vector<uint32_t> oR(size_t(cs.T)*24*256),pR(PF);q.memcpy(oR.data(),outR,oR.size()*4).wait();q.memcpy(pR.data(),partR,PF*4).wait();
  for(auto&v:vars){
   if(std::strstr(v.name,"diag")||std::strstr(v.name,"probe")||std::strstr(v.name,"only")||std::strstr(v.name,"nobfly")||std::strstr(v.name,"empty"))continue;
   q.memset(partC,0xff,PF*4).wait();q.memset(outC,0xff,size_t(TMAX)*24*256*4).wait();
   v.tiles(q,s,make_args(outC),counts,partC);v.combine(q,s,make_args(outC),counts,partC);q.wait();
   std::vector<uint32_t> oC(oR.size()),pC(PF);q.memcpy(oC.data(),outC,oC.size()*4).wait();q.memcpy(pC.data(),partC,PF*4).wait();
   size_t od=0,pd=0;for(size_t i=0;i<oR.size();++i)od+=oR[i]!=oC[i];
   for(int r=0;r<cs.T;++r){int cnt=(cs.n[r]+31)/32;for(int h=0;h<24;++h)for(int c=0;c<cnt;++c){size_t b=(size_t(r*24+h)*C+c)*258;for(int k=0;k<258;++k)pd+=pR[b+k]!=pC[b+k];}}
   int err_h=0;q.memcpy(&err_h,err,4).wait();
   if(od||pd||err_h){++failures;std::printf("FAIL case %zu T=%d n0=%d mode=%d %s: out diff %zu partial diff %zu err %d\n",ci,cs.T,cs.n[0],cs.mode,v.name,od,pd,err_h);}
  }
 }
 std::printf("exactness: %d failures over %zu cases x %zu variants\n",failures,cases.size(),vars.size());
 // Timing at several slot counts (T=1).
 {
  fill(Q,size_t(TMAX)*24*256,1.f,0);fill(K,size_t(CAP)*512,1.f,0);fill(V,size_t(CAP)*512,1.f,0);
  const int position=CAP-1-TMAX;std::vector<int> perm(position+1);for(int i=0;i<=position;++i)perm[i]=i;std::shuffle(perm.begin(),perm.end(),rng);
  std::vector<Variant> all={ref};for(auto&v:vars)all.push_back(v);
  const char* nl=std::getenv("BENCH_N");std::vector<int> ns={2051};if(nl){ns.clear();for(const char* p=nl;*p;){ns.push_back(std::atoi(p));while(*p&&*p!=',')++p;if(*p)++p;}}
  for(int nn:ns){
   std::vector<int> hid(size_t(TMAX)*S,-1);for(int j=0;j<nn;++j)hid[j]=perm[j];q.memcpy(ids,hid.data(),hid.size()*4).wait();
   {int one=1,zero=0;q.memcpy(err,&zero,4).wait();q.memcpy(pos,&position,4).wait();q.memcpy(act,&one,4).wait();}
   ng::Shape s=base;s.tokens=1;p47::admit_fast(q,s,make_args(outR),counts).wait();
   {int hc=0;q.memcpy(&hc,counts,4).wait();if(hc!=nn){std::printf("timing admit count %d != %d\n",hc,nn);return 4;}}
   for(int i=0;i<200;++i){ref.tiles(q,s,make_args(outC),counts,partC);ref.combine(q,s,make_args(outC),counts,partC);}q.wait();
   for(auto&v:all){
    for(int cold=1;cold>=0;--cold){std::vector<double> tt,tc;
     for(int i=0;i<timing_iters+3;++i){
      if(cold&&!rflush)q.parallel_for(sycl::range<1>(FL),[=](sycl::id<1>k){flush[k]=flush[k]+1.f;});
      if(cold&&rflush)q.parallel_for(sycl::nd_range<1>(FL/16,256),[=](sycl::nd_item<1>it){const size_t b=it.get_global_linear_id()*16;float acc=0.f;for(int k=0;k<16;++k)acc+=flush[b+k];if(acc==12345.f)flush[0]=acc;});
      auto e1=v.tiles(q,s,make_args(outC),counts,partC);auto e2=v.combine(q,s,make_args(outC),counts,partC);
      double a=us(e1),b=us(e2);if(i>=3){tt.push_back(a);tc.push_back(b);}}
     std::sort(tt.begin(),tt.end());std::sort(tc.begin(),tc.end());
     std::printf("timing n=%4d %-16s %s tiles %8.2f us combine %7.2f us (min %7.2f / %6.2f)\n",nn,v.name,cold?"cold":"hot ",tt[tt.size()/2],tc[tc.size()/2],tt[0],tc[0]);}
   }
  }
 }
 return failures?1:0;
}
