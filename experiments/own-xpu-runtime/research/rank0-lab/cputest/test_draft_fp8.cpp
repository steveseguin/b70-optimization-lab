// CPU-device bitwise test (OpenCL CPU, GPU blocked) of OWNRT_DRAFT_EXPERTS_V2 (rank0-lab 2026-10-26): the engine's
// mtp36::fp8v2::rows<K,Pair> against a host replica of the production FP8 draft expert kernel (mtp_kernels.cpp
// Dense<K,2,Pair>: lane<K,2> per lane, adjacent-pair tree, bf16 output, NaN and status for invalid routes), for the gate/up
// pair (K=2560, 640 rows) and down (K=640, 2560 rows), 10 slots including an invalid and a partial route.
#include <sycl/sycl.hpp>
#include "stage2/packet194-expert-diet-engine/mtp_fp8_v2.hpp"
#include <cstdio>
#include <random>
#include <vector>
using iq3::Route;
// Verbatim arithmetic of mtp_kernels.cpp fp8_value / lane<K,2> / Dense<K,2,Pair> (host form).
static float fp8_value(uint8_t b){uint32_t e=(b>>3)&15,m=b&7;float x=e?iq3::bits_float(((e+120)<<23)|(m<<20)):float(m)*0x1p-9f;return b&128?-x:x;}
template<unsigned K> static float lane2(const uint8_t* w,const uint16_t* x,unsigned l){float sum=0;for(unsigned tile=l*8;tile<K;tile+=256)for(unsigned k=tile;k<std::min(tile+8,K);++k){
  const auto* s=w+K+(k/128)*4;uint32_t u=uint32_t(s[0])|(uint32_t(s[1])<<8)|(uint32_t(s[2])<<16)|(uint32_t(s[3])<<24);
  float value=iq3::bits_float(u)*fp8_value(w[k]);float product=value*iq3::bits_float(uint32_t(x[k])<<16);sum=sum+product;}return sum;}
