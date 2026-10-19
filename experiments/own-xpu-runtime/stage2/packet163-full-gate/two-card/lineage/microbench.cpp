// Isolated diagnostic only. Uses the shipped operation bodies for event timing.
#include "build/micro-production.hpp"
#include "p93_kernel.hpp"
#include <csignal>
#include <atomic>
#include <iostream>
#include <chrono>
#include <algorithm>
#include <iomanip>
// Same host handle helper as owner.cpp; prepared capture is inactive here.
namespace ownrt {std::uint64_t next_handle(){static std::atomic<std::uint64_t> n{1};return n.fetch_add(1);}}
static volatile std::sig_atomic_t stopped=0;
static void stop(int){stopped=1;}
static void guard(){if(stopped)throw std::runtime_error("coordinator graceful stop");}
struct Buffers{sycl::queue&q;std::vector<void*> values;~Buffers(){try{q.wait_and_throw();}catch(...){}for(auto p:values)sycl::free(p,q);}void*alloc(size_t bytes){auto*p=sycl::malloc_device(bytes,q);if(!p)throw std::bad_alloc();values.push_back(p);return p;}};
template<unsigned Mode>sycl::event fp32(sycl::queue&q,const uint8_t*w,const uint16_t*x,float*y,unsigned rows){return q.submit([&](sycl::handler&h){h.parallel_for(sycl::nd_range<1>(size_t(rows)*32,32),[=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
 unsigned row=it.get_group_linear_id(),l=it.get_local_linear_id();auto sg=it.get_sub_group();float v;
 if constexpr(Mode==0)v=p33::dense_lane<iq3::Type::Q6_K,2560>(w+size_t(row)*3380,x,0,2560,l);
 else v=p93::lane<Mode>(w,size_t(rows)*10,row,x,0,2560,l);
 for(unsigned width=1;width<32;width*=2){float rhs=sycl::select_from_group(sg,v,(l+width)%32);if(l%(2*width)==0)v=v+rhs;}if(!l)y[row]=v;
 });});}
