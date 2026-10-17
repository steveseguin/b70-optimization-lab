// CPU-buildable SYCL diagnostic; run only by the device coordinator in an
// admitted idle-card window. All initialization precedes event timing.
#include <sycl/sycl.hpp>
#include "p74_packed.hpp"
#include <iostream>
#include <vector>
#include <algorithm>
#include <chrono>
#include <iomanip>
struct DeviceFree { sycl::queue&q;std::vector<void*> p;~DeviceFree(){q.wait_and_throw();for(auto x:p)sycl::free(x,q);} };
template<bool Packed,unsigned Split,bool Check=false>sycl::event launch(sycl::queue&q,const uint8_t*w,const uint16_t*x,float*y,unsigned rows){
 constexpr unsigned K=2560;constexpr size_t rb=Packed?2100:3380;
 return q.submit([&](sycl::handler&h){
  if constexpr(Split==1){h.parallel_for(sycl::nd_range<1>(size_t(rows)*32,Packed?256:32),[=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
   unsigned row=it.get_global_linear_id()/32,lane=it.get_local_linear_id()%32;auto sg=it.get_sub_group();
   float v;if constexpr(Packed)v=p74::lane<iq3::Type::Q6_K,K>(w+row*rb,x,0,K,lane);else v=p33::dense_lane<iq3::Type::Q6_K,K>(w+row*rb,x,0,K,lane);
   for(unsigned width=1;width<32;width*=2){float rhs=sycl::select_from_group(sg,v,(lane+width)%32);if(lane%(2*width)==0)v=v+rhs;}if(!lane){if constexpr(Check)y[row]=v;else reinterpret_cast<uint16_t*>(y)[row]=iq3::bf16_bits(v);}
  });}else {sycl::local_accessor<float,1>partials(4,h);h.parallel_for(sycl::nd_range<1>(size_t(rows)*128,128),[=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
   unsigned row=it.get_group_linear_id(),part=it.get_local_linear_id()/32,lane=it.get_local_linear_id()%32;auto sg=it.get_sub_group();auto bounds=iq3::kopt2::bounds(K,part,4);
   float v;if constexpr(Packed)v=p74::lane<iq3::Type::Q6_K,K>(w+row*rb,x,bounds.first,bounds.second,lane);else v=p33::dense_lane<iq3::Type::Q6_K,K>(w+row*rb,x,bounds.first,bounds.second,lane);
   for(unsigned width=1;width<32;width*=2){float rhs=sycl::select_from_group(sg,v,(lane+width)%32);if(lane%(2*width)==0)v=v+rhs;}if(!lane)partials[part]=v;it.barrier(sycl::access::fence_space::local_space);if(it.get_local_linear_id()==0)y[row]=(partials[0]+partials[1])+(partials[2]+partials[3]);
  });}
 });
}
template<unsigned S>void shape(sycl::queue&q,unsigned rows){
 constexpr unsigned K=2560;DeviceFree free{q,{}};
 auto alloc=[&](size_t bytes){auto p=sycl::malloc_device(bytes,q);if(!p)throw std::bad_alloc();free.p.push_back(p);return p;};
 auto*p=(uint8_t*)alloc(size_t(rows)*2100);auto*e=(uint8_t*)alloc(size_t(rows)*3380);auto*x=(uint16_t*)alloc(K*2);auto*a=(float*)alloc(rows*4);auto*b=(float*)alloc(rows*4);
 std::vector<uint16_t> input(K);for(unsigned i=0;i<K;++i)input[i]=iq3::bf16_bits(float(int(i%31)-15)/16.f);q.memcpy(x,input.data(),K*2).wait_and_throw();
 uint32_t state=74;
 for(unsigned first=0;first<rows;first+=256){unsigned n=std::min(256u,rows-first);std::vector<uint8_t> raw(size_t(n)*2100);for(auto&v:raw){state^=state<<13;state^=state>>17;state^=state<<5;v=state;}for(size_t block=0;block<raw.size()/210;++block){uint16_t half=0x2400+(block%1024);std::memcpy(raw.data()+block*210+208,&half,2);}auto expanded=iq3::expanded::expand(iq3::Type::Q6_K,raw.data(),raw.size(),K);q.memcpy(p+size_t(first)*2100,raw.data(),raw.size()).wait_and_throw();q.memcpy(e+size_t(first)*3380,expanded.data(),expanded.size()).wait_and_throw();}
 launch<false,S,true>(q,e,x,a,rows).wait_and_throw();launch<true,S,true>(q,p,x,b,rows).wait_and_throw();std::vector<float> expected(rows),actual(rows);q.memcpy(expected.data(),a,rows*4).wait_and_throw();q.memcpy(actual.data(),b,rows*4).wait_and_throw();if(std::memcmp(expected.data(),actual.data(),rows*4))throw std::runtime_error("device FP32 identity failed");
 // Alternating ordering, whole-event plus submission/wait wall time. One
 // launch per sample; no separate decoder, no omitted partial reduction.
 for(unsigned rep=0;rep<20;++rep)for(unsigned arm=0;arm<2;++arm){bool packed=bool(arm^(rep&1));auto start=std::chrono::steady_clock::now();auto ev=packed?launch<true,S>(q,p,x,b,rows):launch<false,S>(q,e,x,a,rows);ev.wait_and_throw();double wall=std::chrono::duration<double,std::micro>(std::chrono::steady_clock::now()-start).count();auto ns=ev.template get_profiling_info<sycl::info::event_profiling::command_end>()-ev.template get_profiling_info<sycl::info::event_profiling::command_start>();std::cout<<"{\"rows\":"<<rows<<",\"columns\":2560,\"split\":"<<S<<",\"packed\":"<<(packed?"true":"false")<<",\"repeat\":"<<rep<<",\"launches\":1,\"event_us\":"<<ns/1000.0<<",\"wall_us\":"<<wall<<",\"weight_read_bytes\":"<<size_t(rows)*(packed?2100:3200)<<",\"weight_resident_bytes\":"<<size_t(rows)*(packed?2100:3380)<<",\"exact_fp32\":true,\"diagnostic_only\":true}\n";}
}
int main(int argc,char**argv){try{if(argc!=2||std::string(argv[1])!="--coordinator-admitted-device-window")throw std::runtime_error("requires coordinator admission; no automatic device run");sycl::queue q(sycl::gpu_selector_v,{sycl::property::queue::enable_profiling{},sycl::property::queue::in_order{}});shape<1>(q,248320);shape<1>(q,10240);return 0;}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