template<unsigned K,bool Pair> int run(sycl::queue& q,unsigned rows,unsigned experts,std::mt19937& g){
 constexpr size_t rb=K+4*(K/128);const unsigned batch=10;
 std::uniform_int_distribution<int> code(0,255);std::uniform_real_distribution<float> u(-1.f,1.f),sc(1e-3f,2.f);
 auto weights=[&](){std::vector<uint8_t> w(size_t(experts)*rows*rb);for(size_t r=0;r<size_t(experts)*rows;++r){uint8_t* row=w.data()+r*rb;
  for(unsigned k=0;k<K;++k){int c;do c=code(g);while((c&0x7f)==0x7f);row[k]=uint8_t(c);}
  for(unsigned s=0;s<K/128;++s){float f=sc(g);std::memcpy(row+K+4*s,&f,4);}}return w;};
 auto w=weights();auto pw=Pair?weights():w;
 std::vector<uint16_t> x(size_t(Pair?1:batch)*K);for(auto& v:x)v=iq3::bf16_bits(u(g));
 std::vector<Route> routes(batch);for(unsigned s=0;s<batch;++s)routes[s]={uint32_t(g()%experts),0,rows};
 routes[3]={experts+5,0,rows};routes[7]={uint32_t(1%experts),0,rows/2}; // invalid expert; partial rows
 // host reference
 const size_t n=size_t(rows)*batch;std::vector<uint16_t> wy(n),wpy(n);std::vector<uint32_t> ws(batch,77),wps(batch,77);
 for(size_t i=0;i<n;++i){unsigned slot=unsigned(i/rows),row=unsigned(i%rows);auto r=routes[slot];bool valid=iq3::valid_route(r,experts,rows,rows)&&row<r.row_count;
  float s[32]{},p[32]{};if(valid)for(unsigned l=0;l<32;++l){size_t off=(size_t(r.expert_id)*rows+r.row_begin+row)*rb;const uint16_t* xx=x.data()+(Pair?0:size_t(slot)*K);s[l]=lane2<K>(w.data()+off,xx,l);if(Pair)p[l]=lane2<K>(pw.data()+off,xx,l);}
  for(unsigned width=1;width<32;width*=2)for(unsigned l=0;l<32;l+=2*width){s[l]=s[l]+s[l+width];p[l]=p[l]+p[l+width];}
  wy[i]=iq3::bf16_bits(valid?s[0]:iq3::bits_float(0x7fc00000));if(Pair)wpy[i]=iq3::bf16_bits(valid?p[0]:iq3::bits_float(0x7fc00000));if(row==0){ws[slot]=!valid;if(Pair)wps[slot]=!valid;}}
 // device
 auto* dw=sycl::malloc_device<uint8_t>(w.size(),q);auto* dp=sycl::malloc_device<uint8_t>(pw.size(),q);auto* dx=sycl::malloc_device<uint16_t>(x.size(),q);
 auto* dy=sycl::malloc_device<uint16_t>(n,q);auto* dpy=sycl::malloc_device<uint16_t>(n,q);auto* dr=sycl::malloc_device<Route>(batch,q);auto* ds=sycl::malloc_device<uint32_t>(batch,q);auto* dps=sycl::malloc_device<uint32_t>(batch,q);
 q.memcpy(dw,w.data(),w.size()).wait();q.memcpy(dp,pw.data(),pw.size()).wait();q.memcpy(dx,x.data(),x.size()*2).wait();q.memcpy(dr,routes.data(),batch*sizeof(Route)).wait();
 q.memset(dy,0xff,n*2).wait();q.memset(dpy,0xff,n*2).wait();std::vector<uint32_t> seventy(batch,77);q.memcpy(ds,seventy.data(),batch*4).wait();q.memcpy(dps,seventy.data(),batch*4).wait();
 mtp36::fp8v2::Rows b{dw,dp,dx,dy,dpy,dr,ds,dps,rows,batch,experts};
 q.parallel_for(sycl::nd_range<1>(((n+3)/4)*128,128),[=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{mtp36::fp8v2::rows<K,Pair>(b,n,it);}).wait();
 std::vector<uint16_t> gy(n),gpy(n);std::vector<uint32_t> gs(batch),gps(batch);
 q.memcpy(gy.data(),dy,n*2).wait();q.memcpy(gpy.data(),dpy,n*2).wait();q.memcpy(gs.data(),ds,batch*4).wait();q.memcpy(gps.data(),dps,batch*4).wait();
 size_t bad=0,unwritten=0;for(size_t i=0;i<n;++i){bad+=gy[i]!=wy[i];if(Pair)bad+=gpy[i]!=wpy[i];unwritten+=gy[i]==0xffff;}bad+=unwritten;for(unsigned s=0;s<batch;++s){bad+=gs[s]!=ws[s];if(Pair)bad+=gps[s]!=wps[s];}
 std::printf("  K=%u pair=%d rows=%u experts=%u: outputs %zu, mismatches %zu %s\n",K,int(Pair),rows,experts,n*(Pair?2:1),bad,bad?"FAIL":"ok");
 for(void* p:{(void*)dw,(void*)dp,(void*)dx,(void*)dy,(void*)dpy,(void*)dr,(void*)ds,(void*)dps})sycl::free(p,q);
 return bad!=0;
}
int main(){
 sycl::queue q{sycl::device{sycl::cpu_selector_v},sycl::property::queue::in_order{}};
 std::printf("device: %s\n",q.get_device().get_info<sycl::info::device::name>().c_str());
 std::mt19937 g(2026);int f=0;
 f+=run<2560,true>(q,640,12,g);f+=run<640,false>(q,2560,12,g);f+=run<2560,false>(q,640,12,g);f+=run<640,true>(q,2560,12,g);
 std::printf("%s\n",f?"FAILED":"ALL PASSED");return f;
}