int main(int argc,char**argv){try{
 if(argc!=2||std::string(argv[1])!="--coordinator-admitted-device-window")throw std::runtime_error("coordinator admission required");
 std::signal(SIGTERM,stop);std::signal(SIGINT,stop);
 constexpr unsigned rows=248320,K=2560;constexpr size_t blocks=size_t(rows)*10;
 sycl::queue q(sycl::gpu_selector_v,{sycl::property::queue::enable_profiling{},sycl::property::queue::in_order{}});
 std::cout<<"{\"kind\":\"device\",\"single_device\":true,\"rows\":248320,\"columns\":2560}\n"<<std::flush;
 {Buffers buf{q,{}};auto*raw=static_cast<uint8_t*>(buf.alloc(blocks*210));auto*expanded=static_cast<uint8_t*>(buf.alloc(size_t(rows)*3380));auto*trans=static_cast<uint8_t*>(buf.alloc(blocks*210));auto*x=static_cast<uint16_t*>(buf.alloc(K*2));
  auto*ye=static_cast<uint16_t*>(buf.alloc(rows*2));auto*ya=static_cast<uint16_t*>(buf.alloc(rows*2));auto*fe=static_cast<float*>(buf.alloc(rows*4));auto*fa=static_cast<float*>(buf.alloc(rows*4));
  uint32_t seed=93;auto next=[&]{seed=seed*1664525u+1013904223u;return seed;};std::vector<uint16_t>input(K);for(auto&v:input)v=iq3::bf16_bits(float(int(next()%63)-31)/32.f);q.memcpy(x,input.data(),K*2).wait_and_throw();
  for(unsigned first=0;first<rows;first+=256){guard();unsigned n=std::min(256u,rows-first);size_t nb=size_t(n)*10;std::vector<uint8_t>r(nb*210);for(auto&v:r)v=next()>>24;for(size_t b=0;b<nb;++b){uint16_t h=0x2400+(next()%1024);std::memcpy(r.data()+b*210+208,&h,2);}auto e=iq3::expanded::expand(iq3::Type::Q6_K,r.data(),r.size(),K);auto t=p93::transpose(r.data(),nb);
   q.memcpy(raw+size_t(first)*2100,r.data(),r.size()).wait_and_throw();q.memcpy(expanded+size_t(first)*3380,e.data(),e.size()).wait_and_throw();
   const size_t widths[4]={128,64,16,2},starts[4]={0,128,192,208};for(unsigned plane=0;plane<4;++plane)q.memcpy(trans+starts[plane]*blocks+size_t(first)*10*widths[plane],t.data()+starts[plane]*nb,widths[plane]*nb).wait_and_throw();
  }
  p33::Kernel<0,iq3::Type::Q6_K,K,1>production;production.b.rb=3380;production.b.rows=rows;production.b.count=1;production.b.experts=1;production.b.has_routes=false;
  std::array<void*,9>pp{expanded,expanded,x,ye,ye,x,ye,ye,fe};p93::Kernel<1>plane;plane.rows=rows;p93::Kernel<2>transpose;transpose.rows=rows;
  std::array<void*,3>pa{raw,x,ya},ta{trans,x,ya};
  auto launch=[&](unsigned mode){return mode==0?production.submit(q,pp,{}):mode==1?plane.submit(q,pa,{}):transpose.submit(q,ta,{});};
  fp32<0>(q,expanded,x,fe,rows).wait_and_throw();launch(0).wait_and_throw();std::vector<float>expected(rows),actual(rows);std::vector<uint16_t>ey(rows),ay(rows);q.memcpy(expected.data(),fe,rows*4).wait_and_throw();q.memcpy(ey.data(),ye,rows*2).wait_and_throw();
  auto argmax=[](const auto&y){unsigned best=0;for(unsigned i=1;i<y.size();++i)if(iq3::bits_float(uint32_t(y[i])<<16)>iq3::bits_float(uint32_t(y[best])<<16))best=i;return best;};
  for(unsigned mode=1;mode<=2;++mode){guard();const char*name=mode==1?"head-plane":"head-transpose";if(mode==1)fp32<1>(q,raw,x,fa,rows).wait_and_throw();else fp32<2>(q,trans,x,fa,rows).wait_and_throw();launch(mode).wait_and_throw();q.memcpy(actual.data(),fa,rows*4).wait_and_throw();q.memcpy(ay.data(),ya,rows*2).wait_and_throw();
   if(std::memcmp(expected.data(),actual.data(),rows*4)||ey!=ay||argmax(ey)!=argmax(ay))throw std::runtime_error("device FP32/BF16/argmax mismatch");
   std::cout<<"{\"kind\":\"correctness\",\"view\":\""<<name<<"\",\"rows\":248320,\"columns\":2560,\"fp32_exact\":true,\"bf16_exact\":true,\"argmax_exact\":true}\n"<<std::flush;
   for(unsigned rep=0;rep<40;++rep)for(unsigned pos=0;pos<2;++pos){guard();unsigned arm=(pos^(rep&1))?mode:0;auto start=std::chrono::steady_clock::now();auto event=launch(arm);event.wait_and_throw();auto ns=event.get_profiling_info<sycl::info::event_profiling::command_end>()-event.get_profiling_info<sycl::info::event_profiling::command_start>();double wall=std::chrono::duration<double,std::nano>(std::chrono::steady_clock::now()-start).count();
    std::cout<<"{\"kind\":\"sample\",\"pair\":\""<<name<<"\",\"view\":\""<<(arm?name:"production")<<"\",\"repeat\":"<<rep<<",\"position\":"<<pos<<",\"event_ns\":"<<ns<<",\"wall_ns\":"<<std::setprecision(17)<<wall<<",\"rows\":248320,\"columns\":2560,\"wg\":32,\"sg\":32,\"diagnostic_only\":true}\n"<<std::flush;
   }
  }q.wait_and_throw();guard();
 }
 std::cout<<"{\"kind\":\"summary\",\"passed\":true,\"drained\":true,\"rows\":248320,\"columns\":2560,\"diagnostic_only\":true}\n"<<std::flush;return 0;
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
