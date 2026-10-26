// Lab microbenchmark for QSA select (2026-10-26): exactness of ids (a.i(2)) and scores vs the canonical TOPK path and
// the original all-pairs kernel; device timing per stage.
#include "select_ref.hpp"
#include "select_diag.hpp"
#if __has_include("stage2/packet194-expert-diet-engine/select_fast.hpp")
#include "stage2/packet194-expert-diet-engine/select_fast.hpp"
#include "select_fast_diag.hpp"
#define HAVE_FAST 1
#endif
#include <atomic>
#include <cstdio>
#include <cstring>
#include <random>
#include <algorithm>
#include <functional>
namespace ownrt { std::uint64_t next_handle(){static std::atomic<std::uint64_t> n{1};return n.fetch_add(1);} }
using namespace specialised;
static double us(sycl::event e){e.wait();auto a=e.get_profiling_info<sycl::info::event_profiling::command_start>();auto b=e.get_profiling_info<sycl::info::event_profiling::command_end>();return double(b-a)/1000.0;}
using Fn=std::function<sycl::event(sycl::queue&,ng::Shape,ng::Args,float*)>;
struct Variant{const char* name;Fn s0;Fn s1;bool exact=true;};
static sycl::event ref_s0(sycl::queue&q,ng::Shape s,ng::Args a,float*scratch){s.op=ng::select;auto n=work_items(s,0);
 return q.parallel_for(sycl::range<1>(n),[=](sycl::id<1> i){select_scores_item(s,a,i[0],scratch,Guard{});});}
template<int Phase>static sycl::event ref_s1p(sycl::queue&q,ng::Shape s,ng::Args a,float*scratch){s.op=ng::select;
 return q.submit([&](sycl::handler& h){sycl::local_accessor<int,1> idx(sycl::range<1>(size_t(s.budget/4)),h);sycl::local_accessor<float,1> val(sycl::range<1>(size_t(s.budget/4)),h);
  sycl::local_accessor<int,1> hist(sycl::range<1>(2048),h);sycl::local_accessor<int,1> found(sycl::range<1>(2),h);
  h.parallel_for(sycl::nd_range<1>(sycl::range<1>(size_t(s.tokens)*1024),sycl::range<1>(1024)),[=](sycl::nd_item<1> it){
   if constexpr(Phase==0)select_topk_row(s,a,it,scratch,idx.get_multi_ptr<sycl::access::decorated::no>().get(),val.get_multi_ptr<sycl::access::decorated::no>().get(),hist.get_multi_ptr<sycl::access::decorated::no>().get(),found.get_multi_ptr<sycl::access::decorated::no>().get(),Guard{});
   else select_topk_row_diag<Phase>(s,a,it,scratch,idx.get_multi_ptr<sycl::access::decorated::no>().get(),val.get_multi_ptr<sycl::access::decorated::no>().get(),hist.get_multi_ptr<sycl::access::decorated::no>().get(),found.get_multi_ptr<sycl::access::decorated::no>().get(),Guard{});});});}
