#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet102-iq2-ilp/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet102-iq2-ilp/microbench.cpp"
// Coordinator-only synthetic diagnostic, actual full expert operation bodies.
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet102-iq2-ilp/build/checked/experiments/own-xpu-runtime/stage2/packet102-iq2-ilp/p102_expert.hpp"
#include <atomic>
#include <csignal>
#include <iostream>
#include <chrono>
#include <iomanip>
#include <cstring>
namespace ownrt {std::uint64_t next_handle(){static std::atomic<std::uint64_t> n{1};return n.fetch_add(1);}}
static volatile std::sig_atomic_t stopped=0;
static void stop(int){stopped=1;}
static void guard(){if(stopped)throw std::runtime_error("coordinator graceful stop");}
struct Buffers{
 sycl::queue&q;std::vector<void*> values;
 ~Buffers(){try{q.wait_and_throw();}catch(...){}for(auto p:values)sycl::free(p,q);}
 void*alloc(size_t bytes){auto*p=sycl::malloc_device(bytes,q);if(!p)throw std::bad_alloc();values.push_back(p);return p;}
};
const char*names[]={"production","exp-lookup-batch2","exp-lookup-batch4","exp-gateup-shared","exp-lookup-batch2-shared","exp-lookup-batch4-shared"};
template<iq3::Type T,unsigned K,unsigned Rows>void bench(sycl::queue&q){
 constexpr bool paired=T==iq3::Type::IQ2_S;constexpr unsigned Experts=512,Count=10;
 constexpr size_t rb=p49bgemv::layout(T,K).row_bytes;
 constexpr size_t cached_rb=paired?p90::expert_stride(K):rb;
 constexpr size_t total_rows=size_t(Rows)*Experts;
 Buffers b{q,{}};
 auto*w=static_cast<uint8_t*>(b.alloc(total_rows*rb));
 auto*peer=paired?static_cast<uint8_t*>(b.alloc(total_rows*rb)):w;
 auto*cw=paired?static_cast<uint8_t*>(b.alloc(total_rows*cached_rb)):w;
 auto*cp=paired?static_cast<uint8_t*>(b.alloc(total_rows*cached_rb)):w;
 auto*x=static_cast<uint16_t*>(b.alloc(K*(paired?1:Count)*2));
 auto*y=b.alloc(Rows*Count*2),*py=b.alloc(Rows*Count*2);
 auto*routes=b.alloc(Count*sizeof(iq3::Route)),*status=b.alloc(Count*4),*peer_status=b.alloc(Count*4);
 auto*error=b.alloc(4),*active=b.alloc(4);
 uint32_t seed=102;auto next=[&]{seed=seed*1664525u+1013904223u;return seed;};
 const auto source_rb=p49bgemv::source_row_bytes(T,K);const auto block=iq3::layout(T);
 for(unsigned stream=0;stream<(paired?2u:1u);++stream)for(size_t first=0;first<total_rows;first+=128){
  guard();size_t n=std::min(size_t(128),total_rows-first);std::vector<uint8_t>raw(source_rb),packed(n*rb),cached(n*cached_rb);
  for(size_t row=0;row<n;++row){for(auto&v:raw)v=next()>>24;for(size_t at=0;at<source_rb;at+=block.bytes){uint16_t half=0x2000+next()%4096;std::memcpy(raw.data()+at,&half,2);}
   p49bgemv::repack_row(T,K,raw.data(),packed.data()+row*rb);
   if constexpr(paired)p90::expert_repack(K,raw.data(),cached.data()+row*cached_rb);
  }
  q.memcpy((stream?peer:w)+first*rb,packed.data(),packed.size()).wait_and_throw();
  if constexpr(paired)q.memcpy((stream?cp:cw)+first*cached_rb,cached.data(),cached.size()).wait_and_throw();
 }
 std::vector<uint16_t>input(K*(paired?1:Count));for(auto&v:input)v=iq3::bf16_bits(float(int(next()%63)-31)/32.f);
 q.memcpy(x,input.data(),input.size()*2).wait_and_throw();
 iq3::Route selected[Count];for(unsigned i=0;i<Count;++i)selected[i]={uint32_t((37*i+19)%Experts),0,Rows};
 q.memcpy(routes,selected,sizeof(selected)).wait_and_throw();uint32_t zero=0,one=1;
 q.memcpy(error,&zero,4).wait_and_throw();q.memcpy(active,&one,4).wait_and_throw();
 std::array<void*,19>p{};p[0]=w;p[1]=peer;p[2]=x;p[3]=y;p[4]=py;p[5]=routes;p[6]=status;p[7]=peer_status;p[16]=error;p[17]=active;
 p90exp::Kernel<T,K,64,false,true> production;
 auto launch=[&](unsigned mode){auto a=p;a[0]=cw;a[1]=cp;
  switch(mode){
   case 1:{p102::Kernel<2,false> k;return k.submit(q,a,{});}
   case 2:{p102::Kernel<4,false> k;return k.submit(q,a,{});}
   case 3:{p102::Kernel<1,true> k;return k.submit(q,a,{});}
   case 4:{p102::Kernel<2,true> k;return k.submit(q,a,{});}
   case 5:{p102::Kernel<4,true> k;return k.submit(q,a,{});}
  }return production.submit(q,a,{});
 };
 auto bytes=[&]{std::vector<uint8_t>r(Rows*Count*2*(paired?2:1)+Count*4*(paired?2:1)+4);size_t off=0;
  auto copy=[&](const void*src,size_t n){q.memcpy(r.data()+off,src,n).wait_and_throw();off+=n;};
  copy(y,Rows*Count*2);if constexpr(paired)copy(py,Rows*Count*2);copy(status,Count*4);if constexpr(paired)copy(peer_status,Count*4);copy(error,4);return r;
 };
 auto poison=[&]{q.memset(y,0xa5,Rows*Count*2);q.memset(py,0xa5,Rows*Count*2);q.memset(status,0xa5,Count*4);q.memset(peer_status,0xa5,Count*4).wait_and_throw();};
 poison();launch(0).wait_and_throw();auto expected=bytes();
 for(unsigned mode=1;mode<6;++mode){guard();poison();launch(mode).wait_and_throw();if(bytes()!=expected)throw std::runtime_error("expert output/status byte mismatch");
  std::cout<<"{\"kind\":\"correctness\",\"view\":\""<<names[mode]<<"\",\"rows\":"<<Rows<<",\"columns\":"<<K<<",\"experts\":512,\"selected_experts\":10,\"bf16_exact\":true,\"status_exact\":true}\n"<<std::flush;
  for(unsigned rep=0;rep<40;++rep)for(unsigned pos=0;pos<2;++pos){guard();unsigned arm=(pos^(rep&1))?mode:0;auto start=std::chrono::steady_clock::now();auto event=launch(arm);event.wait_and_throw();auto ns=event.template get_profiling_info<sycl::info::event_profiling::command_end>()-event.template get_profiling_info<sycl::info::event_profiling::command_start>();double wall=std::chrono::duration<double,std::nano>(std::chrono::steady_clock::now()-start).count();
   std::cout<<"{\"kind\":\"sample\",\"pair\":\""<<names[mode]<<"\",\"view\":\""<<names[arm]<<"\",\"repeat\":"<<rep<<",\"position\":"<<pos<<",\"event_ns\":"<<ns<<",\"wall_ns\":"<<std::setprecision(17)<<wall<<",\"rows\":"<<Rows<<",\"columns\":"<<K<<",\"experts\":512,\"selected_experts\":10,\"wg\":64,\"sg\":32,\"diagnostic_only\":true}\n"<<std::flush;
  }
 }q.wait_and_throw();guard();
}
int main(int argc,char**argv){try{
 if(argc!=2||std::string(argv[1])!="--coordinator-admitted-device-window")throw std::runtime_error("coordinator admission required");
 std::signal(SIGTERM,stop);std::signal(SIGINT,stop);
 sycl::queue q(sycl::gpu_selector_v,{sycl::property::queue::enable_profiling{},sycl::property::queue::in_order{}});
 bench<iq3::Type::IQ2_S,2560,640>(q);
 std::cout<<"{\"kind\":\"summary\",\"passed\":true,\"drained\":true,\"rows\":640,\"columns\":2560,\"experts\":512,\"selected_experts\":10,\"diagnostic_only\":true}\n"<<std::flush;return 0;
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
