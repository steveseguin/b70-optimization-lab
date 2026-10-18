// Coordinator-only pair diagnostic; no model performance claim.
#include "p90_expert.hpp"
#include "p100_down.hpp"
#include "p119_warm.hpp"
#include "p119_cache_probe.hpp"
#include <atomic>
#include <csignal>
#include <fstream>
#include <iostream>
namespace ownrt {std::uint64_t next_handle(){static std::atomic<std::uint64_t> n{1};return n.fetch_add(1);}}
static volatile std::sig_atomic_t stopped=0;
static void stop(int){stopped=1;}
static void guard(){if(stopped)throw std::runtime_error("coordinator graceful stop");}
struct Buffers{
 sycl::queue&q;std::vector<void*>values;
 ~Buffers(){try{q.wait_and_throw();}catch(...){}for(auto p:values)sycl::free(p,q);}
 void*alloc(size_t n){auto*p=sycl::malloc_device(n,q);if(!p)throw std::bad_alloc();values.push_back(p);return p;}
};
static uint64_t ns(const sycl::event&e){return e.get_profiling_info<sycl::info::event_profiling::command_end>()-e.get_profiling_info<sycl::info::event_profiling::command_start>();}
void bench(sycl::queue&q,const std::vector<iq3::Route>&captured){
 constexpr unsigned count=10,experts=512,gate_rows=640,down_rows=2560;
 constexpr size_t gate_stride=840,down_stride=360,scrub_bytes=536870912;
 Buffers b{q,{}};
 auto*gate=(uint8_t*)b.alloc(size_t(experts)*gate_rows*gate_stride);
 auto*up=(uint8_t*)b.alloc(size_t(experts)*gate_rows*gate_stride);
 auto*down=(uint8_t*)b.alloc(size_t(experts)*down_rows*down_stride);
 auto*x=(uint16_t*)b.alloc(2560*2);auto*y=(uint16_t*)b.alloc(gate_rows*count*2);
 auto*uy=(uint16_t*)b.alloc(gate_rows*count*2);auto*act=(uint16_t*)b.alloc(gate_rows*count*2);
 auto*dy=(uint16_t*)b.alloc(down_rows*count*2);
 auto*gate_route=(iq3::Route*)b.alloc(count*sizeof(iq3::Route));auto*down_route=(iq3::Route*)b.alloc(count*sizeof(iq3::Route));
 auto*gs=(uint32_t*)b.alloc(count*4);auto*us=(uint32_t*)b.alloc(count*4);auto*ds=(uint32_t*)b.alloc(count*4);
 auto*control=(uint32_t*)b.alloc(12);auto*scrub=(uint32_t*)b.alloc(scrub_bytes);auto*scrub_sink=(uint32_t*)b.alloc(65536*4);
 q.memset(scrub,0x6d,scrub_bytes).wait_and_throw();
 auto evict=[&]{q.parallel_for(sycl::range<1>(65536),[=](sycl::id<1>i){uint32_t sum=0;for(size_t line=i[0];line<scrub_bytes/64;line+=65536)sum^=scrub[line*16];scrub_sink[i[0]]=sum;}).wait_and_throw();};
 uint32_t seed=119;auto next=[&]{seed=seed*1664525u+1013904223u;return seed;};
 for(unsigned stream=0;stream<3;++stream){bool is_down=stream==2;auto type=is_down?iq3::Type::IQ4_NL:iq3::Type::IQ2_S;
  unsigned rows=is_down?down_rows:gate_rows,K=is_down?640:2560;size_t stride=is_down?down_stride:gate_stride;
  auto rawstride=p49bgemv::source_row_bytes(type,K);auto block=iq3::layout(type);auto*w=stream==0?gate:stream==1?up:down;
  for(unsigned first=0;first<experts*rows;first+=256){guard();std::vector<uint8_t>raw(rawstride),packed(256*stride);
   for(unsigned r=0;r<256;++r){for(auto&v:raw)v=next()>>24;
    for(size_t at=0;at<raw.size();at+=block.bytes){uint16_t h=0x2400+next()%1024;std::memcpy(raw.data()+at,&h,2);}
    if(is_down)p49bgemv::repack_row(type,K,raw.data(),packed.data()+r*stride);else p90::expert_repack(K,raw.data(),packed.data()+r*stride);
   }
   if(is_down)packed=p100::transpose(packed.data(),256);
   q.memcpy(w+size_t(first)*stride,packed.data(),packed.size()).wait_and_throw();
  }
 }
 std::vector<uint16_t>hx(2560);for(auto&v:hx)v=iq3::bf16_bits(float(int(next()%63)-31)/32.f);
 q.memcpy(x,hx.data(),hx.size()*2).wait_and_throw();uint32_t hc[3]={0,1,0};
 std::array<void*,19>gp{},dp{};
 gp[0]=gate;gp[1]=up;gp[2]=x;gp[3]=y;gp[4]=uy;gp[5]=gate_route;gp[6]=gs;gp[7]=us;gp[9]=down;
 dp[0]=down;dp[2]=act;dp[3]=dy;dp[5]=down_route;dp[6]=ds;
 for(auto*p:{&gp,&dp}){(*p)[16]=control;(*p)[17]=control+1;(*p)[18]=control+2;}
 p90exp::Kernel<iq3::Type::IQ2_S,2560,64,false,true>production;p119::Kernel candidate;p100::Kernel<2>down_kernel;
 auto launch=[&](bool warm){
  // Exactly one token at a time, as in the engine's serialized M=2 execution.
  auto g=warm?candidate.submit(q,gp,{}):production.submit(q,gp,{});
  auto a=q.submit([&](sycl::handler&h){h.depends_on(g);h.parallel_for(sycl::range<1>(gate_rows*count),[=](sycl::id<1>i){act[i]=p39::activation(y[i],uy[i]);});});
  auto d=down_kernel.submit(q,dp,{a});d.wait_and_throw();return std::array<sycl::event,3>{g,a,d};
 };
 auto poison=[&]{q.memset(y,0xa5,gate_rows*count*2);q.memset(uy,0xa5,gate_rows*count*2);q.memset(act,0xa5,gate_rows*count*2);q.memset(dy,0xa5,down_rows*count*2);for(auto*s:{gs,us,ds})q.memset(s,0xa5,count*4);q.memcpy(control,hc,12).wait_and_throw();};
 auto bytes=[&]{std::vector<uint8_t>v((3*gate_rows+down_rows)*count*2+3*count*4+12);size_t at=0;
  auto copy=[&](void*src,size_t n){q.memcpy(v.data()+at,src,n).wait_and_throw();at+=n;};
  for(auto*p:{y,uy,act})copy(p,gate_rows*count*2);copy(dy,down_rows*count*2);for(auto*s:{gs,us,ds})copy(s,count*4);copy(control,12);return v;
 };
 for(unsigned ri=0;ri<captured.size()/count;++ri){guard();iq3::Route selected[10];for(unsigned i=0;i<count;++i){selected[i]=captured[ri*count+i];selected[i].row_count=gate_rows;}
  q.memcpy(gate_route,selected,sizeof(selected));q.memcpy(down_route,captured.data()+ri*count,sizeof(selected)).wait_and_throw();
  poison();evict();launch(false);auto expected=bytes();
  poison();evict();launch(true);
  if(bytes()!=expected)throw std::runtime_error("candidate gate/up/activation/down/status/control bytes differ");
  std::cout<<"{\"kind\":\"correctness\",\"route\":"<<ri<<",\"all_bytes_exact\":true,\"gate_exact\":true,\"up_exact\":true,\"activation_exact\":true,\"down_exact\":true,\"status_exact\":true,\"control_exact\":true}\n";
  for(unsigned rep=0;rep<2;++rep)for(unsigned pos=0;pos<2;++pos){guard();bool warm=pos^(rep&1);
   poison();evict();auto events=launch(warm);
   if(bytes()!=expected)throw std::runtime_error("timed sample output/status/control bytes differ");
   auto gn=ns(events[0]),an=ns(events[1]),dn=ns(events[2]);
   std::cout<<"{\"kind\":\"sample\",\"view\":\""<<(warm?"p119":"production")<<"\",\"route\":"<<ri<<",\"repeat\":"<<rep<<",\"position\":"<<pos<<",\"gate_ns\":"<<gn<<",\"activation_ns\":"<<an<<",\"down_ns\":"<<dn<<",\"event_ns\":"<<(gn+dn)<<",\"all_bytes_exact\":true,\"rows_gate\":640,\"rows_down\":2560,\"count\":10,\"experts\":512,\"scrub_bytes\":536870912,\"scrub_between_operators\":false,\"diagnostic_only\":true}\n";
  }std::cout<<std::flush;
 }q.wait_and_throw();guard();
}
int main(int argc,char**argv){try{
 if(argc!=3||std::string(argv[1])!="--coordinator-admitted-device-window")throw std::runtime_error("coordinator admission and real route payload required");
 std::ifstream in(argv[2],std::ios::binary);std::vector<uint8_t>raw((std::istreambuf_iterator<char>(in)),{});
 if(!in||raw.size()!=384*120)throw std::runtime_error("exactly384 captured real routes required");
 std::vector<iq3::Route>routes(raw.size()/12);std::memcpy(routes.data(),raw.data(),raw.size());
 for(auto r:routes)if(r.expert_id>=512||r.row_begin||r.row_count!=2560)throw std::runtime_error("captured route shape");
 std::signal(SIGTERM,stop);std::signal(SIGINT,stop);
 {sycl::queue q(sycl::gpu_selector_v,{sycl::property::queue::enable_profiling{},sycl::property::queue::in_order{}});p119_cache::probe(q,guard);guard();bench(q,routes);q.wait_and_throw();}
 std::cout<<"{\"kind\":\"summary\",\"passed\":true,\"drained\":true,\"route_count\":384,\"candidates\":[\"p119\"],\"diagnostic_only\":true}\n"<<std::flush;return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