static sycl::event allpairs_s1(sycl::queue&q,ng::Shape s,ng::Args a,float*scratch){s.op=ng::select;auto n=work_items(s,1);
 return q.parallel_for(sycl::nd_range<1>(sycl::range<1>(n*32),sycl::range<1>(32)),[=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{select_rows<1>(s,a,it,scratch,Guard{});});}

int main(int argc,char**argv){
 const int iters=argc>1?std::atoi(argv[1]):30;const char* only=argc>2?argv[2]:nullptr;
 sycl::queue q{sycl::gpu_selector_v,sycl::property_list{sycl::property::queue::in_order(),sycl::property::queue::enable_profiling()}};
 std::printf("device %s\n",q.get_device().get_info<sycl::info::device::name>().c_str());
 const int CTX=65536,CAP=CTX/4,TMAX=32,S=2051;
 auto dm=[&](size_t bytes){void* p=sycl::malloc_device(bytes,q);if(!p)std::exit(2);q.memset(p,0,bytes).wait();return p;};
 float* Qy=(float*)dm(size_t(TMAX)*4*128*4);float* Kp=(float*)dm(size_t(CAP)*128*4);
 int* idsR=(int*)dm(size_t(TMAX)*S*4);int* idsC=(int*)dm(size_t(TMAX)*S*4);int* err=(int*)dm(64);int* pos=(int*)dm(64);int* act=(int*)dm(64);
 float* scR=(float*)dm(size_t(TMAX)*CAP*4);float* scC=(float*)dm(size_t(TMAX)*CAP*4);
 const size_t FL=size_t(64)<<20;float* flush=(float*)dm(FL*4);
 std::mt19937 rng(77);
 auto args=[&](int* ids){ng::Args a;a.f32=true;a.p[0]=Qy;a.p[1]=Kp;a.p[2]=ids;a.p[15]=err;a.p[17]=pos;a.p[18]=act;return a;};
 auto shape=[&](int T,int position){ng::Shape s{ng::select,T,2560,4,0,ng::f32_activations_flag,CTX,2048,0};s.extent=std::min(CTX,((position+T-1+32)/32)*32);return s;};
 Variant ref{"ref",ref_s0,ref_s1p<0>};
 std::vector<Variant> vars;
 vars.push_back({"allpairs",ref_s0,allpairs_s1});
#ifdef HAVE_FAST
#include "bench_variants.inc"
#endif
 if(only){std::vector<Variant> k;for(auto&v:vars)if(std::strstr(v.name,only))k.push_back(v);vars=k;}
 // mode 0: normal keys; 1: many exact ties (7 repeating block patterns, every third block zero); 2: almost all zero
 auto fill=[&](int mode){std::normal_distribution<float> nd(0.f,1.f);std::vector<float> qh(size_t(TMAX)*512),kh(size_t(CAP)*128);
  for(auto&x:qh)x=nd(rng);
  for(size_t b=0;b<size_t(CAP);++b)for(int j=0;j<128;++j){float v=nd(rng);
   if(mode==1){v=float(int((b%7)*13+j*5)%17-8)/8.f;if(b%3==0)v=0.f;}
   if(mode==2&&b%97!=5)v=0.f;
   kh[b*128+j]=v;}
  q.memcpy(Qy,qh.data(),qh.size()*4).wait();q.memcpy(Kp,kh.data(),kh.size()*4).wait();};
 auto setpos=[&](int position){int one=1,zero=0;q.memcpy(err,&zero,4).wait();q.memcpy(pos,&position,4).wait();q.memcpy(act,&one,4).wait();};
 struct Case{int T;int position;int mode;};
 std::vector<Case> cases={{1,0,0},{1,2,0},{1,3,0},{1,100,0},{1,2046,0},{1,2047,0},{1,2048,0},{1,2051,0},{1,4095,0},{1,4096,0},{1,4099,0},
  {1,30000,0},{1,65530,0},{2,4096,0},{2,2047,0},{1,4096,1},{1,30000,1},{2,9999,1},{1,4096,2},{1,30000,2},{1,1500,2},{32,4000,0},{32,2030,0},{32,29990,1},{32,0,0}};
 int failures=0;
 if(!std::getenv("BENCH_SKIP_EXACT"))for(size_t ci=0;ci<cases.size();++ci){auto cs=cases[ci];fill(cs.mode);setpos(cs.position);ng::Shape s=shape(cs.T,cs.position);
  q.memset(idsR,0x7f,size_t(TMAX)*S*4).wait();q.memset(scR,0xff,size_t(TMAX)*CAP*4).wait();
  ref.s0(q,s,args(idsR),scR);ref.s1(q,s,args(idsR),scR);q.wait();int eR=0;q.memcpy(&eR,err,4).wait();
  std::vector<int> iR(size_t(TMAX)*S);q.memcpy(iR.data(),idsR,iR.size()*4).wait();std::vector<uint32_t> sR(size_t(TMAX)*CAP);q.memcpy(sR.data(),scR,sR.size()*4).wait();
  for(auto&v:vars){if(!v.exact)continue;setpos(cs.position);
   q.memset(idsC,0x7f,size_t(TMAX)*S*4).wait();q.memset(scC,0xff,size_t(TMAX)*CAP*4).wait();
   v.s0(q,s,args(idsC),scC);v.s1(q,s,args(idsC),scC);q.wait();int eC=0;q.memcpy(&eC,err,4).wait();
   std::vector<int> iC(iR.size());q.memcpy(iC.data(),idsC,iC.size()*4).wait();std::vector<uint32_t> sC(sR.size());q.memcpy(sC.data(),scC,sC.size()*4).wait();
   size_t di=0,ds=0;for(size_t i=0;i<size_t(cs.T)*S;++i)di+=iR[i]!=iC[i];
   for(int r=0;r<cs.T;++r){int n=(cs.position+r+1)/4;for(int b=0;b<n;++b)ds+=sR[size_t(r)*CAP+b]!=sC[size_t(r)*CAP+b];}
   if(di||ds||eR!=eC){++failures;std::printf("FAIL case %zu T=%d pos=%d mode=%d %s: ids diff %zu score diff %zu err %d/%d\n",ci,cs.T,cs.position,cs.mode,v.name,di,ds,eR,eC);}
  }
  if(ci==11||ci==16||ci==19){int sel=0;for(int i=0;i<S;++i)sel+=iR[i]>=0;std::printf("case %zu pos=%d mode=%d err=%d: %d ids set, first %d %d %d %d\n",ci,cs.position,cs.mode,eR,sel,iR[0],iR[1],iR[2],iR[3]);}
 }
 std::printf("exactness: %d failures over %zu cases x %zu variants\n",failures,cases.size(),vars.size());
 const char* pl=std::getenv("BENCH_POS");std::vector<int> ps={4096,30000};if(pl){ps.clear();for(const char* p=pl;*p;){ps.push_back(std::atoi(p));while(*p&&*p!=',')++p;if(*p)++p;}}
 std::vector<Variant> all={ref};
 if(std::getenv("BENCH_PHASES"))for(int ph=1;ph<=4;++ph){static const char* nm[]={"","s1_phase1_finite","s1_phase2_radix0","s1_phase3_radix3","s1_phase4_compact"};
  Fn f=ph==1?Fn(ref_s1p<1>):ph==2?Fn(ref_s1p<2>):ph==3?Fn(ref_s1p<3>):Fn(ref_s1p<4>);all.push_back({nm[ph],ref_s0,f,false});}
 for(auto&v:vars)all.push_back(v);
 for(int position:ps){fill(0);setpos(position);ng::Shape s=shape(1,position);
  for(int i=0;i<100;++i){ref.s0(q,s,args(idsC),scC);ref.s1(q,s,args(idsC),scC);}q.wait();
  for(auto&v:all){for(int cold=1;cold>=0;--cold){std::vector<double> a0,a1;
   for(int i=0;i<iters+3;++i){setpos(position);
    if(cold)q.parallel_for(sycl::nd_range<1>(FL/16,256),[=](sycl::nd_item<1>it){const size_t b=it.get_global_linear_id()*16;float acc=0.f;for(int k=0;k<16;++k)acc+=flush[b+k];if(acc==12345.f)flush[0]=acc;});
    auto e0=v.s0(q,s,args(idsC),scC);auto e1=v.s1(q,s,args(idsC),scC);double t0=us(e0),t1=us(e1);if(i>=3){a0.push_back(t0);a1.push_back(t1);}}
   std::sort(a0.begin(),a0.end());std::sort(a1.begin(),a1.end());
   std::printf("timing pos=%5d %-20s %s stage0 %8.2f us stage1 %8.2f us (min %7.2f / %7.2f)\n",position,v.name,cold?"cold":"hot ",a0[a0.size()/2],a1[a1.size()/2],a0[0],a1[0]);}}
 }
 return failures?1:0;
}
